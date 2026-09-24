"""HTTP mission control and ROS adapter. ROS owns motion; browser owns no heartbeat."""
import copy
from .paths import data_dir, runtime_dir, logs_dir, config_dir
from .recording import RecordingManager
from collections import deque
import json
import math
from pathlib import Path as FilePath
import threading
import time
import uuid
import os
import signal
import subprocess
import sys
import tempfile
import yaml

import rclpy
from rclpy.node import Node
from rclpy.executors import ExternalShutdownException
from rclpy.qos import QoSProfile, DurabilityPolicy, qos_profile_sensor_data
from nav_msgs.msg import OccupancyGrid, Odometry, Path
from nav2_msgs.action import ComputePathToPose
from nav2_msgs.srv import GetCostmap
from rclpy.action import ActionClient
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from sensor_msgs.msg import PointCloud2, Imu
from sensor_msgs_py.point_cloud2 import read_points
from std_msgs.msg import String, Bool
from std_srvs.srv import Trigger, SetBool
from tf2_ros import Buffer, TransformListener, TransformException
from ament_index_python.packages import get_package_share_directory
from .core import ProjectionMap, MapStore, finite_pose, serve, validate_grid, mapping_start_backend, glim_session_output_directory, compose_pose_transform


def mapping_api():
    from gouda_navigation.mapping import load_mapping_settings, save_mapping_settings, validate_mapping_settings, GlimSession
    return load_mapping_settings, save_mapping_settings, validate_mapping_settings, GlimSession


def yaw(q):
    return math.atan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))


