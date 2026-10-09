"""Minimal grayscale PNG encoder (standard library only) for showing a map or mask in the monitor page.

Browsers do not display PGM; the monitor converts the stored map/mask on request without changing the stored files.
"""
from __future__ import annotations

import struct
import zlib


def _chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)


def encode_gray(width: int, height: int, rows: bytes) -> bytes:
    """rows: height * width bytes, row 0 = top."""
    if len(rows) != width * height:
        raise ValueError('row data size does not match width*height')
    raw = b''.join(b'\x00' + rows[y * width:(y + 1) * width] for y in range(height))
    return (b'\x89PNG\r\n\x1a\n' + _chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 0, 0, 0, 0))
            + _chunk(b'IDAT', zlib.compress(raw, 6)) + _chunk(b'IEND', b''))


def pgm_to_png(pgm_bytes: bytes) -> tuple[bytes, int, int]:
    """Decode a binary PGM (P5, maxval 255) and return (png bytes, width, height)."""
    if not pgm_bytes.startswith(b'P5'):
        raise ValueError('not a binary PGM')
    parts = []; pos = 2
    while len(parts) < 3:
        while pgm_bytes[pos:pos + 1].isspace(): pos += 1
        if pgm_bytes[pos:pos + 1] == b'#':
            pos = pgm_bytes.index(b'\n', pos) + 1; continue
        end = pos
        while not pgm_bytes[end:end + 1].isspace(): end += 1
        parts.append(int(pgm_bytes[pos:end])); pos = end
    pos += 1   # single whitespace after maxval
    w, h, maxval = parts
    if maxval != 255: raise ValueError('only maxval 255 is supported')
    data = pgm_bytes[pos:pos + w * h]
    return encode_gray(w, h, data), w, h
