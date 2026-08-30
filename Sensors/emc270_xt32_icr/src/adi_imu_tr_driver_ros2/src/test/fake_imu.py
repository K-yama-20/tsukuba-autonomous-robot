# The MIT License (MIT)
# Copyright (c) 2019 Techno Road Inc.
#
# PTY-backed fake TR-IMU-Platform2 device for Layer 4 (parameter / remap)
# tests. It speaks the binary protocol implemented in
# lib/src/adis_rcv_bin.cpp so that ImuNodeRcvBin can come up and publish
# without any real hardware.
#
# Packet layout (70 bytes, see AdisRcvBin::BuildPacket / FindAndParsePacket):
#   0xAA 0xAA | id(1) | length=64(1) | payload(64) | RFC1071 csum(2, LE)
# Checksum is computed over (id + length + payload) and stored low byte first.

import os
import pty
import select
import struct
import threading
import time

HEADER = 0xAA
PACKET_SIZE = 70
PAYLOAD_LEN = 64

# Command IDs sent by the node (lib/src/adis_rcv_bin.cpp).
CMD_NOP = 0x30
CMD_START_TELEMETRY = 0x31
CMD_STOP_TELEMETRY = 0x32
CMD_RESET_ATTITUDE = 0x33
CMD_READ_SETTINGS = 0x70

# Response IDs emitted by the device.
RESP_TELEMETRY = 0x20
RESP_SETTINGS = 0x70


def calc_rfc1071(body):
    """Replicates AdisRcvBin::CalcRFC1071 (byte sum + carry fold, then ~)."""
    s = sum(body)
    while s >> 16:
        s = (s & 0xFFFF) + (s >> 16)
    return (~s) & 0xFFFF


def build_packet(packet_id, payload):
    """Frame a 64-byte payload into a 70-byte protocol packet."""
    assert len(payload) == PAYLOAD_LEN
    body = bytes([packet_id, PAYLOAD_LEN]) + payload
    csum = calc_rfc1071(body)
    return bytes([HEADER, HEADER]) + body + struct.pack("<H", csum)


def make_settings_payload(
    accl_sensitivity=1600000,
    gyro_sensitivity=40000000,
    sample_rate=2000,
    product_id=16470,
    model=0x03,
    build_date=20240101,
):
    """64-byte settings payload matching ParseSettingsPayload offsets."""
    p = bytearray(PAYLOAD_LEN)
    p[0] = 0  # mpu_error
    struct.pack_into("<I", p, 1, 0)  # send_counter
    struct.pack_into("<I", p, 5, build_date)
    p[9] = 0  # peripheral_enable
    p[10] = 1  # read_32bit
    p[11] = 0  # filter_select
    struct.pack_into("<Q", p, 12, accl_sensitivity)
    struct.pack_into("<Q", p, 20, gyro_sensitivity)
    struct.pack_into("<H", p, 28, sample_rate)
    p[30] = 1  # imu_maker
    struct.pack_into("<H", p, 31, product_id)
    p[33] = model
    p[34] = 0  # board
    p[35] = 0  # grav_corr_en
    p[36] = 0  # in_pupd
    p[37] = 0  # in_trigger
    return bytes(p)


