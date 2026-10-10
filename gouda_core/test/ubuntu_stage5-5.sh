#!/usr/bin/env bash
# Stage 5-5 software test on the Ubuntu / ROS 2 Jazzy machine (no vehicle, no ESP32: the Python firmware model on a pty).
# Runs: unit tests; A) motion_controller + vehicle_bridge + esp32_sim with the probe (TS-07, TS-13, TS-19 PC side, TS-12 data);
#       B) gouda.sh start with the bridge configured against the sim: TS-30 (motion_hold latched true in manual mode) and
#       TS-12 (monitor /api/state shows the ESP32 fields, then 不明/STALE after the sim stops).
# Output: everything to $OUT (default /tmp/stage55); copy the record to design/research/vehicle_pc/ afterwards.
set -uo pipefail
source /opt/ros/jazzy/setup.bash
WS="${GOUDA_WORKSPACE:-$HOME/gouda_ws}"; REPO="$WS/src/tsukuba-autonomous-robot"; OUT="${OUT:-/tmp/stage55}"
PARAMS="$REPO/design/generated/params"
mkdir -p "$OUT"; rm -f "$OUT"/*
echo "== commit: $(git -C "$REPO" rev-parse HEAD)  date: $(date -Is)"
cd "$WS" && colcon build --packages-select gouda_interfaces gouda_core 2>&1 | tail -3
source "$WS/install/setup.bash"
cd "$REPO" && echo "== unit tests" && python3 -m unittest discover -s gouda_core/test 2>&1 | tail -3
cleanup() { pkill -f stage55_probe 2>/dev/null; pkill -f "gouda_core/esp32_sim" 2>/dev/null; pkill -f "gouda_core.esp32_sim_pty" 2>/dev/null; pkill -f "vehicle_bridge" 2>/dev/null; pkill -f "gouda_motion_controller" 2>/dev/null; }
trap cleanup EXIT

echo "== A) stub chain (sim pty, bridge, motion_controller, probe)"
ros2 run gouda_core esp32_sim -- --path-file "$OUT/pty" --log "$OUT/sim.log" > "$OUT/sim.out" 2>&1 &
for _ in $(seq 1 20); do [[ -s "$OUT/pty" ]] && break; sleep 0.5; done
PTY="$(cat "$OUT/pty")"; echo "sim pty: $PTY"; head -1 "$OUT/sim.out"
ros2 run gouda_core vehicle_bridge --ros-args --params-file "$PARAMS/vehicle_bridge.trial.yaml" -p "serial_port:=$PTY" -p "params_dir:=$PARAMS" -p trial:=true > "$OUT/bridge.out" 2>&1 &
ros2 run gouda_core gouda_motion_controller --ros-args --params-file "$PARAMS/gouda_motion_controller.yaml" --params-file "$PARAMS/gouda_motion_controller.trial.yaml" > "$OUT/mc.out" 2>&1 &
sleep 3
for n in vehicle_bridge gouda_motion_controller; do ros2 lifecycle set "/$n" configure; ros2 lifecycle set "/$n" activate; done
ros2 lifecycle get /vehicle_bridge; ros2 lifecycle get /gouda_motion_controller
python3 "$REPO/gouda_core/test/stage55_probe.py" --params-dir "$PARAMS" --out "$OUT/probe.log" 2>&1 | tee "$OUT/probe.summary"
echo "-- deactivate bridge: firmware PC source must expire (PRM-13) -> sim log shows source none / pc_stale"
ros2 lifecycle set /vehicle_bridge deactivate; sleep 2.5
echo "-- sim transitions:"; grep -v "^$" "$OUT/sim.log" | tail -30
cleanup; sleep 1

echo "== B) gouda.sh + bridge configured against the sim (TS-30, TS-12)"
ros2 run gouda_core esp32_sim -- --path-file "$OUT/pty2" --log "$OUT/sim2.log" > "$OUT/sim2.out" 2>&1 &
for _ in $(seq 1 20); do [[ -s "$OUT/pty2" ]] && break; sleep 0.5; done
export GOUDA_WORKSPACE="$WS" GOUDA_TRIAL_PARAMS=1 GOUDA_SERIAL_PORT="$(cat "$OUT/pty2")"
bash gouda.sh start | tee "$OUT/gouda_start.out"
sleep 2
echo "-- TS-30 motion_hold (latched; expect hold=true, mode=1 manual):"; timeout 5 ros2 topic echo --once control/motion_hold | tee "$OUT/motion_hold.echo"
ros2 lifecycle set /vehicle_bridge configure; sleep 2
URL="$(cat "$WS/gouda_data/run/monitor.url")"
echo "-- TS-12 /api/state esp32 (bridge configured, sim running):"; curl -s "$URL/api/state" | python3 -c "import json,sys; s=json.load(sys.stdin)['esp32']; print(json.dumps({'freshness': s['freshness'], 'fields': {k: s['fields'].get(k) for k in ('source','reason','target_x_mv','pc_enabled','config_valid')}}, ensure_ascii=False))" | tee "$OUT/esp32_state_1.json"
pkill -f "gouda_core/esp32_sim" 2>/dev/null; pkill -f "gouda_core.esp32_sim_pty" 2>/dev/null; sleep 1.5
echo "-- TS-12 /api/state esp32 after the sim stopped (expect STALE with PRM-15 trial, mode unchanged):"; curl -s "$URL/api/state" | python3 -c "import json,sys; s=json.load(sys.stdin); e=s['esp32']; print(json.dumps({'freshness': e['freshness'], 'mode': s['mode']['name']}, ensure_ascii=False))" | tee "$OUT/esp32_state_2.json"
bash gouda.sh stop | tee "$OUT/gouda_stop.out"
sleep 1; echo "-- leftover processes: $(pgrep -f '^/usr/bin/python3 .*gouda_|^/opt/ros/jazzy/lib/glim_ros/glim_rosnode' | wc -l)"
echo "== done"
