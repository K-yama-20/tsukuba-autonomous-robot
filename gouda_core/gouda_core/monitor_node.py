"""gouda_monitor node (ND-02) — stage 5-2 scope: HMI for mode and record state, mode operation buttons, /config.

Subscribes mode/state (IFD-01, transient_local), record/status (IFD-12, transient_local) and log/decision (IFD-28);
reads the node names on the graph periodically (RQ-I033). Calls the mode services of gouda_mode_manager (IFD-02..07)
and the record services of gouda_recorder (IFD-08..11) when a button is pressed; it holds no mission state of its own
(SO-03: only the sensor /config, the selection inputs and unsaved edits).

The page is served on 127.0.0.1 by MonitorServer (no screen forwarding, RQ-I044). A display interruption is not a stop
trigger; after a reconnect the page fetches the current latched state (DEC-014, TS-10).

Settings: data_root (PRM-25) for the /config file and the URL file; monitor_port (PRM-26, 0 = OS-chosen) as launch
arguments. UI periods and waits are ROS parameters of this relay node (PRM-27..32, DEC-073) read from the generated file
design/generated/params/gouda_monitor.yaml; they are software defaults, not vehicle values, and are never reused as a
drive timeout. A timed-out call is shown as a failure; there is no automatic retry. The effective settings are recorded
as a DecisionEvent (event=settings) at start-up and on every /config save. No numeric value is hard-coded (RQ-I076).
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from std_srvs.srv import Trigger
from diagnostic_msgs.msg import DiagnosticArray
from rclpy.parameter import Parameter
from gouda_interfaces.msg import SoftwareMode, DecisionEvent
from gouda_interfaces.srv import StartAutonomy
from ament_index_python.packages import get_package_share_directory

from gouda_core.monitor_core import MonitorCore, SensorConfig
from gouda_core.monitor_server import MonitorServer
from gouda_core.map_database import MapDatabase
from gouda_core import waypoints as wpmod
from gouda_core import speed_mask
from gouda_core import png as pngmod

LATCHED = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=1)
DECISION_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=50)  # IFD-28 (DEC-072)
# UI periods and waits (PRM-27..32): declared here (the relay node), values come from the generated parameter file.
def optional_double(node, name):
    """Value of a declared-but-possibly-unset DOUBLE parameter, or None (rclpy raises on an uninitialised parameter)."""
    try:
        prm = node.get_parameter(name)
    except Exception:
        return None
    return prm.value if prm.type_ == Parameter.Type.DOUBLE else None

UI_PARAMS = ['ui_node_list_poll_period_s', 'ui_sse_keepalive_s', 'ui_service_ready_wait_s', 'ui_service_response_wait_s', 'ui_pause_service_ready_wait_s', 'ui_pause_service_response_wait_s']

# Button -> service. Mode operations go to gouda_mode_manager (ND-03), record operations to gouda_recorder (ND-04).
TRIGGER_COMMANDS = {
    'pause': 'mode/pause', 'resume': 'mode/resume', 'end_autonomy': 'mode/end_autonomy',
    'start_mapping': 'mode/start_mapping', 'end_mapping': 'mode/end_mapping',
    'record_log_start': 'record/log/start', 'record_log_stop': 'record/log/stop',
    'record_rosbag_start': 'record/rosbag/start', 'record_rosbag_stop': 'record/rosbag/stop',
}


class MonitorNode(Node):
    def __init__(self):
        super().__init__('gouda_monitor')
        self.declare_parameter('data_root', '')     # PRM-25
        self.declare_parameter('monitor_port', 0)   # PRM-26; 0 = OS-chosen, URL written to <data_root>/run/monitor.url
        root = self.get_parameter('data_root').get_parameter_value().string_value
        if not root:
            raise RuntimeError('data_root is not set (PRM-25). Pass it from gouda.sh / the launch file.')
        data_root = Path(os.path.expanduser(root))
        for key in UI_PARAMS:
            self.declare_parameter(key, Parameter.Type.DOUBLE)
        self.declare_parameter('speed_mask_half_width_m', Parameter.Type.DOUBLE)   # PRM-19 (unresolved: 実機調整; a save request may carry an explicit value)
        self.declare_parameter('speed_mask_step_mps', Parameter.Type.DOUBLE)       # PRM-20 (unresolved: depends on Q-06)
        self.ui = {}
        for key in UI_PARAMS:
            v = optional_double(self, key)
            if v is None:
                raise RuntimeError(f'{key} is not set: pass design/generated/params/gouda_monitor.yaml (PRM-27..32 are declared there)')
            self.ui[key] = v
        self.core = MonitorCore(clock=self._now)
        self.core.settings = {'ui': dict(self.ui), 'declared_by': 'gouda_monitor (relay node; the browser page declares nothing)', 'source': 'design/generated/params/gouda_monitor.yaml (PRM-27..32, DEC-073)', 'auto_retry': 'none: a timed-out call is shown as a failure'}
        self.config = SensorConfig(data_root / 'config' / 'sensor_config.json')
        self.maps_index_path = data_root / 'maps' / 'index.json'   # IFD-29 (read-only view of the map database)
        self.map_db = MapDatabase(data_root / 'maps')
        self.routes = wpmod.RouteDatabase(data_root / 'routes')    # IFD-30 / IFD-41 (waypoint_manager, stage 5-4)
        self._lock = threading.Lock()
        self.create_subscription(SoftwareMode, 'mode/state', self._on_mode, LATCHED)
        self.create_subscription(DiagnosticArray, 'record/status', self._on_record, LATCHED)
        self.create_subscription(DecisionEvent, 'log/decision', self._on_decision, DECISION_QOS)
        # IFD-38 /esp32/status (stage 5-5): display/diagnosis only, never a stop condition (DEC-006, TS-12). The stale
        # threshold is PRM-15 (unresolved; trial file in stub tests). Without it, STALE is never shown (freshness verdict says so).
        self.declare_parameter('esp32_status_stale_s', Parameter.Type.DOUBLE)
        self.core.stale_after_esp32_s = optional_double(self, 'esp32_status_stale_s')
        self.create_subscription(DiagnosticArray, '/esp32/status', self._on_esp32, QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE, history=HistoryPolicy.KEEP_LAST, depth=10))
        self.cmd_clients = {name: self.create_client(Trigger, srv) for name, srv in TRIGGER_COMMANDS.items()}
        self.start_client = self.create_client(StartAutonomy, 'mode/start_autonomy')
        self.decision_pub = self.create_publisher(DecisionEvent, 'log/decision', DECISION_QOS)   # event=settings only (DEC-073)
        self.create_timer(self.ui['ui_node_list_poll_period_s'], self._poll_nodes)  # PRM-27; display only, not a stop condition
        web_dir = Path(get_package_share_directory('gouda_core')) / 'web'
        self.server = MonitorServer(web_dir, self._state, self._config_snapshot, self._command, self._config_update,
                                    port=self.get_parameter('monitor_port').get_parameter_value().integer_value,
                                    url_file=data_root / 'run' / 'monitor.url', keepalive_s=self.ui['ui_sse_keepalive_s'],   # PRM-28
                                    get_routes={'/api/map/': self._get_map_png, '/api/routes': self._get_routes, '/api/route/': self._get_route},
                                    post_routes={'/api/waypoints/save': self._save_waypoints})
        url = self.server.start()
        self._publish_settings('startup')
        self.get_logger().info(f'gouda_monitor page: {url} (127.0.0.1 only; open it on this PC desktop)')

    def _now(self) -> float:
        t = self.get_clock().now().seconds_nanoseconds(); return t[0] + t[1] * 1e-9

    # ---- inputs ----
    def _on_mode(self, m: SoftwareMode):
        with self._lock:
            self.core.on_mode({'stamp': m.header.stamp.sec + m.header.stamp.nanosec * 1e-9, 'mode': int(m.mode), 'processing_state': m.processing_state,
                               'run_id': m.run_id, 'remaining_waypoints': int(m.remaining_waypoints), 'current_section': int(m.current_section),
                               'stop_reason': m.stop_reason, 'speed_limit_application_state': m.speed_limit_application_state,
                               'previous_mode': int(m.previous_mode), 'human_pause_or_end_recorded': bool(m.human_pause_or_end_recorded),
                               'initial_pose_required': bool(m.initial_pose_required), 'state_revision': int(m.state_revision)})
        self.server.notify(self.core.connection_revision)

    def _on_record(self, arr: DiagnosticArray):
        for st in arr.status:
            if st.name == 'gouda_recorder':
                with self._lock:
                    self.core.on_record({kv.key: kv.value for kv in st.values} | {'level': int.from_bytes(st.level, 'big') if isinstance(st.level, bytes) else int(st.level), 'message': st.message})
        self.server.notify(self.core.connection_revision)

    def _on_esp32(self, arr: DiagnosticArray):
        for st in arr.status:
            if st.name == 'esp32':
                with self._lock:
                    self.core.on_esp32({kv.key: kv.value for kv in st.values} | {'message': st.message, 'hardware_id': st.hardware_id})
        self.server.notify(self.core.connection_revision)

    def _on_decision(self, d: DecisionEvent):
        with self._lock:
            self.core.on_decision({'stamp': d.header.stamp.sec + d.header.stamp.nanosec * 1e-9, 'node': d.node, 'event': d.event, 'transition_id': d.transition_id,
                                   'reason': d.reason, 'run_id': d.run_id, 'section_id': int(d.section_id), 'details': d.details})
        self.server.notify(self.core.connection_revision)

    def _poll_nodes(self):
        try:
            names = [f'{ns.rstrip("/")}/{n}' if ns != '/' else f'/{n}' for n, ns in self.get_node_names_and_namespaces() if not n.startswith('_ros2cli')]  # the ros2 CLI daemon is not part of the system
        except Exception:
            return
        with self._lock:
            if sorted(names) != self.core.nodes:
                self.core.on_nodes(names)
        self.server.notify(self.core.connection_revision)

    # ---- server callbacks (run on HTTP threads) ----
    def _state(self) -> dict:
        with self._lock:
            snap = self.core.snapshot()
        try:
            snap['maps'] = json.loads(self.maps_index_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            snap['maps'] = {'origins': [], 'note': 'map database index not found (no mapping session yet)'}
        try:
            snap['routes'] = self.routes.index()
        except Exception:
            snap['routes'] = {'sets': []}
        snap['mask_params'] = {'half_width_m': optional_double(self, 'speed_mask_half_width_m'), 'step_mps': optional_double(self, 'speed_mask_step_mps')}
        return snap

    def _config_snapshot(self) -> dict:
        with self._lock:
            return self.config.snapshot()

    # ---- waypoint_manager (IFD-30 / IFD-41, stage 5-4) ----
    def _get_routes(self, rest, query):
        return self.routes.index()

    def _get_route(self, rest, query):
        parts = [x for x in rest.split('/') if x]
        if len(parts) < 2: return {'ok': False, 'message': 'route/<set_id>/<revision>'}
        ws = self.routes.load(parts[0], int(parts[1])); man = self.routes.manifest(parts[0], int(parts[1]))
        if ws is None: return {'ok': False, 'message': 'not found'}
        return {'ok': True, 'set': ws.to_dict(), 'manifest': man}

    def _get_map_png(self, rest, query):
        """/api/map/<origin>/<revision>/map.png | mask.png?set=<id>&rev=<n>: PGM converted on the fly for the browser."""
        parts = [x for x in rest.split('/') if x]
        if len(parts) < 3: return {'ok': False, 'message': 'map/<origin>/<revision>/map.png'}
        origin, rev, what = parts[0], int(parts[1]), parts[2]
        if what == 'map.png':
            d = self.map_db.root / origin / 'converted' / f'{rev:03d}'
            pgm = (d / 'map.pgm').read_bytes(); data, w, h = pngmod.pgm_to_png(pgm)
            return 200, 'image/png', data
        if what == 'geometry.json':
            d = self.map_db.root / origin / 'converted' / f'{rev:03d}'
            g = speed_mask.MapGeometry.from_map_yaml(d / 'map.yaml'); man = self.map_db.converted_manifest(origin, rev) or {}
            return {'ok': True, 'resolution': g.resolution, 'origin_x': g.origin_x, 'origin_y': g.origin_y, 'width': g.width, 'height': g.height, 'content_hash': man.get('content_hash', '')}
        if what == 'mask.png':
            q = dict(x.split('=', 1) for x in query.split('&') if '=' in x)
            d = self.routes.root / q['set'] / f"{int(q['rev']):03d}"
            pgm = (d / 'speed_mask.pgm').read_bytes(); data, w, h = pngmod.pgm_to_png(pgm)
            return 200, 'image/png', data
        return {'ok': False, 'message': 'unknown resource'}

    def _save_waypoints(self, rest, body: dict) -> dict:
        """Save a waypoint set with its speed mask (IFD-30 / IFD-41). Overlap with different limits warns; never refuses (DEC-059 A)."""
        try:
            ws = wpmod.WaypointSet.from_dict(body.get('set', {}))
        except Exception as e:
            return {'ok': False, 'message': f'invalid waypoint set: {e}'}
        errors = ws.validate()
        if errors: return {'ok': False, 'message': '; '.join(errors)}
        man = self.map_db.converted_manifest(ws.map_origin_id, ws.map_revision)
        if man is None: return {'ok': False, 'message': f'converted map {ws.map_origin_id}/{ws.map_revision} not found'}
        if man['content_hash'] != ws.map_content_hash: return {'ok': False, 'message': 'map content hash does not match the stored converted map (RQ-I078)'}
        hw = body.get('half_width_m'); st = body.get('step_mps')
        hw = float(hw) if hw not in (None, '') else optional_double(self, 'speed_mask_half_width_m')
        st = float(st) if st not in (None, '') else optional_double(self, 'speed_mask_step_mps')
        if hw is None or st is None:
            return {'ok': False, 'message': 'speed mask settings missing: half_width_m (PRM-19) and step_mps (PRM-20) are unresolved; give them in the request (実機調整値として記録される)'}
        geom = speed_mask.MapGeometry.from_map_yaml(self.map_db.root / ws.map_origin_id / 'converted' / f'{ws.map_revision:03d}' / 'map.yaml')
        set_id, rev, tmp = self.routes.begin(body.get('set_id') or None)
        try:
            res = speed_mask.generate([(w.x, w.y) for w in ws.waypoints], ws.section_limits_mps, geom, hw, st)
            files = speed_mask.write_mask(res, geom, tmp, 'speed_filter_mask', 'costmap_filter_info')
        except Exception as e:
            return {'ok': False, 'message': self.routes.abort(tmp, str(e))}
        gen = {'half_width_m': hw, 'step_mps': st, 'source': 'request' if body.get('half_width_m') not in (None, '') else 'parameter', 'painted_cells': res.painted_cells, 'overlap_cells': res.overlap_cells, 'sections_clipped': res.sections_clipped}
        ok, msg, manifest = self.routes.publish(set_id, rev, tmp, ws, files, res.warnings, gen)
        with self._lock:
            self.core.on_command_result('waypoints_save', ok, msg)
        self.server.notify(self.core.connection_revision)
        return {'ok': ok, 'message': msg, 'set_id': set_id, 'revision': rev, 'warnings': res.warnings, 'manifest': manifest}

    def _config_update(self, body: dict) -> dict:
        with self._lock:
            ok, msg = self.config.update(body, self._now())
            self.core.on_command_result('config_update', ok, msg)
        self.server.notify(self.core.connection_revision)
        if ok: self._publish_settings('config_saved')
        return {'ok': ok, 'message': msg, 'config': self._config_snapshot()}

    def _publish_settings(self, reason: str):
        """Record the effective settings (UI parameters and /config revision) as a DecisionEvent (RQ-I015, DEC-073)."""
        d = DecisionEvent(); d.header.stamp = self.get_clock().now().to_msg(); d.node = 'gouda_monitor'
        d.event = 'settings'; d.transition_id = ''; d.reason = f'settings recorded ({reason})'; d.run_id = ''; d.section_id = -1
        with self._lock:
            cfg = self.config.snapshot()
        d.details = json.dumps({'ui_parameters': self.ui, 'config_revision': cfg['config_revision'], 'config_values': cfg['values'], 'reason': reason}, ensure_ascii=False)
        self.decision_pub.publish(d)

    def _command(self, name: str, body: dict) -> dict:
        if name == 'start_autonomy':
            req = StartAutonomy.Request(); req.request_id = str(body.get('request_id', ''))
            for k in ('map_id', 'map_revision', 'map_hash', 'waypoint_set_id', 'waypoint_set_revision', 'waypoint_set_hash'):
                setattr(req, k, str(body.get(k, '')))
            ok, msg = self._call(self.start_client, req, lambda r: (bool(r.accepted), r.message), self.ui['ui_service_ready_wait_s'], self.ui['ui_service_response_wait_s'])
        elif name == 'pause':   # the pause button has its own waits (PRM-31 / PRM-32, DEC-073)
            ok, msg = self._call(self.cmd_clients[name], Trigger.Request(), lambda r: (bool(r.success), r.message), self.ui['ui_pause_service_ready_wait_s'], self.ui['ui_pause_service_response_wait_s'])
        elif name in self.cmd_clients:
            ok, msg = self._call(self.cmd_clients[name], Trigger.Request(), lambda r: (bool(r.success), r.message), self.ui['ui_service_ready_wait_s'], self.ui['ui_service_response_wait_s'])
        else:
            ok, msg = False, f'unknown command {name!r}'
        with self._lock:
            self.core.on_command_result(name, ok, msg)
        self.server.notify(self.core.connection_revision)
        return {'ok': ok, 'message': msg}

    def _call(self, client, request, extract, ready_wait_s, response_wait_s):
        # No automatic retry: a timed-out call is reported as a failure and the human decides whether to press again.
        if not client.wait_for_service(timeout_sec=ready_wait_s):
            return False, f'service {client.srv_name} is not available within {ready_wait_s} s (node not running?); no automatic retry'
        fut = client.call_async(request)
        done = threading.Event(); fut.add_done_callback(lambda f: done.set())
        if not done.wait(timeout=response_wait_s):
            return False, f'service {client.srv_name} did not answer within {response_wait_s} s; no automatic retry'
        if fut.exception() is not None:
            return False, f'service {client.srv_name} failed: {fut.exception()}'
        return extract(fut.result())

    def destroy_node(self):
        self.server.stop(); super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = MonitorNode()
    executor = rclpy.executors.MultiThreadedExecutor(num_threads=4)  # service futures complete while HTTP threads wait
    executor.add_node(node)
    try: executor.spin()
    except KeyboardInterrupt: pass
    finally:
        node.destroy_node(); rclpy.try_shutdown()


if __name__ == '__main__': main()
