"""Unit tests of the waypoint skip (DEC-367, REV-235) without ROS.

Checked: the mark skip_allowed is saved only when set (the hash of an unmarked set is unchanged) and is refused on a stop point
and on the last waypoint; the footprint cost on a waypoint; a marked waypoint is given up only when the distance to it has not
shrunk for the stall time (DEC-483: also while the robot circles around it), Nav2 counted a recovery (over re-sent goals), the
waypoint stayed blocked and ND-07 is 正常; an unmarked point, the point right after a skip and an unresolved setting are never
skipped."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import autonomy_core as ac  # noqa: E402
from gouda_core import waypoints as wp  # noqa: E402

FOOTPRINT = ac.parse_footprint('[[0.55, 0.30], [0.55, -0.30], [-0.24, -0.30], [-0.24, 0.30]]')
# software trial values of PRM-137..140 (design/generated/params/gouda_mode_manager.trial.yaml)
TRIAL = ac.SkipSettings(stall_s=10.0, cost_threshold=99.0, occupied_s=3.0, progress_m=1.0)


def wset(points):
    return wp.WaypointSet('o', 1, 'h' * 64, points, [1.0] * (len(points) - 1))


def grid(blocked_at=None, size=40, res=0.5):
    """A 20 m square grid from (-10, -10); one lethal cell (100) at blocked_at."""
    data = [0] * (size * size)
    if blocked_at is not None:
        i, j = math.floor((blocked_at[0] + 10) / res), math.floor((blocked_at[1] + 10) / res)
        data[j * size + i] = 100
    return ac.MaskGrid(-10.0, -10.0, res, size, size, data)


class MarkTests(unittest.TestCase):
    def test_unmarked_set_keeps_its_hash(self):
        pts = [wp.Waypoint(0, 0), wp.Waypoint(1, 0), wp.Waypoint(2, 0)]
        before = wset(pts).content_hash()
        self.assertNotIn('skip_allowed', wset(pts).to_dict()['waypoints'][1])
        pts[1].skip_allowed = True
        marked = wset(pts)
        self.assertNotEqual(marked.content_hash(), before)
        self.assertTrue(wp.WaypointSet.from_dict(marked.to_dict()).waypoints[1].skip_allowed)
        self.assertEqual(marked.validate(), [])

    def test_stop_and_last_points_cannot_be_marked(self):
        e = wset([wp.Waypoint(0, 0), wp.Waypoint(1, 0, kind='stop', skip_allowed=True), wp.Waypoint(2, 0, skip_allowed=True)]).validate()
        self.assertTrue(any('stop point cannot be skipped' in x for x in e))
        self.assertTrue(any('last waypoint' in x for x in e))

    def test_mark_must_be_boolean(self):
        e = wset([wp.Waypoint(0, 0), wp.Waypoint(1, 0, skip_allowed='yes'), wp.Waypoint(2, 0)]).validate()
        self.assertTrue(any('skip_allowed must be true or false' in x for x in e))


class FootprintCostTests(unittest.TestCase):
    def test_cost_under_the_footprint(self):
        self.assertEqual(ac.footprint_max_cost(grid((5.2, 0.0)), 5.0, 0.0, 0.0, FOOTPRINT), 100)
        self.assertEqual(ac.footprint_max_cost(grid((7.0, 0.0)), 5.0, 0.0, 0.0, FOOTPRINT), 0)   # 2 m ahead: not under it

    def test_footprint_turns_with_the_waypoint_yaw(self):
        g = grid((5.0, 0.5), size=400, res=0.05)   # 0.5 m to the left: outside at yaw 0 (half width 0.30), inside the front when turned left
        self.assertEqual(ac.footprint_max_cost(g, 5.0, 0.0, 0.0, FOOTPRINT), 0)
        self.assertEqual(ac.footprint_max_cost(g, 5.0, 0.0, math.pi / 2, FOOTPRINT), 100)

    def test_off_the_grid_and_unknown(self):
        self.assertIsNone(ac.footprint_max_cost(grid(), 50.0, 50.0, 0.0, FOOTPRINT))
        g = grid(); g.data = [-1] * len(g.data)
        self.assertIsNone(ac.footprint_max_cost(g, 0.0, 0.0, 0.0, FOOTPRINT))   # unknown is not a cost

    def test_parse_footprint(self):
        self.assertEqual(len(FOOTPRINT), 4)
        self.assertIsNone(ac.parse_footprint('not a polygon'))
        self.assertIsNone(ac.parse_footprint('[[0, 0], [1, 1]]'))


class SkipTests(unittest.TestCase):
    MARKS = [False, True, False, False]

    WP = (5.0, 0.0)

    def run_stalled(self, s, target=1, marks=None, normal=True, cost=100, recoveries_after=1, seconds=12.0, start=0.0, wp=WP):
        """The robot stays at (0, 0), 5 m before the blocked target; Nav2 counts recoveries_after recoveries after the first tick."""
        marks = self.MARKS if marks is None else marks
        t, why = start, None
        while t <= start + seconds and why is None:
            why = s.update(t, target, marks, (0.0, 0.0), 0 if t == start else recoveries_after, normal, cost, wp)
            t += 0.5
        return why, t

    def test_marked_blocked_stalled_waypoint_is_skipped(self):
        why, t = self.run_stalled(ac.WaypointSkip(TRIAL))
        self.assertIsNotNone(why)
        self.assertEqual(why['waypoint'], 1)
        self.assertGreaterEqual(why['stalled_s'], TRIAL.stall_s)
        self.assertGreaterEqual(why['occupied_s'], TRIAL.occupied_s)
        self.assertGreaterEqual(why['recoveries'], 1)

    def test_not_before_the_stall_time(self):
        why, _ = self.run_stalled(ac.WaypointSkip(TRIAL), seconds=TRIAL.stall_s - 1)
        self.assertIsNone(why)

    def test_unmarked_point_is_never_skipped(self):
        why, _ = self.run_stalled(ac.WaypointSkip(TRIAL), target=2, seconds=60)
        self.assertIsNone(why)

    def test_last_point_is_never_skipped_even_if_marked(self):
        why, _ = self.run_stalled(ac.WaypointSkip(TRIAL), target=3, marks=[False, False, False, True], seconds=60)
        self.assertIsNone(why)

    def test_needs_a_recovery_a_blocked_waypoint_and_normal_localization(self):
        self.assertIsNone(self.run_stalled(ac.WaypointSkip(TRIAL), recoveries_after=0, seconds=60)[0])
        self.assertIsNone(self.run_stalled(ac.WaypointSkip(TRIAL), cost=50, seconds=60)[0])
        self.assertIsNone(self.run_stalled(ac.WaypointSkip(TRIAL), cost=None, seconds=60)[0])
        self.assertIsNone(self.run_stalled(ac.WaypointSkip(TRIAL), normal=False, seconds=60)[0])

    def test_progress_towards_the_waypoint_restarts_the_stall_clock(self):
        s = ac.WaypointSkip(TRIAL)
        t, why = 0.0, None
        while t <= 30 and why is None:   # 1 m closer every 8 s: never stall_s without progress
            why = s.update(t, 1, self.MARKS, (math.floor(t / 8.0) * 1.0 - 30.0, 0.0), 0 if t == 0 else 1, True, 100, self.WP)
            t += 0.5
        self.assertIsNone(why)

    def test_circling_around_the_waypoint_is_a_stall(self):
        # DEC-483 (第211便): moving 2 m around the blocked waypoint without getting closer still counts as a stall
        s = ac.WaypointSkip(TRIAL)
        t, why = 0.0, None
        while t <= 20 and why is None:
            a = t / 3.0
            why = s.update(t, 1, self.MARKS, (5.0 + 2.0 * math.cos(a), 2.0 * math.sin(a)), 0 if t == 0 else 1, True, 100, self.WP)
            t += 0.5
        self.assertIsNotNone(why)

    def test_recoveries_are_counted_over_re_sent_goals(self):
        # a re-sent goal (DEC-460) starts number_of_recoveries at 0 again: 3 then 0, 1 is still one more recovery
        s = ac.WaypointSkip(TRIAL)
        counts = [3] * 4 + [0] * 4 + [1] * 40
        why = None
        for k, c in enumerate(counts):
            why = s.update(k * 0.5, 1, self.MARKS, (0.0, 0.0), c, True, 100, self.WP)
            if why: break
        self.assertIsNotNone(why)
        self.assertEqual(why['recoveries'], 1)

    def test_no_waypoint_position_skips_nothing(self):
        self.assertIsNone(self.run_stalled(ac.WaypointSkip(TRIAL), seconds=60, wp=None)[0])

    def test_one_skip_in_a_row(self):
        s = ac.WaypointSkip(TRIAL)
        marks = [False, True, True, True, False]
        why, t = self.run_stalled(s, target=1, marks=marks)
        self.assertEqual(why['waypoint'], 1)
        self.assertIsNone(self.run_stalled(s, target=2, marks=marks, seconds=60, start=t)[0])   # right after the skipped one
        why, _ = self.run_stalled(s, target=3, marks=marks, start=t + 61)                       # waypoint 2 was reached
        self.assertEqual(why['waypoint'], 3)

    def test_unresolved_settings_skip_nothing(self):
        for unresolved in (ac.SkipSettings(None, 99.0, 3.0, 1.0), ac.SkipSettings(10.0, None, 3.0, 1.0),
                           ac.SkipSettings(10.0, 99.0, None, 1.0), ac.SkipSettings(10.0, 99.0, 3.0, None)):
            self.assertTrue(unresolved.missing())
            self.assertIsNone(self.run_stalled(ac.WaypointSkip(unresolved), seconds=60)[0])
        self.assertEqual(TRIAL.missing(), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
