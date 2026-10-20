"""vehicle_bridge SerialTransport (ND-12): the link survives a USB re-plug (DEC-176).

Runs where pyserial and rclpy are installed (the Ubuntu VM / vehicle PC); skipped elsewhere. A symlink stands in for the
/dev/serial/by-id name and a pseudo-terminal for the ESP32: closing the pty's other end is the unplug (the read fails),
pointing the symlink to a new pty and waking the transport is the re-plug (udev's event in the real node)."""
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import serial  # noqa: F401
    from gouda_core.vehicle_bridge_node import SerialTransport
except ImportError:   # no pyserial / rclpy here
    SerialTransport = None


@unittest.skipIf(SerialTransport is None, 'pyserial / rclpy not installed')
class SerialReconnectTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(); self.link = os.path.join(self.dir, 'usb-esp32')
        self.master = self._plug()
        self.events = []; self.cv = threading.Condition(); self.rx = bytearray(); self.errors = []
        self.t = SerialTransport(self.link, self._bytes, self.errors.append, self._link, watch_cmd=None)

    def tearDown(self):
        self.t.close()
        try: os.close(self.master)
        except OSError: pass
        try: os.unlink(self.link)
        except OSError: pass
        os.rmdir(self.dir)

    def _plug(self):
        master, slave = os.openpty(); name = os.ttyname(slave); os.close(slave)
        if os.path.lexists(self.link): os.unlink(self.link)
        os.symlink(name, self.link); return master

    def _link(self, up, why):
        with self.cv: self.events.append(up); self.cv.notify_all()

    def _bytes(self, data):
        with self.cv: self.rx.extend(data); self.cv.notify_all()

    def _wait(self, pred, what):
        with self.cv:
            self.assertTrue(self.cv.wait_for(pred, timeout=5), what)

    def test_unplug_is_reported_once_and_writes_are_dropped_silently(self):
        os.close(self.master); os.unlink(self.link)
        self._wait(lambda: self.events == [False], 'the lost link was not reported')
        self.assertFalse(self.t.connected)
        for _ in range(10): self.t.write(b'\xa5\x5a')
        self.assertEqual(self.events, [False]); self.assertEqual(self.errors, [])

    def test_replug_reopens_the_same_name_and_both_directions_work(self):
        os.close(self.master); os.unlink(self.link)
        self._wait(lambda: self.events == [False], 'the lost link was not reported')
        self.t.wake()   # a device event while the name is still absent: stays disconnected
        self.master = self._plug(); self.t.wake()
        self._wait(lambda: self.events == [False, True], 'the re-plugged device was not reopened')
        self.assertTrue(self.t.connected)
        self.t.write(b'\x01\x02'); self.assertEqual(os.read(self.master, 16), b'\x01\x02')
        os.write(self.master, b'\x03\x04'); self._wait(lambda: bytes(self.rx).endswith(b'\x03\x04'), 'no bytes after the re-plug')

    def test_repeated_replugs(self):
        for i in range(3):
            os.close(self.master); os.unlink(self.link)
            self._wait(lambda: self.events.count(False) == i + 1, f'unplug {i} not reported')
            self.master = self._plug(); self.t.wake()
            self._wait(lambda: self.events.count(True) == i + 1, f're-plug {i} not reopened')
        self.assertEqual(self.events, [False, True] * 3)


if __name__ == '__main__': unittest.main()
