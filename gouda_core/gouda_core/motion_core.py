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
- Speed feedback (REV-241, DEC-450; #65): when the human enables it in /config (IFD-52 speed_feedback_enabled; off by default),
  each axis is driven by a feedforward from the measured stick -> speed map (Feedforward, DEC-445 values from the generated
  parameter file) plus a PI on the speed error against localization/odometry (IFD-25). The dead-band compensation above is not
  used while the feedback layer is on (the feedforward already contains the dead band; nothing is compensated twice).
  The integral stops while the output is saturated in the direction of the error, is clamped to the integral limit, and is
  reset to 0 (with a neutral axis) when that axis' target is 0 or changes sign, on every neutral reason above, on manual
  priority on the ESP32 and on deactivation. When the odometry is older than the /config timeout, never received or not set,
  the layer drives on the feedforward alone (it never stops for that) and says so in the feedback record.
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
REASON_MANUAL_PRIORITY = 'manual priority on the ESP32 (speed feedback on)'


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


# ---- speed feedback (REV-241, DEC-450) ----
FEEDBACK_FIELDS = ('speed_feedback_enabled', 'forward_kp', 'forward_ki', 'forward_i_limit', 'turn_kp', 'turn_ki', 'turn_i_limit',
                   'odometry_timeout_s')
MODE_OFF = 'off'                # the layer is not enabled: the plain normalization (+ the dead-band compensation)
MODE_FF_PI = 'ff_pi'            # feedforward + PI
MODE_FF_ONLY = 'ff_only'        # feedforward alone (odometry stale / not received / PI values not set)
MODE_NEUTRAL = 'neutral'        # a neutral reason, manual priority or a zero target: integrals are 0
MODE_NO_FEEDFORWARD = 'no_feedforward'   # enabled, but the feedforward table is not usable: the plain normalization is used


@dataclass(frozen=True)
class FeedforwardAxis:
    """Measured stick -> speed of one direction (DEC-445, FILE-MIN-SPEED-20261107), as a piecewise-linear map inverted here.
    Points (stick, speed): (stop_stick, 0) measured stop, (move_stick, min_speed) measured slowest motion, optionally
    (mid_stick, mid_speed) measured, and (1, full_speed) NOT measured (the normalization's assumption: PRM-39 / PRM-78 / PRM-40).
    A positive target slower than min_speed lies between the stop stick and the move stick (the dead band: the PI has to
    lift it); faster targets follow the line through the measured points up to the full stick."""
    stop_stick: float
    move_stick: float
    min_speed: float
    full_speed: float
    mid_stick: Optional[float] = None
    mid_speed: Optional[float] = None

    def points(self) -> list:
        p = [(0.0, self.stop_stick), (self.min_speed, self.move_stick)]
        if self.mid_stick is not None and self.mid_speed is not None:
            p.append((self.mid_speed, self.mid_stick))
        p.append((self.full_speed, 1))
        return p

    def problems(self) -> list:
        vals = [self.stop_stick, self.move_stick, self.min_speed, self.full_speed] + ([self.mid_stick, self.mid_speed] if self.mid_stick is not None else [])
        if not all(_set(v) for v in vals):
            return ['a feedforward value is not a finite number']
        p = self.points()
        if not (0 <= self.stop_stick):
            return [f'stop_stick {self.stop_stick} below 0']
        if any(b[0] <= a[0] or b[1] <= a[1] for a, b in zip(p, p[1:])):
            return [f'feedforward points are not increasing: {p}']
        return []

    def stick(self, speed: float) -> float:
        """Stick amount (>= 0) for |speed| > 0; 0 for 0."""
        s = abs(speed)
        if s == 0:
            return 0.0
        p = self.points()
        for (v0, k0), (v1, k1) in zip(p, p[1:]):
            if s <= v1:
                return k0 + (k1 - k0) * (s - v0) / (v1 - v0)
        return float(p[-1][1])


@dataclass(frozen=True)
class Feedforward:
    forward: FeedforwardAxis
    reverse: FeedforwardAxis
    turn: FeedforwardAxis

    def problems(self) -> list:
        return [f'{n}: {e}' for n in ('forward', 'reverse', 'turn') for e in getattr(self, n).problems()]


@dataclass(frozen=True)
class Feedback:
    """IFD-52 speed-feedback values (/config); None = not set. Gains are stick amounts per (m/s) or (rad/s) for P and per
    (m/s * s) or (rad/s * s) for I; i_limit is the largest |integral| in stick amount."""
    enabled: bool = False
    forward_kp: Optional[float] = None
    forward_ki: Optional[float] = None
    forward_i_limit: Optional[float] = None
    turn_kp: Optional[float] = None
    turn_ki: Optional[float] = None
    turn_i_limit: Optional[float] = None
    odometry_timeout_s: Optional[float] = None

    def problems(self) -> list:
        out = []
        for k in ('forward_kp', 'forward_ki', 'turn_kp', 'turn_ki', 'forward_i_limit', 'turn_i_limit'):
            v = getattr(self, k)
            if _set(v) and v < 0:
                out.append(f'{k}={v!r} is negative')
        for k in ('forward_i_limit', 'turn_i_limit'):
            v = getattr(self, k)
            if _set(v) and v > 1:
                out.append(f'{k}={v!r} is above a full stick')
        v = self.odometry_timeout_s
        if _set(v) and not v > 0:
            out.append(f'odometry_timeout_s={v!r} is not above zero')
        return out

    def pi_ready(self) -> bool:
        return all(_set(getattr(self, k)) for k in FEEDBACK_FIELDS[1:])


NO_FEEDBACK = Feedback()


@dataclass
class AxisTerms:
    target: float = 0.0
    measured: float = math.nan
    ff: float = 0.0
    p: float = 0.0
    i: float = 0.0
    out: float = 0.0


@dataclass(frozen=True)
class MotionOutput:
    forward: float        # IFD-16 axes[0], [-1, 1]
    turn: float           # IFD-16 axes[1], [-1, 1]; positive = left (angular.z > 0, REP-103)
    neutral: bool
    reason: str
    hold_reason: str = ''
    normalized_forward: float = 0.0   # before the dead-band compensation (for the record)
    normalized_turn: float = 0.0
    feedback_mode: str = MODE_OFF
    feedback_reason: str = ''
    forward_terms: Optional[AxisTerms] = None
    turn_terms: Optional[AxisTerms] = None
    odometry_age_s: Optional[float] = None


def _clamp(v: float) -> float:
    return float(max(-1, min(1, v)))


class AxisPI:
    """One axis' integral. The integral is in stick amount."""

    def __init__(self):
        self.i = 0.0
        self.sign = 0

    def reset(self) -> None:
        self.i = 0.0; self.sign = 0

    def step(self, target: float, measured: Optional[float], ff_abs: float, kp: float, ki: float, i_limit: float, dt: Optional[float]) -> AxisTerms:
        """target != 0. measured None: feedforward alone (the integral is reset). The output keeps the target's sign or is 0
        (the PI never reverses the stick)."""
        sign = 1 if target > 0 else -1
        if sign != self.sign:
            self.i = 0.0; self.sign = sign
        ff = sign * ff_abs
        if measured is None:
            self.i = 0.0
            return AxisTerms(target, math.nan, ff, 0.0, 0.0, _same_sign(ff, sign))
        e = target - measured
        p = kp * e
        if dt is not None and dt > 0:
            cand = max(-i_limit, min(i_limit, self.i + ki * e * dt))
            raw = (ff + p + cand) * sign   # in the target's direction; the output is clamped to [0, 1] of it
            saturated = (raw > 1 and e * sign > 0) or (raw < 0 and e * sign < 0)   # conditional integration on the total stick
            if not saturated:
                self.i = cand
        out = _same_sign(ff + p + self.i, sign)
        return AxisTerms(target, measured, ff, p, self.i, out)


def _same_sign(v: float, sign: int) -> float:
    """Clamp to [0, 1] in the direction of sign (0 = neutral, never the opposite direction)."""
    return float(min(1, max(0, v * sign)) * sign)


class MotionCore:
    """SO-08: last_cmd_vel_time / last cmd_vel, motion_hold_state (hold, reason, mode, time). Volatile; neutral at start.
    REV-241: also the speed-feedback state (the last odometry, the ESP32 source, the two integrals)."""

    def __init__(self, settings: MotionSettings, feedforward: Optional[Feedforward] = None):
        settings.validate()
        self.s = settings
        self.cmd: Optional[tuple] = None       # (linear_x, angular_z)
        self.cmd_time: Optional[float] = None
        self.hold: Optional[bool] = None
        self.hold_reason = ''
        self.hold_mode = 0
        self.hold_time: Optional[float] = None
        self.compensation = NO_COMPENSATION
        self.feedforward = feedforward
        self.feedforward_problems = ['feedforward table not given'] if feedforward is None else feedforward.problems()
        self.feedback = NO_FEEDBACK
        self.odom: Optional[tuple] = None      # (linear_x, angular_z) in base_link (IFD-25 twist)
        self.odom_time: Optional[float] = None
        self.vehicle_source = ''               # the ESP32 STATUS source (IFD-38): 'manual' = manual priority
        self.pi_forward = AxisPI(); self.pi_turn = AxisPI()
        self.last_out_t: Optional[float] = None

    # ---- inputs ----
    def on_cmd_vel(self, linear_x: float, angular_z: float, t: float) -> None:
        self.cmd = (float(linear_x), float(angular_z)); self.cmd_time = t

    def on_motion_hold(self, hold: bool, reason: str, mode: int, t: float) -> None:
        self.hold = bool(hold); self.hold_reason = reason; self.hold_mode = int(mode); self.hold_time = t

    def on_odometry(self, linear_x: float, angular_z: float, t: float) -> None:
        if math.isfinite(linear_x) and math.isfinite(angular_z):
            self.odom = (float(linear_x), float(angular_z)); self.odom_time = t

    def on_vehicle_source(self, source: str) -> None:
        self.vehicle_source = str(source)

    def set_compensation(self, comp: Compensation) -> list:
        """Use comp from the next output on (DEC-181). Returns its problems; a compensation with problems is not used and the
        previous one stays."""
        bad = comp.problems()
        if not bad:
            self.compensation = comp
        return bad

    def set_feedback(self, fb: Feedback) -> list:
        """REV-241: used from the next output on. A setting with problems is not used (the previous one stays)."""
        bad = fb.problems()
        if not bad:
            if fb.enabled != self.feedback.enabled:
                self.reset_feedback()
            self.feedback = fb
        return bad

    def reset_feedback(self) -> None:
        self.pi_forward.reset(); self.pi_turn.reset(); self.last_out_t = None

    # ---- decision ----
    def _neutral(self, t: float) -> Optional[MotionOutput]:
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
        if self.feedback.enabled and self.vehicle_source == 'manual':
            return MotionOutput(0.0, 0.0, True, REASON_MANUAL_PRIORITY)
        return None

    def output(self, t: float) -> MotionOutput:
        n = self._neutral(t)
        if n is not None:
            self.reset_feedback()
            if self.feedback.enabled:
                return MotionOutput(n.forward, n.turn, True, n.reason, n.hold_reason, feedback_mode=MODE_NEUTRAL, feedback_reason=n.reason,
                                    odometry_age_s=self._odom_age(t))
            return n
        vx, wz = self.cmd
        nf = _clamp(vx / (self.s.max_linear_speed_mps if vx >= 0 else self.s.max_reverse_speed_mps))
        nt = _clamp(wz / self.s.max_angular_speed_radps)
        if self.feedback.enabled and not self.feedforward_problems:
            return self._feedback_output(t, vx, wz, nf, nt)
        c = self.compensation
        forward = compensate(nf, c.pair('forward' if nf >= 0 else 'reverse'))
        turn = compensate(nt, c.pair('turn'))
        if self.feedback.enabled:   # enabled but the feedforward table is not usable: the plain path, said in the record
            return MotionOutput(forward, turn, forward == 0.0 and turn == 0.0, REASON_DRIVE, '', nf, nt, MODE_NO_FEEDFORWARD,
                                '; '.join(self.feedforward_problems), odometry_age_s=self._odom_age(t))
        return MotionOutput(forward, turn, forward == 0.0 and turn == 0.0, REASON_DRIVE, '', nf, nt)

    def _odom_age(self, t: float) -> Optional[float]:
        return None if self.odom_time is None else t - self.odom_time

    def _feedback_output(self, t: float, vx: float, wz: float, nf: float, nt: float) -> MotionOutput:
        fb, ff = self.feedback, self.feedforward
        age = self._odom_age(t)
        if not fb.pi_ready():
            mode, why = MODE_FF_ONLY, 'PI values not set in /config'
        elif age is None:
            mode, why = MODE_FF_ONLY, 'odometry never received'
        elif age > fb.odometry_timeout_s:
            mode, why = MODE_FF_ONLY, f'odometry stale ({age:.3f} s)'
        else:
            mode, why = MODE_FF_PI, ''
        dt = None if self.last_out_t is None else t - self.last_out_t
        if dt is not None and dt > self.s.cmd_vel_timeout_s:
            dt = None
        self.last_out_t = t
        mv = self.odom[0] if (mode == MODE_FF_PI) else None
        mw = self.odom[1] if (mode == MODE_FF_PI) else None
        meas = self.odom if self.odom is not None else (math.nan, math.nan)
        if vx == 0:
            self.pi_forward.reset(); ft = AxisTerms(0.0, meas[0])
        else:
            axis = ff.forward if vx > 0 else ff.reverse
            ft = self.pi_forward.step(vx, mv, axis.stick(vx), fb.forward_kp or 0.0, fb.forward_ki or 0.0, fb.forward_i_limit or 0.0, dt)
        if wz == 0:
            self.pi_turn.reset(); tt = AxisTerms(0.0, meas[1])
        else:
            tt = self.pi_turn.step(wz, mw, ff.turn.stick(wz), fb.turn_kp or 0.0, fb.turn_ki or 0.0, fb.turn_i_limit or 0.0, dt)
        if mode != MODE_FF_PI:
            ft.measured, tt.measured = meas[0], meas[1]
        if vx == 0 and wz == 0:
            mode, why = MODE_NEUTRAL, 'zero target'
        forward, turn = ft.out, tt.out
        return MotionOutput(forward, turn, forward == 0.0 and turn == 0.0, REASON_DRIVE, '', nf, nt, mode, why, ft, tt, age)

    def state(self, t: float) -> dict:
        return {'cmd_vel_age_s': None if self.cmd_time is None else t - self.cmd_time,
                'hold': self.hold, 'hold_reason': self.hold_reason, 'hold_mode': self.hold_mode,
                'hold_age_s': None if self.hold_time is None else t - self.hold_time,
                'compensation_revision': self.compensation.config_revision, 'compensated_directions': self.compensation.active_directions(),
                'speed_feedback_enabled': self.feedback.enabled, 'odometry_age_s': self._odom_age(t), 'vehicle_source': self.vehicle_source}
