"""PC–ESP32 serial protocol v4 codec (IFD-17 / IFD-43). Design: design/docs/esp32_protocol_v4.md (REV-027, G-FIRMWARE).

Pure Python, no ROS. The firmware side (firmware/gouda_esp32_v4/include/gouda_v4/protocol.hpp) must produce byte-identical
frames; TS-29 checks both against the same golden vectors. All multi-byte integers are little-endian.

Frame: A5 5A | version 4 | kind | payload length u16 | seq u32 | sender ms u32 | payload | CRC-16/CCITT-FALSE over
offsets 2 .. 13+N (sync bytes and the CRC itself are not covered).
"""
from __future__ import annotations

import binascii
import struct
from dataclasses import dataclass
from typing import List, Optional

SYNC = b'\xa5\x5a'
VERSION = 4
HEADER = struct.Struct('<2sBBHII')      # sync, version, kind, length, seq, sender_ms
HEADER_SIZE = HEADER.size               # 14
MAX_PAYLOAD = 64

# PC -> ESP32
HELLO, COMMAND, SET_CONFIG, GET_STATUS, GET_CONFIG = 0x01, 0x02, 0x03, 0x08, 0x09
# ESP32 -> PC
HELLO_REPLY, STATUS, EVENT, CONFIG, ACK = 0x80, 0x81, 0x82, 0x84, 0x85

AXIS_LIMIT = 10000                      # q10000 normalized axes
FLAG_PC_ENABLE_REQUEST = 0x01           # COMMAND flags bit0

# SET_CONFIG / CONFIG item order (design doc §5). Wire unit is ms / mV / q10000; item 10 is reserved (0).
CONFIG_KEYS = ('dac_neutral_mv', 'dac_min_mv', 'dac_max_mv', 'dac_full_scale_mv', 'pc_command_watchdog_ms',
               'bt_report_timeout_ms', 'manual_deadzone_q10000', 'manual_release_neutral_ms', 'status_period_ms')
CONFIG_STRUCT = struct.Struct('<10H')
# Generated firmware_config.yaml keys that are declared in seconds (PRM-13, PRM-21) and travel as ms.
SECONDS_TO_MS = {'pc_command_watchdog_s': 'pc_command_watchdog_ms', 'bt_report_timeout_s': 'bt_report_timeout_ms'}

SOURCE_NAMES = {0: 'none', 1: 'manual', 2: 'pc'}
REASON_NAMES = {0: 'boot', 1: 'config_invalid', 2: 'bt_disconnected', 3: 'bt_stale', 4: 'waiting_center', 5: 'manual_override',
                6: 'pc_disabled', 7: 'pc_stale', 8: 'neutral_recovery_wait', 9: 'pc_control', 10: 'manual_neutral'}
EVENT_NAMES = {0: 'boot', 1: 'config_loaded_nvs', 2: 'config_loaded_build', 3: 'config_set', 4: 'config_rejected', 5: 'bt_connected',
               6: 'bt_disconnected', 7: 'bt_stale', 8: 'manual_override_begin', 9: 'manual_override_end', 10: 'pc_enabled',
               11: 'pc_disabled_stale', 12: 'pc_disabled_request', 13: 'pc_frame_rejected'}
ACK_RESULTS = {0: 'accepted', 1: 'payload_invalid', 2: 'token_mismatch', 3: 'config_invalid', 4: 'store_failed'}
FLAG_BITS = ('bt_connected', 'bt_fresh', 'centered', 'pc_enabled', 'pc_fresh', 'config_valid')
NEVER = 0xFFFFFFFF
STATUS_STRUCT = struct.Struct('<BBBBhhhhhhHHHHIIIIH')   # 42 bytes
HELLO_REPLY_STRUCT = struct.Struct('<IIBBH')
EVENT_STRUCT = struct.Struct('<BBI')
ACK_STRUCT = struct.Struct('<BB')
COMMAND_STRUCT = struct.Struct('<IhhB')


def crc16(data: bytes) -> int:
    """CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, no reflection, xorout 0). crc16(b'123456789') == 0x29B1."""
    return binascii.crc_hqx(data, 0xFFFF)


@dataclass(frozen=True)
class Frame:
    kind: int
    seq: int
    sender_ms: int
    payload: bytes


def encode_frame(kind: int, seq: int, sender_ms: int, payload: bytes = b'') -> bytes:
    if not 0 <= kind <= 255 or not 0 <= seq < 2 ** 32 or not 0 <= sender_ms < 2 ** 32:
        raise ValueError('kind/seq/sender_ms out of range')
    if len(payload) > MAX_PAYLOAD:
        raise ValueError('payload too long')
    head = HEADER.pack(SYNC, VERSION, kind, len(payload), seq, sender_ms)
    body = head + payload
    return body + struct.pack('<H', crc16(body[2:]))


def clamp_axis(q: int) -> int:
    return max(-AXIS_LIMIT, min(AXIS_LIMIT, int(q)))


def encode_command(seq, sender_ms, boot_token, x_q10000, y_q10000, flags) -> bytes:
    return encode_frame(COMMAND, seq, sender_ms, COMMAND_STRUCT.pack(boot_token & 0xFFFFFFFF, clamp_axis(x_q10000), clamp_axis(y_q10000), flags & 0xFF))


def encode_hello(seq, sender_ms, session_id) -> bytes:
    return encode_frame(HELLO, seq, sender_ms, struct.pack('<I', session_id & 0xFFFFFFFF))


