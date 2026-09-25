"""Dependency-light temporal rules for manual pedestrian-signal ROI evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math


class SignalState(str, Enum):
    GREEN = "GREEN"
    RED = "RED"
    UNKNOWN = "UNKNOWN"


class RawColor(str, Enum):
    GREEN = "green"
    RED = "red"
    NONE = "none"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class Observation:
    state: SignalState
    reason: str
    confidence: float

    def __post_init__(self) -> None:
        value = self.confidence if math.isfinite(self.confidence) else 0.0
        object.__setattr__(self, "confidence", min(1.0, max(0.0, value)))


class SignalClassifier:
    """Converts successive ROI color measurements into conservative states.

    Confidence is a heuristic evidence score, never a probability. This class
    deliberately knows nothing about camera detection or object tracking.
    """

    green_confirmation_seconds = 1.2
    blink_recovery_seconds = 2.0
    maximum_frame_gap_seconds = 0.45

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._green_since: float | None = None
        self._recovery_green_since: float | None = None
        self._last_frame_time: float | None = None
        self._previous_raw: RawColor | None = None
        self._green_fall_times: list[float] = []
        self._blink_latched = False

    def invalidate(self, reason: str = "invalidated") -> Observation:
        self.reset()
        return Observation(SignalState.UNKNOWN, reason, 0.0)

    def process(
        self, color: RawColor | str, timestamp: float, confidence: float = 0.0
    ) -> Observation:
        """Process one fresh ROI measurement using a monotonic timestamp."""

        if not math.isfinite(timestamp):
            return self.invalidate("invalid_timestamp")
        try:
            raw = color if isinstance(color, RawColor) else RawColor(color)
        except ValueError:
            raw = RawColor.AMBIGUOUS

        if self._last_frame_time is not None:
            delta = timestamp - self._last_frame_time
            if delta <= 0:
                self.reset()
                self._last_frame_time = timestamp
                return Observation(SignalState.UNKNOWN, "non_monotonic_timestamp", 0.0)
            if delta > self.maximum_frame_gap_seconds:
                self._green_since = None
                self._recovery_green_since = None
                if self._previous_raw == RawColor.GREEN:
                    self._record_green_fall(self._last_frame_time)
                    self._previous_raw = RawColor.NONE

        self._last_frame_time = timestamp
        reason = {
            RawColor.GREEN: "roi_green_pixels",
            RawColor.RED: "roi_red_pixels",
            RawColor.AMBIGUOUS: "roi_color_ambiguous",
            RawColor.NONE: "roi_color_not_found",
        }[raw]

        if self._previous_raw != raw:
            if self._previous_raw == RawColor.GREEN and raw != RawColor.GREEN:
                self._record_green_fall(timestamp)
            self._previous_raw = raw

        score = confidence if math.isfinite(confidence) else 0.0
        score = min(1.0, max(0.0, score))
        if raw == RawColor.RED:
            self._green_since = None
            self._recovery_green_since = None
            self._blink_latched = False
            self._green_fall_times.clear()
            return Observation(SignalState.RED, reason, score)

        if raw != RawColor.GREEN:
            self._green_since = None
            self._recovery_green_since = None
            return Observation(
                SignalState.UNKNOWN,
                "green_blink_latched" if self._blink_latched else reason,
                0.0,
            )

        if self._green_since is None:
            self._green_since = timestamp
        if self._blink_latched:
            if self._recovery_green_since is None:
                self._recovery_green_since = timestamp
            if timestamp - self._recovery_green_since >= self.blink_recovery_seconds:
                self._blink_latched = False
                self._green_fall_times.clear()
            else:
                return Observation(SignalState.UNKNOWN, "green_blink_latched", score)

        if timestamp - self._green_since < self.green_confirmation_seconds:
            return Observation(SignalState.UNKNOWN, "green_warmup", score)
        return Observation(SignalState.GREEN, "steady_green", score)

    def _record_green_fall(self, timestamp: float) -> None:
        self._green_fall_times.append(timestamp)
        self._green_fall_times = [
            fall for fall in self._green_fall_times if timestamp - fall <= 3.2
        ]
        if len(self._green_fall_times) >= 2:
            self._blink_latched = True
            self._green_since = None
            self._recovery_green_since = None
