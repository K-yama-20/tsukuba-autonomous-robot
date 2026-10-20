"""Minimal reader for rosbag2 MCAP files (no external packages): iterates (topic, log_time_ns, cdr_bytes).
Supports uncompressed, zstd and lz4 chunks. CDR decoders for sensor_msgs/Imu and sensor_msgs/PointCloud2 (xyz float32 + others)."""
import struct, numpy as np

MAGIC = b'\x89MCAP0\r\n'


def _str(b, o):
    n = struct.unpack_from('<I', b, o)[0]; return b[o + 4:o + 4 + n].decode('utf-8', 'replace'), o + 4 + n


def _records(buf):
    o = 0; n = len(buf)
    while o + 9 <= n:
        op = buf[o]; ln = struct.unpack_from('<Q', buf, o + 1)[0]
        yield op, buf[o + 9:o + 9 + ln]; o += 9 + ln


def read(path, topics=None, schemas_out=None):
    """Yield (topic, log_time_ns, data) for messages of `topics` (None = all)."""
    channels = {}; schemas = {}
    with open(path, 'rb') as f:
        assert f.read(8) == MAGIC
        while True:
            h = f.read(9)
            if len(h) < 9: return
            op = h[0]; ln = struct.unpack('<Q', h[1:])[0]
            if op == 6:   # chunk
                head = f.read(32); comp_len = struct.unpack_from('<I', head, 28)[0]
                comp = f.read(comp_len).decode(); rec_len = struct.unpack('<Q', f.read(8))[0]
                data = f.read(rec_len)
                if comp == 'zstd':
                    import zstandard; data = zstandard.ZstdDecompressor().decompress(data, max_output_size=struct.unpack_from('<Q', head, 16)[0])
                elif comp == 'lz4':
                    import lz4.frame; data = lz4.frame.decompress(data)
                elif comp:
                    raise ValueError(comp)
                for op2, body in _records(data):
                    yield from _handle(op2, body, channels, schemas, topics, schemas_out)
            elif op == 2:  # footer
                return
            else:
                body = f.read(ln)
                yield from _handle(op, body, channels, schemas, topics, schemas_out)


def _handle(op, body, channels, schemas, topics, schemas_out):
    if op == 3:
        sid = struct.unpack_from('<H', body, 0)[0]; name, o = _str(body, 2); enc, o = _str(body, o)
        n = struct.unpack_from('<I', body, o)[0]; schemas[sid] = (name, body[o + 4:o + 4 + n].decode('utf-8', 'replace'))
        if schemas_out is not None: schemas_out[name] = schemas[sid][1]
    elif op == 4:
        cid, sid = struct.unpack_from('<HH', body, 0); topic, o = _str(body, 4)
        channels[cid] = (topic, schemas.get(sid, ('?', ''))[0])
    elif op == 5:
        cid, seq, lt, pt = struct.unpack_from('<HIQQ', body, 0)
        topic = channels.get(cid, ('?',))[0]
        if topics is None or topic in topics:
            yield topic, lt, body[22:]


# ---------------------------------------------------------------- CDR (little endian, after the 4-byte encapsulation header)
class Cdr:
    def __init__(self, b):
        self.b = b; self.o = 4
    def al(self, n):
        r = (self.o - 4) % n
        if r: self.o += n - r
    def u32(self):
        self.al(4); v = struct.unpack_from('<I', self.b, self.o)[0]; self.o += 4; return v
    def i32(self):
        self.al(4); v = struct.unpack_from('<i', self.b, self.o)[0]; self.o += 4; return v
    def u8(self):
        v = self.b[self.o]; self.o += 1; return v
    def f64s(self, n):
        self.al(8); v = struct.unpack_from('<%dd' % n, self.b, self.o); self.o += 8 * n; return v
    def string(self):
        n = self.u32(); s = self.b[self.o:self.o + n - 1].decode('utf-8', 'replace'); self.o += n; return s
    def header(self):
        sec = self.i32(); ns = self.u32(); fid = self.string(); return sec + ns * 1e-9, fid


def imu(b):
    c = Cdr(b); stamp, fid = c.header()
    q = c.f64s(4); c.f64s(9); w = c.f64s(3); c.f64s(9); a = c.f64s(3)
    return stamp, q, w, a


def cloud(b, want=('x', 'y', 'z')):
    c = Cdr(b); stamp, fid = c.header()
    h = c.u32(); w = c.u32(); nf = c.u32(); fields = {}
    for _ in range(nf):
        name = c.string(); off = c.u32(); dtype = c.u8(); cnt = c.u32(); fields[name] = (off, dtype)
    c.u8(); step = c.u32(); c.u32(); n = c.u32(); data = np.frombuffer(c.b, dtype=np.uint8, count=n, offset=c.o)
    npts = h * w; raw = data.reshape(npts, step)
    DT = {1: 'i1', 2: 'u1', 3: 'i2', 4: 'u2', 5: 'i4', 6: 'u4', 7: 'f4', 8: 'f8'}
    out = {}
    for k in want:
        if k in fields:
            off, dt = fields[k]; sz = np.dtype(DT[dt]).itemsize
            out[k] = raw[:, off:off + sz].copy().view('<' + DT[dt]).ravel()
    return stamp, fid, out, list(fields)