def encode_get(kind, seq, sender_ms, boot_token) -> bytes:
    if kind not in (GET_STATUS, GET_CONFIG):
        raise ValueError('not a GET kind')
    return encode_frame(kind, seq, sender_ms, struct.pack('<I', boot_token & 0xFFFFFFFF))


def config_items(cfg: dict) -> List[int]:
    """Wire items of SET_CONFIG from a dict with the CONFIG_KEYS (missing keys -> 0 = not configured)."""
    vals = []
    for k in CONFIG_KEYS:
        v = cfg.get(k, 0)
        v = 0 if v is None else int(round(v))
        if not 0 <= v <= 0xFFFF:
            raise ValueError(f'{k}={v} does not fit u16')
        vals.append(v)
    return vals + [0]


def encode_set_config(seq, sender_ms, boot_token, cfg: dict) -> bytes:
    return encode_frame(SET_CONFIG, seq, sender_ms, struct.pack('<I', boot_token & 0xFFFFFFFF) + CONFIG_STRUCT.pack(*config_items(cfg)))


def config_from_params(params: dict) -> dict:
    """Map the generated firmware_config.yaml (PRM keys; PRM-13/21 in seconds) to the wire config dict (ms / mV / q10000).
    Keys that are not present stay absent (never filled with a default)."""
    out = {}
    for k, v in params.items():
        if k in SECONDS_TO_MS:
            out[SECONDS_TO_MS[k]] = int(round(float(v) * 1000))
        elif k in CONFIG_KEYS:
            out[k] = int(round(v))
    return out


def decode_config_items(items) -> dict:
    return {k: int(items[i]) for i, k in enumerate(CONFIG_KEYS)}


def decode_status(payload: bytes) -> dict:
    if len(payload) != STATUS_STRUCT.size:
        raise ValueError(f'STATUS payload must be {STATUS_STRUCT.size} bytes, got {len(payload)}')
    (source, reason, flags, gen, mx, my, px, py, ax, ay, tx, ty, dx, dy, pc_age, bt_age, last_seq, uptime, _res) = STATUS_STRUCT.unpack(payload)
    if source not in SOURCE_NAMES or reason not in REASON_NAMES:
        raise ValueError('STATUS has an unknown source or reason')
    d = {'source': SOURCE_NAMES[source], 'reason': REASON_NAMES[reason], 'config_generation': gen,
         'manual_x_q10000': mx, 'manual_y_q10000': my, 'pc_x_q10000': px, 'pc_y_q10000': py, 'applied_x_q10000': ax, 'applied_y_q10000': ay,
         'target_x_mv': tx, 'target_y_mv': ty, 'dac_x': dx, 'dac_y': dy,
         'pc_age_ms': None if pc_age == NEVER else pc_age, 'bt_age_ms': None if bt_age == NEVER else bt_age,
         'last_pc_seq': last_seq, 'uptime_ms': uptime}
    for i, name in enumerate(FLAG_BITS):
        d[name] = bool(flags & (1 << i))
    return d


def decode_hello_reply(payload: bytes) -> dict:
    session_id, token, valid, gen, proto = HELLO_REPLY_STRUCT.unpack(payload)
    return {'session_id': session_id, 'boot_token': token, 'config_valid': bool(valid), 'config_generation': gen, 'protocol_version': proto}


def decode_event(payload: bytes) -> dict:
    code, arg, ms = EVENT_STRUCT.unpack(payload)
    return {'code': code, 'name': EVENT_NAMES.get(code, f'unknown_{code}'), 'arg': arg, 'esp_ms': ms}


def decode_config(payload: bytes) -> dict:
    valid, gen = struct.unpack_from('<BB', payload, 0)
    items = CONFIG_STRUCT.unpack_from(payload, 2)
    return {'config_valid': bool(valid), 'config_generation': gen, **decode_config_items(items)}


def decode_ack(payload: bytes) -> dict:
    req, res = ACK_STRUCT.unpack(payload)
    return {'request_type': req, 'result': res, 'result_name': ACK_RESULTS.get(res, f'unknown_{res}')}


def decode_command(payload: bytes) -> dict:
    token, x, y, flags = COMMAND_STRUCT.unpack(payload)
    return {'boot_token': token, 'x_q10000': x, 'y_q10000': y, 'flags': flags}


class Parser:
    """Byte-stream parser that resynchronises on the sync bytes. Invalid frames (bad CRC, version, length) are dropped and
    counted; nothing is ever guessed from a damaged frame."""

    def __init__(self):
        self.buf = bytearray()
        self.rejected = 0

    def feed(self, data: bytes) -> List[Frame]:
        self.buf += data
        out: List[Frame] = []
        while True:
            i = self.buf.find(SYNC)
            if i < 0:
                self.buf.clear(); break
            if i > 0:
                del self.buf[:i]
            if len(self.buf) < HEADER_SIZE:
                break
            _sync, ver, kind, length, seq, ms = HEADER.unpack_from(self.buf, 0)
            if ver != VERSION or length > MAX_PAYLOAD:
                self.rejected += 1; del self.buf[:1]; continue
            total = HEADER_SIZE + length + 2
            if len(self.buf) < total:
                break
            body = bytes(self.buf[:HEADER_SIZE + length])
            crc_rx, = struct.unpack_from('<H', self.buf, HEADER_SIZE + length)
            if crc16(body[2:]) != crc_rx:
                self.rejected += 1; del self.buf[:1]; continue
            out.append(Frame(kind, seq, ms, body[HEADER_SIZE:]))
            del self.buf[:total]
        return out


def newer_sequence(candidate: int, previous: int) -> bool:
    delta = (candidate - previous) & 0xFFFFFFFF
    return delta != 0 and delta < 0x80000000
