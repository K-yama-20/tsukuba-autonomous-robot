"""Evaluation helper (not product code): logs a localizer's pose topic (PoseWithCovarianceStamped) and, optionally, a
diagnostics topic to CSV. usage: python3 eval_logger.py <out_prefix> [pose_topic=/pcl_pose] [diag_topic=/alignment_status]"""
import sys, json, rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import qos_profile_sensor_data, QoSProfile
from geometry_msgs.msg import PoseWithCovarianceStamped
from diagnostic_msgs.msg import DiagnosticArray


class Logger(Node):
    def __init__(self, prefix, pose_topic, diag_topic):
        super().__init__('eval_logger', parameter_overrides=[Parameter('use_sim_time', Parameter.Type.BOOL, True)])
        self.fp = open(prefix + '_pose.csv', 'w'); self.fd = open(prefix + '_diag.jsonl', 'w')
        self.fp.write('stamp,recv,x,y,z,qx,qy,qz,qw,cxx,cyy,cyaw\n')
        for q in (QoSProfile(depth=50), qos_profile_sensor_data):
            self.create_subscription(PoseWithCovarianceStamped, pose_topic, self.on_pose, q)
        if diag_topic != '-':
            self.create_subscription(DiagnosticArray, diag_topic, self.on_diag, 50)
        self.seen = set()

    def on_pose(self, m):
        s = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
        if s in self.seen: return
        self.seen.add(s); p = m.pose.pose; c = m.pose.covariance
        now = self.get_clock().now().nanoseconds * 1e-9
        self.fp.write(f'{s:.6f},{now:.6f},{p.position.x:.4f},{p.position.y:.4f},{p.position.z:.4f},{p.orientation.x:.6f},{p.orientation.y:.6f},{p.orientation.z:.6f},{p.orientation.w:.6f},{c[0]:.5g},{c[7]:.5g},{c[35]:.5g}\n'); self.fp.flush()

    def on_diag(self, m):
        now = self.get_clock().now().nanoseconds * 1e-9
        for st in m.status:
            self.fd.write(json.dumps({'t': now, 'name': st.name, 'level': int.from_bytes(st.level, 'little') if isinstance(st.level, bytes) else int(st.level), 'message': st.message, 'values': {kv.key: kv.value for kv in st.values}}) + '\n')
        self.fd.flush()


def main():
    a = sys.argv[1:]
    rclpy.init(); n = Logger(a[0], a[1] if len(a) > 1 else '/pcl_pose', a[2] if len(a) > 2 else '/alignment_status')
    try: rclpy.spin(n)
    except KeyboardInterrupt: pass


if __name__ == '__main__':
    main()
