#!/usr/bin/env python3
"""T08-3（P8 取り付けの後）：MID-360 の傾き（roll・pitch）を 2 つの方法で出し、その差を出す。

方法 1：平らな所の地面の点に面を当てる。制約なしの RANSAC（3 点で面の候補 → 距離が閾値以内の点の数で選ぶ）で
        点の多い面から順に取り出し（壁・物・車体の写り込みは別の面か外れ値になる）、各面の inlier に最小二乗
        （重心まわりの SVD）で当て直す。法線はセンサーの原点の側を正にする（センサーは地面の上にある）。
        取り出した面のうち、上向きの目安（--up-hint）に近く、点の割合が下限以上の面で、最も点の多いものを地面とする
方法 2：内蔵 IMU の静止の区間の加速度の平均の向き（比力。静止では重力の逆、上向き）
差    ：roll・pitch の差と、2 つの上向きのベクトルのなす角

roll・pitch の定義：上向きの単位ベクトル u をセンサーの座標で表し、roll = atan2(u_y, u_z)、
pitch = atan2(−u_x, √(u_y² + u_z²))。水平な座標からセンサーへの回転を Rz(yaw)·Ry(pitch)·Rx(roll) と書いたときの
roll・pitch（ROS の RPY と同じ並び）。yaw は重力でも地面でも決まらない
注意：方法 1 は床の面に対する傾き、方法 2 は重力に対する傾き。差には床そのものの傾きが入る（README）

frame：--frame で点群の frame_id（livox_frame か mid360_link）を必ず渡す。bag の frame_id と違えば止まる。
IMU の frame_id（--imu-frame、既定 livox_frame）が点群と違うときは、--imu-in-cloud-rpy-deg で
IMU の座標から点群の座標への回転を渡さない限り、差は未判定にする（frame を混同しない）

例
  python3 t08_3_tilt.py ~/bags/p8_flat --frame livox_frame --json-out ~/bags/p8_t08_3.json
  python3 t08_3_tilt.py ~/bags/p8_flat --frame livox_frame --up-hint 0.77 0 0.64 --max-diff-deg 0.5
  python3 t08_3_tilt.py ~/bags/prod --cloud-topic /sensors/mid360/points --frame mid360_link \
      --imu-in-cloud-rpy-deg 0 0 0
"""
from __future__ import annotations

import argparse
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bagio  # noqa: E402
import bagstats as bs  # noqa: E402


# --------------------------------------------------------------------------- 幾何

def rp_from_up(u) -> tuple:
    """上向きのベクトル u（センサーの座標）から (roll, pitch) [deg]。"""
    u = np.asarray(u, dtype=np.float64)
    u = u / np.linalg.norm(u)
    roll = math.degrees(math.atan2(u[1], u[2]))
    pitch = math.degrees(math.atan2(-u[0], math.hypot(u[1], u[2])))
    return roll, pitch


def rot_rpy(roll_deg, pitch_deg, yaw_deg) -> np.ndarray:
    """Rz(yaw)·Ry(pitch)·Rx(roll)。"""
    r, p, y = (math.radians(v) for v in (roll_deg, pitch_deg, yaw_deg))
    rx = np.array([[1, 0, 0], [0, math.cos(r), -math.sin(r)], [0, math.sin(r), math.cos(r)]])
    ry = np.array([[math.cos(p), 0, math.sin(p)], [0, 1, 0], [-math.sin(p), 0, math.cos(p)]])
    rz = np.array([[math.cos(y), -math.sin(y), 0], [math.sin(y), math.cos(y), 0], [0, 0, 1]])
    return rz @ ry @ rx


def angle_deg(a, b) -> float:
    a = np.asarray(a, dtype=np.float64) / np.linalg.norm(a)
    b = np.asarray(b, dtype=np.float64) / np.linalg.norm(b)
    return math.degrees(math.acos(max(-1.0, min(1.0, float(a @ b)))))


def _refit(P: np.ndarray):
    c = P.mean(axis=0)
    _u, _s, vt = np.linalg.svd(P - c, full_matrices=False)
    n = vt[2]
    if n @ (-c) < 0:  # センサーの原点の側を正にする
        n = -n
    return n, c


