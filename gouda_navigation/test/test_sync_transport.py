"""ROS integration: exact measurement stamps preserved, invalid evidence withheld."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import pytest


def test_sync_gate_ros_transport(tmp_path):
    import rclpy
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import Imu, PointField, PointCloud2
    from sensor_msgs_py.point_cloud2 import create_cloud
    from std_msgs.msg import Header, String
    from gouda_navigation.mapping import DEFAULT_SETTINGS
    root=tmp_path/'bags/gouda';root.mkdir(parents=True)
    config=root/'hesai.yaml';config.write_text('lidar:\n- driver:\n    source_type: 1\n    use_timestamp_type: 0\n')
    (root/'host.json').write_text(json.dumps(dict(hesai_config=str(config))))
    settings={**DEFAULT_SETTINGS,'backend':'glim_imu','clock_policy':'host_mapped','clock_evidence':'Synthetic transport test only',
      'point_time_field':'time','point_time_datatype':'float64','point_time_mode':'relative','point_time_unit':'seconds',
      'imu_accel_unit':'m/s^2','imu_gyro_unit':'rad/s','imu_clock_offset_sec':0.,'lidar_clock_offset_sec':0.,
      'extrinsic_lidar_imu':dict(translation_m=[0,0,0],quaternion_xyzw=[0,0,0,1])}
    path=root/'mapping.json';path.write_text(json.dumps(settings))
    log=(tmp_path/'gate.log').open('w')
    env=dict(os.environ,GOUDA_WORKSPACE=str(tmp_path))
    p=subprocess.Popen([sys.executable,'-c','from gouda_navigation.time_sync import main; main()',
        '--ros-args','-p',f'settings_file:={path}'],env=env,stdout=log,stderr=log)
    rclpy.init();n=rclpy.create_node('clock_gate_transport_test')
    imus=[];clouds=[];states=[]
    n.create_subscription(Imu,'/gouda/synced/imu',imus.append,qos_profile_sensor_data)
    n.create_subscription(PointCloud2,'/gouda/synced/points',clouds.append,qos_profile_sensor_data)
    n.create_subscription(String,'/gouda/time_sync/state',lambda m:states.append(json.loads(m.data)),10)
    ip=n.create_publisher(Imu,'/imu/data_raw',qos_profile_sensor_data)
    cp=n.create_publisher(PointCloud2,'/lidar_points',qos_profile_sensor_data)
    sp=n.create_publisher(String,'/imu/clock_status',1000)
    def spin(seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:rclpy.spin_once(n,timeout_sec=.01)
    try:
        end=time.monotonic()+8
        while ip.get_subscription_count()==0 and time.monotonic()<end:spin(.05)
        assert p.poll() is None and ip.get_subscription_count()>0
        imu=Imu(header=Header(frame_id='imu_link',stamp=n.get_clock().now().to_msg()))
        ip.publish(imu);spin(.3);assert not imus
        imu.header.stamp=n.get_clock().now().to_msg()
        t=imu.header.stamp.sec+imu.header.stamp.nanosec/1e9
        # Deliver IMU first to verify cross-topic reorder buffering.
        ip.publish(imu);spin(.03)
        sp.publish(String(data=json.dumps(dict(state='host_mapped',measurement_stamp=t,residual_ms=.1))))
        spin(.08);assert len(imus)==1 and imus[0].header.stamp==imu.header.stamp
        fields=[PointField(name='time',offset=0,datatype=8,count=1)]
        cloud=create_cloud(Header(frame_id='hesai_lidar',stamp=imu.header.stamp),fields,[(0.,),(.01,)])
        cp.publish(cloud);spin(.1)
        assert len(clouds)==1 and clouds[0].data==cloud.data and clouds[0].header==cloud.header
        bad=create_cloud(Header(frame_id='hesai_lidar',stamp=n.get_clock().now().to_msg()),fields,[(float('nan'),)])
        cp.publish(bad);spin(.3);assert len(clouds)==1
        assert states and not states[-1]['hardware_synchronized']
        assert states[-1]['status']=='blocked'
    finally:
        n.destroy_node();rclpy.shutdown()
        p.terminate()
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:p.kill();p.wait()
        log.close()
    assert 'Traceback' not in (tmp_path/'gate.log').read_text()

