#!/usr/bin/env bash
set -eo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
workspace="${GOUDA_WORKSPACE:-$HOME/gouda_ws}"
source /opt/ros/jazzy/setup.bash
source "$workspace/install/setup.bash"
python3 -m pytest -q "$repo/gouda_sensors/test" "$repo/gouda_navigation/test" "$repo/gouda_vehicle/test" "$repo/gouda_gui/test" "$repo/gouda_camera/test" "$repo/tests"
mkdir -p "$workspace/build/gouda_core"
g++ -std=c++17 -Wall -Wextra -Werror -I "$repo/firmware/gouda_esp32/include" "$repo/firmware/gouda_esp32/test/core_test.cpp" -o "$workspace/build/gouda_core/core_test"
"$workspace/build/gouda_core/core_test"
