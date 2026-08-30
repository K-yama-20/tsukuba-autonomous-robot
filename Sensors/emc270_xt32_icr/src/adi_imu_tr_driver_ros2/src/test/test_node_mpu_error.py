# The MIT License (MIT)
# Copyright (c) 2019 Techno Road Inc.
#
# Layer 4: mpu_error bit4 (IMU not recognized) critical-error flow for
# ImuNodeRcvBin, driven by a PTY fake IMU (fake_imu.py) so no real hardware
# is needed. The fake streams telemetry with mpu_error bit4 (0x10) set; per
# spec 5.4.1 the node must stop the drive system, so it skips publishing
# /imu/data_raw and reports ERROR on /diagnostics. See the node logic in
# src/adis_rcv_bin_node.hpp (PublishSample / Diagnostic).

import os
import sys
import time
import unittest

import launch
import launch_testing
import launch_testing.actions
import pytest
import rclpy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus
from launch_ros.actions import Node
from sensor_msgs.msg import Imu

sys.path.insert(0, os.path.dirname(__file__))
from fake_imu import FakeImu  # noqa: E402

# kMpuErrImuNotFound (lib/include/adis_rcv_bin.h, spec 5.4.1).
MPU_ERR_IMU_NOT_FOUND = 0x10


@pytest.mark.launch_test
def generate_test_description():
    # Stream telemetry with bit4 set the whole time.
    fake = FakeImu(mpu_error=MPU_ERR_IMU_NOT_FOUND)
    fake.start()

    node = Node(
        package="adi_imu_tr_driver_ros2",
        executable="adis_rcv_bin_node",
        output="screen",
        parameters=[{"device": fake.device}],
    )

    return (
        launch.LaunchDescription([node, launch_testing.actions.ReadyToTest()]),
        {"fake": fake},
    )


class MpuErrorBit4Test(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        rclpy.init()

    @classmethod
    def tearDownClass(cls):
        rclpy.shutdown()

    def setUp(self):
        self.node = rclpy.create_node("layer4_mpu_error_helper")

    def tearDown(self):
        self.node.destroy_node()

    def test_no_imu_publish_on_bit4(self):
        """With bit4 set the node must skip publishing /imu/data_raw."""
        msgs = []
        sub = self.node.create_subscription(
            Imu, "/imu/data_raw", lambda m: msgs.append(m), 10)
        try:
            # Give the node ample time to come up and stream several packets.
            end = time.monotonic() + 6.0
            while time.monotonic() < end:
                rclpy.spin_once(self.node, timeout_sec=0.1)
        finally:
            self.node.destroy_subscription(sub)

        self.assertFalse(
            msgs, f"node published {len(msgs)} Imu msgs despite mpu_error bit4")

    def test_diagnostics_error_on_bit4(self):
        """/diagnostics must report ERROR naming the bit4 condition."""
        msgs = []
        sub = self.node.create_subscription(
            DiagnosticArray, "/diagnostics", lambda m: msgs.append(m), 10)
        try:
            # diagnostic_updater publishes at 1 Hz; wait for a few cycles.
            deadline = time.monotonic() + 15.0
            statuses = []
            while time.monotonic() < deadline:
                rclpy.spin_once(self.node, timeout_sec=0.1)
                statuses = [s for m in msgs for s in m.status]
                if statuses:
                    break
        finally:
            self.node.destroy_subscription(sub)

        self.assertTrue(statuses, "no /diagnostics status received")
        last = statuses[-1]
        self.assertEqual(
            last.level, DiagnosticStatus.ERROR,
            f"expected ERROR, got level={last.level} msg={last.message!r}")
        self.assertIn("IMU not recognized", last.message)


@launch_testing.post_shutdown_test()
class StopFakeImu(unittest.TestCase):
    def test_stop_fake(self, fake):
        fake.stop()
