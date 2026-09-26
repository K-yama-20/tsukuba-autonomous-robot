import json
import os
import pytest
from gouda_navigation.time_sync import ClockGate, check_runtime_clock, point_time_error
from gouda_navigation.mapping import DEFAULT_SETTINGS, validate_mapping_settings


def evidence(t, **extra):
    return dict(state='host_mapped',measurement_stamp=t,residual_ms=.1,**extra)


def test_missing_or_unlocked_evidence_cannot_feed_glim():
    g=ClockGate('host_mapped')
    assert not g.accept('imu',100.,100.01,1.)
    g.add_status(dict(state='unlocked',measurement_stamp=100.,residual_ms=.1),1.)
    assert not g.accept('imu',100.,100.02,1.01)
    g.add_status(evidence(100.),1.02)
    assert g.accept('imu',100.,100.03,1.02)
    assert not g.accept('imu',100.,100.04,1.03)
    assert not g.accept('imu',100.01,100.05,1.04) # per-sample evidence required


def test_pairing_age_epoch_and_loss():
    g=ClockGate('host_mapped')
    g.add_status(evidence(100.),1.)
    assert g.accept('imu',100.,100.01,1.)
    assert g.accept('lidar',100.,100.02,1.01)
    state=g.snapshot(1.02)
    assert state['status']=='host_mapped' and state['hardware_synchronized'] is False
    assert g.snapshot(2.)['status']=='blocked'
    assert not g.accept('lidar',100.02,101.01,2.)
    assert not ClockGate('simulation').accept('imu',37.,100.,1.)
    assert not ClockGate('simulation').accept('imu',101.,100.,1.)


def test_clock_jump_is_latched_until_restart():
    g=ClockGate('simulation');assert g.accept('imu',100.,100.,1.)
    g.policy='host_mapped';g.add_status(evidence(101.),1.01)
    assert not g.accept('imu',101.,101.,1.01)
    assert g.reset_required
    g.add_status(evidence(101.01),1.02)
    assert not g.accept('imu',101.01,101.01,1.02)


def test_large_or_nonfinite_residual_rejected():
    for residual in (3.,float('nan'),-1.):
        g=ClockGate('host_mapped');s=evidence(100.);s['residual_ms']=residual;g.add_status(s,1.)
        assert not g.accept('imu',100.,100.01,1.)


def test_runtime_rejects_receipt_time_and_fake_simulation(tmp_path,monkeypatch):
    import yaml
    config=tmp_path/'hesai.yaml';host=tmp_path/'host.json'
    host.write_text(json.dumps(dict(hesai_config=str(config))))
    cfg={'clock_policy':'host_mapped'}
    config.write_text(yaml.safe_dump({'lidar':[{'driver':{'source_type':1,'use_timestamp_type':1}}]}))
    with pytest.raises(ValueError,match='sensor timestamps'):check_runtime_clock(cfg,False,host)
    config.write_text(yaml.safe_dump({'lidar':[{'driver':{'source_type':1,'use_timestamp_type':0}}]}))
    check_runtime_clock(cfg,False,host)
    with pytest.raises(ValueError):check_runtime_clock({'clock_policy':'simulation'},False,host)
    monkeypatch.setenv('ROS_DOMAIN_ID','99')
    with pytest.raises(ValueError):check_runtime_clock({'clock_policy':'simulation'},True)
    monkeypatch.setenv('ROS_DOMAIN_ID','101');check_runtime_clock({'clock_policy':'simulation'},True)


def test_pps_or_operator_note_is_not_hardware_clock_support():
    errors=validate_mapping_settings({**DEFAULT_SETTINGS,'backend':'glim_imu','clock_policy':'external_common','clock_evidence':'PPS observed'},True)
    assert any('External IMU clock' in e for e in errors)


def test_per_point_times_reject_nan_wrong_epoch_and_wrong_units():
    from sensor_msgs.msg import PointField
    from sensor_msgs_py.point_cloud2 import create_cloud
    from std_msgs.msg import Header
    from builtin_interfaces.msg import Time
    fields=[PointField(name='time',offset=0,datatype=PointField.FLOAT64,count=1)]
    cfg=dict(point_time_field='time',point_time_datatype='float64',point_time_mode='relative',point_time_unit='seconds')
    def cloud(values):return create_cloud(Header(stamp=Time(sec=100)),fields,[(v,) for v in values])
    assert not point_time_error(cloud([0.,.1]),cfg)
    assert point_time_error(cloud([float('nan')]),cfg)
    assert point_time_error(cloud([100000.]),cfg)
    cfg['point_time_mode']='absolute'
    assert not point_time_error(cloud([100.,100.1]),cfg)
    assert point_time_error(cloud([63.]),cfg)

