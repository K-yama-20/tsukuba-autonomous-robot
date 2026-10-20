"""Evaluation helper (not product code): voxel-grid downsampling of a PointCloud2 (x y z only), keeping points within
[min_range, max_range] of the sensor; republishes with the same header (frame and stamp). Stands in for the point cloud
preprocessing that autoware_ndt_scan_matcher expects upstream of it.
usage: python3 voxel_downsample.py <in_topic> <out_topic> [leaf_m=1.0] [min_range=1.0] [max_range=100.0]"""
import sys, numpy as np, rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import PointCloud2, PointField
from sensor_msgs_py import point_cloud2


class Voxel(Node):
    def __init__(self, src, dst, leaf, rmin, rmax):
        super().__init__('voxel_downsample', parameter_overrides=[Parameter('use_sim_time', Parameter.Type.BOOL, True)])
        self.leaf, self.rmin, self.rmax = leaf, rmin, rmax
        self.pub = self.create_publisher(PointCloud2, dst, qos_profile_sensor_data)
        self.create_subscription(PointCloud2, src, self.cb, qos_profile_sensor_data); self.n = 0

    def cb(self, m):
        off = {f.name: f.offset for f in m.fields}
        raw = np.frombuffer(m.data, dtype=np.uint8).reshape(-1, m.point_step)
        p = np.empty((raw.shape[0], 3), dtype=np.float32)
        for i, k in enumerate('xyz'):
            p[:, i] = raw[:, off[k]:off[k] + 4].copy().view(np.float32).ravel()
        p = p[np.isfinite(p).all(axis=1)]
        r2 = np.einsum('ij,ij->i', p, p); p = p[(r2 >= self.rmin ** 2) & (r2 <= self.rmax ** 2)]
        g = np.floor(p / self.leaf).astype(np.int64) + 1048576
        key = (g[:, 0] << 42) | (g[:, 1] << 21) | g[:, 2]
        _, idx = np.unique(key, return_index=True); q = p[np.sort(idx)]
        f = [PointField(name=n, offset=4 * i, datatype=PointField.FLOAT32, count=1) for i, n in enumerate('xyz')]
        self.pub.publish(point_cloud2.create_cloud(m.header, f, q)); self.n += 1
        if self.n % 200 == 1: self.get_logger().info(f'{len(p)} -> {len(q)} points')


def main():
    a = sys.argv[1:]
    rclpy.init(); n = Voxel(a[0], a[1], *(float(x) for x in (a[2:5] if len(a) >= 5 else (1.0, 1.0, 100.0))))
    try: rclpy.spin(n)
    except KeyboardInterrupt: pass


if __name__ == '__main__':
    main()
