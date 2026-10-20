"""Unit tests of sensor_extrinsics (/config -> GLIM T_lidar_imu) and of the GLIM runner parts changed for intent.md:105
(RQ-I081): the mounting comes from the human's /config; UNKNOWN never raises or blocks, it is replaced by the neutral element
and listed; GLIM's config_sensors.json gets the computed T_lidar_imu instead of the template's (another sensor's) value;
stop(None) waits without an invented limit (PRM-37 unresolved) and records the save time."""
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gouda_core import sensor_extrinsics as se  # noqa: E402
from gouda_core import glim_runner as gr  # noqa: E402
from gouda_core.monitor_core import SensorConfig, CONFIG_FIELDS  # noqa: E402
import test_mapping_core as tm  # noqa: E402

ALL_UNKNOWN = {k: 'UNKNOWN' for k in CONFIG_FIELDS}


def apply(T, p):
    """Apply a TUM [x,y,z,qx,qy,qz,qw] transform to a point."""
    x, y, z, qx, qy, qz, qw = T
    r = ((1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)),
         (2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)),
         (2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)))
    return tuple(sum(r[i][k] * p[k] for k in range(3)) + (x, y, z)[i] for i in range(3))


class ExtrinsicsTests(unittest.TestCase):
    def test_all_unknown_is_neutral_and_listed(self):
        r = se.t_lidar_imu(ALL_UNKNOWN)
        self.assertEqual(r['T_lidar_imu'], [0, 0, 0, 0, 0, 0, 1]); self.assertFalse(r['complete'])
        self.assertEqual(len(r['defaulted_fields']), len([k for k in CONFIG_FIELDS if k.startswith(('lidar_', 'imu_'))])); self.assertEqual(r['problems'], [])   # T_lidar_imu uses the LiDAR and IMU fields (the GNSS antenna fields of REV-061 are not part of it)

    def test_axis_mapping_parse(self):
        self.assertEqual(se.parse_axis_mapping('+x forward, +y left, +z up'), se.IDENTITY)
        a = se.parse_axis_mapping('+x right, +y forward, +z up')        # a sensor rotated -90 deg about z... columns = sensor axes
        self.assertEqual([tuple(a[r][0] for r in range(3)), tuple(a[r][1] for r in range(3))], [(0, -1, 0), (1, 0, 0)])
        self.assertEqual(se.determinant(a), 1)
        self.assertEqual(se.parse_axis_mapping('x 前方、y 左方、z 上方'), se.IDENTITY)
        for bad in ('+x forward, +y left', '+x forward, +x left, +z up', '+x forward, +y forward, +z up', 'x sideways, y left, z up', 'hello'):
            self.assertIsNotNone(se.validate_axis_mapping(bad), bad)

    def test_left_handed_mapping_is_reported_not_raised(self):
        v = dict(ALL_UNKNOWN, lidar_axis_mapping='-y forward, +x right, +z up')   # the wording of intent.md:100 is left-handed
        self.assertLess(se.determinant(se.parse_axis_mapping(v['lidar_axis_mapping'])), 0)
        r = se.t_lidar_imu(v)
        self.assertIn('lidar_axis_mapping', r['defaulted_fields']); self.assertTrue(any('left-handed' in p for p in r['problems']))

    def test_transform_maps_imu_points_into_lidar_frame(self):
        v = dict(lidar_mount_x_m=0.2, lidar_mount_y_m=0, lidar_mount_z_m=1.6, lidar_mount_roll_rad=0, lidar_mount_pitch_rad=0, lidar_mount_yaw_rad=0,
                 lidar_axis_mapping='+x right, +y forward, +z up',
                 imu_mount_x_m=0.2, imu_mount_y_m=0, imu_mount_z_m=1.5, imu_mount_roll_rad=0, imu_mount_pitch_rad=0, imu_mount_yaw_rad=0.3,
                 imu_axis_mapping='+x forward, +y left, +z up')
        r = se.t_lidar_imu(v); self.assertTrue(r['complete'])
        T = r['T_lidar_imu']; self.assertAlmostEqual(sum(c * c for c in T[3:]), 1, places=8)   # components are rounded to 1e-9
        # the IMU origin is 0.1 m below the LiDAR origin: in LiDAR axes that is z = -0.1
        p = apply(T, (0, 0, 0)); self.assertAlmostEqual(p[0], 0, places=6); self.assertAlmostEqual(p[1], 0, places=6); self.assertAlmostEqual(p[2], -0.1, places=6)
        # a point 1 m along the IMU x axis (yawed 0.3 rad from base forward) seen in the LiDAR frame (+y = base forward, +x = base right)
        p = apply(T, (1, 0, 0)); self.assertAlmostEqual(p[1], math.cos(0.3), places=6); self.assertAlmostEqual(p[0], -math.sin(0.3), places=6)

    def test_monitor_refuses_bad_axis_text_and_warns_left_handed(self):
        with tempfile.TemporaryDirectory() as d:
            c = SensorConfig(Path(d) / 'c.json')
            ok, msg = c.update({'imu_axis_mapping': 'up up up'}, 1); self.assertFalse(ok); self.assertEqual(c.config_revision, 0)
            ok, msg = c.update({'imu_axis_mapping': '+x forward, +y left, +z up'}, 2); self.assertTrue(ok); self.assertNotIn('WARNING', msg)
            ok, msg = c.update({'lidar_axis_mapping': '-y forward, +x right, +z up'}, 3); self.assertTrue(ok); self.assertIn('left-handed', msg)


