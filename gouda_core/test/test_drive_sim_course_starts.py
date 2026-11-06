"""TEST ONLY (planting start poses): the start poses and routes of drive_sim_course_starts.py. No ROS."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import drive_sim_course as dc  # noqa: E402
import drive_sim_course_starts as st  # noqa: E402

st.install(dc)


def test_positions_relative_to_planting():
    c = dc.Course()
    bx, by = c.inside67
    north = by + dc.PLANT_ARM
    for pos, gap in (('P2', 2.0), ('P1', 1.0)):
        x, y, yaw, s, ryaw = st.start_pose(pos, 0)
        assert abs((y - st.FRONT_M) - north - gap) < 1e-6      # the front this far north of the planting's north edge
        assert abs(ryaw + math.pi / 2) < 1e-6                  # route direction south (leg 6)
    x, y, *_ = st.start_pose('PM', 0)
    assert abs(y - (by + dc.PLANT_ARM / 2)) < 1e-6
    x, y, *_ = st.start_pose('PMs', 0)
    assert abs(x - (c.corner67[0] + st.SHIFT_M)) < 1e-6         # shifted towards the inside (east)


def test_every_start_pose_is_free():
    for p in st.poses():
        assert p['feasible'], p


def test_headings_named():
    by = {p['scene']: p for p in st.poses()}
    assert by['pst_PM_+090']['points_at'] == 'planting'
    assert by['pst_PM_-090']['points_at'] == 'outer_wall'
    assert by['pst_P1_+180']['label'] == '逆向き'


def test_route_ahead_to_goal_past_stop_line():
    c = dc.Course()
    for n in st.names():
        sc = dc.scenario(n)
        s0 = st.start_pose(*st.parse(n))[3]
        ss = [c.along(x, y)[0] for x, y in sc.route[1:]]
        assert all(s > s0 for s in ss) and ss == sorted(ss)
        assert abs(ss[-1] - (c.stop_s + st.GOAL_PAST_STOP_M)) < 1e-6
        assert any(math.hypot(x - c.stop_xy[0], y - c.stop_xy[1]) < 1e-6 for x, y in sc.route)
