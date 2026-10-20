#!/usr/bin/env bash
# setup.sh: set up this PC for Gouda (Ubuntu 24.04, ROS 2 Jazzy). Run it as your normal user; sudo is asked only when
# something is missing. Safe to run again: what is already in place is left as it is. update.sh runs it after a pull.
#
#   bash setup.sh
#
#   1. system packages: ROS 2 Jazzy (desktop, as on the verified VM), build tools, Python modules, GLIM 1.2.2 from the
#      GLIM PPA (the version the design was checked with: DEC-062, IFD-35), the Nav2 packages Gouda uses (DEC-121, DEC-122)
#      and the GNSS driver septentrio_gnss_driver (ND-19, DEC-123) from the ROS 2 apt repository, and rtklib (Ubuntu universe)
#      for str2str, the NTRIP relay the sensor supervisor starts (DEC-139 option B1, DEC-151 step 4)
#   2. the sensor drivers at the commits in third_party/drivers.repos, unmodified (DEC-075). A clean checkout is moved to
#      the pinned commit; a checkout with local changes or another origin is never touched (setup stops and says why)
#   3. rosdep for gouda_core, gouda_interfaces and the drivers
#   4. the dialout group (serial ports: IMU, ESP32)
#   5. colcon build --symlink-install of gouda_interfaces, gouda_core and the two drivers
#   6. the LiDAR LAN (the PC address PRM-51 from design/generated/params; it offers to add a NetworkManager profile on a
#      terminal) and time synchronisation (checked and reported)
# The robot is started only by `bash gouda.sh start`.
set -eo pipefail   # no -u: /opt/ros/jazzy/setup.bash reads unset variables
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
src_dir="$(dirname "$repo")"
workspace="$(dirname "$src_dir")"
pins="$repo/third_party/drivers.repos"
params_index="$repo/design/generated/params/index.json"
glim_version="1.2.2-0noble"                                   # DEC-062 / IFD-35 confirmed_installed_version
lidar_prefix=24                                               # the XT-32's own mask is 255.255.255.0 (Pandar Console, 2026-10-13)
packages=(gouda_interfaces gouda_core hesai_ros_driver adi_imu_tr_driver_ros2)
say() { printf '\n== %s\n' "$*"; }
stop() { printf '\nSTOPPED: %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- 0. where and what
. /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 ]] || stop "Ubuntu 24.04 is required (this is $PRETTY_NAME)"
case "$(dpkg --print-architecture)" in amd64|arm64) ;; *) stop "amd64 or arm64 is required";; esac
[[ "$EUID" != 0 ]] || stop "run as your normal user, not root (sudo is asked only when needed)"
[[ "$(basename "$src_dir")" == src ]] || stop "the repository must be at <workspace>/src/$(basename "$repo") (it is at $repo). Clone it into ~/gouda_ws/src (README)"
if [[ -f "$workspace/gouda_data/run/gouda_core.pid" ]] && pgrep -g "$(cat "$workspace/gouda_data/run/gouda_core.pid")" >/dev/null 2>&1; then
  stop "Gouda is running. Stop it first: bash $repo/gouda.sh stop"
fi
echo "workspace: $workspace"

# ---------------------------------------------------------------- 1. system packages
installed() { dpkg-query -W -f='${Status}' "$1" 2>/dev/null | grep -q 'install ok installed'; }
version_of() { dpkg-query -W -f='${Version}' "$1" 2>/dev/null || true; }
say "system packages"
if [[ ! -f /etc/apt/sources.list.d/ros2.sources && ! -f /etc/apt/sources.list.d/ros2.list ]]; then
  echo "adding the ROS 2 apt source (ros2-apt-source)"
  sudo apt-get update
  sudo apt-get install -y ca-certificates curl software-properties-common
  sudo add-apt-repository -y universe
  tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
  ros_apt="$(curl -fsSL https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | python3 -c 'import json,sys; print(json.load(sys.stdin)["tag_name"])')"
  curl -fL --retry 3 -o "$tmp/ros2-apt-source.deb" "https://github.com/ros-infrastructure/ros-apt-source/releases/download/$ros_apt/ros2-apt-source_${ros_apt}.${VERSION_CODENAME}_all.deb"
  sudo dpkg -i "$tmp/ros2-apt-source.deb"
