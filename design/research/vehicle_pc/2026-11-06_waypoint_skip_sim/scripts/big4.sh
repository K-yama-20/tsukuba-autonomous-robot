#!/bin/bash
# usage: big4.sh <outdir> <domain> <delay> <job>...  job=method-level:scene:rep. TEST ONLY.
O=$1; D=$2; sleep $3; shift 3; T=$HOME/gouda_ws_cut/src/tsukuba-autonomous-robot/gouda_core/test; export ROS_DOMAIN_ID=$D
for j in "$@"; do IFS=: read -r ml sc rep <<< "$j"; m=${ml%-*}; l=${ml#*-}; out="$O/${ml}_${sc}_$rep"; mkdir -p "$out"
 case $l in D30) X="--dropout 0.3";; D60) X="--dropout 0.6";; G20) X="--ghost 20";; G100) X="--ghost 100";; D30G20) X="--dropout 0.3 --ghost 20";; *) exit 1;; esac
 export SIM_ARGS="--measured --assist hold --assist-axes v --no-w-dead-moving --noise 0.05 $X"
 unset SKIP_TEST SKIP_CFG
 case $m in base) ;; k10h0) export SKIP_TEST=kuams SKIP_CFG="{\"radius\":1.0,\"hold\":0.0}";; k10h3) export SKIP_TEST=kuams SKIP_CFG="{\"radius\":1.0,\"hold\":3.0}";; *) exit 1;; esac
 export SKIP_LOG="$out/skip.log"
 echo "$(date +%T) start $j load $(cut -d" " -f1 /proc/loadavg)" >> "$O/run.log"
 timeout -s TERM 300 bash "$T/drive_sim.sh" "$sc" "$out" >> "$O/run_$D.log" 2>&1; sleep 5
done; echo "DONE $D" >> "$O/run.log"
