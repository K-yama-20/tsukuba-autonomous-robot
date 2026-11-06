"""The height band of upstream pointcloud_to_laserscan 2.0.2 (PointCloudToLaserScanNode::cloudCallback), copied in numpy.

Source read: https://github.com/ros-perception/pointcloud_to_laserscan/blob/2.0.2/src/pointcloud_to_laserscan_node.cpp
(ros-jazzy-pointcloud-to-laserscan 2.0.2; Apache-2.0). Line numbers below are of that file.

What is copied (the parameters Gouda sets are in gouda_core/gouda_core/nav2_config.py scan_parameters(); the rest stay at the
package defaults, l.61-76):
- target_frame (l.61): the caller transforms the cloud first (l.166-176, tf2 doTransform of PointCloud2 in float).
  Use ``transform_points`` of geometry.py, which computes in float32 like the float Eigen transform of tf2_sensor_msgs.
- min_height / max_height (l.67-68): a point is rejected when z > max_height or z < min_height (l.191). Both ends are kept.
- range_min / range_max (l.73-74): range = hypot(x, y) in the target frame (l.199); rejected when range < range_min or
  range > range_max (l.200-213). Defaults 0.0 and the largest double.
- angle_min / angle_max / angle_increment (l.69-71): defaults -pi, pi, pi/180. They are stored in the float32 fields of
  sensor_msgs/LaserScan (l.147-149), so ranges_size = ceil((angle_max - angle_min) / angle_increment) is computed in float32
  (l.156-157); angle = atan2(y, x) (l.215) is rejected outside [angle_min, angle_max] (l.216); the bin is
  int((angle - angle_min) / angle_increment) (l.225, truncation).
- use_inf / inf_epsilon (l.75-76): bins without a point are +inf (use_inf true) or range_max + inf_epsilon (l.160-164).
- nearest point per bin (l.226-228): the bin keeps the smallest range; ranges are float32.
- NaN points are skipped (l.183).
Not copied (no effect on the ranges): the subscription thread, queue_size, transform_tolerance, scan_time, the header.
hypot/atan2 are evaluated in double from the float32 coordinates; the C++ may pick the float overloads (difference < 1 ulp of
float, far below the noise of the sensors).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

F32 = np.float32
DBL_MAX = np.finfo(np.float64).max


@dataclass
class P2LParams:
    min_height: float = float(np.finfo(np.float64).tiny)   # std::numeric_limits<double>::min() (l.67)
    max_height: float = DBL_MAX
    angle_min: float = -math.pi
    angle_max: float = math.pi
    angle_increment: float = math.pi / 180.0
    range_min: float = 0.0
    range_max: float = DBL_MAX
    use_inf: bool = True
    inf_epsilon: float = 1.0


def gouda_params(min_height: float, max_height: float, range_max: float) -> P2LParams:
    """The values of nav2_config.scan_parameters(): the band PRM-70 / PRM-71, range_max, the whole circle, use_inf true."""
    return P2LParams(min_height=min_height, max_height=max_height, range_max=range_max,
                     angle_min=-math.pi, angle_max=math.pi, use_inf=True)


def n_bins(p: P2LParams) -> int:
    amin, amax, inc = F32(p.angle_min), F32(p.angle_max), F32(p.angle_increment)
    return int(np.ceil(F32((amax - amin) / inc)))


def bin_angles(p: P2LParams) -> np.ndarray:
    """Centre-less bin angles as a LaserScan consumer reads them: angle_min + i * angle_increment (float32 fields)."""
    return float(F32(p.angle_min)) + np.arange(n_bins(p)) * float(F32(p.angle_increment))


def in_band(points: np.ndarray, p: P2LParams) -> np.ndarray:
    """Mask of the points the node would use (height, range and angle tests of l.183-222)."""
    x = points[:, 0].astype(np.float64); y = points[:, 1].astype(np.float64); z = points[:, 2].astype(np.float64)
    ok = ~(np.isnan(x) | np.isnan(y) | np.isnan(z))
    ok &= ~((z > p.max_height) | (z < p.min_height))
    r = np.hypot(x, y)
    ok &= ~(r < p.range_min) & ~(r > p.range_max)
    a = np.arctan2(y, x)
    ok &= ~((a < float(F32(p.angle_min))) | (a > float(F32(p.angle_max))))
    return ok


def laserscan(points: np.ndarray, p: P2LParams):
    """(ranges float32[n_bins], winner int[n_bins]): the scan of ``points`` (N x 3, already in target_frame) and, per bin, the index
    of the point whose range was kept (-1 when none)."""
    nb = n_bins(p)
    fill = np.inf if p.use_inf else float(F32(p.range_max)) + p.inf_epsilon
    ranges = np.full(nb, fill, dtype=F32)
    winner = np.full(nb, -1, dtype=np.int64)
    if len(points) == 0:
        return ranges, winner
    ok = in_band(points, p)
    idx = np.nonzero(ok)[0]
    if len(idx) == 0:
        return ranges, winner
    x = points[idx, 0].astype(np.float64); y = points[idx, 1].astype(np.float64)
    r = np.hypot(x, y)
    a = np.arctan2(y, x)
    b = ((a - float(F32(p.angle_min))) / float(F32(p.angle_increment))).astype(np.int64)   # int() truncation, a >= angle_min
    # With the defaults (angle_min -pi, angle_max pi, increment pi/180 as float32), ranges_size is 360 but a point whose angle is
    # within 1.36e-7 rad of +pi gets index 360 (float32(pi/180) is a little smaller than pi/180): l.226-227 then read and write one
    # element past the vector (undefined behaviour in the C++). Such a point never reaches the published ranges; it is dropped here.
    inside = b < nb
    idx, r, b = idx[inside], r[inside], b[inside]
    # nearest per bin; the kept value is float32(min range) (the sequential compare against the stored float gives the same)
    order = np.lexsort((r, b))
    bs = b[order]
    first = np.r_[True, bs[1:] != bs[:-1]]
    sel = order[first]
    keep = F32(r[sel]) < ranges[b[sel]]          # only replace when smaller than the fill value (use_inf false case)
    ranges[b[sel][keep]] = F32(r[sel][keep])
    winner[b[sel][keep]] = idx[sel][keep]
    return ranges, winner


def bin_of(points: np.ndarray, p: P2LParams) -> np.ndarray:
    """The bin each point would fall in by its direction alone (height and range not tested; -1 outside the angles or past the end)."""
    a = np.arctan2(points[:, 1].astype(np.float64), points[:, 0].astype(np.float64))
    b = np.floor((a - float(F32(p.angle_min))) / float(F32(p.angle_increment))).astype(np.int64)
    bad = (a < float(F32(p.angle_min))) | (a > float(F32(p.angle_max))) | (b >= n_bins(p)) | (b < 0)
    return np.where(bad, -1, b)
