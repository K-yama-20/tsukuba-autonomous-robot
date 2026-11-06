#!/usr/bin/env python3
"""T07（P7 長時間・発熱）：点群の点の数と周期の時系列を CSV に出す（T07-2 の材料）。

- 1 行 1 枚の CSV（--csv-out）と、--bin-s 秒ごとの集計の CSV（--bins-csv-out）
- 集計の区間ごとの周期（受信の時刻から）と点数の平均。全区間の最小・最大を要約に出す
- 判定：--ref-hz（P4 で測った周期）・--ref-points（P4 の点数）と --tol-pct を渡したときだけ、
  すべての集計の区間がその幅に入るかを見る。渡さなければ未判定（基準 tbd）
- 温度：livox_ros_driver2（2144554）は温度の topic を出さない（README）。T07-1 の温度は人が測る。
  bag に名前に temp を含む topic か sensor_msgs/msg/Temperature があれば、名前だけを一覧に出す

例
  python3 t07_timeseries.py ~/bags/p7_60min --csv-out ~/bags/p7_frames.csv --bins-csv-out ~/bags/p7_bins.csv
  python3 t07_timeseries.py ~/bags/p7_60min --csv-out ~/bags/p7_frames.csv --ref-hz 10.0 --ref-points 20000 --tol-pct 5
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bagio  # noqa: E402
import bagstats as bs  # noqa: E402


def build_parser():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    bs.add_common_args(p)
    p.add_argument("--cloud-topic", default="/livox/lidar", help="点群の topic（既定 /livox/lidar。製品は /sensors/mid360/points）")
    p.add_argument("--csv-out", required=True, help="1 行 1 枚の CSV（リポジトリの外に置く）")
    p.add_argument("--bins-csv-out", help="区間ごとの集計の CSV")
    p.add_argument("--bin-s", type=float, default=60.0, help="集計の区間の長さ [s]（既定 60。解析の設定で、基準ではない）")
    p.add_argument("--gap-factor", type=float, default=1.5, help="欠けの疑いを数える倍率（表示だけ）")
    g = p.add_argument_group("判定の基準（人が決める。渡さなければ未判定）")
    g.add_argument("--ref-hz", type=float, help="比べる周期 [Hz]（P4 の値）")
    g.add_argument("--ref-points", type=float, help="比べる 1 枚の点数（P4 の値）")
    g.add_argument("--tol-pct", type=float, help="許容の幅 [%]")
    return p


def bins(s: bs.Series, t0: int, bin_s: float):
    rel = (s.recv_ns - t0) * 1e-9
    if rel.size == 0:
        return []
    edges = np.arange(0.0, rel[-1] + bin_s, bin_s)
    rows = []
    for k in range(len(edges) - 1):
        a, b = edges[k], edges[k + 1]
        m = (rel >= a) & (rel < b) if k < len(edges) - 2 else (rel >= a) & (rel <= b)
        n = int(m.sum())
        r = rel[m]
        hz = (n - 1) / (r[-1] - r[0]) if n >= 2 and r[-1] > r[0] else math.nan
        pts = s.n_points[m]
        rows.append({"bin": k, "start_s": float(a), "end_s": float(min(b, rel[-1])), "frames": n, "rate_hz_recv": hz,
                     "points_mean": float(pts.mean()) if n else math.nan,
                     "points_min": int(pts.min()) if n else None, "points_max": int(pts.max()) if n else None,
                     "full": bool(b <= rel[-1] + 1e-9)})
    return rows


def judge_bins(rows, key, ref, tol, label, args_text):
    """区間の長さが --bin-s に満たない最後の区間は、区間が 1 つしかないときを除いて判定に使わない。"""
    use = [r for r in rows if r["full"]] or rows
    vals = [r[key] for r in use if r["frames"] >= 2 and math.isfinite(r[key])]
    worst = None
    if vals and ref is not None:
        worst = max(vals, key=lambda x: abs(x - ref))
    v = bs.verdict_rel(label, worst if ref is not None else (min(vals) if vals else None), ref, tol, args_text,
                       "基準からいちばん離れた区間の値" if ref is not None else "区間の最小")
    if vals:
        v["min"] = min(vals)
        v["max"] = max(vals)
    return v


def analyze(args) -> dict:
    bag = bagio.open_bag(args.bag, args.reader)
    types = bag.topics()
    data = bs.collect(bag, clouds=[args.cloud_topic])
    s = data[args.cloud_topic]
    t0 = bs.time_origin([s])
    report = {"tool": "t07_timeseries", "tools_version": bs.TOOLS_VERSION, "bag": None, "window_s": args.window,
              "topics_in_bag": types, "verdicts": [],
              "temperature_topics_in_bag": sorted(t for t, ty in types.items()
                                                  if "temp" in t.lower() or ty == "sensor_msgs/msg/Temperature"),
              "temperature_note": "livox_ros_driver2 2144554 は温度の topic を出さない（README の T07 の節）。T07-1 は人が測る"}
    if t0 is None:
        report["bag"] = bs.bag_info(bag, args.sha256)
        report["note"] = "指定の topic のメッセージがない"
        return report
    s = bs.clip(s, t0, args.window)
    t0 = bs.time_origin([s]) if s.count else t0
    report["cloud"] = bs.timing(s, args.gap_factor)
    report["cloud"]["points_per_frame"] = bs.describe(s.n_points)
    rel = (s.recv_ns - t0) * 1e-9
    di = np.r_[math.nan, np.diff(s.recv_ns) * 1e-6]
    dst = np.r_[math.nan, np.diff(s.stamp_ns) * 1e-6]
    lat = (s.recv_ns - s.stamp_ns) * 1e-6
    with open(args.csv_out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["frame", "recv_rel_s", "stamp_rel_s", "recv_interval_ms", "stamp_interval_ms", "latency_ms",
                    "points"])
        for k in range(s.count):
            w.writerow([k, f"{rel[k]:.6f}", f"{(s.stamp_ns[k] - t0) * 1e-9:.6f}",
                        "" if k == 0 else f"{di[k]:.4f}", "" if k == 0 else f"{dst[k]:.4f}", f"{lat[k]:.4f}",
                        int(s.n_points[k])])
    report["csv"] = os.path.basename(args.csv_out)
    rows = bins(s, t0, args.bin_s)
    report["bins"] = {"bin_s": args.bin_s, "count": len(rows), "rows": rows,
                      "note": "最後の区間は短いことがある（full が false）"}
    if args.bins_csv_out:
        with open(args.bins_csv_out, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            keys = ["bin", "start_s", "end_s", "frames", "rate_hz_recv", "points_mean", "points_min", "points_max", "full"]
            w.writerow(keys)
            for r in rows:
                w.writerow([r[k] for k in keys])
        report["bins_csv"] = os.path.basename(args.bins_csv_out)
    report["verdicts"].append(judge_bins(rows, "rate_hz_recv", args.ref_hz, args.tol_pct, "T07-2 区間ごとの周期 [Hz]",
                                         "--ref-hz と --tol-pct"))
    report["verdicts"].append(judge_bins(rows, "points_mean", args.ref_points, args.tol_pct,
                                         "T07-2 区間ごとの点数の平均", "--ref-points と --tol-pct"))
    report["bag"] = bs.bag_info(bag, args.sha256)
    return report


def text(report: dict):
    L = bs.bag_header("T07 の解析", report["bag"])
    d = report.get("cloud")
    if d:
        L.append(f"点群 {d['topic']} {d['count']} 件、{d.get('duration_recv_s', 0):.1f} s、周期（受信）"
                 f"{d.get('rate_hz_recv') or 0:.4f} Hz")
        L.append(f"  1 枚の点数 {bs.fmt(d.get('points_per_frame'), digits=1)}")
        L.append(f"  受信の間隔 [ms] {bs.fmt(d.get('recv_interval_ms'))}")
        bn = report["bins"]
        L.append(f"  集計の区間 {bn['bin_s']} s × {bn['count']}")
        for r in bn["rows"]:
            L.append(f"    {r['start_s']:8.1f}〜{r['end_s']:8.1f} s：{r['frames']} 枚 {r['rate_hz_recv']:.4f} Hz "
                     f"点数の平均 {r['points_mean']:.1f}{'' if r['full'] else '（短い区間）'}")
        L.append(f"CSV：{report.get('csv')}" + (f"、{report['bins_csv']}" if report.get("bins_csv") else ""))
    L.append(f"温度の topic（bag の中）：{report['temperature_topics_in_bag'] or 'なし'}。{report['temperature_note']}")
    L.append("判定：")
    L += [bs.verdict_line(v) for v in report["verdicts"]]
    return L


def main(argv=None):
    p = build_parser()
    args = p.parse_args(argv)
    if (args.ref_hz is not None or args.ref_points is not None) and args.tol_pct is None:
        p.error("--ref-hz・--ref-points を渡すときは --tol-pct も渡す")
    report = analyze(args)
    bs.emit(report, args.json_out, args.json, text(report))
    return report


if __name__ == "__main__":
    main()
