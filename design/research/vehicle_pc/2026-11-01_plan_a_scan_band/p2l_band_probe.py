"""第167便 probe (domain 96, test only): synthetic cloud in base_link -> xt32_scan (our parameters) -> check the scan."""
import math
import struct
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import PointCloud2, PointField, LaserScan


def cloud(stamp):
    pts = []
    for i in range(-30, 31):            # ground at base_link z -0.165 (below the band -0.065), 0.1..4.9 m ahead
        for j in range(1, 50):
            pts.append((j * 0.1, i * 0.1, -0.165))
    for k in range(0, 7):               # a box 2.0 m ahead, y -0.2..0.2, z -0.1..0.5 (in the band)
        for i in range(-2, 3):
            pts.append((2.0, i * 0.1, -0.1 + k * 0.1))
    for i in range(-5, 6):              # an overhang at z 1.5 m, 1.0 m to the left (above the band 1.085)
        pts.append((i * 0.1, 1.0, 1.5))
    m = PointCloud2(); m.header.frame_id = 'base_link'; m.header.stamp = stamp
    m.height, m.width = 1, len(pts)
    m.fields = [PointField(name=n, offset=4 * k, datatype=PointField.FLOAT32, count=1) for k, n in enumerate('xyz')]
    m.point_step, m.row_step, m.is_dense, m.is_bigendian = 12, 12 * len(pts), True, False
    m.data = b''.join(struct.pack('<fff', *p) for p in pts)
    return m


rclpy.init(); n = Node('_p2l_probe_167')
pub = n.create_publisher(PointCloud2, '/sensors/xt32/points', qos_profile_sensor_data)
got = []
n.create_subscription(LaserScan, '/sensors/xt32/scan', got.append, qos_profile_sensor_data)
end = time.monotonic() + 8
while time.monotonic() < end and len(got) < 3:
    pub.publish(cloud(n.get_clock().now().to_msg())); rclpy.spin_once(n, timeout_sec=0.2)
if not got:
    print('NO SCAN'); raise SystemExit(1)
s = got[-1]


def at(deg):
    i = int(round((math.radians(deg) - s.angle_min) / s.angle_increment)); return s.ranges[i]


finite = [(round(math.degrees(s.angle_min + i * s.angle_increment), 1), round(r, 2)) for i, r in enumerate(s.ranges) if math.isfinite(r)]
print('frame', s.header.frame_id, 'beams', len(s.ranges), 'finite', len(finite))
print('ahead 0 deg:', round(at(0), 3), '| left 90 deg (overhang above band):', at(90), '| 45 deg (ground only):', at(45))
print('finite beams (deg, m):', finite[:12])
