"""Evaluation helper (not product code): publishes /initialpose once (map frame) taken from a reference trajectory (TUM) at the
first reference stamp >= start_stamp, optionally perturbed by (dx, dy, dyaw_deg) in the map frame. Waits until /clock passes
the pose stamp + wait_s. usage: python3 init_pose_pub.py <ref_tum> <start_stamp> [dx dy dyaw_deg] [wait_s=1.0]"""
import sys, math, numpy as np, rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from geometry_msgs.msg import PoseWithCovarianceStamped


def qmul(a, b):
    x1, y1, z1, w1 = a; x2, y2, z2, w2 = b
    return (w1*x2 + x1*w2 + y1*z2 - z1*y2, w1*y2 - x1*z2 + y1*w2 + z1*x2, w1*z2 + x1*y2 - y1*x2 + z1*w2, w1*w2 - x1*x2 - y1*y2 - z1*z2)


class InitPose(Node):
    def __init__(self, ref, t0, dx, dy, dyaw, wait):
        super().__init__('init_pose_pub', parameter_overrides=[Parameter('use_sim_time', Parameter.Type.BOOL, True)])
        T = np.loadtxt(ref); k = int(np.searchsorted(T[:, 0], t0)); self.r = T[k].copy(); self.wait = wait; self.sent = 0
        self.r[1] += dx; self.r[2] += dy
        h = math.radians(dyaw) / 2; self.r[4:8] = qmul((0, 0, math.sin(h), math.cos(h)), tuple(self.r[4:8]))
        self.pub = self.create_publisher(PoseWithCovarianceStamped, '/initialpose', 1); self.create_timer(0.1, self.tick)
        self.get_logger().info(f'initial pose at {self.r[0]:.3f}: {self.r[1:4].round(3).tolist()} (perturbation {dx}, {dy}, {dyaw} deg)')

    def tick(self):
        now = self.get_clock().now().nanoseconds * 1e-9
        if self.sent >= 3 or now < self.r[0] + self.wait: return
        m = PoseWithCovarianceStamped(); m.header.frame_id = 'map'
        m.header.stamp.sec = int(self.r[0]); m.header.stamp.nanosec = int(round((self.r[0] - int(self.r[0])) * 1e9)) % 1000000000
        p = m.pose.pose; p.position.x, p.position.y, p.position.z = self.r[1:4]
        p.orientation.x, p.orientation.y, p.orientation.z, p.orientation.w = self.r[4:8]
        m.pose.covariance[0] = m.pose.covariance[7] = 0.25; m.pose.covariance[35] = 0.07
        if self.sent == 0: self.pub.publish(m); self.get_logger().info('published /initialpose')
        self.sent = 3


def main():
    a = sys.argv[1:]
    rclpy.init(); n = InitPose(a[0], float(a[1]), *(float(x) for x in (a[2:5] if len(a) >= 5 else (0, 0, 0))), float(a[5]) if len(a) > 5 else 1.0)
    try: rclpy.spin(n)
    except KeyboardInterrupt: pass


if __name__ == '__main__':
    main()
