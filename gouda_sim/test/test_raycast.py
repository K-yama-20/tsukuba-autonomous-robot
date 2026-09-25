import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gouda_sim.raycast import scan, BOXES

def test_corridor_rays_are_finite_and_match_obstacle_front():
    p=scan((0,0,1.1),np.eye(3),np.random.default_rng(270))
    assert len(p)>5000 and np.isfinite(p).all()
    front=p[(p[:,0]>0)&(np.abs(p[:,1])<.05)&(p[:,2]<0)&(p[:,2]>-.4)]
    assert len(front)>0
    assert abs(float(np.median(front[:,0]))-4.8)<.03
    assert np.linalg.norm(p,axis=1).min()>1.

def test_world_geometry_and_cpu_lidar_use_same_boxes():
    import xml.etree.ElementTree as E
    world=E.parse(Path(__file__).resolve().parents[1]/'worlds/corridor.sdf').getroot().find('world')
    for name,(center,size) in zip(('left_wall','right_wall','end_wall','obstacle'),BOXES):
        model=world.find(f"model[@name='{name}']")
        assert tuple(map(float,model.findtext('pose').split()[:3]))==center
        assert tuple(map(float,model.findtext('link/collision/geometry/box/size').split()))==size
