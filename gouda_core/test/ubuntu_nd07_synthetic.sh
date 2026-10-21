#!/bin/bash
# ND-07 (trial A3; REV-128, TS-41 VM part) with synthetic sensor input (a3_synthetic_feed.py): the robot stands still at one pose
# of the mapping trajectory and sees the map's points from there. Test only; the generated values (approved by DEC-208, REV-132), plus the trial file when one exists.
#   Y1 the initial pose is given with an offset (dx m, dyaw deg): the Monte Carlo search, the EKF and the NDT come up
#   Y2 the state becomes 正常 (the diagnostics keys are found), map->odom equals the true pose (odometry is the identity)
#   Y3 the feed stops -> 推定不能 (input_stale) within stale_timeout_s (PRM-89, trial)
# usage: bash ubuntu_nd07_synthetic.sh <converted map directory with pointcloud_map/> [row] [dx_m] [dyaw_deg]
set -o pipefail
MAP=${1:?map dir}; ROW=${2:-200}; DX=${3:-1.0}; DYAW=${4:-10}
WS=${WS:-~/gouda_rev128_ws}; REPO=$WS/src/tsukuba-autonomous-robot; ROOT=/tmp/nd07_syn; P=$REPO/design/generated/params
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-79}
source /opt/ros/jazzy/setup.bash; source $WS/install/setup.bash
rm -rf $ROOT; mkdir -p $ROOT
$WS/install/gouda_core/lib/gouda_core/gouda_global_localization --ros-args --params-file $P/gouda_global_localization.yaml $( [ -f $P/gouda_global_localization.trial.yaml ] && echo --params-file $P/gouda_global_localization.trial.yaml ) -p data_root:=$ROOT -p map_directory:=$MAP > $ROOT/node.out 2>&1 &
NODE=$!
python3 $REPO/gouda_core/test/a3_synthetic_feed.py $MAP $ROW 60 0.1 > $ROOT/feed.out 2>&1 &
FEED=$!
cleanup() { kill -INT $FEED $NODE 2>/dev/null; [ -n "$POSE" ] && kill $POSE 2>/dev/null; wait $NODE 2>/dev/null; }
trap cleanup EXIT
sleep 5
TRUE=$(head -1 $ROOT/feed.out); echo "true pose (x y z qx qy qz qw): $TRUE"
INIT=$(python3 -c "
import math,sys
x,y,z,qx,qy,qz,qw=[float(v) for v in sys.argv[1].split()]; dx=float(sys.argv[2]); a=math.radians(float(sys.argv[3]))/2
r=(0,0,math.sin(a),math.cos(a)); q=(r[3]*qx+r[0]*qw+r[1]*qz-r[2]*qy, r[3]*qy-r[0]*qz+r[1]*qw+r[2]*qx, r[3]*qz+r[0]*qy-r[1]*qx+r[2]*qw, r[3]*qw-r[0]*qx-r[1]*qy-r[2]*qz)
print('{header: {frame_id: map}, pose: {pose: {position: {x: %f, y: %f}, orientation: {x: %f, y: %f, z: %f, w: %f}}}}' % (x+dx, y, *q))" "$TRUE" $DX $DYAW)
echo "initial pose given: $INIT"
status() { timeout 8 ros2 topic echo --once --qos-durability transient_local --qos-reliability reliable /localization/status gouda_interfaces/msg/EstimatorStatus 2>/dev/null | grep -E "^(state|reason|ndt_nvtl|ekf_pose_no_update_count|ekf_xy_stddev_m|last_input_age_s):" | tr '\n' ' '; echo; }
ros2 lifecycle set /gouda_global_localization configure; sleep 15
timeout 120 ros2 topic pub -r 1 --qos-durability transient_local --qos-reliability reliable /localization/initial_pose geometry_msgs/msg/PoseWithCovarianceStamped "$INIT" > /dev/null 2>&1 &
POSE=$!
echo "=== Y1 / Y2 activate"
ros2 lifecycle set /gouda_global_localization activate
for i in 1 2 3 4 5 6; do sleep 5; echo "  t=$((i*5)) s: $(status)"; done
echo "  map->odom:"; timeout 10 ros2 run tf2_ros tf2_echo map odom 2>/dev/null | grep -m2 -E "Translation|Quaternion" | sed 's/^/    /'
echo "=== Y3 feed stopped"
kill -INT $FEED; sleep 3; echo "  after 3 s: $(status)"
ros2 lifecycle set /gouda_global_localization deactivate; ros2 lifecycle set /gouda_global_localization cleanup; sleep 3
echo "=== node and A3 log (errors, initialization)"
grep -E "ERROR|init|align" $ROOT/node.out | head -10 | cut -c1-200
grep -E "ERROR|died" $ROOT/run/localization/*.log | head -10 | cut -c1-220
