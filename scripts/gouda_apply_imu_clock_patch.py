#!/usr/bin/env python3
"""Apply MCU-to-host measurement timestamp support to the external ADI driver."""
from pathlib import Path
import os
import sys

REPO = Path(__file__).resolve().parents[1]
WORKSPACE = Path(os.environ.get('GOUDA_WORKSPACE', str(Path.home() / 'gouda_ws')))
ROOT = Path(os.environ.get('IMU_DRIVER_ROOT', str(WORKSPACE / 'src/ADI_IMU_TR_Driver_ROS2')))
NODE = ROOT / 'src/adis_rcv_bin_node.hpp'
CMAKE = ROOT / 'CMakeLists.txt'
BACKUP = ROOT / '.imu_clock_patch_backup'
BACKUP_NODE = BACKUP / 'adis_rcv_bin_node.hpp.orig'
BACKUP_CMAKE = BACKUP / 'CMakeLists.txt.orig'
if not NODE.is_file() or not CMAKE.is_file():
    raise SystemExit(f'Runtime driver source not found under {ROOT}')
current_node, current_cmake = NODE.read_text(), CMAKE.read_text()
if BACKUP_NODE.exists() or BACKUP_CMAKE.exists():
    if not (BACKUP_NODE.is_file() and BACKUP_CMAKE.is_file()):
        raise SystemExit('Incomplete backup exists; refusing to continue')
    node, cmake = BACKUP_NODE.read_text(), BACKUP_CMAKE.read_text()
else:
    node, cmake = current_node, current_cmake

replacements = [
('#include <sensor_msgs/msg/imu.hpp>', '#include <sensor_msgs/msg/imu.hpp>\n#include <sensor_msgs/msg/time_reference.hpp>\n#include <std_msgs/msg/string.hpp>\n#include <sstream>\n#include <iomanip>\n#include <limits>\n#include <cmath>\n#include <cstdint>\n#include <adi_imu_tr_driver_ros2/affine_clock_mapper.hpp>'),
('    imu_data_pub_ = this->create_publisher<sensor_msgs::msg::Imu>("imu/data_raw", 1);', '    imu_data_pub_ = this->create_publisher<sensor_msgs::msg::Imu>("imu/data_raw", 1);\n    clock_status_pub_ = this->create_publisher<std_msgs::msg::String>("imu/clock_status", 10);\n    time_reference_pub_ = this->create_publisher<sensor_msgs::msg::TimeReference>("imu/time_reference", 10);'),
('  rclcpp::Publisher<sensor_msgs::msg::Imu>::SharedPtr imu_data_pub_;', '  rclcpp::Publisher<sensor_msgs::msg::Imu>::SharedPtr imu_data_pub_;\n  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr clock_status_pub_;\n  rclcpp::Publisher<sensor_msgs::msg::TimeReference>::SharedPtr time_reference_pub_;\n  adi_imu_tr_driver_ros2::AffineClockMapper clock_mapper_;\n  bool have_pps_low_{false};\n  bool last_pps_level_{false};\n  bool have_last_imu_counter_{false};\n  std::uint16_t last_imu_counter_{0};\n  std::uint64_t last_mcu_time_us_{0};'),
('    data->header.frame_id = frame_id_;\n    data->header.stamp = this->now();', r'''    const auto receive_ros = this->now();
    const auto steady_now = std::chrono::steady_clock::now();
    const auto steady_ns = static_cast<std::uint64_t>(
        std::chrono::duration_cast<std::chrono::nanoseconds>(steady_now.time_since_epoch()).count());
    const auto& telemetry = imu_.GetTelemetry();
    // Firmware repeats packet data between DR events. Fit only new conversions; reset on MCU restart.
    if (have_last_imu_counter_ && telemetry.timestamp >= last_mcu_time_us_ &&
        telemetry.imu_counter == last_imu_counter_) return;
    if (have_last_imu_counter_ && telemetry.timestamp < last_mcu_time_us_) {
      clock_mapper_.Reset();
      have_pps_low_ = false;
      last_pps_level_ = false;
    }
    have_last_imu_counter_ = true;
    last_imu_counter_ = telemetry.imu_counter;
    last_mcu_time_us_ = telemetry.timestamp;
    const bool pps_level = (telemetry.in0_port & 0x01U) != 0;
    if (!pps_level) have_pps_low_ = true;
    const bool pps_edge = have_pps_low_ && !last_pps_level_ && pps_level;
    last_pps_level_ = pps_level;
    const auto estimate = clock_mapper_.AddSample(telemetry.timestamp,
        receive_ros.nanoseconds(), steady_ns, pps_edge);
    const bool mapped = estimate.state != adi_imu_tr_driver_ros2::ClockState::kUnlocked;
    const auto sample_stamp = mapped ? rclcpp::Time(estimate.ros_time_ns, this->get_clock()->get_clock_type()) : receive_ros;
    std::ostringstream status_json;
    status_json << std::setprecision(17)
                << R"json({"state":")json" << (mapped ? "host_mapped" : "unlocked")
                << R"json(","measurement_stamp":)json" << (sample_stamp.nanoseconds() * 1.0e-9)
                << R"json(,"receive_stamp":)json" << (receive_ros.nanoseconds() * 1.0e-9)
                << R"json(,"residual_ms":)json";
    if (std::isfinite(estimate.residual_ms)) status_json << estimate.residual_ms;
    else status_json << "null";
    status_json << R"json(,"mcu_time_us":)json" << telemetry.timestamp
                << R"json(,"hardware_synchronized":false)json"
                << R"json(,"timestamp_basis":"mcu_data_ready_acquisition")json"
                << R"json(,"usb_offset_bias_unresolved":true)json"
                << R"json(,"pps_edge_observed":)json" << (pps_edge ? "true" : "false") << "}";
    std_msgs::msg::String status_msg;
    status_msg.data = status_json.str();
    clock_status_pub_->publish(status_msg);
    sensor_msgs::msg::TimeReference time_reference;
    time_reference.header.stamp = receive_ros;
    time_reference.time_ref = sample_stamp;
    time_reference.source = mapped
        ? "adis_mcu_affine_host_mapped;mcu_data_ready_acquisition;hardware_synchronized=false;usb_offset_bias_unresolved=true"
        : "adis_mcu_clock_unlocked;measurement_time_not_yet_usable";
    time_reference_pub_->publish(time_reference);
    // Do not feed receipt-time stamps into GLIM while the fit is unlocked.
    if (!mapped) return;
    data->header.frame_id = frame_id_;
    data->header.stamp = sample_stamp;'''),
]
for old, new in replacements:
    if node.count(old) != 1:
        raise SystemExit('Expected runtime source anchor not found: ' + old[:100])
    node = node.replace(old, new, 1)
