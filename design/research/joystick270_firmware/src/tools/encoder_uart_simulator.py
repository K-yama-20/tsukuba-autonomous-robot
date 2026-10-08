#!/usr/bin/env python3
"""Send synthetic left/right wheel speeds to the joystick ESP32 UART."""

from __future__ import annotations

import argparse
import struct
import time

SYNC = b"\xA5\x5A"
VERSION = 1
ENCODER_SPEED = 0x40
STATUS_VALID = 1


def crc16_ccitt(data: bytes, initial: int = 0xFFFF) -> int:
    crc = initial
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def frame(sequence: int, timestamp_ms: int, left: int, right: int) -> bytes:
    payload = struct.pack("<iiH", left, right, STATUS_VALID)
    body = struct.pack(
        "<BBHII", VERSION, ENCODER_SPEED, len(payload), sequence, timestamp_ms
    ) + payload
    return SYNC + body + struct.pack("<H", crc16_ccitt(body))


def main() -> None:
    try:
        import serial
    except ImportError as error:
        raise SystemExit(
            "pyserial is required; run: python3 -m pip install -r tools/requirements.txt"
        ) from error

    parser = argparse.ArgumentParser()
    parser.add_argument("port", help="UART adapter device connected to J11-3")
    parser.add_argument("--baud", type=int, default=230400)
    parser.add_argument("--rate-hz", type=float, default=50.0)
    parser.add_argument("--left-mm-s", type=int, default=0)
    parser.add_argument("--right-mm-s", type=int, default=0)
    args = parser.parse_args()
    if not 1.0 <= args.rate_hz <= 500.0:
        parser.error("--rate-hz must be in 1..500")

    start = time.monotonic()
    sequence = 0
    period = 1.0 / args.rate_hz
    deadline = time.monotonic()
    with serial.Serial(args.port, args.baud, timeout=0) as connection:
        while True:
            now = time.monotonic()
            if now < deadline:
                time.sleep(deadline - now)
            timestamp_ms = int((time.monotonic() - start) * 1000) & 0xFFFFFFFF
            sequence = (sequence + 1) & 0xFFFFFFFF
            connection.write(
                frame(sequence, timestamp_ms, args.left_mm_s, args.right_mm_s)
            )
            deadline += period


if __name__ == "__main__":
    main()
