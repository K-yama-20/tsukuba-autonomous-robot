#!/bin/bash
# TEST ONLY (第238便): one run of the confirmation-run course (drive_sim_course.py) through the real stack, as drive_sim.sh does it
# (stack.sh, mode manager, Nav2, pointcloud_to_laserscan, ESP32 simulator, nd07_stub.py), with a long timeout and a state log.
#   bash drive_sim_course.sh <scenario> <out_dir> [values.json]    values.json: {"key": value} of the /config 「Nav2」 tab, as drive_sim.sh
# Env: SIM_ARGS (drive_sim_node.py arguments, e.g. "--m1107 --seed 1"), ROS_DOMAIN_ID, SIM_SPEED (simulated time S times as fast:
#      needs a drive_sim_node.py with --speed and a TEST COPY of nav2_config.py with GOUDA_TEST_NAV2; the Nav2 wall-clock loops are
#      raised S times as in run4x.sh), MAX_SIM_S (default 2400), STALL_END_S (end after this many simulated s without 1 m; default 240).
# Results in <out_dir>: report.json, trace.csv, state.csv (wall, sim s, mode, stop_reason, progress m), events.txt (mode manager
# decisions and Nav2 recoveries from the stack log, wall-clock stamped), course.json (rule metrics), result.json.
set -o pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; repo="$(cd "$here/../.." && pwd)"; ws="$(cd "$repo/../.." && pwd)"
SCENARIO=$1; OUT=$2; VALUES=$3
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-180}
MAX_SIM_S=${MAX_SIM_S:-2400}; STALL_END_S=${STALL_END_S:-240}
ROOT=$(mktemp -d /tmp/course_sim.XXXXXX); mkdir -p "$OUT" "$ROOT/config"
source /opt/ros/jazzy/setup.bash; source "$ws/install/setup.bash"
S=${SIM_SPEED:-1}
# RAYTRACE_MIN_M (comparison condition only): raytrace_min_range of the XT-32 scan source in both costmaps' obstacle_layer
if [ "$S" != "1" ] || [ -n "$RAYTRACE_MIN_M" ]; then
  export GOUDA_TEST_NAV2=$(python3 - "$S" "$RAYTRACE_MIN_M" <<'PY'
import json, sys
s, rmin = float(sys.argv[1]), sys.argv[2]
d = {'params': {}}
if s != 1:
    d['use_sim_time'] = True
    d['params'] = {'controller_server': {'controller_frequency': 20.0 * s},
                   'local_costmap.local_costmap': {'update_frequency': 10.0 * s}, 'global_costmap.global_costmap': {'update_frequency': 1.0 * s}}
if rmin:
    for c in ('local_costmap', 'global_costmap'):
        d['params'][f'{c}.{c}.ros__parameters.obstacle_layer.scan'] = {'raytrace_min_range': float(rmin)}
print(json.dumps(d))
PY
)
  [ "$S" != "1" ] && SIM_ARGS="$SIM_ARGS --speed $S"
