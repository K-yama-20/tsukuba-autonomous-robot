#!/usr/bin/env python3
"""Decode an ESP32 .frames calibration log into CSV."""

from __future__ import annotations

import argparse
import csv
import struct
from pathlib import Path


SYNC = b"\xA5\x5A"
HEADER = struct.Struct("<BBHII")
SAMPLE = struct.Struct("<IIBBbBHHHHiiIH")
CALIBRATION_SAMPLE = 0x83


def crc16_ccitt(data: bytes, initial: int = 0xFFFF) -> int:
    crc = initial
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def iter_frames(data: bytes):
    offset = 0
    while offset + 16 <= len(data):
        if data[offset : offset + 2] != SYNC:
            offset += 1
            continue
        version, message_type, payload_size, sequence, timestamp_ms = HEADER.unpack_from(
            data, offset + 2
        )
        total = 16 + payload_size
        if version != 1 or payload_size > 192 or offset + total > len(data):
            offset += 1
            continue
        body = data[offset + 2 : offset + 14 + payload_size]
        expected_crc = struct.unpack_from("<H", data, offset + 14 + payload_size)[0]
        if crc16_ccitt(body) != expected_crc:
            raise ValueError(f"CRC error at byte {offset}")
        payload = data[offset + 14 : offset + 14 + payload_size]
        yield message_type, sequence, timestamp_ms, payload
        offset += total


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    rows = []
    for message_type, sequence, timestamp_ms, payload in iter_frames(
        args.input.read_bytes()
    ):
        if message_type != CALIBRATION_SAMPLE:
            continue
        if len(payload) != SAMPLE.size:
            raise ValueError(f"sample payload has {len(payload)} bytes, expected {SAMPLE.size}")
        values = SAMPLE.unpack(payload)
        rows.append((sequence, timestamp_ms, *values))

    header = [
        "frame_sequence",
        "device_time_ms",
        "session_id",
        "sample_index",
        "phase",
        "axis",
        "direction",
        "verdict",
        "target_x_mv",
        "target_y_mv",
        "actual_x_mv",
        "actual_y_mv",
        "left_mm_s",
        "right_mm_s",
        "stationary_ms",
        "failure",
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"wrote {len(rows)} samples to {args.output}")


if __name__ == "__main__":
    main()
