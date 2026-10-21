"""TEST ONLY (stage 5-6 VM test, REV-128): a stand-in for gouda_global_localization (ND-07) without sensors.

A lifecycle node with the same name and the same interface towards the mode manager: map_directory, configure / activate /
deactivate / cleanup, and localization/status (IFD-53, transient_local). It publishes no TF (the Nav2 loopback simulator gives
map -> odom -> base_link in the test). While active it reports 正常 every <period> s; the test changes that with
  test/nd07_stub_state (std_msgs/UInt8: the EstimatorStatus state to report) and
  test/nd07_stub_silent (std_msgs/Bool: true = stop publishing, to test the mode manager's timeout PRM-93).
usage: python3 nd07_stub.py <period_s>
"""
import sys

import rclpy
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from std_msgs.msg import UInt8, Bool
from gouda_interfaces.msg import EstimatorStatus

LATCHED = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=1)


class Nd07Stub(LifecycleNode):
    def __init__(self, period):
        super().__init__('gouda_global_localization')
        self.declare_parameter('map_directory', '')
        self.pub = self.create_publisher(EstimatorStatus, 'localization/status', LATCHED)
        self.state, self.silent, self.active = EstimatorStatus.STATE_UNINITIALIZED, False, False
        self.create_subscription(UInt8, 'test/nd07_stub_state', lambda m: setattr(self, 'state', m.data), 10)
        self.create_subscription(Bool, 'test/nd07_stub_silent', lambda m: setattr(self, 'silent', m.data), 10)
        self.create_timer(period, self._tick)
        self._publish()

    def on_configure(self, state):
        self.get_logger().info(f"configured with map_directory {self.get_parameter('map_directory').value}")
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state):
        self.active, self.state = True, EstimatorStatus.STATE_NORMAL
        return super().on_activate(state)

    def on_deactivate(self, state):
        self.active, self.state = False, EstimatorStatus.STATE_UNINITIALIZED
        self._publish()
        return super().on_deactivate(state)

    def on_cleanup(self, state):
        return TransitionCallbackReturn.SUCCESS

    def _tick(self):
        if self.active and not self.silent:
            self._publish()

    def _publish(self):
        m = EstimatorStatus(); m.header.stamp = self.get_clock().now().to_msg(); m.header.frame_id = 'map'
        m.state = self.state
        m.reason = '' if self.state == EstimatorStatus.STATE_NORMAL else 'test_stub'
        m.detail = 'nd07_stub (test only)'; m.ndt_nvtl = float('nan'); m.ekf_pose_no_update_count = -1
        m.ekf_xy_stddev_m = float('nan'); m.last_input_age_s = float('nan'); m.map_id = str(self.get_parameter('map_directory').value)
        self.pub.publish(m)


def main():
    rclpy.init()
    n = Nd07Stub(float(sys.argv[1]))
    try: rclpy.spin(n)
    except KeyboardInterrupt: pass
    finally:
        n.destroy_node(); rclpy.try_shutdown()


if __name__ == '__main__':
    main()
