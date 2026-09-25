"""Python codec for the 64-byte Gouda USB protocol v3."""
from __future__ import annotations

import binascii
import struct
from dataclasses import dataclass

MAGIC = b'\xa5\x5a'
VERSION = 3
FRAME_SIZE = 64
COMMAND, ARM, DISARM, STATUS = 1, 2, 3, 128
STATUS_FLAGS = {'connected': 1 << 0, 'fresh': 1 << 1, 'centered': 1 << 2, 'auto_enabled': 1 << 3}


def crc16_ccitt_false(data: bytes) -> int:
    return binascii.crc_hqx(data, 0xFFFF)


def encode_frame(kind, boot_token, sender_seq, sender_monotonic_ms, payload=b''):
    if not 0 <= int(kind) <= 255 or not 0 <= int(boot_token) < (1 << 64):
        raise ValueError('kind/token out of range')
    if not 0 <= int(sender_seq) < (1 << 32) or not 0 <= int(sender_monotonic_ms) < (1 << 32):
        raise ValueError('sequence/timestamp out of range')
    if len(payload) > 40:
        raise ValueError('payload exceeds 40 bytes')
    body = struct.pack('<2sBBQII', MAGIC, VERSION, int(kind), int(boot_token),
                       int(sender_seq), int(sender_monotonic_ms))
    body += payload.ljust(40, b'\0') + b'\0\0'
    return body + struct.pack('<H', crc16_ccitt_false(body))


def encode_command(boot_token, sender_seq, sender_monotonic_ms, forward_norm, yaw_left_norm):
    """Encode normalized body axes; firmware's right stick is -yaw_left."""
    if not -1.0 <= float(forward_norm) <= 1.0 or not -1.0 <= float(yaw_left_norm) <= 1.0:
        raise ValueError('normalized command axes must be within [-1, 1]')
    right = int(round(-float(yaw_left_norm) * 1000))
    forward = int(round(float(forward_norm) * 1000))
    return encode_frame(COMMAND, boot_token, sender_seq, sender_monotonic_ms,
                        struct.pack('<hh', right, forward))


def encode_arm(boot_token, sender_seq, sender_monotonic_ms):
    return encode_frame(ARM, boot_token, sender_seq, sender_monotonic_ms)


def encode_disarm(boot_token, sender_seq, sender_monotonic_ms):
    return encode_frame(DISARM, boot_token, sender_seq, sender_monotonic_ms)


@dataclass(frozen=True)
class Frame:
    kind: int
    boot_token: int
    sender_seq: int
    sender_monotonic_ms: int
    payload: bytes

    def status(self):
        if self.kind != STATUS:
            return None
        if len(self.payload) != 40:
            raise ValueError('invalid STATUS payload')
        owner, reason, flags, raw_x, raw_y, manual_right, manual_forward, pc_right, pc_forward, applied_right, applied_forward, dac_x, dac_y, mv_x, mv_y, accepted_seq, bt_age, pc_age = struct.unpack(
            '<BBHhhhhhhhhHHHHIII', self.payload)
        if owner not in (0, 1, 2) or reason not in range(9) or flags & ~0x000F:
            raise ValueError('STATUS contains an unknown owner, reason, or flag bit')
        if any(not -1000 <= value <= 1000 for value in
               (raw_x, raw_y, manual_right, manual_forward, pc_right, pc_forward,
                applied_right, applied_forward)):
            raise ValueError('STATUS normalized axes are outside [-1000, 1000]')
        if dac_x > 4095 or dac_y > 4095:
            raise ValueError('STATUS DAC code exceeds 12-bit range')
        return {
            'owner': owner, 'reason': reason,
            'connected': bool(flags & STATUS_FLAGS['connected']),
            'fresh': bool(flags & STATUS_FLAGS['fresh']),
            'centered': bool(flags & STATUS_FLAGS['centered']),
            'auto_enabled': bool(flags & STATUS_FLAGS['auto_enabled']),
            'raw_x_counts': raw_x, 'raw_y_counts': raw_y,
            'manual_right_norm': manual_right / 1000.0, 'manual_forward_norm': manual_forward / 1000.0,
            'pc_right_norm': pc_right / 1000.0, 'pc_forward_norm': pc_forward / 1000.0,
            'applied_right_norm': applied_right / 1000.0, 'applied_forward_norm': applied_forward / 1000.0,
            'dac_x_code': dac_x, 'dac_y_code': dac_y,
            'requested_mv_x': mv_x, 'requested_mv_y': mv_y,
            'last_accepted_pc_seq': accepted_seq, 'bt_age_ms': bt_age, 'pc_age_ms': pc_age,
        }


class Parser:
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data):
        self.buffer.extend(data)
        result = []
        while len(self.buffer) >= FRAME_SIZE:
            offset = self.buffer.find(MAGIC)
            if offset < 0:
                keep_magic_prefix = bool(self.buffer and self.buffer[-1] == MAGIC[0])
                self.buffer[:] = self.buffer[-1:] if keep_magic_prefix else b''
                break
            if offset:
                del self.buffer[:offset]
            if len(self.buffer) < FRAME_SIZE:
                break
            frame = self.buffer[:FRAME_SIZE]
            if frame[2] != VERSION or frame[60:62] != b'\0\0' or crc16_ccitt_false(frame[:62]) != int.from_bytes(frame[62:64], 'little'):
                del self.buffer[0]
                continue
            _, _, kind, token, seq, mono_ms = struct.unpack('<2sBBQII', frame[:20])
            result.append(Frame(kind, token, seq, mono_ms, bytes(frame[20:60])))
            del self.buffer[:FRAME_SIZE]
        return result
