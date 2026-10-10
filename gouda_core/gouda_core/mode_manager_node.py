"""gouda_mode_manager node (ND-03) — stages 5-1 / 5-2 / 5-3.

Stage 5-1: boot transition (TR-01 / TR-02), persisted previous-mode record (SO-01), mode/state (IFD-01) and
DecisionEvents (IFD-28, transient_local, 50).
Stage 5-2: human operation services (IFD-02..07) evaluated by mode_core.request_transition; unimplemented transitions
are refused with their stage; every request is recorded.
Stage 5-3: TR-03 (手動走行 -> 事前地図作成) starts GLIM (ND-06, child process, glim_runner), requests the automatic log start
(IFD-45, asynchronous, never blocks) and records; TR-04 (事前地図作成 -> 手動走行) stops GLIM and waits for its dump,
registers the source map in the map database (IFD-29), starts the conversion action (IFD-37, asynchronous,
processing_state=map_converting until the result), stops the auto-started log (IFD-46) and records. Mapping-mode
exclusivity (RQ-I004): the autonomy estimators ND-07/ND-08 are not active in this build; when they exist, TR-03 must
confirm they are inactive before GLIM starts (guard kept in the design).

Settings: state_root (PRM-25) launch argument; state_publish_period_s (PRM-16, unresolved -> publish on change);
glim_stop_wait_s (PRM-37) from the generated parameter file (trial file in stub tests). GLIM topics/frames are the
design's interface names (IFD-19..22). No numeric value is hard-coded (RQ-I076).
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from std_srvs.srv import Trigger
from gouda_interfaces.msg import SoftwareMode, DecisionEvent, MotionHold
from gouda_interfaces.srv import StartAutonomy
from gouda_interfaces.action import ConvertMap

from gouda_core import mode_core
from gouda_core.glim_runner import GlimRunner, GlimSettings
from gouda_core.map_database import MapDatabase, new_origin_id

LATCHED = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=1)
DECISION_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=50)  # IFD-28 (DEC-072): 保持 50 件、全 publisher を揃える
# Transitions whose actions exist in this build (stage 5-3: mapping start / end).
def optional_double(node, name):
    """Value of a declared-but-possibly-unset DOUBLE parameter, or None (rclpy raises on an uninitialised parameter)."""
    try:
        prm = node.get_parameter(name)
    except Exception:
        return None
    return prm.value if prm.type_ == Parameter.Type.DOUBLE else None

IMPLEMENTED_TRANSITIONS = frozenset({'TR-03', 'TR-04'})
# GLIM wiring from the design's interface names (not settings): IFD-21 points, IFD-22 IMU, IFD-20 frames, IFD-19 odom->base.
GLIM_POINTS_TOPIC = 'sensors/xt32/points'
GLIM_IMU_TOPIC = 'sensors/imu/data'
GLIM_FRAMES = {'lidar': 'xt32_link', 'imu': 'imu_link', 'base': 'base_link', 'odom': 'odom', 'map': 'map'}


class ModeManagerNode(Node):
    def __init__(self):
        super().__init__('gouda_mode_manager')
        self.declare_parameter('state_root', '')                # PRM-25 (launch argument)
        self.declare_parameter('data_root', '')                 # PRM-25 (maps/, mapping work dir)
        self.declare_parameter('state_publish_period_s', 0.0)   # PRM-16; 0.0 means "unresolved: publish on change only"
        self.declare_parameter('glim_stop_wait_s', Parameter.Type.DOUBLE)   # PRM-37; required for TR-04
        root = self.get_parameter('state_root').get_parameter_value().string_value
        if not root:
            raise RuntimeError('state_root is not set (PRM-25). Pass it from gouda.sh / the launch file.')
        data_root = self.get_parameter('data_root').get_parameter_value().string_value or str(Path(root).parent)
        self.data_root = Path(os.path.expanduser(data_root))
        self.record_path = Path(os.path.expanduser(root)) / 'previous_mode_record.json'
        self.state_pub = self.create_publisher(SoftwareMode, 'mode/state', LATCHED)
        # IFD-40 control/motion_hold (stage 5-5, DEC-004): hold=true in every mode except 自律走行; published with mode/state
        # (on change and, when PRM-16 is set, periodically). transient_local so a restarted ND-11 gets the latest value.
        self.hold_pub = self.create_publisher(MotionHold, 'control/motion_hold', LATCHED)
        self.decision_pub = self.create_publisher(DecisionEvent, 'log/decision', DECISION_QOS)
        self._lock = threading.RLock()
        record = mode_core.PreviousModeRecord.load(self.record_path)
        self.decision = mode_core.decide_boot(record)
        self.state = self.decision.state
        mode_core.record_after_boot(self.decision).save(self.record_path)
        self._publish_state()
        self._publish_decision('boot', self.decision.transition_id, self.decision.reason,
                               dict(self.decision.details, record_path=str(self.record_path), record_found=self.decision.record_found))
        # Stage 5-3 helpers
        self.glim = GlimRunner(GlimSettings(points_topic=GLIM_POINTS_TOPIC, imu_topic=GLIM_IMU_TOPIC, lidar_frame_id=GLIM_FRAMES['lidar'],
                                            imu_frame_id=GLIM_FRAMES['imu'], base_frame_id=GLIM_FRAMES['base'], odom_frame_id=GLIM_FRAMES['odom'], map_frame_id=GLIM_FRAMES['map']))
        self.maps = MapDatabase(self.data_root / 'maps')
        self.convert_client = ActionClient(self, ConvertMap, 'map/convert')
        self.mapping_origin_id = None
        # Human operation services (IFD-02..07). Trigger for all but start_autonomy (IFD-02 custom request).
        for event, name in [('pause', 'mode/pause'), ('resume', 'mode/resume'), ('end_autonomy', 'mode/end_autonomy'),
                            ('start_mapping', 'mode/start_mapping'), ('end_mapping', 'mode/end_mapping')]:
            self.create_service(Trigger, name, self._trigger_handler(event))
        self.create_service(StartAutonomy, 'mode/start_autonomy', self._start_autonomy)
        period = self.get_parameter('state_publish_period_s').get_parameter_value().double_value
        if period > 0:
            self.create_timer(period, self._publish_state)
        else:
            self.get_logger().info('state_publish_period_s (PRM-16) is unresolved: mode/state is published on change only (transient_local)')
        self.get_logger().info(f'boot transition {self.decision.transition_id}: mode={self.state.mode} ({self.decision.reason})')

    # ---- services ----
    def _trigger_handler(self, event):
        def handle(request, response):
            r = self._request(event, {})
            response.success, response.message = r.accepted, r.reason
            return response
        return handle

    def _start_autonomy(self, request, response):
        details = {'request_id': request.request_id, 'map_id': request.map_id, 'map_revision': request.map_revision,
                   'waypoint_set_id': request.waypoint_set_id, 'waypoint_set_revision': request.waypoint_set_revision}
        r = self._request('start_autonomy', details)
        response.accepted, response.message, response.run_id = r.accepted, r.reason, (r.new_state.run_id if r.accepted and r.new_state else '')
        return response

    def _request(self, event, details):
        with self._lock:
            r = mode_core.request_transition(event, self.state, IMPLEMENTED_TRANSITIONS)
            if r.accepted:
                ok, why = self._perform(r.transition_id)
                if not ok:
                    r = mode_core.RequestResult(False, r.transition_id, f'refused: {r.transition_id} actions failed: {why}')
            self._publish_decision('human_request', r.transition_id, r.reason, dict(details, event=event, accepted=r.accepted, mode=self.state.mode))
            (self.get_logger().info if r.accepted else self.get_logger().warning)(f'{event}: {r.reason}')
            if r.accepted and r.new_state is not None:
                self._set_state(r.new_state)
            return r

    def _set_state(self, new_state):
        self.state = new_state
        mode_core.PreviousModeRecord(mode=self.state.mode, human_pause_or_end=self.state.human_pause_or_end_recorded,
                                     run_id=self.state.run_id, state_revision=self.state.state_revision).save(self.record_path)
        self._publish_state()

    # ---- transition actions that exist in this build ----
    def _perform(self, transition_id):
        if transition_id == 'TR-03': return self._tr03_start_mapping()
        if transition_id == 'TR-04': return self._tr04_end_mapping()
        return False, 'no actions implemented'

    def _tr03_start_mapping(self):
        """TR-03: start GLIM (ND-06); request the automatic log start (IFD-45) without waiting; record settings."""
        if self.glim.running:
            return False, 'GLIM is already running'
        origin_id = new_origin_id(); work = self.data_root / 'mapping' / origin_id
        try:
            run = self.glim.start(work, work / 'glim_dump', work / 'glim.log')
        except Exception as e:
            self._publish_decision('mapping_start_failed', 'TR-03', f'GLIM start failed: {e}', {'origin_id': origin_id})
            return False, f'GLIM start failed: {e}'
        self.mapping_origin_id = origin_id
        self._publish_decision('mapping_started', 'TR-03', f'GLIM started (pid {run.pid}); origin {origin_id}',
                               {'origin_id': origin_id, 'config_dir': str(run.config_dir), 'dump_dir': str(run.dump_dir), 'points_topic': GLIM_POINTS_TOPIC, 'imu_topic': GLIM_IMU_TOPIC, 'frames': GLIM_FRAMES})
        self.request_auto_record('map_start', 'TR-03')   # asynchronous; a failure never stops mapping (DEC-071)
        return True, 'mapping started'

    def _tr04_end_mapping(self):
        """TR-04: stop GLIM and wait for its dump; register the source; start conversion (async); stop the auto log."""
        wait_s = optional_double(self, 'glim_stop_wait_s')
        if wait_s is None:
            return False, 'glim_stop_wait_s (PRM-37) is unresolved: pass the generated parameter file (trial file in stub tests)'
        origin_id = self.mapping_origin_id or new_origin_id()
        try:
            run = self.glim.stop(wait_s)
        except Exception as e:
            self._publish_decision('mapping_stop_failed', 'TR-04', f'GLIM stop failed: {e}', {'origin_id': origin_id})
            run = None
        self.mapping_origin_id = None
        self._publish_decision('mapping_stopped', 'TR-04', (run.note if run else 'GLIM was not running'),
                               {'origin_id': origin_id, 'dump_ok': run.dump_ok if run else None, 'submaps': run.submaps if run else 0, 'exit_code': run.exit_code if run else None})
        if run and run.dump_ok:
            ok, msg, manifest = self.maps.register_source(run.dump_dir, origin_id, {'software': 'glim_ros', 'version': 'installed package (DEC-062)', 'config_dir': str(run.config_dir)},
                                                           {'started_at': run.started_at, 'stopped_at': run.stopped_at, 'glim_log': str(run.config_dir.parent / 'glim.log')})
            self._publish_decision('source_map_registered' if ok else 'source_map_not_registered', 'TR-04', msg, {'origin_id': origin_id, 'content_hash': manifest['content_hash'] if manifest else None})
            if ok:
                self._start_conversion(origin_id)
        else:
            self._publish_decision('source_map_not_registered', 'TR-04', 'dump incomplete or GLIM not running: the source is kept where it is and nothing is published (RQ-I009)', {'origin_id': origin_id})
        self.request_auto_record('stop_auto', 'TR-04')
        return True, 'mapping ended'

    def _start_conversion(self, origin_id):
        """IFD-37 map/convert, asynchronous. processing_state shows map_converting until the result (DEC-010)."""
        if not self.convert_client.server_is_ready():
            self._publish_decision('map_convert_not_started', 'TR-04', 'map/convert action server is not available (gouda_map_creator not running?); re-conversion can be requested later', {'origin_id': origin_id})
            return
        goal = ConvertMap.Goal(); goal.origin_id = origin_id; goal.settings_json = ''
        self.state = mode_core.ModeState(**{**self.state.as_dict(), 'processing_state': 'map_converting', 'state_revision': self.state.state_revision + 1}); self._publish_state()
        send = self.convert_client.send_goal_async(goal)
        def on_goal(f):
            gh = f.result()
            if not gh.accepted:
                self._finish_conversion(origin_id, False, 'conversion goal rejected'); return
            gh.get_result_async().add_done_callback(lambda rf: self._finish_conversion(origin_id, rf.result().result.ok, rf.result().result.message, rf.result().result))
        send.add_done_callback(on_goal)

    def _finish_conversion(self, origin_id, ok, message, result=None):
        with self._lock:
            details = {'origin_id': origin_id, 'ok': ok}
            if result is not None and ok:
                details.update({'revision': int(result.revision), 'content_hash': result.content_hash, 'map_yaml_path': result.map_yaml_path})
            self._publish_decision('map_converted' if ok else 'map_convert_failed', 'TR-04', message, details)
            if self.state.processing_state == 'map_converting':
                self.state = mode_core.ModeState(**{**self.state.as_dict(), 'processing_state': 'idle', 'state_revision': self.state.state_revision + 1}); self._publish_state()

    # ---- automatic log start / stop (IFD-44 / IFD-45 / IFD-46). Asynchronous: the transition never waits. ----
    AUTO_RECORD_SERVICES = {'autonomy_start': 'record/log/start_autodrive', 'map_start': 'record/log/start_pre_mapping', 'stop_auto': 'record/log/stop_auto'}

    def _auto_record_client(self, kind):
        if not hasattr(self, '_auto_record_clients'): self._auto_record_clients = {}
        if kind not in self._auto_record_clients:
            self._auto_record_clients[kind] = self.create_client(Trigger, self.AUTO_RECORD_SERVICES[kind])
        return self._auto_record_clients[kind]

    def request_auto_record(self, kind: str, transition_id: str):
        """Call the auto-record service for an accepted human start (kind autonomy_start / map_start) or the auto stop
        (stop_auto) without waiting. The outcome is recorded; a failure never stops the transition (DEC-071)."""
        client = self._auto_record_client(kind); name = self.AUTO_RECORD_SERVICES[kind]
        if not client.service_is_ready():
            self._publish_decision('record_auto_start_failed' if kind != 'stop_auto' else 'record_auto_stop_failed', transition_id,
                                   f'{name} is not available (gouda_recorder not running?); driving is not stopped', {'service': name, 'kind': kind})
            return
        fut = client.call_async(Trigger.Request())
        def done(f):
            try:
                r = f.result(); ok, msg = bool(r.success), r.message
            except Exception as e:
                ok, msg = False, f'{name} failed: {e}'
            self._publish_decision(('record_auto_start' if kind != 'stop_auto' else 'record_auto_stop') + ('' if ok else '_failed'), transition_id, msg, {'service': name, 'kind': kind, 'ok': ok})
        fut.add_done_callback(done)

    # ---- publication ----
    def _publish_state(self):
        s = self.state; m = SoftwareMode()
        m.header.stamp = self.get_clock().now().to_msg()
        m.mode = mode_core.MODE_CODES[s.mode]; m.processing_state = s.processing_state; m.run_id = s.run_id
        m.remaining_waypoints = s.remaining_waypoints; m.current_section = s.current_section; m.stop_reason = s.stop_reason
        m.speed_limit_application_state = s.speed_limit_application_state
        m.previous_mode = mode_core.MODE_CODES.get(s.previous_mode, 0); m.human_pause_or_end_recorded = s.human_pause_or_end_recorded
        m.initial_pose_required = s.initial_pose_required; m.state_revision = s.state_revision
        self.state_pub.publish(m)
        self._publish_motion_hold(m.header.stamp)

    def _publish_motion_hold(self, stamp):
        """IFD-40: neutral request to ND-11. Only 自律走行 releases the hold (DEC-004, RQ-I026)."""
        s = self.state; h = MotionHold(); h.header.stamp = stamp
        h.hold = s.mode != mode_core.MODE_AUTONOMY
        h.mode = mode_core.MODE_CODES[s.mode]
        h.reason = ('' if not h.hold else f'mode={s.mode}' + (f' stop_reason={s.stop_reason}' if s.stop_reason else ''))
        self.hold_pub.publish(h)

    def _publish_decision(self, event: str, transition_id: str, reason: str, details: dict):
        d = DecisionEvent(); d.header.stamp = self.get_clock().now().to_msg(); d.node = 'gouda_mode_manager'
        d.event = event; d.transition_id = transition_id; d.reason = reason; d.run_id = self.state.run_id; d.section_id = -1
        d.details = json.dumps(details, ensure_ascii=False, default=str)
        self.decision_pub.publish(d)

    def destroy_node(self):
        if self.glim.running:   # never leave GLIM orphaned; its dump on shutdown is kept in the mapping work dir
            try: self.glim.stop(wait_s=optional_double(self, 'glim_stop_wait_s') or 0.0)
            except Exception: pass
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ModeManagerNode()
    executor = rclpy.executors.MultiThreadedExecutor(num_threads=3)
    executor.add_node(node)
    try: executor.spin()
    except KeyboardInterrupt: pass
    finally:
        node.destroy_node(); rclpy.try_shutdown()


if __name__ == '__main__': main()
