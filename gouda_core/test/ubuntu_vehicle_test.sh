#!/usr/bin/env bash
# /dev tab on the isolated test stack: esp32_sim on a pty and a synthetic IMU, driven through the monitor's HTTP API. No vehicle, no real sensor.
# Checks: a run ends and recovers the model's values; the stop button ends a run; a test is refused outside manual; a second run works without restart.
set -o pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; repo="$(cd "$here/../.." && pwd)"; ws="$(cd "$repo/../.." && pwd)"
OUT="${OUT:-/tmp/vehicle_test}"; rm -rf "$OUT"; mkdir -p "$OUT"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-77}"
source /opt/ros/jazzy/setup.bash; source "$ws/install/setup.bash"
cleanup() { pkill -f vehicle_test_fixture 2>/dev/null; pkill -f esp32_sim 2>/dev/null; bash "$here/stack.sh" stop "$OUT/root"; }
trap cleanup EXIT
ros2 run gouda_core esp32_sim -- --path-file "$OUT/pty" --log "$OUT/sim.log" > "$OUT/sim.out" 2>&1 &
for _ in $(seq 1 20); do [[ -s "$OUT/pty" ]] && break; sleep 0.5; done
bash "$here/stack.sh" start "$OUT/root" || exit 1
for _ in $(seq 1 30); do ros2 lifecycle get /vehicle_bridge >/dev/null 2>&1 && break; sleep 1; done
ros2 param set /vehicle_bridge serial_port "$(cat "$OUT/pty")"
python3 "$here/vehicle_test_fixture.py" > "$OUT/fixture.out" 2>&1 &
python3 "$here/vehicle_test_drive.py" "$(cat "$OUT/root/run/monitor.url")" "$OUT" 2>&1 | tee "$OUT/result.txt"
rc=$?
ros2 lifecycle get /vehicle_bridge | tee -a "$OUT/result.txt"
[[ -n "$HOLD_S" ]] && sleep "$HOLD_S"   # to look at the page
exit $rc
