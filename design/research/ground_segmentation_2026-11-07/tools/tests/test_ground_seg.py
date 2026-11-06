"""Smoke tests of the two bindings on a synthetic flat ground with one box (the OSS do the work; this checks the wrapping)."""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import synth  # noqa: E402
from geometry import Transform, rpy, transform_points  # noqa: E402
from ground_seg import Linefit, PatchworkPP, level_frame  # noqa: E402


def cloud():
    sc = synth.Scene('t', 0.165, objects=[synth.Box('box', 5.0, 5.6, -0.3, 0.3, 0.6)])
    T = Transform(rpy(0, 0, 0), np.array([0.0, 0.0, 1.015]))
    m = synth.xt32_model(0.0)
    pts, lab, _ = synth.scan(sc, m, T, 0, np.random.default_rng(0))
    return level_frame(transform_points(T, pts), T.t), lab


def check(seg):
    lvl, lab = cloud()
    for _ in range(3):
        g = seg.ground_mask(lvl)
    r = np.hypot(lvl[:, 0], lvl[:, 1])
    ground = (lab == 0) & (r > 5) & (r < 30)
    assert g[ground].mean() > 0.9
    top = (lab == 1) & (lvl[:, 2] > -1.18 + 0.3)
    assert top.sum() > 20 and g[top].mean() < 0.1


def test_patchworkpp_flat_and_box(tmp_path):
    check(PatchworkPP(1.18))


def test_linefit_flat_and_box(tmp_path):
    check(Linefit(1.18, workdir=str(tmp_path)))
