cmake_minimum_required(VERSION 3.16)
project(emc270_joystick_driver)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(ament_cmake REQUIRED)
find_package(diagnostic_msgs REQUIRED)
find_package(emc270_joystick_msgs REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_srvs REQUIRED)

get_filename_component(EMC270_REPOSITORY_ROOT
  "${CMAKE_CURRENT_SOURCE_DIR}/../../.." ABSOLUTE)

add_library(emc270_wire_core
  ${EMC270_REPOSITORY_ROOT}/common/src/calibration.cpp
  ${EMC270_REPOSITORY_ROOT}/common/src/control.cpp
  ${EMC270_REPOSITORY_ROOT}/common/src/messages.cpp
  ${EMC270_REPOSITORY_ROOT}/common/src/model.cpp
  ${EMC270_REPOSITORY_ROOT}/common/src/protocol.cpp
)
target_include_directories(emc270_wire_core PUBLIC
  ${EMC270_REPOSITORY_ROOT}/common/include)
target_compile_options(emc270_wire_core PRIVATE -Wall -Wextra -Wpedantic)

add_executable(emc270_joystick_driver_node
  src/driver_node.cpp
  src/main.cpp
  src/serial_port.cpp
)
target_include_directories(emc270_joystick_driver_node PRIVATE include)
target_link_libraries(emc270_joystick_driver_node emc270_wire_core)
target_compile_options(emc270_joystick_driver_node PRIVATE
  -Wall -Wextra -Wpedantic)
ament_target_dependencies(emc270_joystick_driver_node
  diagnostic_msgs
  emc270_joystick_msgs
  rclcpp
  std_srvs
)

install(TARGETS emc270_joystick_driver_node
  DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY config launch
  DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
