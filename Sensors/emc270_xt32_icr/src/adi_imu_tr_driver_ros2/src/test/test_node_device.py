# The MIT License (MIT)
# Copyright (c) 2019 Techno Road Inc.
#
# Layer 4: device parameter negative-path and default-configuration coverage
# for ImuNodeRcvBin.

import os
import sys
import time
import unittest

import launch
import launch_testing
import launch_testing.actions
import pytest
import rclpy
from launch_ros.actions import Node
from sensor_msgs.msg import Imu

sys.path.insert(0, os.path.dirname(__file__))
from fake_imu import FakeImu  # noqa: E402

# Two launches: an unopenable device (node must keep retrying and never
# publish) and a normal launch with only `device` set (defaults must work).
CONFIGS = [
    {"id": "invalid_device", "use_fake": False,
     "device": "/dev/nonexistent_tr_imu", "expect_log": "Waiting for IMU device",
     "expect_publish": False},
    {"id": "defaults", "use_fake": True,
     "expect_log": "Product=ADIS16470-1", "expect_publish": True},
]


@pytest.mark.launch_test
@launch_testing.parametrize("config", CONFIGS)
def generate_test_description(config):
    fake = None
    device = config.get("device")
    if config["use_fake"]:
        fake = FakeImu()
        fake.start()
        device = fake.device

    node = Node(
        package="adi_imu_tr_driver_ros2",
        executable="adis_rcv_bin_node",
        output="screen",
        parameters=[{"device": device}],
    )

    return (
        launch.LaunchDescription([node, launch_testing.actions.ReadyToTest()]),
        {"fake": fake, "node_action": node},
    )


class DeviceTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        rclpy.init()

    @classmethod
    def tearDownClass(cls):
        rclpy.shutdown()

    def setUp(self):
        self.node = rclpy.create_node("layer4_device_helper")

    def tearDown(self):
        self.node.destroy_node()

    def test_expected_log(self, config, proc_output, node_action):
        proc_output.assertWaitFor(
            config["expect_log"], process=node_action, timeout=20.0)

    def test_publish_behavior(self, config):
        msgs = []
        sub = self.node.create_subscription(
            Imu, "/imu/data_raw", lambda m: msgs.append(m), 10)
        try:
            end = time.monotonic() + 6.0
            while time.monotonic() < end:
                rclpy.spin_once(self.node, timeout_sec=0.1)
                if msgs and config["expect_publish"]:
                    break
        finally:
            self.node.destroy_subscription(sub)

        if config["expect_publish"]:
            self.assertTrue(msgs, "expected /imu/data_raw but got none")
        else:
            self.assertFalse(
                msgs, "node published despite an unopenable device")


@launch_testing.post_shutdown_test()
class StopFakeImu(unittest.TestCase):
    def test_stop_fake(self, fake):
        if fake is not None:
            fake.stop()
