"""Global localization core (ND-07, trial A3; REV-128, DEC-115 / DEC-200 / DEC-203). No ROS dependency.

The upstream parts (Autoware Core's NDT scan matcher and EKF localizer, the point-cloud map loader, pcl_ros filters) are run
unmodified by gouda_global_localization; this module holds Gouda's own small parts:
- map->odom from the EKF's map->base_link and the odom->base_link of the odometry (IFD-25) interpolated at the EKF pose's time
  (MapOdomEstimator). The EKF's own TF is not used (it would give base_link a second parent: D-17, RQ-I004);
- the twist for the EKF (only linear.x and angular.z are used by ekf_localizer) and the initial-pose covariance, from settings;
- the initial height from the mapping trajectory (GLIM's traj_imu.txt in the map frame): the human gives x, y and the heading;
- the estimator state of IFD-53 (evaluate): NORMAL only when every input is fresh (PRM-89) and every check passes (PRM-90..92).
  A missing or unreadable input is never NORMAL (IF-010, DEC-200). Ages are measured on the receiving node's clock.
Every number comes from the settings (design/generated/params/gouda_global_localization.yaml); nothing is hard-coded (RQ-I076).
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Optional

from gouda_core import odometry_core as oc

STATE_UNINITIALIZED, STATE_INITIALIZING, STATE_NORMAL, STATE_UNAVAILABLE = 0, 1, 2, 3   # gouda_interfaces/EstimatorStatus
STATE_NAMES = {STATE_UNINITIALIZED: '未初期化', STATE_INITIALIZING: '初期化中', STATE_NORMAL: '正常', STATE_UNAVAILABLE: '推定不能'}
REASONS = {
    'not_configured': 'no map is configured (gouda_global_localization is unconfigured)',
    'not_initialized': 'waiting for the initial pose and the initialization (activate)',
    'initializing': 'initialization in progress (Monte Carlo search, EKF / NDT activation)',
    'init_failed': 'the initialization failed (no map->odom is published)',
    'localizer_exited': 'the A3 launch (map loader / NDT / EKF / filters) ended',
    'input_stale': 'an input is missing or older than stale_timeout_s (PRM-89)',
    'ndt_diagnostics_missing': 'no NDT score in the diagnostics',
    'ndt_score_low': 'nearest_voxel_transformation_likelihood below ndt_nvtl_min (PRM-90)',
    'ekf_diagnostics_missing': 'no pose_no_update_count in the EKF diagnostics',
    'ekf_pose_not_updated': 'pose_no_update_count above ekf_pose_no_update_max (PRM-91)',
    'ekf_covariance_large': 'EKF x-y standard deviation above ekf_xy_stddev_max_m (PRM-92)',
    'no_map_odom': 'map->odom could not be computed yet (no odometry at the EKF pose time)',
}
DOUBLE_SETTINGS = ['points_near_crop_m', 'points_far_crop_m', 'points_voxel_leaf_m', 'twist_vx_variance', 'twist_wz_variance',
                   'initial_xy_variance', 'initial_z_variance', 'initial_roll_pitch_variance', 'initial_yaw_variance',
                   'status_period_s', 'stale_timeout_s', 'ndt_nvtl_min', 'ekf_xy_stddev_max_m']   # PRM-79..90, PRM-92
INT_SETTINGS = ['ekf_pose_no_update_max']                                                         # PRM-91
NDT_SCORE_KEY = 'nearest_voxel_transformation_likelihood'
EKF_NO_UPDATE_KEY = 'pose_no_update_count'


@dataclass(frozen=True)
class Settings:
    points_near_crop_m: float
    points_far_crop_m: float
    points_voxel_leaf_m: float
    twist_vx_variance: float
    twist_wz_variance: float
    initial_xy_variance: float
    initial_z_variance: float
    initial_roll_pitch_variance: float
    initial_yaw_variance: float
    status_period_s: float
    stale_timeout_s: float
    ndt_nvtl_min: float
    ekf_xy_stddev_max_m: float
    ekf_pose_no_update_max: int

    @staticmethod
    def from_values(values: dict) -> 'Settings':
        missing = [k for k in DOUBLE_SETTINGS + INT_SETTINGS if values.get(k) is None]
        if missing:
            raise ValueError(f'settings missing: {missing}')
        s = Settings(**{k: float(values[k]) for k in DOUBLE_SETTINGS}, **{k: int(values[k]) for k in INT_SETTINGS})
        positive = ['points_far_crop_m', 'points_voxel_leaf_m', 'status_period_s', 'stale_timeout_s', 'ekf_xy_stddev_max_m']
        bad = [k for k in positive if not getattr(s, k) > 0]
        bad += [k for k in DOUBLE_SETTINGS + INT_SETTINGS if k not in positive and k != 'ndt_nvtl_min' and getattr(s, k) < 0]
        if not s.points_near_crop_m < s.points_far_crop_m:
            bad.append('points_near_crop_m must be smaller than points_far_crop_m')
        if bad:
            raise ValueError(f'settings out of range: {bad}')
        return s


# ---------------------------------------------------------------- poses

def inverse(p: oc.Pose) -> oc.Pose:
    qi = (-p[3], -p[4], -p[5], p[6])
    t = oc.rotate(qi, p[:3])
    return (-t[0], -t[1], -t[2], *qi)


def interpolate(p0: oc.Pose, t0: float, p1: oc.Pose, t1: float, t: float) -> oc.Pose:
    """Pose at t between (t0, p0) and (t1, p1): linear position, normalised linear quaternion (short arc)."""
    a = 0 if t1 == t0 else (t - t0) / (t1 - t0)
    q0, q1 = p0[3:], p1[3:]
    if sum(x * y for x, y in zip(q0, q1)) < 0:
        q1 = tuple(-x for x in q1)
    q = [x + (y - x) * a for x, y in zip(q0, q1)]
    n = math.sqrt(sum(x * x for x in q))
    return (*(x + (y - x) * a for x, y in zip(p0[:3], p1[:3])), *(x / n for x in q))


class OdomBuffer:
    """odom->base_link poses of IFD-25 kept for span_s (the stale timeout, PRM-89) behind the newest."""

    def __init__(self, span_s: float):
        self.span = span_s
        self.items: deque = deque()

    def add(self, t: float, pose: oc.Pose) -> None:
        if self.items and t <= self.items[-1][0]:
            return   # out of order or repeated: ignored (the interpolation needs increasing times)
        self.items.append((t, pose))
        while self.items and self.items[0][0] < t - self.span:
            self.items.popleft()

    @property
    def newest(self) -> Optional[float]:
        return self.items[-1][0] if self.items else None

    def at(self, t: float) -> Optional[oc.Pose]:
        """Interpolated pose at t, or None when t is outside the kept times (no extrapolation)."""
        if not self.items or t < self.items[0][0] or t > self.items[-1][0]:
            return None
        prev = self.items[0]
        for item in self.items:
            if item[0] >= t:
                return item[1] if item[0] == t else interpolate(prev[1], prev[0], item[1], item[0], t)
            prev = item
        return None


class MapOdomEstimator:
    """map->odom = (map->base_link of the EKF at t) * inverse(odom->base_link at t). An EKF pose newer than the newest odometry
    waits (only the latest one) until the odometry has reached its time."""

    def __init__(self, span_s: float):
        self.odom = OdomBuffer(span_s)
        self.pending: Optional[tuple] = None
        self.map_odom: Optional[oc.Pose] = None
        self.map_odom_time: Optional[float] = None

    def on_odometry(self, t: float, odom_base: oc.Pose) -> None:
        self.odom.add(t, odom_base)
        if self.pending is not None and self.odom.newest is not None and self.pending[0] <= self.odom.newest:
            pending, self.pending = self.pending, None
            self._compute(*pending)

    def on_ekf_pose(self, t: float, map_base: oc.Pose) -> None:
        if self.odom.newest is not None and t <= self.odom.newest:
            self._compute(t, map_base)
        else:
            self.pending = (t, map_base)

    def _compute(self, t: float, map_base: oc.Pose) -> None:
        odom_base = self.odom.at(t)
        if odom_base is None:
            return
        self.map_odom = oc.compose(map_base, inverse(odom_base))
        self.map_odom_time = t

    def reset(self) -> None:
        self.odom = OdomBuffer(self.odom.span); self.pending = None; self.map_odom = None; self.map_odom_time = None


# ---------------------------------------------------------------- covariances, twist, initial pose

def xy_stddev(cov: list) -> float:
    """Square root of the larger eigenvalue of the x-y block of a 6x6 row-major covariance."""
    a, b, c = cov[0], (cov[1] + cov[6]) / 2, cov[7]
    m = (a + c) / 2; d = math.sqrt(max(((a - c) / 2) ** 2 + b * b, 0))
    return math.sqrt(max(m + d, 0))


def twist_covariance(s: Settings) -> list:
    """6x6 row-major; ekf_localizer reads [0] (linear.x) and [35] (angular.z) only, the others stay 0."""
    cov = [0.0] * 36
    cov[0], cov[35] = s.twist_vx_variance, s.twist_wz_variance
    return cov


def initial_pose_covariance(s: Settings) -> list:
    cov = [0.0] * 36
    cov[0] = cov[7] = s.initial_xy_variance
    cov[14] = s.initial_z_variance
    cov[21] = cov[28] = s.initial_roll_pitch_variance
    cov[35] = s.initial_yaw_variance
    return cov


def read_tum(text: str) -> list:
    """Rows (t, x, y, z) of a TUM trajectory (t x y z qx qy qz qw); comment and malformed lines are skipped."""
    rows = []
    for line in text.splitlines():
        f = line.split()
        if len(f) != 8 or line.lstrip().startswith('#'):
            continue
        try:
            rows.append(tuple(float(v) for v in f[:4]))
        except ValueError:
            continue
    return rows


def initial_height(trajectory: list, x: float, y: float, imu_height_above_base_m: float) -> Optional[tuple]:
    """(z of base_link, horizontal distance to the nearest trajectory point) from the mapping trajectory of the IMU, or None.

    GLIM's map frame is its odom frame at the start of mapping (z up from the IMU's gravity); traj_imu.txt holds the IMU poses.
    base_link's height is the nearest IMU pose's height minus the IMU's height above base_link (/config imu_mount_z_m); the
    small roll and pitch of the vehicle are neglected here and searched by the NDT (initial_z_variance, PRM-85)."""
    if not trajectory:
        return None
    best = min(trajectory, key=lambda r: (r[1] - x) ** 2 + (r[2] - y) ** 2)
    return best[3] - imu_height_above_base_m, math.hypot(best[1] - x, best[2] - y)


# ---------------------------------------------------------------- diagnostics and state

def read_diagnostics(statuses: list) -> dict:
    """{NDT_SCORE_KEY: float, EKF_NO_UPDATE_KEY: int} found in a list of (name, {key: value}) diagnostic statuses."""
    out = {}
    for _name, values in statuses:
        if NDT_SCORE_KEY in values:
            try: out[NDT_SCORE_KEY] = float(values[NDT_SCORE_KEY])
            except (TypeError, ValueError): pass
        if EKF_NO_UPDATE_KEY in values:
            try: out[EKF_NO_UPDATE_KEY] = int(float(values[EKF_NO_UPDATE_KEY]))
            except (TypeError, ValueError): pass
    return out


@dataclass
class Inputs:
    """What gouda_global_localization knows at one evaluation. Times are receive times on the node's clock (s)."""
    phase: str = 'unconfigured'          # unconfigured / waiting / initializing / running / failed
    phase_detail: str = ''
    localizer_running: bool = False
    last_ekf_pose: Optional[float] = None
    last_ndt_score: Optional[float] = None
    last_ekf_diag: Optional[float] = None
    last_odometry: Optional[float] = None
    ndt_nvtl: Optional[float] = None
    ekf_pose_no_update_count: Optional[int] = None
    ekf_xy_stddev_m: Optional[float] = None
    has_map_odom: bool = False


