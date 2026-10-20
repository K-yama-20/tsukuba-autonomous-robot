"""Tests of design/tools/reserve_ids.py (two sessions must not get the same REV / DEC / 便 number)."""
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import reserve_ids  # noqa: E402


def make_design(root: Path) -> Path:
    d = root / 'design'
    (d / 'revisions').mkdir(parents=True)
    (d / 'reports').mkdir()
    (d / 'revisions' / 'REV-079.yaml').write_text('id: REV-079\ndecisions:\n- id: DEC-148\n', encoding='utf-8')
    (d / 'model.yaml').write_text('decisions:\n- id: DEC-149\n', encoding='utf-8')
    (d / 'reports' / 'status.md').write_text('**第47便: a**\n**第46便: b**\n', encoding='utf-8')
    return d


class ReserveIdsTests(unittest.TestCase):
    def test_next_numbers(self):
        with tempfile.TemporaryDirectory() as t:
            d = make_design(Path(t))
            r = reserve_ids.reserve('s1', decisions=2, bin_number=True, design=d)
            self.assertEqual(r, {'revision': 'REV-080', 'decisions': ['DEC-150', 'DEC-151'], 'bin': '第48便'})
            self.assertTrue(reserve_ids.is_reservation_only((d / 'revisions' / 'REV-080.yaml').read_text(encoding='utf-8')))

    def test_second_session_gets_the_following_numbers(self):
        with tempfile.TemporaryDirectory() as t:
            d = make_design(Path(t))
            a = reserve_ids.reserve('s1', decisions=1, bin_number=True, design=d)
            b = reserve_ids.reserve('s2', decisions=1, bin_number=True, design=d)
            self.assertEqual((a['revision'], b['revision']), ('REV-080', 'REV-081'))
            self.assertEqual((a['decisions'], b['decisions']), (['DEC-150'], ['DEC-151']))
            self.assertEqual((a['bin'], b['bin']), ('第48便', '第49便'))

    def test_concurrent_reservations_are_distinct(self):
        with tempfile.TemporaryDirectory() as t:
            d = make_design(Path(t))
            got = []
            lock = threading.Lock()

            def run(i):
                r = reserve_ids.reserve(f's{i}', decisions=1, bin_number=True, design=d)
                with lock:
                    got.append(r)
            ths = [threading.Thread(target=run, args=(i,)) for i in range(8)]
            for th in ths:
                th.start()
            for th in ths:
                th.join()
            for key in ('revision', 'bin'):
                vals = [r[key] for r in got]
                self.assertEqual(len(set(vals)), 8, vals)
            decs = [r['decisions'][0] for r in got]
            self.assertEqual(len(set(decs)), 8, decs)

    def test_without_revision(self):
        with tempfile.TemporaryDirectory() as t:
            d = make_design(Path(t))
            r = reserve_ids.reserve('s1', decisions=1, design=d, revision=False)
            self.assertEqual(r, {'revision': None, 'decisions': ['DEC-150'], 'bin': None})
            self.assertEqual(sorted(p.name for p in (d / 'revisions').iterdir()), ['REV-079.yaml'])

    def test_written_change_set_is_not_a_reservation(self):
        self.assertFalse(reserve_ids.is_reservation_only('# 変更セット REV-081\nid: REV-081\n'))
        self.assertFalse(reserve_ids.is_reservation_only('# a plain comment only\n'))


if __name__ == '__main__':
    unittest.main()
