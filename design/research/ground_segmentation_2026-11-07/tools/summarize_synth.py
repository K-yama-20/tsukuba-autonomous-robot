"""Tables (markdown) and figures from run_synth.py's synth_results.json / synth_examples.npz.

usage: python -I summarize_synth.py <out_dir_of_run_synth> <figures_dir>
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pipeline import COLORS, LABELS  # noqa: E402
from run_synth import BAND, MARK_RANGE, PITCH_ERRORS, RANGE_MAX  # noqa: E402

METHODS = ('band', 'patchworkpp', 'linefit')
SHORT = {'band': '帯だけ', 'patchworkpp': 'Patchwork++＋帯', 'linefit': 'linefit＋帯'}


def load(d):
    rows = json.load(open(os.path.join(d, 'synth_results.json')))
    g = defaultdict(dict)
    for r in rows:
        g[(r['sensor'], r['scene'], r['pitch_error_deg'])][r['method']] = r
    return rows, g


def sensors_of(rows):
    out = []
    for r in rows:
        if r['sensor'] not in out:
            out.append(r['sensor'])
    return out


def table_fp(rows, g, scenes):
    L = ['| センサー | 場面 | 方式 | ' + ' | '.join(f'{e:+.0f}°' for e in PITCH_ERRORS) + ' |',
         '|---|---|---|' + '---|' * len(PITCH_ERRORS)]
    for s in sensors_of(rows):
        for sc in scenes:
            for m in METHODS:
                cells = []
                for e in PITCH_ERRORS:
                    r = g[(s, sc, e)][m]
                    cells.append(f'{r["fp_bins_2p5"]:.1f} / {r["fp_bins_6"]:.1f}')
                L.append(f'| {s} | {sc} | {SHORT[m]} | ' + ' | '.join(cells) + ' |')
    return '\n'.join(L)


def table_objects(rows, g, scene, errs=(-2.0, 0.0, 2.0)):
    L = ['| センサー | 方式 | 誤差 | 全部の枚で印になった物 / 写った物 | 印にならない枚があった物（印になった枚 / 写った枚） | 前の地面の印に隠れた物（1 枚あたりの方位） | 縁の距離の誤差（物ごとの中央値の最小〜最大） | 帯の中の障害物の点のうち地面にされた割合 |',
         '|---|---|---|---|---|---|---|---|']
    for s in sensors_of(rows):
        for m in METHODS:
            for e in errs:
                r = g[(s, scene, e)][m]
                vis = {k: v for k, v in r['objects'].items() if v.get('visible_frames', 0) > 0}
                full = [k for k, v in vis.items() if v['marked_frames'] == v['visible_frames']]
                part = [f'{k}（{v["marked_frames"]}/{v["visible_frames"]}）' for k, v in vis.items() if v['marked_frames'] < v['visible_frames']]
                hidden = [f'{k}（{v["phantom_bins"]:.1f}）' for k, v in vis.items() if v['phantom_bins'] >= 0.5]
                ee = [v['edge_error_median_m'] for v in vis.values() if v.get('edge_error_median_m') is not None]
                er = f'{min(ee):+.2f}〜{max(ee):+.2f} m' if ee else '—'
                rem = r['obstacle_points_removed'] / r['obstacle_points_in_band'] if r['obstacle_points_in_band'] else 0
                L.append(f'| {s} | {SHORT[m]} | {e:+.0f}° | {len(full)}/{len(vis)} | {"、".join(part) or "なし"} | '
                         f'{"、".join(hidden) or "なし"} | {er} | {rem * 100:.0f} % |')
    return '\n'.join(L)


def table_curbs(rows, g, heights=(8, 10, 12, 15)):
    L = ['| センサー | 方式 | 物 | ' + ' | '.join(f'{h} cm' for h in heights) + ' |', '|---|---|---|' + '---|' * len(heights)]
    for s in sensors_of(rows):
        for m in METHODS:
            for which, label in (('curb', '前の縁石'), ('step', '左の段差')):
                cells = []
                for h in heights:
                    parts = []
                    for e in (-2.0, 0.0, 2.0):
                        r = g[(s, f'curb{h:02d}', e)][m]
                        v = [x for k, x in r['objects'].items() if k.startswith(which)][0]
                        parts.append('—' if v.get('visible_frames', 0) == 0 else f'{v["marked_frames"]}')
                    cells.append(' / '.join(parts))
                L.append(f'| {s} | {SHORT[m]} | {label} | ' + ' | '.join(cells) + ' |')
    return '\n'.join(L)


def table_time(rows):
    L = ['| センサー | 方式 | 地面分割の 1 枚あたりの時間（条件ごとの平均の最小〜最大、ms） |', '|---|---|---|']
    for s in sensors_of(rows):
        for m in ('patchworkpp', 'linefit'):
            v = [r['seconds'] * 1e3 for r in rows if r['sensor'] == s and r['method'] == m]
            L.append(f'| {s} | {SHORT[m]} | {min(v):.1f}〜{max(v):.1f} |')
    return '\n'.join(L)


def fig_fp(rows, g, figdir):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    S = sensors_of(rows); scenes = [sc for sc in ('flat', 'up4.5', 'down4.5')]
    fig, axs = plt.subplots(len(S), len(scenes), figsize=(12, 3.0 * len(S)), sharex=True, sharey=True)
    for i, s in enumerate(S):
        for j, sc in enumerate(scenes):
            ax = axs[i, j]
            for m in METHODS:
                y6 = [g[(s, sc, e)][m]['fp_bins_6'] for e in PITCH_ERRORS]
                y25 = [g[(s, sc, e)][m]['fp_bins_2p5'] for e in PITCH_ERRORS]
                ax.plot(PITCH_ERRORS, y6, color=COLORS[m], lw=2, marker='o', ms=5, label=f'{LABELS[m]} (within {RANGE_MAX:g} m)')
                ax.plot(PITCH_ERRORS, y25, color=COLORS[m], lw=1.2, ls='--', marker='s', ms=4, label=f'{LABELS[m]} (within {MARK_RANGE:g} m)')
            ax.set_title(f'{s}, {sc}', fontsize=9)
            ax.grid(color='#e6e5e0', lw=0.5)
            if j == 0:
                ax.set_ylabel('ground bins marked\n(mean per frame, of 360)')
            if i == len(S) - 1:
                ax.set_xlabel('pitch error [deg]')
    h, lab = axs[0, 0].get_legend_handles_labels()
    fig.legend(h, lab, loc='lower center', ncol=3, frameon=False, fontsize=8)
    fig.suptitle('Synthetic: scan bins whose mark is a ground point (no obstacle there); the pitch error and the scenes are comparison assumptions', fontsize=10)
    fig.tight_layout(rect=(0, 0.07, 1, 0.97))
    fig.savefig(os.path.join(figdir, 'synth_false_marks.png'), dpi=100); plt.close(fig)


def fig_curbs(rows, g, figdir, heights=(8, 10, 12, 15)):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    S = [s for s in sensors_of(rows) if s.startswith('MID')]
    fig, axs = plt.subplots(len(S), 2, figsize=(10, 3.0 * len(S)), sharex=True, sharey=True)
    for i, s in enumerate(S):
        for j, (which, label) in enumerate((('curb', 'curb across the way, 3.0 m ahead'), ('step', 'step along the left side'))):
            ax = axs[i, j]
            for m in METHODS:
                y = []
                for h in heights:
                    r = g[(s, f'curb{h:02d}', 0.0)][m]
                    v = [x for k, x in r['objects'].items() if k.startswith(which)][0]
                    y.append(v['marked_frames'] / max(v['visible_frames'], 1))
                ax.plot(heights, y, color=COLORS[m], lw=2, marker='o', ms=6, label=LABELS[m])
            ax.set_title(f'{s}: {label} (no pitch error)', fontsize=9)
            ax.set_ylim(-0.05, 1.05); ax.grid(color='#e6e5e0', lw=0.5)
            if j == 0:
                ax.set_ylabel('share of frames\nwith a mark on it')
            if i == len(S) - 1:
                ax.set_xlabel('height [cm] (band floor = 10.0 cm above this ground)')
    axs[0, 0].legend(frameon=False, fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(figdir, 'synth_curbs.png'), dpi=100); plt.close(fig)


def fig_example(d, figdir, key='MID-360 h0.5__up4.5__+2'):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    z = np.load(os.path.join(d, 'synth_examples.npz'))
    pts = z[f'{key}__pts']; lab = z[f'{key}__lab']
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from p2l import bin_angles, gouda_params, in_band
    params = gouda_params(BAND[0], BAND[1], RANGE_MAX); ang = bin_angles(params)
    band = in_band(pts, params)
    fig, axs = plt.subplots(2, 3, figsize=(16, 9.5), gridspec_kw={'height_ratios': [1.5, 1]})
    for j, m in enumerate(METHODS):
        kept = z[f'{key}__{m}_kept']; r = z[f'{key}__{m}_ranges']; w = z[f'{key}__{m}_winner']
        ax = axs[0, j]
        g = ~kept
        ax.scatter(pts[g, 0], pts[g, 1], s=0.3, color='#c3c2b7', label='removed as ground', rasterized=True)
        ax.scatter(pts[kept & ~band, 0], pts[kept & ~band, 1], s=0.3, color='#e6e5e0', rasterized=True)
        okb = kept & band
        ax.scatter(pts[okb & (lab == 0), 0], pts[okb & (lab == 0), 1], s=3, color='#e34948', label='ground point in the band (true label)')
        ax.scatter(pts[okb & (lab > 0), 0], pts[okb & (lab > 0), 1], s=3, color='#0b0b0b', label='obstacle point in the band')
        f = np.isfinite(r)
        ax.scatter(r[f] * np.cos(ang[f]), r[f] * np.sin(ang[f]), s=14, facecolors='none', edgecolors=COLORS[m], lw=1, label='scan mark')
        ax.set_xlim(-1, RANGE_MAX); ax.set_ylim(-3.5, 3.5); ax.set_aspect('equal'); ax.grid(color='#e6e5e0', lw=0.5)
        ax.set_title(f'{LABELS[m]}', fontsize=9); ax.set_xlabel('x forward [m]'); ax.set_ylabel('y left [m]')
        ax.legend(loc='lower left', fontsize=7, markerscale=2)
        ax = axs[1, j]
        sel = np.abs(pts[:, 1]) < 1.0
        ax.scatter(pts[sel & (lab == 0), 0], pts[sel & (lab == 0), 2], s=0.5, color='#c3c2b7', rasterized=True)
        ax.scatter(pts[sel & (lab > 0), 0], pts[sel & (lab > 0), 2], s=1, color='#0b0b0b', rasterized=True)
        ax.scatter(pts[sel & okb & (lab == 0), 0], pts[sel & okb & (lab == 0), 2], s=3, color='#e34948')
        for zb in BAND:
            ax.axhline(zb, color='#52514e', lw=0.8, ls='--')
        ax.set_xlim(-1, RANGE_MAX); ax.set_ylim(-0.4, 0.9); ax.grid(color='#e6e5e0', lw=0.5)
        ax.set_xlabel('x forward [m] (|y| < 1 m)'); ax.set_ylabel('z in base_link [m]')
    fig.suptitle(f'Synthetic frame {key.replace("__", ", ")} deg: MID-360 0.5 m, 50 deg down, slope 4.5 deg from 2 m, mounting 2 deg more nose-down than assumed'
                 ' (all comparison assumptions)', fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(figdir, 'synth_example_mid360_up_slope.png'), dpi=95); plt.close(fig)


def main():
    d, figdir = sys.argv[1], sys.argv[2]
    os.makedirs(figdir, exist_ok=True)
    rows, g = load(d)
    out = ['## false marks (bins within 2.5 m / within 6 m, mean per frame)', table_fp(rows, g, ('flat', 'up4.5', 'down4.5')),
           '## objects (flat)', table_objects(rows, g, 'objects'), '## objects on the slope', table_objects(rows, g, 'objects_up4.5'),
           '## curbs (frames with a mark / 20, pitch error -2 / 0 / +2)', table_curbs(rows, g), '## time', table_time(rows)]
    open(os.path.join(d, 'synth_tables.md'), 'w').write('\n\n'.join(out) + '\n')
    fig_fp(rows, g, figdir); fig_curbs(rows, g, figdir); fig_example(d, figdir)
    print('\n\n'.join(out))


if __name__ == '__main__':
    main()
