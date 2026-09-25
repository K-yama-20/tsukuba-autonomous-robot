import json
import math
from pathlib import Path
import tempfile
import threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import pytest
from gouda_gui.core import MapStore, ProjectionMap, finite_pose, serve, mapping_start_backend, glim_session_output_directory, compose_pose_transform, validate_autonomy_goal, autonomy_start_blocker


def test_projection_preserves_unknown_and_hits():
    mapper=ProjectionMap(size=4,resolution=.1)
    mapper.update((0,0),[(1,0,.5)])
    g=mapper.grid;n=g['width']
    assert g['data'][20*n+30]==100
    assert g['data'][20*n+25]==0
    assert g['data'][0]==-1
    mapper.update((0,0),[(1.5,0,.5)])
    assert g['data'][20*n+30]==100
    with pytest.raises(ValueError):mapper.update((100,0),[(101,0,.5)])


def test_map_roundtrip_and_pgm_orientation(tmp_path):
    m=ProjectionMap(size=2,resolution=.1);m.update((0,0),[(.4,.3,.5)])
    store=MapStore(tmp_path);meta=store.save('広場 / <test>',m.grid,'simulation',1)
    assert store.list()==[meta]
    loaded,grid=store.load(meta['id']);assert grid==m.grid
    assert (tmp_path/meta['id']/'map.yaml').is_file()
    pixels=(tmp_path/meta['id']/'map.pgm').read_bytes().split(b'\n',3)[3]
    x,y=m.cell(.4,.3);assert pixels[(19-y)*20+x]==0
    with pytest.raises(ValueError):store.load('../../etc')
    with pytest.raises(ValueError):store.save('',grid,'simulation',1)
    with pytest.raises(ValueError):store.save('空',ProjectionMap().grid,'simulation',0)


@pytest.mark.parametrize('value',[float('nan'),float('inf'),True,'1',None])
def test_invalid_pose(value):
    with pytest.raises(ValueError):finite_pose(dict(x=value,y=0,yaw=0))


def test_http_rejects_cross_origin_and_limits_actions(tmp_path):
    class Backend:
        def snapshot(self):return {'mode':'simulation'}
        def command(self,action,data):return {'ok':True,'action':action}
    (tmp_path/'index.html').write_text('test')
    server=serve(Backend(),tmp_path,port=0)
    base='http://127.0.0.1:'+str(server.server_port)
    try:
        assert json.load(urlopen(base+'/api/state'))['mode']=='simulation'
        token=json.load(urlopen(base+'/api/session'))['token']
        def post(headers):return urlopen(Request(base+'/api/stop',data=b'{}',headers=headers))
        with pytest.raises(HTTPError) as error:post({})
        assert error.value.code==403
        with pytest.raises(HTTPError) as error:post({'X-Gouda-Session':token,'Origin':'https://example.com'})
        assert error.value.code==403
        assert json.load(post({'X-Gouda-Session':token}))['action']=='stop'
        with pytest.raises(HTTPError):urlopen(base+'/../node.py')
    finally:server.shutdown();server.server_close()


def test_slam_map_commit_requires_graph_and_preserves_metadata(tmp_path):
    mapper=ProjectionMap(size=2,resolution=.1);mapper.update((0,0),[(.4,0,.5)])
    store=MapStore(tmp_path)
    def fail(directory):
        (directory/'slam.posegraph').write_bytes(b'partial')
        raise RuntimeError('serialization failed')
    with pytest.raises(RuntimeError):
        store.save('incomplete',mapper.grid,'live',1,finalize=fail)
    assert store.list()==[]
    def graph(directory):
        (directory/'slam.posegraph').write_bytes(b'graph')
        (directory/'slam.data').write_bytes(b'data')
    meta=store.save('test',mapper.grid,'replay',1,
                   details=dict(method='slam',pose_reference='hesai_lidar',extrinsics_validated=False),
                   finalize=graph)
    assert store.load(meta['id'])[0]['extrinsics_validated'] is False
    assert (tmp_path/meta['id']/'slam.data').read_bytes()==b'data'


