"""gouda_global_localization (ND-07, trial A3; REV-128, DEC-115 / DEC-200 / DEC-203): map->odom on the saved map.

Lifecycle (driven by gouda_mode_manager, IFD-36):
- configure: map_directory (the converted map revision chosen at 自律走行開始, set by ND-03 before configure) must hold
  pointcloud_map/metadata.yaml and trajectory_imu.txt (map conversion, PRM-94 / PRM-95). The settings PRM-79..92 come from the
  generated parameter file; when one is unresolved (on the vehicle without trial values) configure fails and the reason is
  recorded (RQ-I076). The A3 parts are started as a child launch (gouda_localization_a3.launch.py, namespace localization/a3):
  Gouda's point filter gouda_a3_points (crop and voxel on x, y, z: REV-148, DEC-283) and the unmodified point-cloud map loader,
  NDT scan matcher and EKF localizer.
- activate: the initialization runs in a worker: the human's initial pose (IFD-34, transient_local) with the height from the
  mapping trajectory and the covariance PRM-84..87 -> ndt_align_srv (Monte Carlo search) -> the EKF's initial pose -> the
  EKF's and the NDT's trigger_node true. Each step is a DecisionEvent; a failure leaves the state 推定不能 (init_failed) and
  publishes no map->odom. A service that is not there yet is waited for without a time limit (the child launch is starting;
  the human can always pause or end, and the mode manager's start waits for this node's state). Before ndt_align_srv the
  NDT must hold a point cloud: its scan status in /diagnostics shows that a cloud was kept (REV-144, DEC-280). This is also
  waited for without a time limit; meanwhile the detail of IFD-53 says so and gives the NDT's reason for the last dropped
  cloud (e.g. the max distance below its required_distance), so the wait is never mistaken for 推定不能.
- deactivate: the EKF and the NDT are triggered false and map->odom is no longer published. cleanup: the child launch is stopped.
While running: IFD-25 (localization/odometry) -> the EKF's twist (variances PRM-82, PRM-83) and the odometry buffer; the EKF pose
-> map->odom (localization_core.MapOdomEstimator) and localization/pose (IFD-33); /tf map->odom (IFD-18) is published with the
time of each odometry message, so that odom->base_link and map->odom are always found at the same time. This node is the only
map->odom publisher: the EKF's and the NDT's /tf are remapped inside the namespace (D-17).
localization/status (IFD-53, transient_local) every status_period_s (PRM-88) and on every state change (localization_core.evaluate).
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
from pathlib import Path

import rclpy
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from rclpy.parameter import Parameter
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy, qos_profile_sensor_data
from geometry_msgs.msg import PoseWithCovarianceStamped, TwistWithCovarianceStamped, TransformStamped
from nav_msgs.msg import Odometry
from diagnostic_msgs.msg import DiagnosticArray
from std_srvs.srv import SetBool
from tf2_ros import TransformBroadcaster
from gouda_interfaces.msg import DecisionEvent, EstimatorStatus

from gouda_core import localization_core as lc
from gouda_core import map_convert
from gouda_core.monitor_core import SensorConfig

LATCHED = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=1)
DECISION_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=50)  # IFD-28 (DEC-072)
POSE_QOS = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, durability=DurabilityPolicy.VOLATILE, history=HistoryPolicy.KEEP_LAST, depth=5)       # IFD-33
INTERNAL_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE, history=HistoryPolicy.KEEP_LAST, depth=10)
NS = 'localization/a3'   # the A3 parts' namespace (gouda_localization_a3.launch.py); interface names, not settings
A3_LAUNCH = 'gouda_localization_a3.launch.py'
MAP, ODOM, BASE = 'map', 'odom', 'base_link'


def optional(node, name, kind):
    try:
        prm = node.get_parameter(name)
    except Exception:
        return None
    return prm.value if prm.type_ == kind else None


def pose_of(p) -> tuple:
    return (p.position.x, p.position.y, p.position.z, p.orientation.x, p.orientation.y, p.orientation.z, p.orientation.w)


def stamp_s(stamp) -> float:
    return stamp.sec + stamp.nanosec * 1e-9


class GlobalLocalizationNode(LifecycleNode):
    def __init__(self):
        super().__init__('gouda_global_localization')
        self.declare_parameter('data_root', '')        # PRM-25 (/config, run/ logs)
        self.declare_parameter('map_directory', '')    # set by ND-03 at TR-05 (the converted map revision); runtime_set
        for k in lc.DOUBLE_SETTINGS:
            self.declare_parameter(k, Parameter.Type.DOUBLE)
        for k in lc.INT_SETTINGS:
            self.declare_parameter(k, Parameter.Type.INTEGER)
        self.data_root = Path(os.path.expanduser(self.get_parameter('data_root').get_parameter_value().string_value or '.'))
        self._lock = threading.RLock()
        self.settings = None
        self.inputs = lc.Inputs()
        self.estimator = None
        self.proc = None
        self.map_dir = ''
        self.initial_pose = None
        self._pose_event = threading.Event()
        self._points_event = threading.Event()   # the NDT holds a cloud (DEC-280); per child launch
        self._points_last = None                  # (kept, message) of the NDT's newest scan status
        self._points_waiting = False
        self._token = 0
        self.last_state = None
        self.decision_pub = self.create_publisher(DecisionEvent, 'log/decision', DECISION_QOS)
        self.status_pub = self.create_publisher(EstimatorStatus, 'localization/status', LATCHED)   # IFD-53, also while unconfigured
        self.timer = None
        self._subs, self._pubs = [], []
        self.tf = TransformBroadcaster(self)   # /tf map->odom (IFD-18): published only while running
        self._publish_status()
        self.get_logger().info('unconfigured; map_directory is set by gouda_mode_manager at 自律走行開始 (TR-05)')

    # ---- lifecycle ----
    def on_configure(self, state) -> TransitionCallbackReturn:
        values = {k: optional(self, k, Parameter.Type.DOUBLE) for k in lc.DOUBLE_SETTINGS}
        values.update({k: optional(self, k, Parameter.Type.INTEGER) for k in lc.INT_SETTINGS})
        try:
            s = lc.Settings.from_values(values)
        except ValueError as e:
            return self._refuse(f'{e} (PRM-79..92: pass design/generated/params/gouda_global_localization.yaml; trial file only in tests)', values)
        map_dir = Path(self.get_parameter('map_directory').get_parameter_value().string_value)
        meta, traj = map_dir / map_convert.POINTCLOUD_MAP_METADATA, map_dir / map_convert.TRAJECTORY_FILE
        if not meta.is_file():
            return self._refuse(f'{meta} is missing: the map has no point-map tiles (convert it again with PRM-94 / PRM-95 resolved)', {'map_directory': str(map_dir)})
        trajectory = lc.read_tum(traj.read_text(encoding='utf-8')) if traj.is_file() else []
        if not trajectory:
            return self._refuse(f'{traj} is missing or empty: no initial height can be given (convert the map again)', {'map_directory': str(map_dir)})
        cfg = SensorConfig(self.data_root / 'config' / 'sensor_config.json')
        imu_z = dict(cfg.values).get('imu_mount_z_m')
        imu_z_known = isinstance(imu_z, (int, float))
        log_dir = self.data_root / 'run' / 'localization'; log_dir.mkdir(parents=True, exist_ok=True)
        log = log_dir / f'a3_{time.strftime("%Y%m%d_%H%M%S")}.log'
        cmd = ['ros2', 'launch', 'gouda_core', A3_LAUNCH, f'map_directory:={map_dir}', f'points_near_crop_m:={s.points_near_crop_m}',
               f'points_far_crop_m:={s.points_far_crop_m}', f'points_voxel_leaf_m:={s.points_voxel_leaf_m}',
               f'points_voxel_min_points:={s.points_voxel_min_points}']
        try:
            self.proc = subprocess.Popen(cmd, stdout=open(log, 'ab'), stderr=subprocess.STDOUT, start_new_session=True)
        except OSError as e:
            return self._refuse(f'the A3 launch could not be started: {e}', {'command': cmd})
        with self._lock:
            self._points_event.clear(); self._points_last = None   # a new NDT: nothing kept yet
            self.settings, self.map_dir, self.trajectory = s, str(map_dir), trajectory
            self.imu_height = float(imu_z) if imu_z_known else 0.0
            self.estimator = lc.MapOdomEstimator(s.stale_timeout_s)
            self.inputs = lc.Inputs(phase='waiting', localizer_running=True)
        threading.Thread(target=self._watch_child, args=(self.proc,), name='a3_watch', daemon=True).start()
        self._subs = [self.create_subscription(Odometry, 'localization/odometry', self._on_odometry, qos_profile_sensor_data),   # IFD-25
                      self.create_subscription(PoseWithCovarianceStamped, f'{NS}/ekf_pose_with_covariance', self._on_ekf_pose, INTERNAL_QOS),
                      self.create_subscription(DiagnosticArray, '/diagnostics', self._on_diagnostics, INTERNAL_QOS),
                      self.create_subscription(PoseWithCovarianceStamped, 'localization/initial_pose', self._on_initial_pose, LATCHED)]   # IFD-34
        self.twist_pub = self.create_publisher(TwistWithCovarianceStamped, f'{NS}/twist_with_covariance', INTERNAL_QOS)
        self.init_pub = self.create_publisher(PoseWithCovarianceStamped, f'{NS}/initialpose3d', INTERNAL_QOS)
        self.pose_pub = self.create_publisher(PoseWithCovarianceStamped, 'localization/pose', POSE_QOS)   # IFD-33
        self._pubs = [self.twist_pub, self.init_pub, self.pose_pub]
        from autoware_internal_localization_msgs.srv import PoseWithCovarianceStamped as AlignSrv
        self.align = self.create_client(AlignSrv, f'{NS}/ndt_align_srv')
        self.triggers = {n: self.create_client(SetBool, f'{NS}/{n}_trigger_node') for n in ('ekf', 'ndt')}
        self.timer = self.create_timer(s.status_period_s, self._publish_status)
        self._decision('configured', f'A3 launch started (pid {self.proc.pid}); map {map_dir}', {
            'map_directory': str(map_dir), 'log': str(log), 'settings': values, 'trajectory_points': len(trajectory),
            'imu_mount_z_m': imu_z if imu_z_known else 'UNKNOWN in /config: 0 used for the initial height', 'config_revision': cfg.config_revision})
        self._publish_status()
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state) -> TransitionCallbackReturn:
        with self._lock:
            self._token += 1; token = self._token
            # nothing received in an earlier activation counts for this one (DEC-282: 初期化中 until each input arrives)
            self.inputs = lc.Inputs(phase='initializing', phase_detail='waiting for the initial pose (IFD-34)', localizer_running=self.inputs.localizer_running)
            self.estimator.reset()
        self._publish_status()
        threading.Thread(target=self._initialize, args=(token,), name='a3_init', daemon=True).start()
        return super().on_activate(state)

    def on_deactivate(self, state) -> TransitionCallbackReturn:
        with self._lock:
            self._token += 1; self._points_waiting = False
            self.inputs.phase, self.inputs.phase_detail = 'waiting', ''
            self.estimator.reset(); self.initial_pose = None; self._pose_event.clear()
        for name, cli in self.triggers.items():   # best effort; the result is recorded
            if cli.service_is_ready():
                cli.call_async(SetBool.Request(data=False)).add_done_callback(
                    lambda f, n=name: self._decision('trigger_off', f'{n} trigger_node false: {self._result_text(f)}', {}))
        self._decision('deactivated', 'map->odom is no longer published', {})
        self._publish_status()
        return super().on_deactivate(state)

    def on_cleanup(self, state) -> TransitionCallbackReturn:
        self._stop_child()
        for s in self._subs: self.destroy_subscription(s)
        for p in self._pubs: self.destroy_publisher(p)
        if self.timer: self.destroy_timer(self.timer)
        self._subs, self._pubs, self.timer = [], [], None
        with self._lock:
            self.settings = None; self.map_dir = ''; self.inputs = lc.Inputs()
            self._points_event.clear(); self._points_last = None; self._points_waiting = False
        self._decision('cleaned_up', 'A3 launch stopped', {})
        self._publish_status()
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state) -> TransitionCallbackReturn:
        self._stop_child()
        return TransitionCallbackReturn.SUCCESS

    def _refuse(self, why, details):
        self.get_logger().error(f'configure refused: {why}')
        self._decision('configure_refused', why, details)
        return TransitionCallbackReturn.FAILURE

    # ---- child launch ----
    def _watch_child(self, proc):
        code = proc.wait()
        with self._lock:
            if proc is not self.proc:
                return
            self.inputs.localizer_running = False
        self._decision('localizer_exited', f'the A3 launch ended (exit code {code})', {'exit_code': code})
        self._publish_status()

    def _stop_child(self):
        proc, self.proc = self.proc, None
        if proc is None or proc.poll() is not None:
            return
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGINT)
        except ProcessLookupError:
            return
        proc.wait()   # ros2 launch escalates to SIGTERM / SIGKILL on its own; no time value is set here

    # ---- initialization ----
    def _on_initial_pose(self, msg: PoseWithCovarianceStamped):
        with self._lock:
            self.initial_pose = msg
        self._pose_event.set()

    def _initialize(self, token):
        def alive():
            return token == self._token
        def step(detail):
            with self._lock:
                if alive(): self.inputs.phase_detail = detail
            self._publish_status()
        def fail(why, details=None):
            with self._lock:
                if not alive(): return
                self.inputs.phase, self.inputs.phase_detail = 'failed', why
            self._decision('init_failed', why, details or {})
            self._publish_status()
        self._pose_event.wait()   # transient_local: the pose of this start, sent by ND-03 before configure
        if not alive(): return
        with self._lock:
            pose = self.initial_pose; s = self.settings
        p = pose.pose.pose
        h = lc.initial_height(self.trajectory, p.position.x, p.position.y, self.imu_height)
        req_pose = PoseWithCovarianceStamped(); req_pose.header.frame_id = MAP; req_pose.header.stamp = self.get_clock().now().to_msg()
        req_pose.pose.pose.position.x, req_pose.pose.pose.position.y, req_pose.pose.pose.position.z = p.position.x, p.position.y, h[0]
        req_pose.pose.pose.orientation = p.orientation
        req_pose.pose.covariance = lc.initial_pose_covariance(s)
        self._decision('initial_pose_received', f'initial pose ({p.position.x:.2f}, {p.position.y:.2f}); height {h[0]:.2f} m from the mapping trajectory (nearest point {h[1]:.2f} m away)',
                       {'x': p.position.x, 'y': p.position.y, 'z': h[0], 'trajectory_distance_m': h[1]})
        step('waiting for ndt_align_srv (the A3 launch is starting)')
        self.align.wait_for_service()   # no time limit (see the module docstring)
        if not alive(): return
        with self._lock:
            self._points_waiting = True; kept, last = self._points_event.is_set(), self._points_last
        if not kept:
            step(lc.points_wait_detail(last))
            self._decision('ndt_points_waiting', lc.points_wait_detail(last), {})
        self._points_event.wait()   # no time limit (DEC-280; see the module docstring)
        with self._lock:
            if not alive(): return
            self._points_waiting = False
        step('Monte Carlo search of the initial pose (ndt_align_srv)')
        req = self.align.srv_type.Request(); req.pose_with_covariance = req_pose
        res = self._call(self.align, req)
        if not alive(): return
        if res is None or not getattr(res, 'success', False):
            fail('ndt_align_srv did not succeed (no map->odom is published)', {'result': str(res)}); return
        aligned = res.pose_with_covariance; aligned.header.stamp = self.get_clock().now().to_msg()
        self._decision('initial_pose_aligned', f'aligned to ({aligned.pose.pose.position.x:.2f}, {aligned.pose.pose.position.y:.2f})',
                       {'x': aligned.pose.pose.position.x, 'y': aligned.pose.pose.position.y, 'z': aligned.pose.pose.position.z})
        self.init_pub.publish(aligned)
        for name in ('ekf', 'ndt'):
            step(f'activating the {name} (trigger_node)')
            self.triggers[name].wait_for_service()
            if not alive(): return
            r = self._call(self.triggers[name], SetBool.Request(data=True))
            if r is None or not r.success:
                fail(f'{name} trigger_node true failed: {r}'); return
        with self._lock:
            if not alive(): return
            self.inputs.phase, self.inputs.phase_detail = 'running', ''
        self._decision('initialized', 'EKF and NDT active; the state follows the checks (IFD-53)', {})
        self._publish_status()

    def _call(self, client, request):
        fut = client.call_async(request)
        done = threading.Event(); fut.add_done_callback(lambda _: done.set()); done.wait()
        return fut.result() if fut.exception() is None else None

    @staticmethod
    def _result_text(fut):
        try:
            r = fut.result(); return f'{r.success} {r.message}'
        except Exception as e:
            return f'failed: {e}'

    # ---- inputs ----
    def _now(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    def _on_odometry(self, msg: Odometry):
        with self._lock:
            if self.settings is None: return
            self.inputs.last_odometry = self._now()
            t = stamp_s(msg.header.stamp)
            active = self.inputs.phase in ('initializing', 'running')
            if active:
                self.estimator.on_odometry(t, pose_of(msg.pose.pose))   # map->odom is computed here too (DEC-285)
                self.inputs.has_map_odom = self.estimator.map_odom is not None
            running, map_odom, s = self.inputs.phase == 'running', self.estimator.map_odom, self.settings
        if active:
            tw = TwistWithCovarianceStamped(); tw.header.stamp = msg.header.stamp; tw.header.frame_id = BASE
            tw.twist.twist = msg.twist.twist; tw.twist.covariance = lc.twist_covariance(s)
            self.twist_pub.publish(tw)
        if running and map_odom is not None:
            t_msg = TransformStamped(); t_msg.header.stamp = msg.header.stamp; t_msg.header.frame_id = MAP; t_msg.child_frame_id = ODOM
            tr, r = t_msg.transform.translation, t_msg.transform.rotation
            tr.x, tr.y, tr.z = map_odom[:3]; r.x, r.y, r.z, r.w = map_odom[3:]
            self.tf.sendTransform(t_msg)

    def _on_ekf_pose(self, msg: PoseWithCovarianceStamped):
        with self._lock:
            if self.settings is None or self.inputs.phase != 'running': return
            self.inputs.last_ekf_pose = self._now()
            self.inputs.ekf_xy_stddev_m = lc.xy_stddev(list(msg.pose.covariance))
            self.estimator.on_ekf_pose(stamp_s(msg.header.stamp), pose_of(msg.pose.pose))
            self.inputs.has_map_odom = self.estimator.map_odom is not None
        self.pose_pub.publish(msg)

    def _on_diagnostics(self, msg: DiagnosticArray):
        statuses = [(st.name, st.message, {kv.key: kv.value for kv in st.values}) for st in msg.status]
        points = lc.read_ndt_points(statuses)
        if points is not None:
            self._on_ndt_points(points)
        found = lc.read_diagnostics([(name, values) for name, _message, values in statuses])
        if not found: return
        with self._lock:
            now = self._now()
            if lc.NDT_SCORE_KEY in found:
                self.inputs.ndt_nvtl = found[lc.NDT_SCORE_KEY]; self.inputs.last_ndt_score = now
            if lc.EKF_NO_UPDATE_KEY in found:
                self.inputs.ekf_pose_no_update_count = found[lc.EKF_NO_UPDATE_KEY]; self.inputs.last_ekf_diag = now

    def _on_ndt_points(self, points):
        with self._lock:
            if self.settings is None: return
            prev, self._points_last = self._points_last, points
            first_kept = points[0] and not self._points_event.is_set()
            if points[0]: self._points_event.set()
            dropped = not points[0] and (prev is None or prev[0])   # recorded when dropping starts, not for every cloud
            if self._points_waiting and self.inputs.phase == 'initializing':
                self.inputs.phase_detail = lc.points_wait_detail(points)
        if first_kept:
            self._decision('ndt_points_kept', 'the NDT holds a point cloud; ndt_align_srv can be called', {})
        elif dropped:
            self._decision('ndt_points_dropped', f'the NDT dropped a point cloud: {points[1]}', {'message': points[1]})

    # ---- outputs ----
    def _publish_status(self):
        with self._lock:
            inp, s, map_id = self.inputs, self.settings, self.map_dir
            if s is None:
                state, reason, detail = lc.STATE_UNINITIALIZED, 'not_configured', lc.REASONS['not_configured']
            else:
                state, reason, detail = lc.evaluate(self._now(), inp, s)
            age = lc.oldest_age(self._now(), inp)
        m = EstimatorStatus(); m.header.stamp = self.get_clock().now().to_msg(); m.header.frame_id = MAP
        m.state, m.reason, m.detail, m.map_id = state, reason, detail, map_id
        nan = float('nan')
        m.ndt_nvtl = inp.ndt_nvtl if inp.ndt_nvtl is not None else nan
        m.ekf_pose_no_update_count = inp.ekf_pose_no_update_count if inp.ekf_pose_no_update_count is not None else -1
        m.ekf_xy_stddev_m = inp.ekf_xy_stddev_m if inp.ekf_xy_stddev_m is not None else nan
        m.last_input_age_s = age if age is not None else nan
        self.status_pub.publish(m)
        key = (state, reason)
        if key != self.last_state:
            self.last_state = key
            self._decision('estimator_state', f'{lc.STATE_NAMES[state]}' + (f' ({reason}: {detail})' if reason else ''),
                           {'state': state, 'reason': reason, 'ndt_nvtl': inp.ndt_nvtl, 'ekf_pose_no_update_count': inp.ekf_pose_no_update_count,
                            'ekf_xy_stddev_m': inp.ekf_xy_stddev_m, 'last_input_age_s': age, 'map_directory': map_id})

    def _decision(self, event, reason, details):
        d = DecisionEvent(); d.header.stamp = self.get_clock().now().to_msg(); d.node = 'gouda_global_localization'
        d.event = event; d.transition_id = ''; d.reason = reason; d.run_id = ''; d.section_id = -1
        d.details = json.dumps(details, ensure_ascii=False, default=str)
        self.decision_pub.publish(d)


def main(args=None):
    rclpy.init(args=args)
    node = GlobalLocalizationNode()
    executor = rclpy.executors.MultiThreadedExecutor(num_threads=3)
    executor.add_node(node)
    try: executor.spin()
    except KeyboardInterrupt: pass
    finally:
        node._stop_child(); node.destroy_node(); rclpy.try_shutdown()


if __name__ == '__main__': main()
