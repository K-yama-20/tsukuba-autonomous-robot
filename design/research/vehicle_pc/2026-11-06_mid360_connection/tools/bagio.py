"""rosbag2 の読み取り（読むだけ）と、sensor_msgs の CDR の復号。

読み取りの方式（--reader）
- rosbag2_py：ROS 2 の rosbag2_py があればそれで読む（auto の既定）。受信の時刻（recv_timestamp）だけが得られる
- builtin：純 Python。MCAP（.mcap、圧縮なし・zstd・lz4 の chunk）と SQLite3（.db3）を読む。
  MCAP では publishTime（rosbag2 の send_timestamp）も得られる
どちらの方式でも、メッセージの本体（CDR）の復号はこのファイルの関数で行う（方式で結果が変わらないように）。

rosbag2 の時刻（ros2/rosbag2 jazzy 12b5e8b のソースで確認。README の出典）
- recv_timestamp：記録した側（ros2 bag record）が受け取った時刻。use_sim_time なしでは rmw の received_timestamp
- send_timestamp：送り手の source_timestamp。MCAP の publishTime に入る。SQLite3 には残らない
"""
from __future__ import annotations

import glob
import os
import pathlib
import sqlite3
import struct
import zlib
from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, List, Optional, Sequence

import numpy as np

MCAP_MAGIC = b"\x89MCAP0\r\n"
SQLITE_MAGIC = b"SQLite format 3\x00"

TYPE_POINTCLOUD2 = "sensor_msgs/msg/PointCloud2"
TYPE_IMU = "sensor_msgs/msg/Imu"


class BagError(RuntimeError):
    pass


@dataclass
class BagMessage:
    topic: str
    msgtype: str
    recv_ns: int                 # rosbag2 の recv_timestamp（MCAP の logTime、SQLite3 の timestamp）
    publish_ns: Optional[int]    # rosbag2 の send_timestamp（MCAP の publishTime）。得られない方式では None
    data: bytes                  # CDR（4 byte の encapsulation header つき）
    order: int                   # 記録の中の並び（同じ recv_ns の並べ替えに使う）


# --------------------------------------------------------------------------- 入口

def open_bag(path: str, reader: str = "auto"):
    """bag のディレクトリ（metadata.yaml と .mcap/.db3）か、1 つの .mcap/.db3 を開く。"""
    if reader not in ("auto", "rosbag2_py", "builtin"):
        raise BagError(f"unknown reader: {reader}")
    if reader in ("auto", "rosbag2_py"):
        try:
            import rosbag2_py  # noqa: F401
        except ImportError:
            if reader == "rosbag2_py":
                raise BagError("rosbag2_py が import できない（ROS 2 の環境を source したか。python3 -I では PYTHONPATH が効かない）")
            bag = BuiltinBag(path)
            bag.fallback = "rosbag2_py が import できないので純 Python で読んだ"
            return bag
        return Rosbag2PyBag(path)
    return BuiltinBag(path)


def _storage_files(path: str):
    """(storage, [files]) を返す。storage は 'mcap' か 'sqlite3'。"""
    p = pathlib.Path(path)
    if p.is_file():
        return _detect_file(p), [str(p)]
    if not p.is_dir():
        raise BagError(f"bag が見つからない: {path}")
    files: List[str] = []
    storage = None
    meta = p / "metadata.yaml"
    if meta.exists():
        try:
            import yaml  # PyYAML（ROS 2 の環境には入っている）
            info = yaml.safe_load(meta.read_text()).get("rosbag2_bagfile_information", {})
            storage = info.get("storage_identifier") or None
            files = [str(p / f) for f in info.get("relative_file_paths", [])]
        except ImportError:
            pass
    if not files:
        files = sorted(glob.glob(str(p / "*.mcap"))) + sorted(glob.glob(str(p / "*.db3")))
    if not files:
        raise BagError(f".mcap も .db3 もない: {path}")
    kinds = {_detect_file(pathlib.Path(f)) for f in files}
    if len(kinds) != 1:
        raise BagError(f"形式の違うファイルが混ざっている: {sorted(kinds)}")
    kind = kinds.pop()
    if storage and storage != kind:
        raise BagError(f"metadata.yaml の storage_identifier={storage} とファイルの中身（{kind}）が違う")
    return kind, files


