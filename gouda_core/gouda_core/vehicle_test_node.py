"""gouda_vehicle_test (ND-30): runs the vehicle tests of gouda_monitor's /dev tab. Idle until vehicle_test/run (IFD-71) is called.

Path: the stick command goes to vehicle/joystick_command (IFD-16), read by vehicle_bridge exactly as in autonomy. gouda_motion_controller
stays inactive and is not involved, so motion_hold (which holds in manual) and the dead-band compensation do not apply to a test.
The bridge is activated for the test and put back to the lifecycle state it was found in.

A test runs only in the manual mode and with the bridge not already active. It ends, with neutral, when the mode leaves manual or on cancel.
When the firmware reports the gamepad as the source (manual stays first, RQ-I023: nothing here touches that), or the IMU or STATUS stops, it
sends neutral, waits without a limit and repeats the current trial afterwards (DEC-414, DEC-465); cancel ends the wait. Neutral from the PC is not a guarantee that the vehicle stops: the human's means
are the vehicle's own. Sensors are only subscribed, so a test can follow a test without restarting Gouda (the IMU may freeze on restart).
"""
from __future__ import annotations

import json
import threading
import traceback
from pathlib import Path

import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from ament_index_python.packages import get_package_share_directory
from diagnostic_msgs.msg import DiagnosticArray
from lifecycle_msgs.msg import State, Transition
from lifecycle_msgs.srv import ChangeState, GetState
from sensor_msgs.msg import Imu, Joy
from tf2_ros import Buffer, TransformListener
from gouda_interfaces.action import VehicleTest
from gouda_interfaces.msg import DecisionEvent, SoftwareMode

from gouda_core import vehicle_test_core as core
from gouda_core.vehicle_core import MODE_AUTONOMY, MODE_MANUAL
from gouda_core.vehicle_tests import TESTS

LATCHED = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=1)
DECISION_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=50)  # IFD-28
COMMAND_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE, history=HistoryPolicy.KEEP_LAST, depth=1)    # IFD-16
STATUS_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE, history=HistoryPolicy.KEEP_LAST, depth=10)   # IFD-38
SENSOR_QOS = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, durability=DurabilityPolicy.VOLATILE, history=HistoryPolicy.KEEP_LAST, depth=50)
BRIDGE = 'vehicle_bridge'
BASE_FRAME = 'base_link'


def rotation_from_quaternion(q) -> list:
    x, y, z, w = q.x, q.y, q.z, q.w
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]


