import math
from gouda_navigation.control import Follower


def test_goal_heading_waits_for_settle_and_explicitly_aligns():
    f=Follower();f.set_path([(0,0)],math.pi/2)
    assert f.update(0,0,0,0,0,0)==0
    assert f.update(0,0,0,0,0,.3)==3
    assert f.state=='ALIGNING'
    assert f.update(0,0,1.5,0,.3,.4)==0
    assert f.state!='REACHED'
    assert f.update(0,0,math.pi/2,0,0,1.5)==0
    assert f.state=='REACHED'


def test_cancellation_removes_heading_target():
    f=Follower();f.set_path([(0,0)],math.pi/2);f.cancel()
    assert f.update(0,0,0,0,0,1)==0
    assert f.final_yaw is None
