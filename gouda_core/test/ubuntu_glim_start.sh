#!/usr/bin/env bash
# GLIM start/end through the ONE start path (bash gouda.sh start) on the vehicle PC, with whatever sensors are connected.
# Nothing drives the vehicle (vehicle_bridge stays unconfigured). Checks: sensor reception (monitor), start mapping (warning if
# a sensor has no data), the T_lidar_imu record, end mapping (answered at once, saving afterwards), a refused request must not
# kill the mode manager, a second start/end cycle. NOTE: stopping/starting gouda.sh restarts the IMU driver; if the IMU then
# does not answer, re-plug its USB (docs/sensor_supervision.md).
# Output: $OUT (default /tmp/glim_start). Copy the record into design/research/vehicle_pc/.
set -o pipefail   # no -u: ROS setup.bash reads unset variables
source /opt/ros/jazzy/setup.bash
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; WS="$(cd "$REPO/../.." && pwd)"; OUT="${OUT:-/tmp/glim_start}"; MAP_S="${MAP_S:-20}"
mkdir -p "$OUT"; rm -f "$OUT"/*
echo "== commit $(git -C "$REPO" rev-parse --short HEAD)  $(date -Is)  MAP_S=$MAP_S"
cd "$WS" && colcon build --packages-select gouda_interfaces gouda_core 2>&1 | tail -1
source "$WS/install/setup.bash"; cd "$REPO"
bash gouda.sh stop >/dev/null 2>&1
state() { curl -s "$URL/api/state" | python3 -c "import json,sys;s=json.load(sys.stdin);print('mode', s['mode']['name'], 'processing', s['mode']['fields'].get('processing_state'))"; }
events() { curl -s "$URL/api/state" | python3 -c "
import json,sys;s=json.load(sys.stdin)
for e in s['events'][-${1:-8}:]: print('  ', e['node'], e['event'], '|', e['reason'][:230])"; }
cmd() { echo "-- $1: $(curl -s -m 10 -X POST "$URL/api/command/$1")"; }
alive() { echo "-- mode_manager alive: $(pgrep -fc 'lib/gouda_core/gouda_mode_manager')  glim: $(pgrep -fc '^/opt/ros/jazzy/lib/glim_ros/glim_rosnode')"; }

bash gouda.sh start | tee "$OUT/start.out" || { echo "gouda.sh start FAILED"; exit 1; }
URL="$(cat "$WS/gouda_data/run/monitor.url")"; sleep 3; state; alive
if true; then   # sensors are always started (DEC-090)
  echo "== sensors (supervisor records and monitor table)"; curl -s "$URL/api/state" | python3 -c "
import json,sys;s=json.load(sys.stdin)
for e in s['events']:
    if e['node']=='gouda_sensor_supervisor': print('  ', e['event'], '|', e['reason'][:160])
for k,v in s['sensors'].items(): print('  ', k, v['status'], v['rate_hz'])"
  for t in /sensors/xt32/points /sensors/imu/data; do echo "-- $t"; timeout 8 ros2 topic hz "$t" 2>&1 | grep -m2 "average\|min"; done
  python3 - <<'EOF'
import time, rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import PointCloud2, Imu
rclpy.init(); n = Node('stamp_probe'); got = {}
def cb(name):
    def f(m):
        if name not in got: got[name] = (m.header.stamp.sec + m.header.stamp.nanosec * 1e-9, time.time(), m.header.frame_id, getattr(m, 'width', None), [f.name for f in getattr(m, 'fields', [])])
    return f
n.create_subscription(PointCloud2, 'sensors/xt32/points', cb('points'), qos_profile_sensor_data)
n.create_subscription(Imu, 'sensors/imu/data', cb('imu'), qos_profile_sensor_data)
end = time.time() + 5
while time.time() < end and len(got) < 2: rclpy.spin_once(n, timeout_sec=0.1)
for k, (st, now, fr, w, fields) in got.items(): print(f'-- {k}: frame={fr} stamp-now={st - now:+.3f} s width={w} fields={fields}')
print('-- not received:', [k for k in ('points', 'imu') if k not in got])
EOF
fi
if [[ "$(state)" == *"mode PAUSE"* ]]; then echo "== A0 boot entered PAUSE (TR-02); end from pause (TR-12) to return to manual"; cmd end_autonomy; sleep 2; state; events 5; alive; fi
echo "== A1 start mapping"; cmd start_mapping; sleep 3; state; events 6; alive
d=$(ls -td "$WS"/gouda_data/mapping/*/ | head -1); echo "-- T_lidar_imu in GLIM config:"; python3 -c "
import json;print(json.load(open('$d/glim_config/config_sensors.json'))['sensors']['T_lidar_imu'])"
echo "-- mapping for $MAP_S s"; sleep "$MAP_S"; grep -i "warn\|error" "$d/glim.log" | sort | uniq -c | sort -rn | head -12
echo "== A2 end mapping (must answer at once)"; t0=$(date +%s.%N); cmd end_mapping; echo "-- answered in $(python3 -c "print(round($(date +%s.%N)-$t0,2))") s"; state
for _ in $(seq 1 120); do s=$(state); [[ "$s" == *"processing idle"* ]] && break; sleep 1; done; state; events 10; alive
ls "$d" "$d/glim_dump" 2>&1 | head -12
echo "== A3 refused request (end_mapping while manual) must not kill the mode manager"; cmd end_mapping; sleep 1; alive
echo "== A4 second cycle"; cmd start_mapping; sleep 3; cmd end_mapping; for _ in $(seq 1 60); do s=$(state); [[ "$s" == *"processing idle"* ]] && break; sleep 1; done; state; events 6; alive
grep -n "Traceback\|ValueError\|process has died" "$WS/gouda_data/run/gouda_core.launch.log" | head -5
bash gouda.sh stop | tee "$OUT/stop.out"; sleep 1
echo "-- leftover: $(pgrep -f '^/usr/bin/python3 .*gouda_|^/opt/ros/jazzy/lib/glim_ros/glim_rosnode|hesai_ros_driver_node|adis_rcv_bin_node' | wc -l)"
echo "== done"
