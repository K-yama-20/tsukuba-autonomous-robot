import copy
import json
import math
import time
from unittest.mock import patch

import pytest
import rclpy
from rclpy.task import Future
from std_msgs.msg import String
from std_srvs.srv import SetBool
from gouda_navigation import autonomy_mvp as m
from gouda_navigation.autonomy_core import DEFAULT_SETTINGS
from gouda_navigation.mapping import DEFAULT_SETTINGS as MAPPING


class Arm:
    def __init__(self):self.calls=[]
    def service_is_ready(self):return True
    def call_async(self,req):
        self.calls.append(req.data)
        f=Future();f.set_result(SetBool.Response(success=True,message='sent'));return f


@pytest.fixture
def controller():
    cfg=copy.deepcopy(DEFAULT_SETTINGS)
    cfg.update(hardware_enabled=True,serial_port='/dev/ttyUSB0',body_to_lidar=dict(translation_m=[0,0,0],quaternion_xyzw=[0,0,0,1]))
    mapping={**MAPPING,'backend':'glim_imu','extrinsic_lidar_imu':cfg['body_to_lidar'],
        'point_time_field':'timestamp','point_time_datatype':'uint32','point_time_mode':'relative','point_time_unit':'nanoseconds',
        'imu_accel_unit':'m/s^2','imu_gyro_unit':'rad/s','imu_clock_offset_sec':0.,'lidar_clock_offset_sec':0.}
    rclpy.init()
    with patch.object(m,'load_autonomy_settings',return_value=cfg),patch.object(m,'load_mapping_settings',return_value=mapping):
        n=m.AutonomyMVP()
    n.arm=Arm();n.pose=(0.,0.,0.);n.estimate=dict(v_mps=0.,w_rps=0.)
    n.cloud=[(5.,5.,.5)];n.device=dict(boot_token=42,owner=0,connected=True,fresh=True,centered=True,auto_enabled=False)
    n.recording=True;n.fresh=lambda key:True;n.readiness=lambda:''
    yield n
    n.destroy_node();rclpy.shutdown()


def start(n,rid='start'):
    n.on_request(String(data=json.dumps(dict(action='start',request_id=rid,issued_at=n.stamp(),
        goal=dict(forward_m=1.,left_m=0.,yaw_rad=0.),target_v_mps=.2,target_w_rps=.3))))


def test_start_ack_manual_resume_keeps_goal_and_cancel(controller):
    n=controller
    start(n);assert n.phase=='arming' and n.arm.calls==[True]
    n.device['auto_enabled']=True;n.tick();assert n.phase=='running'
    goal=n.goal
    n.device['owner']=1;n.pose=(.2,.1,.1);n.tick()
    assert n.phase=='paused_manual' and n.goal==goal and n.arm.calls==[True]
    n.device['owner']=0;n.tick();assert n.phase=='paused_manual'
    n.resume_until=time.monotonic()-1;n.tick();assert n.phase=='running' and n.goal==goal
    n.on_request(String(data=json.dumps(dict(action='cancel',request_id='cancel',issued_at=n.stamp()))))
    assert n.phase=='cancelled' and n.arm.calls[-1] is False


def test_recording_loss_fault_does_not_auto_resume(controller):
    n=controller;start(n);n.device['auto_enabled']=True;n.tick()
    n.recording=False;n.tick();assert n.phase=='fault' and n.arm.calls[-1] is False
    n.recording=True;n.tick();assert n.phase=='fault'
    start(n);assert n.phase=='fault' # duplicate request is not an explicit retry


def test_sensor_loss_and_reboot_require_new_start(controller):
    n=controller;start(n);n.device['auto_enabled']=True;n.tick()
    n.device['boot_token']=99;n.tick();assert n.phase=='fault'
    n.device['auto_enabled']=False;start(n,'retry');assert n.phase=='arming'
    n.readiness=lambda:'imu input stale';n.tick();assert n.phase=='fault'


def test_obstacle_stops_auto_but_not_manual_ownership(controller):
    n=controller;start(n);n.device['auto_enabled']=True
    n.cloud=[(.60,.0,.5)];n.tick();assert n.phase=='blocked'
    n.device['owner']=1;n.tick();assert n.phase=='paused_manual'
    assert n.arm.calls==[True]


def test_relative_goal_uses_current_heading_and_reverse():
    c=DEFAULT_SETTINGS['controller']
    v,w,done=m.goal_reference((0,0,0),(-1,0,0),.2,.3,c)
    assert v<0 and abs(w)<1e-9 and not done
    v,w,done=m.goal_reference((0,0,0),(0,0,-1),.2,.3,c)
    assert v==0 and w<0 and not done
    assert m.goal_reference((0,0,0),(0,0,0),.2,.3,c)==(0.,0.,True)
