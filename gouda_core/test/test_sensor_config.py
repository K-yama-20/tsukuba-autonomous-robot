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
def model_values():
    """PRM id -> value from the generated index (the model), so the tests never copy a value by hand."""
    import json
    with open(os.path.join(PARAMS, 'index.json'), encoding='utf-8') as f:
        return {x['id']: x['value'] for x in json.load(f)['parameters']}


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

    def test_vehicle_params_are_complete(self):
        """Without trial values the driver config is complete (DEC-091) and equals the model (generated index)."""
        params = sc.read_node_params(PARAMS, 'hesai_ros_driver', trial=False)
        idx = model_values()
        for k, prm in (('device_ip_address', 'PRM-50'), ('host_ip_address', 'PRM-51'), ('udp_port', 'PRM-52'), ('ptc_port', 'PRM-53'), ('use_timestamp_type', 'PRM-55'), ('spin_rate_rpm', 'PRM-60')):
            self.assertEqual(params[k], idx[prm], k)
        cfg, missing = sc.hesai_config(self.template, params)
        self.assertEqual(missing, [])
        drv = cfg['lidar'][0]['driver']
        self.assertEqual(drv['lidar_udp_type']['speed'], idx['PRM-60']); self.assertEqual(drv['default_frame_frequency'], idx['PRM-60'] / 60)

    def test_missing_value_is_refused(self):
        params = sc.read_node_params(PARAMS, 'hesai_ros_driver', trial=False); params.pop('ptc_port')
        _, missing = sc.hesai_config(self.template, params)
        self.assertEqual(missing, ['ptc_port'], 'a missing value is never filled in')
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
        allowed = {'lidar[0].driver.source_type', 'lidar[0].driver.use_timestamp_type', 'lidar[0].driver.default_frame_frequency', 'lidar[0].ros.ros_frame_id', 'lidar[0].ros.ros_send_point_cloud_topic',
                   'lidar[0].ros.ros_send_packet_loss_topic'} | \
                  {f'lidar[0].driver.lidar_udp_type.{k}' for k in ('device_ip_address', 'host_ip_address', 'udp_port', 'ptc_port', 'multicast_ip_address', 'speed')}
        self.assertTrue(changed <= allowed, changed - allowed); self.assertEqual(set(a), set(b), 'no key added or removed')
        drv = cfg['lidar'][0]['driver']; udp = drv['lidar_udp_type']; ros = cfg['lidar'][0]['ros']
        self.assertEqual(drv['source_type'], sc.HESAI_SOURCE_REALTIME); self.assertEqual(drv['use_timestamp_type'], 1)
        self.assertEqual((udp['device_ip_address'], udp['host_ip_address'], udp['udp_port']), ('192.168.1.201', '192.168.1.100', 2368))
        self.assertEqual(udp['multicast_ip_address'], '')
        self.assertEqual(ros['ros_frame_id'], 'xt32_link'); self.assertEqual(ros['ros_send_point_cloud_topic'], 'sensors/xt32/points')
        self.assertEqual(ros['ros_send_packet_loss_topic'], 'sensors/xt32/packet_loss')   # IFD-56 (DEC-281)

    def test_written_file_roundtrips(self):
        params = sc.read_node_params(PARAMS, 'hesai_ros_driver', trial=True)
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 'run', 'cfg.yaml')
            self.assertEqual(sc.write_hesai_config(str(TEMPLATE), params, out), [])
            with open(out) as f:
                self.assertEqual(yaml.safe_load(f), sc.hesai_config(self.template, params)[0])


class ImuParameterTests(unittest.TestCase):
    def test_vehicle_params_are_complete(self):
        p, missing = sc.imu_parameters(sc.read_node_params(PARAMS, 'adi_imu_driver', trial=False))
        idx = model_values()
        self.assertEqual(missing, []); self.assertEqual(p['device'], idx['PRM-54']); self.assertEqual(p['rate'], idx['PRM-56'])
        self.assertTrue(p['device'].startswith('/dev/serial/by-id/'), 'by-id name only (DEC-081)')

    def test_missing_rate_is_refused(self):
        params = sc.read_node_params(PARAMS, 'adi_imu_driver', trial=False); params.pop('rate')
        p, missing = sc.imu_parameters(params)
        self.assertEqual(missing, ['rate'], 'the driver default must not be used silently'); self.assertNotIn('rate', p)

    def test_trial_params(self):
        p, missing = sc.imu_parameters(sc.read_node_params(PARAMS, 'adi_imu_driver', trial=True))
        self.assertEqual(missing, []); self.assertIsInstance(p['rate'], float)
        self.assertEqual(p['frame_id'], 'imu_link'); self.assertIs(p['publish_tf'], False, 'TF has a single owner (ND-13, RQ-I004)')


if __name__ == '__main__':
    unittest.main()
