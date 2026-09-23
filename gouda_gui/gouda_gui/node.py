"""HTTP mission control and ROS adapter. ROS owns motion; browser owns no heartbeat."""
import copy
from .paths import data_dir
from collections import deque
import json
import math
from pathlib import Path as FilePath
import threading
import time
import uuid

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, qos_profile_sensor_data
from nav_msgs.msg import OccupancyGrid, Odometry, Path
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from sensor_msgs.msg import PointCloud2, Imu
from sensor_msgs_py.point_cloud2 import read_points
from std_msgs.msg import String, Bool
from std_srvs.srv import Trigger, SetBool
from tf2_ros import Buffer, TransformListener, TransformException
from ament_index_python.packages import get_package_share_directory
from .core import ProjectionMap, MapStore, finite_pose, serve, validate_grid


def yaw(q):
    return math.atan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))


class MissionControl(Node):
    def __init__(self):
        super().__init__('gouda_mission_control')
        for k, v in [('host','127.0.0.1'),('port',8765),('mode','live'),
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
        self.store = MapStore(self.get_parameter('map_directory').value)
        self.times = {}; self.pose = None; self.nav = {}; self.esp = {}; self.cloud = []
        self.cloud_origin = None; self.cloud_note = '点群を待っています'
        self.grid = None; self.grid_revision = 0; self.map_meta = None
        self.mapping = False; self.mapper = None; self.mapping_started = 0.;self.mapping_elapsed=0
        self.goal = None; self.preview = []; self.plan_id = None; self.planning = False
        self.epoch = 0; self.trail = []; self.logs = []; self.stop_requested = False
        self.tf = Buffer(); self.listener = TransformListener(self.tf,self)
        latched = QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL)
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
        self.create_subscription(Imu,'/imu/data_raw',lambda _:self.touch('imu'),qos_profile_sensor_data)
        self.create_subscription(Bool,'/gouda/lidar_healthy',lambda m:self.touch('lidar_health') if m.data else None,1)
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

    def on_pose(self,msg):
        age=self.get_clock().now().nanoseconds*1e-9-msg.header.stamp.sec-msg.header.stamp.nanosec*1e-9
        if msg.header.frame_id!='map' or not -.05<=age<.5:return
        p=msg.pose.pose.position;t=msg.twist.twist
        data=dict(x=p.x,y=p.y,yaw=yaw(msg.pose.pose.orientation),v=t.linear.x,w=t.angular.z)
        if not all(math.isfinite(v) for v in data.values()):return
        with self.lock:
            self.pose=data;self.times['pose']=time.monotonic()
            if not self.trail or math.dist(self.trail[-1],[p.x,p.y])>.05:
                self.trail.append([p.x,p.y]);self.trail=self.trail[-3000:]

    def on_nav(self,msg):
        with self.lock:
            self.nav=json.loads(msg.data);self.times['navigation']=time.monotonic()
            if self.nav.get('state','').startswith('PLAN_') and self.nav['state']!='PLANNING':self.planning=False

    def on_esp(self,msg):
        with self.lock:self.esp=json.loads(msg.data);self.times['esp32']=time.monotonic()

    def on_path(self,msg):
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
            self.grid=self.grid_from_ros(msg);self.grid_revision+=1;self.times['map']=time.monotonic()
            if not self.map_meta:
                self.map_meta=dict(id='external-map',name='SLAM地図・センサー位置基準',mode=self.mode)
            if self.mapping:self.external_frames += 1

    def receive_cloud(self,msg):
        age=self.get_clock().now().nanoseconds*1e-9-msg.header.stamp.sec-msg.header.stamp.nanosec*1e-9
        if not -.05<=age<.5:return
        self.touch('lidar_raw')
        if self.observation_only:self.pending_clouds.append(msg)
        else:self.on_cloud(msg)

    def process_pending_cloud(self):
        if not self.pending_clouds:return
        msg=self.pending_clouds[0]
        age=self.get_clock().now().nanoseconds*1e-9-msg.header.stamp.sec-msg.header.stamp.nanosec*1e-9
        if age>=.5 or age<-.05:self.pending_clouds.popleft();return
        if self.tf.can_transform('map',msg.header.frame_id,rclpy.time.Time.from_msg(msg.header.stamp)):
            self.pending_clouds.popleft();self.on_cloud(msg)

    def on_cloud(self,msg):
        now=time.monotonic()
        if now-self.times.get('cloud_attempt',0)<.2:return
        self.times['cloud_attempt']=now
        try:
            age=self.get_clock().now().nanoseconds*1e-9-msg.header.stamp.sec-msg.header.stamp.nanosec*1e-9
            if not -.05<=age<.5:raise ValueError('点群の時刻が古いか、時計が一致していません')
            tf=self.tf.lookup_transform('map',msg.header.frame_id,rclpy.time.Time.from_msg(msg.header.stamp))
            q=tf.transform.rotation;t=tf.transform.translation
            # Full rigid transform; no guessed sensor extrinsics.
            matrix=((1-2*(q.y*q.y+q.z*q.z),2*(q.x*q.y-q.z*q.w),2*(q.x*q.z+q.y*q.w)),
                    (2*(q.x*q.y+q.z*q.w),1-2*(q.x*q.x+q.z*q.z),2*(q.y*q.z-q.x*q.w)),
                    (2*(q.x*q.z-q.y*q.w),2*(q.y*q.z+q.x*q.w),1-2*(q.x*q.x+q.y*q.y)))
            raw=read_points(msg,field_names=('x','y','z'),skip_nans=True)
            stride=max(1,len(raw)//1200);points=[]
            for p in raw[::stride]:
                v=[float(p[k]) for k in range(3)]
                if not all(math.isfinite(c) for c in v):continue
                points.append([sum(a*b for a,b in zip(row,v))+offset for row,offset in zip(matrix,(t.x,t.y,t.z))])
            with self.lock:
                self.cloud=points;self.cloud_origin=(t.x,t.y);self.times['cloud']=now;self.cloud_note='map座標の点群を受信中'
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
            return copy.deepcopy(dict(mode=self.mode,observation_only=self.observation_only,
                slam_phase=self.slam.status() if self.slam else None,
                pose_reference='LiDAR中心・取付未校正' if self.observation_only else '車体',pose=self.pose,nav=self.nav,esp=self.esp,ages=ages,
                map=self.grid,map_revision=self.grid_revision,map_meta=self.map_meta,maps=self.store.list(),
                mapping=self.mapping,mapping_seconds=round(time.monotonic()-self.mapping_started) if self.mapping else self.mapping_elapsed,
                mapping_frames=self.external_frames if self.observation_only else self.mapper.frames if self.mapper else 0,cloud=self.cloud,cloud_note=self.cloud_note,
                goal=self.goal,path=self.preview,plan_id=self.plan_id,planning=self.planning,trail=self.trail,
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
            self.epoch+=1;self.plan_id=None;self.preview=[];self.planning=False

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
            if self.observation_only:
                return self.observation_command(action,data)
            if action in ('target','plan','initial_pose','mapping_start','load_map'):
                if not self.stationary() or self.esp.get('flags'):
                    raise RuntimeError('先に停止し、停止確認後に操作してください')
            if action=='target':
                goal=finite_pose(data)
                self.call(self.cancel,Trigger.Request());self.invalidate()
                with self.lock:self.goal=goal
                self.log('ゴールを設定しました。経路を計算してください。')
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
        if action in ('start','plan'):
            raise RuntimeError('計測専用です。実機の経路計算・走行へ接続していません')
        if action=='target':
            with self.lock:self.goal=finite_pose(data)
            self.log('ゴール候補を記録しました。実機走行は無効です。')
        elif action=='mapping_start':
            if not self.fresh('lidar_raw'):raise RuntimeError('新しいLiDAR点群が必要です')
            if self.mapping:raise RuntimeError('地図作成中です')
            self.slam.start()
            with self.lock:
                self.grid=None;self.grid_revision+=1;self.map_meta=None;self.external_frames=0
                self.pose=None;self.trail=[];self.cloud=[];self.pending_clouds.clear()
                self.mapping=True;self.mapping_started=time.monotonic();self.mapping_elapsed=0
            self.log('センサー位置基準のSLAMを開始しました。取付未校正・IMU未融合です。')
        elif action=='mapping_stop':
            self.slam.stop_mapping()
            with self.lock:
                self.mapping=False;self.mapping_elapsed=round(time.monotonic()-self.mapping_started)
            self.log('SLAMの計測を終了しました。地図とSLAMデータを保存できます。')
        elif action=='save_map':
            with self.lock:
                if self.mapping or not self.external_frames or self.grid is None:
                    raise RuntimeError('地図を作成し、計測を終了してください')
                grid=copy.deepcopy(self.grid);frames=self.external_frames
            meta=self.store.save(data.get('name'),grid,self.mode,frames,
                details=dict(method='kiss_icp_slam_toolbox_sensor_plane',loop_closure_enabled=True,
                    loop_closure_verified=False,pose_reference='hesai_lidar',
                    extrinsics_validated=False,imu_fused=False,height_provisional_m=1.6),
                finalize=self.slam.save)
            with self.lock:self.map_meta=meta
            self.log('地図画像と再定位用SLAMデータを保存しました。')
        elif action=='load_map':
            if self.mapping:raise RuntimeError('計測を終了してください')
            meta,grid=self.store.load(data.get('id'))
            if meta.get('method')!='kiss_icp_slam_toolbox_sensor_plane':
                raise RuntimeError('再定位用SLAMデータのある地図を選択してください')
            if meta['mode']!=self.mode:raise RuntimeError('実機と記録再生の地図は区別して選択してください')
            graph=self.store.root/meta['id']/'slam'
            for suffix in ('.data','.posegraph'):
                if not graph.with_suffix(suffix).is_file():raise RuntimeError('SLAMデータが不足しています')
            self.slam.start(graph)
            with self.lock:
                self.grid=grid;self.grid_revision+=1;self.map_meta=meta;self.pose=None;self.trail=[]
                self.cloud=[];self.pending_clouds.clear();self.external_frames=0
            self.log('地図を再読込しました。LiDARの初期位置を指定して推定結果を確認してください。')
        elif action=='initial_pose':
            pose=finite_pose(data)
            if self.slam.status()!='localization' or not self.initial_pub.get_subscription_count():
                raise RuntimeError('保存したSLAM地図を先に読み込んでください')
            msg=PoseWithCovarianceStamped();msg.header=self.pose_message(pose).header
            msg.pose.pose=self.pose_message(pose).pose
            msg.pose.covariance[0]=.25;msg.pose.covariance[7]=.25;msg.pose.covariance[35]=.07
            self.initial_pub.publish(msg)
            with self.lock:self.pose=None;self.trail=[]
            self.log('LiDAR中心の初期位置を送信しました。推定の成功は観測結果で確認してください。')
        else:raise ValueError('未対応の操作です')
        return dict(ok=True)

    def pose_message(self,pose):
        msg=PoseStamped();msg.header.frame_id='map';msg.header.stamp=self.get_clock().now().to_msg()
        msg.pose.position.x=float(pose['x']);msg.pose.position.y=float(pose['y'])
        msg.pose.orientation.z=math.sin(pose['yaw']/2);msg.pose.orientation.w=math.cos(pose['yaw']/2)
        return msg


def main():
    rclpy.init();node=MissionControl()
    try:rclpy.spin(node)
    except KeyboardInterrupt:pass
    finally:
        if node.slam:node.slam.close()
        node.stop_motion();node.server.shutdown();node.server.server_close();node.destroy_node()
        if rclpy.ok():rclpy.shutdown()