def ransac_plane(P: np.ndarray, threshold: float, iters: int, rng):
    """制約なしの RANSAC。inlier（面からの距離 < threshold）が最も多い面 (n, a, 数) を返す。"""
    n_pts = P.shape[0]
    best = (-1, math.inf, None, None)
    done = 0
    while done < iters:
        b = min(32, iters - done)
        idx = rng.integers(0, n_pts, size=(b, 3))
        A, B, C = P[idx[:, 0]], P[idx[:, 1]], P[idx[:, 2]]
        N = np.cross(B - A, C - A)
        nn = np.linalg.norm(N, axis=1)
        good = nn > 1e-9
        if good.any():
            N, A = N[good] / nn[good, None], A[good]
            D = np.abs(P @ N.T - np.einsum("ij,ij->i", N, A)[None, :])   # (点, 候補)
            inl = D < threshold
            cnt = inl.sum(axis=0)
            score = np.where(cnt > 0, (D * inl).sum(axis=0) / np.maximum(cnt, 1), math.inf)
            k = int(np.lexsort((score, -cnt))[0])
            if cnt[k] > best[0] or (cnt[k] == best[0] and score[k] < best[1]):
                best = (int(cnt[k]), float(score[k]), N[k].copy(), A[k].copy())
        done += b
    return best[2], best[3], best[0]


def _refine(P: np.ndarray, n, a, threshold: float, rounds: int):
    inl = np.abs((P - a) @ n) < threshold
    c = a
    for _ in range(rounds):
        if inl.sum() < 3:
            break
        n, c = _refit(P[inl])
        new = np.abs((P - c) @ n) < threshold
        if np.array_equal(new, inl):
            break
        inl = new
    if inl.sum() >= 3:
        n, c = _refit(P[inl])
    return n, c, inl


def fit_ground(P: np.ndarray, hint, threshold: float, iters: int, max_hint_angle: float, rng,
               max_planes: int = 3, min_inlier_ratio: float = 0.1, refine_rounds: int = 3) -> dict:
    """地面の面を求める。
    1. 制約なしの RANSAC で、点の多い面から順に max_planes 枚を取り出す（取り出した面の inlier は除いて次を探す）。
       各面は inlier に最小二乗（SVD）で当て直し、法線はセンサーの原点の側を正にする
    2. そのうち、法線と hint のなす角が max_hint_angle 以下（＝センサーより下の面）で、inlier が全体の
       min_inlier_ratio 以上の面から、inlier の最も多い面を地面とする
    hint は面を選ぶのにだけ使い、法線の値には使わない（先に候補を hint で絞ると、地面を斜めに切る面を選ぶことがある）。"""
    hint = np.asarray(hint, dtype=np.float64)
    hint = hint / np.linalg.norm(hint)
    n_all = P.shape[0]
    if n_all < 3:
        return {"ok": False, "reason": f"点が足りない（{n_all}）", "planes": []}
    remaining = np.ones(n_all, dtype=bool)
    planes = []
    for _ in range(max_planes):
        Q = P[remaining]
        if Q.shape[0] < 3:
            break
        n0, a0, cnt = ransac_plane(Q, threshold, iters, rng)
        if n0 is None or cnt < 3:
            break
        n, c, inl_q = _refine(Q, n0, a0, threshold, refine_rounds)
        res = (Q[inl_q] - c) @ n
        roll, pitch = rp_from_up(n)
        planes.append({"normal": n.tolist(), "roll_deg": roll, "pitch_deg": pitch, "height_m": float(-(n @ c)),
                       "inliers": int(inl_q.sum()), "inlier_ratio": float(inl_q.sum() / n_all),
                       "residual_rms_m": float(np.sqrt(np.mean(res ** 2))), "angle_to_hint_deg": angle_deg(n, hint)})
        idx = np.nonzero(remaining)[0]
        remaining[idx[inl_q]] = False
    cands = [k for k, pl in enumerate(planes)
             if pl["angle_to_hint_deg"] <= max_hint_angle and pl["inlier_ratio"] >= min_inlier_ratio]
    base = {"candidates": int(n_all), "planes": planes,
            "selection": {"max_hint_angle_deg": max_hint_angle, "min_inlier_ratio": min_inlier_ratio,
                          "max_planes": max_planes}}
    if not cands:
        base.update(ok=False, reason="条件に合う面がない（取り出した面は planes。--up-hint か --up-hint-imu、"
                                     "--max-hint-angle-deg、--roi、--max-planes を見直す）")
        return base
    k = max(cands, key=lambda j: planes[j]["inliers"])
    out = dict(base)
    out.update(ok=True, plane_index=k, **planes[k])
    if k != 0:
        out["warning"] = f"地面に選んだ面は、点の数で {k + 1} 番目の面（1 番目は hint に合わない）"
    return out


