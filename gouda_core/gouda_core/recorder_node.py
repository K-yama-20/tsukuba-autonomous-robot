"""gouda_recorder node (ND-04): ROS wrapper around RecorderCore.

Services (std_srvs/Trigger): record/log/start (IFD-08, human Record), record/log/stop (IFD-09, human Stop Record),
record/log/start_autodrive (IFD-44) and record/log/start_pre_mapping (IFD-45) called by gouda_mode_manager only when a
human start operation was accepted (DR-16), record/log/stop_auto (IFD-46) stopping only an auto-started log,
record/rosbag/start (IFD-10), record/rosbag/stop (IFD-11). All log entrances share one start procedure and state
(RecorderCore.start_log); the origin and trigger are kept and written to the log (DEC-071).
Subscribes mode/state (IFD-01) and log/decision (IFD-28, transient_local) and writes them to the log.
Publishes record/status (IFD-12, diagnostic_msgs/DiagnosticArray, reliable, transient_local, depth 1) on every change.

Settings come from the generated parameter file (design/generated/params/gouda_recorder.yaml). record_root is a launch
argument (PRM-25). No numeric value is hard-coded here (RQ-I076).
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from std_srvs.srv import Trigger
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from gouda_interfaces.msg import SoftwareMode, DecisionEvent

from gouda_core.recorder_core import RecorderCore, TRIGGER_HUMAN, TRIGGER_AUTO_AUTONOMY_START, TRIGGER_AUTO_MAP_START

LATCHED = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=1)
DECISION_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=50)  # IFD-28 (DEC-072)


class RecorderNode(Node):
    def __init__(self):
        super().__init__('gouda_recorder')
        self.declare_parameter('record_root', '')   # PRM-25 (launch argument; no default value in code)
        root = self.get_parameter('record_root').get_parameter_value().string_value
        if not root:
            raise RuntimeError('record_root is not set (PRM-25). Pass it from gouda.sh / the launch file.')
        self._bag_proc: subprocess.Popen | None = None
        self._bag_stopping = False
        # Service callbacks and the rosbag watcher thread both change RecorderCore; one lock serialises them.
        self._lock = threading.RLock()
        self.core = RecorderCore(Path(os.path.expanduser(root)), clock=self._now, rosbag_start=self._bag_start, rosbag_stop=self._bag_stop)
        self.status_pub = self.create_publisher(DiagnosticArray, 'record/status', LATCHED)
        self.create_service(Trigger, 'record/log/start', lambda rq, rs: self._svc(rs, self.core.start_log, TRIGGER_HUMAN))
        self.create_service(Trigger, 'record/log/stop', lambda rq, rs: self._svc(rs, self.core.stop_log, TRIGGER_HUMAN))
        self.create_service(Trigger, 'record/log/start_autodrive', lambda rq, rs: self._svc(rs, self.core.start_log, TRIGGER_AUTO_AUTONOMY_START))
        self.create_service(Trigger, 'record/log/start_pre_mapping', lambda rq, rs: self._svc(rs, self.core.start_log, TRIGGER_AUTO_MAP_START))
        self.create_service(Trigger, 'record/log/stop_auto', lambda rq, rs: self._svc(rs, lambda _t: self.core.stop_auto(), None))
        self.create_service(Trigger, 'record/rosbag/start', lambda rq, rs: self._svc(rs, self.core.start_rosbag, TRIGGER_HUMAN))
        self.create_service(Trigger, 'record/rosbag/stop', lambda rq, rs: self._svc(rs, self.core.stop_rosbag, TRIGGER_HUMAN))
        self.create_subscription(SoftwareMode, 'mode/state', self._on_mode, LATCHED)
        self.create_subscription(DecisionEvent, 'log/decision', self._on_decision, DECISION_QOS)
        self._publish_status()
        self.get_logger().info(f'gouda_recorder ready; record_root={self.core.record_root} (recording is NOT started at boot: RQ-I015)')

    def _now(self) -> float:
        t = self.get_clock().now().seconds_nanoseconds()
        return t[0] + t[1] * 1e-9

    def _svc(self, rs, fn, trigger):
        with self._lock:
            ok, msg = fn(trigger)
        rs.success, rs.message = ok, msg
        if ok:   # one call site per severity (rclpy raises when a call site's severity changes)
            self.get_logger().info(msg)
        else:
            self.get_logger().warning(msg)
        self._publish_status()
        return rs

    def _on_mode(self, msg: SoftwareMode):
        self.core.record('input', 'mode/state', self._now(), {
            'stamp': msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9, 'mode': int(msg.mode), 'processing_state': msg.processing_state,
            'run_id': msg.run_id, 'remaining_waypoints': int(msg.remaining_waypoints), 'current_section': int(msg.current_section),
            'stop_reason': msg.stop_reason, 'speed_limit_application_state': msg.speed_limit_application_state,
            'previous_mode': int(msg.previous_mode), 'human_pause_or_end_recorded': bool(msg.human_pause_or_end_recorded),
            'initial_pose_required': bool(msg.initial_pose_required), 'state_revision': int(msg.state_revision)})
        self._publish_status_if_changed()

    def _on_decision(self, msg: DecisionEvent):
        self.core.record('decision', 'log/decision', self._now(), {
            'stamp': msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9, 'node': msg.node, 'event': msg.event, 'transition_id': msg.transition_id,
            'reason': msg.reason, 'run_id': msg.run_id, 'section_id': int(msg.section_id), 'input_names': list(msg.input_names),
            'input_stamps': [s.sec + s.nanosec * 1e-9 for s in msg.input_stamps], 'details': msg.details})
        self._publish_status_if_changed()

    # ---- rosbag child process (RQ-I016: separate folder of the same session) ----
    def _bag_start(self, out_dir: Path):
        """Start `ros2 bag record` into out_dir (a new folder per start). Its output goes to out_dir.log next to it, and a
        watcher thread reports the process ending without a stop request (G-REC-ROSBAG-RESTART: the failure was silent)."""
        if self._bag_proc and self._bag_proc.poll() is None:
            return
        log_path = out_dir.parent / (out_dir.name + '.log')
        log_file = open(log_path, 'ab')
        try:
            proc = subprocess.Popen(['ros2', 'bag', 'record', '-a', '-o', str(out_dir)], stdout=log_file, stderr=subprocess.STDOUT, start_new_session=True)
        finally:
            log_file.close()   # the child keeps its own descriptor
        self._bag_proc = proc; self._bag_stopping = False
        threading.Thread(target=self._watch_bag, args=(proc, log_path), name='rosbag_watch', daemon=True).start()

    def _watch_bag(self, proc: subprocess.Popen, log_path: Path):
        code = proc.wait()
        with self._lock:
            if proc is not self._bag_proc or self._bag_stopping:
                return   # stopped by a request (or replaced): not a failure
            self._bag_proc = None
            ok, msg = self.core.rosbag_exited(code, 'last output: ' + ' | '.join(_tail(log_path)))
            self._publish_status()
        if ok:
            self.get_logger().warning(msg)   # the only warning call site of this method (rclpy: one severity per call site)

    def _bag_stop(self):
        p = self._bag_proc
        if p and p.poll() is None:
            self._bag_stopping = True
            os.killpg(os.getpgid(p.pid), signal.SIGINT)
            try: p.wait(timeout=30)
            except subprocess.TimeoutExpired: os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        self._bag_proc = None

    # ---- status (IFD-12) ----
    _last_status_rev = -1

    def _publish_status_if_changed(self):
        if self.core.status_revision != self._last_status_rev:
            self._publish_status()

    def _publish_status(self):
        st = self.core.status(); self._last_status_rev = st['status_revision']
        arr = DiagnosticArray(); arr.header.stamp = self.get_clock().now().to_msg()
        d = DiagnosticStatus(); d.name = 'gouda_recorder'; d.hardware_id = ''
        d.level = DiagnosticStatus.OK if st['failures'] == 0 else DiagnosticStatus.WARN
        d.message = ('log ' + ('active' if st['log_active'] else 'stopped')) + ', rosbag ' + ('active' if st['rosbag_active'] else 'stopped')
        d.values = [KeyValue(key=k, value=str(v)) for k, v in st.items()]
        arr.status = [d]; self.status_pub.publish(arr)

    def destroy_node(self):
        self._bag_stop(); super().destroy_node()


def _tail(path: Path, lines: int = 3) -> list:
    """Last non-empty lines of a child process log (for the failure record); empty when unreadable."""
    try:
        return [l.strip() for l in path.read_text(encoding='utf-8', errors='replace').splitlines() if l.strip()][-lines:]
    except OSError:
        return []


def main(args=None):
    rclpy.init(args=args)
    node = RecorderNode()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally:
        node.destroy_node(); rclpy.try_shutdown()


if __name__ == '__main__': main()
