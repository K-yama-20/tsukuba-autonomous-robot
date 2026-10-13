"""Unit tests of sensor_config (ND-14 / ND-15 settings) without ROS. Design: PRM-50..56, IFD-21 / IFD-22 (REV-030, REV-031).

Checked: the Hesai driver config replaces ONLY the Gouda keys of the upstream template (saved copy in
design/research/upstream_sensors/hesai_ros2_e7e112f/config.yaml) and keeps every other value; a missing value (PTC port, PRM-53,
unresolved) stops the generation instead of being filled in; the trial file is read only when asked; the IMU parameters carry the
by-id device, frame imu_link, publish_tf=false, and are refused without a declared rate (no silent driver default)."""
import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import sensor_config as sc  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
PARAMS = str(REPO / 'design' / 'generated' / 'params')
TEMPLATE = REPO / 'design' / 'research' / 'upstream_sensors' / 'hesai_ros2_e7e112f' / 'hesai_config.yaml'


def flatten(d, prefix=''):
    out = {}
    if isinstance(d, dict):
        for k, v in d.items(): out.update(flatten(v, f'{prefix}.{k}' if prefix else str(k)))
    elif isinstance(d, list):
        for i, v in enumerate(d): out.update(flatten(v, f'{prefix}[{i}]'))
    else:
        out[prefix] = d
    return out


class HesaiConfigTests(unittest.TestCase):
    def setUp(self):
        self.template = yaml.safe_load(TEMPLATE.read_text(encoding='utf-8'))

    def test_vehicle_params_without_ptc_port_are_refused(self):
        params = sc.read_node_params(PARAMS, 'hesai_ros_driver', trial=False)
        self.assertEqual(params['device_ip_address'], '192.168.1.201'); self.assertEqual(params['host_ip_address'], '192.168.1.100')
        self.assertEqual(params['udp_port'], 2368); self.assertEqual(params['use_timestamp_type'], 1)
        _, missing = sc.hesai_config(self.template, params)
        self.assertEqual(missing, ['ptc_port'], 'PRM-53 is unresolved (DEC-084): never filled in')
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 'cfg.yaml')
            self.assertEqual(sc.write_hesai_config(str(TEMPLATE), params, out), ['ptc_port']); self.assertFalse(os.path.exists(out))

    def test_only_gouda_keys_change(self):
        params = sc.read_node_params(PARAMS, 'hesai_ros_driver', trial=True)
        before = copy.deepcopy(self.template)
        cfg, missing = sc.hesai_config(self.template, params)
        self.assertEqual(missing, []); self.assertEqual(self.template, before, 'template not modified')
        a, b = flatten(before), flatten(cfg)
        changed = {k for k in a if a[k] != b.get(k)}
        allowed = {'lidar[0].driver.source_type', 'lidar[0].driver.use_timestamp_type', 'lidar[0].ros.ros_frame_id', 'lidar[0].ros.ros_send_point_cloud_topic'} | \
                  {f'lidar[0].driver.lidar_udp_type.{k}' for k in ('device_ip_address', 'host_ip_address', 'udp_port', 'ptc_port')}
        self.assertTrue(changed <= allowed, changed - allowed); self.assertEqual(set(a), set(b), 'no key added or removed')
        drv = cfg['lidar'][0]['driver']; udp = drv['lidar_udp_type']; ros = cfg['lidar'][0]['ros']
        self.assertEqual(drv['source_type'], sc.HESAI_SOURCE_REALTIME); self.assertEqual(drv['use_timestamp_type'], 1)
        self.assertEqual((udp['device_ip_address'], udp['host_ip_address'], udp['udp_port']), ('192.168.1.201', '192.168.1.100', 2368))
        self.assertEqual(ros['ros_frame_id'], 'xt32_link'); self.assertEqual(ros['ros_send_point_cloud_topic'], 'sensors/xt32/points')

    def test_written_file_roundtrips(self):
        params = sc.read_node_params(PARAMS, 'hesai_ros_driver', trial=True)
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 'run', 'cfg.yaml')
            self.assertEqual(sc.write_hesai_config(str(TEMPLATE), params, out), [])
            with open(out) as f:
                self.assertEqual(yaml.safe_load(f), sc.hesai_config(self.template, params)[0])


class ImuParameterTests(unittest.TestCase):
    def test_vehicle_params_without_rate_are_refused(self):
        p, missing = sc.imu_parameters(sc.read_node_params(PARAMS, 'adi_imu_driver', trial=False))
        self.assertEqual(missing, ['rate'], 'PRM-56 is unresolved (DEC-085): the driver default must not be used silently')
        import json   # expected value = the model's PRM-54 (generated index), not a copy typed into the test
        prm54 = next(x for x in json.load(open(os.path.join(PARAMS, 'index.json')))['parameters'] if x['id'] == 'PRM-54')
        self.assertEqual(p['device'], prm54['value']); self.assertTrue(p['device'].startswith('/dev/serial/by-id/'))
        self.assertNotIn('tty', p['device'].rsplit('/', 1)[-1].lower().replace('virtual', ''), 'by-id name only (DEC-081)')

    def test_trial_params(self):
        p, missing = sc.imu_parameters(sc.read_node_params(PARAMS, 'adi_imu_driver', trial=True))
        self.assertEqual(missing, []); self.assertIsInstance(p['rate'], float)
        self.assertEqual(p['frame_id'], 'imu_link'); self.assertIs(p['publish_tf'], False, 'TF has a single owner (ND-13, RQ-I004)')


if __name__ == '__main__':
    unittest.main()
