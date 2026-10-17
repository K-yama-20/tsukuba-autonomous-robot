#!/bin/bash
# Evaluation run of candidate A (lidar_localization_ros2) on a recorded rosbag read in place from the external drive (Parallels share; not copied).
# usage: run_eval_A.sh <param.yaml> <bag_dir> <odom_tum> <ref_tum> <start_offset_s> <duration_s> <rate> <out_prefix> [dx dy dyaw_deg]
YAML=$1; BAG=$2; ODOM=$3; REF=$4; OFF=$5; DUR=$6; RATE=$7; OUT=$8; DX=${9:-0}; DY=${10:-0}; DYAW=${11:-0}
export FASTRTPS_DEFAULT_PROFILES_FILE=~/loc_eval_ws/tools/fastdds_eval.xml  # large SHM segment: 2 MB point clouds are lost over UDP inside the VM (G-DDS)
source /opt/ros/jazzy/setup.bash; source ~/loc_eval_ws/install/setup.bash
T=~/loc_eval_ws/tools
BAG0=$(python3 -c "import yaml,sys;d=yaml.safe_load(open('$BAG/metadata.yaml'))['rosbag2_bagfile_information'];print(d['starting_time']['nanoseconds_since_epoch']/1e9)")
T0=$(python3 -c "print($BAG0+$OFF)")
ros2 launch lidar_localization_ros2 lidar_localization.launch.py localization_param_dir:=$YAML cloud_topic:=/sensors/xt32/points publish_lidar_tf:=false use_sim_time:=true > ${OUT}_launch.log 2>&1 &
python3 $T/odom_replay.py $ODOM odom xt32_link 0.15 > ${OUT}_odom.log 2>&1 &
python3 $T/eval_logger.py $OUT /pcl_pose /alignment_status > ${OUT}_logger.log 2>&1 &
python3 $T/init_pose_pub.py $REF $T0 $DX $DY $DYAW 1.0 > ${OUT}_init.log 2>&1 &
sleep 15
( while true; do ps -C lidar_localization_node -o %cpu=,rss= | head -1 | sed "s/^/$(date +%s) /" >> ${OUT}_cpu.txt; sleep 5; done ) &
CPUMON=$!
ros2 bag play $BAG --clock 100 --rate $RATE --start-offset $OFF --playback-duration $DUR --topics /sensors/xt32/points > ${OUT}_play.log 2>&1
sleep 5
kill $CPUMON 2>/dev/null
pkill -INT -f "lidar_localization_ros2|odom_replay.py|eval_logger.py|init_pose_pub.py|start_lifecycle_node" 2>/dev/null; sleep 3
pkill -KILL -f "lidar_localization_node|odom_replay.py|eval_logger.py|init_pose_pub.py" 2>/dev/null
echo "done $OUT T0=$T0"
