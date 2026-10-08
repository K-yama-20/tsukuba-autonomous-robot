"""gouda_mode_manager node (ND-03) — stage 5-1 scope: boot transition and mode/state publication.

At start-up it reads the persisted previous-mode record (SO-01), applies TR-01 / TR-02 (mode_core.decide_boot), persists the
new record, publishes mode/state (IFD-01, reliable, transient_local, depth 1) and a DecisionEvent (IFD-28). It never starts
a recording and never sends a navigation goal (RQ-I015, RQ-I025). The mode services (IFD-02..07), motion_hold (IFD-40) and
the other transitions are added in later stages (docs/implementation_stages.md).

Settings: state_root is a launch argument (PRM-25 data root). state_publish_period_s (PRM-16) is read from the generated
parameter file; while it is unresolved (tbd) the state is published only on change, which transient_local makes
sufficient for late subscribers. No numeric value is hard-coded (RQ-I076).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from gouda_interfaces.msg import SoftwareMode, DecisionEvent

from gouda_core import mode_core

LATCHED = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=1)
DECISION_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE, history=HistoryPolicy.KEEP_LAST, depth=50)


class ModeManagerNode(Node):
    def __init__(self):
        super().__init__('gouda_mode_manager')
        self.declare_parameter('state_root', '')                # PRM-25 (launch argument)
        self.declare_parameter('state_publish_period_s', 0.0)   # PRM-16; 0.0 means "unresolved: publish on change only"
        root = self.get_parameter('state_root').get_parameter_value().string_value
        if not root:
            raise RuntimeError('state_root is not set (PRM-25). Pass it from gouda.sh / the launch file.')
        self.record_path = Path(os.path.expanduser(root)) / 'previous_mode_record.json'
        self.state_pub = self.create_publisher(SoftwareMode, 'mode/state', LATCHED)
        self.decision_pub = self.create_publisher(DecisionEvent, 'log/decision', DECISION_QOS)
        record = mode_core.PreviousModeRecord.load(self.record_path)
        self.decision = mode_core.decide_boot(record)
        self.state = self.decision.state
        mode_core.record_after_boot(self.decision).save(self.record_path)
        self._publish_state()
        self._publish_decision('boot', self.decision.transition_id, self.decision.reason,
                               dict(self.decision.details, record_path=str(self.record_path), record_found=self.decision.record_found))
        period = self.get_parameter('state_publish_period_s').get_parameter_value().double_value
        if period > 0:
            self.create_timer(period, self._publish_state)
        else:
            self.get_logger().info('state_publish_period_s (PRM-16) is unresolved: mode/state is published on change only (transient_local)')
        self.get_logger().info(f'boot transition {self.decision.transition_id}: mode={self.state.mode} ({self.decision.reason})')

    def _publish_state(self):
        s = self.state; m = SoftwareMode()
        m.header.stamp = self.get_clock().now().to_msg()
        m.mode = mode_core.MODE_CODES[s.mode]; m.processing_state = s.processing_state; m.run_id = s.run_id
        m.remaining_waypoints = s.remaining_waypoints; m.current_section = s.current_section; m.stop_reason = s.stop_reason
        m.speed_limit_application_state = s.speed_limit_application_state
        m.previous_mode = mode_core.MODE_CODES.get(s.previous_mode, 0); m.human_pause_or_end_recorded = s.human_pause_or_end_recorded
        m.initial_pose_required = s.initial_pose_required; m.state_revision = s.state_revision
        self.state_pub.publish(m)

    def _publish_decision(self, event: str, transition_id: str, reason: str, details: dict):
        d = DecisionEvent(); d.header.stamp = self.get_clock().now().to_msg(); d.node = 'gouda_mode_manager'
        d.event = event; d.transition_id = transition_id; d.reason = reason; d.run_id = self.state.run_id; d.section_id = -1
        d.details = json.dumps(details, ensure_ascii=False, default=str)
        self.decision_pub.publish(d)


def main(args=None):
    rclpy.init(args=args)
    node = ModeManagerNode()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally:
        node.destroy_node(); rclpy.try_shutdown()


if __name__ == '__main__': main()
