"""Unit tests of gnss_config (ND-19 settings) without ROS. Design: ND-19, IFD-47..49, PRM-65 (REV-061, DEC-123).

Checked: the driver parameters replace ONLY the Gouda keys of the upstream template (saved copy in
design/research/upstream_sensors/septentrio_gnss_driver_1.4.8/gnss.yaml) and keep every other value; an unresolved connection
(PRM-65) stops the generation instead of being filled in; a connection that is neither tcp nor serial is refused; the private
NTRIP file (DEC-154) never reaches the driver, its values never appear in the parameters or the notes, and a valid one only sets
rtk_settings.serial_1.port (PRM-75); the receiver is found by the interface whose prefix
contains its address."""
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import gnss_config as gc  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
TEMPLATE = REPO / 'design' / 'research' / 'upstream_sensors' / 'septentrio_gnss_driver_1.4.8' / 'gnss.yaml'
GOUDA_KEYS = {'device', 'configure_rx', 'frame_id', 'aux1_frame_id', 'vehicle_frame_id', 'poi_frame_id', 'get_spatial_config_from_tf', 'receiver_type',
              'multi_antenna', 'use_gnss_time', 'publish', 'rtk_settings'}
TCP = 'tcp://192.0.2.1:28784'   # documentation address (RFC 5737), not a vehicle value
DECIDED = {'device': TCP, 'configure_rx': False}   # configure_rx (PRM-74) is undecided in the model; a test value here
DECIDED_RTK = dict(DECIDED, rtk_input_port='USB2', rtk_relay_device='serial:/dev/serial/by-id/usb-X-if02')   # PRM-75, PRM-76
FAKE_NTRIP = {'caster': 'caster.example.invalid', 'port': 47613, 'mountpoint': 'FAKEMOUNT', 'user': 'fakeuser', 'password': 'fakepass'}   # made up


def template():
    with open(TEMPLATE, encoding='utf-8') as f:
        return yaml.safe_load(f)


