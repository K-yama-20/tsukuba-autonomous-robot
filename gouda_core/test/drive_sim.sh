#!/bin/bash
# TEST ONLY (第179便): one simulated drive through the real stack (stack.sh, mode manager, Nav2, pointcloud_to_laserscan, ESP32 simulator)
# with drive_sim_node.py as the vehicle and the world and nd07_stub.py as ND-07. Not a way to run the robot; no device is opened.
#   bash drive_sim.sh <scenario> <out_dir> [values.json]    values.json: {"key": value} of the /config 「Nav2」 tab (nav2_config.TUNABLES)
# Env: SIM_ARGS (extra arguments of drive_sim_node.py, e.g. "--delay 0.3"), ROS_DOMAIN_ID (default 78). Result: <out_dir>/result.json
# MID-360 plan stage 2: SIM_MID360_HEIGHT (m above the ground; empty: no MID-360) and GOUDA_TEST_LAYERS (S0/S1/S2, drive_sim_layers.py;
# needs a simulator copy of nav2_config.py patched with drive_sim_layers.py --patch-copy).
set -o pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; repo="$(cd "$here/../.." && pwd)"; ws="$(cd "$repo/../.." && pwd)"
SCENARIO=$1; OUT=$2; VALUES=$3
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-78}
ROOT=$(mktemp -d /tmp/drive_sim.XXXXXX); mkdir -p "$OUT" "$ROOT/config"
source /opt/ros/jazzy/setup.bash; source "$ws/install/setup.bash"
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
REQ=$(python3 "$here/drive_sim_fixture.py" "$ROOT" "$SCENARIO") || exit 1
[ -n "$VALUES" ] && python3 -c "import json,sys; json.dump({'config_revision': 1, 'values': json.load(open(sys.argv[1]))}, open(sys.argv[2], 'w'))" "$VALUES" "$ROOT/config/nav2_recovery.json"
[ -n "$GOUDA_TEST_LAYERS" ] && export GOUDA_TEST_LAYERS GOUDA_TEST_LAYERS_PY="$here/drive_sim_layers.py"
bash "$here/stack.sh" start "$ROOT" || exit 1
if [ -n "$SIM_MID360_HEIGHT" ]; then   # the MID-360's band, as the XT-32's xt32_scan (same parameters, other topics)
  python3 -c "import yaml,sys; p=yaml.safe_load(open(sys.argv[1]))['xt32_scan']['ros__parameters']; yaml.safe_dump({'mid360_scan': {'ros__parameters': p}}, open(sys.argv[2], 'w'))" "$ROOT/run/nav2/nav2_params.yaml" "$ROOT/mid360_scan.yaml"
  ros2 run pointcloud_to_laserscan pointcloud_to_laserscan_node --ros-args -r __node:=mid360_scan -r cloud_in:=/sensors/mid360/points -r scan:=/sensors/mid360/scan --params-file "$ROOT/mid360_scan.yaml" > "$OUT/mid360_scan.out" 2>&1 &
  PIDS+=($!)
  SIM_ARGS="$SIM_ARGS --mid360-height $SIM_MID360_HEIGHT"
fi
URL=$(cat "$ROOT/run/monitor.url")
setsid ros2 run gouda_core esp32_sim -- --path-file "$OUT/pty" --log "$OUT/esp32.log" > "$OUT/esp32.out" 2>&1 &
ESP=$!   # its own process group: `ros2 run` leaves the simulator running when only the wrapper is killed
for _ in $(seq 1 20); do [ -s "$OUT/pty" ] && break; sleep 0.5; done
for _ in $(seq 1 15); do ros2 param set /vehicle_bridge serial_port "$(cat "$OUT/pty")" 2>/dev/null | grep -q successful && break; sleep 2; done   # discovery on a loaded VM
ND07=$(pgrep -g "$(cat "$ROOT/run/stack.pid")" -f "lib/gouda_core/[g]ouda_global_localization"); [ -n "$ND07" ] && kill -INT "$ND07"; sleep 3
python3 "$here/nd07_stub.py" 0.1 > "$OUT/nd07_stub.out" 2>&1 &
PIDS+=($!)
# shellcheck disable=SC2086
PYTHONPATH="$here:$PYTHONPATH" python3 "$here/drive_sim_node.py" "$SCENARIO" "$OUT/report.json" $SIM_ARGS > "$OUT/node.out" 2>&1 &
PIDS+=($!)
for _ in $(seq 1 30); do ros2 node list --no-daemon 2>/dev/null | grep -qx /gouda_global_localization && break; sleep 1; done
for _ in $(seq 1 20); do   # the mode manager may not have discovered the stand-in yet (refused: ND-07 is not running)
  curl -s -X POST -H 'Content-Type: application/json' -d "$REQ" "$URL/api/command/start_autonomy" > "$OUT/start.json"
  grep -q 'is not running' "$OUT/start.json" || break; sleep 3
done
TIMEOUT=$(PYTHONPATH="$here" python3 -c "import drive_sim_core as d,sys; print(int(d.scenario(sys.argv[1]).timeout_s))" "$SCENARIO")
state() { curl -s "$URL/api/state" | python3 -c "import json,sys; s=json.load(sys.stdin); print(s['mode']['name'], s['mode']['fields'].get('stop_reason'))" 2>/dev/null; }
END=""
python3 -c "import json,sys; sys.exit(0 if json.load(open(sys.argv[1])).get('ok') else 1)" "$OUT/start.json" 2>/dev/null || END="start_refused"
for _ in $(seq 1 "$TIMEOUT"); do
  [ -n "$END" ] && break
  sleep 1; read -r mode reason <<< "$(state)"
  if [ "$mode" = "PAUSE" ]; then END="pause:$reason"; break; fi
done
sleep 1.5   # the report's last rewrite
LOG="$ROOT/run/stack.launch.log"; count() { grep -c -- "$1" "$LOG"; }
python3 - "$OUT/report.json" "$OUT/result.json" "$SCENARIO" "${END:-timeout}" "$(cat "$OUT/start.json" | tr -d '\n')" \
  "$(count 'collision ahead')" "$(count 'Failed to make progress')" "$(count 'patience exceeded')" "$(count 'Running spin')" "$(count 'Running backup')" "$(count 'Running wait')" \
  "$(count 'Control loop missed')" "$(count 'Planner loop missed')" "$(count 'Failed to .* frame\|too old')" "$(cut -d' ' -f1 /proc/loadavg)" <<'PY'
import json, os, sys
rep, res, sc, end, start, *c = sys.argv[1:]
r = json.load(open(rep)) if os.path.exists(rep) else {'scenario': sc, 'score': None}
k = ('collision_ahead', 'failed_progress', 'patience_exceeded', 'spin', 'backup', 'wait', 'control_loop_missed', 'planner_loop_missed', 'tf_errors')
r.update(end=end, start=start[:200], log=dict(zip(k, map(int, c))), load1=float(c[-1]))
json.dump(r, open(res, 'w'), ensure_ascii=False, indent=1)
print(json.dumps({x: r.get(x) for x in ('scenario', 'end', 'completed', 'progress', 'duration_s', 'avg_speed_mps', 'stopped_s', 'contacts', 'score', 'load1')}, ensure_ascii=False))
PY
