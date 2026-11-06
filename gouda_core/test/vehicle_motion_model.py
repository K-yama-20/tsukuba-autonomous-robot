"""Test only: the wheelchair's start-of-motion behaviour as the human described it (A lock, B waiting, C running), to check that the
motion_start test recovers known values. These values are inventions of the test, not vehicle values."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

LOCKED, WAITING, RUNNING = 'A', 'B', 'C'


@dataclass
class ModelValues:
    threshold: float = 0.12
    delay_s: float = 0.3
    t_lock_s: float = 1.2
    shock_g: float = 0.4          # one short acceleration spike when the lock releases
    shock_s: float = 0.01
    rise_s: float = 0.05          # motion after the release
    noise_accel: float = 0.01
    noise_yaw: float = 0.002
    gain_accel: float = 1.0
    gain_yaw: float = 1.0


class Model:
    def __init__(self, v: ModelValues = ModelValues(), seed: int = 1):
        self.v = v; self.state = LOCKED; self.t_change = None; self.t_low = None; self.t_run = None; self.forward = self.turn = 0.0
        self.rng = random.Random(seed)

    def command(self, t: float, forward: float, turn: float):
        self.forward, self.turn = forward, turn
        high = math.hypot(forward, turn) >= self.v.threshold
        if self.state == LOCKED and high:
            self.state, self.t_change = WAITING, t
        elif self.state == WAITING:
            if not high: self.state = LOCKED
            elif t - self.t_change >= self.v.delay_s: self.state, self.t_run, self.t_low = RUNNING, t, None
        elif self.state == RUNNING:
            if high: self.t_low = None
            elif self.t_low is None: self.t_low = t
            elif t - self.t_low >= self.v.t_lock_s: self.state = LOCKED

    def imu(self, t: float) -> tuple:
        """(forward acceleration, yaw rate)."""
        a = self.rng.gauss(0, self.v.noise_accel); w = self.rng.gauss(0, self.v.noise_yaw)
        if self.state == RUNNING:
            since = t - self.t_run
            if since < self.v.shock_s: a += self.v.shock_g
            if since >= self.v.rise_s and self.t_low is None:
                a += self.v.gain_accel * self.forward; w += self.v.gain_yaw * self.turn
        return a, w
