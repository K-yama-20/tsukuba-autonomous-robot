#!/usr/bin/env bash
# gouda.sh (ND-01, stage 5-1): start / stop / status of the common Gouda core nodes of the new implementation.
#
#   bash gouda.sh start     launch gouda_core (gouda_mode_manager + gouda_recorder + gouda_monitor) in the background
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
trial_params="${GOUDA_TRIAL_PARAMS:-0}"               # 1 = load <node>.trial.yaml (software trial values; stub tests only, never on the vehicle)
monitor_port="${GOUDA_MONITOR_PORT:-0}"               # PRM-26: 0 = OS-chosen port; URL is written to $data_root/run/monitor.url
serial_port="${GOUDA_SERIAL_PORT:-}"                  # stage 5-5: ESP32 serial device for vehicle_bridge (operational value; a pty in stub tests). Empty = bridge stays unconfigured
url_file="$data_root/run/monitor.url"
run_dir="$data_root/run"
pid_file="$run_dir/gouda_core.pid"
log_file="$run_dir/gouda_core.launch.log"
ros_setup="${ROS_SETUP:-/opt/ros/jazzy/setup.bash}"

usage() { sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; }

# The launch runs in its own process group (job control on) so that SIGINT is not ignored by the background job and
# the whole group (launch + nodes) can be signalled together; "running" means any process of that group is alive.
pgid() { [[ -f "$pid_file" ]] && cat "$pid_file"; }
running() { local g; g="$(pgid)" && [[ -n "$g" ]] && pgrep -g "$g" >/dev/null 2>&1; }

case "${1:-}" in
  start)
    if running; then echo "already running (pid $(cat "$pid_file")); see $log_file"; exit 0; fi
    [[ -f "$ros_setup" ]] || { echo "ROS 2 setup not found: $ros_setup (set ROS_SETUP)"; exit 1; }
    [[ -f "$workspace/install/setup.bash" ]] || { echo "workspace not built: $workspace/install/setup.bash missing (colcon build gouda_interfaces gouda_core)"; exit 1; }
    [[ -d "$params_dir" ]] || { echo "generated parameter directory missing: $params_dir (run design/tools/generate_params.py)"; exit 1; }
    mkdir -p "$run_dir" "$data_root/records" "$data_root/state"
    # shellcheck disable=SC1090
    source "$ros_setup"; source "$workspace/install/setup.bash"
    set -m   # job control: the background launch gets its own process group and keeps default SIGINT handling
    rm -f "$url_file"
    ros2 launch gouda_core gouda_core.launch.py "params_dir:=$params_dir" "data_root:=$data_root" "monitor_port:=$monitor_port" "serial_port:=$serial_port" "trial:=$([[ "$trial_params" == 1 ]] && echo true || echo false)" >"$log_file" 2>&1 &
    launch_pid=$!
    set +m
    echo "$launch_pid" >"$pid_file"   # with job control on, the job's pgid equals the launch pid
    echo "started gouda_core (pgid $launch_pid); params=$params_dir data=$data_root log=$log_file trial_params=$trial_params"
    [[ "$trial_params" == 1 ]] && echo "WARNING: software trial values (<node>.trial.yaml) are loaded; not for the vehicle"
    for _ in $(seq 1 20); do [[ -s "$url_file" ]] && break; sleep 1; done
    [[ -s "$url_file" ]] && echo "monitor: $(cat "$url_file") (open on this PC desktop; no screen forwarding)" || echo "monitor URL not written yet; see $url_file after start-up"
    ;;
  stop)
    if ! running; then echo "not running"; rm -f "$pid_file"; exit 0; fi
    g="$(pgid)"
    kill -INT -- "-$g" 2>/dev/null || true          # launch and every node of the group shut down on SIGINT
    for _ in $(seq 1 30); do pgrep -g "$g" >/dev/null 2>&1 || break; sleep 1; done
    if pgrep -g "$g" >/dev/null 2>&1; then
      echo "still running after SIGINT; sending SIGTERM to the group"; kill -TERM -- "-$g" 2>/dev/null || true
      for _ in $(seq 1 10); do pgrep -g "$g" >/dev/null 2>&1 || break; sleep 1; done
      pgrep -g "$g" >/dev/null 2>&1 && { echo "still running after SIGTERM; sending SIGKILL"; kill -KILL -- "-$g" 2>/dev/null || true; }
    fi
    rm -f "$pid_file"; echo "stopped (no process of group $g remains: $(pgrep -g "$g" >/dev/null 2>&1 && echo no || echo yes))"
    ;;
  status)
    if running; then echo "running (pgid $(pgid); processes: $(pgrep -g "$(pgid)" | wc -l | tr -d ' '))"; else echo "not running"; fi
    echo "data_root=$data_root"; echo "params_dir=$params_dir"; echo "log=$log_file"
    [[ -s "$url_file" ]] && echo "monitor=$(cat "$url_file")"
    [[ -f "$data_root/state/previous_mode_record.json" ]] && { echo -n "previous_mode_record: "; cat "$data_root/state/previous_mode_record.json"; }
    ;;
  *) usage; exit 2 ;;
esac
