import sys,math,pickle,collections
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
bag=sys.argv[1]
want=['/cmd_vel','/cmd_vel_nav','/vehicle/joystick_command','/esp32/status','/sensors/imu/data','/plan','/local_plan','/local_costmap/costmap','/tf','/speed_limit','/mode/state','/control/motion_hold']
r=rosbag2_py.SequentialReader()
r.open(rosbag2_py.StorageOptions(uri=bag,storage_id='mcap'),rosbag2_py.ConverterOptions('',''))
types={t.name:t.type for t in r.get_all_topics_and_types()}
print({k:types.get(k) for k in want})
print('odom-like',[k for k in types if 'odom' in k or 'pose' in k][:15])
r.set_filter(rosbag2_py.StorageFilter(topics=[k for k in want if k in types]))
cls={k:get_message(types[k]) for k in want if k in types}
out=collections.defaultdict(list); grids=[]
tfs={}
while r.has_next():
    k,d,t=r.read_next(); t=t*1e-9; m=deserialize_message(d,cls[k])
    if k in('/cmd_vel','/cmd_vel_nav'):
        tw=m.twist if hasattr(m,'twist') else m; out[k].append((t,tw.linear.x,tw.angular.z))
    elif k=='/sensors/imu/data': out[k].append((t,m.angular_velocity.x,m.angular_velocity.y,m.angular_velocity.z,m.linear_acceleration.x,m.linear_acceleration.y))
    elif k=='/vehicle/joystick_command': out[k].append((t,)+tuple(getattr(m,a,None) for a in m.__slots__ if a.lstrip('_') in('forward','turn','x','y')))
    elif k=='/esp32/status':
        if not out['fields']: out['fields']=[a for a in m.__slots__]
        out[k].append((t,getattr(m,'source',None),getattr(m,'applied_x_q10000',None),getattr(m,'applied_y_q10000',None)))
    elif k=='/tf':
        for x in m.transforms:
            key=(x.header.frame_id,x.child_frame_id)
            if key in(('map','odom'),('odom','base_link'),('odom','base_footprint')):
                q=x.transform.rotation; out['tf'+str(key)].append((t,x.transform.translation.x,x.transform.translation.y,math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y**2+q.z**2))))
    elif k=='/plan': out[k].append((t,[(p.pose.position.x,p.pose.position.y) for p in m.poses[::10]],len(m.poses)))
    elif k=='/local_costmap/costmap': grids.append((t,m.info.width,m.info.height,m.info.resolution,m.info.origin.position.x,m.info.origin.position.y,bytes(bytearray(x&255 for x in m.data))))
    elif k=='/speed_limit': out[k].append((t,m.speed_limit,m.percentage))
    elif k=='/control/motion_hold': out[k].append((t,m.hold))
print({k:len(v) for k,v in out.items()},'grids',len(grids))
pickle.dump((dict(out),grids),open('/tmp/bag_02.pkl','wb'))
