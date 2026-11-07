"""gouda_motion_controller node (ND-11) — stage 5-5 (vehicle output), lifecycle node around MotionCore.

Subscribes cmd_vel (IFD-15, geometry_msgs/TwistStamped since PRM-12 was approved true (DEC-122, REV-061), reliable,
volatile, depth 1; the staleness is still judged by the receive time (PRM-08), the header.stamp is not used for it) and control/motion_hold (IFD-40, gouda_interfaces/MotionHold, reliable, transient_local, depth 1).
Publishes vehicle/joystick_command (IFD-16, sensor_msgs/Joy, reliable, volatile, depth 1; axes[0]=forward, axes[1]=turn,
[-1, 1]) every command_publish_period_s (PRM-41) while ACTIVE; nothing is published while inactive (manual / mapping
modes: no non-neutral command leaves this node). Publishes log/decision (IFD-28, transient_local 50) on every change of
the output reason.

Neutral is output when motion_hold is true / not received / older than motion_hold_timeout_s (PRM-42), and when cmd_vel is
not received / older than cmd_vel_timeout_s (PRM-08) / not finite (DEC-004, RQ-I063). Reversing is normalized by
max_reverse_speed_mps (PRM-78, DEC-172). Nothing here reduces the speed below cmd_vel (RQ-I020) except the dead-band
compensation's threshold (DEC-171 plan A): config/motion_compensation (IFD-52, gouda_interfaces/MotionCompensation, reliable,
transient_local, depth 1) from the monitor's /config is subscribed in every lifecycle state and used from the next output on
(DEC-181); every received setting is recorded. Until one is received, and for a direction that is not set, nothing is
compensated. Every threshold comes from design/generated/params/gouda_motion_controller.yaml (approved values)
and gouda_motion_controller.trial.yaml (software trial values, stub tests only); no number is written here (RQ-I076, DR-15).

REV-241 (DEC-450, #65): the speed-feedback layer. The feedforward table (DEC-445, PRM-150..160) comes from the generated file;
on/off, the PI gains, the integral limits and the odometry timeout come with IFD-52 from /config (off until the human turns it
on). It reads localization/odometry (IFD-25: twist.linear.x, twist.angular.z in base_link, by receive time) and the ESP32
source from /esp32/status (IFD-38; "manual" = manual priority: neutral and the integrals reset while the layer is on). Every
output is published on log/motion_feedback (gouda_interfaces/MotionFeedback, reliable, volatile, depth 10) for the rosbag, and a
change of the layer's mode (ff_pi / ff_only / neutral / no_feedforward) is a DecisionEvent (speed_feedback_mode).

REV-285 (DEC-507): the dead-band floor (motion_core) with the hysteresis floor_hysteresis_mps (PRM-166) from the generated file:
with the layer off the axes are driven by the floor and the table (mode 'floor' in log/motion_feedback and speed_feedback_mode);
MPPI's vx_min is 0 since then. Each change of an axis' floor branch (zero / below_half / move_stick / table / compensation) is a
DecisionEvent (motion_floor).
"""
from __future__ import annotations

import json
import math
import threading

import rclpy
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from rclpy.parameter import Parameter
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import TwistStamped
from sensor_msgs.msg import Joy
from nav_msgs.msg import Odometry
from diagnostic_msgs.msg import DiagnosticArray
from gouda_interfaces.msg import MotionHold, DecisionEvent, MotionCompensation, MotionFeedback

from gouda_core.motion_core import (MotionCore, MotionSettings, Compensation, NO_COMPENSATION, Feedback, NO_FEEDBACK, Feedforward,
                                    FeedforwardAxis, FEEDBACK_FIELDS)

LATCHED = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=1)
DECISION_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=50)  # IFD-28 (DEC-072)
COMMAND_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE, history=HistoryPolicy.KEEP_LAST, depth=1)
SETTINGS = ['cmd_vel_timeout_s', 'max_linear_speed_mps', 'max_angular_speed_radps', 'command_publish_period_s', 'motion_hold_timeout_s', 'max_reverse_speed_mps']
COMPENSATION_FIELDS = ('forward_min', 'forward_threshold', 'reverse_min', 'reverse_threshold', 'turn_min', 'turn_threshold')
# REV-241: the measured stick -> speed points (DEC-445; PRM-150..160)
FEEDFORWARD_SETTINGS = ['ff_forward_stop_stick', 'ff_forward_move_stick', 'ff_forward_min_speed_mps',
                        'ff_reverse_stop_stick', 'ff_reverse_move_stick', 'ff_reverse_min_speed_mps',
                        'ff_turn_stop_stick', 'ff_turn_move_stick', 'ff_turn_min_speed_radps', 'ff_turn_mid_stick', 'ff_turn_mid_speed_radps']
