#!/bin/bash
# ND-07 (gouda_global_localization, trial A3; REV-128, TS-41 part) VM check without sensors: the real A3 parts are started and
# stopped by the node's lifecycle, the TF ownership, and the state without sensor points. Test only; the generated values (approved by DEC-208, REV-132), plus the trial file when one exists.
#   S1 a real source map is converted with the trial settings (the source is only read)
#   S2 configure: the child launch starts the pcl_ros filters, the map loader, the NDT and the EKF in localization/a3
#   S3 activate with an initial pose: without sensor points the initialization cannot succeed -> never 正常
#   S4 /tf: the only map->odom publisher is gouda_global_localization (no publisher from the A3 parts)
#   S5 deactivate + cleanup: the A3 parts are gone
# usage: bash ubuntu_nd07_smoke.sh <source_dir of a GLIM dump (read only)>
set -o pipefail
SRC=${1:?source dir}
WS=${WS:-~/gouda_rev128_ws}; REPO=$WS/src/tsukuba-autonomous-robot; ROOT=/tmp/nd07; P=$REPO/design/generated/params
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-78}
source /opt/ros/jazzy/setup.bash; source $WS/install/setup.bash
rm -rf $ROOT; mkdir -p $ROOT
echo "=== S1 conversion with the trial settings"
python3 - "$SRC" "$ROOT/map" "$P" <<'PY' || exit 1
import sys, yaml
sys.path.insert(0, sys.argv[3] + '/../../../gouda_core')
from pathlib import Path
from gouda_core import map_convert as mc
s = {}
for f in ('gouda_map_creator.yaml', 'gouda_map_creator.trial.yaml'):
    s.update(((yaml.safe_load(open(Path(sys.argv[3]) / f)) or {}).get('gouda_map_creator') or {}).get('ros__parameters') or {})
st = mc.convert(Path(sys.argv[1]), Path(sys.argv[2]), s)
print('  pointcloud_map:', st['pointcloud_map'], 'files', len(st['files']))
PY
$WS/install/gouda_core/lib/gouda_core/gouda_global_localization --ros-args --params-file $P/gouda_global_localization.yaml $( [ -f $P/gouda_global_localization.trial.yaml ] && echo --params-file $P/gouda_global_localization.trial.yaml ) -p data_root:=$ROOT -p map_directory:=$ROOT/map > $ROOT/node.out 2>&1 &
NODE=$!
cleanup() { kill -INT $NODE 2>/dev/null; [ -n "$POSE" ] && kill $POSE 2>/dev/null; wait $NODE 2>/dev/null; }
trap cleanup EXIT
sleep 4
status() { timeout 8 ros2 topic echo --once --qos-durability transient_local --qos-reliability reliable /localization/status gouda_interfaces/msg/EstimatorStatus 2>/dev/null | grep -E "^(state|reason|detail):" | tr '\n' ' '; echo; }
echo "  before configure: $(status)"
echo "=== S2 configure"
ros2 lifecycle set /gouda_global_localization configure; sleep 15
ros2 node list | grep -E "localization/a3|global_localization" | grep -v transform_listener_impl | sed 's/^/  /'
ros2 service list | grep -E "a3/(ndt_align_srv|ekf_trigger_node|ndt_trigger_node|service/get_differential_pcd_map)$" | sed 's/^/  /'
echo "  after configure: $(status)"
echo "=== S3 activate with an initial pose (no sensor points)"
timeout 60 ros2 topic pub -r 1 --qos-durability transient_local --qos-reliability reliable /localization/initial_pose geometry_msgs/msg/PoseWithCovarianceStamped \
  "{header: {frame_id: map}, pose: {pose: {position: {x: 0.0, y: 0.0}, orientation: {w: 1.0}}}}" > /dev/null 2>&1 &
POSE=$!
ros2 lifecycle set /gouda_global_localization activate
for i in 1 2 3 4; do sleep 5; echo "  t=$((i*5)) s: $(status)"; done
echo "=== S4 /tf publishers"
ros2 topic info /tf --verbose | python3 -c "
import sys
node = None
for line in sys.stdin:
    if line.startswith('Node name:'): node = line.split(':', 1)[1].strip()
    elif line.startswith('Node namespace:'): ns = line.split(':', 1)[1].strip()
    elif line.startswith('Endpoint type:') and 'PUBLISHER' in line: print('  publisher:', ns.rstrip('/') + '/' + node)
"
echo "  tf_ekf / tf_ndt (inside localization/a3, read by nobody):"; ros2 topic list | grep -E "a3/tf_(ekf|ndt)" | sed 's/^/    /'
echo "=== S5 deactivate + cleanup"
ros2 lifecycle set /gouda_global_localization deactivate; ros2 lifecycle set /gouda_global_localization cleanup; sleep 5
echo "  A3 nodes left: $(ros2 node list | grep -c 'localization/a3')"
echo "  after cleanup: $(status)"
echo "=== decision events of the node (log)"
grep -E "configure refused|ERROR" $ROOT/node.out | head -5
echo "=== the A3 launch log: map loader lines, errors, process ends"
grep -E "pointcloud_map_loader|ERROR|error|died|finished" $ROOT/run/localization/*.log | cut -c1-220 | head -20
