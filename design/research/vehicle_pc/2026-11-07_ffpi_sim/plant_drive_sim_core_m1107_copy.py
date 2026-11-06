"""TEST ONLY (第179便): the core of the driving simulator used to tune Nav2 roughly without the vehicle. No ROS dependency.

- Plant: the vehicle as a command delay and a first-order lag, with the stick dead band and the wait from a stop (DEC-422). The turn, the dead
  band and the wait come from the vehicle tests of 2026-11-03 (turning in place); the driving delay and the forward values are still synthetic
  (DEC-378 is open), so a sweep should vary them; a result here says which settings are worth trying on the vehicle, not how it will behave.
- Scenario: a route on free space with obstacles that may appear, move or leave (a cone placed late, a person crossing, ...).
- cloud(): the XT-32 as analytic ray casting on the ground, cylinders and boxes, in base_link (the real pointcloud_to_laserscan and
  the real costmaps read it). The ground sits below the height band, so empty directions give inf beams as on the vehicle.
- Scorer: driving metrics and a score. The score only ranks settings against each other: it is no acceptance criterion.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from gouda_core.motion_core import compensate

FOOTPRINT = ((0.55, 0.30), (0.55, -0.30), (-0.24, -0.30), (-0.24, 0.30))   # as PRM-69 in the generated parameter file
GROUND_Z = -0.165          # base_link above the ground, as PRM-05 (記載値)
LIDAR_Z = 1.015            # the XT-32 above base_link, lidar_mount_z_m of the vehicle's /config (2026-11-02); level, on the axis (a simplification)
ELEVATIONS_DEG = np.arange(-16.0, 16.0, 1.0)   # 32 channels, 1 degree apart
AZIMUTH_STEP_DEG = 0.36    # 10 Hz
STOPPED_V, STOPPED_W = 0.05, 0.05   # below both: the vehicle counts as stopped
AVOID_LATERAL_M = 0.15     # this far from the route: the vehicle has started to avoid
WZ_DEADBAND = 0.05         # a turn command smaller than this does not count as a change of direction
GOAL_RADIUS_M = 1.0
# The stick amount where motion starts and stops, by direction of the stick (0 = forward, 90 = turn left): the middle of the two levels found on
# the vehicle (第200便). Starting and stopping were found on the same level, and turning stayed at about min_turn_w just above it.
STICK_THRESHOLD = ((0.0, 0.20), (45.0, 0.24), (90.0, 0.28), (135.0, 0.24), (180.0, 0.20), (225.0, 0.24), (270.0, 0.165), (315.0, 0.20), (360.0, 0.20))
MAX_REVERSE_V = 0.472      # as PRM-78
STOPPED_PLANT = 0.02       # below both (m/s, rad/s): the plant has stopped and needs the wait to start again


def stick_threshold(forward: float, turn: float) -> float:
    a = math.degrees(math.atan2(turn, forward)) % 360
    for (a0, v0), (a1, v1) in zip(STICK_THRESHOLD, STICK_THRESHOLD[1:]):
        if a <= a1: return v0 + (v1 - v0) * (a - a0) / (a1 - a0)
    return STICK_THRESHOLD[-1][1]


@dataclass
class Plant:
    """Commanded (v, w) -> state: pure delay, the dead band of the stick and the wait from a stop, then a first-order lag on each axis and the
    limits. comp is the dead-band compensation of ND-11 as (forward, reverse, turn) pairs of (minimum, threshold); None is the plain normalization."""
    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0
    v: float = 0.0
    w: float = 0.0
    delay_s: float = 0.15
    tau_v_s: float = 0.25
    tau_w_s: float = 0.3         # measured: turning up
    tau_w_stop_s: float = 0.18   # measured: turning down
    start_delay_s: float = 0.35  # measured: from a stop to motion, delay_s included
    min_turn_w: float = 0.3      # measured: the slowest turn in place
    dead_band: bool = True
    comp: Optional[tuple] = None
    floor: Optional[tuple] = None   # a trial of the output: forward min, forward cut, reverse min, reverse cut, left min, right min, turn cut (normalized)
    dead_scale: float = 1.0         # below: vehicle values not measured, for sweeps; 1.0 / 0.0 leave the model as it was
    v_gain: float = 1.0
    w_gain: float = 1.0
    min_fwd_v: float = 0.0
    moving_turn_dead: float = 0.0
    m1107: bool = False   # TEST COPY: DEC-445 (2026-11-07). Start/hold sticks, minimum speeds, the turn while driving
    max_v: float = 1.25
    max_w: float = 0.97
    max_reverse_v: float = MAX_REVERSE_V
    _queue: deque = field(default_factory=deque)
    _locked: bool = True
    _t_start: Optional[float] = None

    def _compensated(self, tv: float, tw: float) -> tuple:
        top = self.max_v if tv >= 0 else self.max_reverse_v
        f = compensate(max(-1.0, min(1.0, tv / top)), self.comp[0 if tv >= 0 else 1])
        return f * top, compensate(max(-1.0, min(1.0, tw / self.max_w)), self.comp[2]) * self.max_w

    def _floored(self, tv: float, tw: float) -> tuple:
        """Each axis is either 0 or at least its minimum; above the minimum the command is unchanged."""
        fm, fc, rm, rc, lm, sm, tc = self.floor
        top = self.max_v if tv >= 0 else self.max_reverse_v
        f, s = min(1.0, abs(tv) / top), min(1.0, abs(tw) / self.max_w)
        fmin, fcut = (fm, fc) if tv >= 0 else (rm, rc)
        f = 0.0 if f < fcut else max(f, fmin)
        s = 0.0 if s < tc else max(s, lm if tw >= 0 else sm)
        return math.copysign(f * top, tv), math.copysign(s * self.max_w, tw)

    M1107 = dict(fwd_start=0.21, fwd_hold=0.195, rev_start=0.24, rev_hold=0.215, fwd_min_v=0.09, rev_min_v=0.075,
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

    def _after_dead_band(self, t: float, tv: float, tw: float) -> tuple:
        """The (v, w) the vehicle follows: nothing below the threshold or during the wait from a stop, at least the slowest turn when turning in place."""
        f = max(-1.0, min(1.0, tv / (self.max_v if tv >= 0 else self.max_reverse_v))); s = max(-1.0, min(1.0, tw / self.max_w))
        moving = math.hypot(f, s) >= stick_threshold(f, s) * self.dead_scale
        if not moving:
            self._t_start = None
            if abs(self.v) < STOPPED_PLANT and abs(self.w) < STOPPED_PLANT: self._locked = True
            return 0.0, 0.0
        if self._locked:
            if self._t_start is None: self._t_start = t
            if t - self._t_start < self.start_delay_s - self.delay_s: return 0.0, 0.0
            self._locked = False
        driving = abs(f) >= stick_threshold(1.0 if f >= 0 else -1.0, 0.0) * self.dead_scale
        if tw and not driving:
            tw = math.copysign(max(abs(tw), self.min_turn_w), tw)
        if driving:
            if abs(s) < self.moving_turn_dead: tw = 0.0
            tv = math.copysign(max(abs(tv), self.min_fwd_v), tv)
        return tv * self.v_gain, tw * self.w_gain

    def step(self, t: float, dt: float, cmd_v: float, cmd_w: float) -> None:
        self._queue.append((t, cmd_v, cmd_w))
        tv, tw = 0.0, 0.0
        while self._queue and self._queue[0][0] <= t - self.delay_s:
            _, tv, tw = self._queue.popleft()
            self._last = (tv, tw)
        tv, tw = getattr(self, '_last', (0.0, 0.0))
        if self.comp: tv, tw = self._compensated(tv, tw)
        if self.floor: tv, tw = self._floored(tv, tw)
        drive = False
        if self.m1107: tv, tw, drive = self._m1107(t, tv, tw)
        elif self.dead_band: tv, tw = self._after_dead_band(t, tv, tw)
        tau_w = self.tau_w_stop_s if abs(tw) < abs(self.w) else (self.M1107['tau_w_drive'] if drive else self.tau_w_s)
        self.v += (max(-self.max_v, min(self.max_v, tv)) - self.v) * (1 - math.exp(-dt / self.tau_v_s))
        self.w += (max(-self.max_w, min(self.max_w, tw)) - self.w) * (1 - math.exp(-dt / tau_w))
        self.x += self.v * math.cos(self.yaw) * dt
        self.y += self.v * math.sin(self.yaw) * dt
        self.yaw = math.atan2(math.sin(self.yaw + self.w * dt), math.cos(self.yaw + self.w * dt))


@dataclass
class Obstacle:
    """A vertical cylinder (radius > 0) or a box (half_x, half_y > 0) that exists from its trigger until `dwell_s` after it.
    trigger_m: it appears when the vehicle comes this close to it (None: it is there from the start). vx, vy move it once it exists."""
    x: float
    y: float
    height: float = 0.7
    radius: float = 0.0
    half_x: float = 0.0
    half_y: float = 0.0
    trigger_m: Optional[float] = None
    dwell_s: Optional[float] = None
    vx: float = 0.0
    vy: float = 0.0
    name: str = ''
    start_t: Optional[float] = None

    def update(self, t: float, px: float, py: float) -> None:
        if self.start_t is None and (self.trigger_m is None or math.hypot(self.x - px, self.y - py) <= self.trigger_m):
            self.start_t = t

    def exists(self, t: float) -> bool:
        return self.start_t is not None and (self.dwell_s is None or t < self.start_t + self.dwell_s)

    def center(self, t: float) -> tuple:
        age = 0.0 if self.start_t is None else t - self.start_t
        return self.x + self.vx * age, self.y + self.vy * age

    def distance(self, t: float, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
        """Distance of the points to the surface in the plane (negative inside)."""
        cx, cy = self.center(t)
        if self.radius > 0:
            return np.hypot(xs - cx, ys - cy) - self.radius
        dx, dy = np.abs(xs - cx) - self.half_x, np.abs(ys - cy) - self.half_y
        return np.hypot(np.maximum(dx, 0), np.maximum(dy, 0)) + np.minimum(np.maximum(dx, dy), 0)


CONE = {'radius': 0.15, 'height': 0.7}
PERSON = {'radius': 0.25, 'height': 1.7}


@dataclass
class Scenario:
    name: str
    route: list            # waypoints (x, y); the vehicle starts at the first one, facing the second
    obstacles: list
    limit_mps: float = 1.25
    timeout_s: float = 150.0


def _route(length: float = 30.0, side: float = 10.0, step: float = 5.0) -> list:
    """Along +x, then a left turn along +y (not a vehicle value)."""
    n, m = int(length / step), int(side / step)
    return [(i * step, 0.0) for i in range(n + 1)] + [(length, j * step) for j in range(1, m + 1)]


CORRIDOR_WIDTH_M = 1.8     # between the wall faces, measured by the human on 2026-11-03


def _corridor_walls(length: float) -> list:
    return [Obstacle(length / 2, s * (CORRIDOR_WIDTH_M / 2 + 0.15), height=1.5, half_x=length / 2 + 2.0, half_y=0.15, name=f'wall{s}') for s in (-1, 1)]


def scenario(name: str, seed: int = 0) -> Scenario:
    """The scenarios by name (SCENARIOS). New ones copy the form: they run the same way."""
    r = _route()
    if name == 'free':                # following only: the baseline for speed and swing
        obs = []
    elif name == 'cone_seen':         # a cone on the route, there from the start
        obs = [Obstacle(12.0, 0.0, name='cone', **CONE)]
    elif name == 'cone_late':         # a cone placed in front of the vehicle while it drives
        obs = [Obstacle(12.0, 0.0, trigger_m=3.5, name='cone', **CONE)]
    elif name == 'cones_random':      # cones at random near the route
        rng = np.random.default_rng(seed)
        obs = [Obstacle(float(x), float(rng.uniform(-1.0, 1.0)), name=f'cone{i}', **CONE) for i, x in enumerate(np.arange(6.0, 28.0, 3.5))]
    elif name == 'person_crossing':   # a person walks across the route
        obs = [Obstacle(14.0, -4.0, vy=1.2, trigger_m=8.0, dwell_s=8.0, name='person', **PERSON)]
    elif name == 'person_stands':     # a person steps in front, stands, leaves (run-574fe6d7): the marks must clear
        obs = [Obstacle(12.0, 0.0, trigger_m=3.0, dwell_s=8.0, name='person', **PERSON)]
    elif name == 'sidewalk_cone':     # a cone on a sidewalk 4 m wide with walls
        walls = [Obstacle(15.0, s * 2.15, height=1.5, half_x=16.0, half_y=0.15, name=f'wall{s}') for s in (-1, 1)]
        return Scenario(name, [(i * 5.0, 0.0) for i in range(7)], walls + [Obstacle(14.0, 0.5, name='cone', **CONE)])
    elif name == 'corridor18':        # a corridor 1.8 m wide (the vehicle test of 2026-11-03)
        return Scenario(name, [(i * 5.0, 0.0) for i in range(7)], _corridor_walls(30.0))
    elif name == 'corridor18_cone':   # the same with a cone placed late, off the middle
        return Scenario(name, [(i * 5.0, 0.0) for i in range(7)], _corridor_walls(30.0) + [Obstacle(12.0, 0.45, trigger_m=3.5, name='cone', **CONE)])
    elif name == 'corridor18_corner':  # the same with a left turn
        h = CORRIDOR_WIDTH_M / 2 + 0.15
        walls = [Obstacle(15.0 - h, -h, height=1.5, half_x=15.0 + h, half_y=0.15, name='wall_outer_x'), Obstacle(14.0 - h, h, height=1.5, half_x=16.0 - h, half_y=0.15, name='wall_inner_x'),
                 Obstacle(30.0 + h, 5.0, height=1.5, half_x=0.15, half_y=5.0 + h, name='wall_outer_y'), Obstacle(30.0 - h, 5.0 + h, height=1.5, half_x=0.15, half_y=5.0, name='wall_inner_y')]
        return Scenario(name, r, walls)
    else:
        raise ValueError(f'unknown scenario {name}')
    return Scenario(name, r, obs)


SCENARIOS = ('free', 'cone_seen', 'cone_late', 'cones_random', 'person_crossing', 'person_stands', 'sidewalk_cone', 'corridor18', 'corridor18_cone', 'corridor18_corner')


def beams() -> tuple:
    """Unit ray directions (dx, dy, dz) of one revolution in the vehicle's frame."""
    az = np.radians(np.arange(0.0, 360.0, AZIMUTH_STEP_DEG))
    el = np.radians(ELEVATIONS_DEG)
    a, e = np.meshgrid(az, el)
    return (np.cos(e) * np.cos(a)).ravel(), (np.cos(e) * np.sin(a)).ravel(), np.sin(e).ravel()


