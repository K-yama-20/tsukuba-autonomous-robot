#!/bin/bash
# usage: blind_run.sh <domain> <delay_s> <variant S0|S2> <seed> <scenario>...   TEST ONLY (issue #90 stage 2), ~/gouda_ws_blind
D=$1; DELAY=$2; V=$3; SEED=$4; shift 4; O=$HOME/blind_runs; T=$HOME/gouda_ws_blind/src/tsukuba-autonomous-robot/gouda_core/test
export ROS_DOMAIN_ID=$D; sleep "$DELAY"
for s in "$@"; do
  out="$O/${V}_${s}_r${SEED}"; echo "$(date +%T) start ${V}_${s}_r${SEED} d$D load $(cut -d" " -f1 /proc/loadavg)" >> "$O/run.log"
  if [ "$V" = S0 ]; then env -u GOUDA_TEST_LAYERS -u SIM_MID360_HEIGHT SIM_ARGS="--seed $SEED" timeout -s TERM 320 bash "$T/drive_sim.sh" "$s" "$out" >> "$O/run_$D.log" 2>&1
  else GOUDA_TEST_LAYERS=$V SIM_MID360_HEIGHT=0.5 SIM_ARGS="--seed $SEED" timeout -s TERM 320 bash "$T/drive_sim.sh" "$s" "$out" >> "$O/run_$D.log" 2>&1; fi
  echo "$(date +%T) end ${V}_${s}_r${SEED} $(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d[\"end\"],d[\"contacts\"],d[\"avg_speed_mps\"],d[\"load1\"])" "$out/result.json" 2>&1 | tail -1 | cut -c1-90)" >> "$O/run.log"
  sleep 5
done
echo "DONE d$D" >> "$O/run.log"
