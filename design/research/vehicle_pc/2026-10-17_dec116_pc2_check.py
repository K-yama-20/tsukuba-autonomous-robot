# DEC-116 check: ~2 MB PointCloud2 at 10 Hz between two processes in the VM; prints how many of N arrived.
import sys, time, rclpy
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import PointCloud2, PointField
role, n = sys.argv[1], int(sys.argv[2])
qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT, history=HistoryPolicy.KEEP_LAST)
rclpy.init(); node = rclpy.create_node('dec116_' + role)
if role == 'sub':
    got = [0]; node.create_subscription(PointCloud2, '/dec116/points', lambda m: got.__setitem__(0, got[0] + 1), qos)
    end = time.time() + n / 10.0 + 8
    while time.time() < end: rclpy.spin_once(node, timeout_sec=0.1)
    print(f'received {got[0]}/{n}')
else:
    m = PointCloud2(); m.height = 1; m.width = 64000; m.point_step = 32; m.row_step = 32 * 64000
    m.fields = [PointField(name=c, offset=4 * i, datatype=7, count=1) for i, c in enumerate('xyz')]
    m.data = bytes(m.row_step)  # 2,048,000 bytes
    pub = node.create_publisher(PointCloud2, '/dec116/points', qos); time.sleep(3)
    for _ in range(n): pub.publish(m); time.sleep(0.1)
    time.sleep(2)
rclpy.shutdown()
