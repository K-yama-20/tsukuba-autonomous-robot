"""bag から topic ごとの時刻・点数・IMU の値を集める処理と、統計・判定の共通部分。

判定の決まり（台帳 ledger.yaml の記入の決まりに合わせる）
- 結果は 合格 / 不合格 / 未判定 のどれか
- 基準の値はスクリプトの中で決めない。引数で渡されなければ「未判定（基準 tbd）」として数値だけを出す
"""
from __future__ import annotations

import json
import math
import os
import sys
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bagio  # noqa: E402

TOOLS_VERSION = "2026-11-07"
G0 = 9.80665  # 標準重力（m/s² と g の換算の定義値）。単位の見分けにだけ使う
PASS, FAIL, UNDECIDED = "合格", "不合格", "未判定"


# --------------------------------------------------------------------------- 集める

@dataclass
class Series:
    topic: str
    msgtype: str = "?"
    recv_ns: np.ndarray = None
    pub_ns: Optional[np.ndarray] = None
    stamp_ns: np.ndarray = None
    frame_list: List[str] = field(default_factory=list)
    frame_idx: Optional[np.ndarray] = None
    # PointCloud2
    n_points: Optional[np.ndarray] = None
    layout_list: List[tuple] = field(default_factory=list)   # (fields, point_step, is_bigendian, height)
    layout_idx: Optional[np.ndarray] = None
    time_field: Optional[str] = None
    time_min: Optional[np.ndarray] = None
    time_max: Optional[np.ndarray] = None
    # Imu
    acc: Optional[np.ndarray] = None
    gyro: Optional[np.ndarray] = None
    pub_note: Optional[str] = None

    @property
    def count(self) -> int:
        return 0 if self.recv_ns is None else len(self.recv_ns)

    @property
    def frame_ids(self) -> Dict[str, int]:
        if self.frame_idx is None:
            return {}
        c = Counter(self.frame_idx.tolist())
        return {self.frame_list[i]: int(n) for i, n in c.most_common()}

    @property
    def layouts(self) -> List[tuple]:
        if self.layout_idx is None:
            return []
        c = Counter(self.layout_idx.tolist())
        return [(self.layout_list[i], int(n)) for i, n in c.most_common()]


def _index(lst: List, value) -> int:
    try:
        return lst.index(value)
    except ValueError:
        lst.append(value)
        return len(lst) - 1


def collect(bag, clouds: Sequence[str] = (), imus: Sequence[str] = (), point_time_field: Optional[str] = None
            ) -> Dict[str, Series]:
    """1 回の読み取りで、指定の topic の時刻などを集める。受信の時刻の順に並べ替えて返す。"""
    types = bag.topics()
    want = list(dict.fromkeys(list(clouds) + list(imus)))
    keys = ("recv", "pub", "stamp", "order", "fidx", "npts", "lidx", "tmin", "tmax", "acc", "gyro")
    raw: Dict[str, dict] = {t: {k: [] for k in keys} for t in want}
    out: Dict[str, Series] = {t: Series(t, types.get(t, "(bag にない)")) for t in want}
    for m in bag.messages(want):
        r = raw[m.topic]
        s = out[m.topic]
        if m.topic in clouds:
            if m.msgtype != bagio.TYPE_POINTCLOUD2:
                raise bagio.BagError(f"{m.topic} の型が {m.msgtype}（PointCloud2 を想定）")
            meta = bagio.decode_cloud_meta(m.data)
            r["stamp"].append(meta.stamp_ns)
            r["fidx"].append(_index(s.frame_list, meta.frame_id))
            r["npts"].append(meta.n_points)
            r["lidx"].append(_index(s.layout_list, (tuple(meta.fields), meta.point_step, meta.is_bigendian,
                                                    meta.height)))
            if point_time_field:
                has = any(f[0] == point_time_field for f in meta.fields)
                if has:
                    s.time_field = point_time_field
                if has and meta.n_points:
                    col = bagio.cloud_columns(m.data, meta, [point_time_field])[point_time_field]
                    r["tmin"].append(float(np.min(col)))
                    r["tmax"].append(float(np.max(col)))
                else:
                    r["tmin"].append(math.nan)
                    r["tmax"].append(math.nan)
        else:
            if m.msgtype != bagio.TYPE_IMU:
                raise bagio.BagError(f"{m.topic} の型が {m.msgtype}（Imu を想定）")
            smp = bagio.decode_imu(m.data)
            r["stamp"].append(smp.stamp_ns)
            r["fidx"].append(_index(s.frame_list, smp.frame_id))
            r["acc"].append(smp.linear_acceleration)
            r["gyro"].append(smp.angular_velocity)
        r["recv"].append(m.recv_ns)
        r["pub"].append(-1 if m.publish_ns is None else m.publish_ns)
        r["order"].append(m.order)
    for t, r in raw.items():
        s = out[t]
        recv = np.asarray(r["recv"], dtype=np.int64)
        idx = np.lexsort((np.asarray(r["order"], dtype=np.int64), recv)) if len(recv) else np.zeros(0, dtype=int)
        s.recv_ns = recv[idx]
        s.stamp_ns = np.asarray(r["stamp"], dtype=np.int64)[idx]
        s.frame_idx = np.asarray(r["fidx"], dtype=np.int64)[idx]
        pub = np.asarray(r["pub"], dtype=np.int64)[idx]
        if len(pub) and np.all(pub > 0):
            if np.array_equal(pub, s.recv_ns):
                s.pub_note = "publishTime が受信の時刻と同じ（送り手の時刻が記録されていない）"
            else:
                s.pub_ns = pub
        if t in clouds:
            s.n_points = np.asarray(r["npts"], dtype=np.int64)[idx]
            s.layout_idx = np.asarray(r["lidx"], dtype=np.int64)[idx]
            if s.time_field and len(r["tmin"]) == len(recv):
                s.time_min = np.asarray(r["tmin"], dtype=np.float64)[idx]
                s.time_max = np.asarray(r["tmax"], dtype=np.float64)[idx]
        else:
            s.acc = np.asarray(r["acc"], dtype=np.float64).reshape(-1, 3)[idx]
            s.gyro = np.asarray(r["gyro"], dtype=np.float64).reshape(-1, 3)[idx]
    return out


