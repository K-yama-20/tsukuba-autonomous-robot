"""Unit tests of map_tab (地図 tab, intent.md:106 / RQ-I082): settings validation and the conversion tracker. TS-33 (software part)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import map_tab as mt  # noqa: E402

GOOD = {'map_resolution_m': '0.1', 'ground_band_max_m': '0.05', 'obstacle_band_min_m': '0.2', 'obstacle_band_max_m': '1.2', 'occupied_min_points': '1',
        'ground_cell_m': '0.5', 'ground_max_slope_deg': '10', 'ground_fill_radius_m': '1'}


class ValidateTests(unittest.TestCase):
    def test_good(self):
        s, e = mt.validate_settings(GOOD)
        self.assertEqual(e, []); self.assertEqual(set(s), set(mt.KEYS)); self.assertIsInstance(s['occupied_min_points'], float)

    def test_errors(self):
        for change, word in [({'map_resolution_m': 'abc'}, '数値'), ({'map_resolution_m': '0'}, '解像度'), ({'occupied_min_points': '1.5'}, '整数'),
                             ({'occupied_min_points': '0'}, '1 以上'), ({'obstacle_band_min_m': '0.01'}, '順'), ({'extra': 1}, 'unknown'),
                             ({'ground_band_max_m': 'nan'}, '有限'), ({'ground_cell_m': '0'}, '格子'), ({'ground_max_slope_deg': '90'}, '傾き'),
                             ({'ground_max_slope_deg': '0'}, '傾き'), ({'ground_fill_radius_m': '-0.1'}, '補う')]:
            s, e = mt.validate_settings(dict(GOOD, **change))
            self.assertIsNone(s, change); self.assertTrue(any(word in x for x in e), (change, e))
        s, e = mt.validate_settings({k: v for k, v in GOOD.items() if k != 'map_resolution_m'})
        self.assertIsNone(s)
        s, e = mt.validate_settings(dict(GOOD, ground_fill_radius_m='0')); self.assertEqual(e, [])   # no filling is allowed

    def test_tab_offers_every_setting_of_the_converter(self):
        from gouda_core import map_convert as mc
        self.assertEqual(mt.KEYS, mc.SETTING_KEYS)


class TrackerTests(unittest.TestCase):
    def test_one_at_a_time_and_result(self):
        t = mt.ConversionTracker()
        self.assertTrue(t.start('o1', {'a': 1}, 10)[0]); self.assertFalse(t.start('o2', {}, 11)[0])
        t.feedback('converting', 0.4); self.assertEqual(t.snapshot()['stage'], 'converting')
        t.finish(True, 'ok', 3, 12); s = t.snapshot(); self.assertEqual((s['state'], s['revision']), ('done', 3))
        self.assertTrue(t.start('o2', {}, 13)[0]); t.finish(False, 'no submap', 9, 14); self.assertEqual((t.state, t.revision), ('failed', None))


if __name__ == '__main__':
    unittest.main()
