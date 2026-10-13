"""gouda_motion_controller core (ND-11): cmd_vel -> normalized joystick command, with neutral on hold / stale input.

No ROS dependency; the lifecycle node wraps it. Design: design/model.yaml ND-11, IFD-15 (cmd_vel), IFD-16
(vehicle/joystick_command), IFD-40 (control/motion_hold), SO-08; tests TS-07, TS-13.

Rules (DEC-004, RQ-I063, RQ-I020):
- Output is neutral when motion_hold has never been received, when hold is true, when the last hold is older than
  motion_hold_timeout_s (PRM-42), when cmd_vel has never been received, is older than cmd_vel_timeout_s (PRM-08) or is not
  finite. Only hold=false AND a fresh finite cmd_vel gives a non-neutral output.
- Normalization: forward = linear.x / max_linear_speed_mps (PRM-39), turn = angular.z / max_angular_speed_radps (PRM-40),
  both saturated to [-1, 1]. Nothing else limits the speed (RQ-I020: the only speed limit path is Nav2's SpeedLimit).
- All thresholds are settings passed in by the node from the generated parameter file; nothing numeric lives here.
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

    def validate(self) -> None:
        for name in ('cmd_vel_timeout_s', 'max_linear_speed_mps', 'max_angular_speed_radps', 'motion_hold_timeout_s'):
            v = getattr(self, name)
            if not (isinstance(v, (int, float)) and math.isfinite(v) and v > 0):
                raise ValueError(f'{name} must be a positive finite number, got {v!r}')


@dataclass(frozen=True)
class MotionOutput:
    forward: float        # IFD-16 axes[0], [-1, 1]
    turn: float           # IFD-16 axes[1], [-1, 1]; positive = left (angular.z > 0, REP-103)
    neutral: bool
    reason: str
    hold_reason: str = ''


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

    # ---- inputs ----
    def on_cmd_vel(self, linear_x: float, angular_z: float, t: float) -> None:
        self.cmd = (float(linear_x), float(angular_z)); self.cmd_time = t

    def on_motion_hold(self, hold: bool, reason: str, mode: int, t: float) -> None:
        self.hold = bool(hold); self.hold_reason = reason; self.hold_mode = int(mode); self.hold_time = t

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
        forward = _clamp(vx / self.s.max_linear_speed_mps)
        turn = _clamp(wz / self.s.max_angular_speed_radps)
        return MotionOutput(forward, turn, forward == 0.0 and turn == 0.0, REASON_DRIVE)

    def state(self, t: float) -> dict:
        return {'cmd_vel_age_s': None if self.cmd_time is None else t - self.cmd_time,
                'hold': self.hold, 'hold_reason': self.hold_reason, 'hold_mode': self.hold_mode,
                'hold_age_s': None if self.hold_time is None else t - self.hold_time}