def time_origin(series: Iterable[Series]) -> Optional[int]:
    firsts = [int(s.recv_ns[0]) for s in series if s.count]
    return min(firsts) if firsts else None


def clip(s: Series, t0_ns: int, window: Optional[Sequence[float]]) -> Series:
    """受信の時刻で [start, end]（t0 からの秒）に切る。"""
    if window is None or s.count == 0:
        return s
    rel = (s.recv_ns - t0_ns) * 1e-9
    k = (rel >= window[0]) & (rel <= window[1])

    def cut(a):
        return None if a is None else a[k]

    return Series(s.topic, s.msgtype, cut(s.recv_ns), cut(s.pub_ns), cut(s.stamp_ns), s.frame_list, cut(s.frame_idx),
                  cut(s.n_points), s.layout_list, cut(s.layout_idx), s.time_field, cut(s.time_min), cut(s.time_max),
                  cut(s.acc), cut(s.gyro), s.pub_note)


# --------------------------------------------------------------------------- 統計

def describe(x) -> Optional[dict]:
    """平均・標準偏差（標本、ddof=1）・最小・最大・パーセンタイル（線形補間）。"""
    a = np.asarray(x, dtype=np.float64)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return None
    p = np.percentile(a, [1, 5, 50, 95, 99])
    return {"n": int(a.size), "mean": float(a.mean()), "std": float(a.std(ddof=1)) if a.size > 1 else 0.0,
            "min": float(a.min()), "max": float(a.max()),
            "p1": float(p[0]), "p5": float(p[1]), "p50": float(p[2]), "p95": float(p[3]), "p99": float(p[4])}


def linear_fit(t_s, y) -> Optional[dict]:
    """y = a + b t の最小二乗。b は y の単位/分で返す。"""
    t = np.asarray(t_s, dtype=np.float64)
    v = np.asarray(y, dtype=np.float64)
    k = np.isfinite(t) & np.isfinite(v)
    t, v = t[k], v[k]
    if t.size < 3 or np.ptp(t) == 0:
        return None
    b, a = np.polyfit(t, v, 1)
    res = v - (a + b * t)
    return {"slope_per_min": float(b * 60.0), "intercept": float(a), "residual_std": float(res.std(ddof=2)),
            "span_s": float(np.ptp(t)), "n": int(t.size)}


