"""gouda_local_odometry (ND-08 relay, REV-061, DEC-123): localization/odometry (IFD-25) from GLIM's odometry-only TF.

GLIM runs odometry only in 自律走行・一時停止 (started by the mode manager, glim_runner odometry_only) and publishes
odom -> odom_glim -> base_link. This node listens to /tf; for each new odom_glim -> base_link it composes odom -> base_link
(with the latest odom -> odom_glim, identity without global mapping) and publishes nav_msgs/Odometry (header odom, child
base_link, pose, body twist from the difference of the last two poses: odometry_core). It publishes nothing while GLIM is not
running (it never invents a pose). It does not publish TF (GLIM's TF is already the odom -> base_link of ND-08).
QoS of IFD-25 (best effort, volatile, the depth of the design) is rclpy's sensor-data profile. No setting value here.
"""
from __future__ import annotations

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy, qos_profile_sensor_data
from nav_msgs.msg import Odometry
from tf2_msgs.msg import TFMessage

from gouda_core import odometry_core as oc
from gouda_core.glim_runner import ODOMETRY_ONLY_FRAMES

ODOM, GLIM_ODOM, BASE = 'odom', ODOMETRY_ONLY_FRAMES['odom'], 'base_link'
IFD25_QOS = qos_profile_sensor_data   # best effort, volatile, keep last 5 (IFD-25)
TF_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE, history=HistoryPolicy.KEEP_LAST, depth=100)


def pose_of(t) -> oc.Pose:
    tr, r = t.transform.translation, t.transform.rotation
    return (tr.x, tr.y, tr.z, r.x, r.y, r.z, r.w)


class LocalOdometryNode(Node):
    def __init__(self):
        super().__init__('gouda_local_odometry')
        self.pub = self.create_publisher(Odometry, 'localization/odometry', IFD25_QOS)
        self.odom_to_glim: oc.Pose = oc.IDENTITY
        self.prev = None   # (pose, t)
        self.create_subscription(TFMessage, '/tf', self._on_tf, TF_QOS)

    def _on_tf(self, msg: TFMessage):
        for t in msg.transforms:
            if t.header.frame_id == ODOM and t.child_frame_id == GLIM_ODOM:
                self.odom_to_glim = pose_of(t)
            elif t.header.frame_id == GLIM_ODOM and t.child_frame_id == BASE:
                self._publish(t)

    def _publish(self, t):
        stamp = t.header.stamp.sec + t.header.stamp.nanosec * 1e-9
        pose = oc.compose(self.odom_to_glim, pose_of(t))
        m = Odometry(); m.header.stamp = t.header.stamp; m.header.frame_id = ODOM; m.child_frame_id = BASE
        p = m.pose.pose
        p.position.x, p.position.y, p.position.z = pose[:3]
        p.orientation.x, p.orientation.y, p.orientation.z, p.orientation.w = pose[3:]
        if self.prev is not None:
            tw = oc.body_twist(self.prev[0], self.prev[1], pose, stamp)
            if tw is not None:
                m.twist.twist.linear.x, m.twist.twist.linear.y, m.twist.twist.linear.z, m.twist.twist.angular.z = tw
        self.prev = (pose, stamp)
        self.pub.publish(m)


def main(args=None):
    rclpy.init(args=args)
    node = LocalOdometryNode()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally:
        node.destroy_node(); rclpy.try_shutdown()


if __name__ == '__main__': main()
