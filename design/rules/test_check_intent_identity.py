"""Tests of the intent identity checker: recorded replacements pass, unrecorded line changes fail."""
import subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / 'design/tools/check_intent_identity.py'


def run(new_path, out):
    return subprocess.run([sys.executable, str(TOOL), '--new', new_path, '--out', out], cwd=ROOT, text=True, capture_output=True)


class IntentIdentityTests(unittest.TestCase):
    def test_current_intent_passes(self):
        with tempfile.TemporaryDirectory() as d:
            r = run('design/intent.md', str(Path(d) / 'rep'))
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_unrecorded_contract_change_fails(self):
        text = (ROOT / 'design/intent.md').read_text()
        self.assertIn('・bluetooth接続の手動操作がESP32で優先される', text)
        altered = text.replace('・bluetooth接続の手動操作がESP32で優先される', '・bluetooth接続の手動操作がPCで優先される')
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'intent_altered.md'; p.write_text(altered)
            r = run(str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p), str(Path(d) / 'rep'))
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn('DIFFERENT', r.stdout)


if __name__ == '__main__': unittest.main()