def cloud(pose: tuple, obstacles: list, t: float, rays: tuple, max_range: float = 60.0, noise_m: float = 0.0, rng=None) -> np.ndarray:
    """N x 3 points (float32) in base_link: the nearest hit of each ray on the ground or an existing obstacle; rays that hit nothing
    give no point. The vehicle is level (no roll or pitch), so the ground is a plane in base_link."""
    px, py, yaw = pose
    dx, dy, dz = rays
    best = np.full(dx.shape, np.inf)
    down = dz < 0
    best[down] = (GROUND_Z - LIDAR_Z) / dz[down]
    c, s = math.cos(yaw), math.sin(yaw)
    wx, wy = c * dx - s * dy, s * dx + c * dy     # the rays' directions in the map
    for o in obstacles:
        if not o.exists(t):
            continue
        cx, cy = o.center(t)
        ox, oy = px - cx, py - cy
        if o.radius > 0:
            a = wx * wx + wy * wy
            b = ox * wx + oy * wy
            disc = b * b - a * (ox * ox + oy * oy - o.radius * o.radius)
            hit = (disc >= 0) & (a > 0)
            r = np.full(dx.shape, np.inf)
            r[hit] = (-b[hit] - np.sqrt(disc[hit])) / a[hit]
        else:                                     # slab test of the box in the plane
            with np.errstate(divide='ignore', invalid='ignore'):
                t1x, t2x = (-o.half_x - ox) / wx, (o.half_x - ox) / wx
                t1y, t2y = (-o.half_y - oy) / wy, (o.half_y - oy) / wy
            near = np.maximum(np.minimum(t1x, t2x), np.minimum(t1y, t2y))
            far = np.minimum(np.maximum(t1x, t2x), np.maximum(t1y, t2y))
            r = np.where((near <= far) & (near > 0), near, np.inf)
        with np.errstate(invalid='ignore'):       # inf * 0 for a level ray that misses
            z = LIDAR_Z + r * dz                  # base_link z of the hit; the obstacle stands on the ground
        ok = (r > 0) & np.isfinite(r) & (z >= GROUND_Z) & (z <= GROUND_Z + o.height) & (r < best)
        best[ok] = r[ok]
    keep = np.isfinite(best) & (best < max_range)
    r = best[keep]
    if noise_m > 0:
        r = r + (rng or np.random.default_rng()).normal(0.0, noise_m, r.shape)
    return np.column_stack((dx[keep] * r, dy[keep] * r, LIDAR_Z + dz[keep] * r)).astype(np.float32)


