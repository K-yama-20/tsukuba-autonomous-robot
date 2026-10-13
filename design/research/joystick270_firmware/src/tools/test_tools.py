"""Host-side checks for the Python binary-protocol utilities."""

from __future__ import annotations

import struct
import unittest

from tools import decode_calibration_log
from tools import encoder_uart_simulator


class ProtocolToolsTest(unittest.TestCase):
    def test_crc_known_vector(self) -> None:
        self.assertEqual(encoder_uart_simulator.crc16_ccitt(b"123456789"), 0x29B1)

    def test_encoder_frame_round_trip(self) -> None:
        encoded = encoder_uart_simulator.frame(17, 1234, -56, 78)
        frames = list(decode_calibration_log.iter_frames(encoded))
        self.assertEqual(len(frames), 1)
        message_type, sequence, timestamp_ms, payload = frames[0]
        self.assertEqual(message_type, encoder_uart_simulator.ENCODER_SPEED)
        self.assertEqual(sequence, 17)
        self.assertEqual(timestamp_ms, 1234)
        self.assertEqual(struct.unpack("<iiH", payload), (-56, 78, 1))

    def test_calibration_sample_layout_is_34_bytes(self) -> None:
        self.assertEqual(decode_calibration_log.SAMPLE.size, 34)


if __name__ == "__main__":
    unittest.main()