fi
PIDS=()
cleanup() {
  for p in "${PIDS[@]}"; do kill -INT "$p" 2>/dev/null; done
  sleep 1; bash "$here/stack.sh" stop "$ROOT" >/dev/null 2>&1
  for p in "${PIDS[@]}"; do kill -KILL "$p" 2>/dev/null; done
  [ -n "$ESP" ] && kill -KILL -- "-$ESP" 2>/dev/null
  cp "$ROOT/run/stack.launch.log" "$OUT/" 2>/dev/null; cp "$ROOT/run/nav2/nav2_params.yaml" "$ROOT/run/nav2/navigate_through_poses.xml" "$ROOT/run/nav2/overrides.json" "$OUT/" 2>/dev/null
  rm -rf "$ROOT"
}
trap cleanup EXIT
REQ=$(python3 "$here/drive_sim_course.py" fixture "$ROOT" "$SCENARIO") || exit 1
[ -n "$VALUES" ] && python3 -c "import json,sys; json.dump({'config_revision': 1, 'values': json.load(open(sys.argv[1]))}, open(sys.argv[2], 'w'))" "$VALUES" "$ROOT/config/nav2_recovery.json"
bash "$here/stack.sh" start "$ROOT" || exit 1
URL=$(cat "$ROOT/run/monitor.url")
setsid ros2 run gouda_core esp32_sim -- --path-file "$OUT/pty" --log "$OUT/esp32.log" > "$OUT/esp32.out" 2>&1 &
ESP=$!
for _ in $(seq 1 20); do [ -s "$OUT/pty" ] && break; sleep 0.5; done
for _ in $(seq 1 15); do ros2 param set /vehicle_bridge serial_port "$(cat "$OUT/pty")" 2>/dev/null | grep -q successful && break; sleep 2; done
ND07=$(pgrep -g "$(cat "$ROOT/run/stack.pid")" -f "lib/gouda_core/[g]ouda_global_localization"); [ -n "$ND07" ] && kill -INT "$ND07"; sleep 3
python3 "$here/nd07_stub.py" 0.1 > "$OUT/nd07_stub.out" 2>&1 &
PIDS+=($!)
# shellcheck disable=SC2086
PYTHONPATH="$here:$PYTHONPATH" python3 "$here/drive_sim_course.py" node "$SCENARIO" "$OUT/report.json" $SIM_ARGS > "$OUT/node.out" 2>&1 &
PIDS+=($!)
for _ in $(seq 1 30); do ros2 node list --no-daemon 2>/dev/null | grep -qx /gouda_global_localization && break; sleep 1; done
for _ in $(seq 1 20); do
  curl -s -X POST -H 'Content-Type: application/json' -d "$REQ" "$URL/api/command/start_autonomy" > "$OUT/start.json"
  grep -q 'is not running' "$OUT/start.json" || break; sleep 3
done
export ROUTE_M=$(PYTHONPATH="$here:$PYTHONPATH" python3 -c "import drive_sim_course as d,sys,numpy as np; r=np.array(d.scenario(sys.argv[1]).route); print(round(float(np.hypot(*np.diff(r,axis=0).T).sum()),1))" "$SCENARIO")
echo "wall,sim_s,mode,stop_reason,progress_frac,completed" > "$OUT/state.csv"
END=""
python3 -c "import json,sys; sys.exit(0 if json.load(open(sys.argv[1])).get('ok') else 1)" "$OUT/start.json" 2>/dev/null || END="start_refused"
if [ -n "$STOP_RESUME_WALL_S" ]; then   # the human at the stop line (一時停止線, DEC-482): 再開 STOP_RESUME_WALL_S wall seconds after the hold
  python3 - "$URL" "$OUT/report.json" "$STOP_RESUME_WALL_S" "$OUT/stop_events.csv" <<'PY' &
import json, sys, time, urllib.request
url, rep, wait, out = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
f = open(out, 'w'); f.write('wall,sim_s,event,detail\n'); f.flush()
def sim():
    try: return json.load(open(rep)).get('elapsed_s')
    except Exception: return ''
held_at, n = None, 0
while n < 10:
    try: s = json.load(urllib.request.urlopen(url + '/api/state', timeout=2))
    except Exception: break
    m, fl = s['mode']['name'], s['mode']['fields']
    held = fl.get('stop_reason') == 'rule_stop'
    if held and held_at is None:
        held_at = time.time(); f.write(f'{held_at:.1f},{sim()},hold,{fl.get("processing_state")}\n'); f.flush()
    if held_at is not None and time.time() - held_at >= wait:
        r = urllib.request.urlopen(urllib.request.Request(url + '/api/command/resume', data=b'{}', headers={'Content-Type': 'application/json'}), timeout=5).read().decode()
        f.write(f'{time.time():.1f},{sim()},resume,{r[:150].replace(",", ";")}\n'); f.flush(); held_at, n = None, n + 1
        time.sleep(2)
    if m == 'PAUSE': break
    time.sleep(0.2)
PY
  PIDS+=($!)
