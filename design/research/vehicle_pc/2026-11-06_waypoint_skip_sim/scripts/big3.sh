#!/bin/bash
# usage: big2.sh <outdir> <domain> <delay> <job>...  job=method:scene:rep. TEST ONLY.
O=$1; D=$2; sleep $3; shift 3; T=$HOME/gouda_ws_cut/src/tsukuba-autonomous-robot/gouda_core/test; export ROS_DOMAIN_ID=$D
export SIM_ARGS="--measured --assist hold --assist-axes v --no-w-dead-moving --noise 0.05"
for j in "$@"; do IFS=: read -r m sc rep <<< "$j"; out="$O/${m}_${sc}_$rep"; mkdir -p "$out"
 export SKIP_TEST=kuams; case $m in
  base) unset SKIP_TEST SKIP_CFG;;
  kuams) export SKIP_CFG={};;
  k10h0)   export SKIP_CFG="{\"radius\":1.0,\"hold\":0.0}";;
  k10h3)   export SKIP_CFG="{\"radius\":1.0,\"hold\":3.0}";;
  k10h10)  export SKIP_CFG="{\"radius\":1.0,\"hold\":10.0}";;
  k07h3)   export SKIP_CFG="{\"radius\":0.7,\"hold\":3.0}";;
  k10n3h3) export SKIP_CFG="{\"radius\":1.0,\"hold\":3.0,\"near\":3.0}";;
  *) echo bad $m; exit 1;;
 esac
 export SKIP_LOG="$out/skip.log"
 echo "$(date +%T) start $j load $(cut -d" " -f1 /proc/loadavg)" >> "$O/run.log"
 timeout -s TERM 300 bash "$T/drive_sim.sh" "$sc" "$out" >> "$O/run_$D.log" 2>&1; sleep 5
done; echo "DONE $D" >> "$O/run.log"
