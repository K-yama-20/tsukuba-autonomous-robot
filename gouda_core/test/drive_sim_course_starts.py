"""TEST ONLY (planting start poses): the confirmation-run course (drive_sim_course.py) started near the planting (植え込み) at the
inside corner leg 6 -> 7, at several positions and headings, to see whether the vehicle still gets out, rounds the corner, stops at
the stop line and reaches a goal 10 m past it.

Scene names: pst_<pos>_<deg>, e.g. pst_P1_+090. deg = heading relative to the route direction at the start, positive = counter-
clockwise (= towards the inside of this left turn, i.e. towards the pillars / the planting). Positions (base_link):
  P2, P1  2 m / 1 m before the point where the front (0.55 m ahead of base_link) is level with the planting's north edge (leg 6)
  PM      abeam the middle of the planting's north-south arm (leg 6, 2.0 m before the corner vertex)
  PM2     abeam the middle of the planting's east-west arm (leg 7, 2.0 m after the corner vertex)
  P1s, PMs  P1 / PM shifted 0.7 m towards the inside of the turn (east)
Use (no change to drive_sim_course.py's own scenes): COURSE_EXT=drive_sim_course_starts bash drive_sim_course.sh pst_P1_+090 <out>
  python3 drive_sim_course_starts.py poses            the start poses (x, y, s, heading, what the heading points at, start clearance)
  python3 drive_sim_course_starts.py analyze <run> <scene>   metrics for this study -> plant.json
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

GOAL_PAST_STOP_M = 10.0          # the scene's goal this far past the stop line (centreline)
SHIFT_M = 0.7                    # the lateral variant: towards the inside of the turn
FRONT_M = 0.55                   # base_link -> front (PRM-69)
HEADINGS = (0, 45, -45, 90, -90, 135, -135, 180)
POSITIONS = ('P2', 'P1', 'PM', 'PM2', 'P1s', 'PMs')
_dc = None
_pending_yaw = [None]


def dc():
    global _dc
    if _dc is None:
        import drive_sim_course
        _dc = drive_sim_course
    return _dc


def _geom():
    m = dc()
    c = m.Course()
    k6 = c.tags.index('leg6')
    s_c = float(c.cum[k6 + 1])                       # the corner vertex leg 6 -> 7
    cx, cy = c.corner67
    bx, by = c.inside67                              # inside corner of the walls (the planting's outer corner)
    north_edge = by + m.PLANT_ARM                    # planting's nearest edge when coming south
    s_level = s_c - (north_edge - cy) - FRONT_M      # base_link where the front is level with it
    return c, s_c, (cx, cy), (bx, by), s_level


def start_pose(pos: str, deg: float) -> tuple:
    """(x, y, yaw, s, route_yaw)."""
    c, s_c, (cx, cy), (bx, by), s_level = _geom()
    m = dc()
    base = pos.rstrip('s') if pos in ('P1s', 'PMs') else pos
    s = {'P2': s_level - 2.0, 'P1': s_level - 1.0, 'PM': s_c - (by + m.PLANT_ARM / 2 - cy),
         'PM2': s_c + (bx + m.PLANT_ARM / 2 - cx)}[base]
    x, y = c.point(s)
    a, b = c.point(s - 0.05), c.point(s + 0.05)
    ryaw = math.atan2(b[1] - a[1], b[0] - a[0])
    if pos.endswith('s') and pos in ('P1s', 'PMs'):
        x, y = x - math.sin(ryaw) * SHIFT_M, y + math.cos(ryaw) * SHIFT_M      # left of the travel direction = inside
    yaw = math.atan2(math.sin(ryaw + math.radians(deg)), math.cos(ryaw + math.radians(deg)))
    return x, y, yaw, s, ryaw


def parse(name: str) -> tuple:
    _, pos, deg = name.split('_')
    return pos, int(deg)


def names(positions=POSITIONS) -> list:
    return [f'pst_{p}_{d:+04d}' for p in positions for d in HEADINGS]


def _route(c, x, y, s0) -> list:
    m = dc()
    sg = c.stop_s + GOAL_PAST_STOP_M
    pts = [p for p in c.waypoints() if s0 + 0.3 < c.along(p[0], p[1])[0] < sg - 0.3]
    return [(x, y)] + pts + [c.point(sg)]


def scenario(name: str, seed: int = 0):
    m = dc()
    if not name.startswith('pst_'):
        return _orig['scenario'](name, seed)
    c = m.Course()
    x, y, yaw, s0, _ = start_pose(*parse(name))
    _pending_yaw[0] = yaw
    return m.ds.Scenario(name, _route(c, x, y, s0), m.obstacles(c, 'A'), limit_mps=1.25, timeout_s=3600.0)


_orig = {}


class _PlantYaw:
    """ds.Plant with the start yaw of the pst_ scene (drive_sim_node.py faces the vehicle at the second route point)."""

    def __init__(self, cls):
        self.cls = cls

    def __call__(self, *a, **k):
        if _pending_yaw[0] is not None and 'yaw' in k:
            k['yaw'] = _pending_yaw[0]
        return self.cls(*a, **k)

    def __getattr__(self, k):            # class attributes (defaults used by drive_sim_node's argument parser)
        return getattr(self.cls, k)


def install(mod) -> None:
    """Called by drive_sim_course.py's COURSE_EXT hook with that module: add the pst_ scenes."""
    global _dc
    if getattr(mod, '_pst_installed', False):
        return
    _dc = mod
    mod._pst_installed = True
    _orig['scenario'], _orig['fixture'] = mod.scenario, mod.fixture
    mod.scenario = scenario
    for n in names():
        mod.LAYOUTS[n] = 'A'
    if not isinstance(mod.ds.Plant, _PlantYaw):
        mod.ds.Plant = _PlantYaw(mod.ds.Plant)

    def fixture(root, name):
        out = _orig['fixture'](root, name)
        if name.startswith('pst_'):
            x, y, yaw, _, _ = start_pose(*parse(name))
            out['initial_pose'] = {'x': x, 'y': y, 'yaw': yaw}      # the true start pose (the localization stand-in is exact)
        return out
    mod.fixture = fixture


