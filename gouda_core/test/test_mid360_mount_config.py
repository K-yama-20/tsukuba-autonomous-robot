"""Unit tests of the MID-360 mounting in the monitor's /config (REV-266, DEC-485) without ROS.

- the seven mid360_* fields are /config fields (IFD-26) like the XT-32's, start UNKNOWN (no assumed value) and survive a reload and
  later saves of other fields (the monitor kept only its own fields, which is why REV-242 put them in mid360.json);
- base_link -> mid360_link comes only from a complete mounting in /config, never from the neutral element (DEC-457), and the
  XT-32 / IMU / GNSS transforms are unchanged;
- mid360.json (IFD-61) is read for the two addresses only; mounting keys left from REV-242 are not used, and the note says whether
  they agree with /config;
- gouda_nav2.launch.py's _mid360_ready uses the addresses from mid360.json and the mounting from /config.
The addresses are generated from the documentation range (RFC 5737) at run time; no address is written in the repository."""
import importlib.util
import ipaddress
import json
import math
import os
import re
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import mid360_config as m3  # noqa: E402
from gouda_core import sensor_extrinsics as se  # noqa: E402
from gouda_core.monitor_core import CONFIG_FIELDS, SensorConfig  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
DOC_NET = ipaddress.IPv4Network((0xC0000200, 24))   # TEST-NET-1 (documentation only)
HOST, LIDAR = str(DOC_NET[7]), str(DOC_NET[9])
IPV4 = re.compile(r'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])')
MOUNT = {'mid360_mount_x_m': 0.4, 'mid360_mount_y_m': 0.0, 'mid360_mount_z_m': 0.3, 'mid360_mount_roll_rad': 0.0,
         'mid360_mount_pitch_rad': 0.5, 'mid360_mount_yaw_rad': 0.0, 'mid360_axis_mapping': '+x forward, +y left, +z up'}


