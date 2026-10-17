"""Evaluation helper (not product code): replays a GLIM odometry trajectory (TUM: stamp x y z qx qy qz qw) as TF
odom_frame -> child_frame, time-aligned to /clock (use_sim_time). Each pose is sent when the clock is within `lead_s` of its stamp.
usage: python3 odom_replay.py <tum_file> [odom_frame=odom] [child_frame=xt32_link] [lead_s=0.15]"""
import sys, numpy as np, rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from tf2_ros import TransformBroadcaster
from geometry_msgs.msg import TransformStamped


class OdomReplay(Node):
    def __init__(self, path, odom, child, lead):
        super().__init__('odom_replay', parameter_overrides=[Parameter('use_sim_time', Parameter.Type.BOOL, True)])
        self.T = np.loadtxt(path); self.i = 0; self.odom, self.child, self.lead = odom, child, lead
        self.br = TransformBroadcaster(self); self.create_timer(0.01, self.tick)
        self.get_logger().info(f'{len(self.T)} poses {self.T[0,0]:.3f}..{self.T[-1,0]:.3f}')

    def tick(self):
        now = self.get_clock().now().nanoseconds * 1e-9
        if now <= 0: return
        while self.i < len(self.T) and self.T[self.i, 0] <= now + self.lead:
            r = self.T[self.i]; m = TransformStamped()
            m.header.stamp.sec = int(r[0]); m.header.stamp.nanosec = int(round((r[0] - int(r[0])) * 1e9)) % 1000000000
            m.header.frame_id = self.odom; m.child_frame_id = self.child
            m.transform.translation.x, m.transform.translation.y, m.transform.translation.z = r[1:4]
            m.transform.rotation.x, m.transform.rotation.y, m.transform.rotation.z, m.transform.rotation.w = r[4:8]
            self.br.sendTransform(m); self.i += 1


def main():
    a = sys.argv[1:]
    rclpy.init(); n = OdomReplay(a[0], a[1] if len(a) > 1 else 'odom', a[2] if len(a) > 2 else 'xt32_link', float(a[3]) if len(a) > 3 else 0.15)
    try: rclpy.spin(n)
    except KeyboardInterrupt: pass


if __name__ == '__main__':
    main()
