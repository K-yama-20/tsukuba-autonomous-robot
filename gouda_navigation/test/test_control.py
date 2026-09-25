import math
from gouda_navigation.control import Follower


def test_goal_cancel_and_stale():
    f=Follower();f.set_path([(0,0),(2,0)])
    assert f.update(0,0,0,0,0,0)==0
    assert f.update(0,0,0,0,0,.3)==1
    assert f.update(0,0,0,.3,0,.4,False)==0
    assert not f.path and f.state=='FAULT'
    f.set_path([(0,0),(2,0)]);f.cancel();assert f.state=='CANCELLED'


def test_turn_and_wrap():
    f=Follower();f.set_path([(0,0),(-2,.01)])
    f.update(0,0,-math.pi+.01,0,0,0)
    assert f.update(0,0,-math.pi+.01,0,0,.3)==1
    f.set_path([(0,0),(0,2)]);f.update(0,0,0,0,0,1)
    assert f.update(0,0,0,0,0,1.3)==3
    assert f.update(0,0,1.5,0,.3,1.4)==0


def test_reached_and_invalid_path():
    f=Follower();f.set_path([(0,0),(1,0)])
    assert f.update(.95,0,0,0,0,0)==0 and f.state=='REACHED'
    f.set_path([(float('nan'),0)]);assert f.state=='INVALID_PATH'
