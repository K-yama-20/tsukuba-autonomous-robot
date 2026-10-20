"""gouda_static_tf (ND-13): the only publisher of the static TF of the vehicle (IFD-20, RQ-I058, RQ-I004).

base_link -> base_footprint (directly below, z = -PRM-05; base_link's only parent is odom, IFD-19) and base_link -> xt32_link / imu_link / gnss_link / gnss_aux1_link from the
human's /config (IFD-26, <data_root>/config/sensor_config.json, written by gouda_monitor). The poses are computed by
sensor_extrinsics, the same code that gives GLIM its T_lidar_imu, so the TF and GLIM agree.
- A field still UNKNOWN in /config is replaced by the neutral element (no translation, no rotation, base_link axes) and the
  list is recorded (DecisionEvent static_tf_published). Unknown mountings never stop anything (intent.md:105, RQ-I081,
  DEC-122 replaces the earlier "no TF while unset").
- /config is read at start and again after every /config save (the monitor records event=settings with the revision); the
  transforms are sent again only when the revision changed.
Settings: data_root (launch argument), base_link_z_m (PRM-05, from the generated parameter file). No number is written here.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from geometry_msgs.msg import TransformStamped
from tf2_msgs.msg import TFMessage
from gouda_interfaces.msg import DecisionEvent

from gouda_core import sensor_extrinsics
from gouda_core.monitor_core import SensorConfig

# /tf_static as tf2 publishes it (transient_local, depth 1). The whole set is sent every time: rclpy's StaticTransformBroadcaster
# keeps the first transform of a child frame and does not replace it on a later send (seen in the VM test of 2026-10-17).
TF_STATIC_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=1)
DECISION_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=50)  # IFD-28 (DEC-072)


class StaticTfNode(Node):
    def __init__(self):
        super().__init__('gouda_static_tf')
        self.declare_parameter('data_root', '')
        self.declare_parameter('base_link_z_m', Parameter.Type.DOUBLE)   # PRM-05
        root = self.get_parameter('data_root').get_parameter_value().string_value
        if not root:
            raise RuntimeError('data_root is not set (PRM-25). Pass it from the launch file.')
        self.config_path = Path(os.path.expanduser(root)) / 'config' / 'sensor_config.json'
        try:
            self.base_link_z = self.get_parameter('base_link_z_m').value
        except Exception:
            self.base_link_z = None
        self.decision_pub = self.create_publisher(DecisionEvent, 'log/decision', DECISION_QOS)
        self.tf_static_pub = self.create_publisher(TFMessage, '/tf_static', TF_STATIC_QOS)
        self.revision = None
        self.create_subscription(DecisionEvent, 'log/decision', self._on_decision, DECISION_QOS)
        self._publish()

    def _on_decision(self, d: DecisionEvent):
        if d.node == 'gouda_monitor' and d.event == 'settings':
            self._publish()

    def _publish(self):
        cfg = SensorConfig(self.config_path)
        if self.revision is not None and cfg.config_revision == self.revision:
            return
        if not isinstance(self.base_link_z, float):
            self._decision('static_tf_not_published', 'base_link_z_m (PRM-05) is not set: no static TF', {})
            return
        res = sensor_extrinsics.static_transforms(dict(cfg.values), self.base_link_z)
        now = self.get_clock().now().to_msg()
        msgs = []
        for t in res['transforms']:
            m = TransformStamped(); m.header.stamp = now; m.header.frame_id = t['parent']; m.child_frame_id = t['child']
            m.transform.translation.x, m.transform.translation.y, m.transform.translation.z = (float(v) for v in t['translation'])
            (m.transform.rotation.x, m.transform.rotation.y, m.transform.rotation.z, m.transform.rotation.w) = (float(v) for v in t['rotation'])
            msgs.append(m)
        self.tf_static_pub.publish(TFMessage(transforms=msgs))
        self.revision = cfg.config_revision
        reason = f'static TF published for /config revision {cfg.config_revision}' + (
            f" (UNKNOWN in /config, neutral used: {', '.join(res['defaulted_fields'])})" if res['defaulted_fields'] else '') + (
            f" (problems: {'; '.join(res['problems'])})" if res['problems'] else '')
        self._decision('static_tf_published', reason, {'config_revision': cfg.config_revision, 'config_path': str(cfg.path),
                                                        'transforms': res['transforms'], 'defaulted_fields': res['defaulted_fields'],
                                                        'problems': res['problems']})

    def _decision(self, event, reason, details):
        d = DecisionEvent(); d.header.stamp = self.get_clock().now().to_msg(); d.node = 'gouda_static_tf'
        d.event = event; d.transition_id = ''; d.reason = reason; d.run_id = ''; d.section_id = -1
        d.details = json.dumps(details, ensure_ascii=False, default=str)
        self.decision_pub.publish(d)
        self.get_logger().info(f'{event}: {reason}')


def main(args=None):
    rclpy.init(args=args)
    node = StaticTfNode()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally:
        node.destroy_node(); rclpy.try_shutdown()


if __name__ == '__main__': main()
