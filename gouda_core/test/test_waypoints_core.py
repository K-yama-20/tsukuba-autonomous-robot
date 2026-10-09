"""Unit tests of the stage 5-4 core: waypoint sets (IFD-30), the route database, the speed mask generator (IFD-41,
DEC-045 lower limit on overlap, TS-22 warning, TS-14 band values), raw map_server output and the PNG encoder.
Design tests: TS-14, TS-22, TS-28.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import waypoints as wp  # noqa: E402
from gouda_core import speed_mask as sm  # noqa: E402
from gouda_core import png  # noqa: E402


def geom(): return sm.MapGeometry(resolution=0.5, origin_x=-5.0, origin_y=-5.0, width=40, height=40)


class WaypointSetTests(unittest.TestCase):
    def test_validation_and_hash(self):
        ws = wp.WaypointSet('o1', 1, 'h' * 64, [wp.Waypoint(0, 0), wp.Waypoint(5, 0)], [1.0])
        self.assertEqual(ws.validate(), [])
        h1 = ws.content_hash(); ws.note = 'x'; ws.set_id = 'id'; self.assertEqual(ws.content_hash(), h1)   # name/note independent
        ws.section_limits_mps = [1.5]; self.assertNotEqual(ws.content_hash(), h1)                      # content dependent
        bad = wp.WaypointSet('', 1, '', [wp.Waypoint(0, 0)], [], )
        errs = bad.validate(); self.assertTrue(any('map reference' in e for e in errs)); self.assertTrue(any('two waypoints' in e for e in errs))
        bad2 = wp.WaypointSet('o1', 1, 'h', [wp.Waypoint(0, 0), wp.Waypoint(1, 0)], [0.0]); self.assertTrue(any('positive' in e for e in bad2.validate()))
        rt = wp.WaypointSet.from_dict(ws.to_dict()); self.assertEqual(rt.content_hash(), ws.content_hash())

    def test_route_database_publish_abort_index(self):
        with tempfile.TemporaryDirectory() as d:
            db = wp.RouteDatabase(Path(d) / 'routes')
            ws = wp.WaypointSet('o1', 1, 'h' * 64, [wp.Waypoint(0, 0), wp.Waypoint(5, 0)], [1.0])
            sid, rev, tmp = db.begin(None); self.assertEqual(rev, 1)
            ok, msg, _ = db.publish(sid, rev, tmp, ws, {'mask_pgm': 'speed_mask.pgm'}, [], {}); self.assertFalse(ok); self.assertIn('discarded', msg); self.assertFalse(tmp.exists())
            sid, rev, tmp = db.begin(sid); (tmp / 'speed_mask.pgm').write_bytes(b'P5\n1 1\n255\n\x00')
            ok, msg, man = db.publish(sid, rev, tmp, ws, {'mask_pgm': 'speed_mask.pgm'}, [{'message': 'w'}], {'half_width_m': 1.0})
            self.assertTrue(ok, msg); self.assertEqual(man['revision'], 1); self.assertEqual(man['map']['origin_id'], 'o1'); self.assertEqual(len(man['content_hash']), 64)
            self.assertEqual(db.load(sid, 1).section_limits_mps, [1.0]); self.assertEqual(db.index()['sets'][0]['revisions'][0]['warnings'], 1)
            sid2, rev2, tmp2 = db.begin(sid); self.assertEqual(rev2, 2); self.assertIn('aborted', db.abort(tmp2, 'x')); self.assertFalse(tmp2.exists())


class SpeedMaskTests(unittest.TestCase):
    def test_band_values_and_outside_unlimited(self):
        r = sm.generate([(-4, 0), (4, 0)], [1.0], geom(), half_width_m=0.6, step_mps=0.02)
        self.assertEqual(r.warnings, []); self.assertGreater(r.painted_cells, 0)
        g = geom(); iy = int((0 - g.origin_y) / g.resolution); ix = int((0 - g.origin_x) / g.resolution)
        self.assertEqual(r.grid[iy, ix], 50)                     # 1.0 / 0.02
        self.assertEqual(r.grid[iy + 8, ix], 0)                  # 4 m away: unlimited (DEC-045: outside the band is Nav2 behaviour)

    def test_overlap_takes_lower_limit_and_warns(self):
        # section 0 at 1.0 m/s and section 2 at 0.5 m/s cross at the origin (re-visit); section 1 links them
        r = sm.generate([(-4, 0), (4, 0), (4, 4), (0, -4), (0, 4)], [1.0, 1.0, 0.5, 0.5], geom(), half_width_m=0.6, step_mps=0.02)
        g = geom(); iy = int((0 - g.origin_y) / g.resolution); ix = int((0 - g.origin_x) / g.resolution)
        self.assertEqual(r.grid[iy, ix], 25)                     # lower limit 0.5 / 0.02 adopted
        self.assertTrue(r.warnings); w = r.warnings[0]
        self.assertEqual(w['adopted_mps'], 0.5); self.assertIn('低い方', w['message']); self.assertGreater(r.overlap_cells, 0)
        same = sm.generate([(-4, 0), (4, 0), (4, 4), (0, -4), (0, 4)], [1.0, 1.0, 1.0, 1.0], geom(), 0.6, 0.02)
        self.assertEqual(same.warnings, [])                      # same limit on overlapping sections: no warning (TS-22)

    def test_quantisation_clips_and_reports(self):
        self.assertEqual(sm.quantise(0.001, 0.02), 1); self.assertEqual(sm.quantise(5.0, 0.02), 100); self.assertEqual(sm.quantise(1.0, 0.02), 50)
        r = sm.generate([(0, 0), (2, 0)], [9.0], geom(), 0.6, 0.02); self.assertEqual(r.sections_clipped, [0])
        with self.assertRaises(ValueError): sm.generate([(0, 0), (2, 0)], [1.0], geom(), 0.0, 0.02)
        with self.assertRaises(ValueError): sm.generate([(0, 0), (2, 0)], [1.0], geom(), 0.6, 0.0)

    def test_write_mask_raw_mode_and_geometry_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            g = geom(); r = sm.generate([(-4, 0), (4, 0)], [1.0], g, 0.6, 0.02)
            files = sm.write_mask(r, g, Path(d), 'speed_filter_mask', 'costmap_filter_info')
            y = (Path(d) / files['mask_yaml']).read_text(); self.assertIn('mode: raw', y); self.assertIn('resolution: 0.5', y); self.assertIn('origin: [-5.0, -5.0, 0.0]', y)
            info = (Path(d) / files['filter_info_yaml']).read_text(); self.assertIn('type: 2', info); self.assertIn('multiplier: 0.02', info); self.assertIn('mask_topic: speed_filter_mask', info)
            g2 = sm.MapGeometry.from_map_yaml(Path(d) / files['mask_yaml']); self.assertEqual((g2.width, g2.height, g2.resolution), (40, 40, 0.5))
            pgm = (Path(d) / files['mask_pgm']).read_bytes(); self.assertEqual(max(pgm[pgm.index(b'255\n') + 4:]), 50)


class PngTests(unittest.TestCase):
    def test_pgm_to_png_roundtrip_header(self):
        pgm = b'P5\n# comment\n3 2\n255\n' + bytes([0, 128, 255, 10, 20, 30])
        data, w, h = png.pgm_to_png(pgm); self.assertEqual((w, h), (3, 2)); self.assertTrue(data.startswith(b'\x89PNG')); self.assertIn(b'IHDR', data); self.assertIn(b'IEND', data)
        with self.assertRaises(ValueError): png.encode_gray(2, 2, b'\x00')


if __name__ == '__main__': unittest.main()
