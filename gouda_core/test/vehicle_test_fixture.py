"""Test only: synthetic IMU for the /dev test on the stack. Feeds vehicle_motion_model from the applied values in /esp32/status."""
import sys
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from diagnostic_msgs.msg import DiagnosticArray
from sensor_msgs.msg import Imu

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vehicle_motion_model import Model   # noqa: E402

IMU_PERIOD_S = 0.005


class Fixture(Node):
    def __init__(self):
        super().__init__('vehicle_test_fixture')
        self.m = Model(); self.applied = (0.0, 0.0)
        self.pub = self.create_publisher(Imu, 'sensors/imu/data', QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, durability=DurabilityPolicy.VOLATILE, history=HistoryPolicy.KEEP_LAST, depth=50))
        self.create_subscription(DiagnosticArray, '/esp32/status', self.on_status, QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE, history=HistoryPolicy.KEEP_LAST, depth=10))
        self.create_timer(IMU_PERIOD_S, self.tick)

    def on_status(self, arr):
        for st in arr.status:
            if st.name == 'esp32':
                d = {k.key: k.value for k in st.values}
                self.applied = (float(d['applied_y_q10000']) / 10000, -float(d['applied_x_q10000']) / 10000)

    def tick(self):
        t = self.get_clock().now().nanoseconds * 1e-9
        self.m.command(t, *self.applied)
        a, w = self.m.imu(t)
        msg = Imu(); msg.header.stamp = self.get_clock().now().to_msg(); msg.header.frame_id = 'imu_link'
        msg.linear_acceleration.x = a; msg.angular_velocity.z = w
        self.pub.publish(msg)


rclpy.init(); n = Fixture()
try: rclpy.spin(n)
except KeyboardInterrupt: pass
