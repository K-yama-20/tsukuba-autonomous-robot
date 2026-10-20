"""NTRIP relay (DEC-139 option B1, DEC-151 step 3, DEC-156) without ROS. All NTRIP values are made up.

Checked: the started command holds the connection data but the recorded one does not; str2str's status lines are reduced to
states / bytes / bps (the message field, which names the caster and mountpoint, is dropped); only state changes are reported;
a fake str2str run end to end leaks nothing into the reports; the supervisor never passes the started command to a record."""
import ast
import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import ntrip_relay as nr  # noqa: E402

FAKE = {'caster': 'caster.example.invalid', 'port': 47613, 'mountpoint': 'FAKEMOUNT', 'user': 'fakeuser', 'password': 'fakepass'}
DEVICE = 'serial:/dev/serial/by-id/usb-Fake_Receiver_TEST-if02'
SUPERVISOR = Path(__file__).resolve().parents[1] / 'gouda_core' / 'sensor_supervisor_node.py'


def secrets_in(text):
    return [str(v) for v in FAKE.values() if str(v) in text]


MSG = 'caster.example.invalid:47613/FAKEMOUNT'


class CommandTests(unittest.TestCase):
    def test_launch_and_public_commands(self):
        launch, public = nr.relay_commands('/usr/bin/str2str', FAKE, DEVICE, 115200)
        self.assertEqual(launch, ['/usr/bin/str2str', '-in', 'ntrip://fakeuser:fakepass@caster.example.invalid:47613/FAKEMOUNT',
                                  '-out', 'serial://serial/by-id/usb-Fake_Receiver_TEST-if02:115200', '-b', '1'])
        self.assertEqual(secrets_in(' '.join(public)), [])
        self.assertIn('ntrip://<redacted>', public)
        self.assertEqual(public[3:], launch[3:], 'only the ntrip URL differs')

    def test_serial_path(self):
        self.assertEqual(nr.serial_path(DEVICE), 'serial/by-id/usb-Fake_Receiver_TEST-if02')
        for bad in ('', None, 'serial:/dev/ttyACM1', '/dev/serial/by-id/x', 'tcp://192.0.2.1:1'):
            self.assertIsNone(nr.serial_path(bad), bad)


class BuildRelayTests(unittest.TestCase):
    def test_reasons_and_commands(self):
        ok = nr.build_relay('/usr/bin/str2str', FAKE, DEVICE, 115200, True)
        self.assertIsNone(ok['reason']); self.assertEqual(ok['serial_path'], '/dev/serial/by-id/usb-Fake_Receiver_TEST-if02')
        self.assertIn('fakepass', ' '.join(ok['launch'])); self.assertEqual(secrets_in(' '.join(ok['public'])), [])
        cases = {'driver': ('/usr/bin/str2str', FAKE, DEVICE, 115200, False), 'ntrip': ('/usr/bin/str2str', None, DEVICE, 115200, True),
                 'device': ('/usr/bin/str2str', FAKE, 'serial:/dev/ttyACM1', 115200, True), 'exe': (None, FAKE, DEVICE, 115200, True),
                 'baud': ('/usr/bin/str2str', FAKE, DEVICE, None, True)}
        for name, args in cases.items():
            r = nr.build_relay(*args)
            self.assertIsNone(r['launch'], name); self.assertIsNone(r['public'], name); self.assertTrue(r['reason'], name)
            self.assertEqual(secrets_in(json.dumps(r)), [], name)


