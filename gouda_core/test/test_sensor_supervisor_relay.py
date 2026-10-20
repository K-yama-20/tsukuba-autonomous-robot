"""The sensor supervisor's NTRIP relay paths (DEC-156) with a fake str2str: the startup summary, the started / state / exit
records hold no NTRIP data, the real data reaches the relay, and a re-created relay is tracked from a fresh state (review
finding). Needs rclpy and gouda_interfaces (skipped where ROS is not installed); no node is created."""
import json
import os
import stat
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    from gouda_core import sensor_supervisor_node as ssn  # noqa: E402
except ImportError:   # no ROS here
    ssn = None
from gouda_core import device_watch as dw  # noqa: E402

FAKE = {'caster': 'caster.example.invalid', 'port': 47613, 'mountpoint': 'FAKEMOUNT', 'user': 'fakeuser', 'password': 'fakepass'}
DEVICE = 'serial:/dev/serial/by-id/usb-Fake_Receiver_TEST-if02'
MSG = 'caster.example.invalid:47613/FAKEMOUNT'


@unittest.skipIf(ssn is None, 'rclpy / gouda_interfaces not available')
class SupervisorRelayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        self.args_file = os.path.join(d, 'args.json')
        script = os.path.join(d, 'str2str')
        lines = ['stream server start', f'2026/10/20 12:00:00 [WC] 0 B 0 bps {MSG}', f'2026/10/20 12:00:05 [CC] 512 B 819 bps {MSG}',
                 'connect error (111) fakeuser fakepass']
        with open(script, 'w') as f:
            f.write(f'#!{sys.executable}\nimport json, sys\njson.dump(sys.argv[1:], open({self.args_file!r}, "w"))\n'
                    f'for line in {lines!r}:\n    print(line, file=sys.stderr)\n')
        os.chmod(script, os.stat(script).st_mode | stat.S_IXUSR)
        self.old_path = os.environ.get('PATH', '')
        os.environ['PATH'] = d + os.pathsep + self.old_path
        sup = ssn.SensorSupervisorNode.__new__(ssn.SensorSupervisorNode)   # no rclpy node: only the methods under test
        sup.records, sup._stopping, sup.previous = [], False, {}
        lock = threading.Lock()

        def record(event, reason, details):
            with lock:
                sup.records.append((event, reason, json.dumps(details, default=str)))
        sup._decision = record
        sup._device_users = lambda drv: ('', [])
        gnss = ssn.Driver('gnss', 'GNSS (ND-19)', dw.WatchedDevice('x'), ['driver'], None)
        gnss.relay_input = (DEVICE, dict(FAKE), 115200)
        sup.drivers = {'gnss': gnss}
        self.relay = sup._build_relay(gnss)
        sup.drivers['ntrip'] = self.relay
        self.sup = sup

    def tearDown(self):
        os.environ['PATH'] = self.old_path
        self.tmp.cleanup()

    def _run_once(self):
        self.assertTrue(self.sup._start(self.relay, 'tty-1', 'driver_started', 'device present'))
        proc = self.relay.proc
        proc.wait(timeout=10)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not any(e == 'ntrip_relay_exited' for e, _, _ in self.sup.records[self._mark:]):
            time.sleep(0.02)

    def _leaks(self, text):
        return [str(v) for v in FAKE.values() if str(v) in text]

    def test_records_hold_no_secret_and_relay_gets_it(self):
        self.assertEqual(self._leaks(json.dumps(self.sup._drivers_summary())), [])
        self.assertIn('ntrip://<redacted>', self.sup._drivers_summary()['ntrip']['command'])
        self._mark = 0
        self._run_once()
        with open(self.args_file) as f:
            self.assertIn('fakeuser:fakepass@caster.example.invalid:47613/FAKEMOUNT', ' '.join(json.load(f)))
        events = [e for e, _, _ in self.sup.records]
        self.assertIn('driver_started', events); self.assertIn('ntrip_relay_state', events); self.assertIn('ntrip_relay_exited', events)
        self.assertEqual(self._leaks(json.dumps(self.sup.records)), [])

    def test_recreated_relay_reports_its_states_again(self):
        self._mark = 0
        self._run_once()
        first = [r for r in self.sup.records if r[0] == 'ntrip_relay_state']
        self._mark = len(self.sup.records)
        self._run_once()   # e.g. USB2 re-connected: the same output again from a new process
        second = [r for r in self.sup.records[self._mark:] if r[0] == 'ntrip_relay_state']
        self.assertEqual(len(second), len(first), 'a new process is tracked from no state')
        self.assertEqual(self._leaks(json.dumps(self.sup.records)), [])


if __name__ == '__main__':
    unittest.main()
