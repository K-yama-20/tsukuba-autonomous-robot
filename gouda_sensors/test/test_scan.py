import math
import numpy as np
from gouda_sensors.scan import offset_stamp, project, shifted_header


def test_scan_keeps_nearest_and_rejects_height_nan_and_blind_zone():
    ranges = project(np.array([1., 2., 3., float('nan'), .1]),
                     np.zeros(5), np.array([0., 0., 1., 0., 0.]))
    assert ranges[360] == 1.
    assert sum(math.isfinite(r) for r in ranges) == 1


def test_scan_wraps_at_pi_and_keeps_unknown_unobserved():
    ranges = project(np.array([-1., -2.]), np.array([0., -0.]), np.zeros(2))
    assert ranges[0] == 1.
    assert math.isinf(ranges[359])


def test_offset_stamp_applies_clock_correction_with_carry():
    assert offset_stamp(10, 900_000_000, 0.2) == (11, 100_000_000)
    assert offset_stamp(10, 100_000_000, -0.2) == (9, 900_000_000)

def test_offset_stamp_rejects_negative_and_nonfinite_results():
    import pytest
    with pytest.raises(ValueError):
        offset_stamp(0, 0, -0.001)
    with pytest.raises(ValueError):
        offset_stamp(1, 0, float('nan'))


def test_shifted_header_does_not_mutate_raw_header():
    from types import SimpleNamespace
    raw = SimpleNamespace(frame_id='hesai_lidar', stamp=SimpleNamespace(sec=12, nanosec=900_000_000))
    shifted = shifted_header(raw, 0.2)
    assert (shifted.stamp.sec, shifted.stamp.nanosec) == (13, 100_000_000)
    assert (raw.stamp.sec, raw.stamp.nanosec) == (12, 900_000_000)
