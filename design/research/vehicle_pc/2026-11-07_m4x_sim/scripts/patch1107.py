"""TEST COPY ONLY: put the vehicle values confirmed in DEC-445 (2026-11-07) into drive_sim_core.Plant behind --m1107."""
import sys, re
core, node = sys.argv[1], sys.argv[2]
s = open(core).read()
s = s.replace("    moving_turn_dead: float = 0.0\n",
"""    moving_turn_dead: float = 0.0
    m1107: bool = False   # TEST COPY: DEC-445 (2026-11-07). Start/hold sticks, minimum speeds, the turn while driving
""")
s = s.replace('''    def _after_dead_band(self, t: float, tv: float, tw: float) -> tuple:''',
'''    M1107 = dict(fwd_start=0.21, fwd_hold=0.195, rev_start=0.24, rev_hold=0.215, fwd_min_v=0.09, rev_min_v=0.075,
                 fwd_k=1.125, rev_k=0.52, turn_dead_moving=0.19, turn_w_at_dead=0.075, turn_k=1.35, tau_w_drive=0.8, rest_delay=0.6)
    # fwd_k: from 0.09 m/s at stick 0.21 and 0.27 m/s at 0.37 (one point, still accelerating); rev_k: to PRM-78 0.472 m/s at full stick (assumed);
    # tau_w_drive: the turn while driving took up to 2.4 s to settle (rough). Others measured (FILE-MIN-SPEED-20261107).

    def _m1107(self, t: float, tv: float, tw: float) -> tuple:
        m = self.M1107
        f = max(-1.0, min(1.0, tv / (self.max_v if tv >= 0 else self.max_reverse_v))); s = max(-1.0, min(1.0, tw / self.max_w))
        fwd = f >= 0
        thr = (m['fwd_hold'] if fwd else m['rev_hold']) if not self._locked else (m['fwd_start'] if fwd else m['rev_start'])
        driving = abs(f) >= thr
        moving = driving or math.hypot(f, s) >= stick_threshold(f, s)
        if not moving:
            self._t_start = None
            if abs(self.v) < STOPPED_PLANT and abs(self.w) < STOPPED_PLANT: self._locked = True
            return 0.0, 0.0, False
        if self._locked:
            if self._t_start is None: self._t_start = t
            if t - self._t_start < m['rest_delay'] - self.delay_s: return 0.0, 0.0, False
            self._locked = False
        if not driving:   # turning in place, as before
            return 0.0, (math.copysign(max(abs(tw), self.min_turn_w), tw) if tw else 0.0), False
        start = m['fwd_start'] if fwd else m['rev_start']
        v = (m['fwd_min_v'] + m['fwd_k'] * max(0.0, abs(f) - start)) if fwd else (m['rev_min_v'] + m['rev_k'] * max(0.0, abs(f) - start))
        v = math.copysign(min(v, abs(f) * (self.max_v if fwd else self.max_reverse_v)), tv)
        if abs(s) < m['turn_dead_moving']: w = 0.0
        else: w = math.copysign(min(m['turn_w_at_dead'] + m['turn_k'] * (abs(s) - m['turn_dead_moving']), abs(tw)), tw)
        return v, w, True

    def _after_dead_band(self, t: float, tv: float, tw: float) -> tuple:''')
s = s.replace('''        if self.dead_band: tv, tw = self._after_dead_band(t, tv, tw)
        tau_w = self.tau_w_stop_s if abs(tw) < abs(self.w) else self.tau_w_s''',
'''        drive = False
        if self.m1107: tv, tw, drive = self._m1107(t, tv, tw)
        elif self.dead_band: tv, tw = self._after_dead_band(t, tv, tw)
        tau_w = self.tau_w_stop_s if abs(tw) < abs(self.w) else (self.M1107['tau_w_drive'] if drive else self.tau_w_s)''')
assert s.count('_m1107') >= 2 and 'drive = False' in s
open(core, 'w').write(s)
n = open(node).read()
n = n.replace("moving_turn_dead=a.moving_turn_dead)", "moving_turn_dead=a.moving_turn_dead, m1107=a.m1107)", 1)
n = n.replace("    ap.add_argument('--moving-turn-dead'", "    ap.add_argument('--m1107', action='store_true')\n    ap.add_argument('--moving-turn-dead'", 1)
n = n.replace("'moving_turn_dead': self.plant.moving_turn_dead,", "'moving_turn_dead': self.plant.moving_turn_dead, 'm1107': self.plant.m1107,", 1)
assert n.count('m1107') >= 3, n.count('m1107')
open(node, 'w').write(n)
print('patched')