# ---------------------------------------------------------------- geometry of the start poses
def _classes(c):
    m = dc()
    left_n = len(c.left) - 2                          # walls: left polygon first (one segment skipped: the pillars)
    obs = m.obstacles(c, 'A')
    walls = [o for o in obs if isinstance(o, m.Wall)]
    return {'inner_wall': walls[:left_n], 'outer_wall': walls[left_n:],
            'pillar': [o for o in obs if o.name.startswith('pillar')], 'planting': [o for o in obs if o.name.startswith('planting')]}


def clearances(c, cls, x, y, yaw) -> dict:
    m = dc()
    per = m.ds.footprint_perimeter()
    cs, sn = math.cos(yaw), math.sin(yaw)
    xs, ys = x + cs * per[:, 0] - sn * per[:, 1], y + sn * per[:, 0] + cs * per[:, 1]
    out = {}
    for k, lst in cls.items():
        d = math.inf
        for o in lst:
            if not isinstance(o, m.Wall) and math.hypot(o.center(0)[0] - x, o.center(0)[1] - y) > 8.0:
                continue
            if isinstance(o, m.Wall) and float(o.distance(0, np.array([x]), np.array([y]))[0]) > 8.0:
                continue
            dd = float(o.distance(0, xs, ys).min())
            if not isinstance(o, m.Wall):                 # an obstacle (centre or box corner) inside the footprint
                pts = [o.center(0)] + ([] if o.radius > 0 else [(o.x + sx * o.half_x, o.y + sy * o.half_y) for sx in (-1, 1) for sy in (-1, 1)])
                for ox, oy in pts:
                    ah, be = cs * (ox - x) + sn * (oy - y), -sn * (ox - x) + cs * (oy - y)
                    if m.ds.FOOTPRINT[2][0] <= ah <= m.ds.FOOTPRINT[0][0] and abs(be) <= m.ds.FOOTPRINT[0][1]:
                        dd = min(dd, -0.01)
            d = min(d, dd)
        out[k] = None if math.isinf(d) else round(d, 3)
    return out


def pointing_at(c, cls, x, y, yaw) -> tuple:
    """(class, distance) of the first thing on the ray from base_link along the heading (at the ground plane)."""
    best = (None, math.inf)
    for r in np.arange(0.0, 12.0, 0.02):
        px, py = x + r * math.cos(yaw), y + r * math.sin(yaw)
        for k, lst in cls.items():
            for o in lst:
                if float(o.distance(0, np.array([px]), np.array([py]))[0]) <= 0.0:
                    return k, round(float(r), 2)
    return best


