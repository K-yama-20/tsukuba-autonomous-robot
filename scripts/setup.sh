#!/usr/bin/env bash
set -eo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
default_workspace="$(python3 - "$repo" <<'PYWORKSPACE'
import sys
from pathlib import Path
repo=Path(sys.argv[1]).resolve()
print(repo.parent.parent if repo.name == 'tsukuba-autonomous-robot' and repo.parent.name == 'src' else Path.home()/'gouda_ws')
PYWORKSPACE
)"
workspace="${GOUDA_WORKSPACE:-$default_workspace}"
configure=1
system=1
with_glim=0
with_gazebo=0
for arg in "$@"; do
  case "$arg" in
    --no-configure) configure=0 ;;
    --skip-system) system=0 ;;
    --with-glim) with_glim=1 ;;
    --with-gazebo) with_gazebo=1 ;;
    *) echo "Usage: bash scripts/setup.sh [--no-configure] [--skip-system] [--with-glim] [--with-gazebo]" >&2; exit 2 ;;
  esac
done
. /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 ]] || { echo 'Ubuntu 24.04 required'; exit 1; }
case "$(dpkg --print-architecture)" in amd64|arm64) ;; *) echo 'amd64/arm64 required'; exit 1;; esac
[[ "$EUID" != 0 ]] || { echo 'Run as your normal user (sudo is requested only for system packages).'; exit 1; }
export GOUDA_WORKSPACE="$workspace"
if (( system )); then
  sudo apt-get update
  sudo apt-get install -y ca-certificates curl git locales software-properties-common
  sudo add-apt-repository universe -y
  if [[ ! -f /etc/apt/sources.list.d/ros2.sources && ! -f /etc/apt/sources.list.d/ros2.list ]]; then
    tmp="$(mktemp -d)"
    trap 'rm -rf "$tmp"' EXIT
    version="$(curl -fsSL https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | python3 -c 'import json,sys; print(json.load(sys.stdin)["tag_name"])')"
    curl -fL --retry 3 -o "$tmp/ros.deb" "https://github.com/ros-infrastructure/ros-apt-source/releases/download/$version/ros2-apt-source_${version}.noble_all.deb"
    sudo dpkg -i "$tmp/ros.deb"
  fi
  sudo apt-get update
  sudo apt-get install -y ros-jazzy-desktop ros-dev-tools python3-rosdep python3-vcstool \
    python3-colcon-common-extensions python3-pytest python3-aiohttp python3-yaml \
    ros-jazzy-navigation2 ros-jazzy-nav2-bringup ros-jazzy-slam-toolbox \
    libboost-all-dev libyaml-cpp-dev libpcap-dev network-manager x11-utils \
    linuxptp ethtool \
    gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad gstreamer1.0-libav
  if (( with_glim )); then
    # Official GLIM PPA for Ubuntu 24.04/Jazzy, CPU-only package set.
    key=/usr/share/keyrings/gouda-koide3.gpg
    list=/etc/apt/sources.list.d/gouda-koide3.list
    if ! sudo grep -Rqs 'koide3.github.io/ppa/ubuntu2404' /etc/apt/sources.list.d; then
      curl -fsSL --compressed https://koide3.github.io/ppa/ubuntu2404/KEY.gpg | sudo gpg --dearmor --yes -o "$key"
      printf '%s\n' 'deb [signed-by=/usr/share/keyrings/gouda-koide3.gpg] https://koide3.github.io/ppa/ubuntu2404 ./' | sudo tee "$list" >/dev/null
    fi
    sudo chmod 644 "$key" "$list" 2>/dev/null || true
    sudo apt-get update
    sudo apt-get install -y libiridescence-dev libboost-all-dev libglfw3-dev libmetis-dev \
      libgtsam-points-dev ros-jazzy-glim-ros
  fi
  [[ -f /etc/ros/rosdep/sources.list.d/20-default.list ]] || sudo rosdep init
  rosdep update
fi
source /opt/ros/jazzy/setup.bash
# The old launcher detached child groups; preserve their state before changing source paths.
if ! PYTHONPATH="$repo/scripts${PYTHONPATH:+:$PYTHONPATH}" python3 -c 'import configure_host,sys; sys.exit(1 if configure_host.running_gouda() else 0)'; then
  echo 'Gouda is running or its process state cannot be verified; stop it before setup.' >&2
  exit 1
fi
mkdir -p "$workspace/src"
python3 "$repo/scripts/prepare_sources.py" "$repo" "$workspace"
repo="$workspace/src/tsukuba-autonomous-robot"
# Do not discover the separate historical ICR workspace under Sensors/.
# It has another ADI package with the same name.
packages=("$repo"/gouda_gui "$repo"/gouda_sensors "$repo"/gouda_navigation "$repo"/gouda_vehicle "$repo"/gouda_bringup "$repo"/gouda_camera)
if (( with_gazebo )); then packages+=("$repo"/gouda_sim); fi
external=("$workspace/src/ADI_IMU_TR_Driver_ROS2" "$workspace/src/HesaiLidar_ROS_2.0" "$workspace/src/kiss-icp" "$workspace/src/urg_node2")
if (( system )); then
  if (( with_gazebo )); then sudo apt-get install -y xvfb xauth; fi
  rosdep install --from-paths "${packages[@]}" "${external[@]}" --ignore-src --rosdistro jazzy -y
fi
bash "$repo/scripts/gouda_apply_hesai_patch.sh"
bash "$repo/scripts/gouda_apply_imu_patch.sh"
python3 "$repo/scripts/gouda_apply_imu_clock_patch.py"
# Migrate user settings and maps before changing generated build state.
PYTHONPATH="$repo/gouda_sensors${PYTHONPATH:+:$PYTHONPATH}" python3 "$repo/scripts/configure_host.py" --workspace "$workspace" --defaults
PYTHONPATH="$repo/gouda_sensors${PYTHONPATH:+:$PYTHONPATH}" python3 "$repo/scripts/configure_host.py" \
  --workspace "$workspace" --prepare-build --source "$repo"
cd "$workspace"
# Bound compiler memory on small PCs and the development VM.
export CMAKE_BUILD_PARALLEL_LEVEL="${CMAKE_BUILD_PARALLEL_LEVEL:-2}"
export MAKEFLAGS="${MAKEFLAGS:--j2}"
colcon build --symlink-install --base-paths "${packages[@]}" "${external[@]}" --executor sequential --cmake-args -DCMAKE_BUILD_TYPE=RelWithDebInfo
PYTHONPATH="$repo/gouda_sensors${PYTHONPATH:+:$PYTHONPATH}" python3 "$repo/scripts/configure_host.py" \
  --workspace "$workspace" --record-build --source "$repo"
source "$workspace/install/setup.bash"
if (( configure )); then python3 "$repo/scripts/configure_host.py" --workspace "$workspace"; fi
printf '\nセットアップ完了。画面のみ: bash %q/scripts/gouda.sh view\n' "$repo"
printf '実機観測: bash %q/scripts/gouda.sh observe\n' "$repo"
