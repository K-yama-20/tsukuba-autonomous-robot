"""gouda_mode_manager node (ND-03) — stages 5-1 / 5-2 / 5-3 / 5-6.

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

Stage 5-6 (REV-061, DEC-120 / DEC-122): TR-05 (自律走行開始) — the waypoint set, its mask and the map are checked by hash
(autonomy_core.resolve_mission), Nav2 must be configured (nav2_config: no unresolved vehicle value) and an initial pose in the
map frame must be given; then the mode becomes 自律走行 with motion_hold still true, and a worker sets the Nav2 parameters,
sends the initial pose (IFD-34), starts Nav2 (IFD-36), activates ND-11 / ND-12 and sends the NavigateThroughPoses goal
(IFD-13). The hold is released only when speed_limit_application_state is 適用中 (DEC-056). A failed start goes to 一時停止
(stop_reason node_failure, recorded with TR-07). TR-06 一時停止 (hold, goal cancel), TR-10 再開 in the same process (a new goal
from the first waypoint not yet passed; after a PC restart the resume is refused: 5-7), TR-11 / TR-12 終了 (cancel, ND-11 /
ND-12 deactivate, Nav2 RESET, auto log stop), TR-07 (Nav2 failed) and TR-08 (last waypoint reached) from the result.
TR-05 starts ND-08 (GLIM odometry only, before Nav2) and needs the ND-07 node; in this build ND-07 does not exist, so on the
vehicle the start is refused (no self-localisation, no driving). Recovery (TR-13..16) is stage 5-7.

Settings: state_root (PRM-25) launch argument; params_dir / trial (launch: Nav2 readiness); state_publish_period_s (PRM-16, unresolved -> publish on change);
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
from gouda_core.glim_runner import GlimRunner, GlimSettings, unexpected_exit_report
from gouda_core.map_database import MapDatabase, new_origin_id
from gouda_core.monitor_core import SensorConfig
from gouda_core import sensor_extrinsics
from gouda_core import autonomy_core as ac
from gouda_core.gnss_log import GnssLog
from gouda_core import nav2_config

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

# TR-12 (一時停止 -> 手動走行, 自律走行終了ボタン) is needed already for mapping: a PC restart after mapping enters 一時停止 (TR-02,
# RQ-I064) and only TR-12 leads back to 手動走行. Its navigation actions are void in this build (no navigation client exists).
LOCALIZATION_NODE = 'gouda_global_localization'   # ND-07 node name (in test scripts: the Nav2 loopback simulator stands in for ND-07 / ND-08)
IMPLEMENTED_TRANSITIONS = frozenset({'TR-03', 'TR-04', 'TR-05', 'TR-06', 'TR-10', 'TR-11', 'TR-12'})
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
        self.declare_parameter('params_dir', '')                # design/generated/params (Nav2 readiness, launch argument)
        self.declare_parameter('trial', False)                  # TEST SCRIPTS ONLY (trial values)
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
        # ND-08 (REV-061, DEC-123): the same GLIM, odometry only, in 自律走行・一時停止 (never together with the mapping GLIM: RQ-I004)
        self.glim_odom = GlimRunner(GlimSettings(points_topic=GLIM_POINTS_TOPIC, imu_topic=GLIM_IMU_TOPIC, lidar_frame_id=GLIM_FRAMES['lidar'],
                                                 imu_frame_id=GLIM_FRAMES['imu'], base_frame_id=GLIM_FRAMES['base'], odom_frame_id=GLIM_FRAMES['odom'],
                                                 map_frame_id=GLIM_FRAMES['map'], odometry_only=True))
        self.convert_client = ActionClient(self, ConvertMap, 'map/convert')
        # DEC-126: GNSS (IFD-47..50) recorded during 事前地図作成 into the mapping work dir, registered with the source map
        self.gnss_log = GnssLog()
        self.gnss_types_note = self._subscribe_gnss_log()
        self.mapping_origin_id = None
        # Stage 5-6 autonomy
        self.params_dir = self.get_parameter('params_dir').get_parameter_value().string_value
        self.trial = self.get_parameter('trial').get_parameter_value().bool_value
        self.mission = None                 # autonomy_core.Mission of the current run (this process only)
        self.next_offset = 0                # first waypoint not yet passed (resume, RQ-I014)
        self.drive_released = False         # hold released in 自律走行 only after 適用中 (DEC-056)
        self.goal_active = False
        self._pending_start = None
        from gouda_core.autonomy_client import AutonomyClient
        self.auto = AutonomyClient(self, self._on_nav_feedback, self._on_nav_result, self._on_speed_state)
        miss = self._nav2_missing()
        if miss:
            self._publish_decision('nav2_not_configured', 'TR-05', f'Nav2 is not started: unresolved vehicle values {miss}; 自律走行開始 is refused until they are decided (intent.md:85)', {'missing': miss})
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

    def _nav2_missing(self):
        return nav2_config.missing(nav2_config.read_values(self.params_dir, self.trial)) if self.params_dir else ['params_dir (launch argument)']

    def _start_autonomy(self, request, response):
        details = {'request_id': request.request_id, 'map_id': request.map_id, 'map_revision': request.map_revision,
                   'waypoint_set_id': request.waypoint_set_id, 'waypoint_set_revision': request.waypoint_set_revision}
        why, mission = self._start_precheck(request)
        if why:
            r = mode_core.RequestResult(False, 'TR-05', f'refused: TR-05: {why}')
            with self._lock:
                self._publish_decision('human_request', 'TR-05', r.reason, dict(details, event='start_autonomy', accepted=False, mode=self.state.mode))
            self.get_logger().warning(f'start_autonomy: {r.reason}')
            response.accepted, response.message, response.run_id = False, r.reason, ''
            return response
        self._pending_start = (mission, request.initial_pose)
        r = self._request('start_autonomy', details)
        response.accepted, response.message, response.run_id = r.accepted, r.reason, (r.new_state.run_id if r.accepted and r.new_state else '')
        return response

    def _start_precheck(self, request):
        """TR-05 guard (before any change): mode, Nav2 configured, mission hashes, initial pose, map->base_link available."""
        if self.state.mode != mode_core.MODE_MANUAL:
            return None, None   # mode_core refuses with the usual reason
        miss = self._nav2_missing()
        if miss:
            return f'Nav2 is not configured: unresolved vehicle values {miss}', None
        mission, reason = ac.resolve_mission(self.data_root, {'waypoint_set_id': request.waypoint_set_id, 'waypoint_set_revision': request.waypoint_set_revision,
                                                              'waypoint_set_hash': request.waypoint_set_hash, 'map_id': request.map_id,
                                                              'map_revision': request.map_revision, 'map_hash': request.map_hash})
        if mission is None:
            return reason, None
        p = request.initial_pose
        bad = ac.check_initial_pose(p.header.frame_id, p.pose.pose.position.x, p.pose.pose.position.y, p.pose.pose.orientation.z, p.pose.pose.orientation.w)
        if bad:
            return bad, None
        # ND-07 (TR-05 guard): the global localization node must exist (ND-08, GLIM odometry, is started by TR-05 itself). In
        # this build ND-07 is not implemented, so on the vehicle the start is refused here (no driving without self-localisation).
        names = {n for n, _ in self.get_node_names_and_namespaces()}
        if LOCALIZATION_NODE not in names:
            return f'{LOCALIZATION_NODE} (ND-07) is not running: no self-localisation (stage 5-6, DEC-115)', None
        return None, mission

    def _request(self, event, details):
        with self._lock:
            if event != 'start_autonomy':
                self._pending_start = None
            self._next_state_fields = None
            r = mode_core.request_transition(event, self.state, IMPLEMENTED_TRANSITIONS)
            if r.accepted:
                ok, why = self._perform(r.transition_id)
                if not ok:
                    r = mode_core.RequestResult(False, r.transition_id, f'refused: {r.transition_id} actions failed: {why}')
            self._publish_decision('human_request', r.transition_id, r.reason, dict(details, event=event, accepted=r.accepted, mode=self.state.mode))
            # Separate call sites: rclpy refuses a logging call site whose severity changes between calls (it raised and
            # killed this node when an accepted request was followed by a refused one: 2026-10-13 VM test).
            if r.accepted:
                self.get_logger().info(f'{event}: {r.reason}')
            else:
                self.get_logger().warning(f'{event}: {r.reason}')
            if r.accepted and r.new_state is not None:
                fields, self._next_state_fields = getattr(self, '_next_state_fields', None), None
                self._set_state(mode_core.ModeState(**{**r.new_state.as_dict(), **fields}) if fields else r.new_state)
                if getattr(self, '_after_transition', None):
                    job, self._after_transition = self._after_transition, None
                    threading.Thread(target=job, name=f'{r.transition_id}_after', daemon=True).start()
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
        if transition_id == 'TR-05': return self._tr05_start_autonomy()
        if transition_id == 'TR-06': return self._tr06_pause()
        if transition_id == 'TR-10': return self._tr10_resume()
        if transition_id in ('TR-11', 'TR-12'): return self._tr11_12_end(transition_id)
        return False, 'no actions implemented'

    def _subscribe_gnss_log(self):
        """Subscribe the GNSS topics for the mapping record. Returns a note when the driver's message types are missing."""
        from rclpy.qos import QoSProfile as Q
        from sensor_msgs.msg import NavSatFix
        from rosidl_runtime_py.convert import message_to_ordereddict
        qos = Q(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE, history=HistoryPolicy.KEEP_LAST, depth=50)
        def sub(msg_type, topic):
            def cb(m):
                if self.gnss_log.active:
                    self.gnss_log.write(topic, self.get_clock().now().nanoseconds * 1e-9, message_to_ordereddict(m))
            self.create_subscription(msg_type, topic, cb, qos)
        sub(NavSatFix, 'sensors/gnss/navsatfix')                       # IFD-47
        try:
            from septentrio_gnss_driver.msg import PVTGeodetic, AttEuler, AttCovEuler
        except ImportError:
            return 'septentrio_gnss_driver message types are not installed: only navsatfix is recorded'
        sub(PVTGeodetic, 'sensors/gnss/pvtgeodetic')                   # IFD-48
        sub(AttEuler, 'sensors/gnss/atteuler')                         # IFD-49
        sub(AttCovEuler, 'sensors/gnss/attcoveuler')                   # IFD-50
        return ''

    def _tr03_start_mapping(self):
        """TR-03: start GLIM (ND-06); request the automatic log start (IFD-45) without waiting; record settings."""
        if self.glim.running:
            return False, 'GLIM is already running'
        if self.glim_odom.running:
            return False, 'the odometry GLIM of autonomy (ND-08) is still running; mapping GLIM is not started together with it (RQ-I004)'
        origin_id = new_origin_id(); work = self.data_root / 'mapping' / origin_id
        # GLIM's LiDAR-IMU transform from the human's /config (intent.md:105). UNKNOWN fields never stop the start: they are
        # replaced by the neutral element and listed in the record and on the monitor.
        cfg = SensorConfig(self.data_root / 'config' / 'sensor_config.json')
        ext = sensor_extrinsics.t_lidar_imu(dict(cfg.values))
        self._publish_decision('glim_extrinsic', 'TR-03',
                               'T_lidar_imu from /config' + ('' if ext['complete'] else f" (UNKNOWN in /config, neutral used: {', '.join(ext['defaulted_fields'])})")
                               + (f" (problems: {'; '.join(ext['problems'])})" if ext['problems'] else ''),
                               dict(ext, config_revision=cfg.config_revision, config_path=str(cfg.path)))
        try:
            run = self.glim.start(work, work / 'glim_dump', work / 'glim.log', t_lidar_imu=ext['T_lidar_imu'])
        except Exception as e:
            self._publish_decision('mapping_start_failed', 'TR-03', f'GLIM start failed: {e}', {'origin_id': origin_id})
            return False, f'GLIM start failed: {e}'
        self.mapping_origin_id = origin_id
        gpath = self.gnss_log.open(work)
        try:   # the /config of this run, registered with the source map (GNSS calibration, REV-067)
            (work / 'sensor_config.json').write_bytes(cfg.path.read_bytes())
        except OSError:
            pass
        if self.gnss_types_note:
            self.gnss_log.note(self.gnss_types_note, self.get_clock().now().nanoseconds * 1e-9)
        self._publish_decision('gnss_record_started', 'TR-03', f'GNSS recorded to {gpath}' + (f' ({self.gnss_types_note})' if self.gnss_types_note else ''), {'path': str(gpath)})
        if getattr(self.glim, 'proc', None) is not None and hasattr(self.glim.proc, 'wait'):
            threading.Thread(target=self._watch_glim, args=(self.glim.proc, run, origin_id), name='glim_watch', daemon=True).start()
        self._publish_decision('mapping_started', 'TR-03', f'GLIM started (pid {run.pid}); origin {origin_id}',
                               {'origin_id': origin_id, 'config_dir': str(run.config_dir), 'dump_dir': str(run.dump_dir), 'points_topic': GLIM_POINTS_TOPIC, 'imu_topic': GLIM_IMU_TOPIC, 'frames': GLIM_FRAMES,
                                'T_lidar_imu': ext['T_lidar_imu'], 'config_revision': cfg.config_revision})
        self.request_auto_record('map_start', 'TR-03')   # asynchronous; a failure never stops mapping (DEC-071)
        return True, 'mapping started'

    def _watch_glim(self, proc, run, origin_id):
        """Wait for the GLIM process; when it ends without a stop request, record and show it (G-GLIM-EXIT, TR-14 detection
        only). The wait is event-driven (no polling period is introduced)."""
        code = proc.wait()
        with self._lock:
            report = unexpected_exit_report(run, code, self._now())
            if report is None:
                return   # ended by the human's 地図作成終了 (TR-04)
            reason, details = report
            self._publish_decision('glim_exited', 'TR-14', reason, dict(details, origin_id=origin_id, mode=self.state.mode))
        self.get_logger().error(reason)   # the only error call site of this method (rclpy: one severity per call site)

    def _now(self) -> float:
        t = self.get_clock().now().seconds_nanoseconds()
        return t[0] + t[1] * 1e-9

    def _tr04_end_mapping(self):
        """TR-04 (the guard accepts every human end): the mode returns to manual at once and the request is answered; saving
        the GLIM dump, registering the source map (IFD-29), starting the conversion (IFD-37) and stopping the auto-started log
        (IFD-46) continue after the transition with processing_state=map_saving -> map_converting (DEC-010).
        The save wait is PRM-37; while it is unresolved there is no upper limit (no value is invented) and the save time is
        recorded for its measurement."""
        wait_s = optional_double(self, 'glim_stop_wait_s')
        origin_id = self.mapping_origin_id or new_origin_id()
        self.mapping_origin_id = None
        self._after_transition = lambda: self._finish_mapping(origin_id, wait_s)
        return True, 'mapping ended; the map is being saved (processing_state=map_saving)'

    # ---- stage 5-6 autonomy (TR-05 / 06 / 07 / 08 / 10 / 11 / 12) ----
    def _tr05_start_autonomy(self):
        """TR-05: accepted after _start_precheck. The mode becomes 自律走行 with the hold kept (drive_released False); the start
        continues in a worker (parameters, initial pose, Nav2 STARTUP, ND-11 / ND-12, goal) and the auto log is requested."""
        if self._pending_start is None:
            return False, 'no checked start request'
        mission, pose = self._pending_start; self._pending_start = None
        import uuid
        self.mission, self.next_offset, self.drive_released = mission, 0, False
        run_id = f'run-{uuid.uuid4().hex[:8]}'
        self._next_state_fields = {'run_id': run_id, 'remaining_waypoints': len(mission.waypoints), 'current_section': 0,
                                   'initial_pose_required': False, 'speed_limit_application_state': ac.SL_NOT_LOADED}
        token = self.auto.new_token()
        def steps(rec):
            self._start_odometry(rec, run_id)
            self.auto.start(token, mission, pose, rec)
        def job():
            self.request_auto_record('autonomy_start', 'TR-05')
            self._run_steps(token, 'TR-05', steps)
        self._after_transition = job
        return True, f'autonomy starting ({len(mission.waypoints)} waypoints, set {mission.set_id}/{mission.set_revision:03d})'

    def _tr06_pause(self):
        """TR-06: the mode change itself holds (motion_hold=true); the goal is cancelled; Nav2 stays active without a goal."""
        self.drive_released = False
        self.auto.new_token()   # abandons a start still in progress
        self.goal_active = False
        self._after_transition = lambda: self.auto.cancel(self._rec('TR-06'), 'TR-06')
        return True, 'paused (motion_hold=true, Nav2 goal cancelled)'

    def _tr10_resume(self):
        """TR-10 within the same process: a new goal from the first waypoint not yet passed (RQ-I014, RQ-I067)."""
        if self.mission is None:
            return False, 'no mission in this process (after a PC restart the resume is stage 5-7)'
        if self.goal_active or self.auto.goal_handle is not None:
            return False, 'the previous Nav2 goal has not ended yet'
        if not self.auto.nav2_active:
            return False, 'Nav2 is not active'
        self.drive_released = False
        offset = min(self.next_offset, len(self.mission.waypoints) - 1)
        self._next_state_fields = {'speed_limit_application_state': ac.SL_UNKNOWN}
        token = self.auto.new_token(); mission = self.mission
        self._after_transition = lambda: self._run_steps(token, 'TR-10', lambda rec: self.auto.send_goal(token, mission, offset, rec))
        return True, f'resuming from waypoint {offset}'

    def _tr11_12_end(self, transition_id):
        """TR-11 / TR-12: hold (by the mode), goal cancel, ND-11 / ND-12 deactivate, Nav2 RESET, auto log stop."""
        self.drive_released = False; self.goal_active = False; self.mission = None
        token = self.auto.new_token()
        def job():
            rec = self._rec(transition_id)
            self.auto.cancel(rec, transition_id)
            self.auto.stop(token, rec)
            self._stop_odometry(rec)
            self.request_auto_record('stop_auto', transition_id)
        self._after_transition = job
        return True, 'autonomy ended'

    def _start_odometry(self, rec, run_id):
        """ND-08: GLIM odometry only (TF odom -> odom_glim -> base_link; gouda_local_odometry relays IFD-25)."""
        from gouda_core.autonomy_client import StepFailed
        if self.glim_odom.running:
            rec('odometry_running', 'ND-08 GLIM (odometry only) is already running', {}); return
        cfg = SensorConfig(self.data_root / 'config' / 'sensor_config.json')
        ext = sensor_extrinsics.t_lidar_imu(dict(cfg.values))
        work = self.data_root / 'run' / 'glim_odometry' / run_id
        try:
            r = self.glim_odom.start(work, work / 'glim_dump', work / 'glim.log', t_lidar_imu=ext['T_lidar_imu'])
        except Exception as e:
            raise StepFailed(f'ND-08 GLIM (odometry only) start failed: {e}')
        rec('odometry_started', f'ND-08 GLIM (odometry only) started (pid {r.pid})' + ('' if ext['complete'] else f" (UNKNOWN in /config, neutral used: {', '.join(ext['defaulted_fields'])})"),
            {'config_dir': str(r.config_dir), 'T_lidar_imu': ext['T_lidar_imu']})

    def _stop_odometry(self, rec):
        if not self.glim_odom.running:
            return
        try:
            r = self.glim_odom.stop(optional_double(self, 'glim_stop_wait_s'))
            rec('odometry_stopped', f'ND-08 GLIM (odometry only) stopped (exit code {r.exit_code})', {})
        except Exception as e:
            rec('odometry_stop_failed', f'ND-08 GLIM stop failed: {e}', {})

    def _rec(self, transition_id):
        def rec(event, reason, details):
            with self._lock:
                self._publish_decision(event, transition_id, reason, details)
        return rec

    def _run_steps(self, token, transition_id, steps):
        from gouda_core.autonomy_client import StepFailed, Abandoned
        rec = self._rec(transition_id)
        try:
            steps(rec)
            with self._lock:
                if token == self.auto._token: self.goal_active = True
        except Abandoned:
            rec('autonomy_start_abandoned', 'a human pause / end came first; the remaining start steps were not run', {})
        except StepFailed as e:
            with self._lock:
                if token != self.auto._token: return
                self._auto_pause('TR-07', mode_core.STOP_REASON_NODE_FAILURE, f'{transition_id} failed: {e}', {'step_error': str(e)})

    def _auto_pause(self, transition_id, stop_reason, reason, details):
        new = mode_core.automatic_pause(self.state, transition_id, stop_reason, self.state.remaining_waypoints)
        if new is None:
            self._publish_decision('nav2_result_ignored', transition_id, f'{reason} (mode {self.state.mode}: no transition)', details); return
        self.drive_released = False; self.goal_active = False
        self._publish_decision('automatic_pause', transition_id, reason, dict(details, stop_reason=stop_reason))
        self.get_logger().warning(f'{transition_id}: {reason}')
        self._set_state(new)

    def _on_nav_feedback(self, offset, poses, remaining):
        with self._lock:
            if self.state.mode != mode_core.MODE_AUTONOMY: return
            section = ac.section_from_feedback(offset, poses, remaining)
            self.next_offset = ac.remaining_offset(offset, poses, remaining)
            total = len(self.mission.waypoints) if self.mission else 0
            if (section, total - self.next_offset) != (self.state.current_section, self.state.remaining_waypoints):
                skipped = section - self.state.current_section - 1
                if skipped > 0:
                    self._publish_decision('sections_skipped', 'TR-05', f'{skipped} section(s) passed at once (Nav2 RemovePassedGoals)', {'from': self.state.current_section, 'to': section})
                self._update_fields({'current_section': section, 'remaining_waypoints': total - self.next_offset})

    def _on_nav_result(self, status, error_code, error_msg):
        from action_msgs.msg import GoalStatus
        with self._lock:
            self.goal_active = False
            if status == GoalStatus.STATUS_SUCCEEDED:
                if self.mission: self.next_offset = len(self.mission.waypoints) - 1   # resume aims at the last waypoint (RQ-I067)
                new = mode_core.automatic_pause(self.state, 'TR-08', mode_core.STOP_REASON_GOAL_REACHED, 1)
                if new is not None:
                    self.drive_released = False
                    self._publish_decision('goal_reached', 'TR-08', 'Nav2 reached the last waypoint', {'status': status})
                    self._set_state(new)
                return
            if status == GoalStatus.STATUS_CANCELED:
                self._publish_decision('nav2_goal_ended', '', 'Nav2 goal cancelled', {'status': status}); return
            self._auto_pause('TR-07', mode_core.STOP_REASON_PLAN_FAILURE, f'Nav2 goal ended with status {status}: error_code {error_code} {error_msg}'.strip(),
                             {'status': status, 'error_code': error_code, 'error_msg': error_msg})

    def _on_speed_state(self, state, details):
        with self._lock:
            if self.state.mode != mode_core.MODE_AUTONOMY: return
            if state != self.state.speed_limit_application_state:
                self._publish_decision('speed_limit_application_state', 'TR-05', f'{state} ({ac.SL_LABELS.get(state, state)})', details)
                self._update_fields({'speed_limit_application_state': state})
            if state == ac.SL_APPLIED and self.goal_active and not self.drive_released:
                self.drive_released = True
                self._publish_decision('motion_hold_released', 'TR-05', 'speed limit applied (適用中): motion_hold=false (DEC-056)', details)
                self._publish_state()

    def _update_fields(self, fields):
        self.state = mode_core.ModeState(**{**self.state.as_dict(), **fields, 'state_revision': self.state.state_revision + 1})
        self._publish_state()

    def _set_processing(self, processing_state):
        with self._lock:
            self.state = mode_core.ModeState(**{**self.state.as_dict(), 'processing_state': processing_state, 'state_revision': self.state.state_revision + 1})
            self._publish_state()

    def _finish_mapping(self, origin_id, wait_s):
        self._set_processing('map_saving')
        try:
            run = self.glim.stop(wait_s)
        except Exception as e:
            self._publish_decision('mapping_stop_failed', 'TR-04', f'GLIM stop failed: {e}', {'origin_id': origin_id})
            run = None
        self._publish_decision('mapping_stopped', 'TR-04', (run.note if run else 'GLIM was not running'),
                               {'origin_id': origin_id, 'dump_ok': run.dump_ok if run else None, 'submaps': run.submaps if run else 0, 'exit_code': run.exit_code if run else None,
                                'save_duration_s': run.save_duration_s if run else None,
                                'glim_exited_unexpectedly_at': run.exited_unexpectedly_at if run else None,
                                'wait_limit_s': wait_s if wait_s is not None else 'none (PRM-37 unresolved)'})
        converting = False
        gpath = self.gnss_log.path
        gsum = self.gnss_log.close()
        self._publish_decision('gnss_record_stopped', 'TR-04', f"GNSS record closed: {gsum['counts'] if gsum else 'not open'}" + ('' if (gsum and any(k != 'note' for k in gsum['counts'])) else ' (no GNSS message: no alignment can be made from this map)'),
                               {'path': str(gpath) if gpath else None, 'summary': gsum})
        if run and run.dump_ok:
            ok, msg, manifest = self.maps.register_source(run.dump_dir, origin_id, {'software': 'glim_ros', 'version': 'installed package (DEC-062)', 'config_dir': str(run.config_dir)},
                                                           {'started_at': run.started_at, 'stopped_at': run.stopped_at, 'glim_log': str(run.config_dir.parent / 'glim.log')},
                                                           gnss=(gpath, gsum) if gsum else None,
                                                           config_snapshot=(gpath.parent / 'sensor_config.json') if gpath else None)
            self._publish_decision('source_map_registered' if ok else 'source_map_not_registered', 'TR-04', msg, {'origin_id': origin_id, 'content_hash': manifest['content_hash'] if manifest else None})
            if ok:
                converting = self._start_conversion(origin_id)
        else:
            self._publish_decision('source_map_not_registered', 'TR-04', 'dump incomplete or GLIM not running: the source is kept where it is and nothing is published (RQ-I009)', {'origin_id': origin_id})
        if not converting:
            self._set_processing('idle')
        self.request_auto_record('stop_auto', 'TR-04')

    def _start_conversion(self, origin_id):
        """IFD-37 map/convert, asynchronous. processing_state shows map_converting until the result (DEC-010)."""
        if not self.convert_client.server_is_ready():
            self._publish_decision('map_convert_not_started', 'TR-04', 'map/convert action server is not available (gouda_map_creator not running?); re-conversion can be requested later', {'origin_id': origin_id})
            return False
        goal = ConvertMap.Goal(); goal.origin_id = origin_id; goal.settings_json = ''
        self._set_processing('map_converting')
        send = self.convert_client.send_goal_async(goal)
        def on_goal(f):
            gh = f.result()
            if not gh.accepted:
                self._finish_conversion(origin_id, False, 'conversion goal rejected'); return
            gh.get_result_async().add_done_callback(lambda rf: self._finish_conversion(origin_id, rf.result().result.ok, rf.result().result.message, rf.result().result))
        send.add_done_callback(on_goal)
        return True

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
        h.hold = not (s.mode == mode_core.MODE_AUTONOMY and getattr(self, 'drive_released', False))   # 自律走行 holds until 適用中 (DEC-056)
        h.mode = mode_core.MODE_CODES[s.mode]
        h.reason = ('' if not h.hold else f'mode={s.mode}' + (f' stop_reason={s.stop_reason}' if s.stop_reason else '')
                    + (f' speed_limit={s.speed_limit_application_state} (waiting for 適用中)' if s.mode == mode_core.MODE_AUTONOMY else ''))
        self.hold_pub.publish(h)

    def _publish_decision(self, event: str, transition_id: str, reason: str, details: dict):
        d = DecisionEvent(); d.header.stamp = self.get_clock().now().to_msg(); d.node = 'gouda_mode_manager'
        d.event = event; d.transition_id = transition_id; d.reason = reason; d.run_id = self.state.run_id; d.section_id = -1
        d.details = json.dumps(details, ensure_ascii=False, default=str)
        self.decision_pub.publish(d)

    def destroy_node(self):
        self.gnss_log.close()
        if self.glim_odom.running:
            try: self.glim_odom.stop(wait_s=optional_double(self, 'glim_stop_wait_s'))
            except Exception: pass
        if self.glim.running:   # never leave GLIM orphaned; its dump on shutdown is kept in the mapping work dir
            try: self.glim.stop(wait_s=optional_double(self, 'glim_stop_wait_s'))   # PRM-37; None = until GLIM has saved
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
