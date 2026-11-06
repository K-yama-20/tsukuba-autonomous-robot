"""停止距離の解析（DEC-346 (1)・DEC-377 (1)・DEC-378 (1)）: 「止める合図」から車体が止まるまでに進んだ距離を、記録から求める。
ROS は要らない（extract.py が作った CSV と、GLIM の軌跡のファイルを読む）。値は実測の候補で、人が確認するまで確定扱いにしない。

止める合図（--trigger）
  hold     control/motion_hold が false から true に変わった時（自律走行での停止: 停止点、待機ボタンなど）。hold.csv
  neutral  ESP32 が適用した前後の操作量 applied_y が 0 でない値から 0 になった時（手動操作でスティックを戻した時など）。esp32.csv
位置（--track）
  odom.csv（localization/odometry）か、GLIM の軌跡 odom_lidar.txt（TUM: t x y z qx qy qz qw）。拡張子 .csv / .txt で見分ける
時刻は既定で header.stamp（--clock stamp）。CSV だけを使うときは rosbag が受け取った時刻（--clock receive）も選べる。

合図ごとに出すもの
  v0_mps        合図の直前 pre_s 秒の平均の速さ（位置の差から。twist は使わない）
  d_along_m     合図の時の位置から、止まった位置までの、進行方向の距離（停止距離）
  d_lateral_m   同じく横の距離
  t_stop_s      合図から、位置が止まった位置の eps_m 以内に収まり続けるようになるまでの時間
  settle_max_m  窓の最後 tail_s 秒の中で、止まった位置から最も離れた距離（止まった後の揺れの目安）
判定できないものは verdict「未判定」と理由を出す（値を推測で埋めない）。

usage: python3 stop_distance.py <dir> --trigger hold|neutral --track <odom.csv | odom_lidar.txt>
                                [--clock stamp|receive] [--pre-s 0.5] [--window-s 6] [--tail-s 1] [--eps-m 0.02] [--json out.json]
"""
import argparse
import bisect
import csv
import json
import math
import statistics
from pathlib import Path


