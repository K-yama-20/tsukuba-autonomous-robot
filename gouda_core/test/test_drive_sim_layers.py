"""Unit tests of drive_sim_layers (TEST ONLY, MID-360 plan stage 2)."""
import copy
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drive_sim_layers as dl  # noqa: E402


def params():
    xt = {'plugin': 'nav2_costmap_2d::ObstacleLayer', 'enabled': True, 'observation_sources': 'scan', 'min_obstacle_height': -1e9,
          'max_obstacle_height': 1e9, 'scan': {'topic': '/sensors/xt32/scan', 'obstacle_max_range': 2.5, 'raytrace_max_range': 3.0}}
    lc = {'plugins': ['obstacle_layer', 'inflation_layer'], 'obstacle_layer': copy.deepcopy(xt)}
    gxt = copy.deepcopy(xt); gxt['combination_method'] = 2
    gc = {'plugins': ['static_layer', 'obstacle_layer', 'keepout_layer', 'inflation_layer'], 'obstacle_layer': gxt}
    return {'local_costmap': {'local_costmap': {'ros__parameters': lc}}, 'global_costmap': {'global_costmap': {'ros__parameters': gc}}}


class LayerTests(unittest.TestCase):
    def test_s0_changes_nothing(self):
        p = params(); dl.apply(p, 'S0'); self.assertEqual(p, params())

    def test_s1_adds_the_mid360_to_the_xt32_layer(self):
        p = params(); dl.apply(p, 'S1')
        for n in ('local_costmap', 'global_costmap'):
            c = p[n][n]['ros__parameters']
            self.assertEqual(c['obstacle_layer']['observation_sources'], 'scan mid_mark mid_clear')
            self.assertNotIn(dl.LAYER, c['plugins'])

    def test_s2_adds_its_own_layer_after_the_xt32_layer(self):
        p = params(); dl.apply(p, 'S2')
        lc = p['local_costmap']['local_costmap']['ros__parameters']; gc = p['global_costmap']['global_costmap']['ros__parameters']
        self.assertEqual(lc['plugins'], ['obstacle_layer', dl.LAYER, 'inflation_layer'])
        self.assertEqual(gc['plugins'][:3], ['static_layer', 'obstacle_layer', dl.LAYER])
        self.assertEqual(lc['obstacle_layer']['observation_sources'], 'scan')   # the XT-32 layer is untouched
        self.assertEqual(gc[dl.LAYER]['combination_method'], 2)
        m, c = lc[dl.LAYER]['mid_mark'], lc[dl.LAYER]['mid_clear']
        self.assertEqual((m['marking'], m['clearing'], c['marking'], c['clearing']), (True, False, False, True))
        self.assertEqual(c['sensor_frame'], dl.MID_FRAME)
        self.assertEqual((m['obstacle_max_range'], c['raytrace_max_range']), (2.5, 3.0))

    def test_unknown_variant(self):
        with self.assertRaises(ValueError):
            dl.apply(params(), 'S9')

    def test_patch_copy_only_on_a_copy(self):
        here = os.path.dirname(os.path.abspath(__file__))
        with self.assertRaises(SystemExit):
            dl.patch_copy(os.path.join(here, '..', 'gouda_core', 'nav2_config.py'))
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, 'nav2_config.py')
            open(f, 'w').write('def write():\n' + dl.ANCHOR + '    return 1\n')
            self.assertTrue(dl.patch_copy(f)); self.assertFalse(dl.patch_copy(f))
            self.assertIn('GOUDA_TEST_LAYERS', open(f).read())


if __name__ == '__main__':
    unittest.main()
