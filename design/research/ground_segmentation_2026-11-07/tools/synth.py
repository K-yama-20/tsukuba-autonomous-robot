"""Synthetic scenes with ground truth, and ray-cast scans of XT-32-like and MID-360-like sensors.

World frame W = the true base_link of a vehicle standing level on flat ground (x forward, y left, z up). The ground under the vehicle
is z = -base_height. Every surface is intersected analytically; the first hit along each ray is the return.
Labels: 0 = ground (flat or slope), k >= 1 = obstacle k (Scene.objects[k - 1]).

Sensor values (sources):
- XT-32 (design/docs/lidar_xt32_spec.md, measured from records, not the datasheet): 32 beams, ring n at +15.05 - 1.00 n deg,
  2000 columns over 360 deg (0.180 deg). Height above ground 1.182 m measured; the mounting in base_link comes from /tf_static.
  Range and angle noise: not known (the datasheet is not checked, 原本未照合). The runs set the range noise to a comparison
  assumption (比較用の仮定), given by the caller.
- MID-360 (Livox Mid-360 User Manual v1.2, Specifications): FOV horizontal 360 deg, vertical -7 to 52 deg; 200,000 points/s at
  10 Hz (20,000 points per frame); close blind zone 0.1 m; range random error (1 sigma) <= 2 cm @ 10 m and <= 3 cm @ 0.2 m; angular
  random error (1 sigma) <= 0.15 deg; detection range 40 m @ 10 % reflectivity. The scan pattern is not published as a point
  distribution, so the directions are a comparison assumption: azimuth and elevation each uniform (a Halton sequence that continues
  from frame to frame, i.e. never repeats), and the range error is interpolated linearly between the two published points.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from geometry import Transform, ry


# ------------------------------------------------------------------------------------------------------------- scenes
@dataclass
class Box:
    name: str
    x0: float; x1: float; y0: float; y1: float; h: float          # height above the local ground at the box's centre
    kind: str = 'box'


@dataclass
class Cylinder:
    name: str
    cx: float; cy: float; r: float; h: float
    kind: str = 'cylinder'


@dataclass
class Cone:
    name: str
    cx: float; cy: float; r: float; h: float                       # base radius r, apex h above the ground
    kind: str = 'cone'


@dataclass
class Scene:
    name: str
    base_height: float                     # base_link above the ground under the vehicle
    slope_x: float = math.inf              # the ground is flat for x < slope_x
    slope_deg: float = 0.0                 # then rises (positive) or falls (negative) along +x
    objects: list = field(default_factory=list)

    def ground_z(self, x):
        x = np.asarray(x, dtype=np.float64)
        z = np.full(x.shape, -self.base_height)
        k = x > self.slope_x
        z[k] += (x[k] - self.slope_x) * math.tan(math.radians(self.slope_deg))
        return z


def _ray_ground(scene: Scene, o, d):
    """t of the first hit with the piecewise-planar ground (flat for x < slope_x, then the slope)."""
    n = len(d)
    t = np.full(n, np.inf)
    zg = -scene.base_height
    # flat piece
    with np.errstate(divide='ignore', invalid='ignore'):
        tf = (zg - o[2]) / d[:, 2]
    xf = o[0] + tf * d[:, 0]
    ok = (tf > 1e-9) & np.isfinite(tf) & (xf <= scene.slope_x)
    t[ok] = tf[ok]
    if math.isfinite(scene.slope_x):
        m = math.tan(math.radians(scene.slope_deg))
        # z = zg + m (x - xs)  ->  o_z + t d_z = zg + m (o_x + t d_x - xs)
        den = d[:, 2] - m * d[:, 0]
        with np.errstate(divide='ignore', invalid='ignore'):
            ts = (zg + m * (o[0] - scene.slope_x) - o[2]) / den
        xs = o[0] + ts * d[:, 0]
        ok = (ts > 1e-9) & np.isfinite(ts) & (xs > scene.slope_x)
        t = np.where(ok & (ts < t), ts, t)
    return t


def _ray_box(b: Box, scene: Scene, o, d):
    zg = float(scene.ground_z(np.array([(b.x0 + b.x1) / 2]))[0])
    lo = np.array([b.x0, b.y0, zg - 0.05]); hi = np.array([b.x1, b.y1, zg + b.h])   # sunk 5 cm so a slope cannot leave a gap
    with np.errstate(divide='ignore', invalid='ignore'):
        inv = 1.0 / d
        t1 = (lo - o) * inv; t2 = (hi - o) * inv
    tmin = np.nanmax(np.minimum(t1, t2), axis=1); tmax = np.nanmin(np.maximum(t1, t2), axis=1)
    hit = (tmax >= tmin) & (tmax > 1e-9)
    t = np.where(tmin > 1e-9, tmin, tmax)
    return np.where(hit, t, np.inf)


def _ray_cylinder(c: Cylinder, scene: Scene, o, d):
    zg = float(scene.ground_z(np.array([c.cx]))[0])
    ox, oy = o[0] - c.cx, o[1] - c.cy
    a = d[:, 0] ** 2 + d[:, 1] ** 2
    b = 2 * (ox * d[:, 0] + oy * d[:, 1])
    cc = ox * ox + oy * oy - c.r * c.r
    disc = b * b - 4 * a * cc
    t = np.full(len(d), np.inf)
    ok = (disc >= 0) & (a > 1e-12)
    sq = np.sqrt(np.where(ok, disc, 0))
    for sgn in (-1, 1):
        with np.errstate(divide='ignore', invalid='ignore'):
            ti = (-b + sgn * sq) / (2 * a)
        z = o[2] + ti * d[:, 2]
        good = ok & (ti > 1e-9) & (z >= zg - 0.05) & (z <= zg + c.h) & (ti < t)
        t = np.where(good, ti, t)
    # top disc
    with np.errstate(divide='ignore', invalid='ignore'):
        tt = (zg + c.h - o[2]) / d[:, 2]
        px, py = ox + tt * d[:, 0], oy + tt * d[:, 1]
        good = (tt > 1e-9) & (px * px + py * py <= c.r * c.r) & (tt < t)
    return np.where(good, tt, t)


def _ray_cone(c: Cone, scene: Scene, o, d):
    zg = float(scene.ground_z(np.array([c.cx]))[0])
    k = c.r / c.h                    # radius = k (apex_z - z)
    apex = zg + c.h
    ox, oy, oz = o[0] - c.cx, o[1] - c.cy, o[2] - apex
    # x^2 + y^2 = k^2 z^2 (z <= 0 relative to the apex)
    a = d[:, 0] ** 2 + d[:, 1] ** 2 - k * k * d[:, 2] ** 2
    b = 2 * (ox * d[:, 0] + oy * d[:, 1] - k * k * oz * d[:, 2])
    cc = ox * ox + oy * oy - k * k * oz * oz
    disc = b * b - 4 * a * cc
    t = np.full(len(d), np.inf)
    ok = (disc >= 0) & (np.abs(a) > 1e-12)
    sq = np.sqrt(np.where(ok, disc, 0))
    for sgn in (-1, 1):
        with np.errstate(divide='ignore', invalid='ignore'):
            ti = (-b + sgn * sq) / (2 * a)
        z = oz + ti * d[:, 2]
        good = ok & (ti > 1e-9) & (z <= 0) & (z >= -c.h - 0.05) & (ti < t)
        t = np.where(good, ti, t)
    return t


def raycast(scene: Scene, origin_w: np.ndarray, dirs_w: np.ndarray, max_range: float):
    """(t, label): the first hit distance along each unit direction (inf when nothing within max_range) and its label."""
    o = np.asarray(origin_w, dtype=np.float64)
    t = _ray_ground(scene, o, dirs_w)
    lab = np.zeros(len(dirs_w), dtype=np.int64)
    fn = {'box': _ray_box, 'cylinder': _ray_cylinder, 'cone': _ray_cone}
    for k, ob in enumerate(scene.objects, start=1):
        tk = fn[ob.kind](ob, scene, o, dirs_w)
        closer = tk < t
        t = np.where(closer, tk, t); lab = np.where(closer, k, lab)
    far = ~(t <= max_range)
    t[far] = np.inf; lab[far] = -1
    return t, lab


# ------------------------------------------------------------------------------------------------------------- sensors
def _halton(i, base):
    f, r = 1.0, np.zeros(len(i))
    i = i.astype(np.int64).copy()
    while (i > 0).any():
        f /= base
        r += f * (i % base)
        i //= base
    return r


@dataclass
class SensorModel:
    name: str
    kind: str                      # 'xt32' or 'mid360'
    range_sigma: callable          # sigma(r) in m
    angle_sigma_deg: float
    min_range: float               # returns closer than this are dropped
    max_range: float

    def directions(self, frame: int, rng: np.random.Generator) -> np.ndarray:
        """Unit directions in the sensor frame for one frame."""
        if self.kind == 'xt32':
            el = np.radians(15.05 - 1.00 * np.arange(32))
            az0 = rng.uniform(0, 0.18)                      # the column phase changes from frame to frame
            az = np.radians(az0 + 0.18 * np.arange(2000))
            A, E = np.meshgrid(az, el, indexing='ij')
            A, E = A.ravel(), E.ravel()
        else:
            n = 20000
            i = np.arange(frame * n + 1, (frame + 1) * n + 1)
            A = 2 * np.pi * _halton(i, 2)
            E = np.radians(-7.0 + 59.0 * _halton(i, 3))
        return np.c_[np.cos(E) * np.cos(A), np.cos(E) * np.sin(A), np.sin(E)]


def xt32_model(range_sigma_m: float) -> SensorModel:
    return SensorModel('XT-32', 'xt32', lambda r: np.full(np.shape(r), range_sigma_m), 0.0, 0.0, 120.0)


def mid360_model() -> SensorModel:
    def sig(r):
        r = np.asarray(r, dtype=np.float64)
        return np.interp(r, [0.2, 10.0], [0.03, 0.02])   # constant outside the two published points
    return SensorModel('MID-360', 'mid360', sig, 0.15, 0.1, 40.0)


def scan(scene: Scene, sensor: SensorModel, T_base_sensor_true: Transform, frame: int, rng: np.random.Generator):
    """(points_sensor float32 N x 3 as measured, labels N, true points in W N x 3)."""
    d_s = sensor.directions(frame, rng)
    d_w = d_s @ T_base_sensor_true.R.T
    t, lab = raycast(scene, T_base_sensor_true.t, d_w, sensor.max_range)
    ok = np.isfinite(t) & (t >= sensor.min_range)
    d_s, t, lab = d_s[ok], t[ok], lab[ok]
    true_w = T_base_sensor_true.t + t[:, None] * (d_s @ T_base_sensor_true.R.T)
    # measurement: noisy range along a noisy reported direction (in the sensor frame)
    r = t + rng.normal(0, 1, len(t)) * sensor.range_sigma(t)
    if sensor.angle_sigma_deg > 0:
        az = np.arctan2(d_s[:, 1], d_s[:, 0]) + np.radians(sensor.angle_sigma_deg) * rng.normal(0, 1, len(t))
        el = np.arcsin(np.clip(d_s[:, 2], -1, 1)) + np.radians(sensor.angle_sigma_deg) * rng.normal(0, 1, len(t))
        d_s = np.c_[np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)]
    pts = (r[:, None] * d_s).astype(np.float32)
    return pts, lab, true_w


def with_pitch_error(T_nominal: Transform, err_deg: float) -> Transform:
    """The true mounting: the nominal one tilted by err_deg about base_link's y axis (positive = the sensor leans nose-down toward the
    vehicle's front, REP-103 pitch). The same as the vehicle body pitched by err_deg against the ground under it."""
    return Transform(ry(math.radians(err_deg)) @ T_nominal.R, T_nominal.t.copy())