def timing(s: Series, gap_factor: float) -> dict:
    """受信の間隔、header.stamp の間隔、逆行・重複、受信 − stamp の遅れ。時間は ms。"""
    out: dict = {"topic": s.topic, "type": s.msgtype, "count": s.count, "frame_ids": s.frame_ids}
    if s.count == 0:
        out["note"] = "メッセージがない"
        return out
    recv = s.recv_ns
    stamp = s.stamp_ns
    out["duration_recv_s"] = float((recv[-1] - recv[0]) * 1e-9)
    if s.count >= 2:
        out["rate_hz_recv"] = float((s.count - 1) / ((recv[-1] - recv[0]) * 1e-9)) if recv[-1] > recv[0] else None
        span = (int(stamp.max()) - int(stamp.min())) * 1e-9
        out["rate_hz_stamp"] = float((s.count - 1) / span) if span > 0 else None
        di = np.diff(recv) * 1e-6
        ds = np.diff(stamp) * 1e-6
        out["recv_interval_ms"] = describe(di)
        out["stamp_interval_ms"] = describe(ds)
        med = float(np.median(di))
        out["recv_gaps"] = {"factor_of_median": gap_factor, "median_ms": med,
                            "count": int(np.sum(di > gap_factor * med)) if med > 0 else 0}
        back = np.nonzero(ds < 0)[0]
        out["stamp_backward"] = {"count": int(back.size),
                                 "max_ms": float(-ds[back].min()) if back.size else 0.0,
                                 "first_indices": [int(i + 1) for i in back[:20]]}
        out["stamp_repeat_consecutive"] = int(np.sum(ds == 0))
    out["stamp_duplicate"] = int(s.count - np.unique(stamp).size)
    lat = (recv - stamp) * 1e-6
    out["latency_recv_minus_stamp_ms"] = describe(lat)
    out["latency_drift"] = linear_fit((recv - recv[0]) * 1e-9, lat)  # slope_per_min は ms/分
    if s.pub_ns is not None:
        out["publish_minus_stamp_ms"] = describe((s.pub_ns - stamp) * 1e-6)
        out["recv_minus_publish_ms"] = describe((recv - s.pub_ns) * 1e-6)
    else:
        out["publish_time"] = s.pub_note or "なし（SQLite3 か rosbag2_py で読んだ。MCAP を --reader builtin で読むと出る）"
    return out


def cloud_points(s: Series) -> dict:
    out: dict = {}
    if s.count == 0:
        return out
    out["points_per_frame"] = describe(s.n_points)
    layouts = []
    for (fields, step, big, height), n in s.layouts:
        layouts.append({"frames": n, "point_step": step, "is_bigendian": big, "height": height,
                        "fields": [{"name": f[0], "offset": f[1], "datatype": bagio.POINTFIELD_TYPES.get(f[2], ("?",))[0],
                                    "count": f[3]} for f in fields]})
    out["layouts"] = layouts
    out["layout_changed"] = len(layouts) > 1
    if s.time_min is not None:
        out["point_time"] = point_time(s)
    return out


def point_time(s: Series) -> dict:
    """点ごとの時刻の field を、header.stamp と比べる。単位は値の大きさから推定し、推定と明記する。"""
    stamp_s = s.stamp_ns * 1e-9
    tmin, tmax = s.time_min, s.time_max
    cands = {
        "ns（絶対時刻）": (tmin * 1e-9 - stamp_s, (tmax - tmin) * 1e-9),
        "s（絶対時刻）": (tmin - stamp_s, tmax - tmin),
        "ns（stamp からの相対）": (tmin * 1e-9, (tmax - tmin) * 1e-9),
        "s（stamp からの相対）": (tmin, tmax - tmin),
    }
    first = None
    for name, (off, span) in cands.items():
        med = float(np.nanmedian(np.abs(off))) if np.isfinite(off).any() else math.inf
        if med < 1.0 and float(np.nanmedian(span)) < 10.0:
            first = name
            break
    out = {"field": s.time_field, "raw_first_frame": {"min": float(tmin[0]), "max": float(tmax[0])},
           "unit_guess": first or "不明（どの解釈でも stamp から 1 s 以上離れる）"}
    if first:
        off, span = cands[first]
        out["first_point_minus_stamp_ms"] = describe(off * 1e3)
        out["span_in_frame_ms"] = describe(span * 1e3)
        out["note"] = "単位は値の大きさからの推定。float64 の絶対 ns は約 256 ns の刻みになる"
    return out


def imu_values(s: Series) -> dict:
    """静止の区間の加速度・角速度。加速度の単位は 1 と 9.80665 のどちらに近いか（対数の比）で示す。"""
    if s.count == 0:
        return {}
    acc, gyro = s.acc, s.gyro
    an = np.linalg.norm(acc, axis=1)
    gn = np.linalg.norm(gyro, axis=1)
    mean_vec = acc.mean(axis=0)
    norm_mean = float(an.mean())
    r1 = abs(math.log(norm_mean / 1.0)) if norm_mean > 0 else math.inf
    r9 = abs(math.log(norm_mean / G0)) if norm_mean > 0 else math.inf
    return {
        "samples": int(s.count),
        "accel_norm": describe(an),
        "accel_mean_vector": [float(v) for v in mean_vec],
        "accel_mean_vector_norm": float(np.linalg.norm(mean_vec)),
        "gyro_norm": describe(gn),
        "gyro_mean_vector": [float(v) for v in gyro.mean(axis=0)],
        "unit_guess": {
            "nearest": "g" if r1 < r9 else "m/s^2",
            "norm_mean": norm_mean,
            "norm_over_1": norm_mean / 1.0,
            "norm_over_9.80665": norm_mean / G0,
            "note": "判定ではなく、静止の区間のノルムが 1 と 9.80665 のどちらに近いかの表示（対数の比で比べる）",
        },
    }


