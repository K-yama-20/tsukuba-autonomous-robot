"""Unit tests of the drawn areas (REV-137, DEC-220..223; TS-47 core part). No ROS.

Polygons -> the KeepoutFilter mask on the speed mask's grid (keepout 100, allowed 0, neither -1, keepout wins), the hash of the
values map_server publishes (DEC-224 (a)), the waypoint warning, and that a waypoint set without areas keeps its earlier hash.
"""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import keepout_mask as km  # noqa: E402
from gouda_core import speed_mask as sm  # noqa: E402
from gouda_core import waypoints as wp  # noqa: E402

GEOM = sm.MapGeometry(resolution=0.5, origin_x=-5.0, origin_y=-5.0, width=20, height=20)   # 10 m x 10 m
SQUARE = lambda x0, y0, x1, y1: [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def cell(x, y):
    return int((y - GEOM.origin_y) // GEOM.resolution), int((x - GEOM.origin_x) // GEOM.resolution)


class KeepoutMaskTests(unittest.TestCase):
    def test_values_and_keepout_wins(self):
        areas = [{'kind': 'allowed', 'polygon': SQUARE(-4, -4, 0, 0)}, {'kind': 'keepout', 'polygon': SQUARE(-1, -1, 2, 2)}]
        g = km.rasterize(areas, GEOM)
        self.assertEqual(g.shape, (20, 20)); self.assertEqual(g.dtype, np.int8)
        self.assertEqual(g[cell(-3, -3)], km.FREE)          # only allowed
        self.assertEqual(g[cell(-0.5, -0.5)], km.OCCUPIED)  # both: keepout wins
        self.assertEqual(g[cell(1.5, 1.5)], km.OCCUPIED)    # only keepout
        self.assertEqual(g[cell(4, 4)], km.UNKNOWN)         # neither
        self.assertEqual(int((g == km.OCCUPIED).sum()), 36)  # 3 m x 3 m at 0.5 m: not widened (DEC-223)

    def test_written_mask_is_what_map_server_reads(self):
        """The trinary pgm read back as map_server does gives the same values; the hash is over those values (DEC-224 (a))."""
        areas = [{'kind': 'allowed', 'polygon': SQUARE(-4, -4, 0, 0)}, {'kind': 'keepout', 'polygon': SQUARE(1, 1, 3, 4)}]
        g = km.rasterize(areas, GEOM)
        with tempfile.TemporaryDirectory() as d:
            files, rec = km.write(g, GEOM, Path(d), '/keepout_filter_mask', '/keepout_costmap_filter_info')
            meta = yaml.safe_load((Path(d) / files['keepout_yaml']).read_text())
            self.assertEqual((meta['mode'], meta['resolution'], meta['origin'][:2]), ('trinary', 0.5, [-5.0, -5.0]))
            raw = (Path(d) / files['keepout_pgm']).read_bytes(); w, h = [int(v) for v in raw.split(b'\n')[1].split()]
            img = np.frombuffer(raw.split(b'\n', 3)[3], dtype=np.uint8).reshape(h, w)
            back = km.map_server_values(img)
            self.assertTrue((back == g).all())
            self.assertEqual(rec['data_sha256'], km.data_sha256(g)); self.assertEqual((rec['width'], rec['height']), (20, 20))
            info = yaml.safe_load((Path(d) / files['keepout_info_yaml']).read_text())['costmap_filter_info_server']['ros__parameters']
            self.assertEqual((info['type'], info['base'], info['multiplier']), (0, 0.0, 1.0))   # what KeepoutFilter requires

    def test_no_area_is_all_unknown(self):
        self.assertTrue((km.rasterize([], GEOM) == km.UNKNOWN).all())

    def test_waypoints_in_keepout_and_validation(self):
        areas = [{'kind': 'keepout', 'polygon': SQUARE(0, 0, 2, 2)}, {'kind': 'allowed', 'polygon': SQUARE(3, 3, 4, 4)}]
        self.assertEqual(km.waypoints_in_keepout(areas, [(1, 1), (3.5, 3.5), (-1, -1)]), [0])
        self.assertTrue(km.validate_areas([{'kind': 'nogo', 'polygon': SQUARE(0, 0, 1, 1)}]))
        self.assertTrue(km.validate_areas([{'kind': 'keepout', 'polygon': [[0, 0], [1, 1]]}]))
        self.assertTrue(km.validate_areas([{'kind': 'keepout', 'polygon': [[0, 0], [1, 'a'], [1, 1]]}]))
        self.assertEqual(km.validate_areas(areas), [])

    def test_narrow_gaps(self):
        """DEC-227 (REV-140): keepout pairs closer than the threshold are reported with the gap and its closest points; touching,
        overlapping or nested areas close the way and are not reported, nor a gap inside a third keepout area (touch-inner lies in a);
        allowed areas are not keepout."""
        a = {'kind': 'keepout', 'polygon': SQUARE(0, 0, 1, 1)}
        near = {'kind': 'keepout', 'polygon': SQUARE(1.8, 0.2, 3, 0.8)}         # 0.8 m to the right of a
        far = {'kind': 'keepout', 'polygon': SQUARE(0, 3, 1, 4)}                # 2.0 m above a
        touch = {'kind': 'keepout', 'polygon': SQUARE(-1, 0, 0, 1)}             # shares an edge with a
        inner = {'kind': 'keepout', 'polygon': SQUARE(0.2, 0.2, 0.4, 0.4)}      # inside a
        allowed = {'kind': 'allowed', 'polygon': SQUARE(1.5, 0, 2, 1)}
        g = km.narrow_gaps([a, near, far, touch, inner, allowed], 1.0)
        self.assertEqual([x['areas'] for x in g], [[0, 1]])
        self.assertAlmostEqual(g[0]['gap_m'], 0.8); self.assertEqual((g[0]['from'][0], g[0]['to'][0]), (1.0, 1.8))
        self.assertEqual(km.narrow_gaps([a, far], 2.5)[0]['gap_m'], 2.0)
        self.assertEqual(km.narrow_gaps([a, far], 2.0), [])   # not below the threshold
        tri = {'kind': 'keepout', 'polygon': [[1.3, -1], [1.3, 2], [0.5, 0.5]]}   # crosses a
        self.assertEqual(km.narrow_gaps([a, tri], 1.0), [])
        diag = {'kind': 'keepout', 'polygon': SQUARE(1.3, 1.4, 2, 2)}            # corner to corner: hypot(0.3, 0.4) = 0.5
        self.assertAlmostEqual(km.narrow_gaps([a, diag], 1.0)[0]['gap_m'], 0.5)


class WaypointSetAreaTests(unittest.TestCase):
    def ws(self, areas=None):
        return wp.WaypointSet('o1', 1, 'h' * 64, [wp.Waypoint(0, 0), wp.Waypoint(1, 0)], [0.5], areas=areas or [])

    def test_hash_without_areas_is_unchanged(self):
        """REV-137: a set without areas keeps the hash it had before the areas existed (saved sets stay valid)."""
        ws = self.ws()
        self.assertNotIn('areas', ws.to_dict())
        # the hashed content has exactly the keys it had before REV-137
        d = ws.to_dict(); [d.pop(k) for k in ('set_id', 'revision', 'note')]
        self.assertEqual(sorted(d), ['frame', 'map', 'schema', 'section_limits_mps', 'waypoints'])
        import hashlib, json
        self.assertEqual(ws.content_hash(), hashlib.sha256(json.dumps(d, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest())

    def test_areas_are_part_of_the_set(self):
        a = [{'kind': 'keepout', 'polygon': SQUARE(0, 0, 1, 1)}]
        ws = self.ws(a)
        self.assertNotEqual(ws.content_hash(), self.ws().content_hash())
        rt = wp.WaypointSet.from_dict(ws.to_dict()); self.assertEqual(rt.content_hash(), ws.content_hash()); self.assertEqual(rt.areas, ws.to_dict()['areas'])
        ws.areas = [{'kind': 'keepout', 'polygon': [[0, 0], [1, 0]]}]; self.assertTrue(ws.validate())


if __name__ == '__main__':
    unittest.main()
