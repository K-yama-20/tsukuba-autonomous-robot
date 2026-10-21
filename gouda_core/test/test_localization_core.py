"""Unit tests of localization_core (ND-07 trial A3, REV-128; TS-41 core part). No ROS.

map->odom from the EKF pose and the interpolated odometry, the estimator state (never NORMAL with a missing, stale or failing
input: IF-010, DEC-200), the initial height from the mapping trajectory, covariances and settings.
"""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import localization_core as lc  # noqa: E402
from gouda_core import odometry_core as oc  # noqa: E402


def yaw_pose(x, y, yaw, z=0.0):
    return (x, y, z, 0.0, 0.0, math.sin(yaw / 2), math.cos(yaw / 2))


def settings(**over):
    v = {'points_near_crop_m': 1.0, 'points_far_crop_m': 100.0, 'points_voxel_leaf_m': 0.5, 'twist_vx_variance': 0.04, 'twist_wz_variance': 0.01,
         'initial_xy_variance': 0.25, 'initial_z_variance': 0.01, 'initial_roll_pitch_variance': 0.01, 'initial_yaw_variance': 0.07,
         'status_period_s': 0.1, 'stale_timeout_s': 1.0, 'ndt_nvtl_min': 2.3, 'ekf_xy_stddev_max_m': 0.5, 'ekf_pose_no_update_max': 50}
    v.update(over)
    return lc.Settings.from_values(v)


def normal_inputs(now):
    return lc.Inputs(phase='running', localizer_running=True, last_ekf_pose=now, last_ndt_score=now, last_ekf_diag=now, last_odometry=now,
                     ndt_nvtl=3.0, ekf_pose_no_update_count=0, ekf_xy_stddev_m=0.1, has_map_odom=True)


def close(a, b, places=9):
    return all(abs(x - y) < 10 ** -places for x, y in zip(a, b))


class MapOdomTests(unittest.TestCase):
    def test_inverse_and_compose(self):
        p = yaw_pose(1.0, 2.0, 0.7, 0.3)
        self.assertTrue(close(oc.compose(p, lc.inverse(p)), oc.IDENTITY))

    def test_map_odom_from_ekf_and_interpolated_odometry(self):
        # the true map->odom; odometry at 10 Hz; EKF poses between odometry times
        T = yaw_pose(5.0, -3.0, 0.4)
        est = lc.MapOdomEstimator(1.0)
        odom = {t / 10: yaw_pose(t * 0.1, t * 0.02, t * 0.01) for t in range(10)}
        for t, p in odom.items(): est.on_odometry(t, p)
        t = 0.45
        ob = lc.interpolate(odom[0.4], 0.4, odom[0.5], 0.5, t)
        est.on_ekf_pose(t, oc.compose(T, ob))
        self.assertTrue(close(est.map_odom, T, places=6))
        self.assertEqual(est.map_odom_time, t)

    def test_ekf_pose_newer_than_odometry_waits(self):
        T = yaw_pose(1.0, 1.0, 0.2)
        est = lc.MapOdomEstimator(1.0)
        est.on_odometry(0.0, yaw_pose(0, 0, 0)); est.on_odometry(0.1, yaw_pose(0.1, 0, 0))
        later = yaw_pose(0.15, 0, 0)
        est.on_ekf_pose(0.15, oc.compose(T, later))
        self.assertIsNone(est.map_odom)                      # no extrapolation
        est.on_odometry(0.2, yaw_pose(0.2, 0, 0))
        self.assertTrue(close(est.map_odom, T, places=6))

    def test_buffer_keeps_only_the_span_and_increasing_times(self):
        b = lc.OdomBuffer(1.0)
        for i in range(30): b.add(i / 10, yaw_pose(i, 0, 0))
        self.assertGreaterEqual(b.items[0][0], 2.9 - 1.0 - 1e-9)
        b.add(1.0, yaw_pose(0, 0, 0)); self.assertAlmostEqual(b.newest, 2.9)
        self.assertIsNone(b.at(0.5)); self.assertIsNone(b.at(3.5))


