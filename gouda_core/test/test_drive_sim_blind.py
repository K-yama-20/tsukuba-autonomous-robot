"""The scenes and the measure of the marks left behind by small robots (第245便, DEC-493, issue #90). No ROS."""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drive_sim_blind as db  # noqa: E402
import drive_sim_core as ds  # noqa: E402

BAND_LOW, BAND_HIGH = -0.065, 1.085   # as PRM-70 / PRM-71


def band(points):
    return points[(points[:, 2] >= BAND_LOW) & (points[:, 2] <= BAND_HIGH)]


class StopTests(unittest.TestCase):
    def test_an_obstacle_stops_after_its_time(self):
        o = ds.Obstacle(10.0, 1.0, vx=-0.5, stop_after_s=4.0)
        o.update(1.0, 0.0, 0.0)
        self.assertEqual(o.center(3.0), (9.0, 1.0))      # still moving
        self.assertEqual(o.center(5.0), (8.0, 1.0))      # 4 s after it appeared
        self.assertEqual(o.center(60.0), (8.0, 1.0))     # stands there

    def test_without_the_time_it_keeps_moving(self):
        o = ds.Obstacle(10.0, 1.0, vx=-0.5)
        o.update(0.0, 0.0, 0.0)
        self.assertEqual(o.center(60.0), (-20.0, 1.0))


class ScenarioTests(unittest.TestCase):
    def test_every_scene_is_reached_through_the_core(self):
        for name in db.SCENARIOS:
            sc = ds.scenario(name)
            self.assertEqual(sc.name, name)
            self.assertGreaterEqual(len(sc.route), 2)
            self.assertTrue(sc.obstacles)
            self.assertTrue(all(o.name for o in sc.obstacles))

    def test_unknown_names_are_still_refused(self):
        for name in ('blind_nothing', 'blind_pass_h99', 'nothing'):
            with self.assertRaises(ValueError):
                ds.scenario(name)

    def test_the_existing_scenes_are_unchanged(self):
        self.assertEqual(len(ds.scenario('cone_seen').obstacles), 1)
        self.assertNotIn('blind_pass_h30', ds.SCENARIOS)   # the old list (and what iterates it) stays as it was

    def test_the_stopping_robot_ends_inside_the_corner(self):
        sc = ds.scenario('blind_stop_h30')
        o = sc.obstacles[0]
        o.update(0.0, 16.5, 0.9)                           # the vehicle is near: it appears
        x, y = o.center(100.0)
        self.assertAlmostEqual(x, 14.0); self.assertAlmostEqual(y, 0.9)
        corner = sc.route[3]
        self.assertEqual(corner, (15.0, 0.0)); self.assertEqual(sc.route[4], (15.0, 5.0))   # the route turns left there
        self.assertEqual(o.height, 0.3); self.assertEqual(ds.scenario('blind_stop_h50').obstacles[0].height, 0.5)

    def test_the_passing_robot_does_not_stop(self):
        o = ds.scenario('blind_pass_h50').obstacles[0]
        o.update(0.0, 15.5, 0.8)
        self.assertAlmostEqual(o.center(20.0)[0], 5.5)

    def test_the_block_leaves(self):
        block = ds.scenario('blind_wait').obstacles[0]
        block.update(0.0, 7.0, 0.0)
        self.assertTrue(block.exists(19.0)); self.assertFalse(block.exists(21.0))


class SightTests(unittest.TestCase):
    """What the scenes rely on: close to the vehicle a small robot is below the XT-32's beams, and the MID-360 sees it in front."""

    def test_a_small_robot_close_in_front(self):
        o = ds.Obstacle(1.5, 0.0, height=0.3, radius=db.ROBOT_RADIUS_M)
        o.update(0.0, 0.0, 0.0)
        xt = band(ds.cloud((0.0, 0.0, 0.0), [o], 0.0, ds.beams()))
        self.assertEqual(len(xt), 0)
        mid = band(ds.mid360_cloud((0.0, 0.0, 0.0), [o], 0.0, ds.MidMount(), np.random.default_rng(0)))
        self.assertGreater(len(mid), 0)


class StaleMarkTests(unittest.TestCase):
    W, H, RES = 40, 40, 0.1    # a grid of 4 m x 4 m from (0, 0)

    def grid(self, cells):
        g = np.full((self.H, self.W), 0, dtype=np.int8)
        for (col, row), v in cells.items():
            g[row, col] = v
        return g.ravel().tolist()

    def count(self, cells, obstacles, t=0.0, pose=(0.0, 0.0)):
        return db.stale_marks(self.grid(cells), self.W, self.H, self.RES, 0.0, 0.0, obstacles, t, pose)

    def robot(self, x, y, **kw):
        o = ds.Obstacle(x, y, height=0.3, radius=db.ROBOT_RADIUS_M, **kw)
        o.update(0.0, x, y)
        return o

    def test_an_empty_grid(self):
        self.assertEqual(self.count({}, [self.robot(1.0, 1.0)]), {'lethal': 0, 'stale': 0, 'stale_near': 0})

    def test_a_mark_on_the_obstacle_is_not_stale(self):
        c = self.count({(10, 10): 100}, [self.robot(1.0, 1.0)])     # the cell's centre is (1.05, 1.05)
        self.assertEqual(c, {'lethal': 1, 'stale': 0, 'stale_near': 0})

    def test_a_mark_away_from_every_obstacle_is_stale(self):
        c = self.count({(10, 10): 100, (30, 10): 100}, [self.robot(1.0, 1.0)], pose=(3.0, 3.0))   # (3.05, 1.05): 1.8 m from the robot
        self.assertEqual(c, {'lethal': 2, 'stale': 1, 'stale_near': 1})   # and 1.95 m from the vehicle

    def test_far_from_the_vehicle_it_is_not_near(self):
        c = self.count({(30, 10): 100}, [self.robot(1.0, 1.0)], pose=(0.0, 3.9))
        self.assertEqual(c, {'lethal': 1, 'stale': 1, 'stale_near': 0})

    def test_inflated_and_unknown_cells_do_not_count(self):
        c = self.count({(30, 10): 99, (31, 10): -1, (32, 10): 50}, [])
        self.assertEqual(c['lethal'], 0)

    def test_the_mark_of_an_obstacle_that_left_is_stale(self):
        o = self.robot(1.0, 1.0, dwell_s=5.0)
        self.assertEqual(self.count({(10, 10): 100}, [o], t=1.0)['stale'], 0)
        self.assertEqual(self.count({(10, 10): 100}, [o], t=6.0)['stale'], 1)

    def test_the_mark_follows_a_moving_obstacle(self):
        o = self.robot(1.0, 1.0, vx=0.5)
        self.assertEqual(self.count({(10, 10): 100}, [o], t=0.0)['stale'], 0)
        self.assertEqual(self.count({(10, 10): 100}, [o], t=4.0)['stale'], 1)    # it is at (3.0, 1.0): the old cell stayed behind
        self.assertEqual(self.count({(30, 10): 100}, [o], t=4.0)['stale'], 0)


if __name__ == '__main__':
    unittest.main()