def test_mapping_start_requires_matching_saved_and_effective_backend():
    saved={'backend':'glim_imu','compute':'cpu','calibration':'measured'}
    runtime=dict(saved)
    assert mapping_start_backend(saved,runtime,'glim_imu',package_available=True,glim_active=True)=='glim_imu'
    with pytest.raises(RuntimeError,match='再起動'):
        mapping_start_backend(saved,runtime,'kiss_icp',package_available=True,glim_active=False)
    with pytest.raises(RuntimeError,match='再起動'):
        mapping_start_backend(saved,{**runtime,'calibration':'changed'},'glim_imu',package_available=True,glim_active=True)


def test_mapping_start_requires_glim_readiness_package_and_live_session():
    config={'backend':'glim_imu','compute':'cpu'}
    with pytest.raises(RuntimeError,match='T_lidar'):
        mapping_start_backend(config,config,'glim_imu',['T_lidar_imu is UNKNOWN'],package_available=True,glim_active=True)
    with pytest.raises(RuntimeError,match='GLIMパッケージ'):
        mapping_start_backend(config,config,'glim_imu',package_available=False,glim_active=False)
    with pytest.raises(RuntimeError,match='入力が準備'):
        mapping_start_backend(config,config,'glim_imu',package_available=True,glim_active=False)


def test_mapping_start_refuses_simultaneous_kiss_and_glim():
    config={'backend':'kiss_icp','compute':'cpu'}
    with pytest.raises(RuntimeError,match='同時'):
        mapping_start_backend(config,config,'kiss_icp',package_available=None,glim_active=True)


def test_glim_output_directory_handles_uninitialized_api_field(tmp_path):
    class Session:map_output_directory=None
    expected=tmp_path/'session'
    assert glim_session_output_directory(Session(),expected)==expected
    Session.map_output_directory=tmp_path/'reported'
    assert glim_session_output_directory(Session(),expected)==tmp_path/'reported'


def test_glim_odom_is_transformed_once_through_map_to_odom():
    # map->odom_lidar has a 90-degree yaw and a translation; odom pose is local.
    p,q=compose_pose_transform((1,0,0),(0,0,0,1),(10,2,0),(0,0,math.sqrt(.5),math.sqrt(.5)))
    assert p==pytest.approx((10,3,0))
    assert q==pytest.approx((0,0,math.sqrt(.5),math.sqrt(.5)))
    # Applying the same transform twice would move the point to (7,12).
    p2,_=compose_pose_transform(p,q,(10,2,0),(0,0,math.sqrt(.5),math.sqrt(.5)))
    assert p2!=pytest.approx(p)


def test_autonomy_relative_goal_requires_finite_target_and_positive_speed():
    goal=validate_autonomy_goal({'goal':{'forward_m':1.2,'left_m':-.3,'yaw_rad':.5},'target_v_mps':.2,'target_w_rps':.4})
    assert goal=={'goal':{'forward_m':1.2,'left_m':-.3,'yaw_rad':.5},'target_v_mps':.2,'target_w_rps':.4}
    for data in (
        {'goal':{'forward_m':float('nan'),'left_m':0,'yaw_rad':0},'target_v_mps':.2,'target_w_rps':.4},
        {'goal':{'forward_m':0,'left_m':0,'yaw_rad':0},'target_v_mps':0,'target_w_rps':.4},
        {'goal':{'forward_m':0,'left_m':0,'yaw_rad':0},'target_v_mps':.2,'target_w_rps':float('inf')},
    ):
        with pytest.raises(ValueError):validate_autonomy_goal(data)


def test_autonomy_start_gate_requires_profile_config_fresh_sensors_calibration_recording():
    state={'phase':'idle','pose_fresh':True,'imu_fresh':True,'calibration_ready':True,'manual_override':False}
    gate=dict(profile_enabled=True,config_ready=True,state=state,state_fresh=True,recording_active=True)
    assert autonomy_start_blocker(**gate) is None
    for change in (
        {'profile_enabled':False}, {'config_ready':False}, {'state_fresh':False}, {'recording_active':False},
        {'state':{**state,'pose_fresh':False}}, {'state':{**state,'imu_fresh':False}},
        {'state':{**state,'calibration_ready':False,'reason':'T_body_lidar未測定'}},
        {'state':{**state,'manual_override':True}}, {'state':{**state,'phase':'running'}},
    ):
        assert autonomy_start_blocker(**(gate|change))
