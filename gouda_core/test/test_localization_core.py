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
         'status_period_s': 0.1, 'stale_timeout_s': 1.0, 'ndt_nvtl_min': 2.3, 'ekf_xy_stddev_max_m': 0.5, 'ekf_pose_no_update_max': 50,
         'points_voxel_min_points': 2}
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

    def test_lagging_odometry_and_frequent_ekf_poses(self):
        # DEC-285 (第121便): EKF poses at 50 Hz stamped at the receive time, odometry at 10 Hz stamped 0.15 s before it arrives.
        # Every EKF pose is newer than all odometry when it arrives; map->odom must still be computed with each odometry.
        T = yaw_pose(2.0, -1.0, 0.3)
        est = lc.MapOdomEstimator(1.0)
        times = []
        for k in range(1, 151):                       # 3 s of receive time in steps of 0.02 s
            now = k * 0.02
            est.on_ekf_pose(now, oc.compose(T, yaw_pose(now, 0, 0)))   # the vehicle moves along x at 1 m/s
            if k % 5 == 0:                            # odometry every 0.1 s, stamped 0.15 s earlier
                stamp = now - 0.15
                if stamp >= 0:
                    est.on_odometry(stamp, yaw_pose(stamp, 0, 0))
                    times.append(est.map_odom_time)
        self.assertIsNotNone(est.map_odom)
        self.assertTrue(close(est.map_odom, T, places=6))
        self.assertTrue(all(t is not None for t in times[1:]))
        self.assertAlmostEqual(times[-1], 2.84, places=6)   # newest EKF pose (every 0.02 s) at or before the newest odometry (2.85)

    def test_ekf_pose_older_than_all_odometry_is_not_extrapolated(self):
        est = lc.MapOdomEstimator(1.0)
        est.on_odometry(1.0, yaw_pose(1.0, 0, 0)); est.on_odometry(1.1, yaw_pose(1.1, 0, 0))
        est.on_ekf_pose(0.5, yaw_pose(0.5, 0, 0))
        self.assertIsNone(est.map_odom)
        est.reset(); self.assertEqual(len(est.ekf), 0); self.assertIsNone(est.map_odom_time)

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
        }
        for reason, change in cases.items():
            inp = normal_inputs(now)
            for k, v in change.items(): setattr(inp, k, v)
            state, why, _ = lc.evaluate(now, inp, s)
            self.assertNotEqual(state, lc.STATE_NORMAL, reason); self.assertEqual(why, reason)
            self.assertIn(why, lc.REASONS)

    def test_an_input_not_yet_received_after_initialization_waits(self):
        # DEC-282 (REV-146): right after the initialization nothing can have arrived yet -> 初期化中, never 推定不能 and never 正常
        # (was: 推定不能 input_stale, which failed every autonomy start on the VM, 第117便)
        inp = normal_inputs(100.0); inp.last_ndt_score = None
        state, why, detail = lc.evaluate(100.0, inp, settings())
        self.assertEqual((state, why), (lc.STATE_INITIALIZING, 'awaiting_inputs')); self.assertIn('ndt_diagnostics', detail)
        self.assertIn(why, lc.REASONS)
        fresh = lc.Inputs(phase='running', localizer_running=True)   # the state just after initialized
        state, why, detail = lc.evaluate(100.0, fresh, settings())
        self.assertEqual((state, why), (lc.STATE_INITIALIZING, 'awaiting_inputs'))
        for name in ('ekf_pose', 'ndt_diagnostics', 'ekf_diagnostics', 'odometry', 'map_odom'): self.assertIn(name, detail)

    def test_map_odom_not_yet_computed_waits(self):
        # DEC-285 (REV-151): every input arrived but map->odom is not computed yet -> 初期化中 (was 推定不能 no_map_odom)
        inp = normal_inputs(100.0); inp.has_map_odom = False
        state, why, detail = lc.evaluate(100.0, inp, settings())
        self.assertEqual((state, why), (lc.STATE_INITIALIZING, 'awaiting_inputs')); self.assertIn('map_odom', detail)
        self.assertNotIn('no_map_odom', lc.REASONS)

    def test_an_input_that_arrived_and_stopped_is_stale(self):
        inp = normal_inputs(100.0); inp.last_odometry = 100.0 - 1.5
        self.assertEqual(lc.evaluate(100.0, inp, settings())[:2], (lc.STATE_UNAVAILABLE, 'input_stale'))

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

    def test_ndt_points_kept_only_with_the_upstream_key(self):
        # DEC-280: autoware_ndt_scan_matcher 1.9.0 adds is_activated only after it keeps the cloud for ndt_align_srv
        name = 'ndt_scan_matcher: scan_matching_status'
        self.assertIsNone(lc.read_ndt_points([('ekf_localizer: ekf', '', {'pose_no_update_count': '0'})]))
        dropped = 'Max distance of sensor points = 7.123 [m] < 10.000 [m]'
        self.assertEqual(lc.read_ndt_points([(name, dropped, {'sensor_points_max_distance': '7.123'})]), (False, dropped))
        self.assertEqual(lc.read_ndt_points([(name, 'Node is not activated.', {'is_activated': 'False'})]), (True, 'Node is not activated.'))
        self.assertEqual(lc.read_ndt_points([(name, dropped, {}), (name, '', {'is_activated': 'True'})]), (True, ''))   # the newest counts
        self.assertIn('no scan status', lc.points_wait_detail(None))
        self.assertIn(dropped, lc.points_wait_detail((False, dropped)))
        self.assertEqual(lc.evaluate(0.0, lc.Inputs(phase='initializing', localizer_running=True, phase_detail=lc.points_wait_detail(None)), settings())[:2],
                         (lc.STATE_INITIALIZING, 'initializing'))   # waiting for a cloud is 初期化中, never 推定不能

    def test_settings_are_required_and_checked(self):
        with self.assertRaises(ValueError): lc.Settings.from_values({})
        with self.assertRaises(ValueError): settings(stale_timeout_s=0.0)
        with self.assertRaises(ValueError): settings(points_near_crop_m=200.0)
        with self.assertRaises(ValueError): settings(twist_vx_variance=-1.0)
        with self.assertRaises(ValueError): settings(points_voxel_min_points=0)


if __name__ == '__main__':
    unittest.main()