class VehicleTestNode(Node):
    def __init__(self):
        super().__init__('gouda_vehicle_test')
        self.declare_parameter('data_root', '')
        root = self.get_parameter('data_root').get_parameter_value().string_value
        if not root:
            raise RuntimeError('data_root is not set (PRM-25)')
        self.root = Path(root).expanduser() / 'vehicle_tests'
        self.share = Path(get_package_share_directory('gouda_core')) / 'vehicle_tests'
        self.cb = ReentrantCallbackGroup()
        self.lock = threading.Lock()
        self.mode = None; self.busy = False; self.run = None
        self.joy_pub = self.create_publisher(Joy, 'vehicle/joystick_command', COMMAND_QOS)
        self.decision_pub = self.create_publisher(DecisionEvent, 'log/decision', DECISION_QOS)
        self.create_subscription(SoftwareMode, 'mode/state', self._on_mode, LATCHED, callback_group=self.cb)
        self.change = self.create_client(ChangeState, f'{BRIDGE}/change_state', callback_group=self.cb)
        self.get_state = self.create_client(GetState, f'{BRIDGE}/get_state', callback_group=self.cb)
        self.tf = Buffer(); self.tf_listener = TransformListener(self.tf, self, spin_thread=False)
        self.server = ActionServer(self, VehicleTest, 'vehicle_test/run', execute_callback=self._execute, goal_callback=self._on_goal,
                                   cancel_callback=lambda _: CancelResponse.ACCEPT, callback_group=self.cb)

    def _now(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    def _on_mode(self, m: SoftwareMode):
        self.mode = int(m.mode)

    def _on_goal(self, goal) -> GoalResponse:
        with self.lock:
            if self.busy: return GoalResponse.REJECT
            self.busy = True
        return GoalResponse.ACCEPT

    # ---- bridge lifecycle ----
    def _call(self, client, req, timeout):
        if not client.wait_for_service(timeout_sec=timeout):
            raise RuntimeError(f'{client.srv_name} is not available')
        fut = client.call_async(req); done = threading.Event(); fut.add_done_callback(lambda _: done.set())
        if not done.wait(timeout) or fut.exception() is not None:
            raise RuntimeError(f'{client.srv_name}: no response')
        return fut.result()

    def _bridge_state(self, timeout) -> int:
        return self._call(self.get_state, GetState.Request(), timeout).current_state.id

    def _bridge_transition(self, tid, timeout):
        req = ChangeState.Request(); req.transition.id = tid
        if not self._call(self.change, req, timeout).success:
            raise RuntimeError(f'{BRIDGE} lifecycle transition {tid} failed (see log/decision)')

    def _bridge_activate(self, timeout) -> int:
        """Returns the state it was found in. Already active means someone else drives through it: refused."""
        found = self._bridge_state(timeout)
        if found == State.PRIMARY_STATE_ACTIVE:
            raise RuntimeError(f'{BRIDGE} is already active')
        if found == State.PRIMARY_STATE_UNCONFIGURED:
            self._bridge_transition(Transition.TRANSITION_CONFIGURE, timeout)
        self._bridge_transition(Transition.TRANSITION_ACTIVATE, timeout)
        return found

    def _bridge_restore(self, found, timeout):
        """Back to the state found, except that a mode that now owns the bridge (autonomy) keeps it."""
        if self.mode == MODE_AUTONOMY: return
        self._bridge_transition(Transition.TRANSITION_DEACTIVATE, timeout)
        if found == State.PRIMARY_STATE_UNCONFIGURED and self.mode == MODE_MANUAL:
            self._bridge_transition(Transition.TRANSITION_CLEANUP, timeout)

    # ---- inputs during a test ----
    def _imu_rotation(self, frame):
        """base_link <- IMU from TF (the sensor /config), or None: the detection then uses the norms and the result says so."""
        try:
            return rotation_from_quaternion(self.tf.lookup_transform(BASE_FRAME, frame, rclpy.time.Time()).transform.rotation)
        except Exception:
            return None

    def _on_imu(self, m: Imu):
        r = self.run
        if r is None: return
        t = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
        if not t: t = self._now()
        if 'rotation' not in r:
            r['rotation'] = self._imu_rotation(m.header.frame_id)
            r['axes'] = 'base_link' if r['rotation'] else 'norm'
        a, w = m.linear_acceleration, m.angular_velocity
        sa, sy = core.imu_signals(a.x, a.y, a.z, w.x, w.y, w.z, r['rotation'])
        with self.lock:
            if self.run is None: return
            r['writer'].imu.writerow([t, a.x, a.y, a.z, w.x, w.y, w.z, sa, sy])
            r['imu_rx'] = self._now()
            r['seq'].feed_imu(t, sa, sy)

    def _on_status(self, arr: DiagnosticArray):
        r = self.run
        if r is None: return
        for st in arr.status:
            if st.name != 'esp32': continue
            d = {kv.key: kv.value for kv in st.values}
            t = self._now()
            with self.lock:
                if self.run is None: return
                r['writer'].status.writerow([t] + [d.get(c, '') for c in core.STATUS_COLUMNS[1:]])
                r['status_rx'] = t; r['source'] = d.get('source', ''); r['reason'] = d.get('reason', '')
                try: r['uptime'].append(float(d['uptime_ms'])); r['status_t'].append(t)
                except (KeyError, ValueError): pass

    # ---- the test ----
    def _publish(self, forward, turn, r=None, trial='', segment=''):
        joy = Joy(); joy.header.stamp = self.get_clock().now().to_msg(); joy.axes = [float(forward), float(turn)]
        self.joy_pub.publish(joy)
        if r is not None:
            with self.lock:
                r['writer'].command.writerow([self._now(), forward, turn, trial, segment])

    def _decision(self, event, reason, details):
        d = DecisionEvent(); d.header.stamp = self.get_clock().now().to_msg(); d.node = 'gouda_vehicle_test'
        d.event = event; d.transition_id = ''; d.reason = reason; d.run_id = details.get('run_id', ''); d.section_id = -1
        d.details = json.dumps(details, ensure_ascii=False, default=str)
        self.decision_pub.publish(d)

    def _finish(self, gh, ok, message, run_id, end_reason):
        res = VehicleTest.Result(); res.ok, res.message, res.run_id, res.end_reason = ok, message, run_id, end_reason
        if gh.is_cancel_requested: gh.canceled()
        elif ok: gh.succeed()
        else: gh.abort()
        self._decision('vehicle_test_end', message, {'run_id': run_id, 'end_reason': end_reason})
        return res

    def _execute(self, gh):
        try:
            return self._run_test(gh)
        except Exception as e:
            self.get_logger().error(traceback.format_exc())
            return self._finish(gh, False, f'test failed: {e}', '', core.END_ERROR)
        finally:
            with self.lock:
                self.busy = False

    def _run_test(self, gh):
        tid = gh.request.test_id
        mod = TESTS.get(tid)
        if mod is None:
            return self._finish(gh, False, f'unknown test {tid!r}', '', core.END_REFUSED)
        definition = core.load_definition(self.share / f'{tid}.yaml')
        params, errors = core.validate_params(definition, json.loads(gh.request.params_json or '{}'))
        if errors:
            return self._finish(gh, False, '; '.join(errors), '', core.END_REFUSED)
        if self.mode != MODE_MANUAL:
            return self._finish(gh, False, f'the mode is not manual (mode {self.mode}): the test is not started', '', core.END_REFUSED)
        rs = definition['runner']
        trials = mod.build_trials(params)
        try:
            found = self._bridge_activate(rs['service_timeout_s'])
        except RuntimeError as e:
            return self._finish(gh, False, str(e), '', core.END_REFUSED)
        run_id, end, message = '', core.END_ERROR, ''
        imu_sub = status_sub = None
        try:
            writer = core.RunWriter(self.root, tid, params, {'title': definition.get('title'), 'started_at': self._now()})
            run_id = writer.run_id
            self._decision('vehicle_test_start', f'{tid} started from the /dev tab', {'run_id': run_id, 'params': params})
            events = []
            def on_event(e):
                events.append(e); writer.event(e)
            r = {'writer': writer, 'seq': core.Sequencer(trials, params, on_event), 'uptime': [], 'status_t': [], 'imu_rx': None, 'status_rx': None, 'source': '', 'reason': ''}
            self.run = r
            imu_sub = self.create_subscription(Imu, 'sensors/imu/data', self._on_imu, SENSOR_QOS, callback_group=self.cb)
            status_sub = self.create_subscription(DiagnosticArray, '/esp32/status', self._on_status, STATUS_QOS, callback_group=self.cb)
            end, message = self._drive(gh, r, rs, run_id)
            self.run = None
            for _ in range(max(1, int(rs['neutral_after_s'] / rs['command_period_s']))):
                self._publish(0.0, 0.0); threading.Event().wait(rs['command_period_s'])
            writer.close()
            result = self._analyze(mod, params, trials, events, writer, r, end, message)
            writer.write_result(result)
        finally:
            self.run = None
            for s in (imu_sub, status_sub):
                if s: self.destroy_subscription(s)
            self._publish(0.0, 0.0)
            try:
                self._bridge_restore(found, rs['service_timeout_s'])
            except RuntimeError as e:
                self._decision('vehicle_test_bridge_restore_failed', str(e), {'run_id': run_id})
        return self._finish(gh, end == core.END_COMPLETED, message or end, run_id, end)

    def _drive(self, gh, r, rs, run_id) -> tuple:
        period = rs['command_period_s']; tick = threading.Event(); fb = VehicleTest.Feedback(); fb.run_id = run_id
        seq = r['seq']; t_start = self._now(); ready = False; lost = None
        while True:
            t = self._now()
            if gh.is_cancel_requested: seq.abort(t); return core.END_CANCELLED, 'cancelled from the /dev tab'
            if self.mode != MODE_MANUAL: seq.abort(t); return core.END_MODE, f'the mode left manual (mode {self.mode})'
            # the firmware takes a neutral COMMAND first (PC source enable), and the gamepad keeps priority over it
            if not ready:
                ready = r['imu_rx'] is not None and r['status_rx'] is not None and r['source'] == 'pc'
                if not ready:
                    if t - t_start > rs['ready_timeout_s'] and r['source'] != 'pc':
                        return core.END_REFUSED, f"not ready: imu={'ok' if r['imu_rx'] else 'none'} status={'ok' if r['status_rx'] else 'none'} source={r['source'] or 'none'} reason={r['reason'] or 'none'}{' ESP32 の USB の差し直しが要る可能性があります（TRB-014）' if r.get('reason') == 'pc_stale' else ''}"
                    self._publish(0.0, 0.0, r); tick.wait(period); continue
            else:
                now_lost = core.wait_reason(r['source'], t - r['imu_rx'], t - r['status_rx'], rs['imu_timeout_s'], rs['status_timeout_s'], lost)
                if now_lost:
                    if lost is None:
                        r['retries'] = r.get('retries', 0) + 1
                        seq.on_event({'t': t, 'event': 'link_lost', 'what': now_lost, 'count': r['retries']})
                        self._decision('vehicle_test_link_lost', f'{now_lost}: neutral, the trial repeats when it is over', {'run_id': run_id, 'count': r['retries']})
                    lost = now_lost
                    self._publish(0.0, 0.0, r)
                    fb.stage, fb.progress = f"{ {'imu': 'IMU', 'status': 'STATUS', 'manual': 'ゲームパッド'}[now_lost]} 待ち（再試行 {r['retries']} 回目）", float(seq.progress()[1]); gh.publish_feedback(fb)
                    tick.wait(period); continue
                if lost:
                    lost = None
                    with self.lock: seq.retry(t)
            with self.lock:
                forward, turn = seq.command(t)
                done = seq.done; stage, progress = seq.progress()
                tr = seq.trials[seq.ti].id if 0 <= seq.ti < len(seq.trials) else ''; si = seq.si
            self._publish(forward, turn, r, tr, si)
            fb.stage, fb.progress = stage, float(progress); gh.publish_feedback(fb)
            if done: return core.END_COMPLETED, 'completed'
            tick.wait(period)

    def _analyze(self, mod, params, trials, events, writer, r, end, message) -> dict:
        status = core.read_csv(writer.dir / 'status.csv')
        clock = core.fit_clock(status.get('uptime_ms', []), status.get('t_rx', []))
        sigma = next((e.get('sigma') for e in events if e['event'] == 'baseline_end'), None)
        run = {'trials': trials, 'events': events, 'status': status, 'clock': clock, 'sigma': sigma, 'axes': r.get('axes'), 'imu': core.read_csv(writer.dir / 'imu.csv')}
        return dict(mod.analyze(run, params), retries=r.get('retries', 0), end_reason=end, message=message, status='実測値（人の確認待ち）')


def main(args=None):
    rclpy.init(args=args)
    node = VehicleTestNode()
    ex = MultiThreadedExecutor()
    ex.add_node(node)
    try: ex.spin()
    except KeyboardInterrupt: pass
    finally:
        node.destroy_node(); rclpy.try_shutdown()


if __name__ == '__main__': main()
