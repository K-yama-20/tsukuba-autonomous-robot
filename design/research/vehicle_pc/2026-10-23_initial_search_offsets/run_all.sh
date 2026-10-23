#!/bin/bash
# DEC-360 (1): the five cases one after another (bin 148). Output: ~/nd07_offsets/case_<dx>_<dyaw>.txt
MAP=${1:?map dir}; ROW=${2:-200}; HERE=$(cd "$(dirname "$0")" && pwd); OUT=~/nd07_offsets; mkdir -p $OUT
for c in "0 90" "0 180" "1 90" "3 0" "5 0"; do
  set -- $c
  bash $HERE/offset_case.sh "$MAP" "$ROW" $1 $2 > $OUT/case_${1}m_${2}deg.txt 2>&1
  sleep 5
done
echo done > $OUT/ALL_DONE
