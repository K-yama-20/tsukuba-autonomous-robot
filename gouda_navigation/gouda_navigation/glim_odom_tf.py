"""Publish only GLIM's local LiDAR odometry TF; SLAM Toolbox owns map->odom."""
import math
import time
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from sensor_msgs.msg import PointCloud2, Imu
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import TransformStamped
from tf2_ros import TransformBroadcaster


class GlimOdomTF(Node):
    def __init__(self):
        super().__init__('glim_odom_tf')
        self.declare_parameter('odom_topic', '/glim_ros/lidar_odom')
        self.declare_parameter('odom_frame', 'odom_lidar')
        self.declare_parameter('base_frame', 'hesai_lidar')
        self._odom_frame = self.get_parameter('odom_frame').value
        self._base_frame = self.get_parameter('base_frame').value
        self.declare_parameter('lidar_topic', '/lidar_points')
        self.declare_parameter('imu_topic', '/imu/data_raw')
        self.declare_parameter('imu_frame', 'imu_link')
        self.declare_parameter('point_time_field', 'timestamp')
        self.declare_parameter('point_time_datatype', 'uint32')
        self._point_time_field = self.get_parameter('point_time_field').value
        self._point_time_datatype = self.get_parameter('point_time_datatype').value
        self._sensor_seen = {'lidar': None, 'imu': None}
        self._broadcaster = TransformBroadcaster(self)
        self._lidar_sub = self.create_subscription(PointCloud2, self.get_parameter('lidar_topic').value,
                                                   self._on_points, qos_profile_sensor_data)
        self._imu_sub = self.create_subscription(Imu, self.get_parameter('imu_topic').value,
                                                 self._on_imu, qos_profile_sensor_data)
        self._sub = self.create_subscription(Odometry, self.get_parameter('odom_topic').value, self._on_odom, 10)

    def _on_points(self, msg):
        aliases = [field for field in msg.fields if field.name in ('t', 'time', 'time_stamp', 'timestamp')]
        selected = next((field for field in msg.fields if field.name == self._point_time_field), None)
        dtype = {6: 'uint32', 7: 'float32', 8: 'float64'}.get(selected.datatype) if selected else None
        valid = (msg.header.frame_id == self._base_frame and bool(aliases) and
                 aliases[-1].name == self._point_time_field and dtype == self._point_time_datatype)
        self._sensor_seen['lidar'] = time.monotonic() if valid else None

    def _on_imu(self, msg):
        self._sensor_seen['imu'] = (time.monotonic()
                                    if msg.header.frame_id == self.get_parameter('imu_frame').value else None)

    def _on_odom(self, msg):
        # Do not relay corrected/world odometry. The native topic's parent is local odometry.
        if msg.header.frame_id != self._odom_frame or msg.child_frame_id != self._base_frame:
            self.get_logger().warning('ignoring GLIM odometry with unexpected frame IDs')
            return
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        values = (p.x, p.y, p.z, q.x, q.y, q.z, q.w)
        if not all(math.isfinite(value) for value in values):
            self.get_logger().warning('ignoring non-finite GLIM odometry')
            return
        norm = math.sqrt(q.x*q.x + q.y*q.y + q.z*q.z + q.w*q.w)
        if abs(norm - 1.0) > 0.01:
            self.get_logger().warning('ignoring GLIM odometry with invalid quaternion')
            return
        now = self.get_clock().now().nanoseconds
        if not all(self._sensor_seen.values()):
            return
        if any(time.monotonic() - stamp > 2.0 for stamp in self._sensor_seen.values()):
            return
        stamp = msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec
        if now and (stamp > now + 500_000_000 or now - stamp > 1_000_000_000):
            self.get_logger().warning('ignoring stale or future GLIM odometry')
            return
        out = TransformStamped()
        out.header = msg.header
        out.child_frame_id = msg.child_frame_id
        out.transform.translation.x = msg.pose.pose.position.x
        out.transform.translation.y = msg.pose.pose.position.y
        out.transform.translation.z = msg.pose.pose.position.z
        out.transform.rotation = msg.pose.pose.orientation
        self._broadcaster.sendTransform(out)


def main(args=None):
    rclpy.init(args=args)
    node = GlimOdomTF()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
