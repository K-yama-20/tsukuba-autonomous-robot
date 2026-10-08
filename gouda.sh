#!/usr/bin/env bash
# gouda.sh (ND-01, stage 5-1): start / stop / status of the common Gouda core nodes of the new implementation.
#
#   bash gouda.sh start     launch gouda_core (gouda_mode_manager + gouda_recorder) in the background
#   bash gouda.sh stop      stop the launch started by this script (only processes it owns)
#   bash gouda.sh status    show whether the launch is running and where logs/data are
#
# Design: design/model.yaml ND-01, docs/implementation_stages.md 5-1. This script publishes nothing and never requests
# driving (M-001 K2). Mode-dependent nodes are activated by later stages (IFD-36). Settings are read from the generated
# parameter files (design/generated/params); the only values decided here are directories (PRM-25 data root).
# The legacy launchers scripts/gouda.sh and scripts/gouda_gui.sh (Mission Control GUI) were removed (DEC-068, 2026-10-09).
set -eo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace="${GOUDA_WORKSPACE:-$(cd "$repo/../.." 2>/dev/null && pwd || echo "$HOME/gouda_ws")}"
data_root="${GOUDA_DATA_ROOT:-$workspace/gouda_data}"        # PRM-25: <data_root>/records, <data_root>/state
params_dir="${GOUDA_PARAMS_DIR:-$repo/design/generated/params}"
run_dir="$data_root/run"
pid_file="$run_dir/gouda_core.pid"
log_file="$run_dir/gouda_core.launch.log"
ros_setup="${ROS_SETUP:-/opt/ros/jazzy/setup.bash}"

usage() { sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; }

running() { [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; }

case "${1:-}" in
  start)
    if running; then echo "already running (pid $(cat "$pid_file")); see $log_file"; exit 0; fi
    [[ -f "$ros_setup" ]] || { echo "ROS 2 setup not found: $ros_setup (set ROS_SETUP)"; exit 1; }
    [[ -f "$workspace/install/setup.bash" ]] || { echo "workspace not built: $workspace/install/setup.bash missing (colcon build gouda_interfaces gouda_core)"; exit 1; }
    [[ -d "$params_dir" ]] || { echo "generated parameter directory missing: $params_dir (run design/tools/generate_params.py)"; exit 1; }
    mkdir -p "$run_dir" "$data_root/records" "$data_root/state"
    # shellcheck disable=SC1090
    source "$ros_setup"; source "$workspace/install/setup.bash"
    nohup ros2 launch gouda_core gouda_core.launch.py "params_dir:=$params_dir" "data_root:=$data_root" >"$log_file" 2>&1 &
    echo $! >"$pid_file"
    echo "started gouda_core (pid $!); params=$params_dir data=$data_root log=$log_file"
    ;;
  stop)
    if ! running; then echo "not running"; rm -f "$pid_file"; exit 0; fi
    pid="$(cat "$pid_file")"
    kill -INT "$pid" 2>/dev/null || true
    for _ in $(seq 1 30); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
    kill -0 "$pid" 2>/dev/null && { echo "still running after SIGINT; sending SIGTERM"; kill -TERM "$pid" 2>/dev/null || true; }
    rm -f "$pid_file"; echo "stopped"
    ;;
  status)
    if running; then echo "running (pid $(cat "$pid_file"))"; else echo "not running"; fi
    echo "data_root=$data_root"; echo "params_dir=$params_dir"; echo "log=$log_file"
    [[ -f "$data_root/state/previous_mode_record.json" ]] && { echo -n "previous_mode_record: "; cat "$data_root/state/previous_mode_record.json"; }
    ;;
  *) usage; exit 2 ;;
esac
