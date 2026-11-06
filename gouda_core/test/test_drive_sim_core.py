"""The core of the driving simulator (第179便): the plant, the synthetic cloud and the metrics. No ROS."""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drive_sim_core as ds  # noqa: E402

BAND_LOW, BAND_HIGH = -0.065, 1.085   # as PRM-70 / PRM-71


def band(points):
    return points[(points[:, 2] >= BAND_LOW) & (points[:, 2] <= BAND_HIGH)]


class PlantTests(unittest.TestCase):
    def test_delay_and_lag(self):
        p = ds.Plant(delay_s=0.2, tau_v_s=0.2, tau_w_s=0.2)
        t = 0.0
        while t < 0.19:
            p.step(t, 0.01, 1.0, 0.0); t += 0.01
        self.assertEqual(p.v, 0.0)            # nothing before the delay
        while t < 2.0:
            p.step(t, 0.01, 1.0, 0.0); t += 0.01
        self.assertAlmostEqual(p.v, 1.0, 2)
        self.assertGreater(p.x, 1.0); self.assertAlmostEqual(p.y, 0.0)

    def test_limits_and_turn(self):
        p = ds.Plant(delay_s=0.0, tau_v_s=0.01, tau_w_s=0.01, max_v=1.0, max_w=0.5)
        for i in range(500):
            p.step(i * 0.01, 0.01, 5.0, 5.0)
        self.assertAlmostEqual(p.v, 1.0); self.assertAlmostEqual(p.w, 0.5)
        self.assertGreater(p.y, 0.1)


class CloudTests(unittest.TestCase):
    rays = ds.beams()

    def test_free_space_has_nothing_in_the_band(self):
        pts = ds.cloud((0.0, 0.0, 0.0), [], 0.0, self.rays)
        self.assertGreater(len(pts), 1000)
        self.assertEqual(len(band(pts)), 0)    # all ground: every beam of the scan is inf
        self.assertLess(abs(pts[:, 2].max() - ds.GROUND_Z), 1e-3)

    def test_cone_ahead_is_in_the_band_at_its_distance(self):
        o = ds.Obstacle(4.0, 0.0, **ds.CONE); o.update(0.0, 0.0, 0.0)
        pts = band(ds.cloud((0.0, 0.0, 0.0), [o], 0.0, self.rays))
        self.assertGreater(len(pts), 3)
        r = (pts[:, 0] ** 2 + pts[:, 1] ** 2) ** 0.5
        self.assertLess(abs(float(r.min()) - 3.85), 0.05)
        self.assertLess(float(abs(pts[:, 1]).max()), 0.2)

    def test_pose_moves_the_cloud(self):
        o = ds.Obstacle(4.0, 3.0, **ds.CONE); o.update(0.0, 0.0, 0.0)
        pts = band(ds.cloud((4.0, 0.0, math.pi / 2), [o], 0.0, self.rays))   # 3 m straight ahead when facing +y
        self.assertLess(abs(float(pts[:, 0].mean()) - 2.9), 0.2)
        self.assertLess(float(abs(pts[:, 1]).max()), 0.2)

    def test_a_near_cone_is_under_the_lowest_channel(self):
        o = ds.Obstacle(1.5, 0.0, **ds.CONE); o.update(0.0, 0.0, 0.0)
        self.assertEqual(len(band(ds.cloud((0.0, 0.0, 0.0), [o], 0.0, self.rays))), 0)

    def test_box_blocks_what_is_behind(self):
        wall = ds.Obstacle(3.0, 0.0, height=1.5, half_x=0.1, half_y=2.0, name='wall'); wall.update(0.0, 0.0, 0.0)
        cone = ds.Obstacle(5.0, 0.0, **ds.CONE); cone.update(0.0, 0.0, 0.0)
        pts = band(ds.cloud((0.0, 0.0, 0.0), [wall, cone], 0.0, self.rays))
        self.assertLess(float(pts[:, 0].max()), 3.0)

    def test_noise_changes_ranges(self):
        o = ds.Obstacle(4.0, 0.0, **ds.CONE); o.update(0.0, 0.0, 0.0)
        a = ds.cloud((0.0, 0.0, 0.0), [o], 0.0, self.rays)
        b = ds.cloud((0.0, 0.0, 0.0), [o], 0.0, self.rays, noise_m=0.02)
        self.assertEqual(a.shape, b.shape); self.assertGreater(float(abs(a - b).max()), 0.0)


def live(o):
    o.update(0.0, 0.0, 0.0)   # an obstacle without a trigger exists from its first update
    return o


