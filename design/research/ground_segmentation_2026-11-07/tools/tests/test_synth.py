import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import synth  # noqa: E402
from geometry import Transform, rpy, transform_points  # noqa: E402


def test_flat_ground_hits_at_ground_height():
    sc = synth.Scene('flat', 0.165)
    o = np.array([0.0, 0.0, 1.0])
    d = np.array([[math.cos(math.radians(-30)), 0, math.sin(math.radians(-30))]])
    t, lab = synth.raycast(sc, o, d, 100)
    p = o + t[0] * d[0]
    assert lab[0] == 0 and abs(p[2] + 0.165) < 1e-9


def test_slope_rises_after_its_start():
    sc = synth.Scene('up', 0.165, 2.0, 10.0)
    o = np.array([0.0, 0.0, 1.0])
    d = np.array([[math.cos(math.radians(-10)), 0, math.sin(math.radians(-10))]])
    t, _ = synth.raycast(sc, o, d, 100)
    p = o + t[0] * d[0]
    assert p[0] > 2.0 and abs(p[2] - (-0.165 + (p[0] - 2.0) * math.tan(math.radians(10)))) < 1e-9


def test_objects_are_hit_before_the_ground():
    for ob in (synth.Box('b', 2.0, 2.3, -0.15, 0.15, 0.3), synth.Cylinder('c', 2.15, 0.0, 0.06, 0.8),
               synth.Cone('k', 2.15, 0.0, 0.19, 0.7)):
        sc = synth.Scene('o', 0.165, objects=[ob])
        o = np.array([0.0, 0.0, 0.0])
        t, lab = synth.raycast(sc, o, np.array([[1.0, 0.0, 0.0]]), 100)
        assert lab[0] == 1 and 1.9 < t[0] < 2.2, ob


def test_mid360_directions_inside_the_published_fov():
    m = synth.mid360_model()
    d = m.directions(3, np.random.default_rng(0))
    el = np.degrees(np.arcsin(d[:, 2]))
    assert len(d) == 20000 and el.min() >= -7.0 - 1e-9 and el.max() <= 52.0 + 1e-9
    d2 = m.directions(4, np.random.default_rng(0))
    assert not np.allclose(d[:100], d2[:100])          # the pattern does not repeat from frame to frame


def test_xt32_rings():
    d = synth.xt32_model(0.0).directions(0, np.random.default_rng(0))
    el = np.unique(np.round(np.degrees(np.arcsin(d[:, 2])), 3))
    assert len(d) == 64000 and len(el) == 32 and math.isclose(el.max(), 15.05) and math.isclose(el.min(), -15.95)


def test_positive_pitch_error_raises_the_ground_ahead():
    sc = synth.Scene('flat', 0.165)
    T_nom = Transform(rpy(0, math.radians(50), 0), np.array([0.55, 0.0, 0.5 - 0.165]))
    m = synth.mid360_model(); m.range_sigma = lambda r: np.zeros(np.shape(r)); m.angle_sigma_deg = 0.0
    for err, sign in ((2.0, 1), (-2.0, -1)):
        pts, lab, true_w = synth.scan(sc, m, synth.with_pitch_error(T_nom, err), 0, np.random.default_rng(0))
        pb = transform_points(T_nom, pts)
        ahead = (pb[:, 0] > 2.0) & (np.abs(pb[:, 1]) < 0.5)
        assert ahead.sum() > 50
        assert sign * (np.median(pb[ahead, 2]) + 0.165) > 0.02


def test_no_error_reproduces_the_ground():
    sc = synth.Scene('flat', 0.165)
    T = Transform(rpy(0, math.radians(50), 0), np.array([0.55, 0.0, 0.335]))
    m = synth.mid360_model(); m.range_sigma = lambda r: np.zeros(np.shape(r)); m.angle_sigma_deg = 0.0
    pts, lab, true_w = synth.scan(sc, m, T, 0, np.random.default_rng(0))
    pb = transform_points(T, pts)
    assert np.abs(pb[:, 2] + 0.165).max() < 1e-4 and np.abs(pb - true_w).max() < 1e-4
