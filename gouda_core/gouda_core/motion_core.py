"""gouda_motion_controller core (ND-11): cmd_vel -> normalized joystick command, with neutral on hold / stale input.

No ROS dependency; the lifecycle node wraps it. Design: design/model.yaml ND-11, IFD-15 (cmd_vel), IFD-16
(vehicle/joystick_command), IFD-40 (control/motion_hold), SO-08; tests TS-07, TS-13.

Rules (DEC-004, RQ-I063, RQ-I020):
- Output is neutral when motion_hold has never been received, when hold is true, when the last hold is older than
  motion_hold_timeout_s (PRM-42), when cmd_vel has never been received, is older than cmd_vel_timeout_s (PRM-08) or is not
  finite. Only hold=false AND a fresh finite cmd_vel gives a non-neutral output.
- Normalization: forward = linear.x / max_linear_speed_mps (PRM-39) when linear.x >= 0, linear.x / max_reverse_speed_mps
  (PRM-78) when it is negative (DEC-172: the wheelchair limits reversing), turn = angular.z / max_angular_speed_radps (PRM-40),
  all saturated to [-1, 1]. Nothing else limits the speed (RQ-I020: the only speed limit path is Nav2's SpeedLimit).
- Dead-band compensation (DEC-171 plan A, DEC-181; IFD-52): per direction (forward, reverse, turn) a minimum stick amount m and
  a threshold t entered by the human in the monitor's /config. For a normalized amount of magnitude r: r < t gives 0 (stays
  neutral), otherwise m + (1 - m) * r with the original sign. A direction whose m or t is not set is not compensated (the
  plain normalization). New values are used from the next output on (also while driving). The neutral rules above come first.
- All thresholds are settings passed in by the node from the generated parameter file or IFD-52; nothing numeric lives here.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

REASON_HOLD_NOT_RECEIVED = 'motion_hold not received'
REASON_HOLD_TRUE = 'motion_hold=true'
REASON_HOLD_EXPIRED = 'motion_hold expired'
REASON_CMD_NOT_RECEIVED = 'cmd_vel not received'
REASON_CMD_STALE = 'cmd_vel stale'
REASON_CMD_NOT_FINITE = 'cmd_vel not finite'
REASON_DRIVE = 'drive'


@dataclass(frozen=True)
class MotionSettings:
    cmd_vel_timeout_s: float          # PRM-08 (approved 0.7 s; read from the generated file)
    max_linear_speed_mps: float       # PRM-39
    max_angular_speed_radps: float    # PRM-40
    motion_hold_timeout_s: float      # PRM-42
    max_reverse_speed_mps: float      # PRM-78 (DEC-172)

    def validate(self) -> None:
        for name in ('cmd_vel_timeout_s', 'max_linear_speed_mps', 'max_angular_speed_radps', 'motion_hold_timeout_s', 'max_reverse_speed_mps'):
            v = getattr(self, name)
            if not (isinstance(v, (int, float)) and math.isfinite(v) and v > 0):
                raise ValueError(f'{name} must be a positive finite number, got {v!r}')


COMPENSATION_DIRECTIONS = ('forward', 'reverse', 'turn')


def _set(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


@dataclass(frozen=True)
class Compensation:
    """IFD-52 values; None (or NaN on the wire) = not set. Each value is a stick amount in [0, 1)."""
    forward_min: Optional[float] = None
    forward_threshold: Optional[float] = None
    reverse_min: Optional[float] = None
    reverse_threshold: Optional[float] = None
    turn_min: Optional[float] = None
    turn_threshold: Optional[float] = None
    config_revision: int = 0

    def problems(self) -> list:
        """Values outside [0, 1) (the monitor refuses them; a bad message is not used)."""
        out = []
        for d in COMPENSATION_DIRECTIONS:
            for k in (f'{d}_min', f'{d}_threshold'):
                v = getattr(self, k)
                if _set(v) and not (0 <= v < 1):
                    out.append(f'{k}={v!r} is outside [0, 1)')
        return out

    def pair(self, direction: str) -> Optional[tuple]:
        """(minimum, threshold) when both are set, else None (that direction is not compensated)."""
        m, t = getattr(self, f'{direction}_min'), getattr(self, f'{direction}_threshold')
        return (float(m), float(t)) if _set(m) and _set(t) else None

    def active_directions(self) -> list:
        return [d for d in COMPENSATION_DIRECTIONS if self.pair(d) is not None]


NO_COMPENSATION = Compensation()


def compensate(value: float, pair: Optional[tuple]) -> float:
    """DEC-171 plan A on one normalized axis value in [-1, 1]. pair None: unchanged."""
    if pair is None or value == 0.0:
        return value
    m, t = pair
    r = abs(value)
    if r < t:
        return 0.0
    return math.copysign(m + (1 - m) * r, value)


@dataclass(frozen=True)
class MotionOutput:
    forward: float        # IFD-16 axes[0], [-1, 1]
    turn: float           # IFD-16 axes[1], [-1, 1]; positive = left (angular.z > 0, REP-103)
    neutral: bool
    reason: str
    hold_reason: str = ''
    normalized_forward: float = 0.0   # before the dead-band compensation (for the record)
    normalized_turn: float = 0.0


def _clamp(v: float) -> float:
    return float(max(-1, min(1, v)))


class MotionCore:
    """SO-08: last_cmd_vel_time / last cmd_vel, motion_hold_state (hold, reason, mode, time). Volatile; neutral at start."""

    def __init__(self, settings: MotionSettings):
        settings.validate()
        self.s = settings
        self.cmd: Optional[tuple] = None       # (linear_x, angular_z)
        self.cmd_time: Optional[float] = None
        self.hold: Optional[bool] = None
        self.hold_reason = ''
        self.hold_mode = 0
        self.hold_time: Optional[float] = None
        self.compensation = NO_COMPENSATION

    # ---- inputs ----
    def on_cmd_vel(self, linear_x: float, angular_z: float, t: float) -> None:
        self.cmd = (float(linear_x), float(angular_z)); self.cmd_time = t

    def on_motion_hold(self, hold: bool, reason: str, mode: int, t: float) -> None:
        self.hold = bool(hold); self.hold_reason = reason; self.hold_mode = int(mode); self.hold_time = t

    def set_compensation(self, comp: Compensation) -> list:
        """Use comp from the next output on (DEC-181). Returns its problems; a compensation with problems is not used and the
        previous one stays."""
        bad = comp.problems()
        if not bad:
            self.compensation = comp
        return bad

    # ---- decision ----
    def output(self, t: float) -> MotionOutput:
        if self.hold is None:
            return MotionOutput(0.0, 0.0, True, REASON_HOLD_NOT_RECEIVED)
        if self.hold:
            return MotionOutput(0.0, 0.0, True, REASON_HOLD_TRUE, self.hold_reason)
        if t - self.hold_time > self.s.motion_hold_timeout_s:
            return MotionOutput(0.0, 0.0, True, REASON_HOLD_EXPIRED, self.hold_reason)
        if self.cmd is None:
            return MotionOutput(0.0, 0.0, True, REASON_CMD_NOT_RECEIVED)
        if t - self.cmd_time > self.s.cmd_vel_timeout_s:
            return MotionOutput(0.0, 0.0, True, REASON_CMD_STALE)
        vx, wz = self.cmd
        if not (math.isfinite(vx) and math.isfinite(wz)):
            return MotionOutput(0.0, 0.0, True, REASON_CMD_NOT_FINITE)
        nf = _clamp(vx / (self.s.max_linear_speed_mps if vx >= 0 else self.s.max_reverse_speed_mps))
        nt = _clamp(wz / self.s.max_angular_speed_radps)
        c = self.compensation
        forward = compensate(nf, c.pair('forward' if nf >= 0 else 'reverse'))
        turn = compensate(nt, c.pair('turn'))
        return MotionOutput(forward, turn, forward == 0.0 and turn == 0.0, REASON_DRIVE, '', nf, nt)

    def state(self, t: float) -> dict:
        return {'cmd_vel_age_s': None if self.cmd_time is None else t - self.cmd_time,
                'hold': self.hold, 'hold_reason': self.hold_reason, 'hold_mode': self.hold_mode,
                'hold_age_s': None if self.hold_time is None else t - self.hold_time,
                'compensation_revision': self.compensation.config_revision, 'compensated_directions': self.compensation.active_directions()}
