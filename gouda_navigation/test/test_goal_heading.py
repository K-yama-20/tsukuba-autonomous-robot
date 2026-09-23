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


def test_final_heading_converges_with_delayed_discrete_turns():
    # The model can only request a fixed angular speed; stopping also rotates.
    # Too-tight final tolerance causes endless direction reversals near the goal.
    from gouda_sim.model import Model
    for target in (-3.,-1.57,-.2,-.1,.1,.2,1.57,3.):
        f=Follower();f.set_path([(0,0)],target)
        m=Model();commands=[]
        for i in range(1200):
            t=i*.05
            motion=f.update(m.x,m.y,m.yaw,m.vx,m.wz,t)
            commands.append(motion)
            # Include 100 ms command/status transport delay.
            m.accept(commands[-3] if len(commands)>=3 else 0,t);m.step(t,.05)
            if f.state=='REACHED':break
        assert f.state=='REACHED',(target,m.yaw,f.state)
        assert abs(math.atan2(math.sin(m.yaw-target),math.cos(m.yaw-target)))<=.15