FLOOR_SETTING = 'floor_hysteresis_mps'   # REV-285 (DEC-507): PRM-166
STATUS_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE, history=HistoryPolicy.KEEP_LAST, depth=10)   # IFD-38
FEEDBACK_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE, history=HistoryPolicy.KEEP_LAST, depth=10)


def compensation_from_msg(msg) -> Compensation:
    """IFD-52 -> Compensation; NaN (not set) becomes None."""
    vals = {k: float(getattr(msg, k)) for k in COMPENSATION_FIELDS}
    return Compensation(**{k: (v if math.isfinite(v) else None) for k, v in vals.items()}, config_revision=int(msg.config_revision))


def feedback_from_msg(msg) -> Feedback:
    """IFD-52 (REV-241) -> Feedback; NaN (not set) becomes None; a message without the fields is 'off'."""
    if not hasattr(msg, 'speed_feedback_enabled'):
        return NO_FEEDBACK
    vals = {k: float(getattr(msg, k)) for k in FEEDBACK_FIELDS[1:]}
    return Feedback(bool(msg.speed_feedback_enabled), **{k: (v if math.isfinite(v) else None) for k, v in vals.items()})


def feedforward_from_values(v: dict):
    """The generated values -> Feedforward, or None when one is missing. The full-stick speeds are PRM-39 / PRM-78 / PRM-40."""
    if any(v.get(k) is None for k in FEEDFORWARD_SETTINGS):
        return None
    return Feedforward(
        FeedforwardAxis(v['ff_forward_stop_stick'], v['ff_forward_move_stick'], v['ff_forward_min_speed_mps'], v['max_linear_speed_mps']),
        FeedforwardAxis(v['ff_reverse_stop_stick'], v['ff_reverse_move_stick'], v['ff_reverse_min_speed_mps'], v['max_reverse_speed_mps']),
        FeedforwardAxis(v['ff_turn_stop_stick'], v['ff_turn_move_stick'], v['ff_turn_min_speed_radps'], v['max_angular_speed_radps'],
                        v['ff_turn_mid_stick'], v['ff_turn_mid_speed_radps']))


def esp32_source(msg) -> str:
    """IFD-38 -> the STATUS source ('manual', 'pc', 'none'), '' when it is not in the message."""
    for st in msg.status:
        if st.name == 'esp32':
            for kv in st.values:
                if kv.key == 'source':
                    return kv.value
    return ''


def _nan(v):
    return math.nan if v is None else float(v)


def optional_double(node, name):
    try:
        prm = node.get_parameter(name)
    except Exception:
        return None
    return prm.value if prm.type_ == Parameter.Type.DOUBLE else None


