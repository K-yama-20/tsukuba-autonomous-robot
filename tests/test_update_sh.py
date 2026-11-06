"""Tests of update.sh (main by default; one commit of another branch with `update.sh <branch> <commit>`) and of the
union merge of design/reports/status.md (.gitattributes). Uses temporary git repositories and a stand-in setup.sh;
nothing is fetched from the network and Gouda is not started."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GIT = ['git', '-c', 'user.name=t', '-c', 'user.email=t@example.invalid', '-c', 'init.defaultBranch=main']


def git(cwd, *args):
    r = subprocess.run([*GIT, *args], cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        raise AssertionError(f'git {args}: {r.stdout}{r.stderr}')
    return r.stdout.strip()


class UpdateShTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        seed = self.tmp / 'seed'
        seed.mkdir()
        git(seed, 'init', '-q')
        shutil.copy(REPO / 'update.sh', seed / 'update.sh')
        (seed / 'setup.sh').write_text('echo "SETUP RAN at $(git rev-parse HEAD)"\n')
        (seed / 'a.txt').write_text('1\n')
        git(seed, 'add', '-A'); git(seed, 'commit', '-q', '-m', 'main 1')
        self.main1 = git(seed, 'rev-parse', 'HEAD')
        git(seed, 'switch', '-q', '-c', 'integ')
        (seed / 'a.txt').write_text('2\n'); git(seed, 'commit', '-q', '-am', 'integ 1')
        self.integ1 = git(seed, 'rev-parse', 'HEAD')
        (seed / 'a.txt').write_text('3\n'); git(seed, 'commit', '-q', '-am', 'integ 2')
        self.integ2 = git(seed, 'rev-parse', 'HEAD')
        git(seed, 'switch', '-q', '-c', 'other', self.main1)
        (seed / 'b.txt').write_text('x\n'); git(seed, 'add', 'b.txt'); git(seed, 'commit', '-q', '-m', 'other 1')
        self.other1 = git(seed, 'rev-parse', 'HEAD')
        git(seed, 'switch', '-q', 'main')
        self.origin = self.tmp / 'origin.git'
        git(self.tmp, 'clone', '-q', '--bare', str(seed), str(self.origin))
        # the PC: <workspace>/src/<repo>, cloned with main only (as setup does)
        self.pc = self.tmp / 'ws' / 'src' / 'repo'
        self.pc.parent.mkdir(parents=True)
        git(self.tmp, 'clone', '-q', '--single-branch', '--branch', 'main', str(self.origin), str(self.pc))
        # main moves on after the clone
        (seed / 'a.txt').write_text('1b\n'); git(seed, 'commit', '-q', '-am', 'main 2')
        self.main2 = git(seed, 'rev-parse', 'HEAD')
        git(seed, 'push', '-q', str(self.origin), 'main')

    def run_update(self, *args):
        return subprocess.run(['bash', str(self.pc / 'update.sh'), *args], cwd=self.pc, capture_output=True, text=True)

    def head(self):
        return git(self.pc, 'rev-parse', 'HEAD')

    def test_without_arguments_follows_main(self):
        r = self.run_update()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.head(), self.main2)
        self.assertEqual(git(self.pc, 'rev-parse', '--abbrev-ref', 'HEAD'), 'main')
        self.assertIn(f'SETUP RAN at {self.main2}', r.stdout)

    def test_branch_and_commit_checks_out_that_commit_detached(self):
        r = self.run_update('integ', self.integ2)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.head(), self.integ2)
        self.assertEqual(git(self.pc, 'rev-parse', '--abbrev-ref', 'HEAD'), 'HEAD')  # detached
        self.assertIn(f'commit: {self.integ2}', r.stdout)
        self.assertIn(f'SETUP RAN at {self.integ2}', r.stdout)
        self.assertEqual(git(self.pc, 'rev-parse', 'main'), self.main1)  # the local main is not moved

    def test_an_earlier_commit_of_the_branch_and_a_short_id(self):
        r = self.run_update('integ', self.integ1[:10])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.head(), self.integ1)

    def test_commit_of_another_branch_is_refused(self):
        git(self.pc, 'fetch', '-q', 'origin', 'other:refs/remotes/origin/other')  # the commit exists locally
        r = self.run_update('integ', self.other1)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('is not on origin/integ', r.stderr)
        self.assertEqual(self.head(), self.main1)
        self.assertNotIn('SETUP RAN', r.stdout)

    def test_unknown_commit_and_unknown_branch_are_refused(self):
        r = self.run_update('integ', 'abcdef1234')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('was not found', r.stderr)
        r = self.run_update('no-such-branch', self.integ2)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('could not fetch', r.stderr)
        self.assertEqual(self.head(), self.main1)

    def test_wrong_arguments_are_refused_before_anything_is_fetched(self):
        for args in (('integ',), ('integ', 'not-a-commit'), ('integ', self.integ2, 'extra'), ('bad..name', self.integ2)):
            r = self.run_update(*args)
            self.assertNotEqual(r.returncode, 0, args)
            self.assertIn('STOPPED', r.stderr)
        self.assertEqual(self.head(), self.main1)
        self.assertNotIn('origin/integ', git(self.pc, 'branch', '-r'))  # nothing was fetched

    def test_local_changes_are_refused_and_kept(self):
        (self.pc / 'a.txt').write_text('local\n')
        (self.pc / 'untracked.txt').write_text('u\n')
        r = self.run_update('integ', self.integ2)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('local changes', r.stderr)
        self.assertEqual(self.head(), self.main1)
        self.assertEqual((self.pc / 'a.txt').read_text(), 'local\n')
        self.assertTrue((self.pc / 'untracked.txt').is_file())

    def test_running_gouda_is_refused(self):
        run = self.tmp / 'ws' / 'gouda_data' / 'run'
        run.mkdir(parents=True)
        p = subprocess.Popen(['sleep', '60'], start_new_session=True)
        self.addCleanup(p.wait)
        self.addCleanup(p.kill)
        (run / 'gouda_core.pid').write_text(f'{p.pid}\n')
        r = self.run_update('integ', self.integ2)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('Gouda is running', r.stderr)
        self.assertEqual(self.head(), self.main1)


class StatusUnionMergeTests(unittest.TestCase):
    def test_two_branches_adding_entries_merge_without_conflict(self):
        line = [ln for ln in (REPO / '.gitattributes').read_text().splitlines() if ln.startswith('design/reports/status.md')]
        self.assertEqual(line, ['design/reports/status.md merge=union'])
        tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, tmp, True)
        git(tmp, 'init', '-q')
        st = tmp / 'design' / 'reports' / 'status.md'
        st.parent.mkdir(parents=True)
        (tmp / '.gitattributes').write_text(line[0] + '\n')
        head = '# 現状の要約\n\n'
        st.write_text(head + '**第1便: base**\n- x\n')
        git(tmp, 'add', '-A'); git(tmp, 'commit', '-q', '-m', 'base')
        git(tmp, 'switch', '-q', '-c', 'chat-a')
        st.write_text(head + '**第2便: a**\n- from a\n\n' + '**第1便: base**\n- x\n'); git(tmp, 'commit', '-q', '-am', 'a')
        git(tmp, 'switch', '-q', '-c', 'chat-b', 'main')
        st.write_text(head + '**第3便: b**\n- from b\n\n' + '**第1便: base**\n- x\n'); git(tmp, 'commit', '-q', '-am', 'b')
        git(tmp, 'switch', '-q', 'main')
        git(tmp, 'merge', '-q', '--no-ff', '-m', 'merge a', 'chat-a')
        git(tmp, 'merge', '-q', '--no-ff', '-m', 'merge b', 'chat-b')  # would conflict without merge=union
        text = st.read_text()
        for must in ('**第2便: a**', '- from a', '**第3便: b**', '- from b', '**第1便: base**'):
            self.assertEqual(text.count(must), 1, text)
        self.assertNotIn('<<<<<<<', text)


if __name__ == '__main__':
    unittest.main()