def select_points(P: np.ndarray, min_range, max_range, roi) -> np.ndarray:
    k = np.all(np.isfinite(P), axis=1)
    r = np.linalg.norm(P, axis=1)
    if min_range is not None:
        k &= r >= min_range
    if max_range is not None:
        k &= r <= max_range
    if roi is not None:
        x0, x1, y0, y1, z0, z1 = roi
        k &= (P[:, 0] >= x0) & (P[:, 0] <= x1) & (P[:, 1] >= y0) & (P[:, 1] <= y1) & (P[:, 2] >= z0) & (P[:, 2] <= z1)
    return P[k]


# --------------------------------------------------------------------------- 読み取り

def load_clouds(bag, topic: str, frame: str, t0: int, window):
    """窓の中の各フレームの x,y,z を返す。frame_id が --frame と違えば止まる。"""
    frames, stamps = [], []
    for m in bag.messages([topic]):
        if window is not None:
            rel = (m.recv_ns - t0) * 1e-9
            if rel < window[0] or rel > window[1]:
                continue
        meta = bagio.decode_cloud_meta(m.data)
        if meta.frame_id != frame:
            raise SystemExit(f"点群の frame_id が {meta.frame_id!r} で、--frame {frame!r} と違う。frame を混同しないため止める")
        col = bagio.cloud_columns(m.data, meta, ["x", "y", "z"])
        frames.append(np.column_stack([col["x"], col["y"], col["z"]]))
        stamps.append(m.recv_ns)
    order = np.argsort(np.asarray(stamps, dtype=np.int64), kind="stable")
    return [frames[i] for i in order]


# --------------------------------------------------------------------------- 本体

def build_parser():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    bs.add_common_args(p)
    p.add_argument("--cloud-topic", default="/livox/lidar", help="点群の topic（既定 /livox/lidar。製品は /sensors/mid360/points）")
    p.add_argument("--imu-topic", default="/livox/imu", help="IMU の topic（既定 /livox/imu）")
    p.add_argument("--frame", required=True, help="点群の frame_id（livox_frame か mid360_link）。bag と違えば止まる")
    p.add_argument("--imu-frame", default="livox_frame",
                   help="IMU の frame_id（既定 livox_frame。上流のドライバは固定、lddc.cpp 481 行）。bag と違えば止まる")
    p.add_argument("--imu-in-cloud-rpy-deg", nargs=3, type=float, metavar=("R", "P", "Y"),
                   help="IMU の座標から点群の座標への回転（Rz·Ry·Rx、度）。frame_id が違うときに要る")
    p.add_argument("--cloud-window", nargs=2, type=float, metavar=("START_S", "END_S"), help="点群の区間（既定 --window）")
    p.add_argument("--imu-window", nargs=2, type=float, metavar=("START_S", "END_S"), help="IMU の静止の区間（既定 --window）")
    p.add_argument("--roi", nargs=6, type=float, metavar=("XMIN", "XMAX", "YMIN", "YMAX", "ZMIN", "ZMAX"),
                   help="地面の点を探す箱（点群の座標、m）。既定は全体")
    p.add_argument("--min-range", type=float, default=0.1,
                   help="これより近い点を捨てる [m]（既定 0.1：User Manual の近距離の死角。点なしは (0,0,0) で来る）")
    p.add_argument("--max-range", type=float, help="これより遠い点を捨てる [m]")
    p.add_argument("--up-hint", nargs=3, type=float, metavar=("X", "Y", "Z"), default=[0.0, 0.0, 1.0],
                   help="点群の座標での上向きの目安（既定 0 0 1）。面の候補を選ぶのにだけ使う")
    p.add_argument("--up-hint-imu", action="store_true", help="上向きの目安に IMU の平均の向きを使う（frame がそろうときだけ）")
    p.add_argument("--max-hint-angle-deg", type=float, default=30.0, help="候補の法線と目安のなす角の上限（既定 30）")
    p.add_argument("--ransac-threshold-m", type=float, default=0.05,
                   help="面からの距離がこれ以内の点を inlier とする [m]（既定 0.05。README の理由）")
    p.add_argument("--ransac-iters", type=int, default=1000, help="RANSAC の候補の数（1 面あたり。既定 1000）")
    p.add_argument("--max-planes", type=int, default=3, help="点の多い順に取り出す面の数（既定 3）")
    p.add_argument("--min-inlier-ratio", type=float, default=0.1,
                   help="地面とみなす面の inlier の割合の下限（使った点に対して。既定 0.1）")
    p.add_argument("--max-points", type=int, default=200000, help="面を当てる点の数の上限（超えたら無作為に間引く）")
    p.add_argument("--seed", type=int, default=0, help="乱数の seed（結果を再現するため固定）")
    p.add_argument("--per-frame", type=int, default=0, metavar="N",
                   help="N 枚を等間隔に選び、1 枚ずつ当てた roll・pitch の揺れも出す（既定 0：しない）")
    g = p.add_argument_group("判定の基準（人が決める。渡さなければ未判定）")
    g.add_argument("--max-diff-deg", type=float, help="2 つの方法の roll・pitch の差の絶対値の上限 [deg]")
    return p


