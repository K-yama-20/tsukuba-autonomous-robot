"""End-to-end acceptance against the isolated simulation GUI (already running)."""
import json
import math
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from pathlib import Path
base=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8765'
token=json.load(urlopen(base+'/api/session'))['token']
results={}


def state():return json.load(urlopen(base+'/api/state',timeout=5))
def post(action,**data):
    try:return json.load(urlopen(Request(base+'/api/'+action,data=json.dumps(data).encode(),headers={'Content-Type':'application/json','X-Gouda-Session':token}),timeout=8))
    except HTTPError as e:
        print('HTTP',action,e.code,e.read().decode(),flush=True);raise
def wait(predicate,seconds=10):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        s=state()
        if predicate(s):return s
        time.sleep(.12)
    raise AssertionError({k:s[k] for k in ('pose','nav','start_reasons','logs')})
def reject(action,**data):
    try:post(action,**data)
    except HTTPError as e:
        assert e.code in (400,409);return True
    raise AssertionError('Unexpected acceptance: '+action)


try:
    assert state()['mode']=='simulation'
    post('stop');wait(lambda s:s['stop_status']=='停止確認済み')
    post('initial_pose',x=0.,y=0.,yaw=math.pi/2)
    s=wait(lambda s:abs(s['pose']['yaw']-math.pi/2)<.03)
    results['initial_position_and_heading']=True
    post('load_map',id=s['maps'][0]['id'])
    assert not state()['path'];results['saved_map_reload']=True
    results['invalid_pose_rejected']=reject('target',x=float('nan'),y=0,yaw=0)
    results['out_of_bounds_reposition_rejected']=reject('initial_pose',x=8,y=0,yaw=0)
    post('target',x=.8,y=.4,yaw=math.pi/2);post('plan')
    s=wait(lambda s:s['nav']['preview_ready'] and s['path'])
    results['wrong_preview_id_rejected']=reject('start',plan_id='old-preview')
    old=s['plan_id'];post('initial_pose',x=0.,y=0.,yaw=0.)
    results['reposition_invalidates_preview']=reject('start',plan_id=old)
    post('plan');s=wait(lambda s:s['nav']['preview_ready'] and s['path'])
    p0=s['pose'];time.sleep(1);s=state()
    assert s['esp']['flags']==0 and abs(s['pose']['v'])<.001
    post('start',plan_id=s['plan_id'])
    s=wait(lambda s:s['nav']['state']=='REACHED',65)
    results['turning_goal_position_error_m']=math.hypot(s['pose']['x']-.8,s['pose']['y']-.4)
    results['turning_goal_heading_error_rad']=abs(math.atan2(math.sin(s['pose']['yaw']-math.pi/2),math.cos(s['pose']['yaw']-math.pi/2)))
    assert results['turning_goal_position_error_m']<=.17 and results['turning_goal_heading_error_rad']<=.15
    post('stop');s=wait(lambda s:s['stop_status']=='停止確認済み');p0=s['pose']
    post('target',x=p0['x']+.5,y=p0['y'],yaw=0.);post('plan')
    s=wait(lambda s:s['nav']['preview_ready'] and s['path']);post('start',plan_id=s['plan_id']);post('stop')
    wait(lambda s:s['stop_status']=='停止確認済み');time.sleep(1.5);s=state()
    assert s['esp']['flags']==0 and math.hypot(s['pose']['x']-p0['x'],s['pose']['y']-p0['y'])<.05
    results['cancel_during_startup_no_revival']=True
    print(json.dumps(results,indent=2),flush=True)
finally:
    post('stop')
    if len(sys.argv)>2:Path(sys.argv[2]).write_text(json.dumps(results,indent=2))
