import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from p2l import P2LParams, gouda_params, laserscan, n_bins  # noqa: E402


def P(*pts):
    return np.array(pts, dtype=np.float32)


def test_default_bins_is_360():
    assert n_bins(P2LParams()) == 360


def test_point_in_band_lands_in_its_bin():
    p = gouda_params(-0.065, 1.085, 6.0)
    r, w = laserscan(P((1.0, 0.0, 0.5)), p)
    i = int((0.0 - np.float32(-math.pi)) / np.float32(math.pi / 180))
    assert i == 180 and math.isclose(r[i], 1.0, rel_tol=1e-6) and w[i] == 0
    assert np.isinf(np.delete(r, i)).all()


def test_band_ends_are_kept_and_outside_rejected():
    p = gouda_params(-0.065, 1.085, 6.0)
    # float32 coordinates are compared with the double band: float32(-0.065) = -0.06499999... is kept, float32(1.085) = 1.08500004
    # is above max_height and rejected (as in the C++, where *iter_z is a float)
    pts = P((1, 0, -0.065), (0, 1, 1.0849999), (1, 1, -0.0651), (0, -1, 1.0851), (1, -1, 1.085))
    r, w = laserscan(pts, p)
    assert np.isfinite(r).sum() == 2
    assert set(w[w >= 0]) == {0, 1}


def test_range_limits_and_nearest_wins():
    p = gouda_params(-1, 1, 6.0)
    pts = P((7.0, 0, 0), (3.0, 0, 0), (2.0, 0.001, 0))
    r, w = laserscan(pts, p)
    assert math.isclose(r[180], np.hypot(2.0, 0.001), rel_tol=1e-6) and w[180] == 2
    p.range_min = 2.5
    r, w = laserscan(pts, p)
    assert math.isclose(r[180], 3.0, rel_tol=1e-6) and w[180] == 1


def test_angle_edges_and_nan():
    p = gouda_params(-1, 1, 6.0)
    pts = P((-1.0, 1e-5, 0.0), (-1.0, -1e-6, 0.0), (np.nan, 0, 0), (-1.0, 0.0, 0.0))
    r, w = laserscan(pts, p)
    # just below +pi -> the last bin; just above -pi -> bin 0; NaN skipped; exactly +pi -> index 360 (past the end upstream): dropped
    assert w[359] == 0 and w[0] == 1 and np.isfinite(r).sum() == 2


def test_use_inf_false_fills_range_max_plus_epsilon():
    p = gouda_params(-1, 1, 6.0)
    p.use_inf = False
    r, _ = laserscan(P((1, 0, 0)), p)
    assert math.isclose(r[0], 7.0) and math.isclose(r[180], 1.0, rel_tol=1e-6)


def test_default_min_height_rejects_ground_below_zero():
    # the package default min_height is the smallest positive double, not -inf
    r, _ = laserscan(P((1, 0, -0.01), (0, 1, 0.01)), P2LParams())
    assert np.isfinite(r).sum() == 1