def _detect_file(p: pathlib.Path) -> str:
    with open(p, "rb") as f:
        head = f.read(16)
    if head.startswith(MCAP_MAGIC):
        return "mcap"
    if head.startswith(SQLITE_MAGIC):
        return "sqlite3"
    if p.suffix in (".zstd", ".lz4"):
        raise BagError(f"ファイル単位の圧縮（{p.name}）は読めない。ros2 bag decompress などで戻してから使う")
    raise BagError(f"MCAP でも SQLite3 でもない: {p.name}")


# --------------------------------------------------------------------------- rosbag2_py

class Rosbag2PyBag:
    backend = "rosbag2_py"

    def __init__(self, path: str):
        import rosbag2_py
        self._rb = rosbag2_py
        self.path = path
        self.storage, self.files = _storage_files(path)
        self._types = None

    def _open(self):
        rb = self._rb
        r = rb.SequentialReader()
        r.open(rb.StorageOptions(uri=self.path, storage_id=""),
               rb.ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr"))
        return r

    def topics(self) -> Dict[str, str]:
        if self._types is None:
            r = self._open()
            self._types = {t.name: t.type for t in r.get_all_topics_and_types()}
            del r
        return dict(self._types)

    def messages(self, topics: Optional[Iterable[str]] = None) -> Iterator[BagMessage]:
        types = self.topics()
        r = self._open()
        if topics is not None:
            want = [t for t in topics if t in types]
            if not want:
                return
            r.set_filter(self._rb.StorageFilter(topics=want))
        i = 0
        while r.has_next():
            topic, data, t = r.read_next()
            yield BagMessage(topic, types.get(topic, "?"), int(t), None, bytes(data), i)
            i += 1


# --------------------------------------------------------------------------- 純 Python

class BuiltinBag:
    backend = "builtin"

    def __init__(self, path: str):
        self.path = path
        self.storage, self.files = _storage_files(path)
        self.truncated_files: List[str] = []
        self._types = None

    def topics(self) -> Dict[str, str]:
        if self._types is None:
            types: Dict[str, str] = {}
            for f in self.files:
                if self.storage == "mcap":
                    for topic, typ, _enc in _mcap_channels(f):
                        types[topic] = typ
                else:
                    with _sqlite_open(f) as con:
                        for name, typ, _fmt in con.execute("SELECT name, type, serialization_format FROM topics"):
                            types[name] = typ
            self._types = types
        return dict(self._types)

    def messages(self, topics: Optional[Iterable[str]] = None) -> Iterator[BagMessage]:
        want = set(topics) if topics is not None else None
        order = 0
        for f in self.files:
            it = _mcap_messages(f, want, self) if self.storage == "mcap" else _sqlite_messages(f, want)
            for topic, typ, recv, pub, data in it:
                yield BagMessage(topic, typ, recv, pub, data, order)
                order += 1


# ---- MCAP（https://mcap.dev/spec）

def _u16(b, o): return struct.unpack_from("<H", b, o)[0]
def _u32(b, o): return struct.unpack_from("<I", b, o)[0]
def _u64(b, o): return struct.unpack_from("<Q", b, o)[0]


def _mstr(b, o):
    n = _u32(b, o)
    return b[o + 4:o + 4 + n].decode("utf-8", "replace"), o + 4 + n


def _iter_records(buf: bytes):
    o, n = 0, len(buf)
    while o + 9 <= n:
        op = buf[o]
        ln = _u64(buf, o + 1)
        yield op, buf[o + 9:o + 9 + ln]
        o += 9 + ln


def _decompress(comp: str, data: bytes, size: int) -> bytes:
    if comp == "":
        return data
    if comp == "zstd":
        try:
            import zstandard
        except ImportError:
            raise BagError("zstd で圧縮された MCAP の chunk を読むには zstandard（python3-zstandard）が要る")
        return zstandard.ZstdDecompressor().decompress(data, max_output_size=size)
    if comp == "lz4":
        try:
            import lz4.frame
        except ImportError:
            raise BagError("lz4 で圧縮された MCAP の chunk を読むには lz4（python3-lz4）が要る")
        return lz4.frame.decompress(data)
    raise BagError(f"MCAP の chunk の圧縮方式 {comp!r} に対応していない")


def _mark_truncated(owner, path):
    name = os.path.basename(path)
    if owner is not None and name not in owner.truncated_files:
        owner.truncated_files.append(name)


def _mcap_walk(path: str, owner=None):
    """データ部の record を (op, body) で順に返す。chunk は展開して中の record を返す。
    Footer の前で終わっている（記録が途中で切れた）ファイルは、読めたところまでを返し、owner に印を付ける。"""
    with open(path, "rb") as f:
        if f.read(8) != MCAP_MAGIC:
            raise BagError(f"MCAP の magic がない: {os.path.basename(path)}")
        while True:
            h = f.read(9)
            if len(h) < 9:
                _mark_truncated(owner, path)
                return
            op, ln = h[0], struct.unpack("<Q", h[1:])[0]
            body = f.read(ln)
            if len(body) < ln:
                _mark_truncated(owner, path)
                return
            if op == 0x06:  # Chunk
                usize = _u64(body, 16)
                crc = _u32(body, 24)
                comp, o = _mstr(body, 28)
                rlen = _u64(body, o)
                data = _decompress(comp, body[o + 8:o + 8 + rlen], usize)
                if crc != 0 and (zlib.crc32(data) & 0xFFFFFFFF) != crc:
                    raise BagError(f"MCAP の chunk の CRC が合わない: {os.path.basename(path)}")
                yield from _iter_records(data)
            elif op in (0x0F, 0x02):  # DataEnd / Footer：ここから先は summary（メッセージはない）
                return
            else:
                yield op, body


def _mcap_channels(path: str):
    schemas, out = {}, []
    for op, body in _mcap_walk(path):
        if op == 0x03:
            sid = _u16(body, 0)
            name, _ = _mstr(body, 2)
            schemas[sid] = name
        elif op == 0x04:
            cid, sid = _u16(body, 0), _u16(body, 2)
            topic, o = _mstr(body, 4)
            enc, o = _mstr(body, o)
            out.append((topic, schemas.get(sid, "?"), enc))
    return out


def _mcap_messages(path: str, want, owner):
    schemas: Dict[int, str] = {}
    chans: Dict[int, tuple] = {}
    for op, body in _mcap_walk(path, owner):
        if op == 0x03:  # Schema
            sid = _u16(body, 0)
            name, _ = _mstr(body, 2)
            schemas[sid] = name
        elif op == 0x04:  # Channel
            cid, sid = _u16(body, 0), _u16(body, 2)
            topic, o = _mstr(body, 4)
            enc, o = _mstr(body, o)
            chans[cid] = (topic, schemas.get(sid, "?"), enc)
        elif op == 0x05:  # Message
            cid = _u16(body, 0)
            topic, typ, enc = chans.get(cid, ("?", "?", "?"))
            if want is not None and topic not in want:
                continue
            if enc != "cdr":
                raise BagError(f"{topic} の message_encoding が cdr でない（{enc}）")
            log_t = _u64(body, 6)
            pub_t = _u64(body, 14)
            yield topic, typ, log_t, pub_t, body[22:]


# ---- SQLite3（rosbag2_storage_sqlite3）

def _sqlite_open(path: str):
    uri = pathlib.Path(path).absolute().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _sqlite_messages(path: str, want):
    con = _sqlite_open(path)
    try:
        topics = {tid: (name, typ, fmt) for tid, name, typ, fmt in
                  con.execute("SELECT id, name, type, serialization_format FROM topics")}
        ids = [tid for tid, (name, _t, _f) in topics.items() if want is None or name in want]
        if not ids:
            return
        for tid in ids:
            if topics[tid][2] != "cdr":
                raise BagError(f"{topics[tid][0]} の serialization_format が cdr でない（{topics[tid][2]}）")
        q = ("SELECT topic_id, timestamp, data FROM messages WHERE topic_id IN (%s) ORDER BY timestamp, id"
             % ",".join("?" * len(ids)))
        for tid, ts, data in con.execute(q, ids):
            name, typ, _fmt = topics[tid]
            yield name, typ, int(ts), None, bytes(data)
    finally:
        con.close()


# --------------------------------------------------------------------------- CDR（XCDR1）

class Cdr:
    """ROS 2 の CDR を読む。整列は 4 byte の encapsulation header の後から数える。"""

    def __init__(self, b: bytes):
        if len(b) < 4:
            raise BagError("CDR が短すぎる")
        rep = b[1]
        if b[0] != 0 or rep not in (0, 1):
            raise BagError(f"CDR の encapsulation {b[:2].hex()} に対応していない（XCDR1 の BE/LE だけ）")
        self.e = "<" if rep == 1 else ">"
        self.b = b
        self.o = 4

    def align(self, n):
        r = (self.o - 4) % n
        if r:
            self.o += n - r

    def _get(self, fmt, size):
        self.align(size)
        v = struct.unpack_from(self.e + fmt, self.b, self.o)[0]
        self.o += size
        return v

    def u8(self):
        v = self.b[self.o]
        self.o += 1
        return v

    def i32(self): return self._get("i", 4)
    def u32(self): return self._get("I", 4)

    def f64s(self, n):
        self.align(8)
        v = struct.unpack_from(self.e + "%dd" % n, self.b, self.o)
        self.o += 8 * n
        return v

    def string(self):
        n = self.u32()
        s = self.b[self.o:self.o + max(n - 1, 0)].decode("utf-8", "replace")
        self.o += n
        return s

    def header(self):
        sec = self.i32()
        nsec = self.u32()
        return sec * 1_000_000_000 + nsec, self.string()


POINTFIELD_TYPES = {1: ("INT8", "i1"), 2: ("UINT8", "u1"), 3: ("INT16", "i2"), 4: ("UINT16", "u2"),
                    5: ("INT32", "i4"), 6: ("UINT32", "u4"), 7: ("FLOAT32", "f4"), 8: ("FLOAT64", "f8")}


@dataclass
class CloudMeta:
    stamp_ns: int
    frame_id: str
    height: int
    width: int
    fields: List[tuple]   # (name, offset, datatype, count)
    is_bigendian: bool
    point_step: int
    row_step: int
    data_offset: int
    data_len: int
    is_dense: bool

    @property
    def n_points(self) -> int:
        return self.height * self.width


def decode_cloud_meta(data: bytes) -> CloudMeta:
    c = Cdr(data)
    stamp, fid = c.header()
    h, w = c.u32(), c.u32()
    nf = c.u32()
    fields = []
    for _ in range(nf):
        name = c.string()
        off = c.u32()
        dt = c.u8()
        cnt = c.u32()
        fields.append((name, off, dt, cnt))
    big = bool(c.u8())
    step, row = c.u32(), c.u32()
    n = c.u32()
    doff = c.o
    c.o += n
    dense = bool(c.b[c.o]) if c.o < len(c.b) else True
    return CloudMeta(stamp, fid, h, w, fields, big, step, row, doff, n, dense)


def cloud_columns(data: bytes, meta: CloudMeta, names: Sequence[str]) -> Dict[str, np.ndarray]:
    """点の field を列で取り出す（count 1 の field のみ）。"""
    npts = meta.n_points
    if npts == 0:
        return {k: np.zeros(0) for k in names}
    if meta.data_len < npts * meta.point_step:
        raise BagError("PointCloud2 の data が height*width*point_step より短い")
    byte_order = ">" if meta.is_bigendian else "<"
    fmap = {f[0]: f for f in meta.fields}
    dt_names, dt_formats, dt_offsets = [], [], []
    for k in names:
        if k not in fmap:
            raise BagError(f"PointCloud2 に field {k!r} がない（あるのは {[f[0] for f in meta.fields]}）")
        _n, off, dt, cnt = fmap[k]
        if cnt != 1:
            raise BagError(f"field {k!r} の count が 1 でない（{cnt}）")
        dt_names.append(k)
        dt_formats.append(byte_order + POINTFIELD_TYPES[dt][1])
        dt_offsets.append(off)
    dtype = np.dtype({"names": dt_names, "formats": dt_formats, "offsets": dt_offsets,
                      "itemsize": meta.point_step})
    arr = np.frombuffer(data, dtype=dtype, count=npts, offset=meta.data_offset)
    return {k: arr[k].astype(np.float64) for k in names}


@dataclass
class ImuSample:
    stamp_ns: int
    frame_id: str
    orientation: tuple
    angular_velocity: tuple
    linear_acceleration: tuple


def decode_imu(data: bytes) -> ImuSample:
    c = Cdr(data)
    stamp, fid = c.header()
    q = c.f64s(4)
    c.f64s(9)
    w = c.f64s(3)
    c.f64s(9)
    a = c.f64s(3)
    return ImuSample(stamp, fid, q, w, a)


def decode_header(data: bytes):
    """先頭が std_msgs/Header の型なら (stamp_ns, frame_id)。"""
    return Cdr(data).header()


def bag_summary(bag) -> dict:
    """出力に載せる bag の情報（ファイル名だけ。ディレクトリのパスは書かない）。"""
    return {
        "name": os.path.basename(os.path.normpath(bag.path)),
        "storage": bag.storage,
        "reader": bag.backend,
        "files": [os.path.basename(f) for f in bag.files],
        "truncated_files": list(getattr(bag, "truncated_files", [])),
        "reader_note": getattr(bag, "fallback", None),
    }


def file_sha256(path: str) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()
