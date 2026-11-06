"""Synthetic comparison (ground truth known): band only vs Patchwork++ + band vs linefit + band.

usage: python -I run_synth.py <out_dir> [--frames 8] [--warmup 4] [--quick]

Conditions (every value that is not from a source is a comparison assumption, 比較用の仮定, and not a design value):
- band: PRM-70 -0.065 m, PRM-71 1.085 m (design/generated/params/gouda_nav2.yaml), range_max 6.0 m = 2 x max(obstacle_max_range 2.5,
  raytrace_max_range 3.0) of the Nav2 1.3.13 template (nav2_config.scan_range_max), angle -pi..pi, increment pi/180 (package default).
- base_link 0.165 m above the ground: base_link -> base_footprint z -0.165 in /tf_static of the 2026-11-07 record (PRM-05 is open).
- XT-32: base_link -> xt32_link from the same /tf_static (-0.07, 0.14, 1.015, yaw 100 deg); 1.18 m above the ground. Range noise
  sigma 0.02 m and no angle noise: 比較用の仮定 (the XT-32 values are not known; 0.02 m is the MID-360's published value).
- MID-360: at x 0.55 m (front edge of the footprint PRM-69), y 0, 0.5 m or 0.8 m above the ground (the two candidates of DEC-425),
  pitched 50 deg down (DEC-424); all 比較用の仮定 until DEC-457 is measured.
- mounting pitch error: -2, -1, 0, +1, +2 deg about base_link y (positive = nose-down toward the front), 比較用の仮定.
- slope 4.5 deg from 2.0 m ahead (比較用の仮定; the 2026-10-14 outdoor records have 4.3-4.5 deg world-fixed tilts and 5 m path pieces
  up to about 8 deg, design/research/vehicle_pc/2026-10-14_evening_maps_rosbag.txt).
- objects and curbs: synth.py (sizes are 比較用の仮定).
- the ground segmentation: ground_seg.py (defaults except the sensor height; for the MID-360 the minimum range 0.2 m, the distance
  from which the manual's note [2] says the precision holds).
Counts per frame (mean over the measured frames, after warm-up frames that let Patchwork++ adapt):
- fp_bins: scan bins whose kept (nearest) point is ground = a mark where there is no obstacle; split at 2.5 m (the template's
  obstacle_max_range: farther beams do not mark the costmap) and 6.0 m.
- fp_points: ground points that pass the band (and the segmentation).
- objects: the bins holding the object's returned points (within range_max); a bin is covered when its mark is an obstacle point
  (this object or one in front) at most OBJ_TOL beyond the object's nearest true range in that bin. marked = at least one covered bin.
  phantom bins = bins of the object whose mark is a ground point nearer than the object. edge error = nearest mark on the object itself
  - true nearest horizontal range of the object's returned points (true geometry, in the true base_link).
- obstacle points removed: obstacle points in the band that the segmentation labelled ground.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import zlib

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geometry import Transform, quat_to_mat, rpy, transform_points  # noqa: E402
from ground_seg import Linefit, PatchworkPP  # noqa: E402
from p2l import bin_of, gouda_params, in_band  # noqa: E402
from pipeline import run_methods  # noqa: E402
import synth  # noqa: E402

BAND = (-0.065, 1.085)
RANGE_MAX = 6.0
MARK_RANGE = 2.5
BASE_HEIGHT = 0.165
XT32_T = Transform(quat_to_mat(0.0, 0.0, 0.76603, 0.6428), np.array([-0.07, 0.14, 1.015]))
SLOPE = 4.5
PITCH_ERRORS = (-2.0, -1.0, 0.0, 1.0, 2.0)


def sensors():
    out = [('XT-32', synth.xt32_model(0.02), XT32_T, {'sensor_height': 1.015 + BASE_HEIGHT})]
    for h in (0.5, 0.8):
        T = Transform(rpy(0.0, math.radians(50.0), 0.0), np.array([0.55, 0.0, h - BASE_HEIGHT]))
        out.append((f'MID-360 h{h:.1f}', synth.mid360_model(), T, {'sensor_height': h, 'min_range': 0.2}))
    return out


def make_segmenters(gs, workdir):
    pw = PatchworkPP(gs['sensor_height'], min_range=gs.get('min_range'))
    lf = Linefit(gs['sensor_height'], r_min=gs.get('min_range'), workdir=workdir)
    return {'patchworkpp': pw, 'linefit': lf}


OBJ_TOL = 0.15   # a mark at most this much beyond the object's nearest true range in that bin counts as marking it (noise, depth)


def frame_metrics(res, lab, true_w, pts_base, params, n_obj):
    band = in_band(pts_base, params)
    true_r = np.hypot(true_w[:, 0], true_w[:, 1])
    meas_r = np.hypot(pts_base[:, 0].astype(np.float64), pts_base[:, 1].astype(np.float64))
    pbin = bin_of(pts_base, params)
    out = {}
    for m, d in res.items():
        r, w = d['ranges'], d['winner']
        wl = np.where(w >= 0, lab[np.maximum(w, 0)], -99)
        fin = np.isfinite(r)
        fp = fin & (wl == 0)
        kept = d['kept']
        row = {'fp_bins_2p5': int((fp & (r <= MARK_RANGE)).sum()), 'fp_bins_6': int(fp.sum()),
               'fp_points_2p5': int((band & kept & (lab == 0) & (meas_r <= MARK_RANGE)).sum()),
               'fp_points_6': int((band & kept & (lab == 0)).sum()),
               'fp_min_range': float(r[fp].min()) if fp.any() else None,
               'obstacle_points_removed': int((band & ~kept & (lab > 0)).sum()),
               'obstacle_points_in_band': int((band & (lab > 0)).sum()),
               'seconds': d['seconds'], 'objects': {}}
        for k in range(1, n_obj + 1):
            ok = (lab == k) & (meas_r <= params.range_max) & (pbin >= 0)
            if not ok.any():
                row['objects'][k] = {'visible': 0}
                continue
            bins = np.unique(pbin[ok])
            t_kb = np.array([true_r[ok & (pbin == b)].min() for b in bins])
            covered = fin[bins] & (r[bins] <= t_kb + OBJ_TOL) & (wl[bins] > 0)
            phantom = fin[bins] & (r[bins] < t_kb - OBJ_TOL) & (wl[bins] == 0)
            own = fin & (wl == k)
            e = {'visible': int(ok.sum()), 'in_band': int((ok & band).sum()), 'removed': int((ok & band & ~kept).sum()),
                 'bins': int(len(bins)), 'covered_bins': int(covered.sum()), 'phantom_bins': int(phantom.sum()),
                 'true_edge': float(true_r[ok].min())}
            if own.any():
                e['edge_error'] = float(r[own].min()) - e['true_edge']
            row['objects'][k] = e
        out[m] = row
    return out


def run(out_dir, frames, warmup, quick=False):
    os.makedirs(out_dir, exist_ok=True)
    params = gouda_params(BAND[0], BAND[1], RANGE_MAX)
    rows = []
    sc_all = synth.scenes(BASE_HEIGHT, SLOPE)
    errs = PITCH_ERRORS
    if quick:
        sc_all = [s for s in sc_all if s.name in ('flat', 'objects')]; errs = (0.0, 2.0)
    examples = {}
    for sname, model, T_nom, gs in sensors():
        for scene in sc_all:
            for err in errs:
                T_true = synth.with_pitch_error(T_nom, err)
                segs = make_segmenters(gs, out_dir)
                rng = np.random.default_rng(zlib.crc32(f'{sname}|{scene.name}|{err:+.1f}'.encode()))   # the same draws on every run
                acc = []
                for f in range(warmup + frames):
                    pts_s, lab, true_w = synth.scan(scene, model, T_true, f, rng)
                    pts_b = transform_points(T_nom, pts_s)          # the pipeline only knows the nominal mounting
                    res = run_methods(pts_b, T_nom.t, params, segs)
                    if f >= warmup:
                        acc.append(frame_metrics(res, lab, true_w, pts_b, params, len(scene.objects)))
                    if f == warmup + frames - 1 and ((scene.name.startswith('up') and err == 2.0) or (scene.name == 'objects' and err == 0.0)
                                                       or (scene.name == 'curb10' and err == 0.0)):
                        examples[(sname, scene.name, err)] = (pts_b, lab, {m: {k: v for k, v in d.items()} for m, d in res.items()})
                for m in acc[0]:
                    agg = {'sensor': sname, 'scene': scene.name, 'pitch_error_deg': err, 'method': m, 'frames': len(acc)}
                    for key in ('fp_bins_2p5', 'fp_bins_6', 'fp_points_2p5', 'fp_points_6', 'obstacle_points_removed',
                                'obstacle_points_in_band', 'seconds'):
                        agg[key] = float(np.mean([a[m][key] for a in acc]))
                    mins = [a[m]['fp_min_range'] for a in acc if a[m]['fp_min_range'] is not None]
                    agg['fp_min_range_median'] = float(np.median(mins)) if mins else None
                    agg['fp_frames'] = len(mins)
                    objs = {}
                    for k, ob in enumerate(scene.objects, start=1):
                        v = [a[m]['objects'][k] for a in acc]
                        vis = [x for x in v if x['visible'] > 0]
                        if not vis:
                            objs[ob.name] = {'visible_frames': 0}
                            continue
                        marked = [x for x in vis if x['covered_bins'] > 0]
                        errs_e = [x['edge_error'] for x in vis if 'edge_error' in x]
                        objs[ob.name] = {'visible_frames': len(vis), 'marked_frames': len(marked),
                                         'covered_bin_share': float(np.mean([x['covered_bins'] / x['bins'] for x in vis])),
                                         'phantom_bins': float(np.mean([x['phantom_bins'] for x in vis])),
                                         'in_band_points': float(np.mean([x['in_band'] for x in vis])),
                                         'removed_points': float(np.mean([x['removed'] for x in vis])),
                                         'true_edge_m': float(np.median([x['true_edge'] for x in vis])),
                                         'edge_error_median_m': float(np.median(errs_e)) if errs_e else None,
                                         'edge_error_max_abs_m': float(np.max(np.abs(errs_e))) if errs_e else None}
                    agg['objects'] = objs
                    rows.append(agg)
                print(f'{time.strftime("%H:%M:%S")} {sname} {scene.name} {err:+.0f}: ' + ', '.join(
                    f'{r["method"]} fp2.5={r["fp_bins_2p5"]:.1f} fp6={r["fp_bins_6"]:.1f}' for r in rows[-3:]), flush=True)
    with open(os.path.join(out_dir, 'synth_results.json'), 'w') as f:
        json.dump(rows, f, indent=1)
    np.savez_compressed(os.path.join(out_dir, 'synth_examples.npz'), **{
        f'{s}__{sc}__{e:+.0f}__{part}': arr for (s, sc, e), (pts, lab, res) in examples.items()
        for part, arr in [('pts', pts), ('lab', lab)] + [(f'{m}_kept', d['kept']) for m, d in res.items()]
        + [(f'{m}_ranges', d['ranges']) for m, d in res.items()] + [(f'{m}_winner', d['winner']) for m, d in res.items()]})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out_dir')
    ap.add_argument('--frames', type=int, default=8)
    ap.add_argument('--warmup', type=int, default=4)
    ap.add_argument('--quick', action='store_true')
    a = ap.parse_args()
    run(a.out_dir, a.frames, a.warmup, a.quick)


if __name__ == '__main__':
    main()
