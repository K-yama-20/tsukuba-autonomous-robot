"""Python model of the v4 ESP32 firmware core (ND-17) for software tests. Design: design/docs/esp32_protocol_v4.md.

This is a STUB of the firmware for PC-side tests (TS-13, TS-19 PC side, bridge unit tests, pty runs on Ubuntu). The
vehicle runs the C++ firmware in firmware/gouda_esp32_v4; both follow the same rules and share the protocol golden
vectors (TS-29). Nothing here is a vehicle value: the configuration is injected by the test (trial values) or by the bridge
through SET_CONFIG, exactly as on the device.

Rules (same as control.hpp):
- config_valid requires dac_min < dac_neutral < dac_max <= dac_full_scale, watchdog > 0, bt timeout > 0, deadzone < 10000.
  Without a valid config the DAC is never written (source none, reason config_invalid).
- Manual (Bluetooth gamepad) owns the output while the BT report is fresh (< bt_report_timeout_ms), a centered report has
  been seen since connect, and the stick is outside the deadzone (RQ-I023).
- BT report older than bt_report_timeout_ms, or disconnect: manual input is invalid (centered latch cleared), the manual
  output falls to neutral (RQ-I024). The PC source enable state is not touched.
- PC source: enabled by an accepted COMMAND with flags bit0 whose axes are neutral; disabled when the last valid COMMAND is
  older than pc_command_watchdog_ms (RQ-I068) or when a COMMAND with bit0 clear arrives. Re-enabling needs a neutral
  COMMAND with bit0 again. Invalid frames (CRC, version, token, sequence) never refresh the watchdog.
- PC may own the output only when manual has been inactive for manual_release_neutral_ms (covers stick back to neutral
  and BT loss during an override; TS-17/TS-18 "do not switch immediately").
- Voltage mapping: the circle-limited map of the previous firmware with neutral/min/max from the config; DAC code =
  round(mV * 4095 / full_scale).
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from typing import List, Optional

from gouda_core import esp32_protocol as p

NEVER = p.NEVER
SRC_NONE, SRC_MANUAL, SRC_PC = 0, 1, 2
R_BOOT, R_CONFIG_INVALID, R_BT_DISCONNECTED, R_BT_STALE, R_WAITING_CENTER, R_MANUAL_OVERRIDE, R_PC_DISABLED, R_PC_STALE, R_NEUTRAL_RECOVERY_WAIT, R_PC_CONTROL, R_MANUAL_NEUTRAL = range(11)
(E_BOOT, E_CONFIG_LOADED_NVS, E_CONFIG_LOADED_BUILD, E_CONFIG_SET, E_CONFIG_REJECTED, E_BT_CONNECTED, E_BT_DISCONNECTED, E_BT_STALE,
 E_MANUAL_OVERRIDE_BEGIN, E_MANUAL_OVERRIDE_END, E_PC_ENABLED, E_PC_DISABLED_STALE, E_PC_DISABLED_REQUEST, E_PC_FRAME_REJECTED) = range(14)
ACK_OK, ACK_PAYLOAD, ACK_TOKEN, ACK_CONFIG, ACK_STORE = range(5)


def config_valid(c: dict) -> bool:
    try:
        return (0 < c['dac_min_mv'] < c['dac_neutral_mv'] < c['dac_max_mv'] <= c['dac_full_scale_mv'] and c['pc_command_watchdog_ms'] > 0
                and c['bt_report_timeout_ms'] > 0 and 0 <= c['manual_deadzone_q10000'] < p.AXIS_LIMIT)
    except (KeyError, TypeError):
        return False


def inside_circle(x_mv, y_mv, lo, hi) -> bool:
    dx = 2 * x_mv - (lo + hi); dy = 2 * y_mv - (lo + hi); d = hi - lo
    return dx * dx + dy * dy <= d * d


def map_voltage(x: float, y: float, neutral: int, lo: int, hi: int) -> tuple:
    """x, y in [-1, 1] (x right+, y forward+). Previous firmware's circle-limited mapping, parametrised by the config."""
    mag = math.hypot(x, y)
    if mag == 0:
        return neutral, neutral
    ux, uy = x / mag, y / mag
    center = (lo + hi) / 2; radius = (hi - lo) / 2; offset = neutral - center
    dot = offset * (ux + uy)
    distance = -dot + math.sqrt(max(0.0, dot * dot + radius * radius - 2 * offset * offset))
    travel = min(mag, 1) * distance
    ox = int(round(neutral + ux * travel)); oy = int(round(neutral + uy * travel))
    while not inside_circle(ox, oy, lo, hi):
        dx = 2 * ox - (lo + hi); dy = 2 * oy - (lo + hi)
        if abs(dx) >= abs(dy): ox += -1 if dx > 0 else 1
        else: oy += -1 if dy > 0 else 1
    return ox, oy


