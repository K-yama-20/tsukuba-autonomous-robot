"""Unit tests of the P4 tools without ROS (run on a PC without ROS):
- make_config.py with the repository's copy of the upstream template (livox_ros_driver2 2144554, addresses removed) and a mid360.json
  with documentation-range addresses (RFC 5737 TEST-NET-1), generated at run time: no address is written in the repository;
- run_driver.py and record_bag.py: the commands they build (--dry-run), and record_bag's stop (one SIGINT, then waiting) with a
  stand-in process instead of ros2 bag record.
    python3 -m unittest discover -s <this folder> -p 'test_*.py'
"""
from __future__ import annotations

import importlib.util
import ipaddress
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p4_common  # noqa: E402
import make_config  # noqa: E402
import record_bag  # noqa: E402
import run_driver  # noqa: E402

m3 = p4_common.import_mid360_config()
REPO = p4_common.REPO
TEMPLATE = REPO / 'design/research/upstream_sensors/livox_ros_driver2_2144554/MID360_config.addresses_removed.json'
DOC_NET = ipaddress.IPv4Network((0xC0000200, 24))   # TEST-NET-1 (documentation only)
HOST, LIDAR = str(DOC_NET[11]), str(DOC_NET[13])
DOC_V6 = str(ipaddress.IPv6Network((0x20010DB8 << 96, 32))[1])   # RFC 3849 documentation range
IPV4 = re.compile(r'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])')
ADDRESS_PATHS = ['MID360.host_net_info.cmd_data_ip', 'MID360.host_net_info.push_msg_ip', 'MID360.host_net_info.point_data_ip',
                 'MID360.host_net_info.imu_data_ip', 'lidar_configs[0].ip']
MOUNT = {'mid360_mount_x_m': 0.4, 'mid360_mount_y_m': 0.0, 'mid360_mount_z_m': 0.3, 'mid360_mount_roll_rad': 0.0,
         'mid360_mount_pitch_rad': 0.5, 'mid360_mount_yaw_rad': 0.0, 'mid360_axis_mapping': '+x forward, +y left, +z up'}


def script(name: str, *args: str) -> subprocess.CompletedProcess:
    """The tool as a person runs it, isolated (-I: no PYTHONPATH, so gouda_core can only come from this checkout)."""
    return subprocess.run([sys.executable, '-I', str(HERE / name), *args], capture_output=True, text=True)


class MakeConfigTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.local = self.tmp / 'config' / 'mid360.json'
        self.local.parent.mkdir()
        self.out = self.tmp / 'p4' / 'MID360_config.json'
        with open(TEMPLATE, encoding='utf-8') as f:
            self.template = json.load(f)

    def tearDown(self):
        self._tmp.cleanup()

    def write_local(self, doc: dict, path: Path = None):
        (path or self.local).write_text(json.dumps(doc), encoding='utf-8')

    def make(self, *extra: str) -> subprocess.CompletedProcess:
        return script('make_config.py', '--mid360-json', str(self.local), '--out', str(self.out), '--template', str(TEMPLATE), *extra)

    def test_template_copy_has_the_shape_the_product_expects(self):
        self.assertEqual(self.template['lidar_summary_info'], {'lidar_type': 8})
        self.assertEqual(len(self.template['lidar_configs']), 1)
        for k in m3.HOST_IP_KEYS:
            self.assertIn(k, self.template['MID360']['host_net_info'])

    def test_complete_file_gives_the_template_with_only_the_addresses(self):
        self.write_local({'host_ip': HOST, 'lidar_ip': LIDAR, **MOUNT})
        r = self.make()
        self.assertEqual(r.returncode, 0, r.stderr)
        written = json.loads(self.out.read_text(encoding='utf-8'))
        host = written['MID360']['host_net_info']
        for k in m3.HOST_IP_KEYS:
            self.assertEqual(host[k], HOST)
        self.assertEqual(host['log_data_ip'], '')                          # stays as upstream (the product does not set it)
        self.assertEqual(written['lidar_configs'][0]['ip'], LIDAR)
        # the product's own function gives the same document (made, not copied)
        self.assertEqual(written, m3.driver_config(self.template, HOST, LIDAR))
        # everything else is the template, value and JSON type (the driver reads x, y, z with GetInt: they must stay integers)
        self.assertEqual(make_config.changed_paths(self.template, written), ADDRESS_PATHS)
        ext = written['lidar_configs'][0]['extrinsic_parameter']
        self.assertEqual(ext, {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0, 'x': 0, 'y': 0, 'z': 0})
        self.assertEqual({k: type(v) for k, v in ext.items()},
                         {'roll': float, 'pitch': float, 'yaw': float, 'x': int, 'y': int, 'z': int})
        self.assertIn('changed from the template: ' + ', '.join(ADDRESS_PATHS), r.stdout)
        self.assertNotIn('note: the mounting', r.stdout)
        self.assertIsNone(IPV4.search(r.stdout + r.stderr), 'the tool must not print the addresses')

    def test_addresses_only_is_enough_for_p4(self):
        self.write_local({'host_ip': HOST, 'lidar_ip': LIDAR})
        r = self.make()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.out.is_file())
        self.assertIn('note: the mounting in mid360.json is not complete', r.stdout)
        self.assertIsNone(IPV4.search(r.stdout + r.stderr))

    def test_missing_or_bad_address_stops(self):
        for doc, key in (({'host_ip': HOST}, 'lidar_ip'), ({'host_ip': HOST, 'lidar_ip': 'not-an-address'}, 'lidar_ip'),
                         ({'host_ip': DOC_V6, 'lidar_ip': LIDAR}, 'host_ip')):
            with self.subTest(key=key, doc=sorted(doc)):
                self.write_local(doc)
                r = self.make()
                self.assertEqual(r.returncode, 2)
                self.assertIn(f'{key} is missing or not an IPv4 address', r.stderr)
                self.assertFalse(self.out.exists())

    def test_missing_file_stops(self):
        r = self.make()
        self.assertEqual(r.returncode, 2)
        self.assertIn('does not exist', r.stderr)
        self.assertFalse(self.out.exists())

    def test_other_file_name_stops(self):
        other = self.tmp / 'config' / 'mid360_p4.json'
        self.write_local({'host_ip': HOST, 'lidar_ip': LIDAR}, other)
        r = script('make_config.py', '--mid360-json', str(other), '--out', str(self.out), '--template', str(TEMPLATE))
        self.assertEqual(r.returncode, 2)
        self.assertIn('give a file named mid360.json', r.stderr)

    def test_template_with_a_nonzero_extrinsic_stops(self):
        tpl = json.loads(json.dumps(self.template))
        tpl['lidar_configs'][0]['extrinsic_parameter']['z'] = 1
        bad = self.tmp / 'MID360_config.json'
        bad.write_text(json.dumps(tpl), encoding='utf-8')
        self.write_local({'host_ip': HOST, 'lidar_ip': LIDAR})
        r = script('make_config.py', '--mid360-json', str(self.local), '--out', str(self.out), '--template', str(bad))
        self.assertEqual(r.returncode, 2)
        self.assertIn('non-zero extrinsic_parameter', r.stderr)
        self.assertFalse(self.out.exists())

    @unittest.skipIf(importlib.util.find_spec('ament_index_python') is not None, 'ROS is loaded here')
    def test_without_template_and_ros_it_says_what_to_do(self):
        self.write_local({'host_ip': HOST, 'lidar_ip': LIDAR})
        r = script('make_config.py', '--mid360-json', str(self.local), '--out', str(self.out))
        self.assertEqual(r.returncode, 2)
        self.assertIn('give --template, or source <workspace>_livox/install/setup.bash', r.stderr)

    def test_changed_paths(self):
        self.assertEqual(make_config.changed_paths({'a': {'b': 0}}, {'a': {'b': 0.0}}), ['a.b'])   # type change counts
        self.assertEqual(make_config.changed_paths({'a': 1}, {'a': 1, 'c': 2}), ['c'])
        self.assertEqual(make_config.changed_paths([1, 2], [1, 2, 3]), [''])