fi
if ! grep -Rqs 'koide3.github.io/ppa/ubuntu2404' /etc/apt/sources.list.d; then
  echo "adding the GLIM PPA (https://koide3.github.io/ppa/ubuntu2404)"
  installed curl || { sudo apt-get update; sudo apt-get install -y curl; }
  curl -fsSL --compressed https://koide3.github.io/ppa/ubuntu2404/KEY.gpg | sudo gpg --dearmor --yes -o /usr/share/keyrings/gouda-koide3.gpg
  echo 'deb [signed-by=/usr/share/keyrings/gouda-koide3.gpg] https://koide3.github.io/ppa/ubuntu2404 ./' | sudo tee /etc/apt/sources.list.d/gouda-koide3.list >/dev/null
fi
wanted=(git curl ros-jazzy-desktop ros-dev-tools python3-colcon-common-extensions python3-rosdep python3-vcstool
        python3-numpy python3-serial python3-yaml libpcap-dev libyaml-cpp-dev libboost-all-dev network-manager iproute2 udev
        # Nav2 (ND-10, DEC-121 / DEC-122): bringup (the parameter template), the servers and the chosen plugins
        ros-jazzy-nav2-bringup ros-jazzy-nav2-lifecycle-manager ros-jazzy-nav2-bt-navigator ros-jazzy-nav2-planner ros-jazzy-nav2-navfn-planner
        ros-jazzy-nav2-controller ros-jazzy-nav2-regulated-pure-pursuit-controller ros-jazzy-nav2-behaviors ros-jazzy-nav2-smoother
        ros-jazzy-nav2-velocity-smoother ros-jazzy-nav2-costmap-2d ros-jazzy-nav2-map-server
        # GNSS driver (ND-19, DEC-123) and the NTRIP relay str2str (DEC-139 option B1, DEC-151 step 4)
        ros-jazzy-septentrio-gnss-driver rtklib)
missing=(); for p in "${wanted[@]}"; do installed "$p" || missing+=("$p"); done
for p in ros-jazzy-glim ros-jazzy-glim-ros; do
  v="$(version_of "$p")"
  if [[ -z "$v" ]] || ! installed "$p"; then missing+=("$p=$glim_version")
  elif [[ "$v" != "$glim_version" ]]; then
    stop "$p $v is installed, but the design was checked with $glim_version (DEC-062). Changing the GLIM version is a design decision; it is not done here"
  fi