class SensorTests(unittest.TestCase):
    """MID-360 plan stage 1: the XT-32 values of lidar_xt32_spec.md and the MID-360 at the front edge pitched down (DEC-424)."""
    def test_xt32_beams_follow_the_spec(self):
        self.assertAlmostEqual(min(ds.ELEVATIONS_DEG), -15.98); self.assertAlmostEqual(max(ds.ELEVATIONS_DEG), 15.05)
        self.assertEqual(len(ds.ELEVATIONS_DEG), 32)
        self.assertAlmostEqual(ds.LIDAR_Z - ds.GROUND_Z, 1.182)

    def test_xt32_ground_starts_where_the_spec_says(self):
        pts = ds.cloud((0.0, 0.0, 0.0), [], 0.0, ds.beams())
        near = min(math.hypot(x, y) for x, y, z in pts)
        self.assertAlmostEqual(near, 1.182 / math.tan(math.radians(15.98)), delta=0.05)   # 4.13 m in the spec

    def test_mid360_rays_cover_its_field_of_view_after_the_tilt(self):
        import numpy as np
        dx, dy, dz = ds.mid360_rays(ds.MidMount(), np.random.default_rng(1), 50000)
        el = np.degrees(np.arcsin(dz)); front, rear = dx > 0.9, dx < -0.9 * math.cos(math.radians(50))
        self.assertAlmostEqual(el.min(), -57.0, delta=0.5)          # 50 deg down + 7 deg below the sensor's plane
        self.assertGreater(el[front].min(), -57.5)
        self.assertGreater(el[(dx < 0) & (abs(dy) < 0.05)].min(), 40.0)   # straight back only looks up

    def test_mid360_sees_a_low_box_the_xt32_misses(self):
        import numpy as np
        box = live(ds.Obstacle(1.8, 0.0, height=0.3, half_x=0.1, half_y=0.3))   # 1.25 m ahead of the front edge
        in_band = lambda p: [q for q in p if ds.GROUND_Z + 0.10 <= q[2] <= ds.GROUND_Z + 1.25]
        self.assertEqual(len(in_band(ds.cloud((0.0, 0.0, 0.0), [box], 0.0, ds.beams()))), 0)
        mid = in_band(ds.mid360_cloud((0.0, 0.0, 0.0), [box], 0.0, ds.MidMount(height_m=0.5), np.random.default_rng(2)))
        self.assertGreater(len(mid), 20)
        self.assertTrue(all(1.6 <= q[0] <= 1.95 for q in mid))

    def test_mid360_ground_and_minimum_range(self):
        import numpy as np
        m = ds.MidMount(height_m=0.5)
        pts = ds.mid360_cloud((0.0, 0.0, 0.0), [], 0.0, m, np.random.default_rng(3))
        ox, oy, oz = m.origin()
        ahead = [x - ox for x, y, z in pts if abs(y) < 0.05 and x > ox]
        self.assertAlmostEqual(min(ahead), 0.5 / math.tan(math.radians(57)), delta=0.05)   # the ground ahead starts at 0.65 h
        self.assertTrue(all(math.dist((x, y, z), (ox, oy, oz)) >= ds.MID360_MIN_RANGE_M for x, y, z in pts))

    def test_sensor_origin_moves_the_hits(self):
        cone = live(ds.Obstacle(3.0, 0.0, radius=0.15, height=0.7))
        o = (0.55, 0.0, ds.GROUND_Z + 0.5)
        import numpy as np
        pts = ds.cloud((0.0, 0.0, 0.0), [cone], 0.0, (np.array([1.0]), np.array([0.0]), np.array([0.0])), origin=o)
        self.assertAlmostEqual(float(pts[0][0]), 2.85, places=3)   # the cone's face, not shifted by the sensor's offset
        pts = ds.cloud((2.0, 1.0, math.pi / 2), [live(ds.Obstacle(2.0, 4.0, radius=0.15, height=0.7))], 0.0,
                       (np.array([1.0]), np.array([0.0]), np.array([0.0])), origin=o)
        self.assertAlmostEqual(float(pts[0][0]), 2.85 - 0.55 + 0.55, places=3)   # facing +y: the cone is 3 m ahead of base_link


class ObstacleTests(unittest.TestCase):
    def test_trigger_dwell_and_motion(self):
        o = ds.Obstacle(10.0, 0.0, trigger_m=3.0, dwell_s=8.0, vy=1.0, radius=0.2)
        o.update(0.0, 0.0, 0.0); self.assertFalse(o.exists(0.0))
        o.update(1.0, 8.0, 0.0); self.assertTrue(o.exists(1.0))
        self.assertEqual(o.center(3.0), (10.0, 2.0))
        self.assertFalse(o.exists(9.5))

    def test_every_scenario_builds(self):
        for name in ds.SCENARIOS:
            s = ds.scenario(name)
            self.assertGreaterEqual(len(s.route), 2)
        with self.assertRaises(ValueError):
            ds.scenario('nope')

    def test_the_30_patterns_build(self):
        self.assertEqual(len(ds.SIM30), 30)
        for k in ds.SIM30:
            sc = ds.scenario(k)
            self.assertEqual(sc.route[-1], (25.0, 0.0)); self.assertTrue(sc.obstacles)

    def test_random_cones_follow_the_seed(self):
        a, b, c = ds.scenario('cones_random', 1), ds.scenario('cones_random', 1), ds.scenario('cones_random', 2)
        self.assertEqual([o.y for o in a.obstacles], [o.y for o in b.obstacles])
        self.assertNotEqual([o.y for o in a.obstacles], [o.y for o in c.obstacles])


