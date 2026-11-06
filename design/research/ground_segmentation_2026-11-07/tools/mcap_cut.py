"""Cut a time window out of a rosbag2 MCAP file without ROS and without writing on the machine that holds the bag.

Only byte copies are taken from the source machine (``tail -c`` of the file end, ``dd`` of one byte range); this script runs
where the copies land.

  1. ``index <tail_file> <file_size>``: reads the footer and the summary section (Schema, Channel, ChunkIndex records) from a copy
     of the file end and prints the chunks with their log times (relative to the first message) as JSON lines.
  2. ``range <tail_file> <file_size> <t0_s> <t1_s>``: prints ``<byte_start> <byte_count>`` of the chunks that overlap
     [t0_s, t1_s] (relative seconds), including the MessageIndex records after the last chunk. Copy that range with
     ``dd if=<bag> iflag=skip_bytes,count_bytes skip=<byte_start> count=<byte_count>``.
  3. ``assemble <head_file> <tail_file> <file_size> <range_file> <out.mcap>``: writes a valid MCAP (no summary section):
     magic + the Header record (from a copy of the first bytes) + every Schema and Channel record of the summary + the copied
     chunk bytes + DataEnd + Footer(0, 0, 0) + magic. Readers then read it sequentially (mcap NonSeekingReader).

The record layout follows the MCAP specification (https://mcap.dev/spec): record = opcode u8, length u64 LE, content.
Record contents are decoded with the official ``mcap`` Python package (mcap.stream_reader.StreamReader); only the framing is
walked here to copy raw records.
"""
from __future__ import annotations

import io
import json
import struct
import sys

from mcap.records import ChunkIndex, Footer, Header
from mcap.stream_reader import StreamReader

MAGIC = b'\x89MCAP0\r\n'
OP_HEADER, OP_FOOTER, OP_SCHEMA, OP_CHANNEL, OP_DATA_END = 0x01, 0x02, 0x03, 0x04, 0x0F
FOOTER_RECORD_LEN = 1 + 8 + 20          # opcode, length, (summary_start u64, summary_offset_start u64, summary_crc u32)


def split_records(buf: bytes):
    """Yield (opcode, raw_record_bytes) for a byte string that holds whole records back to back."""
    o, n = 0, len(buf)
    while o + 9 <= n:
        op = buf[o]
        ln = struct.unpack_from('<Q', buf, o + 1)[0]
        end = o + 9 + ln
        if end > n:
            raise ValueError(f'truncated record at {o} (opcode {op:#x}, length {ln})')
        yield op, buf[o:end]
        o = end


def read_footer(tail: bytes, file_size: int) -> Footer:
    if tail[-8:] != MAGIC:
        raise ValueError('the copied tail does not end with the MCAP magic')
    rec = tail[-8 - FOOTER_RECORD_LEN:-8]
    if rec[0] != OP_FOOTER:
        raise ValueError('no Footer record before the trailing magic')
    s, so, crc = struct.unpack_from('<QQI', rec, 9)
    return Footer(summary_start=s, summary_offset_start=so, summary_crc=crc)


def summary_bytes(tail: bytes, file_size: int) -> bytes:
    f = read_footer(tail, file_size)
    if f.summary_start == 0:
        raise ValueError('the file has no summary section')
    tail_start = file_size - len(tail)
    if f.summary_start < tail_start:
        raise ValueError(f'the copied tail is too short: summary starts {tail_start - f.summary_start} bytes before it')
    end = f.summary_offset_start or (file_size - 8 - FOOTER_RECORD_LEN)
    return tail[f.summary_start - tail_start:end - tail_start]


def summary_records(tail: bytes, file_size: int):
    """(raw schema/channel records in file order, decoded records of the summary)."""
    sb = summary_bytes(tail, file_size)
    raw = [r for op, r in split_records(sb) if op in (OP_SCHEMA, OP_CHANNEL)]
    # the reader stops at a Footer (and its trailing magic); the summary section alone has neither
    end = bytes([OP_FOOTER]) + struct.pack('<Q', 20) + struct.pack('<QQI', 0, 0, 0) + MAGIC
    decoded = [r for r in StreamReader(io.BytesIO(sb + end), skip_magic=True).records if not isinstance(r, Footer)]
    return raw, decoded


def chunk_indexes(tail: bytes, file_size: int):
    _, dec = summary_records(tail, file_size)
    cis = sorted((r for r in dec if isinstance(r, ChunkIndex)), key=lambda c: c.chunk_start_offset)
    if not cis:
        raise ValueError('the summary has no ChunkIndex records')
    return cis


def select_range(cis, t0_s: float, t1_s: float):
    """(byte_start, byte_count, chosen chunk indexes) for chunks overlapping [t0, t1] seconds after the first message."""
    base = min(c.message_start_time for c in cis)
    a, b = base + int(t0_s * 1e9), base + int(t1_s * 1e9)
    chosen = [c for c in cis if c.message_end_time >= a and c.message_start_time <= b]
    if not chosen:
        raise ValueError('no chunk overlaps the window')
    start = chosen[0].chunk_start_offset
    last = chosen[-1]
    end = last.chunk_start_offset + last.chunk_length + last.message_index_length
    return start, end - start, chosen


def header_record(head: bytes) -> bytes:
    if head[:8] != MAGIC:
        raise ValueError('the copied head does not start with the MCAP magic')
    op = head[8]
    ln = struct.unpack_from('<Q', head, 9)[0]
    if op != OP_HEADER or 17 + ln > len(head):
        raise ValueError('no whole Header record in the copied head')
    return head[8:17 + ln]


def assemble(head: bytes, tail: bytes, file_size: int, chunk_bytes: bytes) -> bytes:
    raw, _ = summary_records(tail, file_size)
    # the copied range must be whole records (chunks and message indexes)
    for op, _r in split_records(chunk_bytes):
        pass
    out = io.BytesIO()
    out.write(MAGIC)
    out.write(header_record(head))
    for r in raw:
        out.write(r)
    out.write(chunk_bytes)
    out.write(bytes([OP_DATA_END]) + struct.pack('<Q', 4) + struct.pack('<I', 0))
    out.write(bytes([OP_FOOTER]) + struct.pack('<Q', 20) + struct.pack('<QQI', 0, 0, 0))
    out.write(MAGIC)
    return out.getvalue()


def main(argv):
    cmd = argv[1]
    if cmd == 'index':
        tail = open(argv[2], 'rb').read(); size = int(argv[3])
        cis = chunk_indexes(tail, size); base = min(c.message_start_time for c in cis)
        for c in cis:
            print(json.dumps({'offset': c.chunk_start_offset, 'length': c.chunk_length, 'index_length': c.message_index_length,
                              't0_s': (c.message_start_time - base) * 1e-9, 't1_s': (c.message_end_time - base) * 1e-9,
                              'compression': c.compression}))
    elif cmd == 'range':
        tail = open(argv[2], 'rb').read(); size = int(argv[3])
        s, n, chosen = select_range(chunk_indexes(tail, size), float(argv[4]), float(argv[5]))
        print(s, n)
        print(f'# {len(chosen)} chunks, {n / 1e6:.1f} MB', file=sys.stderr)
    elif cmd == 'assemble':
        head = open(argv[2], 'rb').read(); tail = open(argv[3], 'rb').read(); size = int(argv[4])
        chunk = open(argv[5], 'rb').read()
        open(argv[6], 'wb').write(assemble(head, tail, size, chunk))
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main(sys.argv)
