"""Serial devices are named only by their /dev/serial/by-id/ link (REV-069, DEC-141), and the IMU (ND-15) and the GNSS receiver
(ND-19), both ttyACM devices, are never confused: the identity watched and the "in use" check follow what each by-id name points
to, even when the ttyACM numbers swap after re-plugging. Simulated /dev, /sys and /proc trees (no hardware, no ROS)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import device_watch as dw  # noqa: E402
from gouda_core import gnss_config as gc  # noqa: E402

IMU_NAME = 'usb-STMicroelectronics_STM32_Virtual_ComPort_TEST-if00'    # test names (not the vehicle's)
GNSS_NAME = 'usb-Septentrio_Septentrio_USB_Device_TEST-if00'


class ByIdRuleTests(unittest.TestCase):
    def test_only_by_id_names(self):
        self.assertIsNone(dw.by_id_problem('/dev/serial/by-id/' + IMU_NAME))
        for bad in ('/dev/ttyACM0', '/dev/ttyUSB0', '/dev/serial/by-path/platform-x', '/dev/serial/by-id/', '/dev/serial/by-id/a/b',
                    '/dev/serial/by-id/..', 'ttyACM0', '', None):
            self.assertIsNotNone(dw.by_id_problem(bad), bad)
        self.assertIsNone(gc.parse_device('serial:/dev/ttyACM1'))
        self.assertEqual(gc.parse_device('serial:/dev/serial/by-id/' + GNSS_NAME)['path'], '/dev/serial/by-id/' + GNSS_NAME)


class Tree:
    """A fake root with by-id links to ttyACM nodes, the sysfs USB device of each tty, and /proc with open file descriptors."""

    def __init__(self, root: Path):
        self.root = root
        for d in ('dev/serial/by-id', 'sys/class/tty', 'proc'):
            (root / d).mkdir(parents=True, exist_ok=True)

    def plug(self, by_id: str, tty: str, bus: int, dev: int):
        """(Re)create /dev/<tty>, the by-id link to it and the sysfs USB device (bus, devnum) behind the tty."""
        node = self.root / 'dev' / tty
        node.touch()
        link = self.root / 'dev/serial/by-id' / by_id
        if link.is_symlink(): link.unlink()
        link.symlink_to(node)
        usbdev = self.root / f'sys/devices/usb{bus}/{bus}-{dev}'
        iface = usbdev / f'{bus}-{dev}:1.0'
        iface.mkdir(parents=True, exist_ok=True)
        (usbdev / 'busnum').write_text(f'{bus}\n'); (usbdev / 'devnum').write_text(f'{dev}\n')
        cls = self.root / 'sys/class/tty' / tty
        cls.mkdir(parents=True, exist_ok=True)
        dlink = cls / 'device'
        if dlink.is_symlink(): dlink.unlink()
        dlink.symlink_to(iface)
        return str(link)

    def unplug(self, by_id: str):
        (self.root / 'dev/serial/by-id' / by_id).unlink()

    def opened_by(self, pid: int, path: str):
        fd = self.root / 'proc' / str(pid) / 'fd'
        fd.mkdir(parents=True, exist_ok=True)
        (fd / '3').symlink_to(path)

    @property
    def sys(self): return str(self.root / 'sys')

    @property
    def proc(self): return str(self.root / 'proc')


class SimultaneousImuGnssTests(unittest.TestCase):
    def test_identities_follow_the_names_when_numbers_swap(self):
        with tempfile.TemporaryDirectory() as d:
            t = Tree(Path(d))
            imu = t.plug(IMU_NAME, 'ttyACM0', 2, 5); gnss = t.plug(GNSS_NAME, 'ttyACM1', 3, 6)
            imu_dev, gnss_dev = dw.WatchedDevice(imu), dw.WatchedDevice(gnss)
            a_imu, a_gnss = dw.tty_identity(imu, t.sys), dw.tty_identity(gnss, t.sys)
            self.assertEqual((a_imu, a_gnss), ('ttyACM0 usb 2-5', 'ttyACM1 usb 3-6'))
            self.assertEqual((imu_dev.decide(a_imu), gnss_dev.decide(a_gnss)), (dw.ACTION_START, dw.ACTION_START))
            imu_dev.apply(a_imu, dw.ACTION_START); gnss_dev.apply(a_gnss, dw.ACTION_START)
            # both unplugged, then plugged back in the other order: the numbers swap
            t.unplug(IMU_NAME); t.unplug(GNSS_NAME)
            self.assertEqual((dw.tty_identity(imu, t.sys), dw.tty_identity(gnss, t.sys)), (None, None))
            gnss = t.plug(GNSS_NAME, 'ttyACM0', 3, 7); imu = t.plug(IMU_NAME, 'ttyACM1', 2, 8)
            b_imu, b_gnss = dw.tty_identity(imu, t.sys), dw.tty_identity(gnss, t.sys)
            self.assertEqual((b_imu, b_gnss), ('ttyACM1 usb 2-8', 'ttyACM0 usb 3-7'), 'each name still finds its own device')
            # each driver is re-created for its own device only (new enumeration of that name)
            self.assertEqual(imu_dev.decide(b_imu), dw.ACTION_RESTART); self.assertEqual(gnss_dev.decide(b_gnss), dw.ACTION_RESTART)

    def test_in_use_is_judged_per_device(self):
        with tempfile.TemporaryDirectory() as d:
            t = Tree(Path(d))
            imu = t.plug(IMU_NAME, 'ttyACM0', 2, 5); gnss = t.plug(GNSS_NAME, 'ttyACM1', 3, 6)
            t.opened_by(4242, str(t.root / 'dev/ttyACM0'))       # someone holds the IMU's tty
            self.assertEqual(dw.tty_users(imu, t.proc), [4242])
            self.assertEqual(dw.tty_users(gnss, t.proc), [], 'the GNSS is free although the IMU is in use')
            # after a swap, the same open ttyACM0 now belongs to the GNSS: "in use" follows the device, not the number
            t.unplug(IMU_NAME); t.unplug(GNSS_NAME)
            gnss = t.plug(GNSS_NAME, 'ttyACM0', 3, 7); imu = t.plug(IMU_NAME, 'ttyACM1', 2, 8)
            self.assertEqual(dw.tty_users(gnss, t.proc), [4242]); self.assertEqual(dw.tty_users(imu, t.proc), [])


if __name__ == '__main__':
    unittest.main()