class StateTests(unittest.TestCase):
    def test_normal_only_when_everything_passes(self):
        s = settings(); now = 100.0
        self.assertEqual(lc.evaluate(now, normal_inputs(now), s)[0], lc.STATE_NORMAL)

    def test_each_failure_is_named_and_not_normal(self):
        s = settings(); now = 100.0
        cases = {
            'not_configured': dict(phase='unconfigured'),
            'not_initialized': dict(phase='waiting'),
            'init_failed': dict(phase='failed'),
            'localizer_exited': dict(localizer_running=False),
            'initializing': dict(phase='initializing'),
            'input_stale': dict(last_ekf_pose=now - 1.5),
            'ndt_diagnostics_missing': dict(ndt_nvtl=None),
            'ndt_score_low': dict(ndt_nvtl=2.0),
            'ekf_diagnostics_missing': dict(ekf_pose_no_update_count=None),
            'ekf_pose_not_updated': dict(ekf_pose_no_update_count=51),
            'ekf_covariance_large': dict(ekf_xy_stddev_m=0.6),
            'no_map_odom': dict(has_map_odom=False),
        }
        for reason, change in cases.items():
            inp = normal_inputs(now)
            for k, v in change.items(): setattr(inp, k, v)
            state, why, _ = lc.evaluate(now, inp, s)
            self.assertNotEqual(state, lc.STATE_NORMAL, reason); self.assertEqual(why, reason)
            self.assertIn(why, lc.REASONS)

    def test_an_input_never_received_is_stale(self):
        inp = normal_inputs(100.0); inp.last_ndt_score = None
        state, why, detail = lc.evaluate(100.0, inp, settings())
        self.assertEqual((state, why), (lc.STATE_UNAVAILABLE, 'input_stale')); self.assertIn('ndt_diagnostics', detail)

    def test_limits_are_inclusive_where_the_design_says_above(self):
        s = settings(); now = 100.0
        inp = normal_inputs(now); inp.ekf_pose_no_update_count = 50; inp.ndt_nvtl = 2.3; inp.ekf_xy_stddev_m = 0.5; inp.last_odometry = now - 1.0
        self.assertEqual(lc.evaluate(now, inp, s)[0], lc.STATE_NORMAL)


class InitAndCovarianceTests(unittest.TestCase):
    def test_initial_height_from_nearest_trajectory_point(self):
        traj = lc.read_tum('# t x y z qx qy qz qw\n1 0 0 1.0 0 0 0 1\n2 10 0 2.0 0 0 0 1\nbad line\n')
        self.assertEqual(len(traj), 2)
        z, d = lc.initial_height(traj, 9.0, 1.0, 0.3)
        self.assertAlmostEqual(z, 1.7); self.assertAlmostEqual(d, math.hypot(1, 1))
        self.assertIsNone(lc.initial_height([], 0, 0, 0))

    def test_covariances(self):
        s = settings()
        tc = lc.twist_covariance(s); self.assertEqual((tc[0], tc[35]), (0.04, 0.01)); self.assertEqual(sum(tc), 0.05)
        ic = lc.initial_pose_covariance(s)
        self.assertEqual([ic[i] for i in (0, 7, 14, 21, 28, 35)], [0.25, 0.25, 0.01, 0.01, 0.01, 0.07])
        cov = [0.0] * 36; cov[0], cov[7], cov[1], cov[6] = 0.04, 0.01, 0.0, 0.0
        self.assertAlmostEqual(lc.xy_stddev(cov), 0.2)
        cov[0] = cov[7] = 0.05; cov[1] = cov[6] = 0.04
        self.assertAlmostEqual(lc.xy_stddev(cov), 0.3)        # eigenvalues 0.09 and 0.01

    def test_diagnostics_are_read_by_key(self):
        d = lc.read_diagnostics([('ndt_scan_matcher: scan_matching_status', {'nearest_voxel_transformation_likelihood': '2.71', 'x': 'y'}),
                                 ('ekf_localizer: ekf', {'pose_no_update_count': '3'}), ('other', {'pose_no_update_count': 'n/a'})])
        self.assertEqual(d, {'nearest_voxel_transformation_likelihood': 2.71, 'pose_no_update_count': 3})

    def test_settings_are_required_and_checked(self):
        with self.assertRaises(ValueError): lc.Settings.from_values({})
        with self.assertRaises(ValueError): settings(stale_timeout_s=0.0)
        with self.assertRaises(ValueError): settings(points_near_crop_m=200.0)
        with self.assertRaises(ValueError): settings(twist_vx_variance=-1.0)


if __name__ == '__main__':
    unittest.main()
