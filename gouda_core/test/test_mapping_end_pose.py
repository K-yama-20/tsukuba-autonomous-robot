"""Unit tests of map_convert.mapping_end_pose / mapping_end_pose_of (REV-155, DEC-289) without ROS.

Checked: the end of the mapping trajectory becomes base_link's pose with the IMU mounting of the mapping run's /config
(T_map_base = T_map_imu * inv(T_base_imu), the same transform as the corridor); the heading is base_link's x axis; the real
mapping run of 2026-10-22 03:14 (the vehicle moved during mapping, bin 125) gives the pose that ND-07 estimated independently
after the start (-0.36, -0.20, about -97 deg); a missing trajectory or /config snapshot gives a reason, never a guess."""
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import map_convert as mc  # noqa: E402
from gouda_core import sensor_extrinsics as se  # noqa: E402
from gouda_core.monitor_core import SensorConfig  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
EVIDENCE = REPO / 'design' / 'research' / 'vehicle_pc' / '2026-10-22_mapping_motion'


def row(t, x, y, z, yaw):
    return [t, x, y, z, 0.0, 0.0, math.sin(yaw / 2), math.cos(yaw / 2)]


VEHICLE_MOUNT = {'imu_mount_x_m': -0.07, 'imu_mount_y_m': 0.14, 'imu_mount_z_m': 0.935, 'imu_mount_roll_rad': 0.0, 'imu_mount_pitch_rad': 0.0,
                 'imu_mount_yaw_rad': 0.1745, 'imu_axis_mapping': '+x left, -y forward, +z up'}


class MappingEndPoseTests(unittest.TestCase):
    def test_no_mounting_offset(self):
        traj = np.array([row(1.0, 0.0, 0.0, 0.0, 0.0), row(2.0, 1.5, -2.0, 0.1, 0.7)])
        p = mc.mapping_end_pose(traj, se.IDENTITY, (0.0, 0.0, 0.0))
        self.assertAlmostEqual(p['x'], 1.5); self.assertAlmostEqual(p['y'], -2.0); self.assertAlmostEqual(p['yaw'], 0.7); self.assertEqual(p['time'], 2.0)
        self.assertIsNone(mc.mapping_end_pose(np.zeros((0, 8)), se.IDENTITY, (0, 0, 0)))

    def test_vehicle_mounting(self):
        r_bi, t_bi, defaulted, problems = se.sensor_pose(VEHICLE_MOUNT, 'imu')
        self.assertEqual((defaulted, problems), ([], []))
        imu_yaw = math.radians(2.4)
        p = mc.mapping_end_pose(np.array([row(5.0, -0.25, -0.19, 0.0, imu_yaw)]), r_bi, t_bi)
        # the IMU's axes are turned 100 deg from base_link (axis mapping 90 deg + mount yaw 10 deg): base heading = IMU heading - 100 deg
        self.assertAlmostEqual(math.degrees(p['yaw']), 2.4 - math.degrees(0.1745) - 90.0, places=3)
        # base_link is where the IMU is minus the IMU offset (rotated into the map): the offset's length is kept
        self.assertAlmostEqual(math.hypot(p['x'] + 0.25, p['y'] + 0.19), math.hypot(-0.07, 0.14), places=6)
        # and the same transform as the corridor's base_path
        np.testing.assert_allclose([p['x'], p['y']], mc.base_path(np.array([row(5.0, -0.25, -0.19, 0.0, imu_yaw)]), r_bi, t_bi)[0])

    def test_real_mapping_run_matches_the_independent_estimate(self):
        traj = mc.read_trajectory((EVIDENCE / 'traj_imu.txt').read_text(encoding='utf-8'))
        values = dict(SensorConfig(EVIDENCE / 'sensor_config.json').values)
        r_bi, t_bi, defaulted, _ = se.sensor_pose(values, 'imu')
        self.assertEqual(defaulted, [])
        p = mc.mapping_end_pose(traj, r_bi, t_bi)
        # ND-07 after the human's start (bin 124 / 125): (-0.36, -0.20), yaw about -97 deg; the human's click was (-1.32, -1.43)
        self.assertLess(math.hypot(p['x'] + 0.36, p['y'] + 0.20), 0.2)
        self.assertLess(abs(math.degrees(p['yaw']) + 97.0), 2.0)
        self.assertGreater(math.hypot(p['x'] + 1.316, p['y'] + 1.429), 1.0)

    def test_missing_inputs_give_a_reason(self):
        with tempfile.TemporaryDirectory() as d:
            j = mc.mapping_end_pose_of(Path(d), VEHICLE_MOUNT)
            self.assertFalse(j['ok']); self.assertIn(mc.TRAJECTORY_FILE, j['message'])
            (Path(d) / mc.TRAJECTORY_FILE).write_text('1.0 0 0 0 0 0 0 1\n2.0 1 2 0 0 0 0 1\n', encoding='utf-8')
            j = mc.mapping_end_pose_of(Path(d), None)
            self.assertFalse(j['ok']); self.assertIn('/config', j['message'])
            j = mc.mapping_end_pose_of(Path(d), VEHICLE_MOUNT)
            self.assertTrue(j['ok']); self.assertEqual(j['time'], 2.0); self.assertEqual(j['defaulted_fields'], [])
            json.dumps(j)   # served as JSON by the monitor


if __name__ == '__main__':
    unittest.main()
