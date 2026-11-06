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


def make_worktree(root: Path, name: str, rev: int, dec: int, bin_no: int, extra_model: str = '') -> Path:
    d = root / name / 'design'
    (d / 'revisions').mkdir(parents=True)
    (d / 'reports').mkdir()
    (d / 'revisions' / f'REV-{rev:03d}.yaml').write_text(f'id: REV-{rev:03d}\n', encoding='utf-8')
    (d / 'model.yaml').write_text(f'decisions:\n- id: DEC-{dec:03d}\n{extra_model}', encoding='utf-8')
    (d / 'reports' / 'status.md').write_text(f'**第{bin_no}便: a**\n', encoding='utf-8')
    return d


class SharedReservationTests(unittest.TestCase):
    """Markers in one place shared by all worktrees; PRM / IFD / ND ids."""

    def test_model_ids(self):
        with tempfile.TemporaryDirectory() as t:
            d = make_design(Path(t))
            (d / 'model.yaml').write_text(
                'decisions:\n- id: DEC-149\nparameters:\n- id: PRM-163\n- id: PRM-07\ninterfaces:\n- id: IFD-71\n'
                'nodes:\n- id: ND-30\n- note: IND-99 and BOND-98 are not node ids\n', encoding='utf-8')
            (d / 'revisions' / 'REV-079.yaml').write_text('id: REV-079\nadd:\n- id: IFD-72\n', encoding='utf-8')
            r = reserve_ids.reserve('s1', design=d, revision=False, model_ids={'PRM': 2, 'IFD': 1, 'ND': 1})
            self.assertEqual(r['prm'], ['PRM-164', 'PRM-165'])
            self.assertEqual(r['ifd'], ['IFD-73'])
            self.assertEqual(r['nd'], ['ND-31'])
            r2 = reserve_ids.reserve('s2', design=d, revision=False, model_ids={'PRM': 1, 'ND': 1})
            self.assertEqual((r2['prm'], r2['nd']), (['PRM-166'], ['ND-32']))
            self.assertNotIn('ifd', r2)

    def test_unknown_model_id_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            d = make_design(Path(t))
            with self.assertRaises(ValueError):
                reserve_ids.reserve('s1', design=d, revision=False, model_ids={'TR': 1})

    def test_two_worktrees_share_the_markers(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            a = make_worktree(root, 'a', rev=280, dec=498, bin_no=254, extra_model='parameters:\n- id: PRM-163\n')
            b = make_worktree(root, 'b', rev=233, dec=443, bin_no=205, extra_model='parameters:\n- id: PRM-120\n')
            shared = root / 'common' / 'gouda-reservations'
            kw = dict(decisions=1, bin_number=True, model_ids={'PRM': 1}, shared=shared, designs=[a, b])
            # the older worktree b reserves first: it must count what worktree a already uses
            rb = reserve_ids.reserve('sb', design=b, **{**kw, 'designs': [b, a]})
            ra = reserve_ids.reserve('sa', design=a, **kw)
            self.assertEqual((rb['revision'], rb['decisions'], rb['bin'], rb['prm']), ('REV-281', ['DEC-499'], '第255便', ['PRM-164']))
            self.assertEqual((ra['revision'], ra['decisions'], ra['bin'], ra['prm']), ('REV-282', ['DEC-500'], '第256便', ['PRM-165']))
            # the REV file is created only in the worktree that reserved it; the markers are only in the shared place
            self.assertTrue((b / 'revisions' / 'REV-281.yaml').is_file())
            self.assertFalse((a / 'revisions' / 'REV-281.yaml').exists())
            self.assertTrue((a / 'revisions' / 'REV-282.yaml').is_file())
            self.assertFalse((a / 'reports' / 'reservations').exists())
            self.assertFalse((b / 'reports' / 'reservations').exists())
            self.assertEqual(sorted(p.name for p in shared.iterdir()),
                             ['DEC-499.txt', 'DEC-500.txt', 'PRM-164.txt', 'PRM-165.txt', 'REV-281.txt', 'REV-282.txt',
                              'bin-255.txt', 'bin-256.txt'])

    def test_marker_alone_keeps_the_number(self):
        """A number reserved in another worktree whose files are not visible (e.g. removed worktree) is not reused."""
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            a = make_worktree(root, 'a', rev=280, dec=498, bin_no=254)
            shared = root / 'common' / 'gouda-reservations'
            shared.mkdir(parents=True)
            for name in ('REV-290.txt', 'DEC-510.txt', 'bin-260.txt', 'ND-40.txt'):
                (shared / name).write_text('# reserved by reserve_ids.py: gone\n', encoding='utf-8')
            r = reserve_ids.reserve('sa', decisions=1, bin_number=True, design=a, model_ids={'ND': 1}, shared=shared, designs=[a])
            self.assertEqual((r['revision'], r['decisions'], r['bin'], r['nd']), ('REV-291', ['DEC-511'], '第261便', ['ND-41']))

    def test_markers_of_the_earlier_scheme_are_counted_and_copied(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            a = make_worktree(root, 'a', rev=280, dec=498, bin_no=254)
            legacy = a / 'reports' / 'reservations'
            legacy.mkdir()
            (legacy / 'DEC-499.txt').write_text('# reserved by reserve_ids.py: old 2026-11-07T05:00:00\n', encoding='utf-8')
            (legacy / 'bin-255.txt').write_text('# reserved by reserve_ids.py: old 2026-11-07T05:00:00\n', encoding='utf-8')
            (a / 'revisions' / 'REV-281.yaml').write_text('# reserved by reserve_ids.py: old 2026-11-07T05:00:00\n', encoding='utf-8')
            shared = root / 'common' / 'gouda-reservations'
            r = reserve_ids.reserve('new', decisions=1, bin_number=True, design=a, shared=shared, designs=[a])
            self.assertEqual((r['revision'], r['decisions'], r['bin']), ('REV-282', ['DEC-500'], '第256便'))
            self.assertEqual((shared / 'DEC-499.txt').read_text(encoding='utf-8'), (legacy / 'DEC-499.txt').read_text(encoding='utf-8'))
            self.assertTrue((shared / 'bin-255.txt').is_file())
            self.assertEqual(sorted(p.name for p in legacy.iterdir()), ['DEC-499.txt', 'bin-255.txt'])  # nothing new in the old place

    def test_rev_file_without_marker_is_skipped(self):
        """A REV file that appears in this worktree after the scan (no marker) is not overwritten."""
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            a = make_worktree(root, 'a', rev=280, dec=498, bin_no=254)
            shared = root / 'common' / 'gouda-reservations'
            real_max = reserve_ids._max_number

            def stale(pattern, texts):  # the scan saw REV-280 only; REV-281.yaml is written meanwhile
                n = real_max(pattern, texts)
                if 'yaml' in pattern and not (a / 'revisions' / 'REV-281.yaml').exists():
                    (a / 'revisions' / 'REV-281.yaml').write_text('id: REV-281\n', encoding='utf-8')
                return n
            reserve_ids._max_number = stale
            try:
                r = reserve_ids.reserve('sa', design=a, shared=shared, designs=[a])
            finally:
                reserve_ids._max_number = real_max
            self.assertEqual(r['revision'], 'REV-282')
            self.assertEqual((a / 'revisions' / 'REV-281.yaml').read_text(encoding='utf-8'), 'id: REV-281\n')

    def test_concurrent_reservations_from_two_worktrees_are_distinct(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            a = make_worktree(root, 'a', rev=280, dec=498, bin_no=254)
            b = make_worktree(root, 'b', rev=233, dec=443, bin_no=205)
            shared = root / 'common' / 'gouda-reservations'
            got = []
            lock = threading.Lock()

            def run(i):
                me, other = (a, b) if i % 2 else (b, a)
                r = reserve_ids.reserve(f's{i}', decisions=1, bin_number=True, design=me, model_ids={'PRM': 1, 'IFD': 1, 'ND': 1},
                                        shared=shared, designs=[me, other])
                with lock:
                    got.append(r)
            ths = [threading.Thread(target=run, args=(i,)) for i in range(8)]
            for th in ths:
                th.start()
            for th in ths:
                th.join()
            for pick in (lambda r: r['revision'], lambda r: r['bin'], lambda r: r['decisions'][0], lambda r: r['prm'][0],
                         lambda r: r['ifd'][0], lambda r: r['nd'][0]):
                vals = [pick(r) for r in got]
                self.assertEqual(len(set(vals)), 8, vals)

    def test_git_worktrees_use_the_common_git_directory(self):
        """With real git: two worktrees of one clone resolve to the same marker directory and see each other's files."""
        import shutil
        import subprocess
        if not shutil.which('git'):
            self.skipTest('git not found')
        with tempfile.TemporaryDirectory() as t:
            root = Path(t).resolve()
            main = root / 'main'
            d = make_worktree(root, 'main', rev=280, dec=498, bin_no=254)

            def git(*args, cwd=main):
                subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@example.invalid', *args], cwd=cwd, check=True,
                               capture_output=True)
            git('init', '-q')
            git('add', '-A')
            git('commit', '-q', '-m', 'base')
            git('worktree', 'add', '-q', '-b', 'chat-b', str(root / 'wt-b'))
            d2 = root / 'wt-b' / 'design'
            self.assertEqual(reserve_ids.shared_dir(d), main / '.git' / 'gouda-reservations')
            self.assertEqual(reserve_ids.shared_dir(d2), main / '.git' / 'gouda-reservations')
            self.assertEqual([p.resolve() for p in reserve_ids.worktree_designs(d2)], [d2.resolve(), d.resolve()])
            r1 = reserve_ids.reserve('main', decisions=1, bin_number=True, design=d)
            r2 = reserve_ids.reserve('wt-b', decisions=1, bin_number=True, design=d2)
            self.assertEqual((r1['revision'], r1['decisions'], r1['bin']), ('REV-281', ['DEC-499'], '第255便'))
            self.assertEqual((r2['revision'], r2['decisions'], r2['bin']), ('REV-282', ['DEC-500'], '第256便'))
            out = subprocess.run(['git', 'status', '--porcelain'], cwd=main, capture_output=True, text=True, check=True).stdout
            self.assertEqual(out.split(), ['??', 'design/revisions/REV-281.yaml'])  # the markers are not in the working tree

    def test_command_line_with_design_of_another_worktree(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as t:
            d = make_design(Path(t))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = reserve_ids.main(['--label', 's1', '--design', str(d), '--decisions', '1', '--bin', '--prm', '2', '--nd', '1'])
            self.assertEqual(rc, 0)
            self.assertEqual(buf.getvalue().split(), ['REV-080', 'DEC-150', '第48便', 'PRM-01', 'PRM-02', 'ND-01'])
            self.assertTrue((d / 'revisions' / 'REV-080.yaml').is_file())

    def test_command_line_refuses_a_folder_that_is_not_a_design_folder(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as t:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                reserve_ids.main(['--label', 's1', '--design', t, '--bin'])
            self.assertEqual(list(Path(t).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
