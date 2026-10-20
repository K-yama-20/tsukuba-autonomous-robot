#!/bin/bash
# Sequential evaluation runs (one at a time to avoid CPU/memory contention). Each line of the job file:
#   A|A3 <out> <map(175857|173522)> <bag_session> <dump_for_odom_and_ref> <offset_s> <duration_s> <rate> <dx> <dy> <dyaw> [align] [leaf]
T=~/loc_eval_ws/tools; B=/media/psf/Crucial_4TB/Gouda/gouda_data; cd ~/loc_eval_ws/runs
while read -r kind out map sess dump off dur rate dx dy dyaw align leaf; do
  [ -z "$kind" ] && continue; case "$kind" in \#*) continue;; esac
  ODOM=$B/maps/$dump/source/odom_lidar.txt; REF=$B/maps/$dump/source/traj_lidar.txt; BAG=$B/records/$sess/rosbag/bag
  echo "$(date +%T) start $kind $out" >> batch.log
  if [ "$kind" = A ]; then
    $T/run_eval_A.sh $T/eval_A_20261014_${map}.yaml $BAG $ODOM $REF $off $dur $rate $out $dx $dy $dyaw > ${out}_run.log 2>&1
  else
    LEAF=${leaf:-0.5} $T/run_eval_A3.sh $T/map_${map}.param.yaml $BAG $ODOM $REF $off $dur $rate $out $dx $dy $dyaw ${align:-0} > ${out}_run.log 2>&1
  fi
  echo "$(date +%T) end $kind $out" >> batch.log
done < "$1"
echo "$(date +%T) BATCH_DONE $1" >> batch.log
