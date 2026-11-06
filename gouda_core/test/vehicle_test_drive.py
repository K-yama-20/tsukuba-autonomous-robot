"""Test only: drives the /dev API of a running test stack (ubuntu_vehicle_test.sh) and checks what comes back."""
import json, os, sys, time, urllib.request, urllib.error

url = sys.argv[1].rstrip('/')
fails = []


def get(p):
    return json.load(urllib.request.urlopen(url + p, timeout=10))


def post(p, b):
    r = urllib.request.Request(url + p, json.dumps(b).encode(), {'Content-Type': 'application/json'})
    try:
        return json.load(urllib.request.urlopen(r, timeout=30))
    except urllib.error.HTTPError as e:
        return json.load(e)


def check(name, ok, detail=''):
    print(('PASS' if ok else 'FAIL'), name, detail, flush=True)
    if not ok: fails.append(name)


def wait_end(limit):
    t = time.time()
    while time.time() - t < limit:
        v = get('/api/state')['vehicle_test']
        if v['state'] == 'idle' and t + 1 < time.time(): return v
        time.sleep(0.5)
    return get('/api/state')['vehicle_test']


defs = get('/api/vehicle_tests')
check('definition served', [t['id'] for t in defs['tests']] == ['motion_start'])
cond = dict(sections=['delay', 'threshold_up', 't_lock'], repeats=1, settle_s=2.5, baseline_s=3.0, delay_angles_deg=[90], delay_amounts=[0.4],
            threshold_angles_deg=[90, 0], threshold_levels=[0.08, 0.1, 0.14, 0.2], stair_hold_s=1.0, gaps_s=[0.25, 2.0])
r = post('/api/vehicle_test_start', {'test_id': 'motion_start', 'params': cond}); check('start accepted', r['ok'], r)
time.sleep(2)
r = post('/api/command/start_autonomy', {}); check('autonomy refused during a test', not r['ok'], r.get('message'))
r = post('/api/command/start_mapping', {}); check('mapping refused during a test', not r['ok'], r.get('message'))
r = post('/api/vehicle_test_start', {'test_id': 'motion_start', 'params': cond}); check('second start refused', not r['ok'], r.get('message'))
v = wait_end(120); check('first run completed', v['end_reason'] == 'completed', v)
res = get('/api/vehicle_test_run/' + v['run_id'])['result']
print(json.dumps(res['tables'], ensure_ascii=False), res['clock'], res['axes'], res['sigma'])
tb = {t['key']: t['rows'] for t in res['tables']}
check('T found', all(x['level'] == [0.14] for x in tb['threshold_up']), tb['threshold_up'])
check('delay over the model value', all(x['mean_s'] > 0.3 for x in tb['delay']), tb['delay'])
check('t_lock bracket', {x['gap_s']: x['locked'] for x in tb['t_lock']} == {0.25: None, 2.0: True}, tb['t_lock'])
check('no delay is negative', all(x['min_s'] >= 0 for k in ('delay', 't_lock') for x in tb[k] if x['n']))
check('clock fitted', res['clock'] and res['clock']['samples'] > 10)
tr = next(x['trial'] for x in res['rows'] if x.get('ran'))
w = get(f"/api/vehicle_test_run/{v['run_id']}/wave/{tr}?points=500"); check('waveform', len(w['imu_yaw']['t']) > 10 and len(w['status']['t']) > 3 and len(w['command']['t']) > 3)
# stop, then a further run without restarting anything
r = post('/api/vehicle_test_start', {'test_id': 'motion_start', 'params': dict(cond, sections=['delay'], repeats=20)}); check('second run accepted', r['ok'], r)
time.sleep(6)
r = post('/api/vehicle_test_stop', {}); check('stop accepted', r['ok'], r)
t0 = time.time(); v = wait_end(20); check('stop ended the run', v['end_reason'] == 'cancelled', (v, time.time() - t0))
res = get('/api/vehicle_test_run/' + v['run_id'])['result']; check('a stopped run has a result', res['end_reason'] == 'cancelled')
check('the second run really drove', any(x.get('ran') for x in res['rows']), [x['trial'] for x in res['rows']][:3])   # TRB-014: a new bridge session restarts seq
r = post('/api/vehicle_test_stop', {}); check('stop with no test says so', not r['ok'], r.get('message'))
# a lost IMU: neutral, wait, the trial repeats, and the run completes (DEC-414)
pause = os.path.join(sys.argv[2], 'imu_pause')
r = post('/api/vehicle_test_start', {'test_id': 'motion_start', 'params': dict(cond, sections=['delay'], repeats=3)}); check('IMU loss run accepted', r['ok'], r)
time.sleep(7); open(pause, 'w').close(); time.sleep(3)
s = get('/api/state')['vehicle_test']; check('still running while the IMU is lost', s['state'] != 'idle', s)
os.remove(pause)
v = wait_end(120); check('IMU loss run completed', v['end_reason'] == 'completed', v)
res = get('/api/vehicle_test_run/' + v['run_id'])['result']; check('the retry is counted', res.get('retries', 0) >= 1, res.get('retries'))
check('every trial has a row', all(x.get('ran') for x in res['rows']), [x['trial'] for x in res['rows'] if not x.get('ran')])
r = post('/api/command/start_mapping', {})
if r['ok']:
    time.sleep(2)
    post('/api/vehicle_test_start', {'test_id': 'motion_start', 'params': cond}); v = wait_end(15); check('refused outside manual', v['end_reason'] == 'refused', v)
    post('/api/command/end_mapping', {})
else:
    print('NOT RUN refused outside manual: mapping did not start', r.get('message'))
print('FAILS', fails)
sys.exit(1 if fails else 0)
