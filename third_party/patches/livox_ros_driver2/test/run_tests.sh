#!/usr/bin/env bash
# Unit tests of the livox_ros_driver2 patches without ROS. The patches are applied in name order, with the same git apply
# as setup.sh, to a copy of the commit pinned in third_party/drivers.repos, and test_lidar_status_info.cpp is built with
# g++ (C++14 and C++17, warnings as errors) and run. Run it again after changing the pin or a patch.
#   bash third_party/patches/livox_ros_driver2/test/run_tests.sh [<livox_ros_driver2 checkout>]
# The checkout defaults to the one setup.sh makes (<workspace>_livox/src/livox_ros_driver2) and is not changed.
set -eo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
patch_dir="$(dirname "$here")"
repo="$(cd "$patch_dir/../../.." && pwd)"
workspace="$(dirname "$(dirname "$repo")")"
checkout="${1:-${workspace}_livox/src/livox_ros_driver2}"
commit="$(awk '/^  livox_ros_driver2:/ {f = 1; next} f && /^  [^ ]/ {f = 0} f && $1 == "version:" {print $2; exit}' \
  "$repo/third_party/drivers.repos")"
[[ -n "$commit" ]] || { echo "no livox_ros_driver2 version in third_party/drivers.repos" >&2; exit 1; }
cxx="${CXX:-g++}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/src"
git -C "$checkout" archive "$commit" | tar -x -C "$tmp/src"
echo "livox_ros_driver2 ${commit:0:7} from $checkout"
while IFS= read -r p; do
  GIT_CEILING_DIRECTORIES="$tmp" git -C "$tmp/src" -c core.autocrlf=false apply --whitespace=nowarn "$p"
  echo "applied $(basename "$p")"
done < <(find "$patch_dir" -maxdepth 1 -type f -name '*.patch' | LC_ALL=C sort)
"$cxx" --version | head -1
for std in c++14 c++17; do
  "$cxx" -std="$std" -Wall -Wextra -Wpedantic -Werror -isystem "$tmp/src/3rdparty" -I "$tmp/src/src" \
    "$here/test_lidar_status_info.cpp" -o "$tmp/test_$std"
  echo "== -std=$std"
  "$tmp/test_$std"
done
