"""The sensor supervisor's NTRIP relay paths (DEC-156, DEC-361) with fake stunnel4 and str2str: the startup summary, the started / state / exit
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
from test_ntrip_relay import write_fakes  # noqa: E402

FAKE = {'caster': 'caster.example.invalid', 'port': 47613, 'mountpoint': 'FAKEMOUNT', 'user': 'fakeuser', 'password': 'fakepass'}
DEVICE = 'serial:/dev/serial/by-id/usb-Fake_Receiver_TEST-if02'
MSG = 'caster.example.invalid:47613/FAKEMOUNT'


@unittest.skipIf(ssn is None, 'rclpy / gouda_interfaces not available')
class SupervisorRelayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        _stunnel, _str2str, _stunnel_rec, self.args_file = write_fakes(d)   # named stunnel4 and str2str, found through PATH
        self.old_path = os.environ.get('PATH', '')
        self.old_pythonpath = os.environ.get('PYTHONPATH')
        os.environ['PATH'] = d + os.pathsep + self.old_path
        os.environ['PYTHONPATH'] = str(Path(__file__).resolve().parents[1]) + (os.pathsep + self.old_pythonpath if self.old_pythonpath else '')
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
        if self.old_pythonpath is None:
            os.environ.pop('PYTHONPATH', None)
        else:
            os.environ['PYTHONPATH'] = self.old_pythonpath
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
            args = ' '.join(json.load(f))
        self.assertRegex(args, r'fakeuser:fakepass@127\.0\.0\.1:\d+/FAKEMOUNT', 'the relay gets the credentials and talks to stunnel only')
        self.assertNotIn('caster.example.invalid', args)
        events = [e for e, _, _ in self.sup.records]
        self.assertIn('driver_started', events); self.assertIn('ntrip_relay_state', events); self.assertIn('ntrip_relay_exited', events)
        self.assertIn('ntrip_tls_state', events)
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

    def test_relay_not_started_without_stunnel_is_still_observed(self):
        """Without stunnel4 the relay is not started, and evaluating it must not fall into the LiDAR branch of _observe
        (AttributeError host_ip killed the supervisor's evaluation thread on the VM, 第147便)."""
        r = ssn.nr.build_relay('/usr/bin/str2str', dict(FAKE), DEVICE, 115200, True, None)
        d = ssn.Driver('ntrip', 'NTRIP relay (ND-19)', dw.WatchedDevice('x'), r['public'], r['reason'], launch=r['launch'],
                       launch_input=r['launch_input'], serial_path=r['serial_path'])
        self.assertIsNone(d.command)
        self.assertIsNone(self.sup._observe(d), 'the fake by-id device does not exist')
        self.sup._save = lambda: None
        self.sup._evaluate(d)   # records presence only; nothing is started
        self.assertIsNone(d.proc)
        self.assertEqual(self._leaks(json.dumps(self.sup.records)), [])


if __name__ == '__main__':
    unittest.main()
