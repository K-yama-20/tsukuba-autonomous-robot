"""PTY integration regression for ADI IMU USB reconnect behavior.

Run on Ubuntu 24.04 / ROS 2 Jazzy after sourcing the driver's install setup:
    python3 test_imu_usb_reconnect.py /path/to/install/setup.bash

Only pseudo terminals are created. The node is launched in a private ROS
domain and is always stopped by this script.
"""

import json
import os
import pty
import select
import shlex
import signal
import struct
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import rclpy
from sensor_msgs.msg import Imu
from std_msgs.msg import String


HEADER = 0xAA
PAYLOAD_LEN = 64
RESP_TELEMETRY = 0x20
RESP_SETTINGS = 0x70
CMD_START_TELEMETRY = 0x31
CMD_STOP_TELEMETRY = 0x32
CMD_READ_SETTINGS = 0x70


def packet(packet_id, payload):
    body = bytes((packet_id, PAYLOAD_LEN)) + payload
    checksum = sum(body)
    while checksum >> 16:
        checksum = (checksum & 0xFFFF) + (checksum >> 16)
    return bytes((HEADER, HEADER)) + body + struct.pack("<H", (~checksum) & 0xFFFF)


def settings_payload():
    p = bytearray(PAYLOAD_LEN)
    p[10] = 1
    struct.pack_into("<Q", p, 12, 1_600_000)
    struct.pack_into("<Q", p, 20, 40_000_000)
    struct.pack_into("<H", p, 28, 2000)
    p[30] = 1
    struct.pack_into("<H", p, 31, 16470)
    p[33] = 3
    return p


def telemetry_payload(counter, mcu_us):
    p = bytearray(PAYLOAD_LEN)
    struct.pack_into("<I", p, 1, counter & 0xFFFFFFFF)
    struct.pack_into("<hhhh", p, 5, 32767, 0, 0, 0)
    struct.pack_into("<i", p, 21, 1_600_000)
    struct.pack_into("<H", p, 39, counter & 0xFFFF)
    struct.pack_into("<Q", p, 48, mcu_us)
    return p


class PtyImu:
    """Minimal fake device; wrong_settings deliberately returns ID 0x20."""

    def __init__(self, wrong_settings=False, counter_start=0, mcu_offset=0):
        self.master, self.slave = pty.openpty()
        self.path = os.ttyname(self.slave)
        self.wrong_settings = wrong_settings
        self.counter = counter_start
        self.mcu_offset = mcu_offset
        self.streaming = False
        self.stop_event = threading.Event()
        self.rx = bytearray()
        self.closed = False
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.stop_event.set()
        self.thread.join(timeout=2)
        for fd in (self.master, self.slave):
            try:
                os.close(fd)
            except OSError:
                pass

    def _run(self):
        last = 0.0
        while not self.stop_event.is_set():
            try:
                ready, _, _ = select.select([self.master], [], [], 0.002)
                if ready:
                    self.rx.extend(os.read(self.master, 4096))
                    while len(self.rx) >= 3:
                        i = self.rx.find(bytes((HEADER, HEADER)))
                        if i < 0:
                            self.rx[:] = self.rx[-1:]
                            break
                        if i:
                            del self.rx[:i]
                        if len(self.rx) < 3:
                            break
                        cmd = self.rx[2]
                        del self.rx[:3]
                        if cmd == CMD_READ_SETTINGS:
                            response_id = RESP_TELEMETRY if self.wrong_settings else RESP_SETTINGS
                            os.write(self.master, packet(response_id, settings_payload()))
                        elif cmd == CMD_START_TELEMETRY:
                            self.streaming = True
                        elif cmd == CMD_STOP_TELEMETRY:
                            self.streaming = False
                now = time.monotonic()
                if self.streaming and now - last >= 0.005:
                    last = now
                    self.counter += 1
                    mcu_us = int(now * 1_000_000) + self.mcu_offset
                    os.write(self.master, packet(RESP_TELEMETRY,
                                                  telemetry_payload(self.counter, mcu_us)))
            except OSError:
                break


def spin_until(node, predicate, timeout, what):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.05)
        if predicate():
            return
    raise AssertionError(f"timed out waiting for {what}")