def analyze(args) -> dict:
    bag = bagio.open_bag(args.bag, args.reader)
    types = bag.topics()
    report = {"tool": "t08_3_tilt", "tools_version": bs.TOOLS_VERSION, "bag": None, "topics_in_bag": types,
              "frame": args.frame, "imu_frame": args.imu_frame, "verdicts": [],
              "definition": "roll = atan2(u_y, u_z)、pitch = atan2(-u_x, hypot(u_y, u_z))。u は上向きの単位ベクトル"
                            "（点群の座標）。水平な座標からの回転 Rz(yaw)·Ry(pitch)·Rx(roll)"}
    data = bs.collect(bag, clouds=[args.cloud_topic], imus=[args.imu_topic])
    imu_all = data[args.imu_topic]
    t0 = bs.time_origin(data.values())
    cloud_frames = data[args.cloud_topic].frame_ids
    if cloud_frames and list(cloud_frames) != [args.frame]:
        raise SystemExit(f"点群の frame_id が {list(cloud_frames)} で、--frame {args.frame!r} と違う。frame を混同しないため止める")
    if t0 is None:
        report["bag"] = bs.bag_info(bag, args.sha256)
        report["note"] = "指定の topic のメッセージがない"
        report["verdicts"].append({"item": "T08-3", "result": bs.UNDECIDED, "reason": "データなし", "value": None,
                                   "statistic": "-"})
        return report

    # ---- 方法 2：IMU
    imu = bs.clip(imu_all, t0, args.imu_window or args.window)
    m2 = {"topic": args.imu_topic, "window_s": args.imu_window or args.window}
    up_imu = None
    if imu.count:
        if imu.frame_ids and list(imu.frame_ids) != [args.imu_frame]:
            raise SystemExit(f"IMU の frame_id が {list(imu.frame_ids)} で、--imu-frame {args.imu_frame!r} と違う。止める")
        vals = bs.imu_values(imu)
        mean = np.asarray(vals["accel_mean_vector"])
        up_imu = mean / np.linalg.norm(mean)
        r_i, p_i = rp_from_up(up_imu)
        per = np.array([rp_from_up(a) for a in imu.acc])
        m2.update({"samples": imu.count, "up_in_imu_frame": up_imu.tolist(), "roll_deg_imu_frame": r_i,
                   "pitch_deg_imu_frame": p_i, "per_sample_roll_deg": bs.describe(per[:, 0]),
                   "per_sample_pitch_deg": bs.describe(per[:, 1]), "accel_norm": vals["accel_norm"],
                   "gyro_norm": vals["gyro_norm"], "accel_unit_guess": vals["unit_guess"]["nearest"]})
    else:
        m2["note"] = "IMU のメッセージがない"
    same_frame = args.frame == args.imu_frame
    R = None
    if same_frame and args.imu_in_cloud_rpy_deg is None:
        R = np.eye(3)
        m2["rotation_to_cloud"] = "なし（frame_id が同じ）"
    elif args.imu_in_cloud_rpy_deg is not None:
        R = rot_rpy(*args.imu_in_cloud_rpy_deg)
        m2["rotation_to_cloud"] = {"rpy_deg": list(args.imu_in_cloud_rpy_deg), "source": "引数"}
    else:
        m2["rotation_to_cloud"] = "未定（frame_id が違い、--imu-in-cloud-rpy-deg が渡されていない）"
    up_imu_c = None
    if up_imu is not None and R is not None:
        up_imu_c = R @ up_imu
        r_c, p_c = rp_from_up(up_imu_c)
        m2.update({"up_in_cloud_frame": up_imu_c.tolist(), "roll_deg": r_c, "pitch_deg": p_c})
    report["method2_imu"] = m2

    # ---- 方法 1：地面
    if args.up_hint_imu:
        if up_imu_c is None:
            raise SystemExit("--up-hint-imu は、IMU のデータがあり、点群の座標への回転が決まるときだけ使える")
        hint = up_imu_c
        hint_src = "IMU の平均の向き（--up-hint-imu）"
    else:
        hint = np.asarray(args.up_hint, dtype=np.float64)
        hint_src = "引数 --up-hint" if args.up_hint != [0.0, 0.0, 1.0] else "既定（0 0 1）"
    frames = load_clouds(bag, args.cloud_topic, args.frame, t0, args.cloud_window or args.window)
    rng = np.random.default_rng(args.seed)
    m1 = {"topic": args.cloud_topic, "window_s": args.cloud_window or args.window, "frames": len(frames),
          "params": {"min_range_m": args.min_range, "max_range_m": args.max_range, "roi": args.roi,
                     "up_hint": (hint / np.linalg.norm(hint)).tolist(), "up_hint_source": hint_src,
                     "max_hint_angle_deg": args.max_hint_angle_deg, "ransac_threshold_m": args.ransac_threshold_m,
                     "ransac_iters": args.ransac_iters, "max_planes": args.max_planes,
                     "min_inlier_ratio": args.min_inlier_ratio, "max_points": args.max_points, "seed": args.seed}}
    if frames:
        P = select_points(np.vstack(frames), args.min_range, args.max_range, args.roi)
        m1["points_total"] = int(sum(f.shape[0] for f in frames))
        m1["points_selected"] = int(P.shape[0])
        if P.shape[0] > args.max_points:
            P = P[rng.choice(P.shape[0], args.max_points, replace=False)]
        m1["points_used"] = int(P.shape[0])
        m1.update(fit_ground(P, hint, args.ransac_threshold_m, args.ransac_iters, args.max_hint_angle_deg, rng,
                             args.max_planes, args.min_inlier_ratio))
        if args.per_frame > 0 and m1.get("ok"):
            pick = np.unique(np.linspace(0, len(frames) - 1, min(args.per_frame, len(frames))).round().astype(int))
            rs, ps = [], []
            for k in pick:
                Q = select_points(frames[k], args.min_range, args.max_range, args.roi)
                if Q.shape[0] > args.max_points:
                    Q = Q[rng.choice(Q.shape[0], args.max_points, replace=False)]
                f = fit_ground(Q, hint, args.ransac_threshold_m, args.ransac_iters, args.max_hint_angle_deg, rng,
                               args.max_planes, args.min_inlier_ratio)
                if f.get("ok"):
                    rs.append(f["roll_deg"])
                    ps.append(f["pitch_deg"])
            m1["per_frame"] = {"frames_tried": int(pick.size), "frames_ok": len(rs), "roll_deg": bs.describe(rs),
                               "pitch_deg": bs.describe(ps)}
    else:
        m1.update(ok=False, reason="区間の中に点群がない")
    report["method1_ground"] = m1

    # ---- 差
    diff = {}
    if m1.get("ok") and up_imu_c is not None:
        dr = m1["roll_deg"] - m2["roll_deg"]
        dp = m1["pitch_deg"] - m2["pitch_deg"]
        dr = (dr + 180.0) % 360.0 - 180.0
        ang = angle_deg(m1["normal"], up_imu_c)
        diff = {"roll_ground_minus_imu_deg": dr, "pitch_ground_minus_imu_deg": dp, "angle_between_up_deg": ang,
                "max_abs_deg": max(abs(dr), abs(dp))}
        if ang > 90.0:
            diff["warning"] = "上向きのなす角が 90° を超える。IMU の加速度の符号の向きか frame の取り違えを疑う"
        report["verdicts"].append(bs.verdict_abs_max("T08-3 2 つの方法の差 [deg]", diff["max_abs_deg"],
                                                     args.max_diff_deg, "--max-diff-deg",
                                                     "|roll の差| と |pitch の差| の大きい方"))
    else:
        why = []
        if not m1.get("ok"):
            why.append("方法 1 が出ていない")
        if up_imu is None:
            why.append("IMU のデータがない")
        elif up_imu_c is None:
            why.append("IMU から点群の座標への回転が未定（--imu-in-cloud-rpy-deg）")
        report["verdicts"].append({"item": "T08-3 2 つの方法の差 [deg]", "value": None, "statistic": "-",
                                   "result": bs.UNDECIDED, "reason": "、".join(why)})
    report["difference"] = diff
    report["bag"] = bs.bag_info(bag, args.sha256)
    return report


