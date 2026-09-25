from gouda_signal.roi import (
    NormalizedROI,
    aspect_fit_rect,
    normalized_rect,
    point_to_normalized,
    roi_to_pixels,
)


def test_aspect_fit_letterbox_is_excluded_from_pointer_mapping():
    fitted = aspect_fit_rect(1000, 400, 640, 480)
    assert round(fitted.width, 3) == 533.333
    assert round(fitted.x, 3) == 233.333
    assert point_to_normalized(100.0, 200.0, fitted) is None
    mapped = point_to_normalized(fitted.x + fitted.width / 2, fitted.height / 2, fitted)
    assert mapped == (0.5, 0.5)


def test_roi_drag_normalizes_reverse_direction_and_clamps_minimum():
    roi = normalized_rect((0.91, 0.9), (0.8, 0.78))
    assert roi is not None
    assert roi.width >= 0.08 and roi.height >= 0.08
    assert roi.x + roi.width <= 1.0
    assert roi.y + roi.height <= 1.0
    assert roi.x == 0.8 and roi.y == 0.78


def test_pixel_mapping_uses_full_source_aspect_and_includes_edges():
    roi = NormalizedROI(0.25, 0.25, 0.5, 0.5)
    assert roi_to_pixels(roi, 1920, 1080) == (480, 270, 1440, 810)
    assert roi_to_pixels(NormalizedROI(0.99, 0.99, 0.5, 0.5), 100, 50) == (99, 49, 100, 50)


def test_zero_sized_view_or_image_maps_to_empty_geometry():
    assert aspect_fit_rect(0, 100, 640, 480).width == 0
    assert roi_to_pixels(NormalizedROI(0, 0, 1, 1), 0, 20) is None
