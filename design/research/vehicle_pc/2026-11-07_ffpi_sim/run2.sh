#!/bin/bash
# TEST ONLY: ND-11 FF+PI layer (REV-241 draft) in the drive simulator on the real stack, DEC-445 plant (--m1107). usage: run.sh <domain> <stagger s> <jobs file> <out dir>
T=~/gouda_ws_ffpi/src/tsukuba-autonomous-robot/gouda_core/test; D=$1; O=$4; mkdir -p $O; export ROS_DOMAIN_ID=$D; sleep "$2"
unset GOUDA_TEST_NAV2 SIM_SPEED
echo "{\"mppi_open_loop\": false}" > $O/olfalse.json; echo "{\"controller_use_mppi\": false}" > $O/rpp.json
GAINS=0.3,0.5,0.15,0.5,1.0,0.15,0.5; GAINS_V=0.3,0.5,0.15,0,0,0,0.5
for j in $(cat "$3"); do
  IFS=: read -r lay sc ctl d rep <<< "$j"; out=$O/${lay}_${sc}_${ctl}_d${d}_$rep; mkdir -p $out
  A="--m1107 --seed $rep"; [ $lay = on ] && A="$A --ffpi $GAINS --odom-delay $d"; [ $lay = onv ] && A="$A --ffpi $GAINS_V --odom-delay $d"
  export SIM_ARGS="$A"
  V=""; [ $ctl = olfalse ] && V=$O/olfalse.json; [ $ctl = rpp ] && V=$O/rpp.json
  echo "$(date +%T) start $j d$D load $(cut -d" " -f1 /proc/loadavg)" >> $O/run.log
  timeout -s TERM 400 setsid bash $T/drive_sim.sh $sc $out $V >> $O/run_$D.log 2>&1
  echo "$(date +%T) end $j $(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d[\"end\"],d.get(\"completed\"),d[\"contacts\"],d[\"duration_s\"],d[\"avg_speed_mps\"],d[\"load1\"])" "$out/result.json" 2>&1|tail -1|cut -c1-100)" >> $O/run.log
  sleep 4
done
echo "$(date +%T) DONE $D" >> $O/run.log
