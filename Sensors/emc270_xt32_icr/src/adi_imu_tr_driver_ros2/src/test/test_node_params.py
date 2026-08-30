# The MIT License (MIT)
# Copyright (c) 2019 Techno Road Inc.
#
# Layer 4: parameter / remap coverage for ImuNodeRcvBin, driven by a PTY
# fake IMU (fake_imu.py) so no real hardware is needed. Each CONFIG below
# relaunches the node with a different parameter / remap / namespace set,
# and the shared test methods verify the node honors it on the *resolved*
# topic and service names. See doc/hide/test_plan_gen2.md (Layer 4).

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
from emc270_icr_msgs.msg import ImuTelemetry
from launch_ros.actions import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Imu
from tf2_msgs.msg import TFMessage

sys.path.insert(0, os.path.dirname(__file__))
from fake_imu import FakeImu  # noqa: E402

from adi_imu_tr_driver_ros2.srv import SimpleCmd  # noqa: E402

DEFAULT_NODE = "adi_rcv_bin_node"

# Each config relaunches the node. Fields default-fill in _fill() so configs
# only need to state what differs from the baseline.
CONFIGS = [
    {"id": "frame_id", "params": {"frame_id": "sensor_link"},
     "expect_frame": "sensor_link"},
    {"id": "parent_id", "params": {"parent_id": "base_link"},
     "expect_parent": "base_link"},
    {"id": "rate50", "params": {"rate": 50.0}, "expect_rate": 50.0},
    {"id": "rate200", "params": {"rate": 200.0}, "expect_rate": 200.0},
    {"id": "defaults", "params": {}, "expect_rate": 100.0},
    {"id": "remap_data", "remaps": [("imu/data_raw", "/custom/imu")],
     "imu_topic": "/custom/imu"},
    {"id": "remap_tf", "remaps": [("tf", "/custom/tf")],
     "tf_topic": "/custom/tf"},
    {"id": "remap_cmd", "remaps": [("imu/cmd_srv", "/custom/cmd")],
     "cmd_service": "/custom/cmd"},
    {"id": "remap_diag", "remaps": [("/diagnostics", "/custom/diag")],
     "diag_topic": "/custom/diag"},
    {"id": "remap_nodename", "node_name": "my_imu"},
    {"id": "namespace", "namespace": "/sensors",
     "imu_topic": "/sensors/imu/data_raw", "tf_topic": "/sensors/tf",
     "cmd_service": "/sensors/imu/cmd_srv",
     "node_name": "my_imu", "node_ns": "/sensors"},
]


def _fill(c):
    c.setdefault("params", {})
    c.setdefault("remaps", [])
    c.setdefault("namespace", None)
    c.setdefault("node_name", DEFAULT_NODE)
    c.setdefault("node_ns", "/")
    c.setdefault("imu_topic", "/imu/data_raw")
    c.setdefault("tf_topic", "/tf")
    c.setdefault("cmd_service", "/imu/cmd_srv")
    c.setdefault("diag_topic", "/diagnostics")
    c.setdefault("telemetry_topic", "/sensors/imu/telemetry"
                 if c["namespace"] else "/imu/telemetry")
    c.setdefault("expect_frame", c["params"].get("frame_id", "imu"))
    c.setdefault("expect_parent", c["params"].get("parent_id", "odom"))
    c.setdefault("expect_rate", None)
    return c


CONFIGS = [_fill(c) for c in CONFIGS]


@pytest.mark.launch_test
@launch_testing.parametrize("config", CONFIGS)
def generate_test_description(config):
    fake = FakeImu()
    fake.start()

    params = dict(config["params"])
    params["device"] = fake.device

    node_kwargs = {
        "package": "adi_imu_tr_driver_ros2",
        "executable": "adis_rcv_bin_node",
        "output": "screen",
        "parameters": [params],
        "remappings": config["remaps"],
    }
    if config["node_name"] != DEFAULT_NODE:
        node_kwargs["name"] = config["node_name"]
    if config["namespace"] is not None:
        node_kwargs["namespace"] = config["namespace"]

    node = Node(**node_kwargs)

    return (
        launch.LaunchDescription([node, launch_testing.actions.ReadyToTest()]),
        {"fake": fake},
    )


class ParamRemapTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        rclpy.init()

    @classmethod
    def tearDownClass(cls):
        rclpy.shutdown()

    def setUp(self):
        self.node = rclpy.create_node("layer4_param_helper")

    def tearDown(self):
        self.node.destroy_node()

    # ---- helpers ----------------------------------------------------------
    def _collect(self, msg_type, topic, duration, warmup=10.0, qos=10):
        """Subscribe to topic, wait up to warmup for the first message, then
        collect for `duration` seconds. Returns the list of messages."""
        msgs = []
        sub = self.node.create_subscription(
            msg_type, topic, lambda m: msgs.append(m), qos)
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

    # ---- tests ------------------------------------------------------------
    def test_imu_frame_id(self, config):
        msgs = self._collect(Imu, config["imu_topic"], 0.5)
        self.assertTrue(msgs, f"no Imu on {config['imu_topic']}")
        self.assertEqual(msgs[-1].header.frame_id, config["expect_frame"])
        # Fake streams identity attitude (W=1).
        self.assertAlmostEqual(msgs[-1].orientation.w, 1.0, delta=0.05)

    def test_tf_frames(self, config):
        msgs = self._collect(TFMessage, config["tf_topic"], 0.5)
        self.assertTrue(msgs, f"no TF on {config['tf_topic']}")
        tf = msgs[-1].transforms[0]
        self.assertEqual(tf.child_frame_id, config["expect_frame"])
        self.assertEqual(tf.header.frame_id, config["expect_parent"])

    def test_publish_rate(self, config):
        window = 3.0
        msgs = self._collect(Imu, config["imu_topic"], window)
        self.assertTrue(msgs, f"no Imu on {config['imu_topic']}")
        if config["expect_rate"] is None:
            return
        freq = len(msgs) / window
        lo = config["expect_rate"] * 0.75
        hi = config["expect_rate"] * 1.25
        self.assertTrue(
            lo <= freq <= hi,
            f"rate {freq:.1f}Hz outside [{lo:.1f},{hi:.1f}] "
            f"(expected {config['expect_rate']}Hz)")

    def test_full_rate_telemetry_is_unique_and_contiguous(self, config):
        window = 1.0
        msgs = self._collect(
            ImuTelemetry, config["telemetry_topic"], window,
            qos=qos_profile_sensor_data)
        self.assertGreater(
            len(msgs), 300,
            f"too few full-rate samples on {config['telemetry_topic']}")
        counters = [message.imu_counter for message in msgs]
        self.assertEqual(len(counters), len(set(counters)))
        deltas = [((current - previous) & 0xFFFF)
                  for previous, current in zip(counters, counters[1:])]
        self.assertTrue(all(delta == 1 for delta in deltas),
                        f"non-contiguous IMU counters: {deltas[:20]}")

    def test_cmd_service(self, config):
        client = self.node.create_client(SimpleCmd, config["cmd_service"])
        self.assertTrue(
            client.wait_for_service(timeout_sec=10.0),
            f"service {config['cmd_service']} unavailable")
        req = SimpleCmd.Request()
        req.cmd = "0x30"  # NOP
        future = client.call_async(req)
        rclpy.spin_until_future_complete(self.node, future, timeout_sec=5.0)
        res = future.result()
        self.assertIsNotNone(res, "service call timed out")
        self.assertTrue(res.is_ok, f"cmd_srv NOP failed: {res.msg}")

    def test_diagnostics(self, config):
        msgs = self._collect(DiagnosticArray, config["diag_topic"], 2.0)
        msgs = [m for m in msgs if m.status]
        self.assertTrue(msgs, f"no diagnostics on {config['diag_topic']}")
        self.assertEqual(msgs[-1].status[0].level, DiagnosticStatus.OK)

    def test_node_name(self, config):
        deadline = time.monotonic() + 10.0
        found = False
        while time.monotonic() < deadline and not found:
            rclpy.spin_once(self.node, timeout_sec=0.1)
            names = self.node.get_node_names_and_namespaces()
            found = any(
                n == config["node_name"] and ns == config["node_ns"]
                for n, ns in names)
        self.assertTrue(
            found,
            f"node {config['node_ns']}/{config['node_name']} not in graph")


@launch_testing.post_shutdown_test()
class StopFakeImu(unittest.TestCase):
    def test_stop_fake(self, fake):
        fake.stop()
