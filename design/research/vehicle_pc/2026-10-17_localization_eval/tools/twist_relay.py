"""Evaluation helper (not product code): from a GLIM odometry trajectory of the LiDAR (TUM), publish the body twist of a
forward-facing evaluation base frame (origin at the LiDAR, x axis = travel direction: R_lidar_base = Rz(base_yaw_in_lidar_deg))
as geometry_msgs/TwistWithCovarianceStamped, time-aligned to /clock. Used as the twist input of autoware_ekf_localizer.
usage: python3 twist_relay.py <odom_tum> <topic> [base_frame=eval_base] [base_yaw_in_lidar_deg=-99.2] [lead_s=0.05]"""
import sys, math, numpy as np, rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from geometry_msgs.msg import TwistWithCovarianceStamped


def qrot(q):
    x, y, z, w = q
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)], [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])


class TwistRelay(Node):
    def __init__(self, path, topic, frame, yaw_deg, lead):
        super().__init__('twist_relay', parameter_overrides=[Parameter('use_sim_time', Parameter.Type.BOOL, True)])
        T = np.loadtxt(path); c, s = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
        Rlb = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])
        Rb = np.array([qrot(q) @ Rlb for q in T[:, 4:8]]); dt = np.diff(T[:, 0])
        v = np.einsum('nji,nj->ni', Rb[:-1], np.diff(T[:, 1:4], axis=0)) / dt[:, None]
        Rrel = np.einsum('nji,njk->nik', Rb[:-1], Rb[1:]); wz = np.arctan2(Rrel[:, 1, 0], Rrel[:, 0, 0]) / dt
        ok = dt > 1e-3
        self.rows = np.c_[T[1:, 0][ok], v[ok, 0], wz[ok]]; self.i = 0; self.frame, self.lead = frame, lead
        self.pub = self.create_publisher(TwistWithCovarianceStamped, topic, 10); self.create_timer(0.01, self.tick)
        self.get_logger().info(f'{len(self.rows)} twists; vx median {np.median(self.rows[:,1]):.2f} m/s')

    def tick(self):
        now = self.get_clock().now().nanoseconds * 1e-9
        if now <= 0: return
        while self.i < len(self.rows) and self.rows[self.i, 0] <= now + self.lead:
            t, vx, wz = self.rows[self.i]; m = TwistWithCovarianceStamped(); m.header.frame_id = self.frame
            m.header.stamp.sec = int(t); m.header.stamp.nanosec = int(round((t - int(t)) * 1e9)) % 1000000000
            m.twist.twist.linear.x = float(vx); m.twist.twist.angular.z = float(wz)
            m.twist.covariance[0] = 0.04; m.twist.covariance[7] = 10000.0; m.twist.covariance[14] = 10000.0
            m.twist.covariance[21] = 10000.0; m.twist.covariance[28] = 10000.0; m.twist.covariance[35] = 0.01
            self.pub.publish(m); self.i += 1


def main():
    a = sys.argv[1:]
    rclpy.init(); n = TwistRelay(a[0], a[1], a[2] if len(a) > 2 else 'eval_base', float(a[3]) if len(a) > 3 else -99.2, float(a[4]) if len(a) > 4 else 0.05)
    try: rclpy.spin(n)
    except KeyboardInterrupt: pass


if __name__ == '__main__':
    main()
