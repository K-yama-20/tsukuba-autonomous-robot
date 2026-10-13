#!/usr/bin/env bash
# Install the sensor drivers specified by the human (DEC-080) into the ROS 2 workspace and build them.
#   ND-14 hesai_ros_driver        https://github.com/HesaiTechnology/HesaiLidar_ROS_2.0      (verified commit e7e112f, SDK 9d5dc4f)
#   ND-15 adi_imu_tr_driver_ros2  https://github.com/technoroad/ADI_IMU_TR_Driver_ROS2       (verified commit 742b7ba)
# The upstream sources are NOT modified (DEC-075: OSS is not changed; the legacy scripts/gouda_apply_*_patch.sh are not applied).
# An existing checkout is never overwritten or reset: its commit and local changes are only reported.
# Usage (on the vehicle PC / Ubuntu):  bash gouda_core/tools/install_sensor_drivers.sh 2>&1 | tee <record file>
set -o pipefail   # no -u: /opt/ros/jazzy/setup.bash reads unset variables
WS="${GOUDA_WORKSPACE:-$HOME/gouda_ws}"
HESAI_URL=https://github.com/HesaiTechnology/HesaiLidar_ROS_2.0.git; HESAI_COMMIT=e7e112f0809f0eed5e3c81c55a1a0376474db234
ADI_URL=https://github.com/technoroad/ADI_IMU_TR_Driver_ROS2.git;     ADI_COMMIT=742b7babec7e7a20937d4e8be0df77a771a1294a
echo "== date: $(date -Is) host: $(hostname) ws: $WS"
source /opt/ros/jazzy/setup.bash
mkdir -p "$WS/src"; cd "$WS/src" || exit 1

fetch() {   # dir url commit
  local dir="$1" url="$2" commit="$3"
  if [[ -d "$dir/.git" ]]; then
    echo "== $dir exists (not changed): $(git -C "$dir" rev-parse HEAD) $(git -C "$dir" remote get-url origin)"
    git -C "$dir" status --short | head -20
    git -C "$dir" submodule status 2>/dev/null
    [[ "$(git -C "$dir" rev-parse HEAD)" == "$commit" ]] || echo "   NOTE: differs from the verified commit $commit (keep it; report to the design record)"
  else
    git clone --recursive "$url" "$dir" && git -C "$dir" checkout -q "$commit" && git -C "$dir" submodule update --init --recursive
    echo "== $dir cloned at $(git -C "$dir" rev-parse HEAD)"; git -C "$dir" submodule status
  fi
}
fetch HesaiLidar_ROS_2.0 "$HESAI_URL" "$HESAI_COMMIT"
fetch ADI_IMU_TR_Driver_ROS2 "$ADI_URL" "$ADI_COMMIT"

echo "== rosdep (dependencies only; prints what is missing)"
rosdep install --from-paths HesaiLidar_ROS_2.0 ADI_IMU_TR_Driver_ROS2 --ignore-src -r -y --simulate 2>&1 | tail -10
echo "== build"
cd "$WS" && colcon build --symlink-install --packages-select hesai_ros_driver adi_imu_tr_driver_ros2 --executor sequential 2>&1 | tail -15
source "$WS/install/setup.bash"
echo "== installed"
ros2 pkg executables hesai_ros_driver; ros2 pkg executables adi_imu_tr_driver_ros2
ls "$(ros2 pkg prefix hesai_ros_driver)/share/hesai_ros_driver/config/config.yaml"
echo "== done"
