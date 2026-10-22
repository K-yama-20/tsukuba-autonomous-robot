#!/usr/bin/env bash
# gouda.sh (ND-01): the ONE way to start Gouda. No environment options (DEC-090, DEC-091).
#
#   bash gouda.sh start     start everything: gouda_core nodes and the sensor drivers (via gouda_sensor_supervisor)
#   bash gouda.sh stop      stop what this script started (only processes it owns); waits, without a time limit, for GLIM and
#                           rosbag to finish saving and shows their progress every second (DEC-174)
#   bash gouda.sh status    show whether it is running and where logs/data are
#
# Everything else is fixed or comes from the design model (design/model.yaml -> design/generated/params):
#   workspace   two directories above this script (<ws>/src/<this repo>/gouda.sh)
#   data        <workspace>/gouda_data (PRM-25): records/, state/, config/, run/ (monitor URL, launch log, sensor state)
#   settings    design/generated/params next to this script; ROS 2 Jazzy from /opt/ros/jazzy (the design's distribution)
#   sensors     always started; a missing device is simply waited for (gouda_sensor_supervisor, DEC-088)
#   DDS         Fast DDS profile written to <data>/run/fastdds_profile.xml from PRM-100 / PRM-101 and given to every process (DEC-279, DEC-138)
# Software trial values (<node>.trial.yaml) are never loaded by this script; only the test scripts in gouda_core/test do.
# This script publishes nothing and never requests driving (M-001 K2). Mode-dependent nodes are activated through
# lifecycle transitions (IFD-36). The legacy launchers scripts/gouda.sh and scripts/gouda_gui.sh were removed (DEC-068).
set -eo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace="$(cd "$repo/../.." && pwd)"
data_root="$workspace/gouda_data"                     # PRM-25
params_dir="$repo/design/generated/params"
ros_setup="/opt/ros/jazzy/setup.bash"
url_file="$data_root/run/monitor.url"
run_dir="$data_root/run"
pid_file="$run_dir/gouda_core.pid"
log_file="$run_dir/gouda_core.launch.log"
dds_profile="$run_dir/fastdds_profile.xml"            # written at start by gouda_core.dds_profile (PRM-100 / PRM-101)

usage() { sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; }

# The launch runs in its own process group (job control on) so that SIGINT is not ignored by the background job and
# the whole group (launch + nodes) can be signalled together; "running" means any process of that group is alive.
pgid() { [[ -f "$pid_file" ]] && cat "$pid_file"; }
running() { local g; g="$(pgid)" && [[ -n "$g" ]] && pgrep -g "$g" >/dev/null 2>&1; }

# Gouda launches of this user that this script does not track (G-DUP-START): e.g. one left running after its workspace or data
# folder was moved away, so its pid file went with it. Test stacks (gouda_core/test/stack.sh, trial:=true) are not counted.
# Prints "<launch pid> <pgid> <working folder>" per launch.
untracked() {
  local own p g
  own="$(pgid 2>/dev/null || true)"
  for p in $(pgrep -u "$(id -u)" -f 'ros2 launch gouda_core gouda_core[.]launch[.]py' 2>/dev/null || true); do
    tr '\0' ' ' <"/proc/$p/cmdline" 2>/dev/null | grep -q 'trial:=true' && continue
    g="$(ps -o pgid= -p "$p" 2>/dev/null | tr -d ' ')"
    [[ -z "$g" || ( -n "$own" && "$g" == "$own" ) ]] && continue
    echo "$p $g $(readlink "/proc/$p/cwd" 2>/dev/null || echo '?')"
  done
}
report_untracked() {   # $1: the list from untracked
  echo "another Gouda is running that this gouda.sh did not start (its pid file is not in $run_dir):"
  while read -r p g cwd; do echo "  process group $g (launch pid $p, folder $cwd)"; done <<<"$1"
  echo "stop it with: kill -INT -- -<process group>   (e.g. kill -INT -- -$(head -1 <<<"$1" | awk '{print $2}'))"
}