class MotionControllerNode(LifecycleNode):
    def __init__(self):
        super().__init__('gouda_motion_controller')
        for key in SETTINGS + FEEDFORWARD_SETTINGS + [FLOOR_SETTING]:
            self.declare_parameter(key, Parameter.Type.DOUBLE)
        self._lock = threading.Lock()
        self.core = None
        self.timer = None
        self.cmd_sub = self.hold_sub = None
        self.joy_pub = None
        self.decision_pub = self.create_publisher(DecisionEvent, 'log/decision', DECISION_QOS)
        self.last_reason = None
        self.compensation = NO_COMPENSATION   # the last usable IFD-52 setting; kept across configure / cleanup
        self.feedback = NO_FEEDBACK           # REV-241: the last usable speed-feedback setting (IFD-52)
        self.feedback_revision = 0
        self.last_fb_mode = None
        self.last_floor = None
        self.odom_sub = self.status_sub = None
        self.fb_pub = None
        self.create_subscription(MotionCompensation, 'config/motion_compensation', self._on_compensation, LATCHED)
        self.get_logger().info('unconfigured; settings are read on configure from the generated parameter file')

    # ---- lifecycle ----
    def on_configure(self, state) -> TransitionCallbackReturn:
        values = {k: optional_double(self, k) for k in SETTINGS}
        missing = [k for k, v in values.items() if v is None]
        if missing:
            self.get_logger().error(f'unresolved settings {missing}: pass design/generated/params/gouda_motion_controller.yaml (and the trial file for stub tests)')
            self._decision('configure_refused', f'settings missing: {missing}', values)
            return TransitionCallbackReturn.FAILURE
        ffv = dict(values, **{k: optional_double(self, k) for k in FEEDFORWARD_SETTINGS})
        ff = feedforward_from_values(ffv)
        try:
            hyst = optional_double(self, FLOOR_SETTING)
            self.core = MotionCore(MotionSettings(values['cmd_vel_timeout_s'], values['max_linear_speed_mps'], values['max_angular_speed_radps'], values['motion_hold_timeout_s'], values['max_reverse_speed_mps']), ff, hyst)
        except ValueError as e:
            self._decision('configure_refused', str(e), values); return TransitionCallbackReturn.FAILURE
        with self._lock:
            self.core.set_compensation(self.compensation)
            self.core.set_feedback(self.feedback)
        values = dict(values, compensation=self._compensation_details(self.compensation), feedforward={k: ffv[k] for k in FEEDFORWARD_SETTINGS},
                      feedforward_problems=self.core.feedforward_problems, speed_feedback=self._feedback_details(self.feedback),
                      floor_hysteresis_mps=hyst, floor_used=self.core.floor_ready())
        self.period = values['command_publish_period_s']
        self.joy_pub = self.create_lifecycle_publisher(Joy, 'vehicle/joystick_command', COMMAND_QOS)
        self.hold_sub = self.create_subscription(MotionHold, 'control/motion_hold', self._on_hold, LATCHED)
        self.cmd_sub = self.create_subscription(TwistStamped, 'cmd_vel', self._on_cmd_vel, COMMAND_QOS)
        self.odom_sub = self.create_subscription(Odometry, 'localization/odometry', self._on_odometry, qos_profile_sensor_data)   # IFD-25
        self.status_sub = self.create_subscription(DiagnosticArray, '/esp32/status', self._on_esp32_status, STATUS_QOS)          # IFD-38
        self.fb_pub = self.create_lifecycle_publisher(MotionFeedback, 'log/motion_feedback', FEEDBACK_QOS)
        self._decision('settings', 'configured from generated parameters', values)
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state) -> TransitionCallbackReturn:
        self.timer = self.create_timer(self.period, self._publish)
        self._decision('activated', 'joystick_command publication started (period PRM-41)', {})
        return super().on_activate(state)

    def on_deactivate(self, state) -> TransitionCallbackReturn:
        if self.timer: self.destroy_timer(self.timer); self.timer = None
        with self._lock:
            if self.core: self.core.reset_feedback()
        self._decision('deactivated', 'joystick_command publication stopped; nothing is sent while inactive', {})
        return super().on_deactivate(state)

    def on_cleanup(self, state) -> TransitionCallbackReturn:
        for s in (self.cmd_sub, self.hold_sub, self.odom_sub, self.status_sub):
            if s: self.destroy_subscription(s)
        for pub in (self.joy_pub, self.fb_pub):
            if pub: self.destroy_publisher(pub)
        self.cmd_sub = self.hold_sub = self.odom_sub = self.status_sub = self.joy_pub = self.fb_pub = None; self.core = None
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state) -> TransitionCallbackReturn:
        if self.timer: self.destroy_timer(self.timer); self.timer = None
        return TransitionCallbackReturn.SUCCESS

    # ---- inputs ----
    def _now(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    def _on_cmd_vel(self, msg: TwistStamped):
        with self._lock:
            if self.core: self.core.on_cmd_vel(msg.twist.linear.x, msg.twist.angular.z, self._now())

    def _on_hold(self, msg: MotionHold):
        with self._lock:
            if self.core: self.core.on_motion_hold(msg.hold, msg.reason, msg.mode, self._now())

    def _on_odometry(self, msg: Odometry):
        with self._lock:
            if self.core: self.core.on_odometry(msg.twist.twist.linear.x, msg.twist.twist.angular.z, self._now())

    def _on_esp32_status(self, msg: DiagnosticArray):
        src = esp32_source(msg)
        if src:
            with self._lock:
                if self.core: self.core.on_vehicle_source(src)

    @staticmethod
    def _feedback_details(f: Feedback) -> dict:
        return {k: (f.enabled if k == 'speed_feedback_enabled' else getattr(f, k)) for k in FEEDBACK_FIELDS}

    @staticmethod
    def _compensation_details(c: Compensation) -> dict:
        return {'config_revision': c.config_revision, 'compensated_directions': c.active_directions(),
                **{k: getattr(c, k) for k in COMPENSATION_FIELDS}}

    def _on_compensation(self, msg: MotionCompensation):
        """IFD-52 (DEC-181): used from the next output on, also while driving. A setting with values outside [0, 1) is not used."""
        c = compensation_from_msg(msg)
        bad = c.problems()
        fb = feedback_from_msg(msg)
        fb_bad = fb.problems()
        with self._lock:
            if not bad:
                self.compensation = c
                if self.core: self.core.set_compensation(c)
            if not fb_bad:
                self.feedback = fb; self.feedback_revision = c.config_revision
                if self.core: self.core.set_feedback(fb)
        fdetails = dict(self._feedback_details(fb), config_revision=c.config_revision)
        if fb_bad:
            self._decision('speed_feedback_refused', f'speed feedback of revision {c.config_revision} not used: {"; ".join(fb_bad)}', fdetails)
        else:
            self._decision('speed_feedback_settings', f'speed feedback revision {c.config_revision}: ' + ('on' if fb.enabled else 'off')
                           + ('' if not fb.enabled or fb.pi_ready() else ' (PI values not set: feedforward alone)'), fdetails)
        details = self._compensation_details(c)
        if bad:
            self._decision('compensation_refused', f'dead-band compensation revision {c.config_revision} not used: {"; ".join(bad)}', details)
        else:
            dirs = c.active_directions()
            self._decision('compensation_settings', f'dead-band compensation revision {c.config_revision}: ' + (', '.join(dirs) if dirs else 'no direction set (not compensated)'), details)

    # ---- output ----
    def _publish(self):
        with self._lock:
            if not self.core or not self.joy_pub: return
            t = self._now(); out = self.core.output(t)
            joy = Joy(); joy.header.stamp = self.get_clock().now().to_msg(); joy.axes = [float(out.forward), float(out.turn)]
            self.joy_pub.publish(joy)
            self._publish_feedback(joy.header.stamp, out)
            fbm = (out.feedback_mode, out.feedback_reason.split(' (')[0])
            if fbm != self.last_fb_mode:
                self.last_fb_mode = fbm
                self._decision('speed_feedback_mode', f'speed feedback {out.feedback_mode}' + (f': {out.feedback_reason}' if out.feedback_reason else ''),
                               {'mode': out.feedback_mode, 'reason': out.feedback_reason, 'odometry_age_s': out.odometry_age_s, 'config_revision': self.feedback_revision})
            fl = (out.floor_forward, out.floor_turn)
            if fl != self.last_floor:   # REV-285 (DEC-507): the floor's branch of each axis
                self.last_floor = fl
                cmd = self.core.cmd or (math.nan, math.nan)
                self._decision('motion_floor', f'floor forward {out.floor_forward or "-"}, turn {out.floor_turn or "-"}',
                               {'forward_branch': out.floor_forward, 'turn_branch': out.floor_turn, 'target_linear_x': cmd[0], 'target_angular_z': cmd[1],
                                'forward': out.forward, 'turn': out.turn})
            reason = (out.reason, out.hold_reason, out.neutral)
            if reason != self.last_reason:
                self.last_reason = reason
                self._decision('output_neutral' if out.neutral else 'output_drive', f'{out.reason}' + (f' ({out.hold_reason})' if out.hold_reason else ''),
                               dict(self.core.state(t), forward=out.forward, turn=out.turn, normalized_forward=out.normalized_forward, normalized_turn=out.normalized_turn))

    def _publish_feedback(self, stamp, out):
        if not self.fb_pub: return
        m = MotionFeedback(); m.header.stamp = stamp; m.header.frame_id = 'base_link'; m.config_revision = int(self.feedback_revision)
        m.mode = out.feedback_mode; m.reason = out.feedback_reason
        cmd = self.core.cmd or (math.nan, math.nan); odom = self.core.odom or (math.nan, math.nan)
        m.target_linear_x, m.target_angular_z = float(cmd[0]), float(cmd[1])
        m.measured_linear_x, m.measured_angular_z = float(odom[0]), float(odom[1])
        m.odometry_age_s = _nan(out.odometry_age_s)
        for name, terms, val in (('forward', out.forward_terms, out.forward), ('turn', out.turn_terms, out.turn)):
            setattr(m, f'{name}_ff', _nan(terms.ff) if terms else math.nan)
            setattr(m, f'{name}_p', _nan(terms.p) if terms else math.nan)
            setattr(m, f'{name}_i', _nan(terms.i) if terms else math.nan)
            setattr(m, f'{name}_out', float(val))
        self.fb_pub.publish(m)

    def _decision(self, event, reason, details):
        d = DecisionEvent(); d.header.stamp = self.get_clock().now().to_msg(); d.node = 'gouda_motion_controller'
        d.event = event; d.transition_id = ''; d.reason = reason; d.run_id = ''; d.section_id = -1
        d.details = json.dumps(details, ensure_ascii=False, default=str)
        self.decision_pub.publish(d)


def main(args=None):
    rclpy.init(args=args)
    node = MotionControllerNode()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally:
        node.destroy_node(); rclpy.try_shutdown()


if __name__ == '__main__': main()
