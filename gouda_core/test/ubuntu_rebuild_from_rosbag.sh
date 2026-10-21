#!/bin/bash
# TEST / ANALYSIS ONLY (DEC-212, REV-134): rebuild a source map and its conversion from a recorded rosbag with the product steps
# (事前地図作成 TR-03 -> GLIM -> 地図作成終了 TR-04 -> source registration with the /config snapshot -> conversion), on the VM.
# Not the way to make maps on the vehicle (that is gouda.sh start + the monitor). The rosbag and the /config are only read.
#
# Same isolation as test/stack.sh (own ROS_DOMAIN_ID, own data_root, no sensor drivers, OS-chosen monitor port, trial values,
# fastdds_test_stack.xml) with one difference: the trial value of glim_stop_wait_s (PRM-37) is left out, so that GLIM's save is
# waited for without a limit as on the vehicle (PRM-37 is unresolved there); a cut-off save would leave no source map.
# The other trial values stay (e.g. PRM-97 while DEC-225 is open): the conversion's manifest records the settings used.
#
# usage: bash ubuntu_rebuild_from_rosbag.sh <rosbag dir> <sensor_config.json of the run> <new data_root> [play rate, default 0.5]
set -o pipefail   # no -u: ROS setup.bash reads unset variables
BAG=${1:?rosbag dir}; CFG=${2:?sensor_config.json}; ROOT=${3:?data_root}; RATE=${4:-0.5}
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; repo="$(cd "$here/../.." && pwd)"; ws="$(cd "$repo/../.." && pwd)"
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-79}
export FASTRTPS_DEFAULT_PROFILES_FILE="$here/fastdds_test_stack.xml"
[ -e "$ROOT" ] && { echo "$ROOT exists; give a new data_root"; exit 2; }
mkdir -p "$ROOT/run" "$ROOT/params" "$ROOT/config"
cp "$CFG" "$ROOT/config/sensor_config.json"
cp "$repo/design/generated/params/"* "$ROOT/params/"; rm -f "$ROOT/params"/hesai_ros_driver* "$ROOT/params"/adi_imu_driver* "$ROOT/params"/septentrio_gnss_driver*
sed -i -E 's/^(\s*monitor_port:).*/\1 0  # test copy: OS-chosen port/' "$ROOT/params/gouda_monitor.yaml"
sed -i -E '/^\s*glim_stop_wait_s:/d' "$ROOT/params/gouda_mode_manager.trial.yaml"
source /opt/ros/jazzy/setup.bash; source "$ws/install/setup.bash"
set -m
ros2 launch gouda_core gouda_core.launch.py "params_dir:=$ROOT/params" "data_root:=$ROOT" trial:=true >"$ROOT/run/stack.launch.log" 2>&1 &
G=$!; set +m
stop() { kill -INT -- "-$G" 2>/dev/null; for _ in $(seq 1 60); do pgrep -g "$G" >/dev/null 2>&1 || break; sleep 1; done; pgrep -g "$G" >/dev/null 2>&1 && kill -TERM -- "-$G"; }
trap stop EXIT
for _ in $(seq 1 30); do [ -s "$ROOT/run/monitor.url" ] && break; sleep 1; done
URL=$(cat "$ROOT/run/monitor.url"); echo "stack up (ROS_DOMAIN_ID=$ROS_DOMAIN_ID, $URL)"
cmd() { curl -s -X POST -H 'Content-Type: application/json' -d '{}' "$URL/api/command/$1" | python3 -c "import json,sys; j=json.load(sys.stdin); print('  $1 ok=%s %s' % (j.get('ok'), j.get('message','')[:200]))"; }
events() { curl -s "$URL/api/state" | python3 -c "
import json,sys; s=json.load(sys.stdin)
for e in reversed(s['events']):
    if e['node'] in ('gouda_mode_manager', 'gouda_map_creator') and e['event'] not in ('boot', 'settings'): print('  ', e['transition_id'] or '-', e['event'], '|', e['reason'][:200])"; }
sleep 5
echo "=== start mapping (TR-03) and play $BAG at rate $RATE (points and IMU only)"
cmd start_mapping; sleep 5
T0=$(date +%s)
ros2 bag play "$BAG" --rate "$RATE" --topics /sensors/xt32/points /sensors/imu/data > "$ROOT/run/play.log" 2>&1
echo "  played in $(( $(date +%s) - T0 )) s"; sleep 5
echo "=== end mapping (TR-04): GLIM save, source registration, conversion"
cmd end_mapping
for _ in $(seq 1 360); do
  st=$(curl -s "$URL/api/state" | python3 -c "import json,sys; print(json.load(sys.stdin)['mode']['fields'].get('processing_state'))")
  [ "$st" = "idle" ] && break; sleep 10
done
echo "  processing_state: $st"
events | head -25
echo "=== maps"
python3 - "$ROOT" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1]) / 'maps'
for o in sorted(p for p in root.iterdir() if p.is_dir()):
    sm = json.loads((o / 'source_manifest.json').read_text())
    print(o.name, 'submaps', sm['submaps'], 'sensor_config' in sm and 'with /config snapshot' or 'NO /config snapshot')
    for c in sorted((o / 'converted').glob('*')) if (o / 'converted').is_dir() else []:
        m = json.loads((c / 'manifest.json').read_text()); st = m['stats']
        print('  rev', m['revision'], m['converter']['version'][:40], '| corridor', st.get('swept_corridor'), '| settings A/B', m['settings'].get('corridor_half_width_m'), m['settings'].get('corridor_gap_m'))
PY
