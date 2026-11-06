"""Unit tests of mid360_config (REV-242, DEC-454) without ROS: the vehicle PC's mid360.json (IFD-61), the driver config built from the
upstream template's shape with only the addresses replaced, and the base_link -> mid360_link transform (only from a complete mounting).
The addresses used here are generated from the documentation range (RFC 5737) at run time; no address is written in the repository."""
import ipaddress
import json
import math
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import mid360_config as m3  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
DOC_NET = ipaddress.IPv4Network((0xC0000200, 24))   # TEST-NET-1 (documentation only)
HOST, LIDAR = str(DOC_NET[7]), str(DOC_NET[9])
IPV4 = re.compile(r'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])')


def template():
    """The shape of the upstream MID360_config.json (livox_ros_driver2 2144554): the keys the driver reads, values blank."""
    host = {k: '' for k in m3.HOST_IP_KEYS}
    host.update({'cmd_data_port': 1, 'push_msg_port': 2, 'point_data_port': 3, 'imu_data_port': 4, 'log_data_ip': '', 'log_data_port': 5})
    return {'lidar_summary_info': {'lidar_type': 8}, 'MID360': {'lidar_net_info': {'cmd_data_port': 6}, 'host_net_info': host},
            'lidar_configs': [{'ip': '', 'pcl_data_type': 1, 'pattern_mode': 0,
                               'extrinsic_parameter': {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0, 'x': 0, 'y': 0, 'z': 0}}]}


def local(**over):
    v = {'host_ip': HOST, 'lidar_ip': LIDAR, 'mid360_mount_x_m': 0.4, 'mid360_mount_y_m': 0.0, 'mid360_mount_z_m': 0.3,
         'mid360_mount_roll_rad': 0.0, 'mid360_mount_pitch_rad': 0.5, 'mid360_mount_yaw_rad': 0.0,
         'mid360_axis_mapping': '+x forward, +y left, +z up'}
    v.update(over)
    return {k: x for k, x in v.items() if x is not None}


class Mid360ConfigTests(unittest.TestCase):
    def write_local(self, d, values):
        with open(os.path.join(d, m3.LOCAL_FILE), 'w') as f:
            json.dump(values, f)

    def test_no_file_no_values(self):
        with tempfile.TemporaryDirectory() as d:
            r = m3.read_local(d)
            self.assertTrue(r['problems']); self.assertIn('does not exist', r['problems'][0])
            t, why = m3.mount_from_file(d)
            self.assertIsNone(t); self.assertIn('does not exist', why)
        self.assertTrue(m3.read_local(None)['problems'])

    def test_every_key_is_required(self):
        """A missing or invalid value is reported, never filled in (no neutral pose, no default address)."""
        for key in m3.ADDRESS_KEYS + m3.MOUNT_KEYS:
            with tempfile.TemporaryDirectory() as d:
                self.write_local(d, local(**{key: None}))
                r = m3.read_local(d)
                self.assertEqual(len(r['problems']), 1, key); self.assertIn(key, r['problems'][0])
                t, _ = m3.mount_from_file(d)
                if key in m3.MOUNT_KEYS:
                    self.assertIsNone(t, key)
                else:
                    self.assertIsNotNone(t, f'{key}: the mounting is complete, the TF does not need the addresses')
        for bad in ({'host_ip': 'pc'}, {'lidar_ip': 7}, {'mid360_mount_z_m': 'x'}, {'mid360_mount_pitch_rad': float('nan')},
                    {'mid360_mount_x_m': True}, {'mid360_axis_mapping': '+x forward, +y right, +z up'}):   # the last one is left-handed
            with tempfile.TemporaryDirectory() as d:
                self.write_local(d, local(**bad))
                self.assertTrue(m3.read_local(d)['problems'], bad)

    def test_mount_transform(self):
        with tempfile.TemporaryDirectory() as d:
            self.write_local(d, local())
            self.assertEqual(m3.read_local(d)['problems'], [])
            t, why = m3.mount_from_file(d)
            self.assertEqual(why, '')
            self.assertEqual((t['parent'], t['child']), ('base_link', 'mid360_link'))
            self.assertEqual(tuple(t['translation']), (0.4, 0.0, 0.3))
            qx, qy, qz, qw = t['rotation']   # pitch 0.5 rad about y (REP-103: positive pitch turns x down)
            self.assertAlmostEqual(qy, math.sin(0.25)); self.assertAlmostEqual(qw, math.cos(0.25)); self.assertAlmostEqual(qx, 0); self.assertAlmostEqual(qz, 0)

    def test_driver_config_from_the_local_values(self):
        """(c) only the addresses of the template change, from the vehicle PC's file; the extrinsic stays zero (TF owner ND-13)."""
        tpl = template()
        with tempfile.TemporaryDirectory() as d:
            self.write_local(d, local())
            tp = os.path.join(d, 'tpl.json')
            with open(tp, 'w') as f: json.dump(tpl, f)
            out = os.path.join(d, 'run', 'mid360', m3.TEMPLATE_NAME)
            m3.write_driver_config(tp, m3.read_local(d), out)
            with open(out) as f: cfg = json.load(f)
        host = cfg['MID360']['host_net_info']
        for k in m3.HOST_IP_KEYS: self.assertEqual(host[k], HOST)
        self.assertEqual(host['log_data_ip'], '')
        self.assertEqual(cfg['lidar_configs'][0]['ip'], LIDAR)
        exp = template()
        for k in m3.HOST_IP_KEYS: exp['MID360']['host_net_info'][k] = HOST
        exp['lidar_configs'][0]['ip'] = LIDAR
        self.assertEqual(cfg, exp, 'nothing else of the template changes')
        self.assertEqual(tpl, template(), 'the template is not modified')
        bad = template(); bad['lidar_configs'][0]['extrinsic_parameter']['x'] = 1
        with self.assertRaises(ValueError): m3.driver_config(bad, HOST, LIDAR)
        with self.assertRaises(ValueError): m3.driver_config({'MID360': {}}, HOST, LIDAR)

    def test_driver_parameters(self):
        p = m3.driver_parameters('/x/MID360_config.json')
        self.assertEqual(p, {'xfer_format': 0, 'frame_id': 'mid360_link', 'user_config_path': '/x/MID360_config.json'})

    def test_no_address_in_the_repository_files(self):
        """(c) the MID-360 code, the Nav2 launch and the generated Nav2 values hold no IPv4 address."""
        files = [REPO / 'gouda_core' / 'gouda_core' / n for n in ('mid360_config.py', 'nav2_config.py', 'static_tf_node.py')]
        files += [REPO / 'gouda_core' / 'launch' / 'gouda_nav2.launch.py', REPO / 'design' / 'generated' / 'params' / 'gouda_nav2.yaml']
        for f in files:
            self.assertEqual(IPV4.findall(f.read_text(encoding='utf-8')), [], str(f))


if __name__ == '__main__':
    unittest.main()