def drive(sc, path, dt=0.02, cmd=(1.0, 0.0)):
    """Feed the scorer from a list of (x, y, yaw, v, w) states."""
    sco = ds.Scorer(sc)
    for i, (x, y, yaw, v, w) in enumerate(path):
        p = ds.Plant(x=x, y=y, yaw=yaw, v=v, w=w)
        t = i * dt
        for o in sc.obstacles:
            o.update(t, x, y)
        sco.add(t, p, cmd[0], w, sc.obstacles)
    return sco.report()


class ScorerTests(unittest.TestCase):
    def straight(self, length=10.0, v=1.0, dt=0.02):
        return [(i * dt * v, 0.0, 0.0, v, 0.0) for i in range(int(length / v / dt) + 1)]

    def test_straight_run_to_the_goal(self):
        sc = ds.Scenario('t', [(0.0, 0.0), (10.0, 0.0)], [])
        r = drive(sc, self.straight())
        self.assertTrue(r['completed']); self.assertEqual(r['contacts'], 0)
        self.assertAlmostEqual(r['avg_speed_mps'], 1.0, 1)
        self.assertEqual(r['stopped_s'], 0.0); self.assertIsNone(r['min_clearance_m'])

    def test_stop_lowers_the_score(self):
        sc = ds.Scenario('t', [(0.0, 0.0), (10.0, 0.0)], [])
        moving = drive(sc, self.straight())
        stop = self.straight(5.0) + [(5.0, 0.0, 0.0, 0.0, 0.0)] * 500 + [(5.0 + i * 0.02, 0.0, 0.0, 1.0, 0.0) for i in range(251)]
        stopped = drive(ds.Scenario('t', [(0.0, 0.0), (10.0, 0.0)], []), stop)
        self.assertAlmostEqual(stopped['longest_stop_s'], 10.0, 0)
        self.assertLess(stopped['score'], moving['score'])

    def test_contact_and_avoid_start(self):
        through = drive(ds.Scenario('t', [(0.0, 0.0), (10.0, 0.0)], [ds.Obstacle(7.0, 0.0, name='c', **ds.CONE)]), self.straight())
        self.assertEqual(through['contacts'], 1); self.assertEqual(through['not_avoided'], ['c'])
        self.assertLess(through['min_clearance_m'], 0)
        path = []
        for i in range(501):                     # x = t; 1 m to the side between x = 5 and x = 9
            x = i * 0.02
            path.append((x, 0.0 if x < 3.5 else (x - 3.5) if x < 4.5 else 1.0 if x < 9.0 else 0.0, 0.0, 1.0, 0.1))
        side = drive(ds.Scenario('t', [(0.0, 0.0), (10.0, 0.0)], [ds.Obstacle(7.0, 0.0, name='c', **ds.CONE)]), path)
        self.assertEqual(side['contacts'], 0)
        self.assertAlmostEqual(side['avoid_start_s']['c'], 1.65, 1)   # seen at x = 2 (5 m), left the route at x = 3.65
        self.assertGreater(side['min_clearance_m'], 0.2)

    def test_swing_is_counted(self):
        sc = ds.Scenario('t', [(0.0, 0.0), (10.0, 0.0)], [])
        path = [(i * 0.02, 0.0, 0.0, 1.0, 0.3 if int(i / 25) % 2 else -0.3) for i in range(501)]
        self.assertGreater(drive(sc, path)['turn_changes_per_min'], 100)

    def test_nothing_before_the_first_command(self):
        sco = ds.Scorer(ds.Scenario('t', [(0.0, 0.0), (10.0, 0.0)], []))
        sco.add(0.0, ds.Plant(), 0.0, 0.0, [])
        self.assertEqual(sco.report()['duration_s'], 0.0)


class SweepTests(unittest.TestCase):
    def test_summary_ranks_by_mean_score_and_counts_a_missing_score_as_zero(self):
        import drive_sim_sweep as sw
        rows = [{'set': 'a', 'score': 100.0, 'completed': True}, {'set': 'a', 'score': None}, {'set': 'b', 'score': 70.0, 'completed': True}]
        self.assertEqual(sw.summary(rows), [('b', 70.0, 1, 1), ('a', 50.0, 2, 1)])
        self.assertIn('| b | 70.0 | 1 | 1 |', sw.markdown(rows))


if __name__ == '__main__':
    unittest.main()