def oldest_age(now: float, inp: Inputs) -> Optional[float]:
    times = [inp.last_ekf_pose, inp.last_ndt_score, inp.last_ekf_diag, inp.last_odometry]
    return None if any(t is None for t in times) else now - min(times)


def evaluate(now: float, inp: Inputs, s: Settings) -> tuple:
    """(state, reason, detail) of IFD-53. The checks are made in this order; the first failing one is the reason."""
    if inp.phase == 'unconfigured':
        return STATE_UNINITIALIZED, 'not_configured', REASONS['not_configured']
    if inp.phase == 'waiting':
        return STATE_UNINITIALIZED, 'not_initialized', REASONS['not_initialized']
    if inp.phase == 'failed':
        return STATE_UNAVAILABLE, 'init_failed', inp.phase_detail or REASONS['init_failed']
    if not inp.localizer_running:
        return STATE_UNAVAILABLE, 'localizer_exited', REASONS['localizer_exited']
    if inp.phase == 'initializing':
        return STATE_INITIALIZING, 'initializing', inp.phase_detail or REASONS['initializing']
    stale = [name for name, t in (('ekf_pose', inp.last_ekf_pose), ('ndt_diagnostics', inp.last_ndt_score),
                                  ('ekf_diagnostics', inp.last_ekf_diag), ('odometry', inp.last_odometry))
             if t is None or now - t > s.stale_timeout_s]
    if stale:
        return STATE_UNAVAILABLE, 'input_stale', f"{REASONS['input_stale']}: {', '.join(stale)}"
    if inp.ndt_nvtl is None:
        return STATE_UNAVAILABLE, 'ndt_diagnostics_missing', REASONS['ndt_diagnostics_missing']
    if inp.ndt_nvtl < s.ndt_nvtl_min:
        return STATE_UNAVAILABLE, 'ndt_score_low', f"{REASONS['ndt_score_low']}: {inp.ndt_nvtl:.3f} < {s.ndt_nvtl_min}"
    if inp.ekf_pose_no_update_count is None:
        return STATE_UNAVAILABLE, 'ekf_diagnostics_missing', REASONS['ekf_diagnostics_missing']
    if inp.ekf_pose_no_update_count > s.ekf_pose_no_update_max:
        return STATE_UNAVAILABLE, 'ekf_pose_not_updated', f"{REASONS['ekf_pose_not_updated']}: {inp.ekf_pose_no_update_count} > {s.ekf_pose_no_update_max}"
    if inp.ekf_xy_stddev_m is None or inp.ekf_xy_stddev_m > s.ekf_xy_stddev_max_m:
        return STATE_UNAVAILABLE, 'ekf_covariance_large', f"{REASONS['ekf_covariance_large']}: {inp.ekf_xy_stddev_m} > {s.ekf_xy_stddev_max_m}"
    if not inp.has_map_odom:
        return STATE_UNAVAILABLE, 'no_map_odom', REASONS['no_map_odom']
    return STATE_NORMAL, '', ''
