"""CPU beam intersections with the exact static corridor boxes used by Gazebo.
This backend excludes the known robot itself. It is not an arbitrary-world lidar.
"""
import numpy as np
BOXES=[((10,1.7,1.5),(30,.2,3)),((10,-1.7,1.5),(30,.2,3)),((25,0,1.5),(.2,3.4,3)),((5,0,.6),(.4,.8,1.2))]

def beams():
    h,v=np.meshgrid(np.linspace(-np.pi,np.pi,720),np.linspace(-.4,.3,16))
    return np.stack((np.cos(v)*np.cos(h),np.cos(v)*np.sin(h),np.sin(v)),axis=-1).reshape(-1,3)
BEAMS=beams()

def scan(origin,rotation,rng):
    directions=BEAMS@np.asarray(rotation).T
    origin=np.asarray(origin);distances=np.full(len(directions),30.)
    for center,size in BOXES:
        lo=np.asarray(center)-np.asarray(size)/2;hi=np.asarray(center)+np.asarray(size)/2
        with np.errstate(divide='ignore',invalid='ignore'):
            a=(lo-origin)/directions;b=(hi-origin)/directions
        near=np.min(np.stack((a,b)),axis=0).max(axis=1)
        far=np.max(np.stack((a,b)),axis=0).min(axis=1)
        hit=(far>=np.maximum(near,.4))&(near>=.4)
        distances=np.minimum(distances,np.where(hit,near,30.))
    with np.errstate(divide='ignore',invalid='ignore'):
        ground=-origin[2]/directions[:,2]
    distances=np.minimum(distances,np.where((ground>=.4)&(directions[:,2]<0),ground,30.))
    valid=(distances>.4)&(distances<30.)
    noisy=distances[valid]+rng.normal(0,.01,int(valid.sum()))
    return (BEAMS[valid]*noisy[:,None]).astype(np.float32)
