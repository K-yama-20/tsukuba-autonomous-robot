"""Provisional sensor-plane scan. No body transform or IMU fusion is invented."""
import math
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import PointCloud2, LaserScan
from sensor_msgs_py.point_cloud2 import read_points


def project(x, y, z, low=-.15, high=.15, bins=720, near=.4, far=20.):
    r = np.hypot(x, y)
    valid = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
    valid &= (z >= low) & (z <= high) & (r >= near) & (r <= far)
    angles = np.arctan2(y[valid], x[valid])
    indices = np.floor((angles + math.pi) * bins / (2 * math.pi)).astype(int) % bins
    ranges = np.full(bins, np.inf)
    np.minimum.at(ranges, indices, r[valid])
    return ranges.tolist()


class Scan(Node):
    def __init__(self):
        super().__init__('gouda_sensor_plane_scan')
        self.declare_parameter('min_height', -.15)
        self.declare_parameter('max_height', .15)
        self.pub = self.create_publisher(LaserScan, '/scan', qos_profile_sensor_data)
        self.create_subscription(PointCloud2, '/lidar_points', self.cloud, qos_profile_sensor_data)

    def cloud(self, msg):
        if msg.header.frame_id != 'hesai_lidar':
            return
        p = read_points(msg, field_names=('x', 'y', 'z'), skip_nans=False)
        scan = LaserScan(); scan.header = msg.header
        scan.angle_min = -math.pi; scan.angle_increment = 2 * math.pi / 720
        scan.angle_max = scan.angle_min + 719 * scan.angle_increment
        scan.range_min = .4; scan.range_max = 20.; scan.scan_time = .1
        # Frame already spans one rotation. Deskew is disabled pending clock calibration.
        scan.time_increment = 0.
        scan.ranges = project(p['x'], p['y'], p['z'],
                             self.get_parameter('min_height').value,
                             self.get_parameter('max_height').value)
        self.pub.publish(scan)


def main():
    rclpy.init(); node = Scan()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally:
        node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()