# ---- 読み込み ----
def read_csv(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def load_track(path, clock='stamp'):
    """[(t, x, y)] sorted by t, from odom.csv or a TUM file (t x y z qx qy qz qw; its t is the only clock it has)."""
    p = Path(path)
    if p.suffix == '.csv':
        key = 't' if clock == 'receive' else 'stamp'
        pts = [(float(r[key]), float(r['x']), float(r['y'])) for r in read_csv(p)]
    else:
        pts = []
        for line in p.read_text(encoding='utf-8').splitlines():
            v = line.split()
            if len(v) >= 3 and not line.lstrip().startswith('#'):
                pts.append((float(v[0]), float(v[1]), float(v[2])))
    return sorted(pts)


def hold_edges(rows, clock='stamp'):
    """(rising, falling): times when hold changed false -> true, and true -> false. Each rising is (t, reason)."""
    key = 't' if clock == 'receive' else 'stamp'
    rising, falling, prev = [], [], None
    for r in sorted(rows, key=lambda r: float(r[key])):
        h = int(r['hold'])
        if prev is not None and h != prev:
            if h:
                rising.append((float(r[key]), r.get('reason', '')))
            else:
                falling.append(float(r[key]))
        prev = h
    return rising, falling


def neutral_edges(rows, clock='stamp'):
    """(to_zero, from_zero): times when applied_y became 0 from a non-zero value, and non-zero from 0.
    Each to_zero is (t, text with the last non-zero value)."""
    key = 't' if clock == 'receive' else 'stamp'
    to_zero, from_zero, prev = [], [], None
    for r in sorted(rows, key=lambda r: float(r[key])):
        if r.get('applied_y_q10000', '') == '':
            continue
        y = int(float(r['applied_y_q10000']))
        if prev is not None:
            if prev != 0 and y == 0:
                to_zero.append((float(r[key]), f'applied_y {prev / 10000:+.3f} -> 0'))
            elif prev == 0 and y != 0:
                from_zero.append(float(r[key]))
        prev = y
    return to_zero, from_zero


# ---- 計算 ----
def position_at(track, t):
    """Linear interpolation of (x, y) at t; None outside the track."""
    ts = [p[0] for p in track]
    if not track or t < ts[0] or t > ts[-1]:
        return None
    i = bisect.bisect_left(ts, t)
    if ts[i] == t:
        return track[i][1], track[i][2]
    (t0, x0, y0), (t1, x1, y1) = track[i - 1], track[i]
    a = (t - t0) / (t1 - t0)
    return x0 + a * (x1 - x0), y0 + a * (y1 - y0)


def analyze_event(track, t, t_end_limit, pre_s, window_s, tail_s, eps_m):
    """One stop: dict with the values, or verdict 未判定 and the reason."""
    out = {'t': t, 'verdict': '未判定'}
    p0, pb = position_at(track, t), position_at(track, t - pre_s)
    if p0 is None or pb is None:
        return dict(out, reason='合図の前後の位置の記録がない')
    before = math.hypot(p0[0] - pb[0], p0[1] - pb[1])
    out['v0_mps'] = before / pre_s
    t_end = min(t + window_s, track[-1][0], t_end_limit if t_end_limit is not None else math.inf)
    out['window_s'] = t_end - t
    if t_end - t < 2 * tail_s:
        return dict(out, reason='合図の後の記録が短い（次の動き出し、または記録の終わりまでが tail_s の 2 倍より短い）')
    tail = [(x, y) for (tt, x, y) in track if t_end - tail_s <= tt <= t_end]
    if len(tail) < 3:
        return dict(out, reason='止まった位置を決める点が 3 つより少ない')
    fx, fy = statistics.median(p[0] for p in tail), statistics.median(p[1] for p in tail)
    out['settle_max_m'] = max(math.hypot(x - fx, y - fy) for x, y in tail)
    if before <= eps_m:
        return dict(out, reason='合図の直前に動いていない（進行方向を決められない）')
    ux, uy = (p0[0] - pb[0]) / before, (p0[1] - pb[1]) / before
    dx, dy = fx - p0[0], fy - p0[1]
    out['d_along_m'], out['d_lateral_m'] = dx * ux + dy * uy, -dx * uy + dy * ux
    after = [(tt, math.hypot(x - fx, y - fy)) for (tt, x, y) in track if t <= tt <= t_end]
    moving = [tt for tt, dist in after if dist > eps_m]
    if not moving:
        out['t_stop_s'] = 0.0
    else:
        later = [tt for tt, _ in after if tt > moving[-1]]
        if not later:
            return dict(out, reason='窓の終わりまで位置が収まらない')
        out['t_stop_s'] = later[0] - t
    if out['settle_max_m'] > eps_m:
        return dict(out, reason='窓の最後でも位置が eps_m より大きく動いている（止まっていない）')
    return dict(out, verdict='算出', reason='')


def analyze(track, starts, restarts, pre_s=0.5, window_s=6.0, tail_s=1.0, eps_m=0.02):
    """starts: [(t, note)] of the stop signals; restarts: times when driving was allowed again (they end a window)."""
    restarts = sorted(restarts)
    events = []
    for k, (t, note) in enumerate(sorted(starts)):
        nxt = [r for r in restarts if r > t]
        limit = min(nxt[0] if nxt else math.inf, starts[k + 1][0] if k + 1 < len(starts) else math.inf)
        e = analyze_event(track, t, None if limit == math.inf else limit, pre_s, window_s, tail_s, eps_m)
        events.append(dict(e, note=note))
    return events


def attach_decisions(events, decision_rows, clock='stamp', within_s=1.0):
    """Add the rule_stop_hold record (waypoint, distance to the stop point at the decision) to the nearest signal."""
    key = 't' if clock == 'receive' else 'stamp'
    for r in decision_rows:
        td = float(r[key])
        near = [e for e in events if abs(e['t'] - td) <= within_s]
        if near:
            d = json.loads(r.get('details') or '{}')
            min(near, key=lambda e: abs(e['t'] - td)).update(stop_waypoint=d.get('waypoint'), distance_to_stop_point_m=d.get('distance_m'))
    return events


def table(events, t0):
    def f(v, n=3):
        return '—' if v is None else f'{v:.{n}f}'
    lines = ['| 時刻 s | 直前の速さ m/s | 停止距離 m | 横 m | 止まるまで s | 止まった後の動き m | 判定 | 備考 |', '|---|---|---|---|---|---|---|---|']
    for e in events:
        lines.append(f"| {e['t'] - t0:.2f} | {f(e.get('v0_mps'))} | {f(e.get('d_along_m'))} | {f(e.get('d_lateral_m'))} | {f(e.get('t_stop_s'), 2)} | "
                     f"{f(e.get('settle_max_m'))} | {e['verdict']} | {e.get('reason') or e.get('note', '')} |")
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser(description='停止距離の解析')
    ap.add_argument('dir'); ap.add_argument('--trigger', choices=['hold', 'neutral'], required=True); ap.add_argument('--track', required=True)
    ap.add_argument('--clock', choices=['stamp', 'receive'], default='stamp')
    ap.add_argument('--pre-s', type=float, default=0.5); ap.add_argument('--window-s', type=float, default=6.0)
    ap.add_argument('--tail-s', type=float, default=1.0); ap.add_argument('--eps-m', type=float, default=0.02); ap.add_argument('--json')
    a = ap.parse_args()
    d = Path(a.dir)
    track = load_track(a.track, a.clock)
    if a.trigger == 'hold':
        starts, restarts = hold_edges(read_csv(d / 'hold.csv'), a.clock)
    else:
        starts, restarts = neutral_edges(read_csv(d / 'esp32.csv'), a.clock)
    events = analyze(track, starts, restarts, a.pre_s, a.window_s, a.tail_s, a.eps_m)
    if (d / 'decision.csv').is_file():
        attach_decisions(events, read_csv(d / 'decision.csv'), a.clock)
    conditions = {'trigger': a.trigger, 'track': Path(a.track).name, 'clock': a.clock, 'pre_s': a.pre_s, 'window_s': a.window_s, 'tail_s': a.tail_s, 'eps_m': a.eps_m,
                  'track_points': len(track), 'signals': len(events), '算出': sum(e['verdict'] == '算出' for e in events), '未判定': sum(e['verdict'] == '未判定' for e in events)}
    print(json.dumps(conditions, ensure_ascii=False))
    print(table(events, track[0][0] if track else 0.0))
    if a.json:
        Path(a.json).write_text(json.dumps({'conditions': conditions, 'events': events}, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
