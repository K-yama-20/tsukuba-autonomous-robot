"""Aspect-fit and normalized ROI geometry shared by the GUI and tests."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class NormalizedROI:
    x: float
    y: float
    width: float
    height: float


def aspect_fit_rect(
    view_width: float, view_height: float, image_width: float, image_height: float
) -> Rect:
    """Return the centered image rectangle for aspect-fit display."""

    if min(view_width, view_height, image_width, image_height) <= 0:
        return Rect(0.0, 0.0, 0.0, 0.0)
    scale = min(view_width / image_width, view_height / image_height)
    width = image_width * scale
    height = image_height * scale
    return Rect((view_width - width) / 2, (view_height - height) / 2, width, height)


def point_to_normalized(
    x: float, y: float, displayed_image: Rect
) -> tuple[float, float] | None:
    """Map a view point into image coordinates, rejecting letterbox bars."""

    if displayed_image.width <= 0 or displayed_image.height <= 0:
        return None
    if not (
        displayed_image.x <= x <= displayed_image.x + displayed_image.width
        and displayed_image.y <= y <= displayed_image.y + displayed_image.height
    ):
        return None
    return (
        min(1.0, max(0.0, (x - displayed_image.x) / displayed_image.width)),
        min(1.0, max(0.0, (y - displayed_image.y) / displayed_image.height)),
    )


def normalized_rect(
    first: tuple[float, float], second: tuple[float, float], minimum_side: float = 0.08
) -> NormalizedROI | None:
    """Make the iOS prototype's clamped normalized ROI from two drag points."""

    values = (*first, *second)
    if not all(math.isfinite(value) for value in values):
        return None
    left, right = sorted((min(1.0, max(0.0, first[0])), min(1.0, max(0.0, second[0]))))
    top, bottom = sorted((min(1.0, max(0.0, first[1])), min(1.0, max(0.0, second[1]))))
    width = right - left
    height = bottom - top
    if width <= 0 or height <= 0:
        return None
    minimum = min(1.0, max(0.02, minimum_side))
    width = min(1.0, max(minimum, width))
    height = min(1.0, max(minimum, height))
    return NormalizedROI(min(left, 1.0 - width), min(top, 1.0 - height), width, height)


def roi_to_pixels(
    roi: NormalizedROI, image_width: int, image_height: int
) -> tuple[int, int, int, int] | None:
    """Map a normalized ROI to a clamped, non-empty ``(x0,y0,x1,y1)`` crop."""

    if image_width <= 0 or image_height <= 0:
        return None
    if not all(math.isfinite(v) for v in (roi.x, roi.y, roi.width, roi.height)):
        return None
    x = min(1.0, max(0.0, roi.x))
    y = min(1.0, max(0.0, roi.y))
    width = min(1.0 - x, max(0.0, roi.width))
    height = min(1.0 - y, max(0.0, roi.height))
    x0 = min(image_width - 1, max(0, math.floor(x * image_width)))
    y0 = min(image_height - 1, max(0, math.floor(y * image_height)))
    x1 = min(image_width, max(x0 + 1, math.ceil((x + width) * image_width)))
    y1 = min(image_height, max(y0 + 1, math.ceil((y + height) * image_height)))
    return x0, y0, x1, y1
