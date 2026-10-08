"""Vectorized color evidence measurement for BGR camera frames."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .classifier import RawColor


@dataclass(frozen=True)
class ColorEvidence:
    color: RawColor
    confidence: float
    red_fraction: float
    green_fraction: float


MINIMUM_COLOR_FRACTION = 0.008


def measure_bgr(frame: np.ndarray) -> ColorEvidence:
    """Measure red/green pixel fractions with the iOS core's HSV thresholds.

    ``frame`` must be a BGR image or ROI crop. Thresholds apply to the whole
    ROI: value >= .28, saturation >= .42, red hue <= 22 or >= 338 degrees,
    and green hue from 72 through 175 degrees.
    """

    if frame is None or frame.ndim != 3 or frame.shape[2] != 3:
        return ColorEvidence(RawColor.NONE, 0.0, 0.0, 0.0)
    height, width = frame.shape[:2]
    total = height * width
    if total == 0:
        return ColorEvidence(RawColor.NONE, 0.0, 0.0, 0.0)

    # Use float32 arrays so the analysis remains cheap at the app's 1280x960
    # preview ceiling while matching the normalized RGB math in the iOS core.
    bgr = frame.astype(np.float32, copy=False) / np.float32(255.0)
    blue, green, red = bgr[..., 0], bgr[..., 1], bgr[..., 2]
    maximum = np.maximum(np.maximum(red, green), blue)
    minimum = np.minimum(np.minimum(red, green), blue)
    delta = maximum - minimum
    saturation = np.zeros_like(maximum)
    np.divide(delta, maximum, out=saturation, where=maximum > 0)
    qualifying = (maximum >= np.float32(0.28)) & (saturation >= np.float32(0.42))

    hue = np.zeros_like(maximum)
    has_delta = delta > 0
    red_max = has_delta & (maximum == red)
    green_max = has_delta & ~red_max & (maximum == green)
    blue_max = has_delta & ~red_max & ~green_max
    red_ratio = np.zeros_like(maximum)
    green_ratio = np.zeros_like(maximum)
    blue_ratio = np.zeros_like(maximum)
    np.divide(green - blue, delta, out=red_ratio, where=red_max)
    np.divide(blue - red, delta, out=green_ratio, where=green_max)
    np.divide(red - green, delta, out=blue_ratio, where=blue_max)
    hue[red_max] = np.remainder(red_ratio[red_max], 6.0) * 60.0
    hue[green_max] = (green_ratio[green_max] + 2.0) * 60.0
    hue[blue_max] = (blue_ratio[blue_max] + 4.0) * 60.0
    hue[hue < 0] += 360.0

    red_pixels = qualifying & ((hue <= 22.0) | (hue >= 338.0))
    green_pixels = qualifying & (hue >= 72.0) & (hue <= 175.0)
    red_fraction = float(np.count_nonzero(red_pixels)) / total
    green_fraction = float(np.count_nonzero(green_pixels)) / total

    has_red = red_fraction >= MINIMUM_COLOR_FRACTION
    has_green = green_fraction >= MINIMUM_COLOR_FRACTION
    if not has_red and not has_green:
        color = RawColor.NONE
        confidence = 0.0
    elif has_red and has_green:
        color = RawColor.AMBIGUOUS
        confidence = min(1.0, max(red_fraction, green_fraction) * 8.0)
    else:
        color = RawColor.GREEN if green_fraction > red_fraction else RawColor.RED
        winner = max(red_fraction, green_fraction)
        loser = min(red_fraction, green_fraction)
        dominance = min(1.0, max(0.0, (winner - loser) / max(winner, 0.008)))
        coverage = min(1.0, winner / 0.08)
        confidence = min(1.0, max(0.0, 0.2 + 0.5 * coverage + 0.3 * dominance))
    return ColorEvidence(color, confidence, red_fraction, green_fraction)
