"""Fail-closed cloud contract. Reception deadlines use monotonic time."""
import math


class CloudContract:
    def __init__(self, frame='hesai_lidar', timeout=0.35, max_age=0.35):
        self.frame, self.timeout, self.max_age = frame, timeout, max_age
        self.last_rx = None
        self.last_stamp = None
        self.valid = False
        self.reason = 'NO_INPUT'

    def observe(self, *, frame, stamp, now_ros, now_mono, xyz, fields):
        reason = 'OK'
        if frame != self.frame:
            reason = 'FRAME'
        elif not {'x', 'y', 'z'}.issubset(fields):
            reason = 'FIELDS'
        elif not math.isfinite(stamp) or stamp <= 0 or not -0.05 <= now_ros - stamp <= self.max_age:
            reason = 'STAMP_AGE'
        elif self.last_stamp is not None and stamp <= self.last_stamp:
            reason = 'STAMP_NONINCREASING'
        elif not xyz or not all(all(math.isfinite(float(v)) for v in p) for p in xyz):
            reason = 'EMPTY_OR_NONFINITE'
        self.last_rx = now_mono
        self.last_stamp = stamp
        self.valid, self.reason = reason == 'OK', reason
        return self.valid

    def check(self, now_mono, now_ros):
        if self.last_rx is None or now_mono - self.last_rx >= self.timeout:
            return False, 'STALE'
        if self.last_stamp is None or not -0.05 <= now_ros - self.last_stamp <= self.max_age:
            return False, 'STAMP_AGE'
        return self.valid, self.reason
