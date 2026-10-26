#!/bin/bash
# DEC-385 S3 (bin 156): offsets 1-4 m (along map x, yaw 0) x search spread (initial_xy_variance = sigma^2: 0.25, 1, 2.25, 4 m^2,
# i.e. sigma 0.5, 1.0, 1.5, 2.0 m). Test only: the variance is passed with -p to the test node; the generated files are not changed.
# Output: ~/nd07_search_matrix/case_<dx>m_var<v>.txt. ROS_DOMAIN_ID 91 (the running Gouda, if any, is in domain 0).
MAP=${1:?map dir}; ROW=${2:-200}; WIN=${3:-90}; HERE=$(cd "$(dirname "$0")" && pwd); OUT=~/nd07_search_matrix; mkdir -p $OUT
export ROS_DOMAIN_ID=91
for v in 0.25 1.0 2.25 4.0; do
  for dx in 1 2 3 4; do
    XYVAR=$v bash $HERE/offset_case.sh "$MAP" "$ROW" $dx 0 $WIN > $OUT/case_${dx}m_var${v}.txt 2>&1
    sleep 5
  done
done
echo done > $OUT/ALL_DONE
