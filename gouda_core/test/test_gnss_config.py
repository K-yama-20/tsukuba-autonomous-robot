"""Unit tests of gnss_config (ND-19 settings) without ROS. Design: ND-19, IFD-47..49, PRM-65 (REV-061, DEC-123).

Checked: the driver parameters replace ONLY the Gouda keys of the upstream template (saved copy in
design/research/upstream_sensors/septentrio_gnss_driver_1.4.8/gnss.yaml) and keep every other value; an unresolved connection
(PRM-65) stops the generation instead of being filled in; a connection that is neither tcp nor serial is refused; the private
RTK file replaces only rtk_settings and its absence means no corrections; the receiver is found by the interface whose prefix
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

    def test_private_rtk_file(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 'run', 'p.yaml')
            r = gc.write_parameter_file(str(TEMPLATE), DECIDED, out, d)
            self.assertIn('not found', r['rtk'])
            rtk = {'ntrip_1': {'id': 'NTR1', 'caster': 'caster.example', 'caster_port': 2101, 'username': 'u', 'password': 'secret', 'mountpoint': 'M'}}
            with open(os.path.join(d, gc.RTK_FILE), 'w') as f: yaml.safe_dump({'rtk_settings': rtk}, f)
            r = gc.write_parameter_file(str(TEMPLATE), DECIDED, out, d)
            self.assertIn('rtk_settings from', r['rtk']); self.assertNotIn('secret', json.dumps(r))
            with open(out) as f: doc = yaml.safe_load(f)
            self.assertEqual(doc['/**']['ros__parameters']['rtk_settings'], rtk)
            self.assertEqual(os.stat(out).st_mode & 0o077, 0, 'the parameter file may hold the account: owner only')
            with open(os.path.join(d, gc.RTK_FILE), 'w') as f: f.write('rtk_settings: [1, 2]\n')
            r = gc.write_parameter_file(str(TEMPLATE), DECIDED, out, d)
            self.assertIn('no rtk_settings mapping', r['rtk'])

    def test_peer_interface(self):
        links = [{'ifname': 'lo', 'ifindex': 1, 'addr_info': [{'local': '127.0.0.1', 'prefixlen': 8}]},
                 {'ifname': 'enp0s5', 'ifindex': 2, 'addr_info': [{'local': '10.0.0.5', 'prefixlen': 24}]},
                 {'ifname': 'usb0', 'ifindex': 9, 'addr_info': [{'local': '192.0.2.2', 'prefixlen': 24}]}]
        self.assertEqual(gc.peer_interface('192.0.2.1', json.dumps(links)), 'usb0 #9')
        self.assertIsNone(gc.peer_interface('198.51.100.1', json.dumps(links)))
        self.assertIsNone(gc.peer_interface('192.0.2.1', 'not json'))


if __name__ == '__main__':
    unittest.main()
