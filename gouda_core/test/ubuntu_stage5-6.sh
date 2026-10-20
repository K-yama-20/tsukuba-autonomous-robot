#!/bin/bash
# Stage 5-6 VM test (REV-061): Nav2 (trial values) driven by the mode manager, with the Nav2 loopback simulator standing in for
# ND-07 / ND-08 (it integrates cmd_vel and publishes map->odom->base_link) and the ESP32 simulator behind vehicle_bridge.
# No vehicle, no sensors. Test only: the loopback simulator and its Python dependencies are read from an extracted copy of the
# ROS apt packages (UPSTREAM_EXTRACT; not installed on the VM: no sudo).
#   T1 before the start: no goal, hold true (TS-21); a start without an initial pose is refused (TR-05 guard)
#   T2 start through the monitor API (selection + initial pose) -> 自律走行, hold true until 適用中, the robot reaches the last
#      waypoint -> 一時停止 (TR-08, TS-05, TS-01)
#   T3 end from pause (TR-12): Nav2 reset, vehicle output inactive
#   T4 start, pause (TR-06), resume (TR-10), end while driving (TR-11)
set -o pipefail
WS=~/gouda_fix_ws; REPO=$WS/src/tsukuba-autonomous-robot; ROOT=/tmp/st56; OUT=${OUT:-/tmp/st56_out}
X=${UPSTREAM_EXTRACT:-$HOME/upstream_pkgs/x}
export ROS_DOMAIN_ID=77
source /opt/ros/jazzy/setup.bash; source $WS/install/setup.bash
rm -rf $ROOT $OUT; mkdir -p $ROOT $OUT
REQ=$(python3 $REPO/gouda_core/test/stage56_fixture.py $ROOT) || exit 1
echo "fixture: $REQ"
bash $REPO/gouda_core/test/stack.sh start $ROOT || exit 1
URL=$(cat $ROOT/run/monitor.url); echo "monitor $URL"
cleanup() { pkill -f "[l]oopback_simulator" ; pkill -f "gouda_core/[e]sp32_sim"; pkill -f "gouda_core.[e]sp32_sim_pty"; bash $REPO/gouda_core/test/stack.sh stop $ROOT; }
trap cleanup EXIT
st() { curl -s "$URL/api/state" | python3 -c "
import json,sys; s=json.load(sys.stdin); f=s['mode']['fields']
print('mode=%s stop=%s remaining=%s section=%s speed_limit=%s' % (s['mode']['name'], f.get('stop_reason'), f.get('remaining_waypoints'), f.get('current_section'), f.get('speed_limit_application_state')))"; }
events() { curl -s "$URL/api/state" | python3 -c "
import json,sys; s=json.load(sys.stdin)
for e in reversed(s['events']):
    if e['node'] in ('gouda_mode_manager',) and e['event'] not in ('boot','settings'): print('  ', e['transition_id'] or '-', e['event'], '|', e['reason'][:150], '| x%d' % e['count'])"; }
hold() { timeout 5 ros2 topic echo --once /control/motion_hold gouda_interfaces/msg/MotionHold 2>/dev/null | grep -E "^hold:|^reason:" | tr '\n' ' '; echo; }
cmd() { curl -s -X POST -H 'Content-Type: application/json' -d "${2:-{\}}" "$URL/api/command/$1" | python3 -c "import json,sys; j=json.load(sys.stdin); print('  %s ok=%s %s' % ('$1', j.get('ok'), j.get('message','')[:200]))"; }
wait_mode() { for i in $(seq 1 ${2:-120}); do m=$(curl -s "$URL/api/state" | python3 -c "import json,sys; print(json.load(sys.stdin)['mode']['name'])"); [ "$m" = "$1" ] && return 0; sleep 1; done; return 1; }
body() { python3 -c "import json,sys; r=json.loads(sys.argv[1]); r.update(request_id='t-'+sys.argv[2]); r.update(initial_pose={'x':1.5,'y':0.0,'yaw':0.0}) if sys.argv[3]=='pose' else None; print(json.dumps(r))" "$REQ" "$1" "$2"; }

echo "=== Nav2 lifecycle after the stack start (expected: servers present, inactive; autostart false)"
sleep 3; for n in controller_server bt_navigator map_server velocity_smoother; do echo "  $n: $(timeout 10 ros2 lifecycle get /$n 2>&1 | head -1)"; done
echo "=== ESP32 simulator behind vehicle_bridge (PRM-61 is unresolved in the model; the test gives the pty)"
ros2 run gouda_core esp32_sim -- --path-file $OUT/pty --log $OUT/sim.log > $OUT/sim.out 2>&1 &
for i in $(seq 1 20); do [ -s $OUT/pty ] && break; sleep 0.5; done
ros2 param set /vehicle_bridge serial_port "$(cat $OUT/pty)"
echo "=== T1 before the start (TS-21) and the TR-05 guards"
st; hold
cmd start_autonomy "$(body 1 nopose)"
echo "  (without ND-07: the loopback simulator is not running yet)"
cmd start_autonomy "$(body 2 pose)"
echo "=== loopback simulator as the ND-07 / ND-08 stub (node name gouda_global_localization)"
( export AMENT_PREFIX_PATH=$X/opt/ros/jazzy:$AMENT_PREFIX_PATH PYTHONPATH=$X/opt/ros/jazzy/lib/python3.12/site-packages:$X/usr/lib/python3/dist-packages:$PYTHONPATH
  exec ros2 run nav2_loopback_sim loopback_simulator --ros-args -r __node:=gouda_global_localization -r initialpose:=localization/initial_pose \
    -p base_frame_id:=base_link -p publish_clock:=false -p enable_stamped_cmd_vel:=true -p scan_frame_id:=xt32_link ) > $OUT/loopback.out 2>&1 &
sleep 4
echo "=== T2 start with selection and initial pose -> drive to the last waypoint (TR-05 -> TR-08)"
cmd start_autonomy "$(body 3 pose)"
sleep 1; st; hold
for i in 1 2 3 4 5 6; do sleep 5; st; done
wait_mode PAUSE 120 && echo "  reached PAUSE" || echo "  did NOT reach PAUSE within the wait"
st; hold
if curl -s "$URL/api/state" | grep -q '"stop_reason": "plan_failure"'; then
  echo "  TR-07 (Nav2 failed): resume (TR-10) from the first waypoint not yet passed"
  cmd resume; for i in 1 2 3 4 5 6; do sleep 5; st; done
  wait_mode PAUSE 120 && echo "  reached PAUSE" || echo "  did NOT reach PAUSE within the wait"; st; hold
fi
events | head -40
echo "  final pose (map->base_link):"; timeout 10 ros2 run tf2_ros tf2_echo map base_link 2>/dev/null | grep -m1 -A1 "Translation" 
echo "=== T3 end from pause (TR-12)"
cmd end_autonomy; sleep 6; st; hold
for n in controller_server bt_navigator; do echo "  $n: $(timeout 10 ros2 lifecycle get /$n 2>&1 | head -1)"; done
for n in gouda_motion_controller vehicle_bridge; do echo "  $n: $(timeout 10 ros2 lifecycle get /$n 2>&1 | head -1)"; done
echo "=== T4 start, pause (TR-06), resume (TR-10), end while driving (TR-11)"
cmd start_autonomy "$(body 4 pose)"; sleep 12; st
cmd pause; sleep 3; st; hold
cmd resume; sleep 8; st; hold
cmd end_autonomy; sleep 6; st; hold
events | head -40
echo "=== warnings / errors in the launch log"
grep -E "gouda_mode_manager.*(WARN|ERROR)" $ROOT/run/stack.launch.log | cut -c1-220 | tail -20
grep -cE "\[(controller_server|bt_navigator|planner_server|velocity_smoother|behavior_server)-[0-9]+\].*ERROR" $ROOT/run/stack.launch.log
