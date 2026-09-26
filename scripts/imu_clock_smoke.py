#!/usr/bin/env python3
"""Real patched ROS driver against a PTY IMU; never opens a hardware serial port."""
import argparse
import importlib.util
import json
from pathlib import Path
import signal
import struct
import subprocess
import time


def main():
    p=argparse.ArgumentParser();p.add_argument('--driver-source',type=Path,required=True);p.add_argument('--executable',required=True)
    a=p.parse_args()
    spec=importlib.util.spec_from_file_location('fake_imu',a.driver_source/'src/test/fake_imu.py')
    fake=importlib.util.module_from_spec(spec);spec.loader.exec_module(fake)
    original=fake.make_telemetry_payload
    state={'origin':time.monotonic(),'freeze':False,'last':None}
    def payload(send_counter=0,**kw):
        if state['freeze'] and state['last'] is not None:return state['last']
        data=bytearray(original(send_counter,**kw))
        struct.pack_into('<Q',data,48,int((time.monotonic()-state['origin'])*1e6))
        state['last']=bytes(data);return state['last']
    fake.make_telemetry_payload=payload
    device=fake.FakeImu(stream_hz=200);device.start()
    assert device.device.startswith('/dev/pts/')
    import rclpy
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import Imu,TimeReference
    from std_msgs.msg import String
    rclpy.init();node=rclpy.create_node('imu_clock_pty_test')
    imus=[];statuses=[];refs=[]
    node.create_subscription(Imu,'/imu/data_raw',imus.append,qos_profile_sensor_data)
    node.create_subscription(String,'/imu/clock_status',lambda m:statuses.append(json.loads(m.data)),1000)
    node.create_subscription(TimeReference,'/imu/time_reference',refs.append,1000)
    log=Path('/tmp/gouda-imu-clock-pty.log').open('w')
    child=subprocess.Popen([a.executable,'--ros-args','-p',f'device:={device.device}','-p','publish_tf:=false'],stdout=log,stderr=log)
    def spin(seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:rclpy.spin_once(node,timeout_sec=.01)
    def until(condition,seconds=12):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            spin(.05)
            if condition():return
            if child.poll() is not None:raise AssertionError('driver exited')
        raise AssertionError(f'timeout imus={len(imus)} status={statuses[-1:]}; inspect /tmp/gouda-imu-clock-pty.log')
    def seconds(stamp):return stamp.sec+stamp.nanosec/1e9
    try:
        until(lambda:len(imus)>15)
        assert any(s['state']=='unlocked' for s in statuses)
        assert any(s['state']=='host_mapped' for s in statuses)
        state['freeze']=True
        spin(.2)
        for m in imus[-10:]:
            t=seconds(m.header.stamp)
            found=[s for s in statuses if abs(s['measurement_stamp']-t)<1e-6]
            assert found and found[-1]['state']=='host_mapped', (t, statuses[-3:])
            assert found[-1]['hardware_synchronized'] is False
            assert found[-1]['timestamp_basis']=='mcu_data_ready_acquisition'
            assert any(abs(seconds(ref.time_ref)-t)<1e-6 for ref in refs)
        assert all(seconds(a.header.stamp)<seconds(b.header.stamp) for a,b in zip(imus,imus[1:]))
        state['freeze']=True;spin(.15);count=len(imus);spin(.2)
        assert len(imus)==count,'duplicate IMU sample was republished'
        state['origin']=time.monotonic();state['freeze']=False
        status_start=len(statuses)
        until(lambda:any(s['state']=='unlocked' for s in statuses[status_start:]),3)
        until(lambda:len(imus)>count+15)
        print(json.dumps({'result':'passed','imu_samples':len(imus),'clock_status_samples':len(statuses),
            'checks':['unlocked withholds IMU','epoch precision preserved','TimeReference pairs','duplicates suppressed','MCU restart relocks'],
            'hardware_used':False},indent=2))
    finally:
        child.send_signal(signal.SIGINT)
        try:child.wait(timeout=5)
        except subprocess.TimeoutExpired:child.kill();child.wait()
        device.stop();node.destroy_node();rclpy.shutdown();log.close()

if __name__=='__main__':main()