# --------------------------------------------------------------------------- 判定

def verdict_rel(item: str, value, expected, tol_pct, arg_names: str, stat: str) -> dict:
    """value が expected の ±tol_pct % に入るか。基準が渡されなければ未判定。"""
    v = {"item": item, "value": value, "statistic": stat}
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        v.update(result=UNDECIDED, reason="値がない（データなし）")
    elif expected is None or tol_pct is None:
        v.update(result=UNDECIDED, reason=f"基準 tbd（{arg_names} が渡されていない）")
    else:
        lo, hi = expected * (1 - tol_pct / 100.0), expected * (1 + tol_pct / 100.0)
        v.update(result=PASS if lo <= value <= hi else FAIL,
                 criteria={"expected": expected, "tol_pct": tol_pct, "range": [lo, hi]})
    return v


def verdict_abs_max(item: str, value, limit, arg_names: str, stat: str) -> dict:
    """|value| <= limit か。基準が渡されなければ未判定。"""
    v = {"item": item, "value": value, "statistic": stat}
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        v.update(result=UNDECIDED, reason="値がない（データなし）")
    elif limit is None:
        v.update(result=UNDECIDED, reason=f"基準 tbd（{arg_names} が渡されていない）")
    else:
        v.update(result=PASS if abs(value) <= limit else FAIL, criteria={"abs_max": limit})
    return v


def need_pair(parser, args, a: str, b: str):
    va, vb = getattr(args, a), getattr(args, b)
    if (va is None) != (vb is None):
        parser.error(f"--{a.replace('_', '-')} と --{b.replace('_', '-')} は両方を渡す")


# --------------------------------------------------------------------------- 出力

def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return f if math.isfinite(f) else None
    if isinstance(o, np.ndarray):
        return _clean(o.tolist())
    return o


def emit(report: dict, json_out: Optional[str], as_json: bool, text_lines: List[str]):
    rep = _clean(report)
    if json_out:
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=2)
            f.write("\n")
    if as_json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print("\n".join(text_lines))


def fmt(d: Optional[dict], unit: str = "", digits: int = 3) -> str:
    if not d:
        return "なし"
    f = f"{{:.{digits}f}}"
    return (f"平均 {f.format(d['mean'])}{unit} 標準偏差 {f.format(d['std'])}{unit} 最小 {f.format(d['min'])}{unit} "
            f"最大 {f.format(d['max'])}{unit} p5 {f.format(d['p5'])} p50 {f.format(d['p50'])} p95 {f.format(d['p95'])} "
            f"p99 {f.format(d['p99'])}（n={d['n']}）")


def verdict_line(v: dict) -> str:
    val = v.get("value")
    sval = "なし" if val is None else (f"{val:.6g}" if isinstance(val, (int, float)) else str(val))
    extra = v.get("reason") or json.dumps(v.get("criteria"), ensure_ascii=False)
    return f"  [{v['result']}] {v['item']}：{sval}（{v['statistic']}）{extra}"


def bag_header(title: str, b: dict, extra: str = "") -> List[str]:
    L = [f"{title}（bag {b['name']}、{b['storage']}、読み取り {b['reader']}）{extra}"]
    if b.get("reader_note"):
        L.append(f"  注：{b['reader_note']}")
    if b.get("truncated_files"):
        L.append(f"  注意：途中で切れたファイル {b['truncated_files']}（読めたところまでで解析）")
    return L


def add_common_args(p):
    p.add_argument("bag", help="bag のディレクトリ（metadata.yaml と .mcap/.db3）か、1 つの .mcap/.db3")
    p.add_argument("--reader", choices=["auto", "rosbag2_py", "builtin"], default="auto",
                   help="auto：rosbag2_py があればそれ、なければ純 Python（既定 auto）")
    p.add_argument("--window", nargs=2, type=float, metavar=("START_S", "END_S"),
                   help="解析する区間（最初の受信からの秒、受信の時刻で切る）。既定は全体")
    p.add_argument("--json-out", help="結果の JSON を書くファイル（リポジトリの外に置く）")
    p.add_argument("--json", action="store_true", help="要約の代わりに JSON を標準出力に出す")
    p.add_argument("--sha256", action="store_true", help="bag のファイルの sha256 を出す（台帳の evidence 用）")


def bag_info(bag, sha: bool) -> dict:
    info = bagio.bag_summary(bag)
    if sha:
        info["sha256"] = {os.path.basename(f): bagio.file_sha256(f) for f in bag.files}
    return info
