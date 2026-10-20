"""Command lines of other processes are redacted before they are recorded (DEC-139: NTRIP connection data never in logs,
rosbag or records; DEC-151 step 1). All values below are made up."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import device_watch as dw  # noqa: E402

SECRETS = ('fakeuser', 'fakepass', 'caster.example.invalid', 'FAKEMOUNT', '2101')


class RedactCommandTest(unittest.TestCase):
    def test_ntrip_url_is_removed_entirely(self):
        cmd = 'str2str -in ntrip://fakeuser:fakepass@caster.example.invalid:2101/FAKEMOUNT -out serial://serial/by-id/x-if02:115200 -b 1'
        out = dw.redact_command(cmd)
        for s in SECRETS:
            self.assertNotIn(s, out)
        self.assertIn('ntrip://<redacted>', out)
        self.assertIn('serial://serial/by-id/x-if02:115200', out)   # non-secret parts stay readable

    def test_other_ntrip_schemes_and_case(self):
        for scheme in ('ntrips', 'ntripc', 'NTRIP'):
            out = dw.redact_command(f'mrtk relay -out {scheme}://:fakepass@caster.example.invalid:2101/FAKEMOUNT')
            for s in SECRETS:
                self.assertNotIn(s, out, scheme)

    def test_userinfo_of_other_urls(self):
        out = dw.redact_command('curl http://fakeuser:fakepass@host.example.invalid/x tcpcli://fakeuser@h:1')
        self.assertNotIn('fakeuser', out)
        self.assertNotIn('fakepass', out)
        self.assertIn('http://<redacted>@host.example.invalid/x', out)

    def test_password_with_slash_or_at(self):
        for pw in ('fa/kepass', 'fa@kepass', 'fa/ke@pass'):
            out = dw.redact_command(f'curl http://fakeuser:{pw}@host.example.invalid/x')
            self.assertNotIn('fakeuser', out, pw); self.assertNotIn('kepass', out, pw); self.assertNotIn(pw, out)

    def test_plain_commands_unchanged(self):
        cmd = '/opt/ros/jazzy/lib/septentrio_gnss_driver/septentrio_gnss_driver_node --ros-args -r __ns:=/sensors/gnss'
        self.assertEqual(dw.redact_command(cmd), cmd)

    def test_command_lines_redacts_before_shortening(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, '41'))
            long_prefix = 'x' * 190
            with open(os.path.join(root, '41', 'cmdline'), 'wb') as f:
                f.write(f'{long_prefix} -in\0ntrip://fakeuser:fakepass@caster.example.invalid:2101/FAKEMOUNT\0'.encode())
            got = dw.command_lines([41, 42], proc_root=root)
            self.assertEqual(got[42], '?')
            self.assertLessEqual(len(got[41]), 200)
            for s in SECRETS:
                self.assertNotIn(s, got[41])
            for cut in range(1, 12):    # even a cut in the middle of the redacted URL shows no secret
                part = dw.command_lines([41], proc_root=root, limit=len(long_prefix) + cut)[41]
                for s in SECRETS:
                    self.assertNotIn(s, part)


if __name__ == '__main__':
    unittest.main()
