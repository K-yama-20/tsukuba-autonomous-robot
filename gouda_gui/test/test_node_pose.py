import math
import threading
from types import SimpleNamespace as NS
import pytest

pytest.importorskip('rclpy')
try:
    from gouda_gui.node import MissionControl
except ImportError as exc:
    pytest.skip(f'ROS GUI runtime dependencies are unavailable: {exc}', allow_module_level=True)


def quaternion_yaw(angle):
    return NS(x=0.,y=0.,z=math.sin(angle/2),w=math.cos(angle/2))


def pose_msg(frame, x, y, yaw=0.):
    return NS(header=NS(frame_id=frame,stamp=NS(sec=1,nanosec=0)),
              child_frame_id='hesai_lidar',
              pose=NS(pose=NS(position=NS(x=x,y=y,z=0.),orientation=quaternion_yaw(yaw))),
              twist=NS(twist=NS(linear=NS(x=0.2),angular=NS(z=0.1))))


class FakeTransformBuffer:
    def __init__(self, transform=None):self.transform=transform;self.lookups=0
    def lookup_transform(self,target,source,stamp):
        self.lookups+=1
        assert (target,source)==('map','odom_lidar')
        if self.transform is None:
            from tf2_ros import TransformException
            raise TransformException('not available')
        return self.transform


def fake_node(status='mapping',transform=None):
    node=MissionControl.__new__(MissionControl)
    node.observation_only=True;node.effective_mapping_backend='glim_imu'
    node.runtime_mapping_settings={'lidar_frame':'hesai_lidar'}
    node.slam=NS(status=lambda:status);node.tf=FakeTransformBuffer(transform)
    node.lock=threading.RLock();node.pose=None;node.pose_frame='odom_lidar';node.times={};node.trail=[]
    node.get_clock=lambda:NS(now=lambda:NS(nanoseconds=1_000_000_000))
    return node


def test_glim_odom_callback_maps_live_pose_during_2d_mapping():
    transform=NS(transform=NS(translation=NS(x=10.,y=2.,z=0.),
                             rotation=quaternion_yaw(math.pi/2)))
    node=fake_node(status='mapping',transform=transform)
    node.on_glim_odom(pose_msg('odom_lidar',1.,0.))
    assert node.pose['x']==pytest.approx(10.)
    assert node.pose['y']==pytest.approx(3.)
    assert node.pose['yaw']==pytest.approx(math.pi/2)
    assert node.pose_frame=='map (LiDAR中心)'
    assert node.tf.lookups==1


def test_map_frame_pose_callback_does_not_apply_map_transform_twice():
    node=fake_node(status='mapping',transform=None)
    msg=pose_msg('map',10.,3.,math.pi/2)
    node.on_pose(msg)
    assert node.pose['x']==pytest.approx(10.)
    assert node.pose['y']==pytest.approx(3.)
    assert node.pose['yaw']==pytest.approx(math.pi/2)
    assert node.pose_frame=='map (LiDAR中心)'
    assert node.tf.lookups==0