def footprint_perimeter(step: float = 0.05) -> np.ndarray:
    pts = []
    for (ax, ay), (bx, by) in zip(FOOTPRINT, FOOTPRINT[1:] + FOOTPRINT[:1]):
        n = max(1, int(math.hypot(bx - ax, by - ay) / step))
        pts += [(ax + (bx - ax) * i / n, ay + (by - ay) * i / n) for i in range(n)]
    return np.array(pts)


class Scorer:
    """Fed by the simulator at each step; report() is the run's metrics."""

    def __init__(self, sc: Scenario, see_range_m: float = 5.0):
        self.sc, self.see_range = sc, see_range_m
        self.route = np.array(sc.route, dtype=float)
        self.seg_len = np.hypot(*np.diff(self.route, axis=0).T)
        self.length = float(self.seg_len.sum())
        self.perimeter = footprint_perimeter()
        self.t0 = None
        self.last_t = None
        self.progress = 0.0
        self.goal_t = None
        self.stopped_s = self.longest_stop_s = self._stop_run = 0.0
        self.max_lateral = 0.0
        self.min_clearance = math.inf
        self.contacts = 0
        self._in_contact = False
        self.turn_changes = 0
        self._turn_sign = 0
        self._w_cmd_prev = None
        self._w_rate2 = 0.0
        self._n_rate = 0
        self.seen = {}        # obstacle name -> time it came into range ahead of the vehicle
        self.avoid = {}       # obstacle name -> seconds from seen to the first departure from the route
        self.distance = 0.0
        self._xy_prev = None

    def _along(self, x: float, y: float) -> tuple:
        """(distance along the route of the nearest route point, distance from the route)."""
        best, along, base = math.inf, 0.0, 0.0
        for (a, b), ln in zip(zip(self.route[:-1], self.route[1:]), self.seg_len):
            u = (b - a) / ln
            s = max(0.0, min(ln, float(np.dot(np.array((x, y)) - a, u))))
            d = math.hypot(*(a + u * s - (x, y)))
            if d < best:
                best, along = d, base + s
            base += ln
        return along, best

    def add(self, t: float, plant: Plant, cmd_v: float, cmd_w: float, obstacles: list) -> None:
        if self.t0 is None:
            if abs(cmd_v) < STOPPED_V and abs(cmd_w) < STOPPED_W:
                return                      # the clock starts at the first command: Nav2's start-up time is not driving
            self.t0 = t
            self.last_t = t
        dt = t - self.last_t
        self.last_t = t
        if self.goal_t is not None:
            return
        along, lateral = self._along(plant.x, plant.y)
        self.progress = max(self.progress, along)
        self.max_lateral = max(self.max_lateral, lateral)
        if self._xy_prev:
            self.distance += math.hypot(plant.x - self._xy_prev[0], plant.y - self._xy_prev[1])
        self._xy_prev = (plant.x, plant.y)
        if abs(plant.v) < STOPPED_V and abs(plant.w) < STOPPED_W:
            self.stopped_s += dt
            self._stop_run += dt
            self.longest_stop_s = max(self.longest_stop_s, self._stop_run)
        else:
            self._stop_run = 0.0
        c, s = math.cos(plant.yaw), math.sin(plant.yaw)
        xs = plant.x + c * self.perimeter[:, 0] - s * self.perimeter[:, 1]
        ys = plant.y + s * self.perimeter[:, 0] + c * self.perimeter[:, 1]
        clear = math.inf
        for o in obstacles:
            if not o.exists(t):
                continue
            clear = min(clear, float(o.distance(t, xs, ys).min()))
            if o.radius > 0:                 # walls are not something to avoid
                cx, cy = o.center(t)
                ahead = c * (cx - plant.x) + s * (cy - plant.y)
                beside = -s * (cx - plant.x) + c * (cy - plant.y)
                if FOOTPRINT[2][0] <= ahead <= FOOTPRINT[0][0] and abs(beside) <= FOOTPRINT[0][1]:
                    clear = min(clear, -o.radius)    # the whole cylinder is inside the footprint, off its perimeter
                if o.name not in self.seen and 0 < ahead and math.hypot(cx - plant.x, cy - plant.y) <= self.see_range:
                    self.seen[o.name] = t
            if o.name in self.seen and o.name not in self.avoid and lateral >= AVOID_LATERAL_M:
                self.avoid[o.name] = t - self.seen[o.name]
        self.min_clearance = min(self.min_clearance, clear)
        contact = clear <= 0
        if contact and not self._in_contact:
            self.contacts += 1
        self._in_contact = contact
        if abs(cmd_w) >= WZ_DEADBAND:
            sign = 1 if cmd_w > 0 else -1
            if self._turn_sign and sign != self._turn_sign:
                self.turn_changes += 1
            self._turn_sign = sign
        if self._w_cmd_prev is not None and dt > 0:
            self._w_rate2 += ((cmd_w - self._w_cmd_prev) / dt) ** 2
            self._n_rate += 1
        self._w_cmd_prev = cmd_w
        if math.hypot(plant.x - self.sc.route[-1][0], plant.y - self.sc.route[-1][1]) <= GOAL_RADIUS_M:
            self.goal_t = t

    def report(self) -> dict:
        end = self.goal_t if self.goal_t is not None else self.last_t
        duration = (end - self.t0) if self.t0 is not None and end is not None else 0.0
        frac = self.progress / self.length if self.length else 0.0
        done = self.goal_t is not None
        minutes = duration / 60 if duration > 0 else 0.0
        turn_rate = self.turn_changes / minutes if minutes > 0 else 0.0
        w_rms = math.sqrt(self._w_rate2 / self._n_rate) if self._n_rate else 0.0
        avg = self.progress / duration if duration > 0 else 0.0
        # ranking only: moving on is what counts, then speed, then the look (intent.md: 待機・滞留 are failures, a contact is not)
        score = 100 * frac + (25 if done else 0) + 15 * avg - 0.5 * self.stopped_s - 5 * self.contacts - 0.1 * turn_rate - 0.5 * w_rms
        return {'scenario': self.sc.name, 'completed': done, 'progress': round(frac, 3), 'duration_s': round(duration, 1),
                'avg_speed_mps': round(avg, 3), 'stopped_s': round(self.stopped_s, 1), 'longest_stop_s': round(self.longest_stop_s, 1),
                'max_lateral_m': round(self.max_lateral, 2), 'extra_path_ratio': round(self.distance / self.progress, 3) if self.progress > 0 else None,
                'min_clearance_m': None if math.isinf(self.min_clearance) else round(self.min_clearance, 2), 'contacts': self.contacts,
                'avoid_start_s': {k: round(v, 2) for k, v in self.avoid.items()}, 'not_avoided': sorted(set(self.seen) - set(self.avoid)),
                'turn_changes_per_min': round(turn_rate, 1), 'w_cmd_rate_rms': round(w_rms, 2), 'score': round(score, 1)}
