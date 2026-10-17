#!/bin/bash
# VM test of the two fixes (G-REC-ROSBAG-RESTART, G-GLIM-EXIT) on the test stack (own ROS domain, no sensor drivers).
set -o pipefail
WS=~/gouda_fix_ws; REPO=$WS/src/tsukuba-autonomous-robot; ROOT=/tmp/fixtest
export ROS_DOMAIN_ID=77
source /opt/ros/jazzy/setup.bash; source $WS/install/setup.bash
rm -rf $ROOT; mkdir -p $ROOT
bash $REPO/gouda_core/test/stack.sh start $ROOT || exit 1
URL=$(cat $ROOT/run/monitor.url); echo "monitor $URL"
svc() { ros2 service call "/$1" std_srvs/srv/Trigger "{}" 2>&1 | grep -oE "success=(True|False), message='[^']*'" ; }
state() { curl -s "$URL/api/state" | python3 -c "import json,sys; s=json.load(sys.stdin); f=s['record']['fields']; print('record:', {k: f.get(k) for k in ('rosbag_active','rosbag_output','failures','last_failure')})"; }
echo "=== R1: rosbag start/stop/start/stop in one session"
svc record/rosbag/start; sleep 4; svc record/rosbag/stop; sleep 2
svc record/rosbag/start; sleep 4; state; svc record/rosbag/stop; sleep 2
S=$(ls -d $ROOT/records/*/ | head -1); echo "session $S"; ls -la $S/rosbag/
for b in $S/rosbag/bag_0*/; do echo "$b: $(ls $b | tr '\n' ' ')"; done
python3 -c "import json; d=json.load(open('$S/session.json')); print('rosbag_outputs:', [(o['output'].split('/')[-1], o['result']) for o in d['rosbag_outputs']], 'failures:', len(d['failures']))"
echo "=== R2: ros2 bag record killed while recording (unexpected exit)"
svc record/rosbag/start; sleep 4
P=$(pgrep -f "[r]os2 bag record -a -o $S"rosbag/bag_03 | head -1); echo "killing pid $P"; kill -KILL $P; sleep 3
state
python3 -c "import json; d=json.load(open('$S/session.json')); print('last failure:', d['failures'][-1]['what'], d['failures'][-1]['error'][:160]); print('outputs:', [(o['output'].split('/')[-1], o['result']) for o in d['rosbag_outputs']])"
echo "=== G1: GLIM killed during mapping"
svc mode/start_mapping; sleep 6
GP=$(pgrep -f "[g]lim_rosnode" | head -1); echo "GLIM pid $GP"; kill -ABRT $GP; sleep 4
curl -s "$URL/api/state" | python3 -c "import json,sys; s=json.load(sys.stdin); ev=[e for e in s['events'] if e['event']=='glim_exited']; print('glim_exited events:', len(ev)); [print(' ', e['transition_id'], e['reason'][:200]) for e in ev]; print('mode:', s['mode']['fields'].get('mode'))"
svc mode/end_mapping; sleep 5
curl -s "$URL/api/state" | python3 -c "import json,sys; s=json.load(sys.stdin); ev=[e for e in s['events'] if e['event'] in ('mapping_stopped','source_map_not_registered')]; [print(' ', e['event'], e['reason'][:120], json.loads(e['details']).get('glim_exited_unexpectedly_at')) for e in ev]"
echo "=== G2: normal mapping start/end (no glim_exited expected)"
svc mode/start_mapping; sleep 6; svc mode/end_mapping; sleep 8
curl -s "$URL/api/state" | python3 -c "import json,sys; s=json.load(sys.stdin); ev=[e for e in s['events'] if e['event']=='glim_exited']; print('glim_exited events (still 1 expected):', sum(e['count'] for e in ev))"
bash $REPO/gouda_core/test/stack.sh stop $ROOT
grep -E "rosbag_watch|rosbag recording failed|GLIM exited" $ROOT/run/stack.launch.log | cut -c1-200 | head -5
