"""gouda_motion_controller node (ND-11) — stage 5-5 (vehicle output), lifecycle node around MotionCore.

Subscribes cmd_vel (IFD-15, geometry_msgs/Twist, reliable, volatile, depth 1; Nav2 jazzy default type. TwistStamped is
PRM-12, unresolved) and control/motion_hold (IFD-40, gouda_interfaces/MotionHold, reliable, transient_local, depth 1).
Publishes vehicle/joystick_command (IFD-16, sensor_msgs/Joy, reliable, volatile, depth 1; axes[0]=forward, axes[1]=turn,
[-1, 1]) every command_publish_period_s (PRM-41) while ACTIVE; nothing is published while inactive (manual / mapping
modes: no non-neutral command leaves this node). Publishes log/decision (IFD-28, transient_local 50) on every change of
the output reason.

Neutral is output when motion_hold is true / not received / older than motion_hold_timeout_s (PRM-42), and when cmd_vel is
not received / older than cmd_vel_timeout_s (PRM-08) / not finite (DEC-004, RQ-I063). Nothing here reduces the speed
below cmd_vel (RQ-I020). Every threshold comes from design/generated/params/gouda_motion_controller.yaml (approved values)
and gouda_motion_controller.trial.yaml (software trial values, stub tests only); no number is written here (RQ-I076, DR-15).
"""
from __future__ import annotations

import json
import threading

import rclpy
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from rclpy.parameter import Parameter
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Joy
from gouda_interfaces.msg import MotionHold, DecisionEvent

from gouda_core.motion_core import MotionCore, MotionSettings

LATCHED = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=1)
DECISION_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=50)  # IFD-28 (DEC-072)
COMMAND_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE, history=HistoryPolicy.KEEP_LAST, depth=1)
SETTINGS = ['cmd_vel_timeout_s', 'max_linear_speed_mps', 'max_angular_speed_radps', 'command_publish_period_s', 'motion_hold_timeout_s']


def optional_double(node, name):
    try:
        prm = node.get_parameter(name)
    except Exception:
        return None
    return prm.value if prm.type_ == Parameter.Type.DOUBLE else None


class MotionControllerNode(LifecycleNode):
    def __init__(self):
        super().__init__('gouda_motion_controller')
        for key in SETTINGS:
            self.declare_parameter(key, Parameter.Type.DOUBLE)
        self._lock = threading.Lock()
        self.core = None
        self.timer = None
        self.cmd_sub = self.hold_sub = None
        self.joy_pub = None
        self.decision_pub = self.create_publisher(DecisionEvent, 'log/decision', DECISION_QOS)
        self.last_reason = None
        self.get_logger().info('unconfigured; settings are read on configure from the generated parameter file')

    # ---- lifecycle ----
    def on_configure(self, state) -> TransitionCallbackReturn:
        values = {k: optional_double(self, k) for k in SETTINGS}
        missing = [k for k, v in values.items() if v is None]
        if missing:
            self.get_logger().error(f'unresolved settings {missing}: pass design/generated/params/gouda_motion_controller.yaml (and the trial file for stub tests)')
            self._decision('configure_refused', f'settings missing: {missing}', values)
            return TransitionCallbackReturn.FAILURE
        try:
            self.core = MotionCore(MotionSettings(values['cmd_vel_timeout_s'], values['max_linear_speed_mps'], values['max_angular_speed_radps'], values['motion_hold_timeout_s']))
        except ValueError as e:
            self._decision('configure_refused', str(e), values); return TransitionCallbackReturn.FAILURE
        self.period = values['command_publish_period_s']
        self.joy_pub = self.create_lifecycle_publisher(Joy, 'vehicle/joystick_command', COMMAND_QOS)
        self.hold_sub = self.create_subscription(MotionHold, 'control/motion_hold', self._on_hold, LATCHED)
        self.cmd_sub = self.create_subscription(Twist, 'cmd_vel', self._on_cmd_vel, COMMAND_QOS)
        self._decision('settings', 'configured from generated parameters', values)
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state) -> TransitionCallbackReturn:
        self.timer = self.create_timer(self.period, self._publish)
        self._decision('activated', 'joystick_command publication started (period PRM-41)', {})
        return super().on_activate(state)

    def on_deactivate(self, state) -> TransitionCallbackReturn:
        if self.timer: self.destroy_timer(self.timer); self.timer = None
        self._decision('deactivated', 'joystick_command publication stopped; nothing is sent while inactive', {})
        return super().on_deactivate(state)

    def on_cleanup(self, state) -> TransitionCallbackReturn:
        for s in (self.cmd_sub, self.hold_sub):
            if s: self.destroy_subscription(s)
        if self.joy_pub: self.destroy_publisher(self.joy_pub)
        self.cmd_sub = self.hold_sub = self.joy_pub = None; self.core = None
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state) -> TransitionCallbackReturn:
        if self.timer: self.destroy_timer(self.timer); self.timer = None
        return TransitionCallbackReturn.SUCCESS

    # ---- inputs ----
    def _now(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    def _on_cmd_vel(self, msg: Twist):
        with self._lock:
            if self.core: self.core.on_cmd_vel(msg.linear.x, msg.angular.z, self._now())

    def _on_hold(self, msg: MotionHold):
        with self._lock:
            if self.core: self.core.on_motion_hold(msg.hold, msg.reason, msg.mode, self._now())

    # ---- output ----
    def _publish(self):
        with self._lock:
            if not self.core or not self.joy_pub: return
            t = self._now(); out = self.core.output(t)
            joy = Joy(); joy.header.stamp = self.get_clock().now().to_msg(); joy.axes = [float(out.forward), float(out.turn)]
            self.joy_pub.publish(joy)
            reason = (out.reason, out.hold_reason, out.neutral)
            if reason != self.last_reason:
                self.last_reason = reason
                self._decision('output_neutral' if out.neutral else 'output_drive', f'{out.reason}' + (f' ({out.hold_reason})' if out.hold_reason else ''),
                               dict(self.core.state(t), forward=out.forward, turn=out.turn))

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
