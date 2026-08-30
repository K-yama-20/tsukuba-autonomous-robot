cmake_minimum_required(VERSION 3.28.3)

project(adi_imu_tr_driver_ros2)


# The telemetry and clock-mapping extension uses C++17.
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(diagnostic_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(std_srvs REQUIRED)
find_package(tf2_msgs REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)
find_package(diagnostic_updater REQUIRED)
find_package(emc270_icr_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "srv/SimpleCmd.srv"
)

include_directories(
  include
  lib/include
  )

add_library(affine_clock_mapper STATIC
  src/affine_clock_mapper.cpp
)
target_include_directories(affine_clock_mapper PUBLIC include)

rosidl_get_typesupport_target(cpp_typesupport_target "${PROJECT_NAME}" "rosidl_typesupport_cpp")

### CSV node (existing)
add_subdirectory(lib)
add_executable(adis_rcv_csv_node
  src/adis_rcv_csv_node.cpp
  )
target_link_libraries(adis_rcv_csv_node "${cpp_typesupport_target}")
ament_target_dependencies(adis_rcv_csv_node
  "rclcpp"
  "sensor_msgs"
  "tf2_ros"
  "tf2_geometry_msgs"
  "diagnostic_updater"
  )
target_link_libraries(adis_rcv_csv_node adis_rcv_csv)

### Binary node (new)
add_executable(adis_rcv_bin_node
  src/adis_rcv_bin_node.cpp
  )
target_link_libraries(adis_rcv_bin_node
  "${cpp_typesupport_target}"
  adis_rcv_bin
  affine_clock_mapper
)
ament_target_dependencies(adis_rcv_bin_node
  "geometry_msgs"
  "diagnostic_msgs"
  "rclcpp"
  "sensor_msgs"
  "std_srvs"
  "tf2_msgs"
  "tf2_ros"
  "tf2_geometry_msgs"
  "diagnostic_updater"
  "emc270_icr_msgs"
  )

install(DIRECTORY
  launch rviz urdf
  DESTINATION share/${PROJECT_NAME}/
  PATTERN "__pycache__" EXCLUDE
  PATTERN "*.pyc" EXCLUDE
  )

install(TARGETS
  adis_rcv_csv_node
  adis_rcv_bin_node
  DESTINATION lib/${PROJECT_NAME}
  )

install(DIRECTORY include/
  DESTINATION include
)

### Tests (Layer 3: ROS2 node integration)
if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)

  ament_add_gtest(test_adis_rcv_bin_node
    src/test/test_adis_rcv_bin_node.cpp
    TIMEOUT 180
  )
  if(TARGET test_adis_rcv_bin_node)
    target_include_directories(test_adis_rcv_bin_node PRIVATE src)
    target_link_libraries(test_adis_rcv_bin_node
      "${cpp_typesupport_target}"
      adis_rcv_bin
      affine_clock_mapper
    )
    ament_target_dependencies(test_adis_rcv_bin_node
      "geometry_msgs"
      "diagnostic_msgs"
      "rclcpp"
      "sensor_msgs"
      "std_srvs"
      "tf2_msgs"
      "tf2_ros"
      "tf2_geometry_msgs"
      "diagnostic_updater"
      "emc270_icr_msgs"
    )
  endif()

  # Layer 4: parameter / remap / launch-arg coverage (no hardware; PTY fake
  # IMU in src/test/fake_imu.py). Driven via launch_testing.
  find_package(launch_testing_ament_cmake REQUIRED)
  add_launch_test(src/test/test_node_params.py TIMEOUT 300)
  add_launch_test(src/test/test_node_device.py TIMEOUT 120)
  add_launch_test(src/test/test_launch_args.py TIMEOUT 180)
  add_launch_test(src/test/test_node_mpu_error.py TIMEOUT 120)
endif()

ament_package()
