"""gouda_a3_points (part of ND-07's trial A3; REV-148, DEC-283 plan a): the point pre-processing of the NDT in one process.

Started only by gouda_localization_a3.launch.py (the child launch of gouda_global_localization), in the namespace
localization/a3: input (remapped to sensors/xt32/points, IFD-21) -> a3_points.filter_points -> output (points_downsampled,
x, y, z FLOAT32, same header). The settings PRM-79..81 and PRM-102 are passed by the launch; a missing one stops the node (nothing is filled
in). A cloud that cannot be read (no FLOAT32 x, y, z) is not published and the reason is logged (throttled by message count,
not by time: the first and then every 100th).
"""
from __future__ import annotations

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import PointCloud2, PointField

from gouda_core import a3_points

SETTINGS = ('points_near_crop_m', 'points_far_crop_m', 'points_voxel_leaf_m')   # PRM-79, PRM-80, PRM-81
MIN_POINTS = 'points_voxel_min_points'                                           # PRM-102
LOG_EVERY = 100   # a repeated read error is logged for the first and every LOG_EVERY-th cloud (log volume, not a vehicle value)


class A3PointsNode(Node):
    def __init__(self):
        super().__init__('points_filter')
        for k in SETTINGS:
            self.declare_parameter(k, Parameter.Type.DOUBLE)
        self.declare_parameter(MIN_POINTS, Parameter.Type.INTEGER)
        missing = [k for k in SETTINGS if self.get_parameter(k).type_ != Parameter.Type.DOUBLE]
        missing += [MIN_POINTS] if self.get_parameter(MIN_POINTS).type_ != Parameter.Type.INTEGER else []
        if missing:
            raise SystemExit(f'gouda_a3_points: settings missing {missing} (PRM-79..81, PRM-102 from gouda_global_localization)')
        self.near, self.far, self.leaf = (self.get_parameter(k).value for k in SETTINGS)
        self.min_points = self.get_parameter(MIN_POINTS).value
        a3_points.filter_points(np.zeros((0, 3)), self.near, self.far, self.leaf, self.min_points)   # validates the settings once
        self.errors = 0
        self.pub = self.create_publisher(PointCloud2, 'output', qos_profile_sensor_data)
        self.create_subscription(PointCloud2, 'input', self._on_cloud, qos_profile_sensor_data)
        self.get_logger().info(f'near {self.near} m, far {self.far} m, leaf {self.leaf} m, min points {self.min_points} (PRM-79..81, PRM-102)')

    def _on_cloud(self, m: PointCloud2):
        try:
            p = a3_points.xyz_view(m.data, m.point_step, m.width * m.height, a3_points.xyz_offsets(m.fields), m.is_bigendian)
        except ValueError as e:
            self.errors += 1
            if self.errors % LOG_EVERY == 1:
                self.get_logger().error(f'cloud not used ({self.errors} so far): {e}')
            return
        q = a3_points.filter_points(p, self.near, self.far, self.leaf, self.min_points)
        o = PointCloud2(); o.header = m.header; o.height = 1; o.width = len(q)
        o.fields = [PointField(name=n, offset=4 * i, datatype=PointField.FLOAT32, count=1) for i, n in enumerate('xyz')]
        o.is_bigendian = False; o.point_step = 12; o.row_step = 12 * o.width; o.is_dense = True; o.data = q.tobytes()
        self.pub.publish(o)


def main(args=None):
    rclpy.init(args=args)
    node = A3PointsNode()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally:
        node.destroy_node(); rclpy.try_shutdown()


if __name__ == '__main__': main()
