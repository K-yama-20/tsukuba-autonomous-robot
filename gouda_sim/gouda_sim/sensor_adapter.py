"""Gazebo sensor conversion. Ground truth is explicitly tagged, never a GLIM result."""
import copy
import json
import os
import numpy as np
from sensor_msgs_py import point_cloud2
from std_msgs.msg import Header
from .raycast import scan
from pathlib import Path
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu, PointCloud2, PointField
from std_msgs.msg import String
from gouda_navigation.autonomy_core import rotate

class Adapter(Node):
    def __init__(self):
        super().__init__('gouda_sim_sensor_adapter')
        if os.environ.get('ROS_DOMAIN_ID')!='101' or not self.get_parameter('use_sim_time').value:
            raise RuntimeError('Gazebo domain 101 and simulation clock required')
        self.declare_parameter('estimator','ground_truth')
        self.mode=self.get_parameter('estimator').value
        if self.mode not in ('ground_truth','glim'):raise ValueError('Invalid estimator')
        self.declare_parameter('lidar_backend','cpu_ray')
        self.lidar_backend=self.get_parameter('lidar_backend').value
        self.truth=None;self.rng=np.random.default_rng(270)
        if self.lidar_backend=='cpu_ray':self.create_timer(.1,self.cpu_scan)
        self.faults={}
        self.glim=None
        from gouda_gui.recording import RecordingManager
        self.recorder=RecordingManager(use_sim_time=True)
        config=self.recorder.get_config()
        config['topics']=list(dict.fromkeys(config['topics']+['/sim/odometry','/sim/manual','/sim/fault','/sim/estimator','/clock']))
        self.recorder.update_config(config)
        self.recorder.start()
        self.recording_pub=self.create_publisher(String,'/gouda/recording/state',10)
        self.create_timer(.2,self.recording_status)
        self.odom=self.create_publisher(Odometry,'/glim_ros/lidar_odom',10) if self.mode=='ground_truth' else None
        self.imu=self.create_publisher(Imu,'/imu/data_raw',qos_profile_sensor_data)
        self.cloud=self.create_publisher(PointCloud2,'/lidar_points',qos_profile_sensor_data)
        self.create_subscription(Odometry,'/sim/odometry',self.on_odom,10)
        self.create_subscription(Imu,'/sim/imu',self.on_imu,qos_profile_sensor_data)
        self.create_subscription(PointCloud2,'/sim/points',self.on_cloud,qos_profile_sensor_data)
        self.create_subscription(String,'/sim/fault',self.on_fault,10)
        self.info=self.create_publisher(String,'/sim/estimator',10)
        self.create_timer(.5,lambda:self.info.publish(String(data=json.dumps(dict(estimator=self.mode,ground_truth=self.mode=='ground_truth',simulation=True)))))
    def recording_status(self):
        s=self.recorder.status()
        active=s.get("phase") in ("awaiting_sensor_data","recording","no_sensor_data") and s.get("return_code") is None
        self.recording_pub.publish(String(data=json.dumps(dict(active=active,simulation=True))))

    def on_fault(self,msg):
        try:
            d=json.loads(msg.data)
            for k in ('imu_loss','lidar_loss','odom_loss'):
                if k in d and type(d[k]) is bool:self.faults[k]=d[k]
        except (ValueError,TypeError):pass
    def on_imu(self,msg):
        if self.faults.get('imu_loss'):return
        msg.header.frame_id='imu_link';self.imu.publish(msg)
    def on_odom(self,msg):
        self.truth=copy.deepcopy(msg)
        if self.odom is None or self.faults.get('odom_loss'):return
        msg=copy.deepcopy(msg);msg.header.frame_id='odom_lidar';msg.child_frame_id='hesai_lidar'
        q=msg.pose.pose.orientation;qv=(q.x,q.y,q.z,q.w)
        offset=rotate(qv,(0,0,1.1));p=msg.pose.pose.position
        p.x+=offset[0];p.y+=offset[1];p.z+=offset[2]
        v=msg.twist.twist.linear;w=msg.twist.twist.angular
        v.x,v.y,v.z=rotate(qv,(v.x+.5*w.y,v.y-.5*w.x,v.z))
        self.odom.publish(msg)
    def cpu_scan(self):
        if self.truth is None or self.faults.get('lidar_loss'):return
        m=self.truth;q=m.pose.pose.orientation;p=m.pose.pose.position
        rotation=np.asarray([rotate((q.x,q.y,q.z,q.w),axis) for axis in ((1,0,0),(0,1,0),(0,0,1))]).T
        origin=np.asarray((p.x,p.y,p.z))+rotation@np.asarray((0,0,1.1))
        points=scan(origin,rotation,self.rng)
        h=Header();h.stamp=m.header.stamp;h.frame_id='hesai_lidar'
        cloud=point_cloud2.create_cloud_xyz32(h,points)
        self.on_cloud(cloud)

    def on_cloud(self,msg):
        if self.faults.get('lidar_loss'):return
        msg=copy.deepcopy(msg);msg.header.frame_id='hesai_lidar'
        if not any(f.name=='time' for f in msg.fields):
            old=msg.point_step;new=old+4;data=bytearray(msg.width*msg.height*new)
            for row in range(msg.height):
                for col in range(msg.width):
                    src=row*msg.row_step+col*old;dst=(row*msg.width+col)*new
                    data[dst:dst+old]=msg.data[src:src+old]
            msg.fields.append(PointField(name='time',offset=old,datatype=PointField.FLOAT32,count=1))
            msg.point_step=new;msg.row_step=msg.width*new;msg.data=bytes(data)
        self.cloud.publish(msg)

def main():
    rclpy.init();node=Adapter()
    try:rclpy.spin(node)
    except KeyboardInterrupt:pass
    finally:
        node.recorder.close()
        if node.glim:node.glim.stop(wait=True)
        node.destroy_node()
        if rclpy.ok():rclpy.shutdown()
