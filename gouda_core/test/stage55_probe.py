"""Stage 5-5 ROS probe (software test on Ubuntu, no vehicle): drives gouda_motion_controller + vehicle_bridge + the Python
ESP32 model on a pty, and records what TS-07 / TS-13 / TS-19 (PC side) / TS-12 observe.

Phases (wall-clock, settings read from the generated parameter files so no number is typed here):
  1. hold=true published (transient_local) + cmd_vel non-zero at the controller period  -> expect joystick neutral (TS-07 hold)
  2. hold=false + cmd_vel non-zero                                                     -> expect non-neutral; sim source=pc
  3. cmd_vel stopped, hold kept fresh                                                  -> expect neutral within PRM-08 (+ one period) (TS-13)
  4. hold=false but hold publication stopped                                           -> expect neutral within PRM-42 (TS-07 hold expiry)
Outputs a JSON summary to stdout and the raw observations to --out.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Joy
from diagnostic_msgs.msg import DiagnosticArray
from gouda_interfaces.msg import MotionHold, DecisionEvent

LATCHED = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=1)
DECISION_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=50)
VOL1 = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE, history=HistoryPolicy.KEEP_LAST, depth=1)


def load_flat(path):
    vals = {}
    for line in Path(path).read_text().splitlines():
        m = re.match(r'\s*(\w+): ([-\d.]+)', line)
        if m: vals[m.group(1)] = float(m.group(2))
    return vals


class Probe(Node):
    def __init__(self, params_dir, out):
        super().__init__('stage55_probe')
        mc = {**load_flat(f'{params_dir}/gouda_motion_controller.yaml'), **load_flat(f'{params_dir}/gouda_motion_controller.trial.yaml')}
        self.cmd_timeout = mc['cmd_vel_timeout_s']; self.hold_timeout = mc['motion_hold_timeout_s']; self.period = mc['command_publish_period_s']
        self.vmax = mc['max_linear_speed_mps']
        self.out = open(out, 'w'); self.t0 = time.monotonic()
        self.hold_pub = self.create_publisher(MotionHold, 'control/motion_hold', LATCHED)
        self.cmd_pub = self.create_publisher(Twist, 'cmd_vel', VOL1)
        self.create_subscription(Joy, 'vehicle/joystick_command', self.on_joy, VOL1)
        self.create_subscription(DiagnosticArray, '/esp32/status', self.on_status, QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE, history=HistoryPolicy.KEEP_LAST, depth=10))
        self.create_subscription(DecisionEvent, 'log/decision', self.on_decision, DECISION_QOS)
        self.joy_log = []; self.status_log = []; self.decisions = []
        self.last_joy = None; self.last_src = None
        self.phase = 0; self.hold = True; self.send_cmd = True; self.send_hold = True
        self.phase_t = {}
        self.create_timer(self.period, self.tick)
        self.create_timer(0.1, self.hold_tick)

    def now(self): return time.monotonic() - self.t0
    def log(self, kind, text):
        self.out.write(f'{self.now():8.3f} {kind} {text}\n'); self.out.flush()

    def tick(self):
        if self.send_cmd:
            m = Twist(); m.linear.x = self.vmax / 2; m.angular.z = 0.0; self.cmd_pub.publish(m)

    def hold_tick(self):
        if self.send_hold:
            h = MotionHold(); h.header.stamp = self.get_clock().now().to_msg(); h.hold = self.hold; h.reason = 'probe'; h.mode = 4 if self.hold else 3
            self.hold_pub.publish(h)

    def on_joy(self, j):
        v = (round(j.axes[0], 3), round(j.axes[1], 3)); t = self.now()
        self.joy_log.append((t, v))
        if v != self.last_joy:
            self.last_joy = v; self.log('joy', f'{v} phase={self.phase}')

    def on_status(self, arr):
        for st in arr.status:
            if st.name != 'esp32': continue
            d = {kv.key: kv.value for kv in st.values}; key = (d.get('source'), d.get('reason'), d.get('target_x_mv'), d.get('target_y_mv'), d.get('pc_enabled'))
            self.status_log.append((self.now(), d))
            if key != self.last_src:
                self.last_src = key; self.log('esp32', f'source={d.get("source")} reason={d.get("reason")} target=({d.get("target_x_mv")},{d.get("target_y_mv")}) pc_enabled={d.get("pc_enabled")} phase={self.phase}')

    def on_decision(self, d):
        self.decisions.append((self.now(), d.node, d.event, d.reason)); self.log('decision', f'{d.node} {d.event}: {d.reason}')

    def set_phase(self, n):
        self.phase = n; self.phase_t[n] = self.now(); self.log('phase', f'-> {n}')

    def first_after(self, t, pred, log):
        for tt, v in log:
            if tt >= t and pred(v): return tt
        return None

    def summary(self):
        neutral = lambda v: v == (0.0, 0.0)
        s = {'settings': {'cmd_vel_timeout_s(PRM-08)': self.cmd_timeout, 'motion_hold_timeout_s(PRM-42)': self.hold_timeout, 'command_publish_period_s(PRM-41)': self.period}}
        p1, p2, p3, p4 = (self.phase_t.get(i) for i in (1, 2, 3, 4))
        s['phase1_hold_true_joy_all_neutral'] = all(neutral(v) for t, v in self.joy_log if p1 <= t < p2)
        s['phase1_joy_count'] = sum(1 for t, v in self.joy_log if p1 <= t < p2)
        t_drive = self.first_after(p2, lambda v: not neutral(v), self.joy_log)
        s['phase2_first_non_neutral_after_hold_false_s'] = None if t_drive is None else round(t_drive - p2, 3)
        s['phase2_esp32_pc_source_seen'] = any(p2 <= t < p3 and d.get('source') == 'pc' for t, d in self.status_log)
        t_neu = self.first_after(p3, neutral, self.joy_log)
        s['phase3_cmd_vel_stop_to_neutral_s'] = None if t_neu is None else round(t_neu - p3, 3)
        s['phase3_within_PRM08_plus_period'] = (t_neu is not None) and (t_neu - p3 <= self.cmd_timeout + 2 * self.period) and (t_neu - p3 >= self.cmd_timeout - self.period)
        joy_p3 = [t for t, v in self.joy_log if p3 <= t < p4]
        s['phase3_joy_rate_hz'] = round(len(joy_p3) / max(1e-6, (joy_p3[-1] - joy_p3[0])), 1) if len(joy_p3) > 2 else None
        st_p3 = [t for t, d in self.status_log if p3 <= t < p4]
        s['phase3_esp32_status_rate_hz'] = round(len(st_p3) / max(1e-6, (st_p3[-1] - st_p3[0])), 1) if len(st_p3) > 2 else None
        s['phase3_esp32_stayed_pc_source'] = all(d.get('source') == 'pc' for t, d in self.status_log if p3 + 0.3 <= t < p4)
        t_neu4 = self.first_after(p4, neutral, self.joy_log)
        s['phase4_hold_stop_to_neutral_s'] = None if t_neu4 is None else round(t_neu4 - p4, 3)
        s['phase4_within_PRM42_plus_period'] = (t_neu4 is not None) and (t_neu4 - p4 <= self.hold_timeout + 2 * self.period)
        s['decisions'] = [f'{n} {e}: {r}' for t, n, e, r in self.decisions if n in ('gouda_motion_controller', 'vehicle_bridge')]
        return s


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--params-dir', required=True); ap.add_argument('--out', required=True); a = ap.parse_args()
    rclpy.init(); n = Probe(a.params_dir, a.out)
    def spin(sec):
        end = time.monotonic() + sec
        while time.monotonic() < end: rclpy.spin_once(n, timeout_sec=0.01)
    spin(1.0)
    n.set_phase(1); n.hold = True; n.send_cmd = True; spin(2.0)
    n.set_phase(2); n.hold = False; spin(2.0)
    n.set_phase(3); n.send_cmd = False; spin(2.0)
    n.hold = False; n.send_cmd = True; spin(1.0)   # drive again briefly so phase 4 starts from a non-neutral output
    n.set_phase(4); n.send_hold = False; spin(max(2.0, n.hold_timeout + 1.0))
    s = n.summary(); print(json.dumps(s, ensure_ascii=False, indent=1)); n.out.write(json.dumps(s, ensure_ascii=False) + '\n'); n.out.close()
    n.destroy_node(); rclpy.shutdown()


if __name__ == '__main__': main()
