"""Unit tests of gnss_log and the GNSS part of the source registration (REV-063, DEC-126) without ROS."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core.gnss_log import GnssLog, FILE_NAME  # noqa: E402
from gouda_core.map_database import MapDatabase, content_hash  # noqa: E402


def dump(d: Path):
    d.mkdir(parents=True); (d / 'graph.txt').write_text('g'); (d / 'values.bin').write_bytes(b'v'); (d / '000000').mkdir()


class GnssLogTests(unittest.TestCase):
    def test_lines_counts_and_hash(self):
        with tempfile.TemporaryDirectory() as d:
            g = GnssLog(); self.assertFalse(g.active)
            g.write('sensors/gnss/navsatfix', 1.0, {'x': 1})      # not open: ignored
            p = g.open(Path(d) / 'w')
            g.write('sensors/gnss/navsatfix', 2.0, {'latitude': 36.08})
            g.write('sensors/gnss/pvtgeodetic', 2.1, {'mode': 4, 'block_header': {'tow': 1}})
            g.note('types missing', 2.2)
            s = g.close(); self.assertFalse(g.active); self.assertIsNone(g.close())
            lines = [json.loads(x) for x in p.read_text().splitlines()]
            self.assertEqual([x['topic'] for x in lines], ['sensors/gnss/navsatfix', 'sensors/gnss/pvtgeodetic', 'note'])
            self.assertEqual(lines[1]['msg']['mode'], 4)
            self.assertEqual(s['counts'], {'sensors/gnss/navsatfix': 1, 'sensors/gnss/pvtgeodetic': 1, 'note': 1}); self.assertEqual(len(s['sha256']), 64)

    def test_registered_next_to_source_without_changing_its_hash(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); dump(d / 'a' / 'glim_dump'); dump(d / 'b' / 'glim_dump')
            g = GnssLog(); p = g.open(d / 'a'); g.write('sensors/gnss/navsatfix', 1.0, {'status': 2}); s = g.close()
            db = MapDatabase(d / 'maps')
            ok, _, m1 = db.register_source(d / 'a' / 'glim_dump', 'o1', {}, {}, gnss=(p, s))
            ok2, _, m2 = db.register_source(d / 'b' / 'glim_dump', 'o2', {}, {})
            self.assertTrue(ok and ok2)
            self.assertEqual(m1['gnss'], s); self.assertNotIn('gnss', m2)
            self.assertEqual(m1['content_hash'], m2['content_hash'], 'the GLIM dump hash does not include the GNSS record')
            self.assertTrue((d / 'maps' / 'o1' / FILE_NAME).is_file()); self.assertTrue(p.is_file(), 'the work copy is kept')


if __name__ == '__main__':
    unittest.main()
