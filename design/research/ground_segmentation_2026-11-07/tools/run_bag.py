"""Recorded data (no ground truth): where band only and <segmenter> + band disagree.

usage: python -I run_bag.py <cut.mcap> <out_dir> <name> [--topic /sensors/xt32/points] [--tf-bag other.mcap] [--t-origin-ns N]
                            [--min-range M] [--traj traj_lidar.txt] [--every K]

- The cloud's frame comes from its header; base_link <- sensor and base_link <- base_footprint come from /tf_static of the bag
  (or of --tf-bag when the bag has none). The sensor height for the segmentation = z of the sensor in base_footprint.
- The band, range_max and the segmentation settings are those of run_synth.py (BAND, RANGE_MAX; ground_seg defaults except the
  sensor height and, for --min-range, Patchwork++ min_range and linefit r_min).
- A bin disagrees when band only has a mark there and the segmented scan has none or one more than TOL farther.
  Counted within 2.5 m (MARK_RANGE: the template's obstacle_max_range, where marks enter the costmap) and within 6.0 m.
- For each disagreeing bin, the height of the band's mark above the lowest points nearby (5th percentile of z of all points in the
  same bin and the two next to it, within +-1.0 m of the mark's range; independent of the segmenters) is kept, as a rough hint whether
  the mark is ground-like or a low object. It is not a ground truth: a human has to look at the figures.
- Writes <out_dir>/<name>_frames.json (per frame counts), <name>_summary.json and the figures <name>_*.png (aggregated top views,
  time series, one example frame). Raw points are not written.
For a MID-360 bag: --topic /sensors/mid360/points (IFD-59) and --min-range 0.2; the TF must be in /tf_static (mid360_link).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geometry import lookup, tf_tree, transform_points  # noqa: E402
from ground_seg import Linefit, PatchworkPP  # noqa: E402
from p2l import bin_angles, bin_of, gouda_params, in_band  # noqa: E402
from pipeline import COLORS, LABELS, run_methods  # noqa: E402
from run_synth import BAND, MARK_RANGE, RANGE_MAX  # noqa: E402

TOL = 0.10
DT = {1: 'i1', 2: 'u1', 3: 'i2', 4: 'u2', 5: 'i4', 6: 'u4', 7: 'f4', 8: 'f8'}


def read_msgs(path, topics):
    from mcap.reader import NonSeekingReader
    from mcap_ros2.decoder import DecoderFactory
    with open(path, 'rb') as f:
        for _s, ch, m, msg in NonSeekingReader(f, decoder_factories=[DecoderFactory()]).iter_decoded_messages(topics=topics):
            yield ch.topic, m.log_time, msg


def cloud_xyz(msg):
    fields = {f.name: (f.offset, f.datatype) for f in msg.fields}
    n = msg.width * msg.height
    raw = np.frombuffer(bytes(msg.data), dtype=np.uint8).reshape(n, msg.point_step)
    out = []
    for k in 'xyz':
        off, dt = fields[k]
        sz = np.dtype(DT[dt]).itemsize
        out.append(raw[:, off:off + sz].copy().view('<' + DT[dt]).ravel().astype(np.float32))
    p = np.c_[out[0], out[1], out[2]]
    ok = np.isfinite(p).all(axis=1) & ~((p[:, 0] == 0) & (p[:, 1] == 0) & (p[:, 2] == 0))   # no return = (0, 0, 0)
    return p[ok]


def static_tree(path):
    tr = []
    for _t, _lt, msg in read_msgs(path, ['/tf_static']):
        tr.extend(msg.transforms)
    return tf_tree(tr)


def disagreement(res, name, params):
    rb = res['band']['ranges']; rg = res[name]['ranges']
    d = np.isfinite(rb) & (~np.isfinite(rg) | (rg > rb + TOL))
    return d


def local_low(pts_base, bins_pts, b, r_mark, nb):
    sel = np.isin(bins_pts, [(b - 1) % nb, b, (b + 1) % nb])
    rr = np.hypot(pts_base[sel, 0], pts_base[sel, 1])
    near = np.abs(rr - r_mark) <= 1.0
    if near.sum() < 5:
        return None
    return float(np.percentile(pts_base[sel][near, 2], 5))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('bag'); ap.add_argument('out_dir'); ap.add_argument('name')
    ap.add_argument('--topic', default='/sensors/xt32/points')
    ap.add_argument('--target', default='base_link'); ap.add_argument('--footprint', default='base_footprint')
    ap.add_argument('--tf-bag'); ap.add_argument('--t-origin-ns', type=int)
    ap.add_argument('--min-range', type=float); ap.add_argument('--traj'); ap.add_argument('--every', type=int, default=1)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    tree = static_tree(a.bag)
    tf_source = 'the bag'
    if not tree:
        if not a.tf_bag:
            raise SystemExit('the bag has no /tf_static: give --tf-bag')
        tree = static_tree(a.tf_bag); tf_source = f'--tf-bag ({os.path.basename(a.tf_bag)})'
    params = gouda_params(BAND[0], BAND[1], RANGE_MAX)
    ang = bin_angles(params)
    frames = []; heat = {}; ex = None; hgt = {}
    segs = None; T = None
    edges = np.linspace(-RANGE_MAX, RANGE_MAX, 121)
    for i, (_tp, lt, msg) in enumerate(read_msgs(a.bag, [a.topic])):
        if i % a.every:
            continue
        if T is None:
            frame = msg.header.frame_id
            T = lookup(tree, a.target, frame)
            Tf = lookup(tree, a.footprint, frame)
            h = float(Tf.t[2])
            segs = {'patchworkpp': PatchworkPP(h, min_range=a.min_range), 'linefit': Linefit(h, r_min=a.min_range, workdir=a.out_dir)}
            meta = {'sensor_frame': frame, 'tf_source': tf_source, 'T_base_sensor_t': T.t.tolist(),
                    'T_base_sensor_R': T.R.tolist(), 'sensor_height_m': h,
                    'settings': {k: v.settings for k, v in segs.items()}, 'band': BAND, 'range_max': RANGE_MAX, 'tol': TOL}
        pts = transform_points(T, cloud_xyz(msg))
        res = run_methods(pts, T.t, params, segs)
        band = in_band(pts, params)
        pb = bin_of(pts, params)
        t_rel = (lt - a.t_origin_ns) * 1e-9 if a.t_origin_ns else lt * 1e-9
        row = {'t': t_rel, 'points': int(len(pts)), 'in_band': int(band.sum())}
        for m in res:
            r = res[m]['ranges']
            row[f'{m}_bins_2p5'] = int((np.isfinite(r) & (r <= MARK_RANGE)).sum())
            row[f'{m}_bins_6'] = int(np.isfinite(r).sum())
            if m == 'band':
                continue
            d = disagreement(res, m, params)
            rb = res['band']['ranges']
            row[f'{m}_diff_2p5'] = int((d & (rb <= MARK_RANGE)).sum())
            row[f'{m}_diff_6'] = int(d.sum())
            row[f'{m}_removed_in_band'] = int((band & res[m]['ground']).sum())
            row[f'{m}_seconds'] = res[m]['seconds']
            if m == 'patchworkpp':
                row['patchworkpp_height'] = segs[m].height()
            bi = np.nonzero(d)[0]
            x = rb[bi] * np.cos(ang[bi]); y = rb[bi] * np.sin(ang[bi])
            H, _, _ = np.histogram2d(x, y, bins=[edges, edges])
            heat[m] = heat.get(m, 0) + H
            for b in bi:
                w = res['band']['winner'][b]
                g = local_low(pts, pb, b, float(rb[b]), len(rb))
                if g is not None:
                    hgt.setdefault(m, []).append((float(rb[b]), float(pts[w, 2]) - g, float(pts[w, 0]), float(pts[w, 1])))
        bi_all = np.isfinite(res['band']['ranges'])
        H, _, _ = np.histogram2d(res['band']['ranges'][bi_all] * np.cos(ang[bi_all]), res['band']['ranges'][bi_all] * np.sin(ang[bi_all]),
                                 bins=[edges, edges])
        heat['band_all'] = heat.get('band_all', 0) + H
        score = row['patchworkpp_diff_6'] + row['linefit_diff_6']
        if ex is None or score > ex[0]:
            ex = (score, row['t'], pts.copy(), {m: {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in d.items()}
                                                 for m, d in res.items()})
        frames.append(row)
    if not frames:
        raise SystemExit('no clouds on ' + a.topic)
    summ = {'meta': meta, 'frames': len(frames), 't0': frames[0]['t'], 't1': frames[-1]['t']}
    for m in ('patchworkpp', 'linefit'):
        for k in ('diff_2p5', 'diff_6', 'removed_in_band'):
            v = np.array([f[f'{m}_{k}'] for f in frames])
            summ[f'{m}_{k}'] = {'mean': float(v.mean()), 'median': float(np.median(v)), 'p95': float(np.percentile(v, 95)),
                                'max': int(v.max()), 'frames_with_any': int((v > 0).sum())}
        s = np.array([f[f'{m}_seconds'] for f in frames])
        summ[f'{m}_seconds'] = {'median': float(np.median(s)), 'p95': float(np.percentile(s, 95)), 'max': float(s.max())}
        hh = np.array(hgt.get(m, []))
        if len(hh):
            summ[f'{m}_mark_height_above_lowest_nearby'] = {
                'n': int(len(hh)), 'quantiles_m': {q: float(np.percentile(hh[:, 1], q)) for q in (5, 25, 50, 75, 95)},
                'share_below_0.15m': float((hh[:, 1] < 0.15).mean()), 'share_0.15_0.30m': float(((hh[:, 1] >= 0.15) & (hh[:, 1] < 0.30)).mean()),
                'share_above_0.30m': float((hh[:, 1] >= 0.30).mean()),
                'range_quantiles_m': {q: float(np.percentile(hh[:, 0], q)) for q in (5, 50, 95)}}
    for m in ('band', 'patchworkpp', 'linefit'):
        v = np.array([f[f'{m}_bins_2p5'] for f in frames]); w = np.array([f[f'{m}_bins_6'] for f in frames])
        summ[f'{m}_marked_bins'] = {'2p5_mean': float(v.mean()), '6_mean': float(w.mean())}
    summ['patchworkpp_height'] = {'first': frames[0]['patchworkpp_height'], 'last': frames[-1]['patchworkpp_height'],
                                  'median': float(np.median([f['patchworkpp_height'] for f in frames]))}
    with open(os.path.join(a.out_dir, f'{a.name}_frames.json'), 'w') as f:
        json.dump(frames, f)
    with open(os.path.join(a.out_dir, f'{a.name}_summary.json'), 'w') as f:
        json.dump(summ, f, indent=1)
    traj = None
    if a.traj and a.t_origin_ns:
        traj = load_slope(a.traj, a.t_origin_ns)
    figures(a.out_dir, a.name, frames, heat, edges, ex, ang, params, hgt, traj)
    print(json.dumps(summ, indent=1))


def load_slope(path, t_origin_ns):
    d = np.loadtxt(path)
    t = d[:, 0] - t_origin_ns * 1e-9
    p = d[:, 1:4]
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(p[:, :2], axis=0), axis=1))]
    sl = np.full(len(t), np.nan)
    for i in range(len(t)):
        a = np.searchsorted(s, s[i] - 2.5); b = np.searchsorted(s, s[i] + 2.5) - 1
        if b > a and s[b] - s[a] > 3:
            sl[i] = np.degrees(np.arctan2(p[b, 2] - p[a, 2], s[b] - s[a]))
    return t, sl


FOOT = np.array([[0.55, 0.30], [0.55, -0.30], [-0.24, -0.30], [-0.24, 0.30], [0.55, 0.30]])   # PRM-69


def _top_axes(ax, lim=RANGE_MAX):
    ax.plot(FOOT[:, 0], FOOT[:, 1], color='#0b0b0b', lw=1)
    for rr in (MARK_RANGE, RANGE_MAX):
        th = np.linspace(0, 2 * np.pi, 200)
        ax.plot(rr * np.cos(th), rr * np.sin(th), color='#9a9890', lw=0.8, ls='--')
    ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim); ax.set_aspect('equal')
    ax.set_xlabel('x forward [m] (base_link)'); ax.set_ylabel('y left [m]')
    ax.grid(color='#e6e5e0', lw=0.5)


def figures(out, name, frames, heat, edges, ex, ang, params, hgt, traj):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    t = np.array([f['t'] for f in frames])
    # 1. time series
    nrow = 3 if traj is not None else 2
    fig, axs = plt.subplots(nrow, 1, figsize=(9, 2.6 * nrow), sharex=True)
    for ax, k, title in ((axs[0], '2p5', f'within {MARK_RANGE} m'), (axs[1], '6', f'within {RANGE_MAX} m')):
        for m in ('patchworkpp', 'linefit'):
            ax.plot(t, [f[f'{m}_diff_{k}'] for f in frames], color=COLORS[m], lw=1.5, label=LABELS[m])
        ax.set_ylabel(f'bins marked only\nby band ({title})')
        ax.grid(color='#e6e5e0', lw=0.5)
    if traj is not None:      # its own panel (one quantity per axis)
        k = (traj[0] >= t.min()) & (traj[0] <= t.max())
        axs[2].plot(traj[0][k], traj[1][k], color='#52514e', lw=1.5)
        axs[2].axhline(0, color='#9a9890', lw=0.8)
        axs[2].set_ylabel('path slope [deg]\n(GLIM, over 5 m)'); axs[2].grid(color='#e6e5e0', lw=0.5)
    axs[0].legend(loc='upper right', frameon=False)
    axs[-1].set_xlabel('time in the record [s]')
    fig.suptitle(f'{name}: scan bins where band only marks and the segmented scan does not (per frame)', fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(out, f'{name}_timeseries.png'), dpi=110); plt.close(fig)
    # 2. aggregated top views
    fig, axs = plt.subplots(1, 3, figsize=(15, 5.2))
    for ax, m, title in ((axs[0], 'band_all', 'all band-only marks'), (axs[1], 'patchworkpp', 'band only, not Patchwork++ + band'),
                         (axs[2], 'linefit', 'band only, not linefit + band')):
        H = heat.get(m)
        if H is None:
            continue
        Hm = np.ma.masked_equal(H.T, 0)
        im = ax.pcolormesh(edges, edges, Hm, cmap='Blues' if m == 'band_all' else 'Oranges', shading='flat')
        _top_axes(ax)
        ax.set_title(f'{title}\n(count of frames x bins, 0.1 m cells, {len(frames)} frames)', fontsize=9)
        fig.colorbar(im, ax=ax, shrink=0.75)
    fig.tight_layout(); fig.savefig(os.path.join(out, f'{name}_topview_heat.png'), dpi=110); plt.close(fig)
    # 3. example frame
    if ex is not None:
        _, tex, pts, res = ex
        band = in_band(pts, params)
        fig, axs = plt.subplots(2, 2, figsize=(14, 12), gridspec_kw={'height_ratios': [1.6, 1]})
        for j, m in enumerate(('patchworkpp', 'linefit')):
            ax = axs[0, j]
            g = res[m]['ground']
            rh = np.hypot(pts[:, 0], pts[:, 1])
            near = rh <= RANGE_MAX + 0.5
            rb = res['band']['ranges']; rg = res[m]['ranges']
            d = np.isfinite(rb) & (~np.isfinite(rg) | (rg > rb + TOL))
            cats = ((near & g, '#c3c2b7', 0.3, 'ground (by the segmenter)'), (near & ~g & ~band, '#e6e5e0', 0.3, None),
                    (band & ~g, '#0b0b0b', 1.5, 'in the band, kept'), (band & g, COLORS[m], 4, 'in the band, removed as ground'))
            for k, c, sz, lab in cats:
                ax.scatter(pts[k, 0], pts[k, 1], s=sz, color=c, label=lab, rasterized=True)
            ax.scatter(rb[d] * np.cos(ang[d]), rb[d] * np.sin(ang[d]), s=26, facecolors='none', edgecolors=COLORS['band'], lw=1.2,
                       label='band-only mark that disappears')
            _top_axes(ax)
            ax.set_title(f'{LABELS[m]}: frame at {tex:.1f} s (most disagreement in the window), from above', fontsize=9)
            ax.legend(loc='lower left', fontsize=7, markerscale=3, frameon=True)
            ax = axs[1, j]      # the same points: horizontal range vs height
            for k, c, sz, lab in cats:
                ax.scatter(rh[k], pts[k, 2], s=sz, color=c, rasterized=True)
            wv = res['band']['winner'][d]
            ax.scatter(rh[wv], pts[wv, 2], s=26, facecolors='none', edgecolors=COLORS['band'], lw=1.2)
            for zb in BAND:
                ax.axhline(zb, color='#52514e', lw=0.8, ls='--')
            ax.axvline(MARK_RANGE, color='#9a9890', lw=0.8, ls='--')
            ax.set_xlim(0, RANGE_MAX + 0.5); ax.set_ylim(-0.6, 1.4)
            ax.set_xlabel('horizontal range from base_link [m]'); ax.set_ylabel('z in base_link [m] (dashed: the band)')
            ax.grid(color='#e6e5e0', lw=0.5)
        fig.tight_layout(); fig.savefig(os.path.join(out, f'{name}_example_frame.png'), dpi=100); plt.close(fig)
    # 4. heights of the disappearing marks above the local ground
    fig, ax = plt.subplots(figsize=(7, 3.6))
    bins = np.linspace(-0.1, 1.2, 53)
    for m in ('patchworkpp', 'linefit'):
        hh = np.array(hgt.get(m, []))
        if len(hh):
            ax.hist(hh[:, 1], bins=bins, histtype='step', lw=2, color=COLORS[m], label=f'{LABELS[m]} (n={len(hh)})')
    ax.set_xlabel("height of the disappearing mark above the lowest points nearby [m]")
    ax.set_ylabel('bins (all frames)'); ax.legend(frameon=False); ax.grid(color='#e6e5e0', lw=0.5)
    fig.tight_layout(); fig.savefig(os.path.join(out, f'{name}_mark_heights.png'), dpi=110); plt.close(fig)
    # 5. where the disappearing marks stand 0.15 m or more above the lowest points nearby (the candidates of a miss to look at)
    fig, axs = plt.subplots(1, 2, figsize=(12, 5.6))
    for ax, m in zip(axs, ('patchworkpp', 'linefit')):
        hh = np.array(hgt.get(m, []))
        _top_axes(ax)
        if len(hh):
            lo = hh[:, 1] < 0.15
            ax.scatter(hh[lo, 2], hh[lo, 3], s=2, color='#c3c2b7', label=f'< 0.15 m above the lowest points nearby (n={lo.sum()})', rasterized=True)
            ax.scatter(hh[~lo, 2], hh[~lo, 3], s=10, color=COLORS[m], label=f'>= 0.15 m (n={(~lo).sum()})')
        ax.set_title(f'band-only marks that {LABELS[m]} removes, all {len(frames)} frames', fontsize=9)
        ax.legend(loc='lower left', fontsize=7, markerscale=2)
    fig.tight_layout(); fig.savefig(os.path.join(out, f'{name}_tall_removed_marks.png'), dpi=100); plt.close(fig)


if __name__ == '__main__':
    main()
