#!/bin/bash
# ND-07 (trial A3; REV-144, DEC-280, TS-41 VM part): ndt_align_srv is called only after the NDT keeps a point cloud. The point
# clouds start AFTER activate (the order of the failure seen on the vehicle on 2026-10-22: No InputSource, 推定不能). Test only;
# the generated values, plus the trial file when one exists. Fast DDS uses the profile of gouda.sh when one was written (PRM-100).
#   W1 activate without point clouds: 初期化中 for the whole wait (never 推定不能), detail "no scan status from the NDT yet"
#   W2 point clouds the NDT drops (all points within <near_m> m in 3-D: max distance below its required_distance): still 初期化中, the
#      detail gives the NDT's reason
#   W3 point clouds the NDT keeps (horizontal radius <far_m> m; keep the cloud near the XT-32's size, about 64000 points, or the
#      VM cannot process 10 Hz): the initialization runs and the state becomes 正常
#   W4 the decision events of the wait: ndt_points_waiting, ndt_points_dropped, ndt_points_kept, initial_pose_aligned, initialized
# usage: bash ubuntu_nd07_wait_points.sh <converted map directory with pointcloud_map/> [row] [near_m] [far_m]
set -o pipefail
MAP=${1:?map dir}; ROW=${2:-200}; NEAR=${3:-6}; FAR=${4:-10}
WS=${WS:-~/gouda_ws}; REPO=$WS/src/tsukuba-autonomous-robot; ROOT=/tmp/nd07_wait; P=$REPO/design/generated/params
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-79}
PROFILE=${PROFILE:-$WS/gouda_data/run/fastdds_profile.xml}
[ -f "$PROFILE" ] && export FASTRTPS_DEFAULT_PROFILES_FILE=$PROFILE && echo "Fast DDS profile: $PROFILE"
source /opt/ros/jazzy/setup.bash; source $WS/install/setup.bash
rm -rf $ROOT; mkdir -p $ROOT
$WS/install/gouda_core/lib/gouda_core/gouda_global_localization --ros-args --params-file $P/gouda_global_localization.yaml $( [ -f $P/gouda_global_localization.trial.yaml ] && echo --params-file $P/gouda_global_localization.trial.yaml ) -p data_root:=$ROOT -p map_directory:=$MAP > $ROOT/node.out 2>&1 &
NODE=$!
timeout 200 ros2 topic echo --qos-durability transient_local --qos-reliability reliable /log/decision gouda_interfaces/msg/DecisionEvent > $ROOT/decisions.out 2>&1 &
ECHO=$!
cleanup() { kill -INT $FEED $NODE 2>/dev/null; kill $POSE $ECHO 2>/dev/null; wait $NODE 2>/dev/null; }
trap cleanup EXIT
sleep 4
# the true pose of the trajectory row, from the feed's first line (the feed is started only for that and stopped at once)
python3 $REPO/gouda_core/test/a3_synthetic_feed.py $MAP $ROW 1 10 > $ROOT/pose.out 2>&1 & PFEED=$!
for _ in $(seq 1 20); do [ -s $ROOT/pose.out ] && break; sleep 1; done; kill -INT $PFEED 2>/dev/null; wait $PFEED 2>/dev/null
TRUE=$(head -1 $ROOT/pose.out); echo "true pose (x y z qx qy qz qw): $TRUE"
INIT=$(python3 -c "
import sys
x,y,z,qx,qy,qz,qw=[float(v) for v in sys.argv[1].split()]
print('{header: {frame_id: map}, pose: {pose: {position: {x: %f, y: %f}, orientation: {x: %f, y: %f, z: %f, w: %f}}}}' % (x, y, qx, qy, qz, qw))" "$TRUE")
status() { timeout 8 ros2 topic echo --once --qos-durability transient_local --qos-reliability reliable /localization/status gouda_interfaces/msg/EstimatorStatus 2>/dev/null | grep -E "^(state|reason|detail):" | tr '\n' ' '; echo; }
ros2 lifecycle set /gouda_global_localization configure; sleep 15
timeout 180 ros2 topic pub -r 1 --qos-durability transient_local --qos-reliability reliable /localization/initial_pose geometry_msgs/msg/PoseWithCovarianceStamped "$INIT" > /dev/null 2>&1 &
POSE=$!
echo "=== W1 activate without point clouds"
ros2 lifecycle set /gouda_global_localization activate
for i in 1 2 3; do sleep 5; echo "  t=$((i*5)) s: $(status)"; done
echo "=== W2 point clouds within $NEAR m in 3-D (the NDT drops them)"
python3 $REPO/gouda_core/test/a3_synthetic_feed.py $MAP $ROW $NEAR 0.1 3d > $ROOT/feed_near.out 2>&1 &
FEED=$!
for i in 1 2 3; do sleep 5; echo "  t=$((i*5)) s: $(status)"; done
kill -INT $FEED; wait $FEED 2>/dev/null
echo "=== W3 point clouds within $FAR m (the NDT keeps them)"
python3 $REPO/gouda_core/test/a3_synthetic_feed.py $MAP $ROW $FAR 0.1 > $ROOT/feed.out 2>&1 &
FEED=$!
for i in 1 2 3 4 5 6; do sleep 5; echo "  t=$((i*5)) s: $(status)"; done
ros2 lifecycle set /gouda_global_localization deactivate; ros2 lifecycle set /gouda_global_localization cleanup; sleep 3
echo "=== W4 decision events (event: reason)"
python3 - $ROOT/decisions.out <<'PY'
import sys, re
ev = None
for line in open(sys.argv[1], encoding='utf-8', errors='replace'):
    m = re.match(r"^event: (.*)$", line.rstrip())
    if m: ev = m.group(1).strip("'\""); continue
    m = re.match(r"^reason: (.*)$", line.rstrip())
    if m and ev: print(f'  {ev}: {m.group(1)[:160]}'); ev = None
PY
grep -h "points within" $ROOT/feed_near.out $ROOT/feed.out | sed "s/^/  /" | cut -c1-160
echo "=== node and A3 log (errors)"
grep -E "ERROR|Traceback" $ROOT/node.out | head -10 | cut -c1-200
grep -E "ERROR|died" $ROOT/run/localization/*.log | head -10 | cut -c1-220
