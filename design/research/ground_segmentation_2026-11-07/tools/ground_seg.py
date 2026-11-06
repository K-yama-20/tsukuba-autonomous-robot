"""The OSS ground segmentation, used through their published Python bindings (CLAUDE.md 1.11: not written here).

- Patchwork++: PyPI ``pypatchworkpp==1.4.1`` (url-kaist/patchwork-plusplus tag v1.4.1, commit 3e6903a1d5537a4cc2ace897b0bbb98a92d6014c,
  BSD-2-Clause). Every Params value stays the C++ default (cpp/patchworkpp/include/patchwork/patchworkpp.h, Params()) except
  ``sensor_height`` (the sensor's height above the ground, from the mounting) and, when given, ``min_range`` / ``max_range``.
  ``enable_RNR`` is set false: RNR needs an intensity column and with x, y, z only it returns at once after printing
  "RNR requires intensity information !" (patchworkpp.cpp reflected_noise_removal), so the result is the same without the print.
  The object keeps its adaptive thresholds (elevation_thr, flatness_thr, and sensor_height itself, update_elevation_thr) from frame
  to frame, as in the ROS node: use one object per sequence.
  Points outside (min_range, max_range] are returned as non-ground (pc2czm).
- linefit: PyPI ``linefit==1.1.0`` (Kin-Zhang/linefit tag v1.1.0, commit 892386191be232022b124cc59ad2c1e47e3d5dcf, BSD-3-Clause;
  C++ from lorenwel/linefit_ground_segmentation, Himmelsbach 2010). The TOML reader of v1.1.0 has its own fallbacks that differ
  from the struct defaults (e.g. max_fit_error 0.01 -> max_error_square 1e-4 instead of 0.01), so every key is written: the values of
  GroundSegmentationParams() (cpp/linefit/ground_segmentation.h) except ``height`` (sensor height) and, when given, r_min / r_max.
  Points outside (r_min, r_max) get label 0 (non-ground).

Both expect the points in a frame whose origin is the sensor and whose z is up (Patchwork++ README; linefit README "the origin pose
should in sensor link"). ``level_frame`` gives that frame from the points in base_link: base_link's axes, origin moved to the sensor.
base_link is the vehicle body, not gravity: on a slope or with a mounting error the frame is tilted by that much.
"""
from __future__ import annotations

import os
import tempfile

import numpy as np

LINEFIT_DEFAULTS = {   # GroundSegmentationParams() of linefit v1.1.0 (ground_segmentation.h l.8-25)
    'r_min': 0.5, 'r_max': 50.0, 'n_bins': 120, 'n_segments': 360,
    'min_slope': 0.0, 'max_slope': 0.1, 'max_dist_to_line': 0.1, 'max_fit_error': 0.1,   # sqrt(max_error_square 0.01)
    'long_threshold': 1.0, 'max_long_height': 0.2, 'max_start_height': 0.2, 'line_search_angle': 0.33, 'n_threads': 8,
}


def level_frame(points_base: np.ndarray, sensor_origin_base: np.ndarray) -> np.ndarray:
    return (points_base.astype(np.float64) - np.asarray(sensor_origin_base, dtype=np.float64)).astype(np.float32)


class PatchworkPP:
    name = 'patchworkpp'

    def __init__(self, sensor_height: float, min_range: float | None = None, max_range: float | None = None):
        import pypatchworkpp
        p = pypatchworkpp.Parameters()
        p.sensor_height = float(sensor_height)
        if min_range is not None:
            p.min_range = float(min_range)
        if max_range is not None:
            p.max_range = float(max_range)
        p.enable_RNR = False
        p.verbose = False
        self.settings = {'sensor_height': p.sensor_height, 'min_range': p.min_range, 'max_range': p.max_range,
                         'enable_RNR': False, 'other': 'C++ defaults (Params())'}
        self.pw = pypatchworkpp.patchworkpp(p)

    def ground_mask(self, pts_level: np.ndarray) -> np.ndarray:
        m = np.zeros(len(pts_level), dtype=bool)
        if len(pts_level) == 0:
            return m
        self.pw.estimateGround(np.ascontiguousarray(pts_level[:, :3], dtype=np.float32))
        gi = np.asarray(self.pw.getGroundIndices(), dtype=np.int64).ravel()
        m[gi] = True
        return m

    def height(self) -> float:
        return float(self.pw.getHeight())


class Linefit:
    name = 'linefit'

    def __init__(self, sensor_height: float, r_min: float | None = None, r_max: float | None = None, workdir: str | None = None):
        import linefit
        v = dict(LINEFIT_DEFAULTS)
        if r_min is not None:
            v['r_min'] = float(r_min)
        if r_max is not None:
            v['r_max'] = float(r_max)
        v['height'] = float(sensor_height)
        self.settings = dict(v)
        toml = ('[important]\nheight = {height}\n[segments]\nr_min = {r_min}\nr_max = {r_max}\nn_segments = {n_segments}\n'
                'n_bins = {n_bins}\n[ground]\nmin_slope = {min_slope}\nmax_slope = {max_slope}\nlong_threshold = {long_threshold}\n'
                'max_long_height = {max_long_height}\nmax_start_height = {max_start_height}\nmax_fit_error = {max_fit_error}\n'
                'max_dist_to_line = {max_dist_to_line}\nline_search_angle = {line_search_angle}\n[general]\n'
                'n_threads = {n_threads}\nverbose = false\n').format(**{k: (float(x) if isinstance(x, float) else x) for k, x in v.items()})
        d = workdir or tempfile.mkdtemp(prefix='linefit_')
        self.toml_path = os.path.join(d, 'linefit.toml')
        with open(self.toml_path, 'w') as f:
            f.write(toml)
        self.gs = linefit.ground_seg(self.toml_path)

    def ground_mask(self, pts_level: np.ndarray) -> np.ndarray:
        if len(pts_level) == 0:
            return np.zeros(0, dtype=bool)
        return np.asarray(self.gs.run(np.ascontiguousarray(pts_level[:, :3], dtype=np.float64)), dtype=bool).ravel()