# Saves in progress during stop (DEC-174): GLIM (its dump_path) and ros2 bag record (its -o folder) of this Gouda, i.e. writing
# under $data_root. Only the command lines of these matched processes are read (never all processes: secrets, see ntrip_relay).
declare -A last_bytes=()
save_targets() {   # prints "<kind> <folder>" per save in progress
  local p arg prev
  for p in $(pgrep -u "$(id -u)" -f 'glim_rosnode' 2>/dev/null || true); do
    while IFS= read -r -d '' arg; do [[ "$arg" == dump_path:=* ]] && echo "GLIM ${arg#dump_path:=}"; done <"/proc/$p/cmdline" 2>/dev/null
  done
  for p in $(pgrep -u "$(id -u)" -f 'ros2 bag record' 2>/dev/null || true); do
    prev=""; while IFS= read -r -d '' arg; do [[ "$prev" == "-o" ]] && echo "rosbag $arg"; prev="$arg"; done <"/proc/$p/cmdline" 2>/dev/null
  done
}
saving_report() {   # $1: stop start time (s); one line per save: elapsed, size on disk, growth since the last line
  local now kind dir bytes rate line="" any=0
  now=$(date +%s)
  while read -r kind dir; do
    [[ -z "$dir" || "$dir" != "$data_root"/* ]] && continue
    any=1; bytes=$(du -sb "$dir" 2>/dev/null | cut -f1); bytes=${bytes:-0}
    rate=""; [[ -n "${last_bytes[$dir]:-}" ]] && rate=", +$(( (bytes - last_bytes[$dir]) / 1024 )) KB/s"
    last_bytes[$dir]=$bytes
    line+="  $kind saving: $(( bytes / 1048576 )) MB$rate  ($dir)"$'\n'
  done < <(save_targets)
  if (( any )); then printf 'stopping %3d s\n%s' "$(( now - $1 ))" "$line"
  else printf 'stopping %3d s  (waiting for the nodes to exit)\n' "$(( now - $1 ))"; fi
}

case "${1:-}" in
  start)
    if running; then echo "already running (pid $(cat "$pid_file")); see $log_file"; exit 0; fi
    others="$(untracked)"
    if [[ -n "$others" ]]; then   # two Gouda would share the IMU port, the LiDAR and the monitor port (G-DUP-START)
      echo "REFUSED: not started."; report_untracked "$others"; exit 1
    fi
    [[ -f "$ros_setup" ]] || { echo "ROS 2 Jazzy not found: $ros_setup"; exit 1; }
    [[ -f "$workspace/install/setup.bash" ]] || { echo "workspace not built: $workspace/install/setup.bash missing (colcon build --symlink-install --packages-select gouda_interfaces gouda_core)"; exit 1; }
    [[ -d "$params_dir" ]] || { echo "generated parameter directory missing: $params_dir (run design/tools/generate_params.py)"; exit 1; }
    mkdir -p "$run_dir" "$data_root/records" "$data_root/state"
    # shellcheck disable=SC1090
    source "$ros_setup"; source "$workspace/install/setup.bash"
    # Fast DDS profile of every process of this start (PRM-100 / PRM-101, DEC-279, DEC-138): written from the generated settings each time
    python3 -m gouda_core.dds_profile "$params_dir" "$dds_profile" || { echo "REFUSED: not started (Fast DDS profile)"; exit 1; }
    set -m   # job control: the background launch gets its own process group and keeps default SIGINT handling
    rm -f "$url_file"
    launch_args=("params_dir:=$params_dir" "data_root:=$data_root")
    FASTRTPS_DEFAULT_PROFILES_FILE="$dds_profile" ros2 launch gouda_core gouda_core.launch.py "${launch_args[@]}" >"$log_file" 2>&1 &
    launch_pid=$!
    set +m
    echo "$launch_pid" >"$pid_file"   # with job control on, the job's pgid equals the launch pid
    echo "started gouda (pgid $launch_pid); params=$params_dir data=$data_root log=$log_file"
    for _ in $(seq 1 20); do [[ -s "$url_file" ]] && break; running || break; sleep 1; done
    if ! running; then   # the launch exited during start-up: report it instead of claiming success
      echo "FAILED: the launch exited during start-up. Last lines of $log_file:"; tail -20 "$log_file"; rm -f "$pid_file"; exit 1
    fi
    [[ -s "$url_file" ]] && echo "monitor: $(cat "$url_file") (open on this PC desktop; no screen forwarding)" || echo "monitor URL not written yet; see $url_file after start-up"
    ;;
  stop)
    if ! running; then
      echo "not running"; rm -f "$pid_file"
      others="$(untracked)"; [[ -n "$others" ]] && report_untracked "$others"
      exit 0
    fi
    g="$(pgid)"
    kill -INT -- "-$g" 2>/dev/null || true          # launch and every node of the group shut down on SIGINT
    # No time limit and no forced stop (DEC-174): GLIM and ros2 bag record finish saving (mode_manager and the recorder wait
    # for them). Every PRM-77 (1 s) the saves in progress are shown. If it never ends, the human restarts the PC.
    t0=$(date +%s)
    while pgrep -g "$g" >/dev/null 2>&1; do
      sleep 1   # PRM-77
      saving_report "$t0"
    done
    rm -f "$pid_file"; echo "stopped ($(( $(date +%s) - t0 )) s; no process of group $g remains)"
    ;;
  status)
    if running; then echo "running (pgid $(pgid); processes: $(pgrep -g "$(pgid)" | wc -l | tr -d ' '))"; else echo "not running"; fi
    others="$(untracked)"; [[ -n "$others" ]] && report_untracked "$others"
    echo "data_root=$data_root"; echo "params_dir=$params_dir"; echo "log=$log_file"
    [[ -s "$url_file" ]] && echo "monitor=$(cat "$url_file")"
    [[ -f "$data_root/state/previous_mode_record.json" ]] && { echo -n "previous_mode_record: "; cat "$data_root/state/previous_mode_record.json"; }
    ;;
  *) usage; exit 2 ;;
esac
