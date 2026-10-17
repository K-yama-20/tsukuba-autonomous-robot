#!/bin/bash
# Evaluation run of candidate A3 (autoware_ndt_scan_matcher + autoware_ekf_localizer + autoware_pointcloud_map_loader, Jazzy 1.9.0)
# (input points range-cropped 1..100 m and voxel-downsampled by eval_voxel_filter (PCL VoxelGrid), leaf $LEAF m, default 0.5) on a recorded rosbag read in place from the external drive (Parallels share; not copied). Twist from the GLIM odometry (twist_relay.py).
# usage: run_eval_A3.sh <map_param.yaml> <bag_dir> <odom_tum> <ref_tum> <start_offset_s> <duration_s> <rate> <out_prefix> [dx dy dyaw_deg align(0|1)]
MAPP=$1; BAG=$2; ODOM=$3; REF=$4; OFF=$5; DUR=$6; RATE=$7; OUT=$8; DX=${9:-0}; DY=${10:-0}; DYAW=${11:-0}; ALIGN=${12:-0}
BYAW_DEG=-99.2; BYAW_RAD=$(python3 -c "import math;print(-math.radians($BYAW_DEG))")
export FASTRTPS_DEFAULT_PROFILES_FILE=~/loc_eval_ws/tools/fastdds_eval.xml  # large SHM segment: 2 MB point clouds are lost over UDP inside the VM (G-DDS)
source /opt/ros/jazzy/setup.bash; source ~/loc_eval_ws/install/setup.bash
T=~/loc_eval_ws/tools
BAG0=$(python3 -c "import yaml;d=yaml.safe_load(open('$BAG/metadata.yaml'))['rosbag2_bagfile_information'];print(d['starting_time']['nanoseconds_since_epoch']/1e9)")
T0=$(python3 -c "print($BAG0+$OFF)")
ros2 run tf2_ros static_transform_publisher --yaw $BYAW_RAD --frame-id base_link --child-frame-id xt32_link --ros-args -p use_sim_time:=true > ${OUT}_stf.log 2>&1 &
ros2 run autoware_map_loader autoware_pointcloud_map_loader --ros-args --params-file $MAPP -r __node:=pointcloud_map_loader > ${OUT}_map.log 2>&1 &
ros2 run eval_voxel_filter voxel_filter --ros-args -r input:=/sensors/xt32/points -r output:=/eval/points_downsampled -p leaf_size:=${LEAF:-0.5} -p min_range:=1.0 -p max_range:=100.0 -p use_sim_time:=true > ${OUT}_voxel.log 2>&1 &
ros2 launch autoware_ndt_scan_matcher ndt_scan_matcher.launch.xml param_file:=${NDTP:-$T/eval_A3_ndt.param.yaml} input_pointcloud:=/eval/points_downsampled input_initial_pose_topic:=/ekf_pose_with_covariance input_service_trigger_node:=/ndt_trigger_node client_map_loader:=/service/get_differential_pcd_map > ${OUT}_ndt.log 2>&1 &
ros2 launch autoware_ekf_localizer ekf_localizer.launch.xml param_file:=$T/eval_A3_ekf.param.yaml input_pose_with_cov_name:=/ndt_pose_with_covariance input_twist_with_cov_name:=/eval/twist_with_covariance input_initial_pose_name:=/initialpose3d input_trigger_node_service_name:=/ekf_trigger_node > ${OUT}_ekf.log 2>&1 &
python3 $T/twist_relay.py $ODOM /eval/twist_with_covariance base_link $BYAW_DEG 0.0 > ${OUT}_twist.log 2>&1 &
python3 $T/eval_logger.py $OUT /ndt_pose_with_covariance /diagnostics > ${OUT}_logger.log 2>&1 &
python3 $T/eval_logger.py ${OUT}_ekf /ekf_pose_with_covariance - > ${OUT}_logger_ekf.log 2>&1 &
python3 $T/a3_init.py $REF $T0 $DX $DY $DYAW $ALIGN $BYAW_DEG > ${OUT}_init.log 2>&1 &
sleep 12
( while true; do ps -C autoware_ndt_scan_matcher_node -o %cpu=,rss= | head -1 | sed "s/^/$(date +%s) ndt /" >> ${OUT}_cpu.txt; ps -C autoware_ekf_localizer_node -o %cpu=,rss= | head -1 | sed "s/^/$(date +%s) ekf /" >> ${OUT}_cpu.txt; sleep 5; done ) &
CPUMON=$!
ros2 bag play $BAG --clock 100 --rate $RATE --start-offset $OFF --playback-duration $DUR --topics /sensors/xt32/points > ${OUT}_play.log 2>&1
sleep 5
kill $CPUMON 2>/dev/null
pkill -INT -f "autoware_ndt_scan_matcher_node|autoware_ekf_localizer_node|autoware_pointcloud_map_loader|static_transform_publisher|voxel_filter|twist_relay.py|eval_logger.py|a3_init.py|ndt_scan_matcher.launch|ekf_localizer.launch" 2>/dev/null; sleep 3
pkill -KILL -f "autoware_ndt_scan_matcher_node|autoware_ekf_localizer_node|autoware_pointcloud_map_loader|voxel_filter|twist_relay.py|eval_logger.py|a3_init.py" 2>/dev/null
echo "done $OUT T0=$T0"
