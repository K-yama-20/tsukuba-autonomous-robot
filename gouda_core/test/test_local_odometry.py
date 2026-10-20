"""Unit tests of the ND-08 parts without ROS (REV-061, DEC-123, TS-38): the odometry-only GLIM configuration and the relay's
pose composition and body velocity."""
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import odometry_core as oc  # noqa: E402
from gouda_core import glim_runner as gr  # noqa: E402
import test_mapping_core as tm  # noqa: E402


def pose(x, y, yaw):
    return (x, y, 0.0, 0.0, 0.0, math.sin(yaw / 2), math.cos(yaw / 2))


class RelayTests(unittest.TestCase):
    def test_body_twist_forward_and_turn(self):
        tw = oc.body_twist(pose(0, 0, math.pi / 2), 10.0, pose(0, 0.5, math.pi / 2 + 0.1), 10.5)
        self.assertAlmostEqual(tw[0], 1.0); self.assertAlmostEqual(tw[1], 0.0); self.assertAlmostEqual(tw[3], 0.2)

    def test_time_must_advance(self):
        self.assertIsNone(oc.body_twist(pose(0, 0, 0), 1.0, pose(1, 0, 0), 1.0))
        self.assertIsNone(oc.body_twist(pose(0, 0, 0), 2.0, pose(1, 0, 0), 1.0))

    def test_yaw_wraps(self):
        tw = oc.body_twist(pose(0, 0, math.pi - 0.05), 0.0, pose(0, 0, -math.pi + 0.05), 1.0)
        self.assertAlmostEqual(tw[3], 0.1)

    def test_compose(self):
        c = oc.compose(pose(1, 0, math.pi / 2), pose(1, 0, 0))
        self.assertAlmostEqual(c[0], 1.0); self.assertAlmostEqual(c[1], 1.0); self.assertAlmostEqual(oc.yaw(c[3:]), math.pi / 2)


class OdometryOnlyConfigTests(unittest.TestCase):
    def test_runtime_config(self):
        with tempfile.TemporaryDirectory() as d:
            tpl = Path(d) / 'tpl'; tm.make_template(tpl)
            s = gr.GlimSettings(points_topic='p', imu_topic='i', lidar_frame_id='xt32_link', imu_frame_id='imu_link', base_frame_id='base_link',
                                template_dir=tpl, odometry_only=True)
            r = gr.build_runtime_config(s, Path(d) / 'out')
            self.assertEqual((r['enable_local_mapping'], r['enable_global_mapping'], r['publish_imu2lidar']), (False, False, False))
            self.assertEqual((r['map_frame_id'], r['odom_frame_id'], r['base_frame_id']), ('odom', 'odom_glim', 'base_link'))
            self.assertEqual(r['extension_modules'], [gr.TF_EXTENSION])
            m = gr.build_runtime_config(gr.GlimSettings('p', 'i', 'xt32_link', 'imu_link', 'base_link', template_dir=tpl), Path(d) / 'map')
            self.assertEqual(m['extension_modules'], [], 'the mapping GLIM is unchanged (no viewer)')
            self.assertNotEqual(m.get('enable_global_mapping'), False)


if __name__ == '__main__':
    unittest.main()
