"""gouda_monitor node (ND-02) — stage 5-2 scope: HMI for mode and record state, mode operation buttons, /config.

Subscribes mode/state (IFD-01, transient_local), record/status (IFD-12, transient_local) and log/decision (IFD-28);
reads the node names on the graph periodically (RQ-I033). Calls the mode services of gouda_mode_manager (IFD-02..07)
and the record services of gouda_recorder (IFD-08..11) when a button is pressed; it holds no mission state of its own
(SO-03: only the sensor /config, the selection inputs and unsaved edits).

The page is served on 127.0.0.1 by MonitorServer (no screen forwarding, RQ-I044). A display interruption is not a stop
trigger; after a reconnect the page fetches the current latched state (DEC-014, TS-10).

Settings: data_root (PRM-25) for the /config file and the URL file; monitor_port (PRM-26, 0 = OS-chosen) as launch
arguments. No numeric value is hard-coded (RQ-I076).
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
from gouda_interfaces.msg import SoftwareMode, DecisionEvent
from gouda_interfaces.srv import StartAutonomy
from ament_index_python.packages import get_package_share_directory

from gouda_core.monitor_core import MonitorCore, SensorConfig
from gouda_core.monitor_server import MonitorServer

LATCHED = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=1)
DECISION_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE, history=HistoryPolicy.KEEP_LAST, depth=50)

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
        self.core = MonitorCore(clock=self._now)
        self.config = SensorConfig(data_root / 'config' / 'sensor_config.json')
        self._lock = threading.Lock()
        self.create_subscription(SoftwareMode, 'mode/state', self._on_mode, LATCHED)
        self.create_subscription(DiagnosticArray, 'record/status', self._on_record, LATCHED)
        self.create_subscription(DecisionEvent, 'log/decision', self._on_decision, DECISION_QOS)
        self.cmd_clients = {name: self.create_client(Trigger, srv) for name, srv in TRIGGER_COMMANDS.items()}
        self.start_client = self.create_client(StartAutonomy, 'mode/start_autonomy')
        self.create_timer(2.0, self._poll_nodes)  # graph poll for the node list (display only; not a stop condition)
        web_dir = Path(get_package_share_directory('gouda_core')) / 'web'
        self.server = MonitorServer(web_dir, self._state, self._config_snapshot, self._command, self._config_update,
                                    port=self.get_parameter('monitor_port').get_parameter_value().integer_value,
                                    url_file=data_root / 'run' / 'monitor.url')
        url = self.server.start()
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
            return self.core.snapshot()

    def _config_snapshot(self) -> dict:
        with self._lock:
            return self.config.snapshot()

    def _config_update(self, body: dict) -> dict:
        with self._lock:
            ok, msg = self.config.update(body, self._now())
            self.core.on_command_result('config_update', ok, msg)
        self.server.notify(self.core.connection_revision)
        return {'ok': ok, 'message': msg, 'config': self._config_snapshot()}

    def _command(self, name: str, body: dict) -> dict:
        if name == 'start_autonomy':
            req = StartAutonomy.Request(); req.request_id = str(body.get('request_id', ''))
            for k in ('map_id', 'map_revision', 'map_hash', 'waypoint_set_id', 'waypoint_set_revision', 'waypoint_set_hash'):
                setattr(req, k, str(body.get(k, '')))
            ok, msg = self._call(self.start_client, req, lambda r: (bool(r.accepted), r.message))
        elif name in self.cmd_clients:
            ok, msg = self._call(self.cmd_clients[name], Trigger.Request(), lambda r: (bool(r.success), r.message))
        else:
            ok, msg = False, f'unknown command {name!r}'
        with self._lock:
            self.core.on_command_result(name, ok, msg)
        self.server.notify(self.core.connection_revision)
        return {'ok': ok, 'message': msg}

    def _call(self, client, request, extract):
        if not client.wait_for_service(timeout_sec=1.0):
            return False, f'service {client.srv_name} is not available (node not running?)'
        fut = client.call_async(request)
        done = threading.Event(); fut.add_done_callback(lambda f: done.set())
        if not done.wait(timeout=5.0):
            return False, f'service {client.srv_name} did not answer within 5 s'
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