def write_json(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(doc, f)


def save_config(config_dir, changes):
    ok, msg = SensorConfig(Path(config_dir) / m3.CONFIG_FILE).update(changes, 1.0)
    assert ok, msg


class ConfigFieldTests(unittest.TestCase):
    def test_the_seven_fields_are_config_fields_without_a_default(self):
        kinds = {k: CONFIG_FIELDS.get(k) for k in m3.MOUNT_KEYS}
        self.assertEqual(kinds, {**{k: 'number' for k in m3.MOUNT_KEYS[:-1]}, m3.MOUNT_KEYS[-1]: 'axes'})
        with tempfile.TemporaryDirectory() as d:
            c = SensorConfig(Path(d) / m3.CONFIG_FILE)
            self.assertEqual({k: c.values[k] for k in m3.MOUNT_KEYS}, {k: 'UNKNOWN' for k in m3.MOUNT_KEYS})

    def test_saved_values_survive_a_reload_and_later_saves(self):
        """The REV-242 reason for mid360.json: a save kept only the monitor's own fields. Now the fields are its own."""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / m3.CONFIG_FILE
            ok, msg = SensorConfig(p).update({k: str(v) for k, v in MOUNT.items()}, 1.0)   # the browser sends text
            self.assertTrue(ok, msg)
            ok, msg = SensorConfig(p).update({'lidar_mount_z_m': '0.9'}, 2.0)              # a later save of another field
            self.assertTrue(ok, msg)
            c = SensorConfig(p)                                                            # tab change / reload / restart
            self.assertEqual({k: c.values[k] for k in m3.MOUNT_KEYS}, MOUNT)
            self.assertEqual(json.loads(p.read_text(encoding='utf-8'))['values']['mid360_mount_pitch_rad'], 0.5)
            self.assertEqual(c.config_revision, 2)

    def test_a_file_saved_before_rev266_loads_with_the_new_fields_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / m3.CONFIG_FILE
            write_json(str(p), {'values': {'lidar_mount_z_m': 0.9}, 'config_revision': 4, 'updated_at': 1.0})
            c = SensorConfig(p)
            self.assertEqual(c.values['lidar_mount_z_m'], 0.9); self.assertEqual(c.config_revision, 4)
            self.assertTrue(all(c.values[k] == 'UNKNOWN' for k in m3.MOUNT_KEYS))

    def test_a_bad_axis_mapping_is_refused_on_save(self):
        with tempfile.TemporaryDirectory() as d:
            ok, msg = SensorConfig(Path(d) / m3.CONFIG_FILE).update({'mid360_axis_mapping': '+x forward, +y up'}, 1.0)
            self.assertFalse(ok); self.assertIn('mid360_axis_mapping', msg)

    def test_a_left_handed_mapping_is_saved_with_the_mid360_warning(self):
        """As for the XT-32 the save is not refused, but the warning says what happens to the MID-360 (no TF, no path)."""
        with tempfile.TemporaryDirectory() as d:
            c = SensorConfig(Path(d) / m3.CONFIG_FILE)
            ok, msg = c.update({'mid360_axis_mapping': '+x forward, +y right, +z up'}, 1.0)
            self.assertTrue(ok, msg); self.assertIn('mid360_link is not published', msg); self.assertNotIn('base_link axes', msg)
            ok, msg = c.update({'lidar_axis_mapping': '+x forward, +y right, +z up'}, 2.0)
            self.assertTrue(ok, msg); self.assertIn('base_link axes are used', msg)


class MountFromConfigTests(unittest.TestCase):
    def test_complete_mounting_gives_the_transform(self):
        t, why = m3.mount_from_config(dict(MOUNT))
        self.assertEqual(why, '')
        self.assertEqual((t['parent'], t['child']), ('base_link', 'mid360_link'))
        self.assertEqual(tuple(t['translation']), (0.4, 0.0, 0.3))
        qx, qy, qz, qw = t['rotation']   # pitch 0.5 rad about y
        self.assertAlmostEqual(qy, math.sin(0.25)); self.assertAlmostEqual(qw, math.cos(0.25)); self.assertAlmostEqual(qx, 0); self.assertAlmostEqual(qz, 0)
        self.assertEqual(t, m3.mount_transform(dict(MOUNT)))

    def test_no_neutral_element(self):
        """DEC-457: an UNKNOWN field is never replaced by 0 / no rotation (the XT-32 rule of DEC-122 does not apply)."""
        t, why = m3.mount_from_config({k: 'UNKNOWN' for k in CONFIG_FIELDS})
        self.assertIsNone(t)
        for k in m3.MOUNT_KEYS:
            self.assertIn(k, why)
        for key in m3.MOUNT_KEYS:
            t, why = m3.mount_from_config(dict(MOUNT, **{key: 'UNKNOWN'}))
            self.assertIsNone(t, key); self.assertIn(key, why)
        for bad in ({'mid360_mount_z_m': float('nan')}, {'mid360_mount_x_m': True},
                    {'mid360_axis_mapping': '+x forward, +y right, +z up'},   # left-handed
                    {'mid360_axis_mapping': 'sideways'}):
            t, why = m3.mount_from_config(dict(MOUNT, **bad))
            self.assertIsNone(t, bad); self.assertIn(next(iter(bad)), why)

    def test_other_static_transforms_are_unchanged(self):
        """sensor_extrinsics.static_transforms (XT-32, IMU, GNSS; neutral when UNKNOWN) does not take the MID-360 in."""
        r = se.static_transforms(dict(MOUNT), 0.165)
        self.assertNotIn('mid360_link', [t['child'] for t in r['transforms']])
        self.assertFalse([k for k in r['defaulted_fields'] if k.startswith('mid360_')])


class LocalFileTests(unittest.TestCase):
    def test_addresses_only(self):
        with tempfile.TemporaryDirectory() as d:
            write_json(os.path.join(d, m3.LOCAL_FILE), {'host_ip': HOST, 'lidar_ip': LIDAR})
            a = m3.read_addresses(d)
            self.assertEqual(a['problems'], []); self.assertEqual(a['legacy_mount_keys'], [])
            self.assertEqual(a['values'], {'host_ip': HOST, 'lidar_ip': LIDAR})
            write_json(os.path.join(d, m3.LOCAL_FILE), {'host_ip': HOST})
            a = m3.read_addresses(d)
            self.assertEqual(len(a['problems']), 1); self.assertIn('lidar_ip', a['problems'][0])
        with tempfile.TemporaryDirectory() as d:
            self.assertIn('does not exist', m3.read_addresses(d)['problems'][0])
        self.assertTrue(m3.read_addresses(None)['problems'])

    def test_rev242_file_gives_the_addresses_and_lists_the_mounting_keys(self):
        with tempfile.TemporaryDirectory() as d:
            write_json(os.path.join(d, m3.LOCAL_FILE), dict(MOUNT, host_ip=HOST, lidar_ip=LIDAR))
            a = m3.read_addresses(d)
            self.assertEqual(a['problems'], []); self.assertEqual(a['legacy_mount_keys'], list(m3.MOUNT_KEYS))

    def test_the_driver_config_from_read_addresses(self):
        tpl = {'MID360': {'host_net_info': {k: '' for k in m3.HOST_IP_KEYS}},
               'lidar_configs': [{'ip': '', 'extrinsic_parameter': {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0, 'x': 0, 'y': 0, 'z': 0}}]}
        with tempfile.TemporaryDirectory() as d:
            write_json(os.path.join(d, m3.LOCAL_FILE), {'host_ip': HOST, 'lidar_ip': LIDAR})
            tp, out = os.path.join(d, 'tpl.json'), os.path.join(d, 'run', 'mid360', m3.TEMPLATE_NAME)
            write_json(tp, tpl)
            m3.write_driver_config(tp, m3.read_addresses(d), out)
            with open(out, encoding='utf-8') as f:
                cfg = json.load(f)
        self.assertEqual(cfg['lidar_configs'][0]['ip'], LIDAR)
        self.assertEqual({cfg['MID360']['host_net_info'][k] for k in m3.HOST_IP_KEYS}, {HOST})
        self.assertEqual(set(cfg['lidar_configs'][0]['extrinsic_parameter'].values()), {0})


class StaticTfTests(unittest.TestCase):
    """ND-13 (static_tf_node) takes the MID-360 transform and the record note from mid360_config.static_tf."""

    def test_from_config_only(self):
        with tempfile.TemporaryDirectory() as d:
            t, note = m3.static_tf(dict(MOUNT), d)
            self.assertIsNotNone(t); self.assertEqual(note, 'mid360_link published from /config')
            t, note = m3.static_tf({k: 'UNKNOWN' for k in CONFIG_FIELDS}, d)
            self.assertIsNone(t); self.assertTrue(note.startswith('mid360_link not published'))
            self.assertNotIn(m3.LOCAL_FILE, note)

    def test_rev242_mounting_left_in_mid360_json(self):
        with tempfile.TemporaryDirectory() as d:
            write_json(os.path.join(d, m3.LOCAL_FILE), dict(MOUNT, host_ip=HOST, lidar_ip=LIDAR))
            t, note = m3.static_tf({k: 'UNKNOWN' for k in CONFIG_FIELDS}, d)   # the old file alone gives no TF any more
            self.assertIsNone(t); self.assertIn('not read since REV-266', note); self.assertIn('enter the mounting', note)
            t, note = m3.static_tf(dict(MOUNT), d)
            self.assertIsNotNone(t); self.assertIn('same transform', note)
            t, note = m3.static_tf(dict(MOUNT, mid360_mount_z_m=0.31), d)   # /config is used, the difference is reported
            self.assertEqual(tuple(t['translation']), (0.4, 0.0, 0.31)); self.assertIn('DIFFERENT', note)
            write_json(os.path.join(d, m3.LOCAL_FILE), {'host_ip': HOST, 'lidar_ip': LIDAR, 'mid360_mount_x_m': 0.4})
            t, note = m3.static_tf(dict(MOUNT), d)
            self.assertIsNotNone(t); self.assertIn('mid360_mount_x_m', note); self.assertNotIn('same', note)


class LaunchInputTests(unittest.TestCase):
    def test_addresses_from_the_file_and_mounting_from_config(self):
        with tempfile.TemporaryDirectory() as d:
            write_json(os.path.join(d, m3.LOCAL_FILE), {'host_ip': HOST, 'lidar_ip': LIDAR})
            reason, addresses, note = m3.launch_inputs(d)
            self.assertIn('does not exist', reason); self.assertIn('mounting', reason)   # no /config file yet
            save_config(d, {k: MOUNT[k] for k in m3.MOUNT_KEYS[:-1]})
            reason, _, _ = m3.launch_inputs(d)
            self.assertIn('mid360_axis_mapping', reason); self.assertNotIn('mid360_mount_x_m', reason)
            save_config(d, {'mid360_axis_mapping': MOUNT['mid360_axis_mapping']})
            reason, addresses, note = m3.launch_inputs(d)
            self.assertEqual((reason, note), ('', '')); self.assertEqual(addresses['values'], {'host_ip': HOST, 'lidar_ip': LIDAR})
            os.remove(os.path.join(d, m3.LOCAL_FILE))
            reason, _, _ = m3.launch_inputs(d)
            self.assertIn(m3.LOCAL_FILE, reason); self.assertNotIn('mounting', reason)
        reason, _, _ = m3.launch_inputs(None)
        self.assertTrue(reason)

    def test_a_rev242_file_alone_no_longer_starts_the_path(self):
        with tempfile.TemporaryDirectory() as d:
            write_json(os.path.join(d, m3.LOCAL_FILE), dict(MOUNT, host_ip=HOST, lidar_ip=LIDAR))
            reason, _, note = m3.launch_inputs(d)
            self.assertIn('mounting', reason); self.assertIn('enter the mounting', note)
            save_config(d, MOUNT)
            reason, _, note = m3.launch_inputs(d)
            self.assertEqual(reason, ''); self.assertIn('same transform', note)


def load_launch(share_dir):
    """gouda_nav2.launch.py with stand-ins for the ROS launch modules (only _mid360_ready is called)."""
    class PackageNotFoundError(Exception):
        pass

    def share(name):
        if name == m3.DRIVER_PACKAGE and share_dir:
            return share_dir
        raise PackageNotFoundError(name)

    def mod(name, **attrs):
        m = types.ModuleType(name); m.__dict__.update(attrs); return m
    stub = object
    mods = {'launch': mod('launch', LaunchDescription=stub), 'launch.actions': mod('launch.actions', DeclareLaunchArgument=stub, OpaqueFunction=stub, LogInfo=stub),
            'launch.substitutions': mod('launch.substitutions', LaunchConfiguration=stub), 'launch_ros': mod('launch_ros'),
            'launch_ros.actions': mod('launch_ros.actions', Node=stub), 'ament_index_python': mod('ament_index_python'),
            'ament_index_python.packages': mod('ament_index_python.packages', get_package_share_directory=share, PackageNotFoundError=PackageNotFoundError)}
    with mock.patch.dict(sys.modules, mods):
        spec = importlib.util.spec_from_file_location('gouda_nav2_launch_under_test', REPO / 'gouda_core' / 'launch' / 'gouda_nav2.launch.py')
        launch = importlib.util.module_from_spec(spec); spec.loader.exec_module(launch)
    return launch, mods


class LaunchTests(unittest.TestCase):
    def test_mid360_ready(self):
        tpl = {'MID360': {'host_net_info': {k: '' for k in m3.HOST_IP_KEYS}},
               'lidar_configs': [{'ip': '', 'extrinsic_parameter': {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0, 'x': 0, 'y': 0, 'z': 0}}]}
        with tempfile.TemporaryDirectory() as d:
            cfg, run, share = os.path.join(d, 'config'), os.path.join(d, 'run'), os.path.join(d, 'share')
            write_json(os.path.join(share, 'config', m3.TEMPLATE_NAME), tpl)
            write_json(os.path.join(cfg, m3.LOCAL_FILE), {'host_ip': HOST, 'lidar_ip': LIDAR})
            launch, mods = load_launch(share)
            with mock.patch.dict(sys.modules, mods):
                reason, path, note = launch._mid360_ready(cfg, run)
                self.assertIn('mounting', reason); self.assertIsNone(path); self.assertEqual(note, '')
                save_config(cfg, MOUNT)
                reason, path, note = launch._mid360_ready(cfg, run)
                self.assertEqual((reason, note), ('', ''))
                self.assertEqual(path, os.path.join(run, 'mid360', m3.TEMPLATE_NAME))
                with open(path, encoding='utf-8') as f:
                    self.assertEqual(json.load(f)['lidar_configs'][0]['ip'], LIDAR)
            launch, mods = load_launch(None)
            with mock.patch.dict(sys.modules, mods):
                reason, path, _ = launch._mid360_ready(cfg, run)
                self.assertIn('not installed', reason); self.assertIsNone(path)


class NoAddressTests(unittest.TestCase):
    def test_no_address_in_the_changed_files(self):
        files = [REPO / 'gouda_core' / 'gouda_core' / n for n in ('mid360_config.py', 'static_tf_node.py', 'monitor_core.py')]
        files += [REPO / 'gouda_core' / 'launch' / 'gouda_nav2.launch.py', REPO / 'gouda_core' / 'web' / 'app.js',
                  REPO / 'gouda_core' / 'web' / 'index.html', Path(__file__)]
        for f in files:
            self.assertEqual(IPV4.findall(f.read_text(encoding='utf-8')), [], str(f))


if __name__ == '__main__':
    unittest.main()
