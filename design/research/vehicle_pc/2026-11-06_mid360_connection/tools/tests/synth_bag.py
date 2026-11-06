"""テスト用の合成 bag を書く（MCAP と SQLite3）。読み取り側（bagio.py）のコードは使わない。

- CDR の符号化、MCAP の record、SQLite3 の表は、このファイルで独立に書く
- 合成の条件（周期・揺れ・遅れ・傾き）を Truth に残し、テストの期待値はそこから決める
"""
from __future__ import annotations

import math
import sqlite3
import struct
import zlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

T_BASE_NS = 1_762_400_000 * 1_000_000_000  # 合成の時刻の起点（2025-11 ごろの UNIX 時刻）

# ---------------------------------------------------------------------------- CDR


class CdrWriter:
    def __init__(self, big: bool = False):
        self.e = ">" if big else "<"
        self.buf = bytearray(b"\x00\x00\x00\x00" if big else b"\x00\x01\x00\x00")

    def _align(self, n):
        self.buf += b"\x00" * ((-(len(self.buf) - 4)) % n)

    def u8(self, v):
        self.buf += struct.pack("B", v)

    def u32(self, v):
        self._align(4)
        self.buf += struct.pack(self.e + "I", v)

    def i32(self, v):
        self._align(4)
        self.buf += struct.pack(self.e + "i", v)

    def f64(self, *vs):
        self._align(8)
        self.buf += struct.pack(self.e + "%dd" % len(vs), *vs)

    def string(self, s: str):
        b = s.encode() + b"\x00"
        self.u32(len(b))
        self.buf += b

    def octets(self, b: bytes):
        self.u32(len(b))
        self.buf += b

    def header(self, stamp_ns: int, frame_id: str):
        self.i32(stamp_ns // 1_000_000_000)
        self.u32(stamp_ns % 1_000_000_000)
        self.string(frame_id)


LIVOX_DTYPE = np.dtype({"names": ["x", "y", "z", "intensity", "tag", "line", "timestamp"],
                        "formats": ["<f4", "<f4", "<f4", "<f4", "u1", "u1", "<f8"],
                        "offsets": [0, 4, 8, 12, 16, 17, 18], "itemsize": 26})
LIVOX_FIELDS = [("x", 0, 7, 1), ("y", 4, 7, 1), ("z", 8, 7, 1), ("intensity", 12, 7, 1), ("tag", 16, 2, 1),
                ("line", 17, 2, 1), ("timestamp", 18, 8, 1)]
XYZI_DTYPE = np.dtype({"names": ["x", "y", "z", "intensity"], "formats": ["<f4"] * 4, "offsets": [0, 4, 8, 12],
                       "itemsize": 16})
XYZI_FIELDS = [("x", 0, 7, 1), ("y", 4, 7, 1), ("z", 8, 7, 1), ("intensity", 12, 7, 1)]


def enc_cloud(stamp_ns: int, frame_id: str, pts: np.ndarray, fields, big: bool = False) -> bytes:
    w = CdrWriter(big)
    w.header(stamp_ns, frame_id)
    w.u32(1)
    w.u32(len(pts))
    w.u32(len(fields))
    for name, off, dt, cnt in fields:
        w.string(name)
        w.u32(off)
        w.u8(dt)
        w.u32(cnt)
    w.u8(1 if big else 0)
    step = pts.dtype.itemsize
    w.u32(step)
    w.u32(step * len(pts))
    data = pts.astype(pts.dtype.newbyteorder(">")).tobytes() if big else pts.tobytes()
    w.octets(data)
    w.u8(1)
    return bytes(w.buf)


def enc_imu(stamp_ns: int, frame_id: str, gyro, acc, big: bool = False) -> bytes:
    w = CdrWriter(big)
    w.header(stamp_ns, frame_id)
    w.f64(0.0, 0.0, 0.0, 1.0)
    w.f64(*([0.0] * 9))
    w.f64(*gyro)
    w.f64(*([0.0] * 9))
    w.f64(*acc)
    w.f64(*([0.0] * 9))
    return bytes(w.buf)


def enc_temperature(stamp_ns: int, frame_id: str, value: float) -> bytes:
    w = CdrWriter()
    w.header(stamp_ns, frame_id)
    w.f64(value, 0.0)
    return bytes(w.buf)


# ---------------------------------------------------------------------------- 書き出し

@dataclass
class Msg:
    topic: str
    msgtype: str
    recv_ns: int
    pub_ns: int
    data: bytes


def _rec(op: int, body: bytes) -> bytes:
    return struct.pack("<BQ", op, len(body)) + body


def _s(x: str) -> bytes:
    b = x.encode()
    return struct.pack("<I", len(b)) + b


def write_mcap(path: str, msgs: List[Msg], chunk_size: Optional[int] = 200, compression: str = "",
               bad_crc: bool = False, message_index: bool = True):
    """chunk_size=None なら chunk なし。compression は '' / 'zstd' / 'lz4'。"""
    topics = list(dict.fromkeys((m.topic, m.msgtype) for m in msgs))
    sids = {t: i + 1 for i, t in enumerate(dict.fromkeys(ty for _t, ty in topics))}
    cids = {t: i + 1 for i, (t, _ty) in enumerate(topics)}
    defs = b""
    for ty, sid in sids.items():
        defs += _rec(0x03, struct.pack("<H", sid) + _s(ty) + _s("ros2msg") + struct.pack("<I", 0))
    for (t, ty) in topics:
        defs += _rec(0x04, struct.pack("<HH", cids[t], sids[ty]) + _s(t) + _s("cdr") + struct.pack("<I", 0))
    out = bytearray(b"\x89MCAP0\r\n")
    out += _rec(0x01, _s("ros2") + _s("synth_bag"))
    seq = {}

    def message(m):
        seq[m.topic] = seq.get(m.topic, 0) + 1
        return _rec(0x05, struct.pack("<HIQQ", cids[m.topic], seq[m.topic], m.recv_ns, m.pub_ns) + m.data)

    if chunk_size is None:
        out += defs
        for m in msgs:
            out += message(m)
    else:
        first = True
        for k in range(0, len(msgs), chunk_size):
            part = msgs[k:k + chunk_size]
            recs = (defs if first else b"") + b"".join(message(m) for m in part)
            first = False
            crc = zlib.crc32(recs) & 0xFFFFFFFF
            if bad_crc:
                crc ^= 0x1
            if compression == "zstd":
                import zstandard
                comp = zstandard.ZstdCompressor().compress(recs)
            elif compression == "lz4":
                import lz4.frame
                comp = lz4.frame.compress(recs)
            else:
                comp = recs
            body = (struct.pack("<QQQI", part[0].recv_ns, part[-1].recv_ns, len(recs), crc) + _s(compression)
                    + struct.pack("<Q", len(comp)) + comp)
            out += _rec(0x06, body)
            if message_index:  # 中身は読み取り側が使わない（読み飛ばせることを見る）
                out += _rec(0x07, struct.pack("<HI", 1, 0))
    out += _rec(0x0F, struct.pack("<I", 0))
    out += defs  # summary の Schema・Channel（読み取り側は DataEnd で止まる）
    out += _rec(0x02, struct.pack("<QQI", 0, 0, 0))
    out += b"\x89MCAP0\r\n"
    with open(path, "wb") as f:
        f.write(out)


def write_db3(path: str, msgs: List[Msg]):
    """rosbag2_storage_sqlite3（Jazzy）の表の形で書く。"""
    con = sqlite3.connect(path)
    c = con.cursor()
    c.execute("CREATE TABLE schema(schema_version INTEGER PRIMARY KEY,ros_distro TEXT NOT NULL);")
    c.execute("CREATE TABLE metadata(id INTEGER PRIMARY KEY,metadata_version INTEGER NOT NULL,metadata TEXT NOT NULL);")
    c.execute("CREATE TABLE topics(id INTEGER PRIMARY KEY,name TEXT NOT NULL,type TEXT NOT NULL,"
              "serialization_format TEXT NOT NULL,offered_qos_profiles TEXT NOT NULL,type_description_hash TEXT NOT NULL);")
    c.execute("CREATE TABLE message_definitions(id INTEGER PRIMARY KEY,topic_type TEXT NOT NULL,encoding TEXT NOT NULL,"
              "encoded_message_definition TEXT NOT NULL,type_description_hash TEXT NOT NULL);")
    c.execute("CREATE TABLE messages(id INTEGER PRIMARY KEY,topic_id INTEGER NOT NULL,timestamp INTEGER NOT NULL, "
              "data BLOB NOT NULL);")
    c.execute("CREATE INDEX timestamp_idx ON messages (timestamp ASC);")
    c.execute("INSERT INTO schema VALUES (4, 'jazzy')")
    topics = list(dict.fromkeys((m.topic, m.msgtype) for m in msgs))
    ids = {}
    for i, (t, ty) in enumerate(topics, 1):
        c.execute("INSERT INTO topics VALUES (?,?,?,?,?,?)", (i, t, ty, "cdr", "", ""))
        ids[t] = i
    c.executemany("INSERT INTO messages (topic_id, timestamp, data) VALUES (?,?,?)",
                  [(ids[m.topic], m.recv_ns, m.data) for m in msgs])
    con.commit()
    con.close()


def write_metadata(dirpath: str, storage: str, files: List[str]):
    lines = ["rosbag2_bagfile_information:", "  version: 9", f"  storage_identifier: {storage}",
             "  relative_file_paths:"] + [f"    - {f}" for f in files]
    with open(f"{dirpath}/metadata.yaml", "w") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------- 合成の条件


@dataclass
class Truth:
    cloud_stamp_ns: np.ndarray = None
    cloud_recv_ns: np.ndarray = None
    cloud_pub_ns: np.ndarray = None
    cloud_npts: np.ndarray = None
    point_interval_ns: int = 0
    imu_stamp_ns: np.ndarray = None
    imu_recv_ns: np.ndarray = None
    imu_acc: np.ndarray = None
    xt_stamp_ns: np.ndarray = None
    xt_recv_ns: np.ndarray = None
    roll_true: float = 0.0       # 地面に対するセンサーの傾き（方法 1 の正解）
    pitch_true: float = 0.0
    roll_imu: float = 0.0        # IMU の重力の向きの傾き（方法 2 の正解）
    pitch_imu: float = 0.0
    height_m: float = 0.0
    params: Dict = field(default_factory=dict)


def rot_rpy(r_deg, p_deg, y_deg=0.0):
    r, p, y = (math.radians(v) for v in (r_deg, p_deg, y_deg))
    rx = np.array([[1, 0, 0], [0, math.cos(r), -math.sin(r)], [0, math.sin(r), math.cos(r)]])
    ry = np.array([[math.cos(p), 0, math.sin(p)], [0, 1, 0], [-math.sin(p), 0, math.cos(p)]])
    rz = np.array([[math.cos(y), -math.sin(y), 0], [math.sin(y), math.cos(y), 0], [0, 0, 1]])
    return rz @ ry @ rx


def scene_points(rng, n: int, R: np.ndarray, height: float, outlier_ratio: float, noise_m: float):
    """水平な座標で地面（z=-height）・壁・空中のごみを作り、センサーの座標（R^T）に移す。"""
    n_out = int(round(n * outlier_ratio))
    n_g = n - n_out
    g = np.column_stack([rng.uniform(-6, 6, n_g), rng.uniform(-6, 6, n_g), -height + rng.normal(0, noise_m, n_g)])
    n_wall = n_out // 2
    wall = np.column_stack([4.0 + rng.normal(0, noise_m, n_wall), rng.uniform(-6, 6, n_wall),
                            rng.uniform(-height, 2.0, n_wall)])
    n_rand = n_out - n_wall
    junk = np.column_stack([rng.uniform(-6, 6, n_rand), rng.uniform(-6, 6, n_rand), rng.uniform(-height + 0.2, 2.0, n_rand)])
    P = np.vstack([g, wall, junk])
    P = P[rng.permutation(len(P))]
    return P @ R  # 各行 p_s = R^T p_l


def make_scenario(seed: int = 0, frames: int = 100, imu_hz: float = 200.0, accel_scale: float = 1.0,
                  cloud_frame: str = "livox_frame", imu_frame: str = "livox_frame", with_xt: bool = True,
                  backward_at: Optional[int] = None, duplicate_at: Optional[int] = None,
                  with_temperature_topic: bool = False, cloud_topic: str = "/livox/lidar",
                  imu_topic: str = "/livox/imu", xt_topic: str = "/sensors/xt32/points", big: bool = False,
                  points_base: int = 1500) -> Tuple[List[Msg], Truth]:
    rng = np.random.default_rng(seed)
    tr = Truth()
    tr.roll_true, tr.pitch_true, tr.height_m = 2.0, -35.0, 0.60
    tr.roll_imu, tr.pitch_imu = tr.roll_true + 0.20, tr.pitch_true - 0.10
    R = rot_rpy(tr.roll_true, tr.pitch_true)
    R_imu = rot_rpy(tr.roll_imu, tr.pitch_imu)
    period_ns = 100_000_000
    lat0_ns, drift_ns_per_s = 105_000_000, 500_000  # 受信 − stamp：105 ms から 0.5 ms/s（30 ms/分）で増える
    i = np.arange(frames)
    stamp = T_BASE_NS + i * period_ns + np.round(rng.normal(0, 0.5e6, frames)).astype(np.int64)
    if backward_at is not None:
        stamp[backward_at] = stamp[backward_at - 1] - 5_000_000
    if duplicate_at is not None:
        stamp[duplicate_at] = stamp[duplicate_at - 1]
    t_s = (i * period_ns) * 1e-9
    recv = (T_BASE_NS + i * period_ns + lat0_ns + np.round(drift_ns_per_s * t_s).astype(np.int64)
            + np.round(rng.normal(0, 0.3e6, frames)).astype(np.int64))
    pub = recv - 1_000_000 - np.round(rng.uniform(0, 0.2e6, frames)).astype(np.int64)
    npts = points_base + (i % 7) * 10
    tr.point_interval_ns = 40_000
    tr.cloud_stamp_ns, tr.cloud_recv_ns, tr.cloud_pub_ns, tr.cloud_npts = stamp, recv, pub, npts
    tr.params = {"period_ns": period_ns, "lat0_ns": lat0_ns, "drift_ms_per_min": drift_ns_per_s * 60 / 1e6}
    msgs: List[Msg] = []
    for k in range(frames):
        P = scene_points(rng, int(npts[k]), R, tr.height_m, outlier_ratio=0.3, noise_m=0.01)
        a = np.zeros(len(P), dtype=LIVOX_DTYPE)
        a["x"], a["y"], a["z"] = P[:, 0], P[:, 1], P[:, 2]
        a["intensity"] = 50.0
        a["line"] = np.arange(len(P)) % 4
        a["timestamp"] = (stamp[k] + np.arange(len(P), dtype=np.int64) * tr.point_interval_ns).astype(np.float64)
        msgs.append(Msg(cloud_topic, "sensor_msgs/msg/PointCloud2", int(recv[k]), int(pub[k]),
                        enc_cloud(int(stamp[k]), cloud_frame, a, LIVOX_FIELDS, big)))
    # IMU
    n_imu = int(round(frames * period_ns * 1e-9 * imu_hz))
    j = np.arange(n_imu)
    imu_period = int(round(1e9 / imu_hz))
    istamp = T_BASE_NS + 2_000_000 + j * imu_period + np.round(rng.normal(0, 0.1e6, n_imu)).astype(np.int64)
    irecv = istamp + 1_500_000 + np.round(rng.uniform(0, 0.4e6, n_imu)).astype(np.int64)
    up = R_imu.T @ np.array([0.0, 0.0, 1.0])
    acc = (up[None, :] + rng.normal(0, 0.002, (n_imu, 3))) * accel_scale
    gyro = rng.normal(0, 0.001, (n_imu, 3))
    tr.imu_stamp_ns, tr.imu_recv_ns, tr.imu_acc = istamp, irecv, acc
    for k in range(n_imu):
        msgs.append(Msg(imu_topic, "sensor_msgs/msg/Imu", int(irecv[k]), int(irecv[k] - 300_000),
                        enc_imu(int(istamp[k]), imu_frame, gyro[k], acc[k], big)))
    if with_xt:
        xstamp = T_BASE_NS + 23_000_000 + i * period_ns + np.round(rng.normal(0, 0.3e6, frames)).astype(np.int64)
        xrecv = xstamp + 30_000_000 + np.round(rng.uniform(0, 2e6, frames)).astype(np.int64)
        tr.xt_stamp_ns, tr.xt_recv_ns = xstamp, xrecv
        for k in range(frames):
            q = np.zeros(10, dtype=XYZI_DTYPE)
            q["x"] = np.arange(10)
            msgs.append(Msg(xt_topic, "sensor_msgs/msg/PointCloud2", int(xrecv[k]), int(xrecv[k] - 500_000),
                            enc_cloud(int(xstamp[k]), "xt32_link", q, XYZI_FIELDS, big)))
    if with_temperature_topic:
        msgs.append(Msg("/livox/temperature", "sensor_msgs/msg/Temperature", int(recv[0]), int(recv[0]),
                        enc_temperature(int(stamp[0]), cloud_frame, 30.0)))
    msgs.sort(key=lambda m: m.recv_ns)
    return msgs, tr