def text(report: dict):
    L = bs.bag_header("T08-3 の解析", report["bag"],
                      f"、点群の frame {report['frame']}、IMU の frame {report['imu_frame']}")
    m1 = report.get("method1_ground", {})
    if m1:
        if m1.get("ok"):
            L.append(f"方法 1（地面）：roll {m1['roll_deg']:.3f}°、pitch {m1['pitch_deg']:.3f}°、高さ {m1['height_m']:.4f} m、"
                     f"inlier {m1['inliers']}/{m1['candidates']}（{m1['inlier_ratio']:.2%}）、残差 RMS "
                     f"{m1['residual_rms_m'] * 1000:.1f} mm、{m1['frames']} 枚")
            if m1.get("per_frame"):
                pf = m1["per_frame"]
                L.append(f"  1 枚ずつ（{pf['frames_ok']}/{pf['frames_tried']} 枚）roll {bs.fmt(pf['roll_deg'])}")
                L.append(f"  1 枚ずつ pitch {bs.fmt(pf['pitch_deg'])}")
        else:
            L.append(f"方法 1（地面）：出ない（{m1.get('reason')}）")
        for k, pl in enumerate(m1.get("planes", [])):
            L.append(f"  面 {k + 1}：inlier {pl['inliers']}（{pl['inlier_ratio']:.1%}）、hint とのなす角 "
                     f"{pl['angle_to_hint_deg']:.1f}°、高さ {pl['height_m']:.3f} m、roll {pl['roll_deg']:.2f}°、"
                     f"pitch {pl['pitch_deg']:.2f}°")
        if m1.get("warning"):
            L.append("  注意：" + m1["warning"])
    m2 = report.get("method2_imu", {})
    if m2.get("samples"):
        if "roll_deg" in m2:
            L.append(f"方法 2（IMU）：roll {m2['roll_deg']:.3f}°、pitch {m2['pitch_deg']:.3f}°（点群の座標）、"
                     f"{m2['samples']} 件、加速度の単位 {m2['accel_unit_guess']} に近い")
        L.append(f"  IMU の座標で roll {m2['roll_deg_imu_frame']:.3f}°、pitch {m2['pitch_deg_imu_frame']:.3f}°、"
                 f"点群の座標への回転：{m2['rotation_to_cloud']}")
        L.append(f"  角速度のノルム {bs.fmt(m2['gyro_norm'], digits=5)}")
    d = report.get("difference")
    if d:
        L.append(f"差（地面 − IMU）：roll {d['roll_ground_minus_imu_deg']:.3f}°、pitch {d['pitch_ground_minus_imu_deg']:.3f}°、"
                 f"上向きのなす角 {d['angle_between_up_deg']:.3f}°")
        if d.get("warning"):
            L.append("  注意：" + d["warning"])
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
