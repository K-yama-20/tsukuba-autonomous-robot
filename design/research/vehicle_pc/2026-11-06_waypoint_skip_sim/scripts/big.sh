#!/bin/bash
# usage: big.sh <domain> <delay> <job>...  job=method:scene:rep. TEST ONLY.
D=$1; sleep $2; shift 2; O=$HOME/big; T=$HOME/gouda_ws_cut/src/tsukuba-autonomous-robot/gouda_core/test; export ROS_DOMAIN_ID=$D
export SIM_ARGS="--measured --assist hold --assist-axes v --no-w-dead-moving"
for j in "$@"; do IFS=: read -r m sc rep <<< "$j"; unset BT_RADIUS PLAN_TOL SKIP_TEST; out="$O/${m}_${sc}_$rep"; mkdir -p "$out"
 case $m in wide*) export BT_RADIUS=1.3 PLAN_TOL=0.8;; esac
 case $m in *kuams) export SKIP_TEST=kuams;; *costmap) export SKIP_TEST=costmap;; *stall) export SKIP_TEST=stall;; esac
 export SKIP_LOG="$out/skip.log"
 echo "$(date +%T) start $j load $(cut -d' ' -f1 /proc/loadavg)" >> "$O/run.log"
 timeout -s TERM 300 bash "$T/drive_sim.sh" "$sc" "$out" >> "$O/run_$D.log" 2>&1; sleep 5
done; echo "DONE $D" >> "$O/run.log"
