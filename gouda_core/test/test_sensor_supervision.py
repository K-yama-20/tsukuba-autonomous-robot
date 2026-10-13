"""Unit tests of DEC-088 (TS-31, TS-32 software part), without ROS.

TS-32: device identity by NAME (by-id / interface holding the PC address) and the restart rule: a driver is created when its
device appears and re-created ONLY when the device is re-enumerated (new USB device number / new ifindex); the same identity
never causes a restart; a device that disappears has its driver stopped. Sysfs and `ip -j addr` are faked in a temp dir.
TS-31: the monitor's reception status per sensor and the mapping-start warning (never-received always warned; STALE only with
a declared threshold, PRM-57 / PRM-58)."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import device_watch as dw  # noqa: E402
from gouda_core.monitor_core import MonitorCore  # noqa: E402

BY_ID = 'usb-STMicroelectronics_STM32_Virtual_ComPort_007137944B34-if00'


class FakeSys:
    """A /dev/serial/by-id symlink and the sysfs chain tty -> USB interface -> USB device (busnum, devnum)."""

    def __init__(self, root):
        self.root = Path(root); (self.root / 'dev' / 'serial' / 'by-id').mkdir(parents=True)
        self.by_id = str(self.root / 'dev' / 'serial' / 'by-id' / BY_ID)

    def plug(self, tty, bus, devnum):
        dev = self.root / 'dev' / tty; dev.write_text('')
        usb = self.root / 'sys' / 'devices' / f'usb{bus}' / f'{bus}-2.2-{devnum}'; iface = usb / f'{bus}-2.2:1.0'; iface.mkdir(parents=True, exist_ok=True)
        (usb / 'busnum').write_text(f'{bus}\n'); (usb / 'devnum').write_text(f'{devnum}\n')
        cls = self.root / 'sys' / 'class' / 'tty' / tty; cls.mkdir(parents=True, exist_ok=True)
        if (cls / 'device').is_symlink(): (cls / 'device').unlink()
        os.symlink(iface, cls / 'device')
        if os.path.lexists(self.by_id): os.unlink(self.by_id)
        os.symlink(dev, self.by_id)

    def unplug(self):
        if os.path.lexists(self.by_id): os.unlink(self.by_id)

    def identity(self):
        return dw.tty_identity(self.by_id, str(self.root / 'sys'))


def ip_json(entries):
    return json.dumps([{'ifindex': i, 'ifname': n, 'addr_info': [{'family': 'inet', 'local': a}] if a else []} for n, i, a in entries])


class DeviceIdentityTests(unittest.TestCase):
    def test_tty_identity_follows_the_name_and_the_enumeration(self):
        with tempfile.TemporaryDirectory() as d:
            fs = FakeSys(d)
            self.assertIsNone(fs.identity(), 'absent')
            fs.plug('ttyACM0', 2, 3); a = fs.identity(); self.assertEqual(a, 'ttyACM0 usb 2-3')
            fs.unplug(); self.assertIsNone(fs.identity())
            fs.plug('ttyACM0', 2, 5); b = fs.identity()   # same tty number, new USB device number: a new enumeration
            self.assertNotEqual(a, b)
            fs.plug('ttyACM1', 2, 25); self.assertEqual(fs.identity(), 'ttyACM1 usb 2-25')

    def test_net_identity_is_the_interface_holding_the_pc_address(self):
        self.assertIsNone(dw.net_identity('192.168.1.100', ip_json([('lo', 1, '127.0.0.1'), ('enp0s5', 2, '10.211.55.4')])))
        self.assertEqual(dw.net_identity('192.168.1.100', ip_json([('enp0s5', 2, '10.211.55.4'), ('enx6c6e0754b24a', 6, '192.168.1.100')])), 'enx6c6e0754b24a #6')
        self.assertIsNone(dw.net_identity('192.168.1.100', 'not json'))


class RestartRuleTests(unittest.TestCase):
    def run_sequence(self, observations):
        dev = dw.WatchedDevice('imu'); actions = []
        for o in observations:
            a = dev.decide(o); dev.apply(o, a); actions.append(a)
        return actions

    def test_restart_only_on_reconnect(self):
        acts = self.run_sequence([None, 'ttyACM0 usb 2-3', 'ttyACM0 usb 2-3', 'ttyACM0 usb 2-3', 'ttyACM1 usb 2-25', 'ttyACM1 usb 2-25'])
        self.assertEqual(acts, [dw.ACTION_NONE, dw.ACTION_START, dw.ACTION_NONE, dw.ACTION_NONE, dw.ACTION_RESTART, dw.ACTION_NONE])

    def test_disappear_then_reappear(self):
        acts = self.run_sequence(['ttyACM0 usb 2-3', None, None, 'ttyACM0 usb 2-7'])
        self.assertEqual(acts, [dw.ACTION_START, dw.ACTION_STOP, dw.ACTION_NONE, dw.ACTION_START])

    def test_same_identity_never_restarts_even_if_evaluated_often(self):
        dev = dw.WatchedDevice('imu'); dev.apply('x', dev.decide('x'))
        self.assertEqual({dev.decide('x') for _ in range(100)}, {dw.ACTION_NONE})

    def test_absence_is_reported_at_the_first_evaluation(self):
        dev = dw.WatchedDevice('lidar')
        self.assertTrue(dev.presence_changed(None))
        dev.apply(None, dev.decide(None)); self.assertFalse(dev.presence_changed(None)); self.assertTrue(dev.presence_changed('enx #6'))

    def test_opened_identity_survives_a_session_without_driver(self):
        """A session in which the IMU driver was not started must not erase the enumeration opened earlier."""
        prev = dw.merge_opened({}, {'imu': 'ttyACM0 usb 2-29', 'lidar': 'enx #6'})
        prev = dw.merge_opened(prev, {'imu': None, 'lidar': None})
        self.assertEqual(prev, {'imu': 'ttyACM0 usb 2-29', 'lidar': 'enx #6'})
        self.assertEqual(dw.merge_opened(prev, {'imu': 'ttyACM0 usb 2-31'})['imu'], 'ttyACM0 usb 2-31')


class DeviceInUseTests(unittest.TestCase):
    """G-DUP-START: a driver is not started while another process already uses its device."""
    def fake_proc(self, root, pid, links):
        fd = Path(root) / str(pid) / 'fd'; fd.mkdir(parents=True)
        for i, target in enumerate(links): os.symlink(target, fd / str(i))

    def test_tty_users_finds_the_process_holding_the_port_by_its_by_id_name(self):
        with tempfile.TemporaryDirectory() as d:
            fs = FakeSys(d); fs.plug('ttyACM0', 1, 4)
            proc = Path(d) / 'proc'; proc.mkdir()
            self.fake_proc(proc, 11429, [str(Path(d) / 'dev' / 'ttyACM0'), '/dev/null'])
            self.fake_proc(proc, 500, ['/dev/null', 'socket:[1]'])
            (proc / 'self').mkdir()   # non-numeric entries are skipped
            self.assertEqual(dw.tty_users(fs.by_id, str(proc)), [11429])
            self.assertEqual(dw.tty_users(fs.by_id, str(proc), exclude=(11429,)), [])
            self.assertEqual(dw.tty_users(str(Path(d) / 'dev' / 'ttyACM1'), str(proc)), [])

    def test_udp_port_users_reads_the_socket_tables(self):
        with tempfile.TemporaryDirectory() as d:
            proc = Path(d) / 'proc'; (proc / 'net').mkdir(parents=True)
            head = '   sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode ref pointer drops\n'
            (proc / 'net' / 'udp').write_text(head +
                '  1: 00000000:0940 00000000:0000 07 00000000:00000000 00:00000000 00000000  1000        0 77001 2 0 0\n'
                '  2: 0100007F:14E9 00000000:0000 07 00000000:00000000 00:00000000 00000000  1000        0 77002 2 0 0\n')
            (proc / 'net' / 'udp6').write_text(head)
            self.fake_proc(proc, 11338, ['socket:[77001]'])
            self.fake_proc(proc, 600, ['socket:[77002]'])
            self.assertEqual(dw.udp_port_users(0x0940, str(proc)), [11338])     # the LiDAR data port held by another driver
            self.assertEqual(dw.udp_port_users(0x0941, str(proc)), [])
            self.assertEqual(dw.udp_port_users(0x0940, str(proc), exclude=(11338,)), [])


class ReceptionAndWarningTests(unittest.TestCase):
    def setUp(self):
        self.t = [1000.0]; self.core = MonitorCore(clock=lambda: self.t[0])

    def feed(self, key, n, period, start=None, stamp_offset=0):
        t0 = self.t[0] if start is None else start
        for i in range(n):
            self.core.on_sensor(key, t0 + i * period, t0 + i * period + stamp_offset)
        self.t[0] = t0 + (n - 1) * period

    def test_never_received_is_warned_even_without_thresholds(self):
        w = self.core.mapping_start_warning(); self.assertIn('XT-32', w); self.assertIn('IMU', w)
        self.feed('points', 20, 0.1); self.feed('imu', 200, 0.01, start=self.t[0] - 1.99)
        self.assertIsNone(self.core.mapping_start_warning())
        snap = self.core.sensors_snapshot()
        self.assertAlmostEqual(snap['points']['rate_hz'], 10, places=3); self.assertAlmostEqual(snap['imu']['rate_hz'], 100, places=1)
        self.assertEqual(snap['points']['status'], 'RECEIVED'); self.assertIn('STALE 判定はしない', snap['points']['verdict'])

    def test_stale_with_threshold(self):
        self.core.stale_after_sensor_s = {'points': 0.5, 'imu': 0.5}
        self.feed('points', 20, 0.1); self.feed('imu', 50, 0.01, start=self.t[0] - 0.49)
        self.assertIsNone(self.core.mapping_start_warning())
        self.t[0] += 3   # both stop
        w = self.core.mapping_start_warning(); self.assertIn('届いていない', w); self.assertIn('XT-32', w); self.assertIn('IMU', w)
        self.assertEqual(self.core.snapshot()['sensors']['imu']['status'], 'STALE')

    def test_stamp_offset_is_reported(self):
        self.feed('points', 3, 0.1, stamp_offset=-0.1)
        self.assertAlmostEqual(self.core.sensors_snapshot()['points']['stamp_minus_receive_s'], -0.1, places=6)


class HeaderStampTests(unittest.TestCase):
    def test_reads_cdr_header_stamp(self):
        import struct
        try:
            from gouda_core.monitor_node import header_stamp
        except ImportError:   # rclpy is not available on this machine: the function is tested on the ROS machine
            self.skipTest('rclpy not installed')
        raw = b'\x00\x01\x00\x00' + struct.pack('<iI', 1791883738, 500000000) + b'\x05\x00\x00\x00imu\x00'
        self.assertAlmostEqual(header_stamp(raw), 1791883738.5, places=6); self.assertIsNone(header_stamp(b'\x00\x01'))


class SupervisorLabelTests(unittest.TestCase):
    def test_every_sensor_setting_has_a_label(self):
        """Every key the driver settings can report as missing has a PRM label (a KeyError crashed the supervisor once)."""
        import re
        src = (Path(__file__).resolve().parents[1] / 'gouda_core' / 'sensor_supervisor_node.py').read_text()
        labels = set(re.findall(r"'(\w+)': 'PRM-\d+'", src))
        from gouda_core import sensor_config as sc
        self.assertTrue(set(sc.HESAI_KEYS) | set(sc.IMU_KEYS) <= labels, set(sc.HESAI_KEYS) | set(sc.IMU_KEYS) - labels)


if __name__ == '__main__':
    unittest.main()