fi
while [ -z "$END" ]; do
  sleep 1
  line=$(python3 - "$URL" "$OUT/report.json" <<'PY'
import json, sys, time, urllib.request
try:
    s = json.load(urllib.request.urlopen(sys.argv[1] + '/api/state', timeout=2)); mode, reason = s['mode']['name'], s['mode']['fields'].get('stop_reason')
except Exception:
    mode, reason = 'NA', ''
try:
    r = json.load(open(sys.argv[2])); sim, prog, done = r.get('elapsed_s'), r.get('progress'), r.get('completed')
except Exception:
    sim, prog, done = '', '', ''
print(f'{time.time():.1f},{sim},{mode},{reason},{prog},{done}')
PY
)
  echo "$line" >> "$OUT/state.csv"
  END=$(python3 - "$OUT/state.csv" "$MAX_SIM_S" "$STALL_END_S" "$OUT/report.json" <<'PY'
import csv, json, sys
rows = list(csv.DictReader(open(sys.argv[1]))); maxs, stall = float(sys.argv[2]), float(sys.argv[3])
r = rows[-1]
if r['mode'] == 'PAUSE': print('pause:' + r['stop_reason']); sys.exit()
try: length = 400.0; rep = json.load(open(sys.argv[4]))
except Exception: sys.exit()
pts = [(float(x['sim_s']), float(x['progress'])) for x in rows if x['sim_s'] not in ('', 'None') and x['progress'] not in ('', 'None')]
if not pts: sys.exit()
t, p = pts[-1]
if t > maxs: print('max_sim_time'); sys.exit()
# progress is the fraction of the route (start..last waypoint); 1 m is about 0.0025 of it
best = max(q for _, q in pts); step = 1.0 / float(__import__('os').environ.get('ROUTE_M') or 400.0); first = next(tt for tt, q in pts if q >= best - step)
if t - first > stall and best > 0.002: print('stall_%ds' % int(t - first))
PY
)
done
sleep 2
LOG="$ROOT/run/stack.launch.log"
grep -E "nav2_goal_resend|waypoint_skipped|goal_reached|localization_wait|Running (spin|backup|wait)|Failed to make progress|collision ahead|automatic_pause|TR-07|TR-08|stop_reason" "$LOG" | cut -c1-400 > "$OUT/events.txt"
count() { grep -c -- "$1" "$LOG"; }
python3 - "$OUT/report.json" "$OUT/result.json" "$SCENARIO" "${END:-none}" "$(tr -d '\n' < "$OUT/start.json")" "$S" "$SIM_ARGS" \
  "$(count 'nav2_goal_resend_scheduled')" "$(count 'waypoint_skipped:')" "$(count 'Running spin')" "$(count 'Running backup')" "$(count 'Running wait')" \
  "$(count 'Failed to make progress')" "$(count 'collision ahead')" "$(count 'Control loop missed')" "$(count 'localization_wait')" "$(cut -d' ' -f1 /proc/loadavg)" <<'PY'
import json, os, sys
rep, res, sc, end, start, speed, simargs, *c = sys.argv[1:]
r = json.load(open(rep)) if os.path.exists(rep) else {'scenario': sc}
k = ('resend_scheduled', 'waypoint_skipped', 'spin', 'backup', 'wait', 'failed_progress', 'collision_ahead', 'control_loop_missed', 'localization_wait')
r.update(end=end, start=start[:200], speed=float(speed), sim_args=simargs, log=dict(zip(k, map(int, c[:-1]))), load1=float(c[-1]))
json.dump(r, open(res, 'w'), ensure_ascii=False, indent=1)
PY
PYTHONPATH="$here:$PYTHONPATH" python3 "$here/drive_sim_course.py" analyze "$OUT" "$SCENARIO" > /dev/null 2>"$OUT/analyze.err"
python3 -c "import json,sys; r=json.load(open(sys.argv[1])); c=json.load(open(sys.argv[2])) if __import__('os').path.exists(sys.argv[2]) else {}; print(json.dumps({'end': r['end'], 'log': r['log'], 'goal': c.get('reached_goal_line'), 'time': c.get('time_to_goal_s'), 'prog': c.get('max_progress_m'), 'stall': c.get('longest_no_1m_progress_s'), 'contacts': {k: v['contacts'] for k, v in c.get('contacts', {}).items()}}))" "$OUT/result.json" "$OUT/course.json"
