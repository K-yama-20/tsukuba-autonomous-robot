import json
import math
import time
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.clock import Clock, ClockType
from nav_msgs.msg import Odometry, Path
from nav2_msgs.action import ComputePathToPose
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import UInt8, Bool, String
from std_srvs.srv import Trigger
from tf2_ros import Buffer, TransformListener, TransformException
from .control import Follower


class Navigation(Node):
    def __init__(self):
        super().__init__('gouda_follower')
        parameters={}
        for name,value in [('lookahead',.45),('tolerance',.16),('enter',.21),('leave',.07),('stop_time',1.5),('yaw_tolerance',.15)]:
            self.declare_parameter(name,value);parameters[name]=self.get_parameter(name).value
        self.follower=Follower(**parameters)
        self.declare_parameter('auto_start', True)
        self.preview=None;self.preview_time=0.;self.preview_start=None
        self.preview_pub=self.create_publisher(Path,'/gouda/preview_path',1)
        self.create_service(Trigger,'/gouda/start',self.start_preview)
        self.pose=None;self.last_pose=-1e9;self.healthy=False;self.last_health=-1e9
        self.clear=False;self.last_clear=-1e9;self.generation=0
        self.tf=Buffer();self.listener=TransformListener(self.tf,self)
        self.command=self.create_publisher(UInt8,'/cmd_motion',1)
        self.permit=self.create_publisher(Bool,'/gouda/motion_permit',1)
        self.state=self.create_publisher(String,'/gouda/navigation_state',1)
        self.planner=ActionClient(self,ComputePathToPose,'/compute_path_to_pose')
        self.create_subscription(Odometry,'/gouda/pose',self.on_pose,1)
        self.create_subscription(Bool,'/gouda/lidar_healthy',self.on_health,1)
        self.create_subscription(Bool,'/gouda/swept_clear',self.on_clear,1)
        self.create_subscription(PoseStamped,'/goal_pose',self.goal,1)
        self.create_service(Trigger,'/gouda/cancel',self.cancel)
        self.create_timer(.05,self.tick,clock=Clock(clock_type=ClockType.STEADY_TIME))
        self.progress_time=time.monotonic();self.progress_pose=None

    def on_pose(self,msg):
        now=self.get_clock().now().nanoseconds*1e-9
        stamp=msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9
        if msg.header.frame_id!='map' or not -.05<=now-stamp<.25:
            self.pose=None;return
        self.pose=msg;self.last_pose=time.monotonic()

    def on_health(self,msg):self.healthy=msg.data;self.last_health=time.monotonic()
    def on_clear(self,msg):self.clear=msg.data;self.last_clear=time.monotonic()

    def stop(self,state):
        self.generation+=1;self.follower.cancel(state)
        self.preview=None
        empty=Path();empty.header.frame_id='map';self.preview_pub.publish(empty)
        self.command.publish(UInt8(data=0))

    def start_preview(self,req,res):
        if self.preview is None or self.pose is None or time.monotonic()-self.preview_time>60:
            res.success=False;res.message='Recalculate the preview';return res
        p=self.pose.pose.pose.position
        if math.hypot(p.x-self.preview_start[0],p.y-self.preview_start[1])>.2:
            self.stop('PREVIEW_STALE');res.success=False;res.message='Start position changed';return res
        twist=self.pose.twist.twist
        if max(abs(twist.linear.x),abs(twist.linear.y),abs(twist.angular.z))>=.01:
            res.success=False;res.message='Vehicle must settle before start';return res
        if not self.inputs_good():
            res.success=False;res.message='Inputs are stale or blocked';return res
        path=self.preview;self.preview=None
        self.follower.set_path([(p.pose.position.x,p.pose.position.y) for p in path.poses],self.preview_yaw)
        self.progress_time=time.monotonic();self.progress_pose=None
        res.success=True;res.message='Tracking preview path';return res

    def cancel(self,req,res):
        self.stop('CANCELLED');res.success=True;res.message='STOP requested';return res

    def goal(self,msg):
        self.stop('PLANNING')
        if self.pose is None or msg.header.frame_id!='map' or not self.planner.server_is_ready():
            self.stop('PLAN_UNAVAILABLE');return
        g=ComputePathToPose.Goal();g.goal=msg;g.use_start=True
        g.start.header=self.pose.header;g.start.pose=self.pose.pose.pose;g.planner_id='GridBased'
        generation=self.generation
        def accepted(future):
            try:
                handle=future.result()
                if not handle.accepted:
                    if generation==self.generation:self.stop('PLAN_REJECTED')
                    return
                if generation!=self.generation:handle.cancel_goal_async();return
                handle.get_result_async().add_done_callback(result)
            except Exception as e:
                self.get_logger().error(str(e))
                if generation==self.generation:self.stop('PLAN_ERROR')
        def result(future):
            if generation!=self.generation:return
            try:
                r=future.result().result
                if r.error_code or r.path.header.frame_id!='map' or not r.path.poses:
                    self.stop('PLAN_FAILED');return
                if not all(math.isfinite(v) for p in r.path.poses for v in (p.pose.position.x,p.pose.position.y)):
                    self.stop('PLAN_FAILED');return
                if self.get_parameter('auto_start').value:
                    self.follower.set_path([(p.pose.position.x,p.pose.position.y) for p in r.path.poses])
                    self.progress_time=time.monotonic();self.progress_pose=None
                else:
                    self.preview=r.path;self.preview_time=time.monotonic()
                    self.preview_start=(g.start.pose.position.x,g.start.pose.position.y)
                    q=g.goal.pose.orientation
                    self.preview_yaw=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))
                    self.follower.cancel('PREVIEW_READY')
                self.preview_pub.publish(r.path)
            except Exception as e:
                self.get_logger().error(str(e));self.stop('PLAN_ERROR')
        self.planner.send_goal_async(g).add_done_callback(accepted)

    def inputs_good(self):
        now=time.monotonic()
        good=self.pose is not None and self.healthy and self.clear and max(now-self.last_pose,now-self.last_health,now-self.last_clear)<.25
        if good:
            try:
                tf=self.tf.lookup_transform('map','base_link',rclpy.time.Time())
                age=self.get_clock().now().nanoseconds*1e-9-tf.header.stamp.sec-tf.header.stamp.nanosec*1e-9
                good=0<=age<.25
            except TransformException:good=False
        return good

    def tick(self):
        now=time.monotonic();good=self.inputs_good()
        if self.preview is not None and now-self.preview_time>60:self.stop('PREVIEW_EXPIRED')
        motion=0
        if good:
            p=self.pose.pose.pose;q=p.orientation
            yaw=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))
            twist=self.pose.twist.twist
            motion=self.follower.update(p.position.x,p.position.y,yaw,twist.linear.x,twist.angular.z,now)
            current=(p.position.x,p.position.y,yaw)
            if self.progress_pose is None or math.dist(current,self.progress_pose)>.03:
                self.progress_pose=current;self.progress_time=now
            elif self.follower.path and now-self.progress_time>10:
                self.stop('NO_PROGRESS');motion=0;good=False
        elif self.follower.path:
            self.stop('SENSOR_OR_TF_FAULT')
        self.command.publish(UInt8(data=motion))
        self.permit.publish(Bool(data=good))
        self.state.publish(String(data=json.dumps({'state':self.follower.state,'motion':motion,'inputs_valid':good,
            'preview_ready':self.preview is not None,'explicit_start':not self.get_parameter('auto_start').value})))


def main():
    rclpy.init();node=Navigation()
    try:rclpy.spin(node)
    except KeyboardInterrupt:pass
    finally:
        node.stop('SHUTDOWN');node.permit.publish(Bool(data=False));node.destroy_node()
        if rclpy.ok():rclpy.shutdown()
