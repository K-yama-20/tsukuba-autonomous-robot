import sys,math,pickle,collections,statistics as st
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
bag=sys.argv[1]
want=['/vehicle/joystick_command','/esp32/status','/localization/odometry','/glim_ros/odom_corrected','/glim_ros/odom']
r=rosbag2_py.SequentialReader()
r.open(rosbag2_py.StorageOptions(uri=bag,storage_id='mcap'),rosbag2_py.ConverterOptions('',''))
types={t.name:t.type for t in r.get_all_topics_and_types()}
r.set_filter(rosbag2_py.StorageFilter(topics=want))
cls={k:get_message(types[k]) for k in want if k in types}
J=[];E=[];P=collections.defaultdict(list);kv=None
while r.has_next():
    k,d,t=r.read_next(); t*=1e-9; m=deserialize_message(d,cls[k])
    if k=='/vehicle/joystick_command': J.append((t,)+tuple(m.axes))
    elif k=='/esp32/status':
        if m.status:
            f={x.key:x.value for x in m.status[0].values}
            if kv is None: kv=sorted(f)
            E.append((t,f.get('source'),int(f.get('applied_x_q10000',0)),int(f.get('applied_y_q10000',0))))
    else:
        q=m.pose.pose.orientation; P[k].append((t,m.pose.pose.position.x,m.pose.pose.position.y,math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y**2+q.z**2)),m.header.frame_id))
print(kv); print({k:len(v) for k,v in P.items()},len(J),len(E)); print(J[:1])
o,g=pickle.load(open('/tmp/bag_02.pkl','rb'))
o.update({'J':J,'E':E,'P':dict(P)})
pickle.dump((o,g),open('/tmp/bag_02.pkl','wb'))
imu=o['/sensors/imu/data']; cmd=o['/cmd_vel']; T0=cmd[0][0] if cmd else imu[0][0]
pk='/localization/odometry' if P.get('/localization/odometry') else next(iter(P))
pos=P[pk]; print('pose topic',pk,pos[0][4] if pos else None)
print('start',round(imu[0][0]-T0,1),'end',round(imu[-1][0]-T0,1),'T0',T0)
def W(a,t0,t1): return [x for x in a if t0<=x[0]<t1]
step=5
t=T0-10
print('t(from first cmd) | v max | w absmax | E x,y maxabs | src | yaw integ deg | pos x y | yaw deg')
yaw=0
while t<imu[-1][0]:
    c=W(cmd,t,t+step); e=W(E,t,t+step); i=W(imu,t,t+step); p=W(pos,t,t+step)
    dy=sum(x[3] for x in i)*0.01*180/math.pi; yaw+=dy
    gz=max((abs(x[3]) for x in i),default=0)
    print(round(t-T0),'v',round(max((x[1] for x in c),default=0),3),round(min((x[1] for x in c),default=0),3),'w',round(max((abs(x[2]) for x in c),default=0),3),'E',max((abs(x[2]) for x in e),default=0),max((abs(x[3]) for x in e),default=0),set(x[1] for x in e),'dyaw',round(dy,1),'gz',round(gz,3),'pos',(round(p[-1][1],2),round(p[-1][2],2),round(math.degrees(p[-1][3]))) if p else None)
    t+=step
