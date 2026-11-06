"""TEST ONLY (第238便): the confirmation-run section (確認走行区間) from the human's hand sketch of 2026-11-07, as a drive_sim scenario.

The sketch is not to scale: the shape and the order of the segments come from it, the labelled numbers (start corridor 3 m, chicane
neck 1.5 m, cone spacing 1.5-2 m) are used as given, the total centreline length from the start line to the goal line is 400 m (the
human's assumption) and EVERYTHING ELSE IS AN ASSUMPTION of this file (listed in ASSUMPTIONS and in the work record). Not a map of
the real site; the original rule document was not read (原本未照合).

Coordinates: the start line at x = 0 across the first corridor, the robot drives west (-x) first. Static: walls (line segments, 1.5 m
tall), 9 pillars (the east side of leg 6), the planting (a low L at the inside corner of leg 6 -> 7). They go into the static map too
(permanent things a pre-made map would hold). The green cones are NOT in the map (their places are not known before the run).

usage (the stack's drive_sim_node.py / drive_sim_fixture.py with this scenario, no change to those files):
  python3 drive_sim_course.py node <scenario> <report.json> [drive_sim_node args]   the vehicle and the world
  python3 drive_sim_course.py fixture <data_root> <scenario>                         map + waypoint set; prints the start request
  python3 drive_sim_course.py analyze <run_dir> <scenario>                           rule metrics from trace.csv (+ state.csv) -> course.json
scenarios: course_A (cone layout A, drawn like the sketch), course_B (layout B: A mirrored across the centreline),
           course_nocone (no cones; geometry only), course_A_tall (diagnosis: layout A with 1.3 m tall cones, always in view),
           tail_A / tail_B (the same course started at 340 m: only the end, the cone section and the goal),
           *_L08 / *_L05 (the same with the section speed limit 0.8 / 0.5 m/s instead of 1.25: comparison conditions, not vehicle values).
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import drive_sim_core as ds  # noqa: E402

COURSE_M = 400.0            # start line -> goal line along the centreline (human's assumption)
WALL_H, PILLAR_H, PLANT_H = 1.5, 1.5, 0.6
PILLAR_R = 0.10             # diameter 0.2 m (ASSUMED)
PILLARS = 9                 # as drawn (8-9 circles)
CONE_HALF, CONE_H = 0.20, 0.7   # base 0.4 m square, 0.7 m tall (ASSUMED)
PLANT_ARM, PLANT_T = 1.0, 0.3   # the L: arms 1 m, 0.3 m thick (ASSUMED)
STOP_AFTER_CORNER_M = 3.5   # the stop line after the corner leg 6 -> 7 (ASSUMED from the drawing)
GOAL_WP_PAST_M = 1.0        # the last waypoint this far past the goal line (ASSUMED: a human puts it past the line)
WP_STEP_M = 5.0             # waypoint spacing on straights, as the existing scenarios (ASSUMED for this course)
CONE_FIELD_M = 30.0         # the 4 m wide cone section ends at the goal line (ASSUMED)
ASSUMPTIONS = {
    'scale': 'not to scale; leg lengths below scaled by hand, leg 4 adjusted so that start line -> goal line = 400.0 m',
    'widths': '3.0 m where not labelled (from the start label); 1.5 m on the last chicane diagonal (labelled); 4.0 m in the cone section',
    'walls': 'solid, 1.5 m tall, continuous; static map holds walls, pillars and the planting, not the cones',
    'pillars': f'{PILLARS} pillars, diameter {2 * PILLAR_R} m, {PILLAR_H} m tall, evenly on the east side of leg 6',
    'planting': f'L-shape, arms {PLANT_ARM} m, {PLANT_T} m thick, {PLANT_H} m tall, at the inside corner leg 6 -> 7; leg 7 north wall starts after it',
    'stop_line': f'{STOP_AFTER_CORNER_M} m after the corner leg 6 -> 7 (centreline)',
    'cones': f'9 cones in 3 groups of 3, base {2 * CONE_HALF} m square, {CONE_H} m tall, centre-to-centre nearest neighbour 1.5-2.0 m',
    'ground': 'flat, no slope, no pedestrians, perfect localization (drive_sim stand-in)',
}


def _legs() -> list:
    """Centreline moves (dx, dy, width, tag) from the start line, before the leg-4 length adjustment."""
    return [
        (-28.0, 0.0, 3.0, 'leg1'),
        (0.0, 18.0, 3.0, 'leg2'),
        (-12.0, 0.0, 3.0, 'leg3'), (-1.5, 1.0, 3.0, 'leg3_jog'), (-42.5, 0.0, 3.0, 'leg3'),
        (-3.0, 2.5, 3.0, 'chicane'), (-4.0, -2.5, 3.0, 'chicane'), (-3.0, 2.5, 1.5, 'chicane_neck'),
        (0.0, 64.0, 3.0, 'leg4'),
        (20.0, 0.0, 3.0, 'leg5'), (4.0, -4.0, 3.0, 'leg5_jog'), (60.0, 0.0, 3.0, 'leg5'), (4.0, 4.0, 3.0, 'leg5_jog'), (22.0, 0.0, 3.0, 'leg5'),
        (0.0, -40.0, 3.0, 'leg6'),
        (42.0, 0.0, 3.0, 'leg7'), (2.0, -1.0, 3.0, 'leg7_jog'), (CONE_FIELD_M, 0.0, 4.0, 'cone_field'),
    ]


def legs() -> list:
    """The moves with leg 4 set so that the total is COURSE_M."""
    m = _legs()
    total = sum(math.hypot(dx, dy) for dx, dy, _, _ in m)
    i = next(k for k, x in enumerate(m) if x[3] == 'leg4')
    m[i] = (0.0, m[i][1] + COURSE_M - total, m[i][2], 'leg4')
    return m


class Course:
    def __init__(self):
        self.moves = legs()
        pts = [(0.0, 0.0)]
        for dx, dy, _, _ in self.moves:
            pts.append((pts[-1][0] + dx, pts[-1][1] + dy))
        self.centre = np.array(pts)                      # start line ... goal line
        self.widths = [w for _, _, w, _ in self.moves]
        self.tags = [t for _, _, _, t in self.moves]
        seg = np.diff(self.centre, axis=0)
        self.seg_len = np.hypot(seg[:, 0], seg[:, 1])
        self.cum = np.concatenate([[0.0], np.cumsum(self.seg_len)])
        self.length = float(self.cum[-1])
        k6 = self.tags.index('leg6')
        self.corner67 = tuple(self.centre[k6 + 1])
        self.stop_xy = (self.corner67[0] + STOP_AFTER_CORNER_M, self.corner67[1])
        self.stop_s = float(self.cum[k6 + 1] + STOP_AFTER_CORNER_M)
        self.goal_xy = tuple(self.centre[-1])
        # walls from the extended centreline: 2 m behind the start, 3 m past the goal
        ext = np.vstack([[2.0, 0.0], self.centre, [self.goal_xy[0] + 3.0, self.goal_xy[1]]])
        wext = [3.0] + self.widths + [4.0]
        left, right = _offset(ext, wext, +1), _offset(ext, wext, -1)
        self.left, self.right = left, right
        # leg 6 is centreline segment k6 -> extended segment k6 + 1; its left (east) side is pillars and the planting, not a wall
        j = k6 + 1
        top, bot = left[j], left[j + 1]                  # outer corner leg5/6 (NE) and inside corner leg 6/7
        self.walls = []
        for poly, side in ((left, 'L'), (right, 'R')):
            for i in range(len(poly) - 1):
                a, b = poly[i], poly[i + 1]
                if side == 'L' and i == j:
                    continue                             # pillars instead
                if side == 'L' and i == j + 1:           # leg 7 north wall starts after the planting
                    a = (a[0] + PLANT_ARM, a[1])
                self.walls.append((a, b))
        bx, by = bot
        ys = np.linspace(top[1], by + PLANT_ARM + 1.0, PILLARS)
        self.pillars = [(bx + PILLAR_R, float(y)) for y in ys]
        self.planting = [(bx + PLANT_T / 2, by + PLANT_ARM / 2, PLANT_T / 2, PLANT_ARM / 2),     # (cx, cy, half_x, half_y)
                         (bx + PLANT_ARM / 2, by + PLANT_T / 2, PLANT_ARM / 2, PLANT_T / 2)]
        self.inside67 = (bx, by)

    def along(self, x: float, y: float, s_hint: float | None = None, window: float = 15.0) -> tuple:
        """(s along the centreline, lateral distance); with s_hint only segments within `window` of it."""
        best, bs = math.inf, 0.0
        for i in range(len(self.seg_len)):
            if s_hint is not None and (self.cum[i + 1] < s_hint - window or self.cum[i] > s_hint + window):
                continue
            a, b = self.centre[i], self.centre[i + 1]
            u = (b - a) / self.seg_len[i]
            s = max(0.0, min(self.seg_len[i], float(np.dot((x - a[0], y - a[1]), u))))
            d = math.hypot(a[0] + u[0] * s - x, a[1] + u[1] * s - y)
            if d < best:
                best, bs = d, self.cum[i] + s
        return bs, best

    def point(self, s: float) -> tuple:
        i = int(np.searchsorted(self.cum, s, side='right') - 1)
        i = max(0, min(i, len(self.seg_len) - 1))
        a, b = self.centre[i], self.centre[i + 1]
        f = (s - self.cum[i]) / self.seg_len[i]
        return float(a[0] + (b[0] - a[0]) * f), float(a[1] + (b[1] - a[1]) * f)

    def waypoints(self) -> list:
        """Start pose first, then the waypoints: every vertex, at most WP_STEP_M apart, the stop line, a point past the goal line."""
        s_list = set(float(c) for c in self.cum)
        for i in range(len(self.seg_len)):
            n = int(math.ceil(self.seg_len[i] / WP_STEP_M - 1e-9))
            for k in range(1, n):
                s_list.add(float(self.cum[i] + self.seg_len[i] * k / n))
        s_list.add(self.stop_s)
        s_sorted = sorted(s_list)
        s_sorted = [s for k, s in enumerate(s_sorted) if k == 0 or s - s_sorted[k - 1] > 0.3]
        pts = [self.point(s) for s in s_sorted]
        pts[-1] = self.goal_xy
        pts.append((self.goal_xy[0] + GOAL_WP_PAST_M, self.goal_xy[1]))
        return pts

    def cones(self, layout: str) -> list:
        """(x, y) of the 9 cones; groups at 5, 13, 21 m into the cone field (drawn as three groups of three)."""
        groups = {'A': [(5.0, [(0.0, 1.3), (1.0, 0.0), (0.0, -1.3)]),
                        (13.0, [(0.0, 1.2), (1.1, -0.45), (2.3, -1.4)]),
                        (21.0, [(0.0, 1.3), (1.4, 0.2), (2.4, -1.2)])],
                  # A0: the pilot run's first layout (a 0.7 m straight lane at -0.65 m was left open; replaced by A)
                  'A0': [(5.0, [(0.0, 1.3), (1.0, 0.0), (0.0, -1.3)]),
                         (13.0, [(0.0, 1.2), (1.1, -0.1), (2.3, -1.4)]),
                         (21.0, [(0.0, 1.3), (1.4, 0.2), (2.4, -1.2)])]}
        groups['B'] = [(s, [(a, -b) for a, b in g]) for s, g in groups['A']]
        x0, y0 = self.centre[-2]                         # the cone field starts at the last vertex before the goal
        return [(float(x0 + s + a), float(y0 + b)) for s, g in groups[layout] for a, b in g]


def _offset(pts: np.ndarray, widths: list, side: int) -> list:
    """The boundary at side * width / 2 left of each segment; mitred where segments turn, stepped where only the width changes."""
    segs = []
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        u = (b - a) / math.hypot(*(b - a))
        n = np.array((-u[1], u[0])) * side * widths[i] / 2
        segs.append((a + n, b + n, u))
    out = [tuple(segs[0][0])]
    for (a1, b1, u1), (a2, b2, u2) in zip(segs, segs[1:]):
        cr = u1[0] * u2[1] - u1[1] * u2[0]
        if abs(cr) < 1e-9:
            out += [tuple(b1), tuple(a2)] if math.hypot(*(b1 - a2)) > 1e-9 else [tuple(b1)]
        else:
            t = ((a2[0] - a1[0]) * u2[1] - (a2[1] - a1[1]) * u2[0]) / cr
            out.append(tuple(a1 + u1 * t))
    out.append(tuple(segs[-1][1]))
    return [(float(x), float(y)) for x, y in out]


class Wall:
    """A vertical wall on a line segment (thin), duck-typed like drive_sim_core.Obstacle for the Scorer."""
    radius, half_x, half_y, trigger_m, dwell_s, vx, vy = 0.0, 0.0, 0.0, None, None, 0.0, 0.0

    def __init__(self, a, b, height=WALL_H, name='wall'):
        self.a, self.b, self.height, self.name = np.array(a, float), np.array(b, float), height, name
        self.x, self.y = (self.a + self.b) / 2
        self.start_t = 0.0

    def update(self, t, px, py): pass

    def exists(self, t): return True

    def center(self, t): return float(self.x), float(self.y)

    def distance(self, t, xs, ys):
        ab = self.b - self.a
        u = np.clip(((xs - self.a[0]) * ab[0] + (ys - self.a[1]) * ab[1]) / float(ab @ ab), 0.0, 1.0)
        return np.hypot(xs - (self.a[0] + u * ab[0]), ys - (self.a[1] + u * ab[1])) - 0.05


def obstacles(c: Course, layout: str | None, cone_h: float = CONE_H) -> list:
    obs = [Wall(a, b, name=f'wall{i}') for i, (a, b) in enumerate(c.walls)]
    obs += [ds.Obstacle(x, y, height=PILLAR_H, radius=PILLAR_R, name=f'pillar{i}') for i, (x, y) in enumerate(c.pillars)]
    obs += [ds.Obstacle(cx, cy, height=PLANT_H, half_x=hx, half_y=hy, name=f'planting{i}') for i, (cx, cy, hx, hy) in enumerate(c.planting)]
    if layout:
        obs += [ds.Obstacle(x, y, height=cone_h, half_x=CONE_HALF, half_y=CONE_HALF, name=f'cone{i}') for i, (x, y) in enumerate(c.cones(layout))]
    for o in obs:
        o.start_t = 0.0      # there from the start
    return obs


LAYOUTS = {'course_A': 'A', 'course_B': 'B', 'course_nocone': None, 'course_A0': 'A0', 'course_A_tall': 'A', 'tail_A': 'A', 'tail_B': 'B', 'tail_A_L08': 'A', 'stop_A': 'A',
           'tail_B_L08': 'B', 'tail_A_L05': 'A', 'tail_B_L05': 'B', 'course_A_L08': 'A', 'course_B_L08': 'B'}
LIMIT_BY = {'tail_A_L08': 0.8, 'tail_B_L08': 0.8, 'course_A_L08': 0.8, 'course_B_L08': 0.8, 'tail_A_L05': 0.5, 'tail_B_L05': 0.5}   # comparison only: the waypoint sections' speed limit (speed mask) equal to MPPI's vx_max (PRM-131)
STOP_TAIL_START_M = 300.0   # stop_A: the same course started at 300 m (before the stop line at 329.3 m), through the cones to the goal
TAIL_START_M = 340.0   # tail_*: the same course and map, started at 340 m (after the stop line, before the cone section at 370 m)
CONE_H_BY = {'course_A_tall': 1.3}   # diagnosis only: cones taller than the XT-32 (1.18 m) never leave its view


def scenario(name: str, seed: int = 0) -> ds.Scenario:
    c = Course()
    route = c.waypoints()
    if name.startswith('tail_') or name.startswith('stop_'):
        s0 = TAIL_START_M if name.startswith('tail_') else STOP_TAIL_START_M
        route = [c.point(s0)] + [p for p in route if c.along(p[0], p[1])[0] > s0 + 0.3]
    return ds.Scenario(name, route, obstacles(c, LAYOUTS[name], CONE_H_BY.get(name, CONE_H)), limit_mps=LIMIT_BY.get(name, 1.25), timeout_s=3600.0)


_orig_scenario = ds.scenario


def _scenario(name, seed=0):
    return scenario(name, seed) if name in LAYOUTS else _orig_scenario(name, seed)


def cloud(pose, obstacles_, t, rays, max_range=60.0, noise_m=0.0, rng=None, origin=(0.0, 0.0, ds.LIDAR_Z), min_range=0.0, near_m=30.0):
    """drive_sim_core.cloud with walls (segments) and only the obstacles within near_m of the vehicle (speed: ~100 walls)."""
    px, py, yaw = pose
    sx, sy, sz = origin
    dx, dy, dz = rays
    best = np.full(dx.shape, np.inf)
    down = dz < 0
    best[down] = (ds.GROUND_Z - sz) / dz[down]
    c, s = math.cos(yaw), math.sin(yaw)
    wx, wy = c * dx - s * dy, s * dx + c * dy
    mx, my = px + c * sx - s * sy, py + s * sx + c * sy
    walls, others = [], []
    for o in obstacles_:
        if isinstance(o, Wall):
            if float(o.distance(t, np.array([mx]), np.array([my]))[0]) < near_m:
                walls.append(o)
        elif o.exists(t) and math.hypot(o.center(t)[0] - mx, o.center(t)[1] - my) < near_m:
            others.append(o)
    if others:
        best_o = ds_cloud_ranges(others, t, mx, my, sz, wx, wy, dz)
        best = np.minimum(best, best_o)
    if walls:
        A = np.array([w.a for w in walls]); B = np.array([w.b for w in walls]); H = np.array([w.height for w in walls])
        ex, ey = (B - A).T
        qx, qy = A[:, 0] - mx, A[:, 1] - my
        den = wx[:, None] * ey[None, :] - wy[:, None] * ex[None, :]
        with np.errstate(divide='ignore', invalid='ignore'):
            r = (qx[None, :] * ey[None, :] - qy[None, :] * ex[None, :]) / den
            u = (qx[None, :] * wy[:, None] - qy[None, :] * wx[:, None]) / den
            z = sz + r * dz[:, None]
        ok = (np.abs(den) > 1e-12) & (r > 0) & (u >= 0) & (u <= 1) & (z >= ds.GROUND_Z) & (z <= ds.GROUND_Z + H[None, :])
        r = np.where(ok, r, np.inf).min(axis=1)
        best = np.minimum(best, r)
    keep = np.isfinite(best) & (best < max_range) & (best >= min_range)
    r = best[keep]
    if noise_m > 0:
        r = r + (rng or np.random.default_rng()).normal(0.0, noise_m, r.shape)
    return np.column_stack((sx + dx[keep] * r, sy + dy[keep] * r, sz + dz[keep] * r)).astype(np.float32)


def ds_cloud_ranges(obs, t, mx, my, sz, wx, wy, dz):
    """The nearest range of each ray on cylinders and boxes (drive_sim_core.cloud's code)."""
    best = np.full(wx.shape, np.inf)
    for o in obs:
        cx, cy = o.center(t)
        ox, oy = mx - cx, my - cy
        if o.radius > 0:
            a = wx * wx + wy * wy
            b = ox * wx + oy * wy
            disc = b * b - a * (ox * ox + oy * oy - o.radius * o.radius)
            hit = (disc >= 0) & (a > 0)
            r = np.full(wx.shape, np.inf)
            r[hit] = (-b[hit] - np.sqrt(disc[hit])) / a[hit]
        else:
            with np.errstate(divide='ignore', invalid='ignore'):
                t1x, t2x = (-o.half_x - ox) / wx, (o.half_x - ox) / wx
                t1y, t2y = (-o.half_y - oy) / wy, (o.half_y - oy) / wy
            near = np.maximum(np.minimum(t1x, t2x), np.minimum(t1y, t2y))
            far = np.minimum(np.maximum(t1x, t2x), np.maximum(t1y, t2y))
            r = np.where((near <= far) & (near > 0), near, np.inf)
        with np.errstate(invalid='ignore'):
            z = sz + r * dz
        ok = (r > 0) & np.isfinite(r) & (z >= ds.GROUND_Z) & (z <= ds.GROUND_Z + o.height) & (r < best)
        best[ok] = r[ok]
    return best


# ---------------------------------------------------------------- fixture (as drive_sim_fixture.py, with the course's walls in the map)
def fixture(root: Path, name: str) -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from gouda_core import keepout_mask as km
    from gouda_core import speed_mask as sm
    from gouda_core import waypoints as wp
    c, sc = Course(), scenario(name)
    RES = 0.1
    allx = [p[0] for w in c.walls for p in w] + [p[0] for p in c.pillars]
    ally = [p[1] for w in c.walls for p in w] + [p[1] for p in c.pillars]
    OX, OY = math.floor(min(allx)) - 5.0, math.floor(min(ally)) - 5.0
    W, H = int((max(allx) + 5.0 - OX) / RES), int((max(ally) + 5.0 - OY) / RES)
    img = occupancy(c, RES, OX, OY, W, H)
    MAP_ID, MAP_HASH = 'origin_drive_sim_course', 'synthetic-course-map-' + name
    mdir = root / 'maps' / MAP_ID / 'converted' / '001'; mdir.mkdir(parents=True, exist_ok=True)
    (mdir / 'map.pgm').write_bytes(b'P5\n%d %d\n255\n' % (W, H) + img[::-1].tobytes())   # pgm rows top (max y) first
    (mdir / 'map.yaml').write_text(f'image: map.pgm\nmode: trinary\nresolution: {RES}\norigin: [{OX}, {OY}, 0.0]\nnegate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.25\n')
    (mdir / 'pointcloud_map').mkdir(exist_ok=True)
    (mdir / 'pointcloud_map' / 'metadata.yaml').write_text('x_resolution: 20.0\ny_resolution: 20.0\n')
    (mdir / 'trajectory_imu.txt').write_text('0.0 0.0 0.0 0.0 0.0 0.0 0.0 1.0\n')
    (mdir / 'manifest.json').write_text(json.dumps({'revision': 1, 'content_hash': MAP_HASH, 'created_at': time.time()}))
    pts = sc.route[1:]
    kinds = ['stop' if math.hypot(x - c.stop_xy[0], y - c.stop_xy[1]) < 1e-6 else 'pass' for x, y in pts]
    ws = wp.WaypointSet(MAP_ID, 1, MAP_HASH, [wp.Waypoint(x, y, 0.0, k, False) for (x, y), k in zip(pts, kinds)],
                        [sc.limit_mps] * (len(sc.route) - 2), areas=[])
    db = wp.RouteDatabase(root / 'routes')
    sid, rev, tmp = db.begin(None)
    g = sm.MapGeometry(resolution=RES, origin_x=OX, origin_y=OY, width=W, height=H)
    res = sm.generate([(w.x, w.y) for w in ws.waypoints], ws.section_limits_mps, g, 1.0, 0.05)
    files = sm.write_mask(res, g, tmp, 'speed_filter_mask', 'costmap_filter_info')
    kfiles, krec = km.write(km.rasterize(ws.areas, g), g, tmp, '/keepout_filter_mask', '/keepout_costmap_filter_info'); files.update(kfiles)
    ok, msg, man = db.publish(sid, rev, tmp, ws, files, [], {'half_width_m': 1.0, 'step_mps': 0.05, 'keepout': krec})
    assert ok, msg
    (sx, sy), (nx, ny) = sc.route[0], sc.route[1]
    return {'waypoint_set_id': sid, 'waypoint_set_revision': str(rev), 'waypoint_set_hash': man['content_hash'], 'map_id': MAP_ID, 'map_revision': '1',
            'map_hash': MAP_HASH, 'initial_pose': {'x': sx, 'y': sy, 'yaw': math.atan2(ny - sy, nx - sx)}, 'request_id': f'drive-sim-course-{int(time.time())}'}


def occupancy(c: Course, res, ox, oy, w, h) -> np.ndarray:
    """uint8 image, row 0 = lowest y: 254 free, 0 occupied (walls 0.2 m thick, pillars, planting)."""
    img = np.full((h, w), 254, np.uint8)
    xs = ox + (np.arange(w) + 0.5) * res
    ys = oy + (np.arange(h) + 0.5) * res
    for (a, b) in c.walls:
        x0, x1 = min(a[0], b[0]) - 0.3, max(a[0], b[0]) + 0.3
        y0, y1 = min(a[1], b[1]) - 0.3, max(a[1], b[1]) + 0.3
        ix = np.where((xs >= x0) & (xs <= x1))[0]; iy = np.where((ys >= y0) & (ys <= y1))[0]
        if not len(ix) or not len(iy):
            continue
        X, Y = np.meshgrid(xs[ix], ys[iy])
        d = Wall(a, b).distance(0, X, Y) + 0.05
        sub = img[iy[0]:iy[-1] + 1, ix[0]:ix[-1] + 1]
        sub[d <= 0.1] = 0
    for (px, py) in c.pillars:
        iy = np.where(np.abs(ys - py) < 0.5)[0]; ix = np.where(np.abs(xs - px) < 0.5)[0]
        X, Y = np.meshgrid(xs[ix], ys[iy])
        sub = img[iy[0]:iy[-1] + 1, ix[0]:ix[-1] + 1]
        sub[np.hypot(X - px, Y - py) <= PILLAR_R + 0.05] = 0
    for (cx, cy, hx, hy) in c.planting:
        iy = np.where(np.abs(ys - cy) <= hy)[0]; ix = np.where(np.abs(xs - cx) <= hx)[0]
        img[iy[0]:iy[-1] + 1, ix[0]:ix[-1] + 1] = 0
    return img


# ---------------------------------------------------------------- analysis (rule metrics from the trace)
def _footprint_pts():
    return ds.footprint_perimeter()


def _wall_clearance(A, B, xs, ys) -> float:
    """min over the perimeter points and the wall segments of the distance to the wall surface (thin wall, 0.05 m half thickness)."""
    ab = B - A
    px, py = xs[:, None], ys[:, None]
    u = np.clip(((px - A[:, 0]) * ab[:, 0] + (py - A[:, 1]) * ab[:, 1]) / (ab * ab).sum(axis=1), 0.0, 1.0)
    d = np.hypot(px - (A[:, 0] + u * ab[:, 0]), py - (A[:, 1] + u * ab[:, 1]))
    return float(d.min()) - 0.05


def analyze(run_dir: str, name: str) -> dict:
    c = Course()
    obs = obstacles(c, LAYOUTS[name], CONE_H_BY.get(name, CONE_H))
    rows = list(csv.DictReader(open(os.path.join(run_dir, 'trace.csv'))))
    T = np.array([float(r['t']) for r in rows]); X = np.array([float(r['x']) for r in rows]); Y = np.array([float(r['y']) for r in rows])
    YAW = np.array([float(r['yaw']) for r in rows]); V = np.array([float(r['v']) for r in rows])
    S, LAT = np.zeros(len(T)), np.zeros(len(T))
    hint = None                                         # the first sample: the whole course (a tail_* route starts at 340 m)
    for i in range(len(T)):
        S[i], LAT[i] = c.along(X[i], Y[i], hint)
        hint = S[i]
    CV = np.array([float(r['cmd_v']) for r in rows]); CW = np.array([float(r['cmd_w']) for r in rows])
    s0 = TAIL_START_M if name.startswith('tail_') else STOP_TAIL_START_M if name.startswith('stop_') else 0.0
    moving = np.where(np.abs(V) > 0.05)[0]
    t_start = float(T[moving[0]]) if len(moving) else None
    # longest time without 1 m of progress (rule: 3 min), from the first motion to the end (or the goal line)
    smax = np.maximum.accumulate(S)
    gi = np.where(smax >= c.length)[0]
    t_goal = float(T[gi[0]]) if len(gi) else None
    end_i = gi[0] if len(gi) else len(T) - 1
    i0 = moving[0] if len(moving) else 0
    worst, worst_at, j = 0.0, None, i0
    for i in range(i0, end_i + 1):
        while j <= end_i and smax[j] < smax[i] + 1.0:
            j += 1
        dur = (T[j] if j <= end_i else T[end_i]) - T[i]
        if dur > worst:
            worst, worst_at = float(dur), float(S[i])
    # contacts and clearances by class
    per = _footprint_pts()
    classes = {'wall': [o for o in obs if isinstance(o, Wall)], 'pillar': [o for o in obs if o.name.startswith('pillar')],
               'planting': [o for o in obs if o.name.startswith('planting')], 'cone': [o for o in obs if o.name.startswith('cone')]}
    WA = np.array([o.a for o in classes['wall']]); WB = np.array([o.b for o in classes['wall']])
    res_c = {}
    for k, lst in classes.items():
        minc, cnt, inside, where = math.inf, 0, False, []
        for i in range(i0, end_i + 1, 1):
            cs, sn = math.cos(YAW[i]), math.sin(YAW[i])
            xs = X[i] + cs * per[:, 0] - sn * per[:, 1]; ys = Y[i] + sn * per[:, 0] + cs * per[:, 1]
            if k == 'wall':
                d = _wall_clearance(WA, WB, xs, ys); near = []
            else:
                near = [o for o in lst if math.hypot(o.center(0)[0] - X[i], o.center(0)[1] - Y[i]) < 10.0]
                d = min((float(o.distance(0, xs, ys).min()) for o in near), default=math.inf)
            for o in near:
                if not isinstance(o, Wall):
                    ox, oy = o.center(0)
                    ah = cs * (ox - X[i]) + sn * (oy - Y[i]); be = -sn * (ox - X[i]) + cs * (oy - Y[i])
                    if ds.FOOTPRINT[2][0] <= ah <= ds.FOOTPRINT[0][0] and abs(be) <= ds.FOOTPRINT[0][1]:
                        d = min(d, -0.01)
            minc = min(minc, d)
            hit = d <= 0
            if hit and not inside:
                cnt += 1; where.append(round(float(S[i]), 1))
            inside = hit
        res_c[k] = {'contacts': cnt, 'at_s_m': where[:20], 'min_clearance_m': None if math.isinf(minc) else round(minc, 3)}
    # each cone: v, cmd_v, cmd_w when the sensor (base_link) first came within d of the cone's centre, and whether it was touched
    cone_tab = {}
    for o in classes['cone']:
        ox, oy = o.center(0)
        dist = np.hypot(X - ox, Y - oy)
        tab = {}
        for d in (6.0, 5.0, 4.0, 3.0, 2.5, 2.0, 1.7, 1.5, 1.2, 1.0, 0.8):
            k_ = np.where(dist[i0:end_i + 1] <= d)[0]
            if len(k_):
                j_ = i0 + k_[0]
                tab[str(d)] = [round(float(T[j_]), 1), round(float(V[j_]), 2), round(float(CV[j_]), 2), round(float(CW[j_]), 2)]
        cs_, sn_ = np.cos(YAW), np.sin(YAW)
        clr = min((float(o.distance(0, X[i] + cs_[i] * per[:, 0] - sn_[i] * per[:, 1], Y[i] + sn_[i] * per[:, 0] + cs_[i] * per[:, 1]).min())
                   for i in range(i0, end_i + 1) if dist[i] < 2.0), default=None)
        cone_tab[o.name] = {'xy': [round(ox, 2), round(oy, 2)], 'min_clearance_m': None if clr is None else round(clr, 3),
                            'touched': clr is not None and clr <= 0, 'at_d_t_v_cmdv_cmdw': tab}
    # stop line
    k = np.where(S >= c.stop_s)[0]
    near = np.where(np.abs(S - c.stop_s) <= 1.0)[0]
    stop = {'stop_s_m': round(c.stop_s, 2), 'reached': bool(len(k)),
            'speed_at_line_mps': round(float(V[k[0]]), 3) if len(k) else None,
            'min_speed_within_1m_mps': round(float(np.abs(V[near]).min()), 3) if len(near) else None}
    near = np.where(np.abs(S - c.stop_s) <= 3.0)[0]
    stopped = [i for i in near if abs(V[i]) < 0.02]
    if stopped:
        st = np.array(stopped); stop['stopped_s_within_3m'] = round(len(st) / 20.0, 1)
        stop['stop_front_s_m'] = round(float(S[st[0]] + ds.FOOTPRINT[0][0]), 2)
    stop['stopped_within_3m'] = bool(stopped)
    if stopped:
        stop['stop_error_m'] = round(float(S[stopped[0]] - c.stop_s), 2)
    # segment of the worst stall
    seg = None
    if worst_at is not None:
        i = int(np.searchsorted(c.cum, worst_at, side='right') - 1); seg = c.tags[min(i, len(c.tags) - 1)]
    out = {'scenario': name, 'course_m': round(c.length, 2), 'reached_goal_line': t_goal is not None,
           'sim_t_first_motion_s': t_start, 'sim_t_goal_line_s': t_goal,
           'time_to_goal_s': round(t_goal - t_start, 1) if (t_goal is not None and t_start is not None) else None,
           'max_progress_m': round(float(smax[end_i]), 1), 'avg_speed_mps': round((c.length - s0) / (t_goal - t_start), 3) if t_goal and t_start is not None else None, 'start_s_m': s0,
           'longest_no_1m_progress_s': round(worst, 1), 'longest_no_progress_at_s_m': round(worst_at, 1) if worst_at is not None else None,
           'longest_no_progress_segment': seg, 'max_lateral_m': round(float(LAT[i0:end_i + 1].max()), 2), 'contacts': res_c, 'stop_line': stop if s0 < c.stop_s else 'not on this route', 'cones': cone_tab,
           'sim_t_end_s': float(T[-1])}
    json.dump(out, open(os.path.join(run_dir, 'course.json'), 'w'), ensure_ascii=False, indent=1)
    return out


def main():
    cmd = sys.argv[1]
    if cmd == 'node':
        ds.scenario = _scenario
        ds.cloud = cloud
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        import drive_sim_node
        drive_sim_node.main()
    elif cmd == 'fixture':
        print(json.dumps(fixture(Path(sys.argv[2]), sys.argv[3])))
    elif cmd == 'analyze':
        print(json.dumps(analyze(sys.argv[2], sys.argv[3]), ensure_ascii=False))
    elif cmd == 'timeout':
        print(int(scenario(sys.argv[2]).timeout_s))
    else:
        print(__doc__)

if __name__ == '__main__':
    main()
