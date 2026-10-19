#!/usr/bin/env bash
# TEST STACK (gouda_core/test only; not a way to run the robot). The robot is started only by `bash gouda.sh start`.
#
#   bash gouda_core/test/stack.sh start <data_root>   start the same launch as gouda.sh, isolated for software tests
#   bash gouda_core/test/stack.sh stop  <data_root>
#
# Isolation, so that a test never disturbs a running robot session or the real devices:
#   - its own ROS domain (ROS_DOMAIN_ID, default 77) and its own data_root;
#   - a copy of design/generated/params WITHOUT the sensor-driver files (hesai_ros_driver*, adi_imu_driver*, septentrio_gnss_driver*): the sensor
#     supervisor then records "driver_not_started" and never opens the LiDAR or the IMU (restarting the IMU driver would freeze
#     the IMU, docs/sensor_supervision.md);
#   - the monitor port is chosen by the OS (the robot's port 8080 may be in use);
#   - the software trial values (<node>.trial.yaml) are loaded (launch argument trial:=true), which gouda.sh never does;
#   - Fast DDS uses fastdds_test_stack.xml (larger shared-memory segment: ~2 MB point clouds are dropped inside the VM with the
#     default, G-DDS). The robot's DDS settings are unchanged (DEC-116).
set -o pipefail   # no -u: ROS setup.bash reads unset variables
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; repo="$(cd "$here/../.." && pwd)"; ws="$(cd "$repo/../.." && pwd)"
cmd="${1:-}"; root="${2:-}"
[[ -n "$cmd" && -n "$root" ]] || { sed -n '2,6p' "$0"; exit 2; }
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-77}"
export FASTRTPS_DEFAULT_PROFILES_FILE="$here/fastdds_test_stack.xml"
pid_file="$root/run/stack.pid"
running() { [[ -f "$pid_file" ]] && pgrep -g "$(cat "$pid_file")" >/dev/null 2>&1; }
case "$cmd" in
  start)
    running && { echo "test stack already running in $root"; exit 0; }
    mkdir -p "$root/run" "$root/params"
    rm -f "$root/params"/*; cp "$repo/design/generated/params/"* "$root/params/"; rm -f "$root/params"/hesai_ros_driver* "$root/params"/adi_imu_driver* "$root/params"/septentrio_gnss_driver*
    # the robot's monitor port (PRM-26) may be in use by a running session: the test copy lets the OS choose a free port
    sed -i -E 's/^(\s*monitor_port:).*/\1 0  # test copy: OS-chosen port/' "$root/params/gouda_monitor.yaml"
    source /opt/ros/jazzy/setup.bash; source "$ws/install/setup.bash"
    set -m
    ros2 launch gouda_core gouda_core.launch.py "params_dir:=$root/params" "data_root:=$root" trial:=true >"$root/run/stack.launch.log" 2>&1 &
    echo $! >"$pid_file"; set +m
    for _ in $(seq 1 20); do [[ -s "$root/run/monitor.url" ]] && break; running || break; sleep 1; done
    running || { echo "test stack FAILED; see $root/run/stack.launch.log"; tail -20 "$root/run/stack.launch.log"; exit 1; }
    echo "test stack started (ROS_DOMAIN_ID=$ROS_DOMAIN_ID, data_root=$root, monitor $(cat "$root/run/monitor.url" 2>/dev/null))"
    ;;
  stop)
    running || { echo "test stack not running"; exit 0; }
    g="$(cat "$pid_file")"; kill -INT -- "-$g" 2>/dev/null
    for _ in $(seq 1 30); do pgrep -g "$g" >/dev/null 2>&1 || break; sleep 1; done
    pgrep -g "$g" >/dev/null 2>&1 && { kill -TERM -- "-$g" 2>/dev/null; sleep 5; kill -KILL -- "-$g" 2>/dev/null; }
    rm -f "$pid_file"; echo "test stack stopped"
    ;;
  *) sed -n '2,6p' "$0"; exit 2 ;;
esac