done
if (( ${#missing[@]} )); then
  echo "installing: ${missing[*]}"
  sudo apt-get update
  sudo apt-get install -y "${missing[@]}"
else
  echo "all present (ROS 2 Jazzy, build tools, Python modules, GLIM $glim_version)"
fi
# shellcheck disable=SC1091
source /opt/ros/jazzy/setup.bash

# ---------------------------------------------------------------- 2. sensor drivers (pinned, unmodified)
say "sensor drivers ($pins)"
mapfile -t pin_lines < <(python3 - "$pins" <<'PY'
import sys, yaml
for name, r in yaml.safe_load(open(sys.argv[1]))['repositories'].items():
    print(name, r['url'], r['version'])
PY
)
for line in "${pin_lines[@]}"; do
  read -r name url commit <<<"$line"; dir="$src_dir/$name"
  if [[ ! -e "$dir" ]]; then
    echo "$name: cloning $url"
    git clone -q "$url" "$dir"
  fi
  [[ -d "$dir/.git" ]] || stop "$dir exists but is not a git checkout; move it away and run setup.sh again"
  origin="$(git -C "$dir" remote get-url origin 2>/dev/null || true)"
  [[ "${origin%.git}" == "${url%.git}" ]] || stop "$dir has origin '$origin', not $url; it is left as it is"
  if [[ -n "$(git -C "$dir" status --porcelain --ignore-submodules=none)" ]]; then
    git -C "$dir" status --short | head -10
    stop "$dir has local changes (the drivers are used unmodified: DEC-075; the legacy scripts/setup.sh patched them). Keep them aside with: git -C $dir stash --include-untracked ; then run setup.sh again"
  fi
  if [[ "$(git -C "$dir" rev-parse HEAD)" != "$commit" ]]; then
    git -C "$dir" cat-file -e "$commit^{commit}" 2>/dev/null || git -C "$dir" fetch -q origin
    git -C "$dir" -c advice.detachedHead=false checkout -q "$commit"
    echo "$name: moved to $commit"
  fi
  git -C "$dir" submodule update -q --init --recursive
  echo "$name: $(git -C "$dir" rev-parse --short HEAD) (pinned); submodules: $(git -C "$dir" submodule status --recursive | awk '{printf "%s %s  ", substr($1,1,7), $2}')"
done

# ---------------------------------------------------------------- 3. rosdep
say "rosdep"
paths=("$repo/gouda_interfaces" "$repo/gouda_core" "$src_dir/HesaiLidar_ROS_2.0" "$src_dir/ADI_IMU_TR_Driver_ROS2")
[[ -f /etc/ros/rosdep/sources.list.d/20-default.list ]] || sudo rosdep init
if ! rosdep check --from-paths "${paths[@]}" --ignore-src --rosdistro jazzy >/dev/null 2>&1; then
  rosdep update --rosdistro jazzy
  rosdep install --from-paths "${paths[@]}" --ignore-src --rosdistro jazzy -y
fi
echo "all system dependencies of ${packages[*]} are installed"

# ---------------------------------------------------------------- 4. serial ports
say "serial ports (dialout)"
relogin=0
if id -nG "$USER" | tr ' ' '\n' | grep -qx dialout; then echo "$USER is in dialout"
else sudo usermod -aG dialout "$USER"; relogin=1; echo "$USER added to dialout (log out and in once)"; fi

# ---------------------------------------------------------------- 5. build
say "build (colcon build --symlink-install: ${packages[*]})"
cd "$workspace"
for d in "$workspace"/install/gouda_core/lib/python3*/site-packages/gouda_core; do
  if [[ -d "$d" && ! -L "$d" ]]; then   # a copy left by a build without --symlink-install would shadow the sources
    echo "removing the old non-symlink build of gouda_core ($d)"; rm -rf "$workspace/build/gouda_core" "$workspace/install/gouda_core"
  fi
done
export CMAKE_BUILD_PARALLEL_LEVEL="${CMAKE_BUILD_PARALLEL_LEVEL:-2}" MAKEFLAGS="${MAKEFLAGS:--j2}"   # small PCs and the VM
colcon build --symlink-install --base-paths "$src_dir" --packages-select "${packages[@]}" --executor sequential   # only src/ is searched (not gouda_data)

# ---------------------------------------------------------------- 6. checks
say "LiDAR LAN"
host_ip="$(python3 -c 'import json,sys; print(next(p["value"] for p in json.load(open(sys.argv[1]))["parameters"] if p["id"] == "PRM-51"))' "$params_index")"
lidar_ip="$(python3 -c 'import json,sys; print(next(p["value"] for p in json.load(open(sys.argv[1]))["parameters"] if p["id"] == "PRM-50"))' "$params_index")"
default_if="$(ip -o route show default 2>/dev/null | awk '{print $5; exit}')"
holder="$(ip -o -4 addr show | awk -v a="$host_ip/" 'index($4, a) == 1 {print $2; exit}')"
# profiles holding the PC address on the interface with the default route break the internet and the LiDAR (seen on the VM)
profiles_with_host=()   # UUIDs (names can repeat)
while IFS=: read -r uuid cname; do
  [[ -n "$uuid" ]] || continue
  addr="$(nmcli -g ipv4.addresses connection show uuid "$uuid" 2>/dev/null || true)"; bound="$(nmcli -g connection.interface-name connection show uuid "$uuid" 2>/dev/null || true)"
  [[ "$addr" == *"$host_ip/"* ]] || continue
  profiles_with_host+=("$uuid")
  if [[ -n "$default_if" && "$bound" == "$default_if" ]]; then
    echo "WARNING: profile '$cname' ($uuid) puts $host_ip on $default_if (the interface with the default route). Remove it if it is not needed: sudo nmcli connection delete uuid $uuid"
  fi
done < <(nmcli -t -f UUID,NAME connection show 2>/dev/null || true)
if [[ -n "$holder" ]]; then
  echo "$host_ip (PRM-51) is on $holder. The XT-32 is expected at $lidar_ip (PRM-50)"
elif (( ${#profiles_with_host[@]} )); then
  echo "a NetworkManager profile with $host_ip exists but is not active (is the LiDAR's USB-LAN connected?): nmcli connection show"
else
  mapfile -t cands < <(nmcli -t -f DEVICE,TYPE device status 2>/dev/null | awk -F: -v d="$default_if" '$2 == "ethernet" && $1 != d {print $1}')
  echo "no interface or profile holds $host_ip (PRM-51) yet. Wired interfaces without the default route: ${cands[*]:-none}"
  added=0
  if [[ -t 0 && ${#cands[@]} -gt 0 ]]; then
    for i in "${!cands[@]}"; do echo "  [$((i + 1))] ${cands[$i]}"; done
    read -r -p "the LiDAR's wired LAN [number, Enter to skip]: " choice
    if [[ "$choice" =~ ^[0-9]+$ && "$choice" -ge 1 && "$choice" -le ${#cands[@]} ]]; then
      ifname="${cands[$((choice - 1))]}"
      sudo nmcli connection add type ethernet con-name "gouda-lidar-$ifname" ifname "$ifname" ipv4.method manual \
        ipv4.addresses "$host_ip/$lidar_prefix" ipv4.never-default yes ipv6.method disabled connection.autoconnect yes
      sudo nmcli connection up "gouda-lidar-$ifname" || echo "the profile is added; it becomes active when the cable is connected"
      added=1
    fi
  fi
  (( added )) || echo "to add it later: sudo nmcli connection add type ethernet con-name gouda-lidar-<IF> ifname <IF> ipv4.method manual ipv4.addresses $host_ip/$lidar_prefix ipv4.never-default yes ipv6.method disabled"
fi

say "IMU"
imu_dev="$(python3 -c 'import json,sys; print(next(p["value"] for p in json.load(open(sys.argv[1]))["parameters"] if p["id"] == "PRM-54"))' "$params_index")"
if [[ -e "$imu_dev" ]]; then echo "$imu_dev (PRM-54) is present"; else echo "$imu_dev (PRM-54) is not connected now (the sensor supervisor waits for it)"; fi

say "time synchronisation"
if [[ "$(timedatectl show -p NTP --value 2>/dev/null)" == yes ]]; then echo "NTP is on (synchronised: $(timedatectl show -p NTPSynchronized --value 2>/dev/null))"
else echo "NTP is off. The clock of the VM jumped on 2026-10-13/14. To turn it on: sudo timedatectl set-ntp true"; fi

say "done"
echo "GLIM: $(version_of ros-jazzy-glim-ros)   drivers: pinned   build: $workspace/install"
(( relogin )) && echo "log out and in once (dialout), then start."
echo "start: bash $repo/gouda.sh start   (it prints the monitor URL)"