def make_telemetry_payload(send_counter=0, quat=(32767, 0, 0, 0),
                           mpu_error=0, timestamp_us=None):
    """64-byte telemetry payload matching ParseTelemetryPayload offsets.

    Default quaternion is the identity attitude (W=32767 -> 1.0) so tests
    can assert a known orientation. ``mpu_error`` defaults to 0 so the node
    does not skip publishing; set it to ``kMpuErrImuNotFound`` (0x10, bit4)
    to exercise the "IMU not recognized" critical-error flow (spec 5.4.1).
    """
    p = bytearray(PAYLOAD_LEN)
    p[0] = mpu_error & 0xFF  # mpu_error (bit4 = IMU not recognized)
    struct.pack_into("<I", p, 1, send_counter & 0xFFFFFFFF)
    struct.pack_into("<h", p, 5, quat[0])  # W
    struct.pack_into("<h", p, 7, quat[1])  # X
    struct.pack_into("<h", p, 9, quat[2])  # Y
    struct.pack_into("<h", p, 11, quat[3])  # Z
    struct.pack_into("<i", p, 13, 0)  # acc X
    struct.pack_into("<i", p, 17, 0)  # acc Y
    struct.pack_into("<i", p, 21, 1600000)  # acc Z (~1 g with default sensitivity)
    struct.pack_into("<i", p, 25, 0)  # gyro X
    struct.pack_into("<i", p, 29, 0)  # gyro Y
    struct.pack_into("<i", p, 33, 0)  # gyro Z
    struct.pack_into("<h", p, 37, 250)  # temperature (25.0 C)
    struct.pack_into("<H", p, 39, send_counter & 0xFFFF)  # imu_counter
    struct.pack_into("<H", p, 41, 0)  # imu_dropped
    struct.pack_into("<H", p, 43, 0)  # computation_time_us
    struct.pack_into("<H", p, 45, 0)  # spi_transaction_time_us
    p[47] = 0  # in0_port
    if timestamp_us is None:
        timestamp_us = send_counter * 1000
    struct.pack_into("<Q", p, 48, timestamp_us)  # MCU boot time [us]
    return bytes(p)


class FakeImu:
    """Pseudo-terminal backed fake IMU.

    Opens a PTY master/slave pair, exposes the slave path as ``device`` for
    the node to open, and runs a background thread that answers the node's
    commands and streams telemetry once telemetry has been started.
    """

    def __init__(self, stream_hz=1000.0, mpu_error=0):
        self.master_fd, self.slave_fd = pty.openpty()
        self.device = os.ttyname(self.slave_fd)
        self._stream_interval = 1.0 / stream_hz
        # mpu_error byte streamed in every telemetry packet. 0x10 (bit4) makes
        # the node treat the IMU as unrecognized (spec 5.4.1).
        self._mpu_error = mpu_error
        self._streaming = False
        self._stop = threading.Event()
        self._rxbuf = bytearray()
        self._counter = 0
        self._boot_monotonic = time.monotonic()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2.0)
        for fd in (self.master_fd, self.slave_fd):
            try:
                os.close(fd)
            except OSError:
                pass

    def _run(self):
        last_tx = 0.0
        while not self._stop.is_set():
            try:
                r, _, _ = select.select([self.master_fd], [], [], 0.001)
                if r:
                    data = os.read(self.master_fd, 4096)
                    if data:
                        self._handle_rx(data)
                if self._streaming:
                    now = time.monotonic()
                    if now - last_tx >= self._stream_interval:
                        last_tx = now
                        self._counter += 1
                        os.write(
                            self.master_fd,
                            build_packet(
                                RESP_TELEMETRY,
                                make_telemetry_payload(
                                    self._counter, mpu_error=self._mpu_error,
                                    timestamp_us=int(
                                        (now - self._boot_monotonic) * 1e6)),
                            ),
                        )
            except OSError:
                # Slave closed (node exited) -> shut the loop down.
                break

    def _handle_rx(self, data):
        # Scan the incoming byte stream for command headers and act on the
        # command ID. A small tail is retained in case a header straddles
        # two reads.
        buf = self._rxbuf + data
        i = 0
        while i + 2 < len(buf):
            if buf[i] == HEADER and buf[i + 1] == HEADER:
                self._on_command(buf[i + 2])
                i += 3
            else:
                i += 1
        self._rxbuf = bytearray(buf[max(0, len(buf) - 2):])

    def _on_command(self, cmd_id):
        if cmd_id == CMD_READ_SETTINGS:
            os.write(
                self.master_fd,
                build_packet(RESP_SETTINGS, make_settings_payload()),
            )
        elif cmd_id == CMD_START_TELEMETRY:
            self._streaming = True
        elif cmd_id == CMD_STOP_TELEMETRY:
            self._streaming = False
        # CMD_NOP / CMD_RESET_ATTITUDE need no reply (node does not wait).