JP = {'inner_wall': '内側の壁', 'outer_wall': '外側の壁', 'pillar': '柱', 'planting': '植込み', None: '柱の列の隙間（内側の空き地）'}


def label(deg: int, k) -> str:
    if deg == 0:
        return '進行方向'
    if deg == 180:
        return '逆向き'
    return f'{JP[k]}向き'


def poses() -> list:
    c = dc().Course()
    cls = _classes(c)
    out = []
    for n in names():
        pos, deg = parse(n)
        x, y, yaw, s, ryaw = start_pose(pos, deg)
        k, d = pointing_at(c, cls, x, y, yaw)
        cl = clearances(c, cls, x, y, yaw)
        out.append({'scene': n, 'pos': pos, 'deg': deg, 'x': round(x, 3), 'y': round(y, 3), 's': round(s, 2), 'yaw_deg': round(math.degrees(yaw), 1),
                    'points_at': k, 'points_at_m': d, 'label': label(deg, k), 'start_clearance': cl,
                    'feasible': all(v is None or v > 0.0 for v in cl.values())})
    return out


# ---------------------------------------------------------------- analysis of one run
def _outside(c, X, Y, S) -> np.ndarray:
    """base_link beyond the corridor: farther from the centreline than half the width of the segment there (+0.05 m)."""
    w = np.array([c.widths[min(int(np.searchsorted(c.cum, s, side='right') - 1), len(c.widths) - 1)] for s in S])
    lat = np.array([c.along(x, y, s, 8.0)[1] for x, y, s in zip(X, Y, S)])
    return lat > w / 2 + 0.05