# ------------------------------------------------------------------------------------------------------------- the scenes of the runs
CONE = (0.19, 0.70)        # base radius, height (比較用の仮定: the regulations name green road cones but give no size)
LOW_BOX = (0.30, 0.15)     # side, height
MID_BOX = (0.30, 0.30)     # side, height (the 0.3 m low object of the drive simulator, issue #32)
POLE = (0.06, 0.80)        # radius, height: one leg of a standing person


def _objects():
    s, h = LOW_BOX; s2, h2 = MID_BOX; pr, ph = POLE; cr, chh = CONE
    return [
        Cone('cone_1.8m', 1.5, 0.9, cr, chh), Cone('cone_3.6m', 3.5, 1.0, cr, chh),
        Box('box15_1.3m', 1.2 - s / 2, 1.2 + s / 2, -0.4 - s / 2, -0.4 + s / 2, h),
        Box('box15_2.4m', 2.4 - s / 2, 2.4 + s / 2, -s / 2, s / 2, h),
        Box('box30_2.4m', 2.0 - s2 / 2, 2.0 + s2 / 2, -1.3 - s2 / 2, -1.3 + s2 / 2, h2),
        Box('box30_4.3m', 4.2 - s2 / 2, 4.2 + s2 / 2, -0.8 - s2 / 2, -0.8 + s2 / 2, h2),
        Cylinder('leg_a_2.1m', 1.0, 1.9, pr, ph), Cylinder('leg_b_2.3m', 1.0, 2.1, pr, ph),
        Cylinder('leg_c_3.9m', 3.0, -2.5, pr, ph), Cylinder('leg_d_4.0m', 3.2, -2.5, pr, ph),
    ]


def scenes(base_height: float, slope_deg: float, curb_heights=(0.08, 0.10, 0.12, 0.15)):
    out = [Scene('flat', base_height),
           Scene(f'up{slope_deg:g}', base_height, 2.0, slope_deg),
           Scene(f'down{slope_deg:g}', base_height, 2.0, -slope_deg)]
    for hc in curb_heights:
        # a curb across the way 3.0 m ahead and a raised step (sidewalk edge) along the left side
        out.append(Scene(f'curb{int(round(hc * 100)):02d}', base_height, objects=[
            Box(f'curb_{hc:.2f}_ahead', 3.0, 3.15, -1.5, 1.5, hc),
            Box(f'step_{hc:.2f}_left', -3.0, 8.0, 1.2, 4.0, hc)]))
    out.append(Scene('objects', base_height, objects=_objects()))
    out.append(Scene(f'objects_up{slope_deg:g}', base_height, 2.0, slope_deg, objects=_objects()))
    return out
