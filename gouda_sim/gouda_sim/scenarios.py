"""Repeatable Gazebo-only acceptance. Produces a JSON report; never opens USB."""
import json
import fcntl
import math
import os
import time
import uuid
from pathlib import Path
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry

class Scenarios(Node):
    def __init__(self):
        super().__init__('gouda_sim_scenarios')
        if os.environ.get('ROS_DOMAIN_ID')!='101' or not self.get_parameter('use_sim_time').value:
            raise RuntimeError('Gazebo-only domain and clock required')
        self.declare_parameter('suite','full')
        if self.get_parameter('suite').value not in ('full','motion'):raise ValueError('suite must be full or motion')
        self.declare_parameter('report','/tmp/gouda-gazebo-report.json')
        self.truth=None;self.truth_goal=None;self.state=None;self.device=None;self.received=0;self.recording=False;self.results=[];self.trajectory=[]
        self.request=self.create_publisher(String,'/gouda/autonomy/request',10)
        self.manual=self.create_publisher(Twist,'/sim/manual',10)
        self.fault=self.create_publisher(String,'/sim/fault',10)
        self.create_subscription(Odometry,'/sim/odometry',self.on_truth,10)
        self.create_subscription(String,'/gouda/autonomy/state',self.on_state,10)
        self.create_subscription(String,'/esp32/status',lambda m:setattr(self,'device',json.loads(m.data)),10)
        self.create_subscription(String,'/gouda/recording/state',lambda m:setattr(self,'recording',json.loads(m.data).get('active') is True),10)
    def on_truth(self,msg):
        p=msg.pose.pose.position;q=msg.pose.pose.orientation
        self.truth=[p.x,p.y,math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))]

    def on_state(self,msg):
        self.state=json.loads(msg.data);self.received=time.monotonic()
        if self.state.get('pose'):self.trajectory.append(dict(time_sec=self.get_clock().now().nanoseconds/1e9,pose=self.state['pose'],truth_pose=self.truth,phase=self.state['phase']))
    def wait(self,check,timeout=120):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            rclpy.spin_once(self,timeout_sec=.02)
            if check():return
        raise RuntimeError('Timeout: '+json.dumps(self.state,ensure_ascii=False))
    def request_goal(self,f=0.,l=0.,yaw=0.,action='start'):
        stamp=self.get_clock().now().to_msg();rid=uuid.uuid4().hex
        self.request.publish(String(data=json.dumps(dict(action=action,request_id=rid,issued_at=dict(sec=stamp.sec,nanosec=stamp.nanosec),goal=dict(forward_m=f,left_m=l,yaw_rad=yaw),target_v_mps=.25,target_w_rps=.35))))
        return rid
    def start(self,*args):
        self.wait(lambda:self.state and not self.state.get('reason') and self.recording and self.state['phase'] in ('idle','completed','cancelled','fault')) if self.state is None else None
        if self.truth:
            x,y,a=self.truth;f,l,h=args
            self.truth_goal=[x+math.cos(a)*f-math.sin(a)*l,y+math.sin(a)*f+math.cos(a)*l,a+h]
        rid=self.request_goal(*args)
        self.wait(lambda:self.state['request_id']==rid,10)
        self.wait(lambda:self.state['phase'] not in ('arming','idle'),10)
        if self.state['phase']=='fault':raise RuntimeError(self.state['reason'])
    def complete(self,name):
        self.wait(lambda:self.state['phase'] in ('completed','fault','blocked'))
        if self.state['phase']!='completed':raise RuntimeError(name+': '+self.state['reason'])
        p,g=self.state['pose'],self.state['goal']
        error=math.hypot(p[0]-g[0],p[1]-g[1])
        truth_error=math.hypot(self.truth[0]-self.truth_goal[0],self.truth[1]-self.truth_goal[1]) if self.truth and self.truth_goal else None
        self.results.append(dict(case=name,passed=True,position_error_m=error,goal=g,pose=p,truth_pose=self.truth,truth_goal=self.truth_goal,truth_position_error_m=truth_error))
        print(name,'PASS',round(error,4),flush=True)
    def cancel(self):
        self.request_goal(action='cancel');self.wait(lambda:self.state['phase']=='cancelled',10)
    def run(self):
        self.wait(lambda:self.state and self.recording and self.state['pose_fresh'] and self.state['imu_fresh'] and self.state['cloud_fresh'] and self.state.get('recording_active'))
        settle=self.get_clock().now().nanoseconds/1e9+2.
        self.wait(lambda:self.get_clock().now().nanoseconds/1e9>=settle and self.state.get('recording_active'))
        self.start(.6,0.,0.);self.complete('forward')
        self.start(-.3,0.,0.);self.complete('reverse')
        self.start(0.,0.,.4);self.complete('left_rotation')
        self.start(0.,0.,-.4);self.complete('right_rotation')
        self.start(.6,0.,0.)
        goal=self.state['goal']
        manual=Twist();manual.angular.z=.2;self.manual.publish(manual)
        self.wait(lambda:self.state['manual_override'],10)
        assert self.state['goal']==goal
        self.manual.publish(Twist());self.complete('manual_override_resume')
        if self.get_parameter('suite').value=='full':
            self.start(.5,0.,0.)
            self.fault.publish(String(data='{"imu_loss":true}'))
            self.wait(lambda:self.state['phase']=='fault',15)
            self.fault.publish(String(data='{"imu_loss":false}'))
            self.wait(lambda:self.state['imu_fresh'],10)
            assert self.state['phase']=='fault'
            self.results.append(dict(case='imu_loss_no_auto_resume',passed=True));print('imu_loss PASS',flush=True)
            self.cancel()
            self.start(.5,0.,0.)
            self.fault.publish(String(data='{"pc_loss":true}'))
            self.wait(lambda:self.state['phase']=='fault',10)
            self.fault.publish(String(data='{"pc_loss":false}'))
            self.results.append(dict(case='pc_loss',passed=True));print('pc_loss PASS',flush=True)
            self.cancel()
            for fault_name in ('lidar_loss','bt_loss'):
                self.start(.3,0.,0.)
                self.fault.publish(String(data=json.dumps({fault_name:True})))
                self.wait(lambda:self.state['phase']=='fault',15)
                self.fault.publish(String(data=json.dumps({fault_name:False})))
                self.wait(lambda:self.state['cloud_fresh'] and self.device and self.device.get('fresh'),10)
                self.results.append(dict(case=fault_name,passed=True));print(fault_name,'PASS',flush=True)
                self.cancel()
        self.start(6.,0.,0.)
        self.wait(lambda:self.state['phase'] in ('blocked','fault'),120)
        assert self.state['phase']=='blocked',self.state['reason']
        self.wait(lambda:abs(self.state.get('estimate',{}).get('v_mps',1))<.03,15)
        x,y,a=self.truth
        clearance=4.8-(x+abs(math.cos(a))*.5525+abs(math.sin(a))*.3)
        assert clearance>0,'Body overlaps obstacle'
        self.results.append(dict(case='obstacle_stop',passed=True,pose=self.state['pose'],front_clearance_m=clearance));print('obstacle_stop PASS',flush=True)
        self.cancel()

def main():
    lock=open('/tmp/gouda-scenario-101.lock','a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    rclpy.init();node=Scenarios();failure=None
    try:node.run()
    except Exception as exc:failure=str(exc);print('FAILED:',failure,flush=True)
    finally:
        if rclpy.ok():node.manual.publish(Twist());node.request_goal(action='cancel')
        path=Path(node.get_parameter('report').value);path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(dict(simulation=True,results=node.results,trajectory=node.trajectory,passed=failure is None,error=failure),ensure_ascii=False,indent=2)+'\n')
        node.destroy_node()
        if rclpy.ok():rclpy.shutdown()
    if failure:raise SystemExit(1)
