"""vehicle_bridge core (ND-12): what to send to the ESP32 and when, and how STATUS becomes /esp32/status.

No ROS and no serial I/O here; the lifecycle node wraps it with a transport. Design: design/model.yaml ND-12, IFD-16
(input), IFD-17 (COMMAND out), IFD-43 (STATUS/EVENT in), IFD-38 (/esp32/status out), SO-09; docs/esp32_protocol_v4.md §6;
tests TS-13, TS-19 (PC side), TS-29.

Rules:
- A COMMAND is sent only while the node is active, every send_period_s (PRM-14), regardless of whether cmd_vel exists.
- The value is the last joystick_command if it is younger than joystick_timeout_s (PRM-09), otherwise neutral. An old
  non-neutral value is never re-sent. flags bit0 (pc_enable_request) is set while active.
- Axis mapping to the firmware: x_q10000 = -turn * 10000 (firmware x is right-positive, turn is left-positive),
  y_q10000 = forward * 10000. Sign confirmation on the vehicle is Q-03.
- Manual priority (RQ-I023) and the ESP32-side neutralisation (RQ-I068) are the firmware's responsibility; nothing here
  replaces them. STATUS is for display/diagnosis only (DEC-006) and never a stop condition.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from gouda_core import esp32_protocol as proto

REASON_INACTIVE = 'inactive: no COMMAND is sent'
REASON_JOY_NOT_RECEIVED = 'joystick_command not received -> neutral'
REASON_JOY_STALE = 'joystick_command stale -> neutral'
REASON_JOY_NOT_FINITE = 'joystick_command not finite -> neutral'
REASON_FORWARD = 'joystick_command forwarded'


@dataclass(frozen=True)
class BridgeSettings:
    joystick_timeout_s: float   # PRM-09
    send_period_s: float        # PRM-14

    def validate(self) -> None:
        for name in ('joystick_timeout_s', 'send_period_s'):
            v = getattr(self, name)
            if not (isinstance(v, (int, float)) and math.isfinite(v) and v > 0):
                raise ValueError(f'{name} must be a positive finite number, got {v!r}')


@dataclass(frozen=True)
class CommandDecision:
    send: bool
    x_q10000: int
    y_q10000: int
    flags: int
    reason: str


def to_wire(forward: float, turn: float) -> tuple:
    return proto.clamp_axis(round(-turn * proto.AXIS_LIMIT)), proto.clamp_axis(round(forward * proto.AXIS_LIMIT))


class BridgeCore:
    """SO-09 link_state: boot_token of the current ESP32 session, last sent values, last STATUS. Volatile."""

    def __init__(self, settings: BridgeSettings):
        settings.validate()
        self.s = settings
        self.joy: Optional[tuple] = None      # (forward, turn)
        self.joy_time: Optional[float] = None
        self.boot_token: Optional[int] = None
        self.config_valid: Optional[bool] = None
        self.config_generation: Optional[int] = None
        self.last_status: Optional[dict] = None
        self.last_uptime_ms: Optional[int] = None
        self.last_sent: Optional[tuple] = None
        self.seq = 0

    # ---- inputs ----
    def on_joystick(self, forward: float, turn: float, t: float) -> None:
        self.joy = (float(forward), float(turn)); self.joy_time = t

    def on_hello_reply(self, reply: dict) -> bool:
        """Returns True when the ESP32 session (boot_token) changed, i.e. the config must be (re)registered."""
        changed = reply['boot_token'] != self.boot_token
        self.boot_token = reply['boot_token']; self.config_valid = reply['config_valid']; self.config_generation = reply['config_generation']
        return changed

    def on_status(self, status: dict) -> bool:
        """Store the STATUS. Returns True when the ESP32 appears to have rebooted (uptime went backwards), so the node
        should re-run HELLO / SET_CONFIG."""
        rebooted = self.last_uptime_ms is not None and status['uptime_ms'] < self.last_uptime_ms
        self.last_uptime_ms = status['uptime_ms']; self.last_status = status
        if 'config_valid' in status: self.config_valid = status['config_valid']
        return rebooted

    def next_seq(self) -> int:
        self.seq = (self.seq + 1) & 0xFFFFFFFF
        if self.seq == 0: self.seq = 1
        return self.seq

    # ---- decision ----
    def command(self, t: float, active: bool) -> CommandDecision:
        if not active:
            return CommandDecision(False, 0, 0, 0, REASON_INACTIVE)
        flags = proto.FLAG_PC_ENABLE_REQUEST
        if self.joy is None:
            return CommandDecision(True, 0, 0, flags, REASON_JOY_NOT_RECEIVED)
        if t - self.joy_time > self.s.joystick_timeout_s:
            return CommandDecision(True, 0, 0, flags, REASON_JOY_STALE)
        forward, turn = self.joy
        if not (math.isfinite(forward) and math.isfinite(turn)):
            return CommandDecision(True, 0, 0, flags, REASON_JOY_NOT_FINITE)
        x, y = to_wire(forward, turn)
        return CommandDecision(True, x, y, flags, REASON_FORWARD)

    # ---- /esp32/status (IFD-38) ----
    @staticmethod
    def status_key_values(status: dict) -> list:
        """Flatten a decoded STATUS into (key, value) strings. Fields the firmware cannot know are not present; the monitor
        shows them as 不明 (DEC-006)."""
        out = []
        for k, v in status.items():
            out.append((k, '' if v is None else (str(v).lower() if isinstance(v, bool) else str(v))))
        return out
