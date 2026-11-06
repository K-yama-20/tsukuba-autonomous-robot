"""The two ways of making the obstacle scan, side by side:
- band: the points in base_link through the band (p2l.laserscan), as xt32_scan / mid360_scan do now;
- <segmenter> + band: the same, after removing the points the OSS labels as ground.
The ground segmentation sees the points in the level frame of ground_seg.level_frame (base_link axes, origin at the sensor)."""
from __future__ import annotations

import time

import numpy as np

from ground_seg import level_frame
from p2l import in_band, laserscan

COLORS = {'band': '#2a78d6', 'patchworkpp': '#eb6834', 'linefit': '#1baf7a'}   # categorical slots 1-3 (dataviz reference palette)
LABELS = {'band': 'band only', 'patchworkpp': 'Patchwork++ + band', 'linefit': 'linefit + band'}


def run_methods(pts_base: np.ndarray, sensor_origin_base, params, segmenters: dict) -> dict:
    """{method: {'ranges', 'winner' (index into pts_base or -1), 'kept' mask, 'ground' mask or None, 'seconds'}}."""
    out = {}
    r, w = laserscan(pts_base, params)
    out['band'] = {'ranges': r, 'winner': w, 'kept': np.ones(len(pts_base), dtype=bool), 'ground': None, 'seconds': 0.0}
    if segmenters:
        lvl = level_frame(pts_base, sensor_origin_base)
    for name, seg in segmenters.items():
        t0 = time.perf_counter()
        g = seg.ground_mask(lvl)
        dt = time.perf_counter() - t0
        sub = np.nonzero(~g)[0]
        r2, w2 = laserscan(pts_base[sub], params)
        w2 = np.where(w2 >= 0, sub[np.maximum(w2, 0)], -1) if len(sub) else w2
        out[name] = {'ranges': r2, 'winner': w2, 'kept': ~g, 'ground': g, 'seconds': dt}
    return out


def band_mask(pts_base, params):
    return in_band(pts_base, params)
