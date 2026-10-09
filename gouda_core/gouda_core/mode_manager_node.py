"""gouda_mode_manager node (ND-03) — stages 5-1 / 5-2 scope.

Stage 5-1: boot transition (TR-01 / TR-02, mode_core.decide_boot), persisted previous-mode record (SO-01), mode/state
publication (IFD-01, reliable, transient_local, depth 1) and DecisionEvents (IFD-28).
Stage 5-2: the human operation services are served (IFD-02 start_autonomy, IFD-03 pause, IFD-04 resume, IFD-05
end_autonomy, IFD-06 start_mapping, IFD-07 end_mapping). Each request is evaluated against the transition table and
guards (mode_core.request_transition). Transitions whose actions are not implemented yet are refused with the stage
that implements them, and every request is recorded as a DecisionEvent. No request starts a recording or sends a goal.

Settings: state_root is a launch argument (PRM-25). state_publish_period_s (PRM-16) comes from the generated parameter
file; while unresolved the state is published only on change. No numeric value is hard-coded (RQ-I076).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from std_srvs.srv import Trigger
from gouda_interfaces.msg import SoftwareMode, DecisionEvent
from gouda_interfaces.srv import StartAutonomy

from gouda_core import mode_core

LATCHED = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=1)
DECISION_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE, history=HistoryPolicy.KEEP_LAST, depth=50)
# Transitions whose actions exist in this build. Empty in stage 5-2: the services are served, guards are applied and
# every request is recorded, but no mode change is pretended before its stage implements the actions.
IMPLEMENTED_TRANSITIONS = frozenset()


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
        # Human operation services (IFD-02..07). Trigger for all but start_autonomy (IFD-02 custom request).
        for event, name in [('pause', 'mode/pause'), ('resume', 'mode/resume'), ('end_autonomy', 'mode/end_autonomy'),
                            ('start_mapping', 'mode/start_mapping'), ('end_mapping', 'mode/end_mapping')]:
            self.create_service(Trigger, name, self._trigger_handler(event))
        self.create_service(StartAutonomy, 'mode/start_autonomy', self._start_autonomy)
        period = self.get_parameter('state_publish_period_s').get_parameter_value().double_value
        if period > 0:
            self.create_timer(period, self._publish_state)
        else:
            self.get_logger().info('state_publish_period_s (PRM-16) is unresolved: mode/state is published on change only (transient_local)')
        self.get_logger().info(f'boot transition {self.decision.transition_id}: mode={self.state.mode} ({self.decision.reason})')

    # ---- services ----
    def _trigger_handler(self, event):
        def handle(request, response):
            r = self._request(event, {})
            response.success, response.message = r.accepted, r.reason
            return response
        return handle

    def _start_autonomy(self, request, response):
        details = {'request_id': request.request_id, 'map_id': request.map_id, 'map_revision': request.map_revision,
                   'waypoint_set_id': request.waypoint_set_id, 'waypoint_set_revision': request.waypoint_set_revision}
        r = self._request('start_autonomy', details)
        response.accepted, response.message, response.run_id = r.accepted, r.reason, (r.new_state.run_id if r.accepted and r.new_state else '')
        return response

    def _request(self, event, details):
        r = mode_core.request_transition(event, self.state, IMPLEMENTED_TRANSITIONS)
        self._publish_decision('human_request', r.transition_id, r.reason, dict(details, event=event, accepted=r.accepted, mode=self.state.mode))
        (self.get_logger().info if r.accepted else self.get_logger().warning)(f'{event}: {r.reason}')
        if r.accepted and r.new_state is not None:
            self.state = r.new_state
            mode_core.PreviousModeRecord(mode=self.state.mode, human_pause_or_end=self.state.human_pause_or_end_recorded,
                                         run_id=self.state.run_id, state_revision=self.state.state_revision).save(self.record_path)
            self._publish_state()
        return r

    # ---- publication ----
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
