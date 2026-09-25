#!/usr/bin/env bash
set -eo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
workspace="${GOUDA_WORKSPACE:-$HOME/gouda_ws}"
source /opt/ros/jazzy/setup.bash
source "$workspace/install/setup.bash"
python3 -m pytest -q "$repo/gouda_sensors/test" "$repo/gouda_navigation/test" "$repo/gouda_vehicle/test" "$repo/gouda_gui/test" "$repo/gouda_camera/test" "$repo/tests" "$repo/gouda_sim/test"
mkdir -p "$workspace/build/gouda_core"
g++ -std=c++17 -Wall -Wextra -Werror -I "$repo/firmware/gouda_esp32/include" "$repo/firmware/gouda_esp32/test/core_test.cpp" -o "$workspace/build/gouda_core/core_test"
"$workspace/build/gouda_core/core_test"

bash "$repo/firmware/gouda_dualsense_usb/test/run_host_tests.sh"

# Verify real patched ROS driver with a generated PTY device, never physical USB.
ROS_DOMAIN_ID=105 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST python3 "$repo/scripts/imu_clock_smoke.py" \
  --driver-source "$workspace/src/ADI_IMU_TR_Driver_ROS2" \
  --executable "$(ros2 pkg prefix adi_imu_tr_driver_ros2)/lib/adi_imu_tr_driver_ros2/adis_rcv_bin_node"
mapper="$repo/Sensors/emc270_xt32_icr/src/adi_imu_tr_driver_ros2"
g++ -std=c++17 -Wall -Wextra -Werror -I "$mapper/include" \
  "$repo/tests/imu_clock_mapper_test.cpp" "$mapper/src/affine_clock_mapper.cpp" \
  -o "$workspace/build/gouda_core/imu_clock_mapper_test"
"$workspace/build/gouda_core/imu_clock_mapper_test"