cpp_target = '"' + '$' + '{cpp_typesupport_target}' + '"'
old = 'target_link_libraries(adis_rcv_bin_node ' + cpp_target + ' adis_rcv_bin)'
new = ('add_library(affine_clock_mapper STATIC src/affine_clock_mapper.cpp)\n'
       'target_include_directories(affine_clock_mapper PUBLIC include)\n'
       'target_link_libraries(adis_rcv_bin_node ' + cpp_target + ' adis_rcv_bin affine_clock_mapper)')
if old not in cmake:
    raise SystemExit('Expected CMake target link anchor not found')
cmake = cmake.replace(old, new, 1)
test_anchor = '      adis_rcv_bin\n    )'
if test_anchor not in cmake:
    raise SystemExit('Expected test target link anchor not found')
cmake = cmake.replace(test_anchor, '      adis_rcv_bin\n      affine_clock_mapper\n    )', 1)
include_anchor = 'include_directories(\n  lib/include'
if include_anchor not in cmake:
    raise SystemExit('Expected CMake include anchor not found')
cmake = cmake.replace(include_anchor, 'include_directories(\n  include\n  lib/include', 1)
source = REPO / 'Sensors/emc270_xt32_icr/src/adi_imu_tr_driver_ros2'
header = source / 'include/adi_imu_tr_driver_ros2/affine_clock_mapper.hpp'
impl = source / 'src/affine_clock_mapper.cpp'
if not header.is_file() or not impl.is_file():
    raise SystemExit('Reviewed affine clock mapper sources are missing from repository')
mapper_include = ROOT / 'include/adi_imu_tr_driver_ros2'
mapper_header = mapper_include / 'affine_clock_mapper.hpp'
mapper_impl = ROOT / 'src/affine_clock_mapper.cpp'
if BACKUP_NODE.exists():
    # Accept only the exact reviewed reconnect overlay; preserve the clock backup contract.
    from gouda_apply_imu_reconnect_patch import transform, changes
    reconnect_node = transform(node, changes()['src/adis_rcv_bin_node.hpp'])
    exact = (current_node in (node, reconnect_node) and current_cmake == cmake and
             mapper_header.is_file() and mapper_header.read_text() == header.read_text() and
             mapper_impl.is_file() and mapper_impl.read_text() == impl.read_text())
    if exact:
        print('Exact adapter already applied; source and mapper match generated content.')
        sys.exit(0)
    raise SystemExit('Backup exists but runtime files differ from exact expected output')
if BACKUP.exists():
    raise SystemExit('Backup directory exists without original source; refusing to continue')
if mapper_header.exists() or mapper_impl.exists():
    raise SystemExit('Mapper destination already exists; refusing to overwrite user files')
BACKUP.mkdir(parents=True, exist_ok=False)
BACKUP_NODE.write_text(current_node)
BACKUP_CMAKE.write_text(current_cmake)
mapper_include.mkdir(parents=True, exist_ok=True)
mapper_header.write_text(header.read_text())
mapper_impl.write_text(impl.read_text())
NODE.write_text(node)
CMAKE.write_text(cmake)
print('Applied adapter: /imu/clock_status and /imu/time_reference; IMU output waits for host mapping lock.')
