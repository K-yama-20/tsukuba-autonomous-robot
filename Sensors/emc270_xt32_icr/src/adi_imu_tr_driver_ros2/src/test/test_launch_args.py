# The MIT License (MIT)
# Copyright (c) 2019 Techno Road Inc.
#
# Layer 4: verifies that adis_rcv_bin.launch.py wires its launch arguments
# (device / frame_id / parent_id / rate / with_rviz) through to the node's
# parameters and that with_rviz:=False suppresses rviz2.
# See doc/hide/test_plan_gen2.md (Layer 4).

import os
import sys
import time
import unittest

import launch
import launch_testing
import launch_testing.actions
import pytest
import rclpy
from ament_index_python.packages import get_package_share_directory
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from sensor_msgs.msg import Imu
from tf2_msgs.msg import TFMessage

sys.path.insert(0, os.path.dirname(__file__))
from fake_imu import FakeImu  # noqa: E402

CONFIGS = [
    {"id": "defaults", "args": {},
     "expect_frame": "imu", "expect_parent": "odom", "expect_rate": 100.0},
    {"id": "plumbing",
     "args": {"frame_id": "foo", "parent_id": "bar", "rate": "50.0"},
     "expect_frame": "foo", "expect_parent": "bar", "expect_rate": 50.0},
]


@pytest.mark.launch_test
@launch_testing.parametrize("config", CONFIGS)
def generate_test_description(config):
    fake = FakeImu()
    fake.start()

    launch_file = os.path.join(
        get_package_share_directory("adi_imu_tr_driver_ros2"),
        "launch", "adis_rcv_bin.launch.py")

    launch_args = {"device": fake.device, "with_rviz": "False"}
    launch_args.update(config["args"])

    incl = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(launch_file),
        launch_arguments=launch_args.items())

    return (
        launch.LaunchDescription([incl, launch_testing.actions.ReadyToTest()]),
        {"fake": fake},
    )


class LaunchArgsTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        rclpy.init()

    @classmethod
    def tearDownClass(cls):
        rclpy.shutdown()

    def setUp(self):
        self.node = rclpy.create_node("layer4_launch_helper")

    def tearDown(self):
        self.node.destroy_node()

    def _collect(self, msg_type, topic, duration, warmup=12.0):
        msgs = []
        sub = self.node.create_subscription(
            msg_type, topic, lambda m: msgs.append(m), 10)
        try:
            deadline = time.monotonic() + warmup
            while not msgs and time.monotonic() < deadline:
                rclpy.spin_once(self.node, timeout_sec=0.1)
            end = time.monotonic() + duration
            while time.monotonic() < end:
                rclpy.spin_once(self.node, timeout_sec=0.05)
        finally:
            self.node.destroy_subscription(sub)
        return msgs

    def test_frame_args(self, config):
        imu = self._collect(Imu, "/imu/data_raw", 0.3)
        self.assertTrue(imu, "no /imu/data_raw from included launch")
        self.assertEqual(imu[-1].header.frame_id, config["expect_frame"])

        tf = self._collect(TFMessage, "/tf", 0.3)
        self.assertTrue(tf, "no /tf from included launch")
        self.assertEqual(
            tf[-1].transforms[0].header.frame_id, config["expect_parent"])

    def test_rate_arg(self, config):
        window = 3.0
        msgs = self._collect(Imu, "/imu/data_raw", window)
        self.assertTrue(msgs, "no /imu/data_raw from included launch")
        freq = len(msgs) / window
        lo = config["expect_rate"] * 0.75
        hi = config["expect_rate"] * 1.25
        self.assertTrue(
            lo <= freq <= hi,
            f"rate {freq:.1f}Hz outside [{lo:.1f},{hi:.1f}]")

    def test_no_rviz(self, config):
        # with_rviz:=False -> rviz2 node must never appear.
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            rclpy.spin_once(self.node, timeout_sec=0.1)
        names = [n for n, _ in self.node.get_node_names_and_namespaces()]
        self.assertNotIn("rviz2", names)


@launch_testing.post_shutdown_test()
class StopFakeImu(unittest.TestCase):
    def test_stop_fake(self, fake):
        fake.stop()
