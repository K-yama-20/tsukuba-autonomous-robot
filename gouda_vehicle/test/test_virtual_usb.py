"""Full ROS service/topic + production C++ Core test over pipes, never a USB device."""
import copy
import json
import os
from pathlib import Path
import subprocess
import time
from unittest.mock import patch

import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.parameter import Parameter
from std_msgs.msg import String
from gouda_vehicle import hardware_bridge as bridge
from gouda_navigation import autonomy_mvp as autonomy
from gouda_navigation.autonomy_core import DEFAULT_SETTINGS
from gouda_navigation.mapping import DEFAULT_SETTINGS as MAPPING


def test_pc_to_cpp_firmware_arm_drive_and_sensor_fault(tmp_path):
    root=Path(__file__).resolve().parents[2]
    executable=tmp_path/'virtual-device'
    subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-I',str(root/'firmware/gouda_dualsense_usb/include'),str(root/'firmware/gouda_dualsense_usb/test/virtual_device.cpp'),'-o',str(executable)],check=True)
    process=subprocess.Popen([str(executable)],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    os.set_blocking(process.stdout.fileno(),False)
    class Link:
        def read(self,n):
            try:return os.read(process.stdout.fileno(),n)
            except BlockingIOError:return b''
        def write(self,data):process.stdin.write(data);process.stdin.flush();return len(data)
        def close(self):pass
    cfg=copy.deepcopy(DEFAULT_SETTINGS)
    transform=dict(translation_m=[0,0,0],quaternion_xyzw=[0,0,0,1])
    cfg.update(hardware_enabled=True,serial_port='/dev/ttyUSB0',body_to_lidar=transform)
    mapping={**MAPPING,'backend':'glim_imu','clock_policy':'host_mapped','clock_evidence':'fixture','extrinsic_lidar_imu':transform,
        'point_time_field':'timestamp','point_time_datatype':'uint32','point_time_mode':'relative','point_time_unit':'nanoseconds',
        'imu_accel_unit':'m/s^2','imu_gyro_unit':'rad/s','imu_clock_offset_sec':0.,'lidar_clock_offset_sec':0.}
    rclpy.init(args=['--ros-args','-p','hardware_enabled:=true','-p','port:=/dev/ttyUSB0'])
    b=n=None
    try:
        with patch.object(bridge,'open_hardware_serial',return_value=Link()):b=bridge.HardwareSerialBridge()
        with patch.object(autonomy,'load_autonomy_settings',return_value=cfg),patch.object(autonomy,'load_mapping_settings',return_value=mapping):n=autonomy.AutonomyMVP()
        n.pose=(0.,0.,0.);n.estimate=dict(v_mps=0.,w_rps=0.);n.cloud=[(5.,5.,.5)];n.recording=True
        original_fresh=n.fresh
        n.fresh=lambda key:original_fresh(key) if key=='device' else True
        n.readiness=lambda:'' if n.fresh('device') else 'device stale'
        executor=SingleThreadedExecutor();executor.add_node(b);executor.add_node(n)
        def until(check,timeout=3.):
            end=time.monotonic()+timeout
            while time.monotonic()<end:
                executor.spin_once(timeout_sec=.01)
                if check():return
            raise AssertionError(f'timeout phase={n.phase} reason={n.reason} status={b.status_values}')
        until(lambda:n.device is not None and n.arm.service_is_ready() and b.drive is not None)
        assert not b.status_values['auto_enabled']
        n.on_request(String(data=json.dumps(dict(action='start',request_id='virtual-start',issued_at=n.stamp(),
            goal=dict(forward_m=1.,left_m=0.,yaw_rad=0.),target_v_mps=.2,target_w_rps=.3))))
        until(lambda:b.status_values['owner']==2 and b.status_values['applied_forward_norm']>0)
        assert n.phase=='running'
        n.readiness=lambda:'imu input stale'
        until(lambda:n.phase=='fault' and not b.status_values['auto_enabled'])
        assert b.status_values['applied_forward_norm']==0
        n.readiness=lambda:''
        for _ in range(20):executor.spin_once(timeout_sec=.01)
        assert n.phase=='fault' and not b.status_values['auto_enabled']
        executor.shutdown()
    finally:
        if b:b.close();b.destroy_node()
        if n:n.destroy_node()
        rclpy.shutdown();process.terminate();process.wait(timeout=3)
