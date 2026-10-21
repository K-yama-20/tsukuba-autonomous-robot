"""TEST ONLY (REV-128, TS-41 VM part): synthetic sensor input for gouda_global_localization (ND-07, trial A3) without a rosbag.

The robot stands still at one pose of the mapping trajectory (trajectory_imu.txt of the converted map). The points of the
map's tiles within <radius> m of that pose, seen from it, are published as sensors/xt32/points (frame xt32_link); base_link ->
xt32_link is the identity (static TF), so base_link is that pose. localization/odometry (IFD-25) is the identity pose with
zero velocity. Then the NDT must converge to the pose, the EKF must follow and ND-07 must report 正常 with map->odom = the pose.
usage: python3 a3_synthetic_feed.py <map_directory> <trajectory row> <radius_m> <period_s> [3d]
  3d: the radius is the 3-D distance (every point nearer than radius_m; default: the horizontal distance). Used to give the
  NDT clouds whose max distance is below its required_distance (ubuntu_nd07_wait_points.sh, DEC-280).
Prints the pose (x y z qx qy qz qw) on stdout first.
"""
import math
import sys
from pathlib import Path

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from sensor_msgs.msg import PointCloud2, PointField
from tf2_ros import StaticTransformBroadcaster


def read_pcd(path):
    raw = Path(path).read_bytes(); _, _, body = raw.partition(b'DATA binary\n')
    return np.frombuffer(body, dtype='<f4').reshape(-1, 3)


def rot(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


class Feed(Node):
    def __init__(self, map_dir, row, radius, period, sphere=False):
        super().__init__('a3_synthetic_feed')
        traj = [l.split() for l in (Path(map_dir) / 'trajectory_imu.txt').read_text().splitlines() if len(l.split()) == 8]
        r = [float(v) for v in traj[row]]
        self.t, self.q = np.array(r[1:4]), r[4:8]
        pts = np.concatenate([read_pcd(p) for p in sorted((Path(map_dir) / 'pointcloud_map').glob('*.pcd'))]).astype(np.float64)
        dims = 3 if sphere else 2
        near = pts[np.linalg.norm(pts[:, :dims] - self.t[:dims], axis=1) < radius]
        self.local = ((near - self.t) @ rot(self.q)).astype('<f4')   # p_sensor = R^T (p_map - t)
        print(' '.join(f'{v:.6f}' for v in list(self.t) + list(self.q)), flush=True)
        self.get_logger().info(f'{len(self.local)} points within {radius} m of trajectory row {row}')
        st = TransformStamped(); st.header.stamp = self.get_clock().now().to_msg(); st.header.frame_id = 'base_link'; st.child_frame_id = 'xt32_link'
        st.transform.rotation.w = 1.0
        self.static = StaticTransformBroadcaster(self); self.static.sendTransform(st)
        self.pts_pub = self.create_publisher(PointCloud2, 'sensors/xt32/points', qos_profile_sensor_data)
        self.odom_pub = self.create_publisher(Odometry, 'localization/odometry', qos_profile_sensor_data)
        self.create_timer(period, self.tick)

    def tick(self):
        stamp = self.get_clock().now().to_msg()
        c = PointCloud2(); c.header.stamp = stamp; c.header.frame_id = 'xt32_link'; c.height = 1; c.width = len(self.local)
        c.fields = [PointField(name=n, offset=4 * i, datatype=PointField.FLOAT32, count=1) for i, n in enumerate('xyz')]
        c.is_bigendian = False; c.point_step = 12; c.row_step = 12 * c.width; c.is_dense = True; c.data = self.local.tobytes()
        self.pts_pub.publish(c)
        o = Odometry(); o.header.stamp = stamp; o.header.frame_id = 'odom'; o.child_frame_id = 'base_link'; o.pose.pose.orientation.w = 1.0
        self.odom_pub.publish(o)


def main():
    a = sys.argv[1:]
    rclpy.init(); n = Feed(a[0], int(a[1]), float(a[2]), float(a[3]), sphere=a[4:5] == ['3d'])
    try: rclpy.spin(n)
    except KeyboardInterrupt: pass


if __name__ == '__main__':
    main()
