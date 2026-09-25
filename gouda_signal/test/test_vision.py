import pytest

np = pytest.importorskip("numpy")

from gouda_signal.classifier import RawColor
from gouda_signal.vision import measure_bgr


def test_uniform_red_and_green_frames_match_roi_color_rules():
    red = np.zeros((20, 20, 3), dtype=np.uint8)
    red[..., 2] = 255
    green = np.zeros((20, 20, 3), dtype=np.uint8)
    green[..., 1] = 255
    assert measure_bgr(red).color is RawColor.RED
    assert measure_bgr(green).color is RawColor.GREEN


def test_both_colors_are_ambiguous_and_neutral_is_unknown():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    frame[:10, :10, 2] = 255
    frame[20:30, 20:30, 1] = 255
    assert measure_bgr(frame).color is RawColor.AMBIGUOUS
    neutral = np.full((20, 20, 3), 128, dtype=np.uint8)
    assert measure_bgr(neutral).color is RawColor.NONE


def test_minimum_fraction_is_point_eight_percent_of_roi():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    frame[:8, :10, 1] = 255
    assert measure_bgr(frame).color is RawColor.GREEN
    frame[7, 0, 1] = 0
    assert measure_bgr(frame).color is RawColor.NONE


def test_low_brightness_and_low_saturation_pixels_do_not_count():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    frame[:20, :20, 2] = 71  # Below normalized brightness .28.
    frame[20:40, :20] = (200, 200, 255)  # Saturation is below .42.
    assert measure_bgr(frame).color is RawColor.NONE
