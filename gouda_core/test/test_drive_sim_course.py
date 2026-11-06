"""TEST ONLY (第238便): the geometry of the confirmation-run course scenario (drive_sim_course.py). No ROS."""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import drive_sim_course as dc  # noqa: E402


def _course():
    return dc.Course()


def test_length_400():
    assert abs(_course().length - 400.0) <= 1.0


def test_widths_labelled_and_assumed():
    c = _course()
    w = dict(zip(c.tags, c.widths))
    assert c.widths[0] == 3.0                     # start corridor, labelled
    assert w['chicane_neck'] == 1.5               # labelled
    assert w['cone_field'] == 4.0                 # assumed
    # the boundaries really are that far apart in the middle of each segment
    for i, (a, b) in enumerate(zip(c.centre[:-1], c.centre[1:])):
        m = (a + b) / 2
        dl = min(dc.Wall(p, q).distance(0, np.array([m[0]]), np.array([m[1]]))[0] + 0.05 for p, q in c.walls)
        if c.tags[i] == 'leg6':
            continue                              # east side is pillars
        assert abs(dl - c.widths[i] / 2) < 0.05, (c.tags[i], dl)


def test_cone_spacing():
    for lay in ('A', 'B'):
        cs = _course().cones(lay)
        assert len(cs) == 9
        for i, p in enumerate(cs):
            nn = min(math.hypot(p[0] - q[0], p[1] - q[1]) for j, q in enumerate(cs) if j != i)
            assert 1.5 <= nn <= 2.0, (lay, i, nn)


def test_cones_inside_field_and_off_walls():
    c = _course()
    x0, y0 = c.centre[-2]
    for lay in ('A', 'B'):
        for x, y in c.cones(lay):
            assert x0 < x < c.goal_xy[0]
            assert abs(y - y0) + dc.CONE_HALF < 2.0   # inside the 4 m section, not touching a wall
            d = min(dc.Wall(a, b).distance(0, np.array([x]), np.array([y]))[0] for a, b in c.walls)
            assert d > dc.CONE_HALF


def test_no_straight_line_through_cones():
    """Every lateral line along the cone field (a path parallel to the centreline, 0.6 m wide) meets a cone or a wall."""
    c = _course()
    y0 = c.centre[-2][1]
    for lay in ('A', 'B'):
        cs = c.cones(lay)
        for off in np.arange(-1.7, 1.71, 0.05):
            lo, hi = y0 + off - 0.3, y0 + off + 0.3
            blocked = any(y + dc.CONE_HALF >= lo - 1e-9 and y - dc.CONE_HALF <= hi + 1e-9 for _, y in cs)   # touching counts
            assert blocked, (lay, off)


def test_stop_line_and_waypoints():
    c = _course()
    assert abs(c.stop_s - (c.cum[c.tags.index('leg6') + 1] + dc.STOP_AFTER_CORNER_M)) < 1e-9
    wps = c.waypoints()
    assert any(math.hypot(x - c.stop_xy[0], y - c.stop_xy[1]) < 1e-6 for x, y in wps)
    assert wps[0] == (0.0, 0.0)
    gaps = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(wps, wps[1:])]
    assert max(gaps) <= dc.WP_STEP_M + 1e-6 and min(gaps) > 0.3


def test_pillars_and_planting():
    c = _course()
    assert len(c.pillars) == dc.PILLARS
    bx, by = c.inside67
    assert all(abs(x - (bx + dc.PILLAR_R)) < 1e-9 for x, _ in c.pillars)
    assert min(y for _, y in c.pillars) > by + dc.PLANT_ARM


def test_cloud_sees_walls():
    import drive_sim_core as ds
    c = _course()
    obs = dc.obstacles(c, 'A')
    pts = dc.cloud((-10.0, 0.0, math.pi), obs, 0.0, ds.beams())
    assert len(pts) > 1000
