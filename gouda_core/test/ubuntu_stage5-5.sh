#!/usr/bin/env bash
# Stage 5-5 software test on the Ubuntu / ROS 2 Jazzy machine (no vehicle, no ESP32: the Python firmware model on a pty).
# Runs: unit tests; A) motion_controller + vehicle_bridge + esp32_sim with the probe (TS-07, TS-13, TS-19 PC side, TS-12 data);
#       B) the isolated test stack (stack.sh) with the bridge configured against the sim: TS-30 (motion_hold latched true in manual mode) and
#       TS-12 (monitor /api/state shows the ESP32 fields, then 不明/STALE after the sim stops).
# Output: everything to $OUT (default /tmp/stage55); copy the record to design/research/vehicle_pc/ afterwards.
set -o pipefail   # no -u: /opt/ros/jazzy/setup.bash reads unset variables
source /opt/ros/jazzy/setup.bash
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; WS="$(cd "$REPO/../.." && pwd)"; OUT="${OUT:-/tmp/stage55}"
export ROS_DOMAIN_ID=77   # isolated from a running robot session (same node names)
PARAMS="$REPO/design/generated/params"
mkdir -p "$OUT"; rm -f "$OUT"/*
echo "== commit: $(git -C "$REPO" rev-parse HEAD)  date: $(date -Is)"
cd "$WS" && colcon build --packages-select gouda_interfaces gouda_core 2>&1 | tail -3
source "$WS/install/setup.bash"
cd "$REPO" && echo "== unit tests" && python3 -m unittest discover -s gouda_core/test 2>&1 | tail -3
cleanup() { pkill -f stage55_probe 2>/dev/null; pkill -f "gouda_core/esp32_sim" 2>/dev/null; pkill -f "gouda_core.esp32_sim_pty" 2>/dev/null; pkill -f "vehicle_bridge" 2>/dev/null; pkill -f "gouda_motion_controller" 2>/dev/null; }
trap cleanup EXIT

if [[ "${SKIP_A:-0}" != 1 ]]; then
echo "== A) stub chain (sim pty, bridge, motion_controller, probe)"
ros2 run gouda_core esp32_sim -- --path-file "$OUT/pty" --log "$OUT/sim.log" > "$OUT/sim.out" 2>&1 &
for _ in $(seq 1 20); do [[ -s "$OUT/pty" ]] && break; sleep 0.5; done
PTY="$(cat "$OUT/pty")"; echo "sim pty: $PTY"; head -1 "$OUT/sim.out"
ros2 run gouda_core vehicle_bridge --ros-args --params-file "$PARAMS/vehicle_bridge.trial.yaml" -p "serial_port:=$PTY" -p "params_dir:=$PARAMS" -p trial:=true > "$OUT/bridge.out" 2>&1 &
ros2 run gouda_core gouda_motion_controller --ros-args --params-file "$PARAMS/gouda_motion_controller.yaml" --params-file "$PARAMS/gouda_motion_controller.trial.yaml" > "$OUT/mc.out" 2>&1 &
# wait until both nodes are discoverable (a fixed sleep was too short in a fresh ROS domain); the pass criteria are unchanged
for n in vehicle_bridge gouda_motion_controller; do for _ in $(seq 1 30); do ros2 lifecycle get "/$n" >/dev/null 2>&1 && break; sleep 1; done; done
for n in vehicle_bridge gouda_motion_controller; do ros2 lifecycle set "/$n" configure; ros2 lifecycle set "/$n" activate; done
ros2 lifecycle get /vehicle_bridge; ros2 lifecycle get /gouda_motion_controller
python3 "$REPO/gouda_core/test/stage55_probe.py" --params-dir "$PARAMS" --out "$OUT/probe.log" 2>&1 | tee "$OUT/probe.summary"
echo "-- deactivate bridge: firmware PC source must expire (PRM-13) -> sim log shows source none / pc_stale"
ros2 lifecycle set /vehicle_bridge deactivate; sleep 2.5
echo "-- sim transitions:"; grep -v "^$" "$OUT/sim.log" | tail -30
cleanup; sleep 1
fi

echo "== B) test stack (stack.sh: isolated domain, trial values, no sensor drivers) + bridge against the sim (TS-30, TS-12)"
ros2 run gouda_core esp32_sim -- --path-file "$OUT/pty2" --log "$OUT/sim2.log" > "$OUT/sim2.out" 2>&1 &
for _ in $(seq 1 20); do [[ -s "$OUT/pty2" ]] && break; sleep 0.5; done
export ROS_DOMAIN_ID=77; ROOT="$OUT/stack"
bash "$REPO/gouda_core/test/stack.sh" start "$ROOT" | tee "$OUT/stack_start.out"
sleep 2
echo "-- TS-30 motion_hold (latched; expect hold=true, mode=1 manual):"; timeout 5 ros2 topic echo --once control/motion_hold | tee "$OUT/motion_hold.echo"
ros2 param set /vehicle_bridge serial_port "$(cat "$OUT/pty2")"   # PRM-61 is unresolved in the model; the test gives the pty
ros2 lifecycle set /vehicle_bridge configure; sleep 2
URL="$(cat "$ROOT/run/monitor.url")"
echo "-- TS-12 /api/state esp32 (bridge configured, sim running):"; curl -s "$URL/api/state" | python3 -c "import json,sys; s=json.load(sys.stdin)['esp32']; print(json.dumps({'freshness': s['freshness'], 'fields': {k: s['fields'].get(k) for k in ('source','reason','target_x_mv','pc_enabled','config_valid')}}, ensure_ascii=False))" | tee "$OUT/esp32_state_1.json"
pkill -f "gouda_core/esp32_sim" 2>/dev/null; pkill -f "gouda_core.esp32_sim_pty" 2>/dev/null; sleep 1.5
echo "-- TS-12 /api/state esp32 after the sim stopped (expect STALE with PRM-15 trial, mode unchanged):"; curl -s "$URL/api/state" | python3 -c "import json,sys; s=json.load(sys.stdin); e=s['esp32']; print(json.dumps({'freshness': e['freshness'], 'mode': s['mode']['name']}, ensure_ascii=False))" | tee "$OUT/esp32_state_2.json"
bash "$REPO/gouda_core/test/stack.sh" stop "$ROOT" | tee "$OUT/stack_stop.out"
echo "== done"
