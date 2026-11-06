#!/bin/bash
# TEST ONLY (round 2): onv layer, MPPI open_loop true, vx_min 0.27 (follow override), vx_max {0.4,0.5,0.6,0.8} via the /config Nav2 tab,
# turn model A (as generated) / B (az 0.5, wz 0.5, smoother 0.5) / C (az 0.3, wz 0.4, smoother 0.3 / 0.4). usage: run3.sh <domain> <stagger s> <jobs> <out>
T=~/gouda_ws_ffpi/src/tsukuba-autonomous-robot/gouda_core/test; D=$1; O=$4; mkdir -p $O; export ROS_DOMAIN_ID=$D; sleep "$2"
unset SIM_SPEED
GAINS_V=0.3,0.5,0.15,0,0,0.15,0.5
for j in $(cat "$3"); do
  IFS=: read -r lay sc vx mdl rep <<< "$j"; out=$O/${lay}_${sc}_vx${vx}_${mdl}_$rep; mkdir -p $out
  A="--m1107 --seed $rep"; [ $lay = onv ] && A="$A --ffpi $GAINS_V --odom-delay 0.1"
  export SIM_ARGS="$A"
  case $mdl in
    A) export GOUDA_TEST_NAV2='{"follow": {"vx_min": 0.27}}' ;;
    B) export GOUDA_TEST_NAV2='{"follow": {"vx_min": 0.27, "az_max": 0.5, "wz_max": 0.5}, "params": {"velocity_smoother": {"max_velocity": [1.25, 0.0, 0.5], "min_velocity": [-0.472, 0.0, -0.5], "max_accel": [1.2, 0.0, 0.5], "max_decel": [-1.2, 0.0, -0.5]}}}' ;;
    C) export GOUDA_TEST_NAV2='{"follow": {"vx_min": 0.27, "az_max": 0.3, "wz_max": 0.4}, "params": {"velocity_smoother": {"max_velocity": [1.25, 0.0, 0.4], "min_velocity": [-0.472, 0.0, -0.4], "max_accel": [1.2, 0.0, 0.3], "max_decel": [-1.2, 0.0, -0.3]}}}' ;;
  esac
  export SIM_LIMIT_MPS=$vx   # the section speed limit of the speed mask = vx_max (else MPPI rescales vx_max, vx_min, wz)
  echo "{\"mppi_vx_max_mps\": $vx}" > $out.values.json
  echo "$(date +%T) start $j d$D load $(cut -d" " -f1 /proc/loadavg)" >> $O/run.log
  timeout -s TERM 400 setsid bash $T/drive_sim.sh $sc $out $out.values.json >> $O/run_$D.log 2>&1
  echo "$(date +%T) end $j $(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d[\"end\"],d.get(\"completed\"),d[\"contacts\"],d[\"duration_s\"],d[\"avg_speed_mps\"],d[\"load1\"])" "$out/result.json" 2>&1|tail -1|cut -c1-100)" >> $O/run.log
  sleep 4
done
echo "$(date +%T) DONE $D" >> $O/run.log