class MissionControl(Node):
    def __init__(self):
        super().__init__('gouda_mission_control')
        for k, v in [('host','127.0.0.1'),('port',8765),('mode','live'),('mapping_backend','kiss_icp'),
                     ('observation_only',False),('map_directory',str(data_dir()/'maps'))]:
            self.declare_parameter(k,v)
        self.mode = self.get_parameter('mode').value
        if self.mode not in ('simulation','live','replay'):
            raise ValueError('mode must be simulation, live, or replay')
        self.observation_only = self.get_parameter('observation_only').value
        if self.observation_only and self.mode == 'simulation':
            raise ValueError('observation_only requires live or replay')
        self.slam = None; self.external_frames = 0; self.pending_clouds = deque(maxlen=10)
        self.lock = threading.RLock(); self.operations = threading.Lock()
        self.recording_data_lock=threading.Lock();self.recording_data_seen=False
        self.recording_error=''
        try:self.recorder=RecordingManager(sensor_data_seen=self.recording_sensor_data_seen,use_sim_time=self.mode=='replay')
        except Exception as exc:self.recorder=None;self.recording_error=str(exc)[:300]
        self.store = MapStore(self.get_parameter('map_directory').value)
        self.times = {}; self.pose = None; self.pose_frame='odom_lidar (LiDAR中心)' if self.observation_only else '車体'; self.nav = {}; self.esp = {}; self.cloud = []
        self.cloud_origin = None; self.cloud_note = '点群を待っています'
        self.grid = None; self.grid_revision = 0; self.map_meta = None
        self.mapping = False; self.mapper = None; self.mapping_started = 0.;self.mapping_elapsed=0
        self.runtime_mapping_settings={};self.effective_mapping_backend=self.get_parameter('mapping_backend').value
        self.glim_package_available=None;self.glim_session=None;self.glim_output_dir=None;self.glim_error=''
        self.goal = None; self.planning_start = None; self.preview = []; self.plan_id = None; self.planning = False
        self.plan_error = ''; self.plan_process = None
        self.epoch = 0; self.trail = []; self.logs = []; self.stop_requested = False
        self.tf = Buffer(); self.listener = TransformListener(self.tf,self)
        latched = QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.preview_map_pub = self.create_publisher(OccupancyGrid, '/gouda/route_preview/map', latched)
        self.preview_client = ActionClient(self, ComputePathToPose, '/gouda_route_preview/compute_path_to_pose') if self.observation_only else None
        self.map_pub = self.create_publisher(OccupancyGrid,'/map',latched)
        self.goal_pub = self.create_publisher(PoseStamped,'/goal_pose',1)
        self.initial_pub = self.create_publisher(PoseWithCovarianceStamped,'/initialpose',1)
        self.sim_pose_pub = self.create_publisher(PoseStamped,'/gouda/sim/set_pose',1)
        self.cancel = self.create_client(Trigger,'/gouda/cancel')
        self.start = self.create_client(Trigger,'/gouda/start')
        self.arm = self.create_client(SetBool,'/gouda/arm')
        self.create_subscription(Odometry,'/gouda/pose',self.on_pose,1)
        self.create_subscription(String,'/gouda/navigation_state',self.on_nav,1)
        self.create_subscription(String,'/esp32/status',self.on_esp,1)
        self.create_subscription(Path,'/gouda/preview_path',self.on_path,1)
        self.create_subscription(PointCloud2,'/lidar_points',self.receive_cloud,qos_profile_sensor_data)
        if self.observation_only:
            from .slam import SlamSession
            self.slam = SlamSession(self,self.store.root,replay=self.mode=='replay')
            self.create_timer(.05,self.process_pending_cloud)
            self.create_subscription(Odometry,'/glim_ros/lidar_odom',self.on_glim_odom,qos_profile_sensor_data)
        self.create_subscription(Imu,'/imu/data_raw',self.on_imu,qos_profile_sensor_data)
        self.create_subscription(Bool,'/gouda/lidar_healthy',lambda m:self.touch('lidar_health') if m.data else None,1)
        if self.observation_only:self.initialize_mapping_runtime()
        self.create_subscription(OccupancyGrid,'/gouda/world_map',self.on_world,latched)
        self.create_subscription(OccupancyGrid,'/map',self.on_external_map,latched)
        self.server = serve(self,get_package_share_directory('gouda_gui')+'/web',
                            self.get_parameter('host').value,self.get_parameter('port').value)
        self.log('操作画面を起動しました。走行開始は明示操作が必要です。')

    def log(self,message):
        with self.lock:
            self.logs.append(dict(time=time.time(),message=message)); self.logs=self.logs[-40:]

    def touch(self,key):
        with self.lock:self.times[key]=time.monotonic()

    def recording_sensor_data_seen(self,*_):
        with self.recording_data_lock:return self.recording_data_seen

    def on_imu(self,msg):
        with self.recording_data_lock:self.recording_data_seen=True
        self.touch('imu')

    def on_glim_odom(self,msg):
        if not self.observation_only or self.effective_mapping_backend!='glim_imu':return
        if msg.header.frame_id!='odom_lidar' or msg.child_frame_id!=self.runtime_mapping_settings.get('lidar_frame','hesai_lidar'):return
        p=msg.pose.pose.position;q=msg.pose.pose.orientation;t=msg.twist.twist
        position=[p.x,p.y,p.z];frame='odom_lidar (LiDAR中心)'
        try:
            stamp=rclpy.time.Time.from_msg(msg.header.stamp)
            tf=self.tf.lookup_transform('map','odom_lidar',stamp)
            r=tf.transform.rotation;offset=tf.transform.translation
            position,combined=compose_pose_transform(position,(q.x,q.y,q.z,q.w),
                (offset.x,offset.y,offset.z),(r.x,r.y,r.z,r.w))
            from geometry_msgs.msg import Quaternion
            q=Quaternion(x=combined[0],y=combined[1],z=combined[2],w=combined[3]);frame='map (LiDAR中心)'
        except TransformException:pass
        data=dict(x=position[0],y=position[1],yaw=yaw(q),v=t.linear.x,w=t.angular.z)
        if not all(math.isfinite(v) for v in data.values()):return
        with self.lock:
            self.pose=data;self.pose_frame=frame;self.times['pose']=time.monotonic()
            if not self.trail or math.dist(self.trail[-1],[position[0],position[1]])>.05:
                self.trail.append([position[0],position[1]]);self.trail=self.trail[-3000:]

    def on_pose(self,msg):
        age=self.get_clock().now().nanoseconds*1e-9-msg.header.stamp.sec-msg.header.stamp.nanosec*1e-9
        if msg.header.frame_id!='map' or not -.05<=age<.5:return
        p=msg.pose.pose.position;t=msg.twist.twist
        data=dict(x=p.x,y=p.y,yaw=yaw(msg.pose.pose.orientation),v=t.linear.x,w=t.angular.z)
        if not all(math.isfinite(v) for v in data.values()):return
        with self.lock:
            self.pose=data;self.pose_frame='map (LiDAR中心)' if self.observation_only else '車体';self.times['pose']=time.monotonic()
            if not self.trail or math.dist(self.trail[-1],[p.x,p.y])>.05:
                self.trail.append([p.x,p.y]);self.trail=self.trail[-3000:]

    def on_nav(self,msg):
        if self.observation_only:return
        with self.lock:
            self.nav=json.loads(msg.data);self.times['navigation']=time.monotonic()
            if self.nav.get('state','').startswith('PLAN_') and self.nav['state']!='PLANNING':self.planning=False

    def on_esp(self,msg):
        with self.lock:self.esp=json.loads(msg.data);self.times['esp32']=time.monotonic()

    def on_path(self,msg):
        if self.observation_only:return
        with self.lock:
            if not msg.poses:
                self.preview=[];return
            if self.planning and msg.header.frame_id=='map':
                self.preview=[[p.pose.position.x,p.pose.position.y] for p in msg.poses]
                self.planning=False

    @staticmethod
    def grid_from_ros(msg):
        p=msg.info.origin.position
        return validate_grid(dict(width=msg.info.width,height=msg.info.height,resolution=msg.info.resolution,
                                  origin=dict(x=p.x,y=p.y,yaw=yaw(msg.info.origin.orientation)),
                                  frame=msg.header.frame_id,data=list(msg.data)))

    def on_world(self,msg):
        if self.mode!='simulation':return
        with self.lock:
            if self.grid is None:
                self.grid=self.grid_from_ros(msg);self.grid_revision+=1
                self.map_meta=dict(id='simulation-world',name='シミュレーション環境',mode='simulation')
                self.publish_map()

    def on_external_map(self,msg):
        # The GUI owns /map only in simulation. Live/replay uses an external mapper.
        if self.mode=='simulation':return
        with self.lock:
            # During live mapping, accept SLAM updates. Once a saved map is selected,
            # keep that immutable planning grid while localization continues separately.
            if self.mapping or self.map_meta is None:
                self.grid=self.grid_from_ros(msg);self.grid_revision+=1;self.times['map']=time.monotonic()
                if not self.map_meta:
                    self.map_meta=dict(id='external-map',name='SLAM地図・センサー位置基準',mode=self.mode)
                if self.mapping:self.external_frames += 1

    def receive_cloud(self,msg):
        # Raw recording/health follows arrival, independently of timestamp validity.
        self.touch('lidar_raw')
        with self.recording_data_lock:self.recording_data_seen=True
        if self.observation_only and self.effective_mapping_backend=='glim_imu':
            return
        age=self.get_clock().now().nanoseconds*1e-9-msg.header.stamp.sec-msg.header.stamp.nanosec*1e-9
        if not -.05<=age<.5:return
        if self.observation_only:self.pending_clouds.append(msg)
        else:self.on_cloud(msg)

    def process_pending_cloud(self):
        if not self.pending_clouds:return
        msg=self.pending_clouds[0]
        age=self.get_clock().now().nanoseconds*1e-9-msg.header.stamp.sec-msg.header.stamp.nanosec*1e-9
        if age>=.5 or age<-.05:self.pending_clouds.popleft();return
        stamp=rclpy.time.Time.from_msg(msg.header.stamp)
        if self.tf.can_transform('map',msg.header.frame_id,stamp) or self.tf.can_transform('odom_lidar',msg.header.frame_id,stamp):
            self.pending_clouds.popleft();self.on_cloud(msg)

    def on_cloud(self,msg):
        now=time.monotonic()
        if now-self.times.get('cloud_attempt',0)<.2:return
        self.times['cloud_attempt']=now
        try:
            age=self.get_clock().now().nanoseconds*1e-9-msg.header.stamp.sec-msg.header.stamp.nanosec*1e-9
            if not -.05<=age<.5:raise ValueError('点群の時刻が古いか、時計が一致していません')
            stamp=rclpy.time.Time.from_msg(msg.header.stamp)
            target='map' if self.tf.can_transform('map',msg.header.frame_id,stamp) else 'odom_lidar'
            tf=self.tf.lookup_transform(target,msg.header.frame_id,stamp)
            q=tf.transform.rotation;t=tf.transform.translation
            points=[]
            if self.mapping and self.mode=='simulation':
                # Convert points only while the simulation's 2D map projection needs them.
                matrix=((1-2*(q.y*q.y+q.z*q.z),2*(q.x*q.y-q.z*q.w),2*(q.x*q.z+q.y*q.w)),
                        (2*(q.x*q.y+q.z*q.w),1-2*(q.x*q.x+q.z*q.z),2*(q.y*q.z-q.x*q.w)),
                        (2*(q.x*q.z-q.y*q.w),2*(q.y*q.z+q.x*q.w),1-2*(q.x*q.x+q.y*q.y)))
                raw=read_points(msg,field_names=('x','y','z'),skip_nans=True)
                stride=max(1,len(raw)//1200)
                for p in raw[::stride]:
                    v=[float(p[k]) for k in range(3)]
                    if not all(math.isfinite(c) for c in v):continue
                    points.append([sum(a*b for a,b in zip(row,v))+offset for row,offset in zip(matrix,(t.x,t.y,t.z))])
            with self.lock:
                self.cloud=[];self.cloud_origin=(t.x,t.y);self.times['cloud']=now;self.cloud_note='LiDAR座標変換を受信中'
                if self.observation_only:
                    heading=yaw(q); prev=self.pose; previous=self.times.get('pose')
                    dt=now-previous if previous else 0.
                    self.pose=dict(x=t.x,y=t.y,yaw=heading,
                        v=math.hypot(t.x-prev['x'],t.y-prev['y'])/dt if prev and dt>0 else 0.,
                        w=math.atan2(math.sin(heading-prev['yaw']),math.cos(heading-prev['yaw']))/dt if prev and dt>0 else 0.)
                    self.times['pose']=now
                    if not self.trail or math.dist(self.trail[-1],[t.x,t.y])>.05:
                        self.trail.append([t.x,t.y]);self.trail=self.trail[-3000:]
                if self.mapping and self.mode=='simulation':
                    self.mapper.update(self.cloud_origin,[p for p in points if .15<=p[2]<=1.8])
                    self.grid=self.mapper.grid;self.grid_revision+=1;self.times['map']=now
        except (TransformException,ValueError) as exc:
            with self.lock:self.cloud_note=str(exc)[:200]

    def publish_map(self):
        g=self.grid
        if g is None:return
        msg=OccupancyGrid();msg.header.frame_id='map';msg.header.stamp=self.get_clock().now().to_msg()
        msg.info.width=g['width'];msg.info.height=g['height'];msg.info.resolution=float(g['resolution'])
        o=g['origin'];msg.info.origin.position.x=float(o['x']);msg.info.origin.position.y=float(o['y'])
        msg.info.origin.orientation.z=math.sin(o['yaw']/2);msg.info.origin.orientation.w=math.cos(o['yaw']/2)
        msg.data=g['data'];self.map_pub.publish(msg)

    def fresh(self,key,limit=.6):
        return time.monotonic()-self.times.get(key,-1e9)<limit

    def stationary(self):
        return self.pose and self.fresh('pose') and abs(self.pose['v'])<.01 and abs(self.pose['w'])<.01

    def viewer_status(self):
        path=runtime_dir()/'processes.json'
        try:
            item=json.loads(path.read_text()).get('processes',{}).get('viewer')
            if not item:return {'available':False,'error':'RViz2停止中 · gouda.sh observe または gouda.sh viewer で起動'}
            fields=FilePath(f"/proc/{item['pid']}/stat").read_text().rsplit(')',1)[1].split()
            boot=FilePath('/proc/sys/kernel/random/boot_id').read_text().strip()
            if fields[0]=='Z' or boot+':'+fields[19]!=item.get('start'):
                return {'available':False,'error':'RViz2が終了しています · gouda.sh viewer で再起動'}
            cmd=FilePath(f"/proc/{item['pid']}/cmdline").read_bytes().decode(errors='replace')
            if 'rviz2' not in cmd:
                return {'available':False,'error':'管理対象のRViz2プロセスではありません · gouda.sh viewer で再起動'}
            return {'available':True,'pid':item['pid'],'display':item.get('display')}
        except (OSError,ValueError,KeyError,TypeError):
            failure=''
            try: failure=(logs_dir()/'viewer.log').read_text(errors='replace')[-600:].strip()
            except OSError: pass
            return {'available':False,'error':'RViz2終了 · gouda.sh viewer で再起動','failure':failure}

    def initialize_mapping_runtime(self):
        try:
            load_settings,_,validate_settings,_=mapping_api()
            self.runtime_mapping_settings=load_settings()
            errors=validate_settings(self.runtime_mapping_settings,require_ready=self.runtime_mapping_settings.get('backend')=='glim_imu')
            if self.runtime_mapping_settings.get('backend')!=self.effective_mapping_backend:
                self.glim_error='保存設定と処理起動時のバックエンドが異なります。Mission Controlを再起動してください';return
            if errors and self.runtime_mapping_settings.get('backend')=='glim_imu':
                self.glim_error='GLIM起動条件: '+' / '.join(errors);return
            if self.runtime_mapping_settings.get('compute')=='cuda':
                self.glim_error='CUDAは未対応です。CPUを選択してMission Controlを再起動してください';return
            if self.runtime_mapping_settings.get('backend')=='glim_imu':
                try:
                    get_package_share_directory('glim');get_package_share_directory('glim_ros')
                    self.glim_package_available=True
                except Exception as exc:
                    self.glim_package_available=False;self.glim_error='GLIMパッケージを利用できません: '+str(exc)[:200];return
                self.start_glim_runtime()
        except Exception as exc:self.glim_error=str(exc)[:300]

    def start_glim_runtime(self):
        if self.glim_session is not None:
            status=self.glim_session.status()
            if status in ('waiting_for_sensors','processing','mapping'):return
        GlimSession=mapping_api()[3]
        output=data_dir()/'maps_glim'/('session_'+uuid.uuid4().hex)
        session=GlimSession(self,output)
        self.glim_session=session;self.glim_output_dir=glim_session_output_directory(session,output)
        session.start(self.runtime_mapping_settings,self.glim_output_dir,use_sim_time=self.mode=='replay')
        self.glim_output_dir=glim_session_output_directory(session,self.glim_output_dir)
        self.glim_error=''
        self.active_mapping_settings=copy.deepcopy(self.runtime_mapping_settings)

    def mapping_settings_snapshot(self):
        try:
            load_settings,_,validate_settings,_=mapping_api();saved=load_settings();errors=validate_settings(saved,require_ready=saved.get('backend')=='glim_imu')
        except Exception as exc:
            saved={};errors=[str(exc)[:300]]
        active_backend=None;active_compute=None
        if self.glim_session is not None:
            glim_status=self.glim_session.status()
            if glim_status in ('waiting_for_sensors','processing','mapping'):
                active_backend=getattr(self.glim_session,'active_backend','glim_imu') or 'glim_imu'
                active_compute=(getattr(self,'active_mapping_settings',{}) or {}).get('compute')
            elif glim_status in ('failed','preflight_error'):
                detail=getattr(self.glim_session,'error','') or '; '.join(getattr(self.glim_session,'input_state',{}).get('errors',[]))
                if detail:self.glim_error=str(detail)[:300]
                elif not self.glim_error:self.glim_error='GLIMプロセスが終了しました。ログを確認してMission Controlを再起動してください'
        elif self.observation_only and self.effective_mapping_backend=='kiss_icp':
            current=getattr(self,'active_mapping_settings',self.runtime_mapping_settings)
            active_backend='kiss_icp';active_compute=current.get('compute')
        elif self.observation_only and self.slam is not None and self.slam.status() in ('mapping','paused','localization'):
            current=getattr(self,'active_mapping_settings',self.runtime_mapping_settings)
            active_backend=current.get('backend','kiss_icp');active_compute=current.get('compute')
        return dict(saved=saved,ready=not errors,errors=errors,restart_required=bool(self.observation_only and saved and (saved!=self.runtime_mapping_settings or saved.get('backend')!=self.effective_mapping_backend)),package_available=self.glim_package_available,runtime_backend=self.effective_mapping_backend,runtime_available=(bool(self.glim_session and self.glim_session.process is not None and self.glim_session.process.poll() is None) if self.effective_mapping_backend=='glim_imu' else None),active=dict(backend=active_backend,compute=active_compute,state=self.glim_session.status() if self.glim_session else ('configured' if self.runtime_mapping_settings.get('backend')=='kiss_icp' else 'unavailable'),input_state=getattr(self.glim_session,'input_state',None) if self.glim_session else None,error=self.glim_error or None,output_directory=str(self.glim_output_dir) if active_backend=='glim_imu' and self.glim_output_dir else None))

    def snapshot(self):
        with self.lock:
            ages={k:round(time.monotonic()-v,3) for k,v in self.times.items()}
            reasons=[]
            if self.mode!='simulation':reasons.append('実機走行接続は未校正のため無効です')
            if self.mapping:reasons.append('地図作成を終了してください')
            if not self.preview or not self.nav.get('preview_ready'):reasons.append('経路を計算してください')
            if not self.fresh('navigation') or not self.nav.get('inputs_valid'):reasons.append('走行入力が未準備または更新停止です')
            if not self.fresh('esp32'):reasons.append('ESP32応答を待っています')
            if not self.nav.get('explicit_start'):reasons.append('明示開始に対応したナビゲーションが必要です')
            if not self.stationary():reasons.append('停止位置の確認が必要です')
            stopped=bool(self.stop_requested and self.stationary() and self.fresh('esp32') and not self.esp.get('flags'))
            return copy.deepcopy(dict(mode=self.mode,observation_only=self.observation_only,viewer=self.viewer_status(),
                slam_phase=self.slam.status() if self.slam else None,
                recording=self.recorder.status() if self.recorder else dict(phase='failed',error=self.recording_error,sensor_data_seen=False),recording_config=self.recorder.get_config() if self.recorder else None,
                mapping_settings=self.mapping_settings_snapshot(),
                localization_available=bool(self.map_meta and (self.store.root/self.map_meta.get('id','')/'slam.posegraph').is_file() and (self.store.root/self.map_meta.get('id','')/'slam.data').is_file()),
                pose_reference=self.pose_frame,pose=self.pose,nav=self.nav,esp=self.esp,ages=ages,
                map=self.grid,map_revision=self.grid_revision,map_meta=self.map_meta,maps=self.store.list(),
                mapping=self.mapping,mapping_seconds=round(time.monotonic()-self.mapping_started) if self.mapping else self.mapping_elapsed,
                mapping_frames=self.external_frames if self.observation_only else self.mapper.frames if self.mapper else 0,cloud=self.cloud,cloud_note=self.cloud_note,
                goal=self.goal,planning_start=self.planning_start,path=self.preview,plan_id=self.plan_id,planning=self.planning,plan_error=self.plan_error,trail=self.trail,
                start_reasons=reasons,stop_status='停止確認済み' if stopped else '停止要求中' if self.stop_requested else '',
                logs=self.logs))

    def call(self,client,request):
        if not client.service_is_ready():raise RuntimeError('Ubuntu側の操作サービスが起動していません')
        future=client.call_async(request);event=threading.Event();future.add_done_callback(lambda _:event.set())
        if not event.wait(2):raise TimeoutError('操作の応答がありません。状態を確認してください')
        response=future.result()
        if not response.success:raise RuntimeError(response.message)
        return response

    def invalidate(self):
        with self.lock:
            self.epoch+=1;self.plan_id=None;self.preview=[];self.planning=False;self.plan_error=''

    def stop_motion(self):
        if self.observation_only:
            return dict(ok=False,message='この画面は計測専用です。車体の停止機能へ接続していません')
        self.invalidate()
        with self.lock:self.stop_requested=True
        sent=[]
        for client,req in [(self.cancel,Trigger.Request()),(self.arm,SetBool.Request(data=False))]:
            if client.service_is_ready():client.call_async(req);sent.append(True)
        self.log('停止指令を送信しました。車体の停止応答を確認中です。')
        return dict(ok=bool(sent),message='停止要求を送信しました' if sent else '停止サービスに接続できません')

    def command(self,action,data):
        if action=='stop':return self.stop_motion()
        if not self.operations.acquire(blocking=False):raise RuntimeError('前の操作を処理中です')
        try:
            if action=='recording_config_save':
                if not self.recorder:raise RuntimeError('記録設定を読み込めません: '+self.recording_error)
                return dict(ok=True,config=self.recorder.update_config(data))
            if action=='recording_start':
                if not self.recorder:raise RuntimeError('記録設定を読み込めません: '+self.recording_error)
                with self.recording_data_lock:self.recording_data_seen=False
                return dict(ok=True,recording=self.recorder.start())
            if action=='recording_stop':
                if not self.recorder:raise RuntimeError('記録機能を利用できません')
                return dict(ok=True,recording=self.recorder.stop())
            if action=='mapping_settings_save':
                if self.mapping:raise RuntimeError('SLAM実行中は方式や取付設定を変更できません。計測を終了してください')
                try:
                    api=mapping_api();api[1](data);saved=api[0]()
                except ImportError as exc:raise RuntimeError('SLAM設定機能を読み込めません。Ubuntuのワークスペースをビルドしてください') from exc
                return dict(ok=True,mapping_settings=saved)
            if self.observation_only:
                if action=='mapping_start':
                    load_settings,_,validate_settings,_=mapping_api();saved=load_settings()
                    settings=self.runtime_mapping_settings
                    errors=validate_settings(settings,require_ready=settings.get('backend')=='glim_imu')
                    glim_active=bool(self.glim_session and self.glim_session.status()=='mapping')
                    mapping_start_backend(saved,settings,self.effective_mapping_backend,errors,
                        package_available=self.glim_package_available,glim_active=glim_active)
                return self.observation_command(action,data)
            if action in ('target','planning_start','plan','initial_pose','mapping_start','load_map'):
                if not self.stationary() or self.esp.get('flags'):
                    raise RuntimeError('先に停止し、停止確認後に操作してください')
            if action=='target':
                goal=finite_pose(data)
                self.call(self.cancel,Trigger.Request());self.invalidate()
                with self.lock:self.goal=goal
                self.log('ゴールを設定しました。経路を計算してください。')
            elif action=='planning_start':
                pose=finite_pose(data)
                with self.lock:self.planning_start=pose
                self.invalidate()
                self.log('計画用の開始位置を記録しました。測定位置・自己位置推定は変更していません。')
            elif action=='plan':
                if self.mapping or self.goal is None or self.grid is None:raise RuntimeError('地図とゴールを設定し、地図作成を終了してください')
                if self.map_meta is None:raise RuntimeError('作成した地図を保存してから経路を計算してください')
                if not self.nav.get('explicit_start'):raise RuntimeError('明示開始モードのナビゲーションが必要です')
                self.call(self.cancel,Trigger.Request());self.invalidate()
                with self.lock:
                    self.plan_id=uuid.uuid4().hex;self.planning=True;self.stop_requested=False
                    msg=self.pose_message(self.goal);self.goal_pub.publish(msg)
                self.log('経路計算を要求しました。走行は開始していません。')
            elif action=='start':
                state=self.snapshot()
                if state['start_reasons']:raise RuntimeError(' / '.join(state['start_reasons']))
                if data.get('plan_id')!=self.plan_id:raise RuntimeError('経路が変更されました。再確認してください')
                epoch=self.epoch
                self.call(self.arm,SetBool.Request(data=True))
                end=time.monotonic()+1.
                while time.monotonic()<end and not (self.fresh('esp32') and self.esp.get('flags')):time.sleep(.02)
                if epoch!=self.epoch or not self.esp.get('flags'):
                    self.stop_motion();raise RuntimeError('走行準備の確認ができませんでした')
                try:self.call(self.start,Trigger.Request())
                except Exception:
                    self.stop_motion();raise
                if epoch!=self.epoch:
                    self.stop_motion();raise RuntimeError('開始操作が中止されました')
                with self.lock:self.stop_requested=False
                self.log('確認済みの経路で走行を開始しました。')
            elif action=='mapping_start':
                self.call(self.cancel,Trigger.Request());self.invalidate()
                if self.mode=='simulation':
                    if not self.fresh('cloud'):raise RuntimeError('座標変換済みの新しい点群が必要です')
                    with self.lock:
                        self.mapper=ProjectionMap(self.pose['x'],self.pose['y']);self.grid=self.mapper.grid
                        self.grid_revision+=1;self.map_meta=None
                else:
                    raise RuntimeError('実機のSLAM・取付TFは未構成です。現在はシミュレーションで地図生成を利用できます')
                with self.lock:self.mapping=True;self.mapping_started=time.monotonic()
                self.log('点群投影による地図作成を開始しました。')
            elif action=='mapping_stop':
                with self.lock:
                    if self.mapping:self.mapping_elapsed=round(time.monotonic()-self.mapping_started)
                    self.mapping=False
                self.log('地図作成を終了しました。保存できます。')
            elif action=='save_map':
                with self.lock:
                    if self.mapping:raise RuntimeError('地図作成を終了してから保存してください')
                    if not self.mapper or not self.mapper.frames:raise RuntimeError('作成した地図がありません')
                    self.map_meta=self.store.save(data.get('name'),self.grid,self.mode,self.mapper.frames)
                    if self.mode=='simulation':self.publish_map()
                self.log('地図を保存しました。走行計画で使用できます。')
            elif action=='load_map':
                if self.mapping:raise RuntimeError('地図作成を終了してください')
                meta,grid=self.store.load(data.get('id'))
                if self.mode!='simulation' or meta['mode']!=self.mode:
                    raise RuntimeError('現在はシミュレーション地図の読込のみ対応しています')
                self.call(self.cancel,Trigger.Request());self.invalidate()
                with self.lock:
                    self.grid=grid;self.grid_revision+=1;self.map_meta=meta;self.mapper=None;self.goal=None
                    self.publish_map()
                self.log('地図を読み込みました。自己位置とゴールを確認してください。')
            elif action=='initial_pose':
                pose=finite_pose(data);self.call(self.cancel,Trigger.Request());self.invalidate()
                if self.mode=='simulation':
                    if max(abs(pose['x']),abs(pose['y']))>3.:raise ValueError('模擬環境の配置はX・Yとも−3〜3 mの範囲です')
                    if not self.sim_pose_pub.get_subscription_count():raise RuntimeError('シミュレータに接続できません')
                    self.sim_pose_pub.publish(self.pose_message(pose))
                    end=time.monotonic()+1.
                    while time.monotonic()<end:
                        if self.pose and math.hypot(self.pose['x']-pose['x'],self.pose['y']-pose['y'])<.03 and abs(math.atan2(math.sin(self.pose['yaw']-pose['yaw']),math.cos(self.pose['yaw']-pose['yaw'])))<.03:break
                        time.sleep(.02)
                    else:raise RuntimeError('仮想車両の配置を確認できませんでした')
                    self.log('仮想車両の初期位置を変更しました。')
                elif self.mode=='live' and self.initial_pub.get_subscription_count():
                    msg=PoseWithCovarianceStamped();msg.header=self.pose_message(pose).header
                    msg.pose.pose=self.pose_message(pose).pose;msg.pose.covariance[0]=.25;msg.pose.covariance[7]=.25;msg.pose.covariance[35]=.07
                    self.initial_pub.publish(msg);self.log('自己位置推定へ初期位置を送信しました。推定結果を確認してください。')
                else:raise RuntimeError('自己位置推定の受信先がありません')
                with self.lock:self.trail=[]
            else:raise ValueError('未対応の操作です')
            return dict(ok=True)
        finally:self.operations.release()

    def observation_command(self,action,data):
        if action=='start':
            raise RuntimeError('計測専用です。走行開始は無効です')
        if action=='plan':
            self.compute_observation_preview();return dict(ok=True)
        if action=='target':
            with self.lock:self.goal=finite_pose(data)
            self.invalidate()
            self.log('ゴール候補を記録しました。経路プレビューのみ利用できます。')
        elif action=='planning_start':
            with self.lock:self.planning_start=finite_pose(data)
            self.invalidate()
            self.log('計画用の開始位置を記録しました。LiDAR位置推定へは送信していません。')
        elif action=='mapping_start':
            if not self.fresh('lidar_raw'):raise RuntimeError('新しいLiDAR点群が必要です')
            if self.mapping:raise RuntimeError('地図作成中です')
            if self.runtime_mapping_settings.get('backend')=='glim_imu' and (self.glim_session is None or self.glim_session.status() not in ('waiting_for_sensors','processing','mapping')):
                self.start_glim_runtime()
            self.active_mapping_settings=copy.deepcopy(self.runtime_mapping_settings)
            self.slam.start()
            with self.lock:
                self.grid=None;self.grid_revision+=1;self.map_meta=None;self.external_frames=0
                self.pose=None;self.trail=[];self.cloud=[];self.pending_clouds.clear()
                self.planning_start=None;self.goal=None
                self.mapping=True;self.mapping_started=time.monotonic();self.mapping_elapsed=0
            self.invalidate()
            self.log('SLAM Toolboxで2D地図作成を開始しました。' if self.runtime_mapping_settings.get('backend')=='glim_imu' else 'SLAM Toolboxで2D LiDAR地図作成を開始しました。')
        elif action=='mapping_stop':
            self.slam.stop_mapping()
            with self.lock:
                self.mapping=False;self.mapping_elapsed=round(time.monotonic()-self.mapping_started)
            self.log('2D地図の更新を終了しました。センサー位置推定は継続しています。地図を保存できます。')
        elif action=='save_map':
            with self.lock:
                if self.mapping or not self.external_frames or self.grid is None:
                    raise RuntimeError('地図を作成し、計測を終了してください')
                grid=copy.deepcopy(self.grid);frames=self.external_frames
            backend=self.runtime_mapping_settings.get('backend','kiss_icp')
            meta=self.store.save(data.get('name'),grid,self.mode,frames,
                details=dict(method='kiss_icp_slam_toolbox_sensor_plane',loop_closure_enabled=True,
                    loop_closure_verified=False,pose_reference='hesai_lidar',mapping_backend=backend,
                    extrinsics_validated=False,extrinsics_calibrated=False,imu_fused=backend=='glim_imu',height_provisional_m=1.6),
                finalize=self.slam.save)
            with self.lock:
                self.map_meta=meta;self.planning_start=None;self.goal=None
            self.invalidate()
            self.log('地図画像と再定位用SLAMデータを保存しました。')
        elif action=='load_map':
            if self.mapping:raise RuntimeError('計測を終了してください')
            meta,grid=self.store.load(data.get('id'))
            if meta.get('method')!='kiss_icp_slam_toolbox_sensor_plane':
                raise RuntimeError('再定位用SLAMデータのある地図を選択してください')
            if meta['mode']!=self.mode:raise RuntimeError('実機と記録再生の地図は区別して選択してください')
            self.slam.close()
            with self.lock:
                self.grid=grid;self.grid_revision+=1;self.map_meta=meta;self.pose=None;self.trail=[]
                self.planning_start=None;self.goal=None;self.cloud=[];self.pending_clouds.clear();self.external_frames=0
            self.invalidate()
            self.log('保存地図を読み込みました。開始位置とゴールを指定すると地図上の経路をプレビューできます。自己位置推定は別操作です。')
        elif action=='initial_pose':
            pose=finite_pose(data)
            if not self.map_meta or not self.snapshot()['localization_available']:
                raise RuntimeError('再定位用SLAMデータを含む保存地図を先に読み込んでください')
            if self.slam.status()!='localization':
                graph=self.store.root/self.map_meta['id']/'slam'
                self.slam.start(graph)
            deadline=time.monotonic()+5.
            while time.monotonic()<deadline and not self.initial_pub.get_subscription_count():time.sleep(.05)
            if not self.initial_pub.get_subscription_count():raise RuntimeError('自己位置推定の再定位処理が起動しません')
            msg=PoseWithCovarianceStamped();msg.header=self.pose_message(pose).header
            msg.pose.pose=self.pose_message(pose).pose
            msg.pose.covariance[0]=.25;msg.pose.covariance[7]=.25;msg.pose.covariance[35]=.07
            self.initial_pub.publish(msg)
            with self.lock:self.pose=None;self.trail=[]
            self.log('LiDAR中心の初期位置を送信しました。推定の成功は観測結果で確認してください。')
        else:raise ValueError('未対応の操作です')
        return dict(ok=True)

    def close_preview_process(self, proc=None):
        proc=proc or self.plan_process
        if proc and proc.poll() is None:
            try:os.killpg(proc.pid,signal.SIGINT)
            except ProcessLookupError:pass
            try:proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                try:os.killpg(proc.pid,signal.SIGTERM)
                except ProcessLookupError:pass
                try:proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    try:os.killpg(proc.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    proc.wait()
        if self.plan_process is proc:self.plan_process=None

    def compute_observation_preview(self):
        if not self.observation_only:
            raise RuntimeError('この計算経路は計測専用です')
        with self.lock:
            if self.mapping: raise RuntimeError('地図作成を終了してから計算してください')
            if self.grid is None or self.map_meta is None or self.map_meta.get('id')=='external-map': raise RuntimeError('保存地図を読み込んでください')
            if self.planning_start is None: raise RuntimeError('計画用の開始位置を設定してください')
            if self.goal is None: raise RuntimeError('ゴールを設定してください')
            grid=copy.deepcopy(self.grid); start=copy.deepcopy(self.planning_start); goal=copy.deepcopy(self.goal)
            revision=self.grid_revision; request_id=uuid.uuid4().hex
            self.plan_id=request_id;self.preview=[];self.planning=True;self.plan_error=''
        proc=None; config_path=None; log=None; log_path=None; diagnostic_log=None
        try:
            validate_grid(grid)
            if abs(grid['origin']['yaw'])>1e-6: raise ValueError('地図の原点が回転しています。このプレビューでは回転地図を扱えません')
            if math.hypot(goal['x']-start['x'],goal['y']-start['y'])<1e-6: raise ValueError('開始位置とゴールが同じです')
            def cell(p):
                x=math.floor((p['x']-grid['origin']['x'])/grid['resolution'])
                y=math.floor((p['y']-grid['origin']['y'])/grid['resolution'])
                if not (0<=x<grid['width'] and 0<=y<grid['height']): raise ValueError('開始位置またはゴールが地図の範囲外です')
                value=grid['data'][y*grid['width']+x]
                if value<0: raise ValueError('開始位置またはゴールが未観測セルです')
                if value>=65: raise ValueError('開始位置またはゴールが障害物セルです')
            cell(start);cell(goal)
            config={
                '/gouda_route_preview/planner_server':{'ros__parameters':{
                    'use_sim_time':False,
                    'expected_planner_frequency':1.0,'planner_plugins':['GridBased'],'costmap_update_timeout':5.0,
                    'GridBased':{'plugin':'nav2_navfn_planner::NavfnPlanner','tolerance':0.0,
                        'use_astar':True,'allow_unknown':False,'use_final_approach_orientation':False}}},
                '/gouda_route_preview/global_costmap/global_costmap':{'ros__parameters':{
                    'use_sim_time':False,
                    'global_frame':'map','robot_base_frame':'map','update_frequency':2.0,
                    'publish_frequency':0.0,'transform_tolerance':0.3,'resolution':grid['resolution'],
                    'track_unknown_space':True,'rolling_window':False,'robot_radius':0.0,
                    'plugins':['static_layer','inflation_layer'],'always_send_full_costmap':True,
                    'static_layer':{'plugin':'nav2_costmap_2d::StaticLayer','map_topic':'/gouda/route_preview/map','map_subscribe_transient_local':True,
                        'subscribe_to_updates':False,'trinary_costmap':False,'lethal_cost_threshold':64},
                    'inflation_layer':{'plugin':'nav2_costmap_2d::InflationLayer','inflation_radius':0.0,
                        'cost_scaling_factor':1.0}}}
            }
            tmp=tempfile.NamedTemporaryFile(mode='w',suffix='.yaml',prefix='gouda-preview-',delete=False)
            config_path=tmp.name;yaml.safe_dump(config,tmp,sort_keys=False);tmp.close()
            log_path=config_path+'.log';log=open(log_path,'w')
            msg=OccupancyGrid();msg.header.frame_id=grid['frame'];msg.header.stamp.sec=0;msg.header.stamp.nanosec=0
            msg.info.width=grid['width'];msg.info.height=grid['height'];msg.info.resolution=float(grid['resolution'])
            msg.info.origin.position.x=float(grid['origin']['x']);msg.info.origin.position.y=float(grid['origin']['y'])
            msg.info.origin.orientation.w=1.0;msg.data=grid['data']
            self.preview_map_pub.publish(msg)
            proc=subprocess.Popen(['ros2','launch','gouda_gui','route_preview.launch.py','params_file:='+config_path],
                                  stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            self.plan_process=proc
            deadline=time.monotonic()+15.
            while time.monotonic()<deadline:
                if proc.poll() is not None:raise RuntimeError('Nav2プランナーが起動できません: '+FilePath(log_path).read_text(errors='replace')[-500:])
                if self.preview_client.wait_for_server(timeout_sec=.1):break
            else:raise TimeoutError('Nav2プランナーの起動がタイムアウトしました')
            map_deadline=time.monotonic()+3.0
            while time.monotonic()<map_deadline and self.preview_map_pub.get_subscription_count()==0:time.sleep(.05)
            if self.preview_map_pub.get_subscription_count()==0:raise TimeoutError('プランナーが選択地図を受信できません')
            costmap_client=None; costmap_ready=False; costmap_deadline=time.monotonic()+6.0
            try:
                while time.monotonic()<costmap_deadline:
                    if costmap_client is None:
                        services=self.get_service_names_and_types()
                        match=next((name for name,types in services if name.startswith('/gouda_route_preview/') and any('nav2_msgs/srv/GetCostmap' in t for t in types)),None)
                        if match:costmap_client=self.create_client(GetCostmap,match)
                    if costmap_client and costmap_client.service_is_ready():
                        future=costmap_client.call_async(GetCostmap.Request());done=threading.Event();box={}
                        def costmap_cb(f,result_box=box,completed=done):
                            try:result_box['response']=f.result()
                            except Exception as exc:result_box['error']=exc
                            finally:completed.set()
                        future.add_done_callback(costmap_cb)
                        if not done.wait(.75):
                            future.cancel()
                            time.sleep(.05)
                            continue
                        if 'error' in box:raise RuntimeError('プランナーのコストマップ応答を読み取れませんでした') from box['error']
                        costmap=box['response'].map;meta=costmap.metadata;origin=meta.origin.position
                        geometry=(costmap.header.frame_id=='map' and meta.size_x==grid['width'] and meta.size_y==grid['height'] and
                            abs(meta.resolution-grid['resolution'])<1e-6 and
                            abs(origin.x-grid['origin']['x'])<grid['resolution']*.1 and
                            abs(origin.y-grid['origin']['y'])<grid['resolution']*.1 and len(costmap.data)==grid['width']*grid['height'])
                        if geometry:
                            matches=True
                            for source,value in zip(grid['data'],costmap.data):
                                if source<0 and value!=255 or source>=65 and value!=254 or 0<=source<65 and value>=253:
                                    matches=False;break
                            sx=math.floor((start['x']-origin.x)/meta.resolution);sy=math.floor((start['y']-origin.y)/meta.resolution)
                            gx=math.floor((goal['x']-origin.x)/meta.resolution);gy=math.floor((goal['y']-origin.y)/meta.resolution)
                            endpoints=(0<=sx<meta.size_x and 0<=sy<meta.size_y and 0<=gx<meta.size_x and 0<=gy<meta.size_y and
                                costmap.data[sy*meta.size_x+sx]<253 and costmap.data[gy*meta.size_x+gx]<253)
                            if matches and endpoints:costmap_ready=True;break
                    time.sleep(.1)
            finally:
                if costmap_client:self.destroy_client(costmap_client)
            if not costmap_ready:raise TimeoutError('プランナーのコストマップが選択地図と一致しませんでした')
            request=ComputePathToPose.Goal();request.start=self.pose_message(start);request.goal=self.pose_message(goal)
            request.start.header.stamp.sec=0;request.start.header.stamp.nanosec=0
            request.goal.header.stamp.sec=0;request.goal.header.stamp.nanosec=0
            request.use_start=True;request.planner_id='GridBased'
            accepted=threading.Event();result_event=threading.Event();box={}
            future=self.preview_client.send_goal_async(request)
            def accepted_cb(f):
                try:box['handle']=f.result()
                except Exception as exc:box['error']=exc
                finally:accepted.set()
            future.add_done_callback(accepted_cb)
            if not accepted.wait(2.):raise TimeoutError('経路計算の受付がタイムアウトしました')
            if 'error' in box:raise RuntimeError('Nav2プランナーへの接続に失敗しました') from box['error']
            handle=box.get('handle')
            if not handle or not handle.accepted:raise RuntimeError('Nav2プランナーが経路計算を受け付けませんでした')
            result_future=handle.get_result_async()
            def result_cb(f):
                try:box['result']=f.result()
                except Exception as exc:box['error']=exc
                finally:result_event.set()
            result_future.add_done_callback(result_cb)
            if not result_event.wait(10.):
                handle.cancel_goal_async();raise TimeoutError('経路計算がタイムアウトしました')
            if 'error' in box:raise RuntimeError('Nav2プランナーの応答を読み取れませんでした') from box['error']
            result=box['result'].result;path=result.path
            if result.error_code:
                detail=getattr(result,'error_msg','') or 'Nav2 did not report a detail'
                raise RuntimeError(f'保存地図上に経路がありません (Nav2 {result.error_code}): {detail}')
            if path.header.frame_id!='map' or len(path.poses)<2:raise RuntimeError('有効な経路が見つかりません')
            points=[]
            for item in path.poses:
                x=item.pose.position.x;y=item.pose.position.y
                if not math.isfinite(x) or not math.isfinite(y):raise RuntimeError('経路に不正な座標があります')
                if not points:
                    points.append([x,y]);continue
                px,py=points[-1];distance=math.hypot(x-px,y-py)
                count=max(1,math.ceil(distance/(grid['resolution']*.5)))
                for j in range(1,count+1):
                    probe={'x':px+(x-px)*j/count,'y':py+(y-py)*j/count}
                    try:cell(probe)
                    except ValueError as exc:raise RuntimeError('経路が地図外または未観測・障害物セルを通ります') from exc
                points.append([x,y])
            with self.lock:
                if revision!=self.grid_revision or request_id!=self.plan_id or start!=self.planning_start or goal!=self.goal:
                    raise RuntimeError('計算中に地図または位置が変更されました。再計算してください')
                self.preview=points;self.planning=False;self.plan_error='';self.plan_id=request_id
            self.log('地図上の経路プレビューを計算しました。車体の通過可否は未確認です。走行開始は無効です。')
        except Exception as exc:
            detail=str(exc)
            self.close_preview_process(proc)
            try:
                if log:
                    log.flush()
                if log_path and FilePath(log_path).is_file():
                    diagnostic_dir=logs_dir();diagnostic_dir.mkdir(parents=True,exist_ok=True)
                    diagnostic_log=diagnostic_dir/f'route-preview-{request_id}.log'
                    os.replace(log_path,diagnostic_log)
                    tail='\n'.join(FilePath(diagnostic_log).read_text(errors='replace').splitlines()[-12:]).strip()
                    if tail:detail += '\n'+tail
                    old=sorted(diagnostic_dir.glob('route-preview-*.log'),key=lambda item:item.stat().st_mtime,reverse=True)
                    for stale in old[5:]:
                        try:stale.unlink()
                        except OSError:pass
            except OSError:pass
            if len(detail)>700:detail=detail[:160]+'\n…\n'+detail[-500:]
            with self.lock:
                self.preview=[];self.plan_id=None;self.planning=False;self.plan_error=detail
            self.log('経路プレビューに失敗しました: '+detail[-400:])
            raise
        finally:
            self.close_preview_process(proc)
            if log:log.close()
            for path in (config_path,config_path+'.log' if config_path else None):
                if path:
                    try:os.unlink(path)
                    except OSError:pass

    def pose_message(self,pose):
        msg=PoseStamped();msg.header.frame_id='map';msg.header.stamp=self.get_clock().now().to_msg()
        msg.pose.position.x=float(pose['x']);msg.pose.position.y=float(pose['y'])
        msg.pose.orientation.z=math.sin(pose['yaw']/2);msg.pose.orientation.w=math.cos(pose['yaw']/2)
        return msg


def main():
    rclpy.init();node=MissionControl()
    try:rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):pass
    finally:
        for label,cleanup in (
            ('preview',lambda:node.close_preview_process()),
            ('recording',lambda:node.recorder.close() if node.recorder else None),
            ('SLAM',lambda:node.slam.close() if node.slam else None),
            ('GLIM',lambda:node.glim_session.close(timeout=90.0) if node.glim_session is not None else None),
            ('vehicle stop',node.stop_motion),
        ):
            try:cleanup()
            except Exception as exc:print(f'{label} cleanup failed: {exc}', file=sys.stderr, flush=True)
        try:node.server.shutdown()
        except Exception as exc:print(f'HTTP shutdown failed: {exc}', file=sys.stderr, flush=True)
        try:node.server.server_close()
        except Exception as exc:print(f'HTTP close failed: {exc}', file=sys.stderr, flush=True)
        try:node.destroy_node()
        finally:
            if rclpy.ok():rclpy.shutdown()
