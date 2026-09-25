"""Explicit-start, mapless v/w feedback controller. No lateral command channel."""
import collections
import json
import math
import os
import numpy as np
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu, PointCloud2
from sensor_msgs_py import point_cloud2
from std_msgs.msg import String
from std_srvs.srv import SetBool

from .autonomy_core import (load_autonomy_settings, save_autonomy_settings,
    validate_autonomy_settings, compose_transforms, body_pose_from_lidar,
    estimate_body_twist, normalize_quaternion, rotate, AxisPI, obstacle_in_swept_envelope)
from .mapping import load_mapping_settings, validate_mapping_settings


def wrap(value):
    return math.atan2(math.sin(value), math.cos(value))


def goal_reference(pose, goal, speed, turn_speed, cfg):
    """Turn toward the shortest forward/reverse route, drive, then final heading."""
    x, y, yaw = pose
    dx, dy = goal[0]-x, goal[1]-y
    distance = math.hypot(dx, dy)
    if distance <= cfg['position_tolerance_m']:
        error = wrap(goal[2]-yaw)
        if abs(error) <= cfg['heading_tolerance_rad']:
            return 0., 0., True
        return 0., math.copysign(min(turn_speed, abs(error)), error), False
    bearing = wrap(math.atan2(dy, dx)-yaw)
    reverse = abs(bearing) > math.pi/2
    error = wrap(bearing-math.pi) if reverse else bearing
    w = max(-turn_speed, min(turn_speed, error))
    if abs(error) > .20:
        return 0., w, False
    return (-1 if reverse else 1)*min(speed, distance), w, False