class StatusTests(unittest.TestCase):
    LINE = '2026/10/20 12:00:05 [CC---]       4096 B    6553 bps caster.example.invalid:47613/FAKEMOUNT'

    def test_parse_drops_the_message(self):
        st = nr.parse_status(self.LINE)
        self.assertEqual(st, {'input': 'connected', 'outputs': ['connected', 'closed', 'closed', 'closed'], 'bytes': 4096, 'bps': 6553})
        self.assertEqual(secrets_in(json.dumps(st)), [])
        for not_status in ('stream server start', '', 'caster.example.invalid:47613/FAKEMOUNT', '[XX] 1 B 1 bps'):
            self.assertIsNone(nr.parse_status(not_status), not_status)

    def test_tracker_reports_state_changes_only(self):
        t = [0.0]
        tr = nr.StatusTracker(clock=lambda: t[0])
        self.assertIsNotNone(tr.feed('2026/10/20 12:00:00 [WC]   0 B   0 bps x'))
        self.assertEqual(tr.bytes_changed_at, 0.0, 'the first status counts as the start')
        t[0] = 5.0
        self.assertIsNone(tr.feed('2026/10/20 12:00:05 [WC]   0 B   0 bps x'), 'same states: no report')
        self.assertIsNotNone(tr.feed('2026/10/20 12:00:10 [CC] 100 B 160 bps x'))
        self.assertEqual(tr.bytes_changed_at, 5.0)
        t[0] = 9.0
        self.assertIsNone(tr.feed('2026/10/20 12:00:15 [CC] 900 B 1280 bps x'))
        self.assertEqual(tr.bytes_changed_at, 9.0)
        self.assertIsNone(tr.feed('garbage with caster.example.invalid'))
        self.assertEqual(tr.unparsed, 1)


class ReaderTests(unittest.TestCase):
    def test_reader_keeps_draining_after_a_callback_error(self):
        lines = [f'2026/10/20 12:00:{i:02d} [{"WC"[i % 2]}C] {i} B 0 bps {MSG}' for i in range(10)]
        seen = []

        def boom(st):
            seen.append(st)
            raise RuntimeError('publish failed')
        it = iter(lines)
        tr = nr.StatusTracker()
        nr.read_status(it, tr, boom)
        self.assertEqual(next(it, None), None, 'every line was read')
        self.assertEqual(tr.callback_errors, len(seen)); self.assertGreater(len(seen), 1)


class FakeStr2strTests(unittest.TestCase):
    def test_end_to_end_reports_hold_no_secret(self):
        with tempfile.TemporaryDirectory() as d:
            args_file = os.path.join(d, 'args.json')
            script = os.path.join(d, 'str2str')
            with open(script, 'w') as f:
                f.write(textwrap.dedent(f'''\
                    #!{sys.executable}
                    import json, sys
                    json.dump(sys.argv[1:], open({args_file!r}, 'w'))
                    msg = 'caster.example.invalid:47613/FAKEMOUNT'
                    for line in ('stream server start',
                                 f'2026/10/20 12:00:00 [WC]          0 B       0 bps {{msg}}',
                                 f'2026/10/20 12:00:05 [CC]        512 B     819 bps {{msg}}',
                                 f'2026/10/20 12:00:10 [CC]       1024 B     819 bps {{msg}}',
                                 'connect error (111) fakeuser fakepass',
                                 f'2026/10/20 12:00:15 [EC]       1024 B       0 bps {{msg}}'):
                        print(line, file=sys.stderr)
                    '''))
            os.chmod(script, os.stat(script).st_mode | stat.S_IXUSR)
            launch, public = nr.relay_commands(script, FAKE, DEVICE, 115200)
            proc = subprocess.Popen(launch, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, errors='replace')
            reports, tracker = [], nr.StatusTracker()
            nr.read_status(proc.stderr, tracker, reports.append)
            self.assertEqual(proc.wait(), 0)
            with open(args_file) as f:
                self.assertEqual(json.load(f), launch[1:], 'the relay gets the real connection data')
            self.assertEqual([r['input'] for r in reports], ['waiting', 'connected', 'error'])
            self.assertEqual(tracker.unparsed, 2)
            self.assertEqual(secrets_in(json.dumps(reports) + json.dumps(public)), [])


class SupervisorSourceTests(unittest.TestCase):
    def test_started_command_never_recorded(self):
        """Static check: no _decision(...) call and no logger call in the supervisor mentions `launch` (the secret command)."""
        tree = ast.parse(SUPERVISOR.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ('_decision', 'info', 'warn', 'warning', 'error'):
                names = {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)} | {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
                self.assertNotIn('launch', names, ast.unparse(node)[:120])
                self.assertNotIn('ntrip', names, ast.unparse(node)[:120])


if __name__ == '__main__':
    unittest.main()
