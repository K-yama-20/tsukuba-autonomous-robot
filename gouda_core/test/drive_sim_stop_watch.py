"""TEST ONLY (一時停止線, DEC-482): started by drive_sim_stop_fixture.py. Records mode/state, control/motion_hold, the simulated
vehicle's localization/odometry and the mode manager's decisions; when the robot is held at a stop point (rule_stop_hold) it
waits hold_s and presses 再開 through the monitor API (POST /api/command/resume, as the human would). Ends when the mode leaves
自律走行 after the resume, when the test's data root is removed (drive_sim.sh ended) or after a deadline.
usage: python3 drive_sim_stop_watch.py <data_root> <scenario> <out_dir> [hold_s]   -> <out_dir>/stop_watch.json"""
import json
import math
import sys
import time
import urllib.request
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from nav_msgs.msg import Odometry
from gouda_interfaces.msg import SoftwareMode, MotionHold, DecisionEvent

sys.path.insert(0, str(Path(__file__).resolve().parent))
import drive_sim_core as ds  # noqa: E402

root, scenario, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
hold_s = float(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] else None
DEADLINE_S = 900.0   # test bound of the watcher itself
LATCHED = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=1)
DECISIONS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=50)
KEEP = ('rule_stop_hold', 'human_request', 'goal_reached', 'nav2_goal_sent', 'automatic_pause', 'nav2_goal_resend_scheduled',
        'localization_wait', 'nav2_goal_ended', 'motion_hold_released', 'waypoint_skipped')


class Watch(Node):
    def __init__(self):
        super().__init__('drive_sim_stop_watch')
        self.t0 = time.monotonic()
        self.mode = self.hold = self.xy = None
        self.v = 0.0
        self.samples, self.decisions = [], []
        self.create_subscription(SoftwareMode, 'mode/state', lambda m: setattr(self, 'mode', m), LATCHED)
        self.create_subscription(MotionHold, 'control/motion_hold', lambda m: setattr(self, 'hold', m.hold), LATCHED)
        self.create_subscription(Odometry, 'localization/odometry', self._odom, 10)
        self.create_subscription(DecisionEvent, 'log/decision', self._decision, DECISIONS)

    def t(self):
        return round(time.monotonic() - self.t0, 2)

    def _odom(self, m):
        self.xy = (m.pose.pose.position.x, m.pose.pose.position.y); self.v = m.twist.twist.linear.x

    def _decision(self, d):
        if d.node == 'gouda_mode_manager' and d.event in KEEP:
            self.decisions.append({'t': self.t(), 'event': d.event, 'transition_id': d.transition_id, 'reason': d.reason, 'details': json.loads(d.details or '{}')})

    def sample(self):
        m = self.mode
        s = {'t': self.t(), 'mode': m.mode if m else None, 'processing_state': m.processing_state if m else None,
             'stop_reason': m.stop_reason if m else None, 'remaining': m.remaining_waypoints if m else None, 'hold': self.hold,
             'x': round(self.xy[0], 3) if self.xy else None, 'y': round(self.xy[1], 3) if self.xy else None, 'v': round(self.v, 3)}
        self.samples.append(s)
        return s


def post(url, path):
    req = urllib.request.Request(url + path, data=b'{}', headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode('utf-8'))


def main():
    rclpy.init()
    w = Watch()
    url_file = root / 'run' / 'monitor.url'
    url, held_at, resumed_at, resume_answer, ended = None, None, None, None, ''
    route = ds.scenario(scenario).route
    while True:
        rclpy.spin_once(w, timeout_sec=0.25)
        if not root.exists():
            ended = 'data root removed (drive_sim.sh ended)'; break
        if time.monotonic() - w.t0 > DEADLINE_S:
            ended = 'watcher deadline'; break
        if url is None and url_file.is_file() and url_file.read_text().strip():
            url = url_file.read_text().strip()
        if not w.samples or w.t() - w.samples[-1]['t'] >= 0.5:
            s = w.sample()
            if s['processing_state'] == 'rule_stop_hold' and held_at is None:
                held_at = s
            if held_at is not None and resumed_at is None and hold_s is not None and url and s['t'] - held_at['t'] >= hold_s:
                resumed_at = s
                try:
                    resume_answer = post(url, '/api/command/resume')
                except Exception as e:   # recorded, the run goes on
                    resume_answer = {'error': str(e)}
            if resumed_at is not None and s['mode'] not in (None, SoftwareMode.MODE_AUTONOMY):
                ended = f'mode {s["mode"]} stop_reason {s["stop_reason"]}'
                for _ in range(8):
                    rclpy.spin_once(w, timeout_sec=0.25)
                break
    summary = {'scenario': scenario, 'ended': ended, 'hold_s_requested': hold_s, 'held_at': held_at, 'resumed_at': resumed_at,
               'resume_answer': resume_answer, 'final': w.samples[-1] if w.samples else None, 'goal_xy': route[-1]}
    stop = next((d['details'] for d in w.decisions if d['event'] == 'rule_stop_hold'), None)
    if stop and held_at:
        sx, sy = stop['waypoint_xy']
        window = [s for s in w.samples if held_at['t'] <= s['t'] <= (resumed_at or w.samples[-1])['t']]
        settled = [s for s in window if s['t'] >= held_at['t'] + 3.0]   # after the vehicle's own stopping (inertia of the plant)
        pts = [(s['x'], s['y']) for s in settled if s['x'] is not None]
        rest = pts[0] if pts else None
        summary.update(stop_waypoint=stop['waypoint'], stop_xy=[sx, sy], decision=stop,
                       dist_at_hold_m=math.hypot(held_at['x'] - sx, held_at['y'] - sy) if held_at['x'] is not None else None,
                       dist_at_rest_m=math.hypot(rest[0] - sx, rest[1] - sy) if rest else None,
                       along_route_at_rest_m=(rest[0] - sx, rest[1] - sy) if rest else None,
                       held_span_s=round(window[-1]['t'] - held_at['t'], 2) if window else None,
                       settled_span_s=round(settled[-1]['t'] - settled[0]['t'], 2) if settled else None,
                       settled_max_move_m=max(math.hypot(x - rest[0], y - rest[1]) for x, y in pts) if pts else None,
                       settled_max_abs_v=max(abs(s['v']) for s in settled) if settled else None,
                       hold_true_whole_window=all(s['hold'] is True for s in window),
                       states_in_window=sorted({(s['mode'], s['processing_state'], s['stop_reason']) for s in window}))
    f = summary['final']
    if f and f['x'] is not None:
        summary['final_dist_to_goal_m'] = math.hypot(f['x'] - route[-1][0], f['y'] - route[-1][1])
    (out / 'stop_watch.json').write_text(json.dumps(dict(summary, decisions=w.decisions, samples=w.samples), ensure_ascii=False, indent=1, default=str))
    print(json.dumps({k: v for k, v in summary.items() if k not in ('decision',)}, ensure_ascii=False, default=str))
    w.destroy_node(); rclpy.try_shutdown()


if __name__ == '__main__':
    main()
