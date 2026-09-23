import json
import math
from pathlib import Path
import tempfile
import threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import pytest
from gouda_gui.core import MapStore, ProjectionMap, finite_pose, serve


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
