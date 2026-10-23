#!/bin/bash
# DEC-360 (1), bin 148: ND-07 (trial A3) with synthetic point clouds (a3_synthetic_feed.py), the initial pose given with an offset
# (dx m along the map x axis, dyaw deg). Test only; the generated values (the trial file when one exists), the code installed in $WS.
# Based on wait_points_long2.sh (bin 122) without W1/W2: the point clouds the NDT keeps start right after activate, the window is
# <window_s> s. Reports the state every 5 s, the decision events (initial_pose_aligned gives the aligned x, y), and the final
# localization/pose (x, y, yaw) to compare with the true pose.
# usage: bash offset_case.sh <converted map dir> <row> <dx_m> <dyaw_deg> [window_s] [far_m] [odom_lag_s]
set -o pipefail
MAP=${1:?map dir}; ROW=${2:?row}; DX=${3:?dx}; DYAW=${4:?dyaw}; WIN=${5:-150}; FAR=${6:-10}; LAG=${7:-0.15}
WS=${WS:-~/gouda_ws}; REPO=$WS/src/tsukuba-autonomous-robot; ROOT=/tmp/nd07_offset; P=$REPO/design/generated/params
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-89}
PROFILE=${PROFILE:-$WS/gouda_data/run/fastdds_profile.xml}
[ -f "$PROFILE" ] && export FASTRTPS_DEFAULT_PROFILES_FILE=$PROFILE && echo "Fast DDS profile: $PROFILE"
source /opt/ros/jazzy/setup.bash; source $WS/install/setup.bash
rm -rf $ROOT; mkdir -p $ROOT
echo "case: dx $DX m, dyaw $DYAW deg, row $ROW, map $MAP, window $WIN s, ROS_DOMAIN_ID $ROS_DOMAIN_ID"
$WS/install/gouda_core/lib/gouda_core/gouda_global_localization --ros-args --params-file $P/gouda_global_localization.yaml $( [ -f $P/gouda_global_localization.trial.yaml ] && echo --params-file $P/gouda_global_localization.trial.yaml ) -p data_root:=$ROOT -p map_directory:=$MAP > $ROOT/node.out 2>&1 &
NODE=$!
timeout $((WIN + 60)) ros2 topic echo --qos-durability transient_local --qos-reliability reliable /log/decision gouda_interfaces/msg/DecisionEvent > $ROOT/decisions.out 2>&1 &
ECHO=$!
cleanup() { kill -INT $FEED $NODE 2>/dev/null; kill $POSE $ECHO 2>/dev/null; wait $NODE 2>/dev/null; }
trap cleanup EXIT
sleep 4
python3 $REPO/gouda_core/test/a3_synthetic_feed.py $MAP $ROW 1 10 > $ROOT/pose.out 2>&1 & PFEED=$!
for _ in $(seq 1 20); do [ -s $ROOT/pose.out ] && break; sleep 1; done; kill -INT $PFEED 2>/dev/null; wait $PFEED 2>/dev/null
TRUE=$(head -1 $ROOT/pose.out); echo "true pose (x y z qx qy qz qw): $TRUE"
INIT=$(python3 -c "
import math, sys
x,y,z,qx,qy,qz,qw=[float(v) for v in sys.argv[1].split()]; dx=float(sys.argv[2]); a=math.radians(float(sys.argv[3]))/2
r=(0.0,0.0,math.sin(a),math.cos(a))
q=(r[3]*qx+r[0]*qw+r[1]*qz-r[2]*qy, r[3]*qy-r[0]*qz+r[1]*qw+r[2]*qx, r[3]*qz+r[0]*qy-r[1]*qx+r[2]*qw, r[3]*qw-r[0]*qx-r[1]*qy-r[2]*qz)
print('{header: {frame_id: map}, pose: {pose: {position: {x: %f, y: %f}, orientation: {x: %f, y: %f, z: %f, w: %f}}}}' % (x+dx, y, *q))" "$TRUE" $DX $DYAW)
echo "initial pose given: $INIT"
status() { timeout 8 ros2 topic echo --once --qos-durability transient_local --qos-reliability reliable /localization/status gouda_interfaces/msg/EstimatorStatus 2>/dev/null | grep -E "^(state|reason|ndt_nvtl|ekf_xy_stddev_m):" | tr '\n' ' '; echo; }
ros2 lifecycle set /gouda_global_localization configure; sleep 15
timeout $((WIN + 30)) ros2 topic pub -r 1 --qos-durability transient_local --qos-reliability reliable /localization/initial_pose geometry_msgs/msg/PoseWithCovarianceStamped "$INIT" > /dev/null 2>&1 &
POSE=$!
ros2 lifecycle set /gouda_global_localization activate
python3 $REPO/gouda_core/test/a3_synthetic_feed.py $MAP $ROW $FAR 0.1 odom_lag=$LAG > $ROOT/feed.out 2>&1 &
FEED=$!
echo "=== point clouds within $FAR m from activate, odometry stamped $LAG s late"
for i in $(seq 1 $((WIN / 5))); do sleep 5; echo "  t=$((i*5)) s: $(status)"; done
echo "=== final localization/pose (IFD-33)"
timeout 10 ros2 topic echo --once /localization/pose geometry_msgs/msg/PoseWithCovarianceStamped 2>/dev/null > $ROOT/final_pose.out
python3 - $ROOT/final_pose.out "$TRUE" <<'PY'
import math, re, sys
t = open(sys.argv[1]).read()
v = [float(m) for m in re.findall(r'^\s+(?:x|y|z|w): (-?[0-9.e+-]+)$', t, re.M)]
tx, ty, tz, tqx, tqy, tqz, tqw = [float(s) for s in sys.argv[2].split()]
yaw = lambda qx, qy, qz, qw: math.degrees(math.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz)))
if len(v) >= 7:
    x, y, z, qx, qy, qz, qw = v[:7]
    dyaw = (yaw(qx, qy, qz, qw) - yaw(tqx, tqy, tqz, tqw) + 180) % 360 - 180
    print(f'  estimate ({x:.2f}, {y:.2f}) yaw {yaw(qx, qy, qz, qw):.1f} deg; true ({tx:.2f}, {ty:.2f}) yaw {yaw(tqx, tqy, tqz, tqw):.1f} deg; '
          f'error {math.hypot(x - tx, y - ty):.2f} m, {dyaw:.1f} deg')
else:
    print('  no localization/pose received')
PY
ros2 lifecycle set /gouda_global_localization deactivate; ros2 lifecycle set /gouda_global_localization cleanup; sleep 3
echo "=== decision events (event: reason)"
python3 - $ROOT/decisions.out <<'PY'
import sys, re
ev = None
for line in open(sys.argv[1], encoding='utf-8', errors='replace'):
    m = re.match(r"^event: (.*)$", line.rstrip())
    if m: ev = m.group(1).strip("'\""); continue
    m = re.match(r"^reason: (.*)$", line.rstrip())
    if m and ev: print(f'  {ev}: {m.group(1)[:160]}'); ev = None
PY
echo "=== node and A3 log (errors)"
grep -E "ERROR|Traceback" $ROOT/node.out | head -10 | cut -c1-200
grep -E "ERROR|died" $ROOT/run/localization/*.log | head -10 | cut -c1-220