def main():
    setup = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None
    if setup is None or not setup.is_file():
        raise SystemExit("usage: test_imu_usb_reconnect.py /path/to/install/setup.bash")

    with tempfile.TemporaryDirectory(prefix="imu-reconnect-") as tmp:
        link = Path(tmp) / "imu-device"
        bad = PtyImu(wrong_settings=True)
        first = second = None
        os.symlink(bad.path, link)

        env = os.environ.copy()
        env["ROS_DOMAIN_ID"] = "119"
        # The subscriber and child node must inhabit the same isolated domain.
        os.environ["ROS_DOMAIN_ID"] = env["ROS_DOMAIN_ID"]
        # Source ROS and this isolated build, then exec the actual node.
        shell = ("source /opt/ros/jazzy/setup.bash && source " + shlex.quote(str(setup)) +
                 " && exec ros2 run adi_imu_tr_driver_ros2 adis_rcv_bin_node "
                 "--ros-args -p " + shlex.quote("device:=" + str(link)))
        log_file = open(Path(tmp) / "node.log", "wb")
        proc = subprocess.Popen(["bash", "-lc", shell], env=env,
                                stdout=log_file, stderr=subprocess.STDOUT)
        rclpy.init(args=None)
        helper = rclpy.create_node("imu_usb_reconnect_regression")
        imu_msgs, clock_msgs = [], []
        subs = [helper.create_subscription(Imu, "/imu/data_raw", imu_msgs.append, 50),
                helper.create_subscription(String, "/imu/clock_status", clock_msgs.append, 50)]
        try:
            # A telemetry packet cannot satisfy ReadSettings. No IMU samples
            # may escape while the configured endpoint fails settings reads.
            time.sleep(2.5)
            rclpy.spin_once(helper, timeout_sec=0.1)
            assert not imu_msgs, "IMU published while settings response was invalid"

            # Retarget the same configured path and prove recovery in the same PID.
            first = PtyImu(counter_start=0)
            link.unlink()
            link.symlink_to(first.path)
            try:
                spin_until(helper, lambda: len(imu_msgs) >= 5, 12, "initial IMU recovery")
            except AssertionError as exc:
                log_file.flush()
                detail = (Path(tmp) / "node.log").read_text(errors="replace")[-4000:]
                statuses = [m.data for m in clock_msgs[-12:]]
                raise AssertionError(f"{exc}; imu={len(imu_msgs)} clock={len(clock_msgs)} "
                                     f"clock_tail={statuses}; node log:\n{detail}") from exc
            pid = proc.pid
            assert proc.poll() is None, "node exited before first recovery"

            # Break telemetry, wait past watchdog, then reconnect with a reset
            # device counter and a deliberately different MCU clock epoch.
            disconnected_before = len(clock_msgs)
            first.streaming = False
            first.close()
            spin_until(helper,
                       lambda: any(json.loads(m.data).get("state") == "disconnected"
                                    for m in clock_msgs[disconnected_before:]),
                       5, "disconnected clock status")
            second = PtyImu(counter_start=0, mcu_offset=5_000_000_000)
            link.unlink()
            link.symlink_to(second.path)
            before = len(clock_msgs)
            imu_before_second = len(imu_msgs)
            spin_until(helper,
                       lambda: len(clock_msgs) >= before + 8 and
                       any(json.loads(m.data).get("state") == "host_mapped"
                           for m in clock_msgs[before:]),
                       12, "clock mapper relearning after reconnect")
            spin_until(helper, lambda: len(imu_msgs) >= imu_before_second + 5,
                       5, "IMU samples after counter reset")
            assert proc.poll() is None and proc.pid == pid, "node PID changed across reconnect"
            states = [json.loads(m.data).get("state") for m in clock_msgs[before:]]
            assert "unlocked" in states, f"clock mapper did not reset after reconnect: {states}"
            print("PASS: invalid settings withheld IMU; same node PID recovered through symlink retarget; clock mapping reset and relearned")
        finally:
            for sub in subs:
                helper.destroy_subscription(sub)
            helper.destroy_node()
            rclpy.shutdown()
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2)
            log_file.close()
            for fake in (bad, first, second):
                if fake is not None:
                    fake.close()


if __name__ == "__main__":
    main()

