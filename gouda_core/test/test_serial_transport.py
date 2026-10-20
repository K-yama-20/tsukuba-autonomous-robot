"""vehicle_bridge SerialTransport (ND-12): writes never block the executor (DEC-174).

Runs where pyserial and rclpy are installed (the Ubuntu VM / vehicle PC); skipped elsewhere. A pseudo-terminal whose other
end is never read stands in for a stalled ESP32 link: the kernel buffer fills, and write must return at once and report the
dropped frame instead of waiting."""
import os
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import serial  # noqa: F401
    from gouda_core.vehicle_bridge_node import SerialTransport
except ImportError:   # no pyserial / rclpy here
    SerialTransport = None


@unittest.skipIf(SerialTransport is None, 'pyserial / rclpy not installed')
class SerialTransportTests(unittest.TestCase):
    def setUp(self):
        self.master, slave = os.openpty(); self.slave_name = os.ttyname(slave); os.close(slave)
        self.errors = []
        self.t = SerialTransport(self.slave_name, lambda b: None, self.errors.append)

    def tearDown(self):
        self.t.close(); os.close(self.master)

    def test_write_reaches_the_other_end(self):
        self.t.write(b'\xa5\x5a\x01\x02'); self.assertEqual(os.read(self.master, 16), b'\xa5\x5a\x01\x02'); self.assertEqual(self.errors, [])

    def test_full_buffer_drops_the_frame_without_waiting(self):
        frame = bytes(25)
        start = time.monotonic()
        for _ in range(20000):   # far more than a pty buffer holds; the other end is never read
            self.t.write(frame)
            if self.errors: break
        self.assertTrue(self.errors, 'the full buffer was never reported')
        self.assertTrue(all('incomplete' in e for e in self.errors), self.errors)
        self.assertLess(time.monotonic() - start, 5, 'writes waited for the port')


if __name__ == '__main__': unittest.main()
