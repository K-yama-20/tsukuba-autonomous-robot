import math
import numpy as np
from gouda_sensors.scan import project


def test_scan_keeps_nearest_and_rejects_height_nan_and_blind_zone():
    ranges = project(np.array([1., 2., 3., float('nan'), .1]),
                     np.zeros(5), np.array([0., 0., 1., 0., 0.]))
    assert ranges[360] == 1.
    assert sum(math.isfinite(r) for r in ranges) == 1


def test_scan_wraps_at_pi_and_keeps_unknown_unobserved():
    ranges = project(np.array([-1., -2.]), np.array([0., -0.]), np.zeros(2))
    assert ranges[0] == 1.
    assert math.isinf(ranges[359])
