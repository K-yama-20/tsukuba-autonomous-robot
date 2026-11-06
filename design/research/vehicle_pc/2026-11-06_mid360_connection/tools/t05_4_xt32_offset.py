#!/usr/bin/env python3
"""T05-4（P5 XT-32 と同時に）：XT-32 と MID-360 の header.stamp の差（近いフレームの対応）と、各 topic の受信の遅れ。

- 対応の取り方：MID-360 の各フレームに、header.stamp がいちばん近い XT-32 のフレームを当てる。
  差の絶対値が --max-pair-gap-ms を超える組は捨てる（既定：XT-32 の stamp の間隔の中央値の半分。データから決める）
- 差 = stamp(MID-360) − stamp(XT-32)。2 台は別々に走査しているので、この差は「走査の位相」と「時刻の付け方の誤差」の
  両方を含む（差の大きさそのものは誤差ではない）。位相が回ると差は周期だけ跳ぶので、跳びを数え、つないだ差の傾きも出す
- 受信の遅れ = 受信の時刻（rosbag2 の recv_timestamp）− header.stamp（topic ごと）
- 台帳の基準は「記録のみ（足りるかの基準は人）」。--offset-std-max-ms などを渡したときだけ判定する

例
  python3 t05_4_xt32_offset.py ~/bags/p5_wall --pairs-csv ~/bags/p5_wall_pairs.csv --json-out ~/bags/p5_wall_t05_4.json
  python3 t05_4_xt32_offset.py ~/bags/prod --mid-topic /sensors/mid360/points
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bagio  # noqa: E402
import bagstats as bs  # noqa: E402


def build_parser():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    bs.add_common_args(p)
    p.add_argument("--mid-topic", default="/livox/lidar", help="MID-360 の点群（既定 /livox/lidar。製品は /sensors/mid360/points）")
    p.add_argument("--xt-topic", default="/sensors/xt32/points", help="XT-32 の点群（既定 /sensors/xt32/points、IFD-21）")
    p.add_argument("--max-pair-gap-ms", type=float, help="組にする stamp の差の上限 [ms]（既定：XT-32 の stamp の間隔の中央値の半分）")
    p.add_argument("--pairs-csv", help="組ごとの CSV を書くファイル（リポジトリの外に置く）")
    p.add_argument("--gap-factor", type=float, default=1.5, help="欠けの疑いを数える倍率（表示だけ）")
    g = p.add_argument_group("判定の基準（台帳では記録のみ。渡したときだけ判定）")
    g.add_argument("--offset-std-max-ms", type=float, help="つないだ差の標準偏差の上限 [ms]")
    g.add_argument("--latency-std-max-ms", type=float, help="各 topic の受信の遅れの標準偏差の上限 [ms]")
    return p


def pair_frames(mid_stamp: np.ndarray, xt_stamp: np.ndarray, max_gap_ns: float):
    """各 MID-360 の stamp に、いちばん近い XT-32 の stamp の添字を返す（組にならないものは -1）。"""
    order = np.argsort(xt_stamp, kind="stable")
    xs = xt_stamp[order]
    pos = np.searchsorted(xs, mid_stamp)
    lo = np.clip(pos - 1, 0, len(xs) - 1)
    hi = np.clip(pos, 0, len(xs) - 1)
    d_lo = np.abs(mid_stamp - xs[lo])
    d_hi = np.abs(mid_stamp - xs[hi])
    pick = np.where(d_hi < d_lo, hi, lo)
    d = np.minimum(d_lo, d_hi)
    idx = order[pick]
    idx[d > max_gap_ns] = -1
    return idx


def unwrap(offset_ms: np.ndarray, period_ms: float):
    """位相が回ったときの ±周期の跳びをつなぐ。跳びの数も返す。"""
    if offset_ms.size == 0:
        return offset_ms, 0
    out = offset_ms.astype(np.float64).copy()
    jumps = 0
    shift = 0.0
    for k in range(1, out.size):
        step = offset_ms[k] - offset_ms[k - 1]
        if step > period_ms / 2:
            shift -= period_ms
            jumps += 1
        elif step < -period_ms / 2:
            shift += period_ms
            jumps += 1
        out[k] = offset_ms[k] + shift
    return out, jumps


def analyze(args) -> dict:
    bag = bagio.open_bag(args.bag, args.reader)
    types = bag.topics()
    data = bs.collect(bag, clouds=[args.mid_topic, args.xt_topic])
    t0 = bs.time_origin(data.values())
    report = {"tool": "t05_4_xt32_offset", "tools_version": bs.TOOLS_VERSION, "bag": None, "window_s": args.window,
              "topics_in_bag": types, "verdicts": []}
    if t0 is None:
        report["bag"] = bs.bag_info(bag, args.sha256)
        report["note"] = "指定の topic のメッセージがない"
        return report
    mid = bs.clip(data[args.mid_topic], t0, args.window)
    xt = bs.clip(data[args.xt_topic], t0, args.window)
    report["mid360"] = bs.timing(mid, args.gap_factor)
    report["xt32"] = bs.timing(xt, args.gap_factor)
    v = report["verdicts"]
    if mid.count == 0 or xt.count < 2:
        report["bag"] = bs.bag_info(bag, args.sha256)
        report["note"] = "どちらかの topic のメッセージが足りない"
        v.append({"item": "T05-4 時刻の差", "result": bs.UNDECIDED, "reason": "データなし", "value": None, "statistic": "-"})
        return report
    xt_period_ms = float(np.median(np.diff(np.sort(xt.stamp_ns)))) * 1e-6
    max_gap_ms = args.max_pair_gap_ms if args.max_pair_gap_ms is not None else xt_period_ms / 2
    idx = pair_frames(mid.stamp_ns, xt.stamp_ns, max_gap_ms * 1e6)
    ok = idx >= 0
    mi = np.nonzero(ok)[0]
    xi = idx[ok]
    off = (mid.stamp_ns[mi] - xt.stamp_ns[xi]) * 1e-6
    unwrapped, jumps = unwrap(off, xt_period_ms)
    t_rel = (mid.recv_ns[mi] - t0) * 1e-9
    lat_mid = (mid.recv_ns[mi] - mid.stamp_ns[mi]) * 1e-6
    lat_xt = (xt.recv_ns[xi] - xt.stamp_ns[xi]) * 1e-6
    report["pairs"] = {
        "pairs": int(mi.size), "mid360_frames": int(mid.count), "unpaired_mid360": int((~ok).sum()),
        "xt32_frames_used": int(np.unique(xi).size), "xt32_frames": int(xt.count),
        "max_pair_gap_ms": max_gap_ms, "max_pair_gap_source": "引数" if args.max_pair_gap_ms is not None
        else "XT-32 の stamp の間隔の中央値の半分",
        "xt32_stamp_period_median_ms": xt_period_ms,
        "offset_mid_minus_xt_ms": bs.describe(off),
        "offset_unwrapped_ms": bs.describe(unwrapped),
        "offset_wraps": jumps,
        "offset_drift": bs.linear_fit(t_rel, unwrapped),
        "latency_mid360_minus_xt32_ms": bs.describe(lat_mid - lat_xt),
        "recv_mid_minus_recv_xt_ms": bs.describe((mid.recv_ns[mi] - xt.recv_ns[xi]) * 1e-6),
        "note": "差は走査の位相と時刻の付け方の誤差を含む。PRM-55=1・DEC-442（同期なし）ではどちらも PC の受信の時刻",
    }
    sd = (report["pairs"]["offset_unwrapped_ms"] or {}).get("std")
    if args.offset_std_max_ms is None:
        v.append({"item": "T05-4 stamp の差（つないだ差の標準偏差）[ms]", "value": sd, "statistic": "標準偏差",
                  "result": bs.UNDECIDED, "reason": "記録のみ（足りるかの基準は人。--offset-std-max-ms で判定できる）"})
    else:
        v.append(bs.verdict_abs_max("T05-4 stamp の差（つないだ差の標準偏差）[ms]", sd, args.offset_std_max_ms,
                                    "--offset-std-max-ms", "標準偏差"))
    for key, name in (("mid360", "MID-360"), ("xt32", "XT-32")):
        s = (report[key].get("latency_recv_minus_stamp_ms") or {}).get("std")
        if args.latency_std_max_ms is None:
            v.append({"item": f"T05-4 {name} の受信の遅れの標準偏差 [ms]", "value": s, "statistic": "標準偏差",
                      "result": bs.UNDECIDED, "reason": "記録のみ（--latency-std-max-ms で判定できる）"})
        else:
            v.append(bs.verdict_abs_max(f"T05-4 {name} の受信の遅れの標準偏差 [ms]", s, args.latency_std_max_ms,
                                        "--latency-std-max-ms", "標準偏差"))
    if args.pairs_csv:
        with open(args.pairs_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["pair", "mid_index", "xt_index", "mid_recv_rel_s", "mid_stamp_rel_s", "xt_stamp_rel_s",
                        "offset_ms", "offset_unwrapped_ms", "mid_latency_ms", "xt_latency_ms"])
            for k in range(mi.size):
                w.writerow([k, int(mi[k]), int(xi[k]), f"{t_rel[k]:.6f}", f"{(mid.stamp_ns[mi[k]] - t0) * 1e-9:.6f}",
                            f"{(xt.stamp_ns[xi[k]] - t0) * 1e-9:.6f}", f"{off[k]:.4f}", f"{unwrapped[k]:.4f}",
                            f"{lat_mid[k]:.4f}", f"{lat_xt[k]:.4f}"])
        report["pairs_csv"] = os.path.basename(args.pairs_csv)
    report["bag"] = bs.bag_info(bag, args.sha256)
    return report


def text(report: dict):
    L = bs.bag_header("T05-4 の解析", report["bag"])
    for key, name in (("mid360", "MID-360"), ("xt32", "XT-32")):
        d = report.get(key)
        if not d:
            continue
        L.append(f"{name} {d['topic']} [{d['type']}] {d['count']} 件、周期（受信）{d.get('rate_hz_recv') or 0:.4f} Hz")
        L.append(f"  stamp の間隔 [ms] {bs.fmt(d.get('stamp_interval_ms'))}")
        L.append(f"  受信 − stamp [ms] {bs.fmt(d.get('latency_recv_minus_stamp_ms'))}")
    pr = report.get("pairs")
    if pr:
        L.append(f"組 {pr['pairs']}（MID-360 {pr['mid360_frames']} 枚のうち組にならない {pr['unpaired_mid360']}、"
                 f"上限 {pr['max_pair_gap_ms']:.2f} ms：{pr['max_pair_gap_source']}）")
        L.append(f"  stamp(MID-360) − stamp(XT-32) [ms] {bs.fmt(pr['offset_mid_minus_xt_ms'])}")
        L.append(f"  つないだ差 [ms] {bs.fmt(pr['offset_unwrapped_ms'])}、跳び {pr['offset_wraps']} 回")
        if pr.get("offset_drift"):
            L.append(f"  つないだ差の傾き {pr['offset_drift']['slope_per_min']:.4f} ms/分")
        L.append(f"  受信の遅れの差（MID-360 − XT-32）[ms] {bs.fmt(pr['latency_mid360_minus_xt32_ms'])}")
        L.append(f"  注：{pr['note']}")
    if report.get("note"):
        L.append(report["note"])
    L.append("判定：")
    L += [bs.verdict_line(v) for v in report["verdicts"]]
    return L


def main(argv=None):
    args = build_parser().parse_args(argv)
    report = analyze(args)
    bs.emit(report, args.json_out, args.json, text(report))
    return report


if __name__ == "__main__":
    main()