def analyze(run_dir: str, name: str) -> dict:
    m = dc()
    c, s_c, (cx, cy), _, _ = _geom()
    cls = _classes(c)
    pos, deg = parse(name)
    x0, y0, yaw0, s0, _ = start_pose(pos, deg)
    rows = list(csv.DictReader(open(os.path.join(run_dir, 'trace.csv'))))
    T = np.array([float(r['t']) for r in rows]); X = np.array([float(r['x']) for r in rows]); Y = np.array([float(r['y']) for r in rows])
    YAW = np.array([float(r['yaw']) for r in rows]); V = np.array([float(r['v']) for r in rows]); CV = np.array([float(r['cmd_v']) for r in rows])
    S, LAT, RY = np.zeros(len(T)), np.zeros(len(T)), np.zeros(len(T))
    hint = s0
    for i in range(len(T)):
        S[i], LAT[i] = c.along(X[i], Y[i], hint, 8.0)
        hint = S[i]
        a, b = c.point(S[i] - 0.05), c.point(S[i] + 0.05)
        RY[i] = math.atan2(b[1] - a[1], b[0] - a[0])
    err = np.degrees(np.abs(np.arctan2(np.sin(YAW - RY), np.cos(YAW - RY))))
    CW = np.array([float(r['cmd_w']) for r in rows])
    cmd = np.where((np.abs(CV) > 0.01) | (np.abs(CW) > 0.01))[0]
    i0 = int(cmd[0]) if len(cmd) else 0                # the first command of the autonomy (before it: the stack still starting)
    t0 = float(T[i0])
    sg = c.stop_s + GOAL_PAST_STOP_M
    ok = np.where((err < 30.0) & (V > 0.1))[0]
    t_go = round(float(T[ok[0]] - t0), 1) if len(ok) else None
    corner = np.where((S >= s_c + 1.0) & (X > cx + 0.5))[0]
    t_corner = round(float(T[corner[0]] - t0), 1) if len(corner) else None
    smax = np.maximum.accumulate(S)
    gi = np.where(smax >= sg - 1.0)[0]
    end_i = len(T) - 1                                   # the run ends at the goal (PAUSE goal_reached) or by the time limits
    worst, worst_at, j = 0.0, None, i0
    for i in range(i0, end_i + 1):
        while j <= end_i and smax[j] < smax[i] + 1.0:
            j += 1
        dur = (T[j] if j <= end_i else T[end_i]) - T[i]
        if dur > worst:
            worst, worst_at = float(dur), (round(float(X[i]), 2), round(float(Y[i]), 2), round(float(T[i] - t0), 1))
    # the stop line hold time, from stop_events.csv (sim s) -> do not count the hold as no progress
    hold = []
    p = os.path.join(run_dir, 'stop_events.csv')
    if os.path.exists(p):
        ev = list(csv.DictReader(open(p)))
        hs = [float(e['sim_s']) for e in ev if e['event'] == 'hold' and e['sim_s'] not in ('', 'None')]
        rs = [float(e['sim_s']) for e in ev if e['event'] == 'resume' and e['sim_s'] not in ('', 'None')]
        hold = list(zip(hs, rs + [None] * (len(hs) - len(rs))))
    # clearances and contacts over the run
    minc = {k: math.inf for k in cls}; cnt = {k: 0 for k in cls}; inside = {k: False for k in cls}; first_hit = {k: None for k in cls}
    for i in range(i0, end_i + 1, 2):
        cl = clearances(c, cls, X[i], Y[i], YAW[i])
        for k, v in cl.items():
            if v is None:
                continue
            minc[k] = min(minc[k], v)
            h = v <= 0
            if h and not inside[k]:
                cnt[k] += 1
                if first_hit[k] is None:
                    first_hit[k] = (round(float(X[i]), 2), round(float(Y[i]), 2), round(float(T[i] - t0), 1))
            inside[k] = h
    dt = np.diff(T, prepend=T[0])
    rev = V < -0.02
    stop = {}
    if hold:
        th = hold[0][0]
        k = int(np.searchsorted(T - T[0], th)) if th < T[-1] else len(T) - 1
        k = min(k, len(T) - 1)
        stop = {'held': True, 'hold_after_first_cmd_s': round(th - (t0 - T[0]), 1), 'resume_sim_s': hold[0][1], 'front_overshoot_m': round(float(S[k] + FRONT_M * math.cos(math.radians(err[k])) - c.stop_s), 2),
                'holds': len(hold)}
    else:
        stop = {'held': False}
    res = json.load(open(os.path.join(run_dir, 'result.json'))) if os.path.exists(os.path.join(run_dir, 'result.json')) else {}
    states = list(csv.DictReader(open(os.path.join(run_dir, 'state.csv')))) if os.path.exists(os.path.join(run_dir, 'state.csv')) else []
    modes = sorted({(r['mode'], r['stop_reason']) for r in states})
    mv = CV[(CV > 0.05) & (S < c.stop_s - 3.0)]           # before the approach to the stop point
    out = {'scene': name, 'pos': pos, 'deg': deg, 'start': [round(x0, 2), round(y0, 2), round(math.degrees(yaw0), 1)], 'start_s': round(s0, 2),
           'end': res.get('end'), 'completed': res.get('completed'), 'log': res.get('log'), 'load1_end': res.get('load1'),
           'reached_goal_s': bool(len(gi)), 'sim_t_total_s': round(float(T[-1] - t0), 1), 'sim_t_first_cmd_s': round(t0 - float(T[0]), 1),
           't_moving_right_way_s': t_go, 't_corner_s': t_corner, 'longest_no_1m_s': round(worst, 1), 'longest_no_1m_at': worst_at,
           'max_dev_m': round(float(LAT[i0:].max()), 2), 'outside_corridor': bool(_outside(c, X[i0:], Y[i0:], S[i0:]).any()), 'min_clear': {k: (None if math.isinf(v) else v) for k, v in minc.items()},
           'contacts': cnt, 'first_contact': first_hit, 'reverse_m': round(float((-V[rev] * dt[rev]).sum()), 2), 'reverse_s': round(float(dt[rev].sum()), 1),
           'stop': stop, 'modes_seen': modes, 'cmd_v_p01': round(float(np.percentile(mv, 1)), 3) if len(mv) else None,
           'cmd_v_p50': round(float(np.percentile(mv, 50)), 3) if len(mv) else None}
    json.dump(out, open(os.path.join(run_dir, 'plant.json'), 'w'), ensure_ascii=False, indent=1)
    return out


def main():
    cmd = sys.argv[1]
    install(dc())
    if cmd == 'poses':
        for p in poses():
            print(json.dumps(p, ensure_ascii=False))
    elif cmd == 'analyze':
        print(json.dumps(analyze(sys.argv[2], sys.argv[3]), ensure_ascii=False))
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
