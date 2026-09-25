#!/usr/bin/env python3
"""Synthetic mechanics, drawing-based envelope. Reproducible standalone SDF."""
from pathlib import Path
import xml.etree.ElementTree as E

def el(p,t,text=None,**attrs):
 c=E.SubElement(p,t,attrs)
 if text is not None:c.text=str(text)
 return c

def shape(link,name,kind,values,pose=None):
 for tag in ('collision','visual'):
  c=el(link,tag,name=name)
  if pose:el(c,'pose',pose)
  g=el(el(c,'geometry'),kind)
  for k,v in values.items():el(g,k,v)
 return c

def inertia(link,mass=1):
 i=el(link,'inertial');el(i,'mass',mass);j=el(i,'inertia')
 for k in ('ixx','iyy','izz'):el(j,k,max(.001,mass*.1))

s=E.Element('sdf',version='1.9');w=el(s,'world',name='gouda_corridor')
p=el(w,'physics',name='physics',type='ignored');el(p,'max_step_size',.002);el(p,'real_time_factor',1)
for name,kind in [('physics','Physics'),('user-commands','UserCommands'),('scene-broadcaster','SceneBroadcaster'),('sensors','Sensors'),('imu','Imu')]:
 p=el(w,'plugin',filename=f'gz-sim-{name}-system',name=f'gz::sim::systems::{kind}')
 if kind=='Sensors':el(p,'render_engine','ogre')
l=el(w,'light',name='sun',type='directional');el(l,'pose','0 0 10 0 0 0');el(l,'direction','-.5 .1 -1');el(l,'diffuse','.8 .8 .8 1')
m=el(w,'model',name='ground');el(m,'static','true');l=el(m,'link',name='ground');shape(l,'ground','plane',dict(normal='0 0 1',size='100 100'))
for name,pos,size in [('left_wall','10 1.7 1.5','30 .2 3'),('right_wall','10 -1.7 1.5','30 .2 3'),('end_wall','25 0 1.5','.2 3.4 3'),('obstacle','5 0 .6','.4 .8 1.2')]:
 m=el(w,'model',name=name);el(m,'static','true');el(m,'pose',pos+' 0 0 0');l=el(m,'link',name='link');shape(l,'box','box',dict(size=size))
m=el(w,'model',name='gouda');el(m,'pose','0 0 .005 0 0 0')
l=el(m,'link',name='body');el(l,'pose','0 0 .5 0 0 0');inertia(l,100);shape(l,'body_box','box',dict(size='1.105 .600 .900'))
i=el(l,'sensor',name='imu',type='imu');el(i,'always_on','true');el(i,'update_rate',100);el(i,'topic','/gouda/imu')
g=el(l,'sensor',name='lidar',type='gpu_lidar');el(g,'pose','0 0 .6 0 0 0');el(g,'always_on','true');el(g,'update_rate',10);el(g,'topic','/gouda/lidar')
r=el(g,'lidar');scan=el(r,'scan')
for axis,samples,amin,amax in [('horizontal',720,-3.14159265359,3.14159265359),('vertical',16,-.4,.3)]:
 a=el(scan,axis)
 for k,v in dict(samples=samples,resolution=1,min_angle=amin,max_angle=amax).items():el(a,k,v)
a=el(r,'range')
for k,v in dict(min=.4,max=30,resolution=.01).items():el(a,k,v)
a=el(r,'noise')
for k,v in dict(type='gaussian',mean=0,stddev=.01).items():el(a,k,v)
for name,y in [('left',.275),('right',-.275)]:
 l=el(m,'link',name=name+'_wheel');el(l,'pose',f'0 {y} .16 -1.57079632679 0 0');inertia(l,2);shape(l,'wheel','cylinder',dict(radius=.16,length=.05))
 j=el(m,'joint',name=name+'_joint',type='revolute');el(j,'parent','body');el(j,'child',name+'_wheel');el(el(j,'axis'),'xyz','0 0 1')
for name,x in [('front',.43),('rear',-.43)]:
 l=el(m,'link',name=name+'_support');el(l,'pose',f'{x} 0 .04 0 0 0');inertia(l,.1);shape(l,'support','sphere',dict(radius=.04))
 collision=l.find('collision');o=el(el(el(collision,'surface'),'friction'),'ode');el(o,'mu',0);el(o,'mu2',0)
 j=el(m,'joint',name=name+'_fixed',type='fixed');el(j,'parent','body');el(j,'child',name+'_support')
p=el(m,'plugin',filename='gz-sim-diff-drive-system',name='gz::sim::systems::DiffDrive')
for k,v in dict(left_joint='left_joint',right_joint='right_joint',wheel_separation=.55,wheel_radius=.16,topic='/model/gouda/cmd_vel',odom_topic='/model/gouda/odometry',frame_id='odom_lidar',child_frame_id='base_link',odom_publish_frequency=50).items():el(p,k,v)
p=el(m,'plugin',filename='gz-sim-odometry-publisher-system',name='gz::sim::systems::OdometryPublisher')
for k,v in dict(odom_topic='/model/gouda/ground_truth',odom_frame='odom_lidar',robot_base_frame='base_link',dimensions=3,odom_publish_frequency=50).items():el(p,k,v)
# Gazebo-only self-render exclusion; keep physical collision geometry intact.
for visual in m.findall('link/visual'):el(visual,'visibility_flags',2)
el(r,'visibility_mask',1)
E.indent(s);E.ElementTree(s).write(Path(__file__).resolve().parents[1]/'worlds/corridor_gpu.sdf',encoding='unicode',xml_declaration=True)
w.remove(next(p for p in w.findall('plugin') if p.get('name')=='gz::sim::systems::Sensors'))
body=m.find("link[@name='body']");body.remove(body.find("sensor[@name='lidar']"))
for visual in m.findall('link/visual'):
    flag=visual.find('visibility_flags')
    if flag is not None:visual.remove(flag)
E.indent(s);E.ElementTree(s).write(Path(__file__).resolve().parents[1]/'worlds/corridor.sdf',encoding='unicode',xml_declaration=True)
