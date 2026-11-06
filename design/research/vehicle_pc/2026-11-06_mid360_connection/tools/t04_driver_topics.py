#!/usr/bin/env python3
"""T04（P4 ROS 2 ドライバ）：rosbag を読むだけで、点群と IMU の周期・揺れ・時刻・点数・field・加速度の単位を出す。

台帳 ledger.yaml の項目との対応
- T04-1 topic・型・frame_id      → topics_in_bag、cloud.frame_ids、imu.frame_ids
- T04-2 周期                     → cloud.rate_hz_recv、imu.rate_hz_recv（判定は --cloud-hz-* / --imu-hz-*）
- T04-3 点数・field              → cloud.points_per_frame、cloud.layouts（判定は --points-*）
- T04-5 時刻                     → *.latency_recv_minus_stamp_ms、*.latency_drift（判定は --latency-drift-max-ms-per-min）
- 加速度の単位                   → imu.values.unit_guess（--static-window の区間）
基準の値はこのスクリプトでは決めない。渡されない基準は「未判定（基準 tbd）」になる。

例
  python3 t04_driver_topics.py ~/bags/p4_60s --json-out ~/bags/p4_60s_t04.json
  python3 t04_driver_topics.py ~/bags/p4_60s --cloud-hz-expected 10 --cloud-hz-tol-pct 5 \
      --imu-hz-expected 200 --imu-hz-tol-pct 5 --points-expected 20000 --points-tol-pct 10
  python3 t04_driver_topics.py ~/bags/prod --cloud-topic /sensors/mid360/points --expect-cloud-frame mid360_link
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bagio  # noqa: E402
import bagstats as bs  # noqa: E402


def build_parser():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    bs.add_common_args(p)
    p.add_argument("--cloud-topic", default="/livox/lidar", help="点群の topic（既定 /livox/lidar。製品は /sensors/mid360/points）")
    p.add_argument("--imu-topic", default="/livox/imu", help="IMU の topic（既定 /livox/imu）")
    p.add_argument("--no-imu", action="store_true", help="IMU を見ない")
    p.add_argument("--point-time-field", default="timestamp", help="点ごとの時刻の field 名（既定 timestamp。空なら見ない）")
    p.add_argument("--expect-cloud-frame", help="点群の frame_id がこれと同じかを見る（livox_frame か mid360_link）")
    p.add_argument("--expect-imu-frame", help="IMU の frame_id がこれと同じかを見る")
    p.add_argument("--static-window", nargs=2, type=float, metavar=("START_S", "END_S"),
                   help="加速度のノルムを見る静止の区間（最初の受信からの秒）。既定は --window と同じ")
    p.add_argument("--gap-factor", type=float, default=1.5,
                   help="受信の間隔が中央値のこの倍を超えたら欠けの疑いとして数える（既定 1.5。表示だけで判定には使わない）")
    g = p.add_argument_group("判定の基準（人が決める。渡さなければ未判定）")
    g.add_argument("--cloud-hz-expected", type=float)
    g.add_argument("--cloud-hz-tol-pct", type=float)
    g.add_argument("--imu-hz-expected", type=float)
    g.add_argument("--imu-hz-tol-pct", type=float)
    g.add_argument("--points-expected", type=float, help="1 枚の点数の期待値（例：仕様の点/秒 ÷ 周期）")
    g.add_argument("--points-tol-pct", type=float)
    g.add_argument("--latency-drift-max-ms-per-min", type=float,
                   help="受信 − stamp の傾きの絶対値の上限（ms/分）。点群と IMU の両方に使う")
    return p


def frame_check(item: str, frame_ids: dict, expected):
    v = {"item": item, "value": list(frame_ids), "statistic": "frame_id の一覧"}
    if not frame_ids:
        v.update(result=bs.UNDECIDED, reason="値がない（データなし）")
    elif expected is None:
        v.update(result=bs.UNDECIDED, reason="記録のみ（期待する frame_id が渡されていない）")
    else:
        v.update(result=bs.PASS if list(frame_ids) == [expected] else bs.FAIL, criteria={"frame_id": expected})
    return v


def analyze(args) -> dict:
    bag = bagio.open_bag(args.bag, args.reader)
    types = bag.topics()
    imus = [] if args.no_imu else [args.imu_topic]
    data = bs.collect(bag, clouds=[args.cloud_topic], imus=imus, point_time_field=args.point_time_field or None)
    t0 = bs.time_origin(data.values())
    report = {"tool": "t04_driver_topics", "tools_version": bs.TOOLS_VERSION, "bag": None,
              "window_s": args.window, "topics_in_bag": types, "verdicts": []}
    if t0 is None:
        report["bag"] = bs.bag_info(bag, args.sha256)
        report["note"] = "指定の topic のメッセージがない"
        report["verdicts"].append({"item": "全体", "result": bs.UNDECIDED, "reason": "データなし", "value": None,
                                   "statistic": "-"})
        return report
    cloud = bs.clip(data[args.cloud_topic], t0, args.window)
    c = bs.timing(cloud, args.gap_factor)
    c.update(bs.cloud_points(cloud))
    report["cloud"] = c
    v = report["verdicts"]
    v.append(frame_check("T04-1 点群の frame_id", c.get("frame_ids", {}), args.expect_cloud_frame))
    v.append(bs.verdict_rel("T04-2 点群の周期 [Hz]", c.get("rate_hz_recv"), args.cloud_hz_expected, args.cloud_hz_tol_pct,
                            "--cloud-hz-expected と --cloud-hz-tol-pct", "受信の時刻からの平均の周期"))
    pts = (c.get("points_per_frame") or {}).get("mean")
    v.append(bs.verdict_rel("T04-3 1 枚の点数", pts, args.points_expected, args.points_tol_pct,
                            "--points-expected と --points-tol-pct", "1 枚の点数の平均"))
    if args.points_expected is not None and cloud.count:
        lo = args.points_expected * (1 - args.points_tol_pct / 100.0)
        hi = args.points_expected * (1 + args.points_tol_pct / 100.0)
        n = cloud.n_points
        c["frames_outside_points_range"] = int(((n < lo) | (n > hi)).sum())
    drift = (c.get("latency_drift") or {}).get("slope_per_min")
    v.append(bs.verdict_abs_max("T04-5 点群の受信 − stamp の傾き [ms/分]", drift, args.latency_drift_max_ms_per_min,
                                "--latency-drift-max-ms-per-min", "最小二乗の傾きの絶対値"))
    if imus:
        imu = bs.clip(data[args.imu_topic], t0, args.window)
        i = bs.timing(imu, args.gap_factor)
        static = bs.clip(data[args.imu_topic], t0, args.static_window or args.window)
        i["values"] = bs.imu_values(static)
        i["values"]["window_s"] = args.static_window or args.window
        report["imu"] = i
        v.append(frame_check("T04-1 IMU の frame_id", i.get("frame_ids", {}), args.expect_imu_frame))
        v.append(bs.verdict_rel("T04-2 IMU の周期 [Hz]", i.get("rate_hz_recv"), args.imu_hz_expected, args.imu_hz_tol_pct,
                                "--imu-hz-expected と --imu-hz-tol-pct", "受信の時刻からの平均の周期"))
        d2 = (i.get("latency_drift") or {}).get("slope_per_min")
        v.append(bs.verdict_abs_max("T04-5 IMU の受信 − stamp の傾き [ms/分]", d2, args.latency_drift_max_ms_per_min,
                                    "--latency-drift-max-ms-per-min", "最小二乗の傾きの絶対値"))
    report["bag"] = bs.bag_info(bag, args.sha256)  # 途中で切れたファイルの印は読み終えてから分かる
    return report


def text(report: dict):
    L = bs.bag_header("T04 の解析", report["bag"])
    L.append("bag の topic：" + ", ".join(f"{k} [{v}]" for k, v in sorted(report["topics_in_bag"].items())))
    for key, name in (("cloud", "点群"), ("imu", "IMU")):
        d = report.get(key)
        if not d:
            continue
        L.append(f"{name} {d['topic']} [{d['type']}] {d['count']} 件 frame_id {d.get('frame_ids')}")
        if d["count"] < 2:
            continue
        L.append(f"  周期（受信）{d.get('rate_hz_recv') or 0:.4f} Hz、周期（stamp）{d.get('rate_hz_stamp') or 0:.4f} Hz")
        L.append(f"  受信の間隔 [ms] {bs.fmt(d.get('recv_interval_ms'))}")
        L.append(f"  stamp の間隔 [ms] {bs.fmt(d.get('stamp_interval_ms'))}")
        L.append(f"  stamp の逆行 {d['stamp_backward']['count']} 件（最大 {d['stamp_backward']['max_ms']:.3f} ms）、"
                 f"重複 {d['stamp_duplicate']} 件、欠けの疑い {d['recv_gaps']['count']} 件"
                 f"（間隔 > 中央値×{d['recv_gaps']['factor_of_median']}）")
        L.append(f"  受信 − stamp [ms] {bs.fmt(d.get('latency_recv_minus_stamp_ms'))}")
        dr = d.get("latency_drift")
        if dr:
            L.append(f"  受信 − stamp の傾き {dr['slope_per_min']:.4f} ms/分（{dr['span_s']:.1f} s、残差の標準偏差 "
                     f"{dr['residual_std']:.3f} ms）")
        if "publish_minus_stamp_ms" in d:
            L.append(f"  送信 − stamp [ms] {bs.fmt(d['publish_minus_stamp_ms'])}")
            L.append(f"  受信 − 送信 [ms] {bs.fmt(d['recv_minus_publish_ms'])}")
        else:
            L.append(f"  送信の時刻：{d.get('publish_time')}")
        if key == "cloud":
            L.append(f"  1 枚の点数 {bs.fmt(d.get('points_per_frame'), digits=1)}")
            for lay in d.get("layouts", []):
                fs = ", ".join(f"{f['name']}:{f['datatype']}@{f['offset']}" for f in lay["fields"])
                L.append(f"  field（{lay['frames']} 枚）point_step {lay['point_step']} height {lay['height']}：{fs}")
            pt = d.get("point_time")
            if pt:
                L.append(f"  点の時刻 field {pt['field']}：単位の推定 {pt['unit_guess']}")
                if "first_point_minus_stamp_ms" in pt:
                    L.append(f"    最初の点 − stamp [ms] {bs.fmt(pt['first_point_minus_stamp_ms'])}")
                    L.append(f"    1 枚の中の時間の幅 [ms] {bs.fmt(pt['span_in_frame_ms'])}")
        else:
            val = d.get("values") or {}
            if val:
                u = val["unit_guess"]
                L.append(f"  静止の区間 {val.get('window_s') or '全体'}：加速度のノルム {bs.fmt(val['accel_norm'], digits=5)}")
                L.append(f"  加速度の単位：{u['nearest']} に近い（ノルムの平均 {u['norm_mean']:.5f}）")
                L.append(f"  角速度のノルム {bs.fmt(val['gyro_norm'], digits=5)}")
    L.append("判定：")
    L += [bs.verdict_line(v) for v in report["verdicts"]]
    return L


def main(argv=None):
    p = build_parser()
    args = p.parse_args(argv)
    for a, b in (("cloud_hz_expected", "cloud_hz_tol_pct"), ("imu_hz_expected", "imu_hz_tol_pct"),
                 ("points_expected", "points_tol_pct")):
        bs.need_pair(p, args, a, b)
    report = analyze(args)
    bs.emit(report, args.json_out, args.json, text(report))
    return report


if __name__ == "__main__":
    main()