class GlimRunnerChangeTests(unittest.TestCase):
    def test_config_sensors_gets_t_lidar_imu(self):
        with tempfile.TemporaryDirectory() as d:
            tpl = Path(d) / 'tpl'; tm.make_template(tpl)
            (tpl / 'config_sensors.json').write_text('{\n  // comment\n  "sensors": {"T_lidar_imu": [0.006, -0.012, 0.008, 0, 0, 0, 1], "imu_acc_noise": 0.05}\n}\n')
            r = gr.build_runtime_config(tm.settings(tpl), Path(d) / 'cfg', [0, 0, -0.1, 0, 0, 0, 1])
            sens = json.loads((Path(d) / 'cfg' / 'config_sensors.json').read_text())
            self.assertEqual(sens['sensors']['T_lidar_imu'], [0, 0, -0.1, 0, 0, 0, 1]); self.assertEqual(sens['sensors']['imu_acc_noise'], 0.05)
            self.assertEqual(r['T_lidar_imu'], [0, 0, -0.1, 0, 0, 0, 1])

    def test_stop_without_limit_records_save_time(self):
        with tempfile.TemporaryDirectory() as d:
            tpl = Path(d) / 'tpl'; tm.make_template(tpl)
            t = [100]
            runner = gr.GlimRunner(tm.settings(tpl), clock=lambda: t[0], popen=tm.FakeProc)
            runner.start(Path(d) / 'work', Path(d) / 'dump', Path(d) / 'glim.log')
            tm.FakeProc.last._alive = False
            (Path(d) / 'dump').mkdir(); (Path(d) / 'dump' / 'graph.txt').write_text('g'); (Path(d) / 'dump' / 'values.bin').write_bytes(b'v')
            run = runner.stop(wait_s=None)
            self.assertTrue(run.dump_ok); self.assertEqual(run.save_duration_s, 0); self.assertNotIn('SIGTERM', run.note)


class StaticTransformTests(unittest.TestCase):
    """ND-13 (REV-061, DEC-122): one list of static transforms; UNKNOWN fields are neutral and listed, never a stop."""

    def test_all_unknown_gives_neutral_transforms(self):
        r = se.static_transforms({}, 0.165)
        frames = [(t['parent'], t['child']) for t in r['transforms']]
        self.assertEqual(frames, [('base_link', 'base_footprint'), ('base_link', 'xt32_link'), ('base_link', 'imu_link'),
                                  ('base_link', 'gnss_link'), ('base_link', 'gnss_aux1_link')])
        self.assertEqual(r['transforms'][0]['translation'], (0, 0, -0.165))
        for t in r['transforms'][1:]:
            self.assertEqual(tuple(t['translation']), (0, 0, 0)); self.assertEqual(tuple(t['rotation']), (0, 0, 0, 1))
        self.assertIn('gnss_main_mount_x_m', r['defaulted_fields']); self.assertIn('lidar_axis_mapping', r['defaulted_fields'])

    def test_values_are_used_and_children_are_unique(self):
        v = {'lidar_mount_x_m': 0.3, 'lidar_mount_z_m': 0.8, 'lidar_axis_mapping': '+x left, +y back, +z up',
             'gnss_main_mount_x_m': 0.1, 'gnss_main_mount_y_m': 0.2, 'gnss_main_mount_z_m': 1.0,
             'gnss_aux1_mount_x_m': -0.4, 'gnss_aux1_mount_y_m': 0.2, 'gnss_aux1_mount_z_m': 1.0}
        r = se.static_transforms(v, 0.165)
        by = {t['child']: t for t in r['transforms']}
        self.assertEqual(len(by), len(r['transforms']), 'each child frame has one parent (one TF owner)')
        self.assertEqual(tuple(by['gnss_link']['translation']), (0.1, 0.2, 1.0))
        self.assertEqual(tuple(by['gnss_aux1_link']['translation']), (-0.4, 0.2, 1.0))
        self.assertEqual(tuple(by['xt32_link']['translation']), (0.3, 0, 0.8))
        q = by['xt32_link']['rotation']   # sensor x -> base_link left: a +90 degree yaw
        self.assertAlmostEqual(q[2], q[3], places=6); self.assertGreater(abs(q[2]), 0.7)
        self.assertNotIn('gnss_main_mount_x_m', r['defaulted_fields']); self.assertEqual(r['problems'], [])


if __name__ == '__main__':
    unittest.main()