class AutonomyMVP(Node):
    def __init__(self):
        super().__init__('gouda_autonomy_mvp')
        self.declare_parameter('gazebo_simulation',False)
        self.simulation=self.get_parameter('gazebo_simulation').value
        if self.get_parameter('use_sim_time').value and not self.simulation:
            raise RuntimeError('Autonomy cannot run with replay/simulation clock')
        self.cfg = load_autonomy_settings()
        self.mapping = load_mapping_settings()
        if self.simulation and (not self.get_parameter('use_sim_time').value or os.environ.get('ROS_DOMAIN_ID')!='101' or self.cfg.get('hardware_enabled') or self.cfg.get('simulation_fixture') is not True):
            raise RuntimeError('Gazebo requires isolated domain 101, simulation fixture, simulation clock and disabled hardware')
        checked_cfg={**self.cfg,'hardware_enabled':True,'serial_port':'/dev/ttyUSB0'} if self.simulation else self.cfg
        self.errors = validate_autonomy_settings(checked_cfg, require_ready=True)
        self.errors += validate_mapping_settings(self.mapping, require_ready=True)
        if self.mapping['backend'] != 'glim_imu':
            self.errors.append('GLIM + IMU must be selected')
        self.phase, self.reason = 'idle', ''
        self.goal = None
        self.request_id = ''
        self.seen = collections.deque(maxlen=256)
        self.odom = self.imu = self.cloud = self.device = None
        self.stamps, self.received = {}, {}
        self.imu_history=collections.deque(maxlen=1000)
        self.last_tick = time.monotonic()
        self.arm_future = None
        self.arm_deadline = 0.
        self.disarm_sent = False
        self.armed_once = False
        self.active_boot = None
        self.manual = False
        self.last_auto = False
        self.resume_until = 0.
        self.pose = self.estimate = None
        self.target_v, self.target_w = 0., 0.
        self.ref = (0., 0.)
        self.t_bl = self.q_bl = self.t_bi = self.q_bi = None
        if not self.errors:
            bl, li = self.cfg['body_to_lidar'], self.mapping['extrinsic_lidar_imu']
            self.t_bl, self.q_bl = bl['translation_m'], bl['quaternion_xyzw']
            self.t_bi, self.q_bi = compose_transforms(self.t_bl,self.q_bl,li['translation_m'],li['quaternion_xyzw'])
        c = self.cfg['controller']
        self.vpi = AxisPI(c['linear_ff_norm_per_mps'],c['linear_kp_norm_per_mps'],c['linear_ki_norm_per_mps_s'],c['integral_limit_norm'])
        self.wpi = AxisPI(c['yaw_ff_norm_per_rps'],c['yaw_kp_norm_per_rps'],c['yaw_ki_norm_per_rps_s'],c['integral_limit_norm'])
        self.state_pub = self.create_publisher(String,'/gouda/autonomy/state',10)
        self.drive_pub = self.create_publisher(String,'/gouda/control/drive',10)
        self.ref_pub = self.create_publisher(String,'/gouda/control/reference',10)
        self.estimate_pub = self.create_publisher(String,'/gouda/control/estimate',10)
        self.arm = self.create_client(SetBool,'/gouda/arm')
        self.create_subscription(String,'/gouda/autonomy/request',self.on_request,10)
        self.recording = False
        self.create_subscription(String,'/gouda/recording/state',self.on_recording,10)
        self.create_subscription(String,'/esp32/status',self.on_device,10)
        self.create_subscription(Odometry,'/glim_ros/lidar_odom',self.on_odom,10)
        self.create_subscription(Imu,self.mapping['imu_topic'],self.on_imu,qos_profile_sensor_data)
        self.create_subscription(PointCloud2,self.mapping['lidar_topic'],self.on_cloud,qos_profile_sensor_data)
        self.timer = self.create_timer(.05,self.tick)

    def stamp(self):
        s=self.get_clock().now().to_msg()
        return {'sec':s.sec,'nanosec':s.nanosec}

    @staticmethod
    def publish(pub, data):
        pub.publish(String(data=json.dumps(data,allow_nan=False,separators=(',',':'))))

    def receive_sensor(self,key,msg,offset=0.):
        stamp=msg.header.stamp.sec+msg.header.stamp.nanosec/1e9+offset
        if not math.isfinite(stamp) or stamp <= self.stamps.get(key,-math.inf):
            return False
        self.stamps[key]=stamp;self.received[key]=time.monotonic()
        return True

    def on_odom(self,msg):
        if msg.child_frame_id != self.mapping['lidar_frame'] or msg.header.frame_id != 'odom_lidar':
            return
        p,q,v=msg.pose.pose.position,msg.pose.pose.orientation,msg.twist.twist.linear
        if not all(math.isfinite(a) for a in (p.x,p.y,p.z,q.x,q.y,q.z,q.w,v.x,v.y,v.z)):
            return
        if not .999 <= math.sqrt(q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w) <= 1.001:
            return
        if self.receive_sensor('pose',msg):self.odom=msg

    def on_imu(self,msg):
        a=msg.angular_velocity
        if msg.header.frame_id != self.mapping['imu_frame'] or not all(math.isfinite(v) for v in (a.x,a.y,a.z)):
            return
        if msg.angular_velocity_covariance[0] == -1:return
        if self.receive_sensor('imu',msg,self.mapping.get('imu_clock_offset_sec') or 0.):
            self.imu=msg;self.imu_history.append((self.stamps['imu'],msg))

    def on_cloud(self,msg):
        if msg.header.frame_id != self.mapping['lidar_frame'] or not msg.width*msg.height:return
        try:
            points=point_cloud2.read_points_numpy(msg,field_names=('x','y','z'),skip_nans=True).reshape(-1,3)
            points=points[np.isfinite(points).all(axis=1)]
            if not len(points):return
        except (ValueError,AssertionError,KeyError):return
        if self.receive_sensor('cloud',msg,self.mapping.get('lidar_clock_offset_sec') or 0.):self.cloud=points

    def on_recording(self,msg):
        try:
            d=json.loads(msg.data);self.recording=d.get("active") is True
            self.received["recording"]=time.monotonic()
        except (ValueError,TypeError):return

    def on_device(self,msg):
        try:
            d=json.loads(msg.data)
            if bool(d.get('simulation')) != self.simulation:return
            if type(d.get('boot_token')) is not int or d.get('owner') not in (0,1,2):return
            self.device=d;self.received['device']=time.monotonic()
        except (ValueError,TypeError):return

    def fresh(self,key):
        if key not in self.received:return False
        age=time.monotonic()-self.received[key]
        if key=='device':return age < .25
        if key=='recording':return age < 1.
        ros_age=self.get_clock().now().nanoseconds/1e9-self.stamps[key]
        return age<=self.cfg['max_sensor_age_sec'] and -.05<=ros_age<=self.cfg['max_sensor_age_sec']

    def aligned_imu(self):
        if not self.imu_history or 'pose' not in self.stamps:return None
        stamp,msg=min(self.imu_history,key=lambda entry:abs(entry[0]-self.stamps['pose']))
        return (stamp,msg) if abs(stamp-self.stamps['pose'])<=self.cfg['max_sensor_skew_sec'] else None

    def readiness(self):
        if self.errors:return '; '.join(self.errors)
        for key in ('pose','imu','cloud','device'):
            if not self.fresh(key):return key+' input missing or stale'
        if self.aligned_imu() is None:
            return 'No IMU sample aligned with LiDAR odometry timestamp'
        if not self.device.get('connected') or not self.device.get('fresh'):
            return 'Manual controller disconnected or stale'
        return ''

    def update_estimate(self):
        if self.errors or self.odom is None or self.imu is None:return
        p,q,v=self.odom.pose.pose.position,self.odom.pose.pose.orientation,self.odom.twist.twist.linear
        pb,qb=body_pose_from_lidar((p.x,p.y,p.z),(q.x,q.y,q.z,q.w),self.t_bl,self.q_bl)
        aligned=self.aligned_imu()
        if aligned is None:return
        aligned_stamp,aligned_msg=aligned
        gyro=aligned_msg.angular_velocity
        scale=math.pi/180 if self.mapping['imu_gyro_unit']=='deg/s' else 1.
        vb,wb=estimate_body_twist((v.x,v.y,v.z),tuple(a*scale for a in (gyro.x,gyro.y,gyro.z)),qb,self.t_bi,self.q_bi,self.cfg['imu_gyro_bias_body_rad_s'])
        x,y,z,w=qb
        self.pose=(pb[0],pb[1],math.atan2(2*(w*z+x*y),1-2*(y*y+z*z)))
        current=self.imu.angular_velocity
        current_w=rotate(self.q_bi,tuple(a*scale for a in (current.x,current.y,current.z)))
        current_w=tuple(current_w[i]-self.cfg['imu_gyro_bias_body_rad_s'][i] for i in range(3))
        self.estimate={'v_mps':vb[0],'lateral_mps':vb[1],'w_rps':current_w[2],
            'translation_stamp':self.stamps['pose'],'aligned_imu_stamp':aligned_stamp,'yaw_stamp':self.stamps['imu']}

    def disarm(self):
        if not self.disarm_sent and self.arm.service_is_ready():
            self.arm.call_async(SetBool.Request(data=False));self.disarm_sent=True

    def halt(self,phase,reason):
        self.phase,self.reason=phase,reason
        self.disarm_sent=False;self.disarm()
        self.vpi.reset();self.wpi.reset()

    def on_request(self,msg):
        try:
            d=json.loads(msg.data);rid=d['request_id'];s=d['issued_at']
            if not isinstance(rid,str) or not rid or len(rid)>80 or rid in self.seen:return
            if type(s['sec']) is not int or type(s['nanosec']) is not int or not 0<=s['nanosec']<1_000_000_000:return
            age=self.get_clock().now().nanoseconds/1e9-s['sec']-s['nanosec']/1e9
            if not -.05<=age<=2.:return
            self.seen.append(rid)
            if d['action']=='cancel':self.halt('cancelled','User cancelled');return
            if d['action']!='start' or self.phase not in ('idle','cancelled','completed','fault'):return
            reason=self.readiness()
            if not self.recording or not self.fresh('recording'):reason='Raw recording is not active'
            if reason:self.reason=reason;return
            if self.device['owner']==1 or not self.device.get('centered'):
                self.reason='Center manual controller before starting';return
            self.update_estimate()
            g=d['goal'];vals=[g[k] for k in ('forward_m','left_m','yaw_rad')]+[d['target_v_mps'],d['target_w_rps']]
            if not all(type(v) in (int,float) and math.isfinite(v) for v in vals) or min(vals[3:])<=0:return
            if not self.arm.service_is_ready():self.reason='USB ARM service unavailable';return
            x,y,a=self.pose;f,l,h=vals[:3]
            self.goal=(x+math.cos(a)*f-math.sin(a)*l,y+math.sin(a)*f+math.cos(a)*l,wrap(a+h))
            self.target_v,self.target_w=vals[3:];self.request_id=rid
            self.phase,self.reason='arming','Waiting for ESP32 ARM acknowledgement'
            self.active_boot=self.device['boot_token'];self.armed_once=False
            self.disarm_sent=False;self.arm_deadline=time.monotonic()+1.
            self.vpi.reset();self.wpi.reset()
            self.arm_future=self.arm.call_async(SetBool.Request(data=True))
        except (ValueError,KeyError,TypeError,OverflowError):return

    def tick(self):
        now=time.monotonic();dt=min(.1,now-self.last_tick);self.last_tick=now
        self.update_estimate()
        self.manual=bool(self.fresh('device') and self.device.get('owner')==1)
        active=self.phase in ('arming','running','paused_manual','blocked')
        reason=self.readiness()
        if active and (not self.recording or not self.fresh('recording')):reason='Raw recording stopped or status stale'
        if active and reason:self.halt('fault',reason);active=False
        if active and self.device['boot_token']!=self.active_boot:
            self.halt('fault','ESP32 restarted; explicit start required');active=False
        if self.phase=='arming':
            if self.arm_future.done() and (self.arm_future.exception() or not self.arm_future.result().success):
                self.halt('fault','ESP32 ARM request rejected')
            elif self.device.get('auto_enabled'):
                self.phase,self.reason='running','';self.armed_once=True
            elif now>self.arm_deadline:self.halt('fault','ESP32 ARM acknowledgement timeout')
        elif active and not self.device.get('auto_enabled'):
            self.halt('fault','ESP32 disabled autonomy; explicit start required')
        v=w=forward=yaw=0.
        if self.phase in ('running','paused_manual','blocked'):
            v,w,done=goal_reference(self.pose,self.goal,self.target_v,self.target_w,self.cfg['controller'])
            if self.manual:
                self.phase,self.reason='paused_manual','Manual owns both axes; goal retained'
                self.vpi.reset();self.wpi.reset();self.resume_until=now+.2
            elif now<self.resume_until:
                self.phase,self.reason='paused_manual','Waiting for centered controller to settle'
            elif done and abs(self.estimate['v_mps'])<.03 and abs(self.estimate['w_rps'])<.05:
                self.halt('completed','Relative goal reached')
            else:
                blocked=obstacle_in_swept_envelope(self.cloud,self.t_bl,self.q_bl,self.cfg['footprint'],self.cfg['obstacle_min_height_m'],
                    'turn' if abs(v)<1e-6 else ('forward' if v>0 else 'reverse'),
                    forward_distance=abs(self.estimate['v_mps'])*.5+.10)
                if blocked:
                    self.phase,self.reason='blocked','Obstacle in body swept volume';self.vpi.reset();self.wpi.reset()
                else:
                    self.phase,self.reason='running',''
                    forward=self.vpi.update(v,self.estimate['v_mps'],dt)
                    yaw=self.wpi.update(w,self.estimate['w_rps'],dt)
        if self.phase not in ('running','paused_manual','blocked','arming'):self.disarm()
        enabled=self.phase in ('running','paused_manual','blocked')
        self.ref=(v,w)
        stamp=self.stamp()
        self.publish(self.drive_pub,dict(issued_at=stamp,request_id=self.request_id,forward_norm=forward,yaw_left_norm=yaw,enable_requested=enabled))
        reference=dict(issued_at=stamp,request_id=self.request_id,v_mps=v,w_rps=w,phase=self.phase)
        self.publish(self.ref_pub,reference)
        if self.estimate:self.publish(self.estimate_pub,dict(issued_at=stamp,**self.estimate,sensor_stamps=self.stamps,valid=not bool(reason)))
        self.publish(self.state_pub,dict(phase=self.phase,reason=self.reason or reason,goal=self.goal,request_id=self.request_id,
            recording_active=self.recording and self.fresh('recording'),manual_override=self.manual,command_ref=dict(v_mps=v,w_rps=w),estimate=self.estimate if not reason else None,
            pose=self.pose,pose_fresh=self.fresh('pose'),imu_fresh=self.fresh('imu'),cloud_fresh=self.fresh('cloud'),
            calibration_ready=not bool(self.errors),device_fresh=self.fresh('device'),emergency_stop_readback='unknown',
            configuration={'autonomy':self.cfg,'mapping':self.mapping}))


def main():
    rclpy.init();node=AutonomyMVP()
    try:rclpy.spin(node)
    except KeyboardInterrupt:pass
    finally:
        if rclpy.ok():node.disarm()
        node.destroy_node()
        if rclpy.ok():rclpy.shutdown()
