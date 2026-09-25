#!/usr/bin/env bash
set -euo pipefail
workspace="${GOUDA_BUILD_WORKSPACE:-$HOME/gouda_ws}"
set +u
source /opt/ros/jazzy/setup.bash
source "$workspace/install/setup.bash"
set -u
export ROS_DOMAIN_ID=101
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export GZ_PARTITION=gouda-simulation-101
# VM virgl can emit invalid constant-minimum GPU lidar depths.
export LIBGL_ALWAYS_SOFTWARE="${GOUDA_SOFTWARE_RENDERING:-1}"
unset ROS_LOCALHOST_ONLY
command="${1:-run}"
shift || true
if [[ "$command" == scenarios ]]; then
  exec ros2 run gouda_sim scenarios --ros-args -p use_sim_time:=true "$@"
fi
if [[ "$command" != run && "$command" != gui ]]; then
  echo 'Usage: gazebo.sh run|gui [estimator:=ground_truth|glim] [left_gain:=0.96], or gazebo.sh scenarios';exit 2
fi
exec 9>/tmp/gouda-gazebo-101.lock
flock -n 9 || { echo "Gazebo simulation domain 101 is already in use"; exit 1; }
mkdir -p "$HOME/gouda_sim_runs"
export GOUDA_WORKSPACE="$(mktemp -d "$HOME/gouda_sim_runs/run-XXXXXXXX")"
touch "$GOUDA_WORKSPACE/.gouda-simulation"
echo "Simulation settings and recordings: $GOUDA_WORKSPACE"
runner=()
if [[ "$command" == run ]]; then runner=(xvfb-run -a -s "-screen 0 1280x720x24"); fi
exec "${runner[@]}" ros2 launch gouda_sim corridor.launch.py "gui:=$([[ "$command" == gui ]] && echo true || echo false)" "$@"