def dac_code(mv: int, full_scale: int) -> int:
    return min(4095, (mv * 4095 + full_scale // 2) // full_scale)


def manual_vector(x_q: int, y_q: int, deadzone_q: int) -> tuple:
    x = max(-1, min(1, x_q / p.AXIS_LIMIT)); y = max(-1, min(1, y_q / p.AXIS_LIMIT))
    r = math.hypot(x, y); dz = deadzone_q / p.AXIS_LIMIT
    if r <= dz:
        return 0.0, 0.0
    m = (min(r, 1) - dz) / (1 - dz)
    return x * m / r, y * m / r


@dataclass
class Applied:
    source: int
    reason: int
    x: float
    y: float
    target_mv: Optional[tuple]     # None when the DAC is not written (config invalid)
    dac: Optional[tuple]


@dataclass
class Esp32Sim:
    boot_token: int
    config: Optional[dict] = None          # build-time or NVS config (None = nothing registered)
    now_ms: int = 0
    config_generation: int = 0
    events: List[tuple] = field(default_factory=list)
    out: bytearray = field(default_factory=bytearray)
    # BT
    bt_connected: bool = False
    bt_have_report: bool = False
    bt_last_ms: int = 0
    centered: bool = False
    manual: tuple = (0.0, 0.0)
    bt_stale_flagged: bool = False
    # PC
    pc_enabled: bool = False
    pc_have_cmd: bool = False
    pc_last_ms: int = 0
    pc_cmd: tuple = (0, 0)
    pc_have_seq: bool = False
    pc_last_seq: int = 0
    last_manual_active_ms: Optional[int] = None
    manual_active_prev: bool = False
    tx_seq: int = 0
    status_last_ms: Optional[int] = None
    parser: p.Parser = field(default_factory=p.Parser)

    def __post_init__(self):
        self._event(E_BOOT, 0)
        if self.config is not None:
            self._event(E_CONFIG_LOADED_BUILD, 1 if config_valid(self.config) else 0)

    # ---- helpers ----
    @property
    def cfg_valid(self) -> bool:
        return self.config is not None and config_valid(self.config)

    def _event(self, code, arg):
        self.events.append((code, arg, self.now_ms))
        self.out += p.encode_frame(p.EVENT, self._seq(), self.now_ms, p.EVENT_STRUCT.pack(code, arg, self.now_ms))

    def _seq(self):
        self.tx_seq = (self.tx_seq + 1) & 0xFFFFFFFF; return self.tx_seq

    def bt_fresh(self) -> bool:
        return self.bt_connected and self.bt_have_report and (self.now_ms - self.bt_last_ms) < self.config['bt_report_timeout_ms'] if self.cfg_valid else False

    def pc_fresh(self) -> bool:
        return self.pc_have_cmd and (self.now_ms - self.pc_last_ms) < self.config['pc_command_watchdog_ms'] if self.cfg_valid else False

    # ---- Bluetooth inputs ----
    def bt_connect(self, now_ms: int):
        self.now_ms = now_ms
        self.bt_connected = True; self.bt_have_report = False; self.centered = False; self.manual = (0.0, 0.0); self.bt_stale_flagged = False
        self._event(E_BT_CONNECTED, 0)

    def bt_disconnect(self, now_ms: int):
        self.now_ms = now_ms
        self.bt_connected = False; self.bt_have_report = False; self.centered = False; self.manual = (0.0, 0.0)
        self._event(E_BT_DISCONNECTED, 0)

    def bt_report(self, x_q: int, y_q: int, now_ms: int):
        """Normalized stick report (x right+, y forward+, q10000)."""
        self.now_ms = now_ms
        if not self.bt_connected:
            return
        if self.cfg_valid and self.bt_have_report and (now_ms - self.bt_last_ms) >= self.config['bt_report_timeout_ms']:
            self.centered = False; self.manual = (0.0, 0.0)   # a report after a gap: wait for center again
        self.bt_last_ms = now_ms; self.bt_have_report = True; self.bt_stale_flagged = False
        dz = self.config['manual_deadzone_q10000'] if self.cfg_valid else p.AXIS_LIMIT
        v = manual_vector(x_q, y_q, dz)
        if not self.centered and v == (0.0, 0.0):
            self.centered = True
        self.manual = v if self.centered else (0.0, 0.0)

    # ---- serial input ----
    def feed(self, data: bytes, now_ms: int) -> bytes:
        self.now_ms = now_ms
        for f in self.parser.feed(data):
            self._handle(f)
        return self.drain()

    def _ack(self, req, result):
        self.out += p.encode_frame(p.ACK, self._seq(), self.now_ms, p.ACK_STRUCT.pack(req, result))

    def _handle(self, f: p.Frame):
        if f.kind == p.HELLO:
            if len(f.payload) != 4: return self._ack(f.kind, ACK_PAYLOAD)
            session, = struct.unpack('<I', f.payload)
            self.out += p.encode_frame(p.HELLO_REPLY, self._seq(), self.now_ms, p.HELLO_REPLY_STRUCT.pack(session, self.boot_token, 1 if self.cfg_valid else 0, self.config_generation, p.VERSION))
            return
        if len(f.payload) < 4: return self._ack(f.kind, ACK_PAYLOAD)
        token, = struct.unpack_from('<I', f.payload, 0)
        if token != self.boot_token:
            self._event(E_PC_FRAME_REJECTED, ACK_TOKEN); return self._ack(f.kind, ACK_TOKEN)
        if f.kind == p.COMMAND:
            if len(f.payload) != p.COMMAND_STRUCT.size: return self._ack(f.kind, ACK_PAYLOAD)
            if self.pc_have_seq and not p.newer_sequence(f.seq, self.pc_last_seq):
                self._event(E_PC_FRAME_REJECTED, 5); return   # replay / old: ignored silently except the event
            c = p.decode_command(f.payload)
            self.pc_last_seq = f.seq; self.pc_have_seq = True
            self.pc_cmd = (c['x_q10000'], c['y_q10000']); self.pc_have_cmd = True; self.pc_last_ms = self.now_ms
            want = bool(c['flags'] & p.FLAG_PC_ENABLE_REQUEST)
            if want and not self.pc_enabled and self.pc_cmd == (0, 0):
                self.pc_enabled = True; self._event(E_PC_ENABLED, 0)
            elif not want and self.pc_enabled:
                self.pc_enabled = False; self._event(E_PC_DISABLED_REQUEST, 0)
            return
        if f.kind == p.SET_CONFIG:
            if len(f.payload) != 4 + p.CONFIG_STRUCT.size: return self._ack(f.kind, ACK_PAYLOAD)
            items = p.CONFIG_STRUCT.unpack_from(f.payload, 4); cfg = p.decode_config_items(items)
            if not config_valid(cfg):
                self._event(E_CONFIG_REJECTED, 0); return self._ack(f.kind, ACK_CONFIG)
            self.config = cfg; self.config_generation = (self.config_generation + 1) & 0xFF
            self._event(E_CONFIG_SET, self.config_generation); self._ack(f.kind, ACK_OK); return
        if f.kind == p.GET_STATUS:
            self.out += self.status_frame(); return
        if f.kind == p.GET_CONFIG:
            items = p.config_items(self.config or {})
            self.out += p.encode_frame(p.CONFIG, self._seq(), self.now_ms, struct.pack('<BB', 1 if self.cfg_valid else 0, self.config_generation) + p.CONFIG_STRUCT.pack(*items)); return
        # unknown kinds are ignored after CRC validation

    # ---- periodic ----
    def tick(self, now_ms: int) -> bytes:
        self.now_ms = now_ms
        if self.cfg_valid:
            if self.bt_connected and self.bt_have_report and not self.bt_fresh() and not self.bt_stale_flagged:
                self.centered = False; self.manual = (0.0, 0.0); self.bt_stale_flagged = True; self._event(E_BT_STALE, 0)
            if self.pc_enabled and not self.pc_fresh():
                self.pc_enabled = False; self._event(E_PC_DISABLED_STALE, 0)
            a = self.applied()
            manual_active = a.source == SRC_MANUAL
            if manual_active:
                self.last_manual_active_ms = now_ms
            if manual_active != self.manual_active_prev:
                self._event(E_MANUAL_OVERRIDE_BEGIN if manual_active else E_MANUAL_OVERRIDE_END, 0); self.manual_active_prev = manual_active
            period = self.config['status_period_ms']
            if period > 0 and (self.status_last_ms is None or now_ms - self.status_last_ms >= period):
                self.out += self.status_frame(); self.status_last_ms = now_ms
        return self.drain()

    def drain(self) -> bytes:
        b = bytes(self.out); self.out.clear(); return b

    # ---- arbitration (pure function of the state) ----
    def applied(self) -> Applied:
        if not self.cfg_valid:
            return Applied(SRC_NONE, R_CONFIG_INVALID, 0.0, 0.0, None, None)
        c = self.config
        bt_fresh = self.bt_fresh()
        manual_active = bt_fresh and self.centered and self.manual != (0.0, 0.0)
        if manual_active:
            src, reason, x, y = SRC_MANUAL, R_MANUAL_OVERRIDE, self.manual[0], self.manual[1]
        else:
            release_ok = self.last_manual_active_ms is None or (self.now_ms - self.last_manual_active_ms) >= c['manual_release_neutral_ms']
            if self.pc_enabled and self.pc_fresh():
                if release_ok:
                    src, reason, x, y = SRC_PC, R_PC_CONTROL, self.pc_cmd[0] / p.AXIS_LIMIT, self.pc_cmd[1] / p.AXIS_LIMIT
                else:
                    src, reason, x, y = SRC_NONE, R_NEUTRAL_RECOVERY_WAIT, 0.0, 0.0
            else:
                if self.bt_connected and self.bt_have_report and not bt_fresh: reason = R_BT_STALE
                elif self.bt_connected and bt_fresh and not self.centered: reason = R_WAITING_CENTER
                elif self.pc_have_cmd and not self.pc_fresh(): reason = R_PC_STALE
                elif bt_fresh and self.centered: reason = R_MANUAL_NEUTRAL
                elif not self.bt_connected and not self.pc_have_cmd: reason = R_BT_DISCONNECTED
                else: reason = R_PC_DISABLED
                src, x, y = SRC_NONE, 0.0, 0.0
        tx, ty = map_voltage(x, y, c['dac_neutral_mv'], c['dac_min_mv'], c['dac_max_mv'])
        return Applied(src, reason, x, y, (tx, ty), (dac_code(tx, c['dac_full_scale_mv']), dac_code(ty, c['dac_full_scale_mv'])))

    def status_frame(self) -> bytes:
        a = self.applied()
        flags = ((1 if self.bt_connected else 0) | (2 if self.bt_fresh() else 0) | (4 if self.centered else 0) | (8 if self.pc_enabled else 0)
                 | (16 if self.pc_fresh() else 0) | (32 if self.cfg_valid else 0))
        q = lambda v: int(round(max(-1, min(1, v)) * p.AXIS_LIMIT))
        payload = p.STATUS_STRUCT.pack(a.source, a.reason, flags, self.config_generation,
                                       q(self.manual[0]), q(self.manual[1]), self.pc_cmd[0], self.pc_cmd[1], q(a.x), q(a.y),
                                       a.target_mv[0] if a.target_mv else 0, a.target_mv[1] if a.target_mv else 0,
                                       a.dac[0] if a.dac else 0, a.dac[1] if a.dac else 0,
                                       (self.now_ms - self.pc_last_ms) if self.pc_have_cmd else NEVER,
                                       (self.now_ms - self.bt_last_ms) if self.bt_have_report else NEVER,
                                       self.pc_last_seq if self.pc_have_seq else 0, self.now_ms & 0xFFFFFFFF, 0)
        return p.encode_frame(p.STATUS, self._seq(), self.now_ms, payload)