class RunDriverTests(unittest.TestCase):
    def test_dry_run_prints_the_command_and_starts_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(os.path.realpath(d), 'MID360_config.json')   # need not exist for --dry-run
            r = script('run_driver.py', '--config', cfg, '--dry-run')
        self.assertEqual(r.returncode, 0, r.stderr)
        expected = ('ros2 run livox_ros_driver2 livox_ros_driver2_node --ros-args -r __node:=livox_ros_driver2 '
                    f'-p xfer_format:=0 -p frame_id:=mid360_link -p user_config_path:={cfg}')
        self.assertEqual(r.stdout.splitlines()[0], 'command: ' + expected)
        self.assertIn('/livox/lidar (sensor_msgs/msg/PointCloud2, frame_id mid360_link)', r.stdout)
        self.assertIn('/livox/imu (sensor_msgs/msg/Imu, frame_id livox_frame: fixed in the driver)', r.stdout)

    def test_parameters_and_names_are_the_products(self):
        cmd = run_driver.build_command('/x/MID360_config.json', m3)
        self.assertEqual(cmd[:5], ['ros2', 'run', m3.DRIVER_PACKAGE, m3.DRIVER_EXECUTABLE, '--ros-args'])
        self.assertEqual(cmd[5:7], ['-r', f'__node:={m3.DRIVER_NODE}'])
        params = dict(a.split(':=', 1) for a in cmd[8::2])
        self.assertEqual(cmd[7::2], ['-p'] * 3)
        self.assertEqual(params, {k: str(v) for k, v in m3.driver_parameters('/x/MID360_config.json').items()})
        self.assertEqual(params['xfer_format'], str(m3.XFER_POINTCLOUD2))
        self.assertNotIn('--remap', cmd)   # topics stay the driver's own (no -r livox/lidar:=...)
        self.assertEqual([a for a in cmd if a.startswith('livox/')], [])

    def test_relative_and_quoted_paths(self):
        cmd = run_driver.build_command('rel/MID360_config.json', m3)
        self.assertIn('user_config_path:=' + p4_common.yaml_scalar(os.path.abspath('rel/MID360_config.json')), cmd)
        cmd = run_driver.build_command('/tmp/a #b/MID360_config.json', m3)
        self.assertIn('user_config_path:="/tmp/a #b/MID360_config.json"', cmd)
        self.assertIn("'user_config_path:=\"/tmp/a #b/MID360_config.json\"'", shlex.join(cmd))


class YamlScalarTests(unittest.TestCase):
    def test_values(self):
        y = p4_common.yaml_scalar
        self.assertEqual([y(0), y(10.0), y(True), y('mid360_link'), y('/a/b-c.json')], ['0', '10.0', 'true', 'mid360_link', '/a/b-c.json'])
        self.assertEqual([y('true'), y('123'), y('a: b'), y('/x #y'), y('/自己/x.json')],
                         ['"true"', '"123"', '"a: b"', '"/x #y"', '"/自己/x.json"'])
        with self.assertRaises(TypeError):
            y(None)


class RecordBagTests(unittest.TestCase):
    def test_dry_run_prints_the_command(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(os.path.realpath(d), 't04-6')
            r = script('record_bag.py', '--out', out, '--dry-run')
            r30 = script('record_bag.py', '--out', out, '--duration', '30', '--dry-run')
            self.assertFalse(os.path.exists(out))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines()[0], f'command: ros2 bag record --disable-keyboard-controls -o {out} /livox/lidar /livox/imu')
        self.assertIn('stop: one SIGINT after 60 s', r.stdout)
        self.assertIn(f'after it ends: ros2 bag info {out}', r.stdout)
        self.assertIn('stop: one SIGINT after 30 s', r30.stdout)

    def test_duration_must_be_positive(self):
        r = script('record_bag.py', '--out', 'x', '--duration', '0', '--dry-run')
        self.assertEqual(r.returncode, 2)

    def test_stop_is_one_sigint_then_waiting(self):
        """A stand-in for ros2 bag record: counts SIGINTs, takes 0.5 s to 'close the bag' after the first, then exits 0."""
        with tempfile.TemporaryDirectory() as d:
            marker = os.path.join(d, 'count')
            child = textwrap.dedent(f'''
                import signal, sys, time
                n = []
                signal.signal(signal.SIGINT, lambda *a: n.append(1))
                while not n:
                    time.sleep(0.01)
                time.sleep(0.5)
                open({marker!r}, 'w').write(str(len(n)))
            ''')
            t0 = time.monotonic()
            rc = record_bag.record([sys.executable, '-I', '-c', child], 0.5)
            elapsed = time.monotonic() - t0
            with open(marker) as f:
                count = f.read()
        self.assertEqual(rc, 0)
        self.assertEqual(count, '1')
        self.assertGreaterEqual(elapsed, 1.0)   # it waited for the 'closing' after the signal

    def test_a_recorder_that_ends_first_is_not_signalled(self):
        rc = record_bag.record([sys.executable, '-I', '-c', 'import sys; sys.exit(3)'], 30)
        self.assertEqual(rc, 3)


class RepositoryRulesTests(unittest.TestCase):
    def test_gouda_core_comes_from_this_checkout(self):
        self.assertEqual(Path(m3.__file__).resolve(), REPO / 'gouda_core' / 'gouda_core' / 'mid360_config.py')

    def test_no_address_in_these_files(self):
        for p in sorted(HERE.iterdir()):
            if p.is_file() and p.suffix in ('.py', '.md'):
                with self.subTest(file=p.name):
                    self.assertIsNone(IPV4.search(p.read_text(encoding='utf-8')))


if __name__ == '__main__':
    unittest.main()
