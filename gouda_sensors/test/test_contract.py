from gouda_sensors.contract import CloudContract
import pytest


def observation(**kw):
    data = dict(frame='hesai_lidar', stamp=10., now_ros=10., now_mono=1.,
                xyz=[(1., 2., 3.)], fields={'x', 'y', 'z'})
    return data | kw


def test_fresh_and_wall_deadline_when_ros_clock_stops():
    c = CloudContract()
    assert c.observe(**observation())
    assert c.check(1.1, 10.1)[0]
    assert not c.check(1.4, 10.)[0]


@pytest.mark.parametrize('change', [dict(frame='wrong'), dict(stamp=9.), dict(stamp=11.),
    dict(xyz=[]), dict(xyz=[(float('nan'), 0., 0.)]), dict(fields={'x', 'y'})])
def test_invalid(change):
    assert not CloudContract().observe(**observation(**change))


def test_duplicate_and_backward_stamp():
    c = CloudContract()
    assert c.observe(**observation())
    assert not c.observe(**observation(now_mono=1.1))
    assert not c.observe(**observation(stamp=9.99))