class DriverParameterTests(unittest.TestCase):
    def test_only_gouda_keys_change(self):
        t = template(); before = copy.deepcopy(t)
        p, missing, problems = gc.driver_parameters(t, DECIDED)
        self.assertEqual((missing, problems), ([], []))
        self.assertEqual(t, before, 'the template must not be modified')
        for k, v in before.items():
            if k not in GOUDA_KEYS:
                self.assertEqual(p[k], v, k)
        self.assertEqual(p['device'], TCP); self.assertIs(p['configure_rx'], False)
        self.assertEqual((p['frame_id'], p['aux1_frame_id'], p['vehicle_frame_id']), (gc.MAIN_FRAME, gc.AUX1_FRAME, gc.VEHICLE_FRAME))
        self.assertTrue(p['get_spatial_config_from_tf']); self.assertTrue(p['multi_antenna']); self.assertFalse(p['use_gnss_time'])
        self.assertFalse(p['publish']['tf'], 'TF has one owner (ND-13)')
        for k, v in before['publish'].items():
            if k not in ('tf', 'navsatfix', 'pvtgeodetic', 'atteuler', 'attcoveuler'):
                self.assertEqual(p['publish'][k], v, k)
        self.assertEqual(p['rtk_settings'], before['rtk_settings'], 'no private file: the template rtk_settings stay')

    def test_unresolved_connection_is_not_filled_in(self):
        p, missing, problems = gc.driver_parameters(template(), {})
        self.assertEqual(missing, ['device', 'configure_rx'])
        self.assertEqual(p['device'], template()['device'], 'the template value is not used as a decision; the caller does not start the driver')
        with tempfile.TemporaryDirectory() as d:
            r = gc.write_parameter_file(str(TEMPLATE), {}, os.path.join(d, 'p.yaml'), d)
            self.assertEqual(r['missing'], ['device', 'configure_rx']); self.assertFalse(os.path.exists(os.path.join(d, 'p.yaml')))

    def test_configure_rx_undecided_does_not_start(self):
        # DEC-140 / DEC-141: with the approved connection but configure_rx undecided, nothing is written (the driver is not started)
        with tempfile.TemporaryDirectory() as d:
            r = gc.write_parameter_file(str(TEMPLATE), {'device': 'serial:/dev/serial/by-id/usb-X-if00'}, os.path.join(d, 'p.yaml'), d)
            self.assertEqual(r['missing'], ['configure_rx']); self.assertFalse(os.path.exists(os.path.join(d, 'p.yaml')))

    def test_connection_forms(self):
        self.assertEqual(gc.parse_device(TCP), {'kind': 'tcp', 'host': '192.0.2.1', 'port': 28784})
        self.assertEqual(gc.parse_device('serial:/dev/serial/by-id/usb-X-if00'), {'kind': 'serial', 'path': '/dev/serial/by-id/usb-X-if00'})
        for bad in ('/dev/ttyACM0', 'tcp://receiver:28784', 'serial:ttyACM0', '', 'serial:/dev/ttyACM0', 'serial:/dev/serial/by-path/pci-x',
                    'serial:/dev/serial/by-id/', 'serial:/dev/serial/by-id/../ttyACM0'):
            self.assertIsNone(gc.parse_device(bad), bad)
        for bad in ('/dev/ttyACM0', 'serial:/dev/ttyACM0'):
            _, _, problems = gc.driver_parameters(template(), {'device': bad, 'configure_rx': False})
            self.assertEqual(len(problems), 1, bad)
            with tempfile.TemporaryDirectory() as d:
                r = gc.write_parameter_file(str(TEMPLATE), {'device': bad, 'configure_rx': False}, os.path.join(d, 'p.yaml'), d)
                self.assertTrue(r['problems']); self.assertFalse(os.path.exists(os.path.join(d, 'p.yaml')), 'a ttyACM name never starts the driver')

    def _write_rtk(self, d, doc, mode=0o600):
        path = os.path.join(d, gc.RTK_FILE)
        with open(path, 'w') as f:
            if isinstance(doc, str):
                f.write(doc)
            else:
                yaml.safe_dump(doc, f)
        os.chmod(path, mode)

    def _check_no_secret(self, out, result):
        text = json.dumps(result) + (open(out).read() if os.path.exists(out) else '')
        for v in FAKE_NTRIP.values():
            self.assertNotIn(str(v), text)

    def test_ntrip_file_valid(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 'run', 'p.yaml')
            r = gc.write_parameter_file(str(TEMPLATE), DECIDED_RTK, out, d)
            self.assertIn('not found', r['rtk']); self.assertFalse(r['corrections'])
            self._write_rtk(d, {'ntrip': FAKE_NTRIP})
            ntrip, note = gc.read_ntrip(d)
            self.assertEqual(ntrip, FAKE_NTRIP, 'the relay gets the five values')
            r = gc.write_parameter_file(str(TEMPLATE), DECIDED_RTK, out, d)
            self.assertTrue(r['corrections']); self.assertIn('ntrip from', r['rtk'])
            with open(out) as f: rtk = yaml.safe_load(f)['/**']['ros__parameters']['rtk_settings']
            expected = copy.deepcopy(template()['rtk_settings']); expected['serial_1']['port'] = 'USB2'
            self.assertEqual(rtk, expected, 'only serial_1.port changes; rtk_standard, send_gga, baud_rate, keep_open stay')
            self._check_no_secret(out, r)
            self.assertEqual(os.stat(out).st_mode & 0o077, 0)

    def test_ntrip_without_input_port(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 'p.yaml')
            self._write_rtk(d, {'ntrip': FAKE_NTRIP})
            r = gc.write_parameter_file(str(TEMPLATE), DECIDED, out, d)
            self.assertFalse(r['corrections']); self.assertIn('rtk_input_port (PRM-75) unresolved', r['rtk'])
            with open(out) as f: rtk = yaml.safe_load(f)['/**']['ros__parameters']['rtk_settings']
            self.assertEqual(rtk, template()['rtk_settings']); self._check_no_secret(out, r)

    def test_ntrip_file_refused(self):
        bad_cases = {
            'missing key': {'ntrip': {k: v for k, v in FAKE_NTRIP.items() if k != 'password'}},
            'port text': {'ntrip': dict(FAKE_NTRIP, port='2101x')},
            'port bool': {'ntrip': dict(FAKE_NTRIP, port=True)},
            'port range': {'ntrip': dict(FAKE_NTRIP, port=70000)},
            'space': {'ntrip': dict(FAKE_NTRIP, user='fake user')},
            'empty': {'ntrip': dict(FAKE_NTRIP, password='')},
            'slash': {'ntrip': dict(FAKE_NTRIP, mountpoint='FAKE/MOUNT')},
            'not mapping': {'ntrip': ['x']},
            'old format': {'rtk_settings': {'ntrip_1': {'caster': FAKE_NTRIP['caster'], 'username': FAKE_NTRIP['user'],
                                                        'password': FAKE_NTRIP['password'], 'mountpoint': FAKE_NTRIP['mountpoint']}},
                           'ntrip': FAKE_NTRIP},
            'hash in password': {'ntrip': dict(FAKE_NTRIP, password='fake#pass')},
            'colon in user': {'ntrip': dict(FAKE_NTRIP, user='fake:user')},
            'colon in mountpoint': {'ntrip': dict(FAKE_NTRIP, mountpoint='FAKE:MOUNT')},
            'colon in caster': {'ntrip': dict(FAKE_NTRIP, caster='caster.example.invalid:1')},
            'yaml list': '- a\n- b\n',
            'broken yaml': 'ntrip: [\n',
        }
        for name, doc in bad_cases.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as d:
                out = os.path.join(d, 'p.yaml')
                self._write_rtk(d, doc)
                ntrip, note = gc.read_ntrip(d)
                self.assertIsNone(ntrip); self.assertIn('no RTK corrections', note)
                r = gc.write_parameter_file(str(TEMPLATE), DECIDED_RTK, out, d)
                self.assertFalse(r['corrections']); self.assertTrue(os.path.exists(out), 'the driver still starts without corrections')
                with open(out) as f: rtk = yaml.safe_load(f)['/**']['ros__parameters']['rtk_settings']
                self.assertEqual(rtk, template()['rtk_settings'])
                self._check_no_secret(out, r)

    def test_numeric_values_get_a_quoting_hint(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_rtk(d, 'ntrip:\n  caster: caster.example.invalid\n  port: 47613\n  mountpoint: FAKEMOUNT\n  user: fakeuser\n  password: 31415926\n')
            ntrip, note = gc.read_ntrip(d)
            self.assertIsNone(ntrip); self.assertIn('password is not a string', note); self.assertIn('quotes', note)
            self.assertNotIn('31415926', note)
            self._write_rtk(d, 'ntrip:\n  caster: caster.example.invalid\n  port: 47613\n  mountpoint: FAKEMOUNT\n  user: fakeuser\n  password: "31415926"\n')
            ntrip, _ = gc.read_ntrip(d)
            self.assertEqual(ntrip['password'], '31415926')

    def test_prepare_driver_hands_the_secret_to_the_relay_only(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 'p.yaml')
            self._write_rtk(d, {'ntrip': FAKE_NTRIP})
            r, ntrip = gc.prepare_driver(str(TEMPLATE), DECIDED_RTK, out, d)
            self.assertEqual(ntrip, FAKE_NTRIP); self.assertTrue(r['corrections']); self.assertEqual(r['baud'], template()['rtk_settings']['serial_1']['baud_rate'])
            self._check_no_secret(out, r)
            r, ntrip = gc.prepare_driver(str(TEMPLATE), DECIDED, out, d)   # PRM-75 missing: no corrections, no secret handed out
            self.assertIsNone(ntrip); self.assertFalse(r['corrections'])

    def test_ntrip_file_permissions(self):
        for mode in (0o640, 0o604, 0o660):
            with self.subTest(oct(mode)), tempfile.TemporaryDirectory() as d:
                self._write_rtk(d, {'ntrip': FAKE_NTRIP}, mode)
                ntrip, note = gc.read_ntrip(d)
                self.assertIsNone(ntrip); self.assertIn('chmod 600', note)
                self.assertNotIn(FAKE_NTRIP['password'], note)

    def test_ntrip_extra_keys_named_not_valued(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_rtk(d, {'ntrip': FAKE_NTRIP, 'comment': 'fake-extra-value'})
            ntrip, note = gc.read_ntrip(d)
            self.assertEqual(ntrip, FAKE_NTRIP); self.assertIn("ignored keys: ['comment']", note)
            self.assertNotIn('fake-extra-value', note)

    def test_peer_interface(self):
        links = [{'ifname': 'lo', 'ifindex': 1, 'addr_info': [{'local': '127.0.0.1', 'prefixlen': 8}]},
                 {'ifname': 'enp0s5', 'ifindex': 2, 'addr_info': [{'local': '10.0.0.5', 'prefixlen': 24}]},
                 {'ifname': 'usb0', 'ifindex': 9, 'addr_info': [{'local': '192.0.2.2', 'prefixlen': 24}]}]
        self.assertEqual(gc.peer_interface('192.0.2.1', json.dumps(links)), 'usb0 #9')
        self.assertIsNone(gc.peer_interface('198.51.100.1', json.dumps(links)))
        self.assertIsNone(gc.peer_interface('192.0.2.1', 'not json'))


if __name__ == '__main__':
    unittest.main()
