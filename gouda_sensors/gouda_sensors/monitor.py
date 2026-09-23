import json
import time
import numpy as np

import rclpy
from rclpy.node import Node
from rclpy.clock import Clock, ClockType
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import PointCloud2
from sensor_msgs_py import point_cloud2
from std_msgs.msg import Bool, String
from .contract import CloudContract


class Monitor(Node):
    def __init__(self):
        super().__init__('cloud_monitor')
        self.declare_parameter('frame', 'hesai_lidar')
        self.declare_parameter('timeout', 0.35)
        self.contract = CloudContract(self.get_parameter('frame').value,
                                      self.get_parameter('timeout').value)
        self.health = self.create_publisher(Bool, '/gouda/lidar_healthy', 1)
        self.diag = self.create_publisher(String, '/gouda/lidar_diagnostics', 1)
        self.create_subscription(PointCloud2, '/lidar_points', self.receive, qos_profile_sensor_data)
        self.create_timer(0.05, self.tick, clock=Clock(clock_type=ClockType.STEADY_TIME))

    def receive(self, msg):
        try:
            if msg.row_step < msg.width * msg.point_step or len(msg.data) != msg.row_step * msg.height:
                raise ValueError('invalid cloud layout')
            points = point_cloud2.read_points(msg, field_names=('x', 'y', 'z'), skip_nans=False)
            finite = len(points) > 0 and all(np.isfinite(points[k]).all() for k in ('x', 'y', 'z'))
            self.contract.observe(frame=msg.header.frame_id,
                stamp=msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
                now_ros=self.get_clock().now().nanoseconds * 1e-9, now_mono=time.monotonic(),
                xyz=[(0., 0., 0.)] if finite else [], fields={f.name for f in msg.fields})
        except (ValueError, AssertionError, TypeError, KeyError):
            self.contract.valid = False
            self.contract.reason = 'MALFORMED'

    def tick(self):
        valid, reason = self.contract.check(time.monotonic(), self.get_clock().now().nanoseconds * 1e-9)
        self.health.publish(Bool(data=valid))
        self.diag.publish(String(data=json.dumps({'healthy': valid, 'reason': reason})))


def main():
    rclpy.init()
    node = Monitor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
