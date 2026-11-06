#!/bin/bash
# TEST ONLY (第214便): DEC-445 plant (--m1107) x MPPI open_loop / output floor, at SPEED x simulated time.
# usage: run4x.sh <ws> <outdir> <domain> <start_delay_s> <speed> <job>...   job = method:scene:rep
# At speed S > 1 the wall-clock loops of Nav2 (controller_server, costmap update; #67) are raised S times (test copy only).
WS=$1; O=$2; D=$3; sleep "$4"; SPEED=$5; shift 5
T=$WS/src/tsukuba-autonomous-robot/gouda_core/test; export ROS_DOMAIN_ID=$D; mkdir -p "$O"
declare -A FL=( [fm]="0.22,0.03,0.25,0.03,0.30,0.18,0.03" [hi]="0.25,0.03,0.28,0.03,0.33,0.21,0.03" [lo]="0.20,0.03,0.23,0.03,0.28,0.16,0.03" [f10]="0.10,0.03,0.10,0.03,0.10,0.10,0.03" )
for j in "$@"; do
  IFS=: read -r m sc rep <<< "$j"; out="$O/${m}_${sc}_$rep"; mkdir -p "$out"
  X="--m1107 --seed $rep"; OL=false
  case $m in
    base) ;; ol) OL=true ;;
    fm) X="$X --floor ${FL[fm]}" ;;
    fmol) X="$X --floor ${FL[fm]}"; OL=true ;;
    hiol) X="$X --floor ${FL[hi]}"; OL=true ;;
    lool) X="$X --floor ${FL[lo]}"; OL=true ;;
    f10ol) X="$X --floor ${FL[f10]}"; OL=true ;;
    *) echo "unknown $m" >> "$O/run.log"; continue ;;
  esac
  export GOUDA_TEST_NAV2=$(python3 - "$OL" "$SPEED" <<'PY'
import json, sys
ol, s = sys.argv[1] == 'true', float(sys.argv[2])
d = {'follow': {'open_loop': True}} if ol else {}
if s > 1:
    d['params'] = {'controller_server': {'controller_frequency': 20.0 * s},
                   'local_costmap.local_costmap': {'update_frequency': 10.0 * s},
                   'global_costmap.global_costmap': {'update_frequency': 1.0 * s}}
print(json.dumps(d))
PY
)
  export SIM_ARGS="$X"; if [ "$SPEED" != "1" ]; then export SIM_SPEED=$SPEED; else unset SIM_SPEED; fi
  echo "$(date +%T) start $j speed $SPEED load $(cut -d' ' -f1 /proc/loadavg)" >> "$O/run.log"
  timeout -s TERM 400 bash "$T/drive_sim.sh" "$sc" "$out" >> "$O/run_$D.log" 2>&1; sleep 4
done
echo "$(date +%T) DONE $D" >> "$O/run.log"
