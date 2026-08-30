cmake_minimum_required(VERSION 3.16)
project(emc270_icr_estimator)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
add_compile_options(-Wall -Wextra -Wpedantic)

find_package(ament_cmake REQUIRED)
find_package(diagnostic_msgs REQUIRED)
find_package(diagnostic_updater REQUIRED)
find_package(Eigen3 REQUIRED NO_MODULE)
find_package(emc270_icr_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(std_srvs REQUIRED)
find_package(tf2 REQUIRED)
find_package(tf2_ros REQUIRED)

add_library(${PROJECT_NAME}_core
  src/icr_core.cpp
  src/imu_lever_arm_validator.cpp
  src/time_offset_estimator.cpp
)
target_include_directories(${PROJECT_NAME}_core PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
target_link_libraries(${PROJECT_NAME}_core PUBLIC Eigen3::Eigen)

add_executable(icr_estimator_node src/icr_estimator_node.cpp)
target_link_libraries(icr_estimator_node ${PROJECT_NAME}_core Eigen3::Eigen)
ament_target_dependencies(icr_estimator_node
  diagnostic_updater
  diagnostic_msgs
  emc270_icr_msgs
  geometry_msgs
  nav_msgs
  rclcpp
  sensor_msgs
  std_srvs
  tf2
  tf2_ros
)

install(TARGETS ${PROJECT_NAME}_core icr_estimator_node
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION lib/${PROJECT_NAME}
)
install(DIRECTORY include/ DESTINATION include)

if(BUILD_TESTING)
  enable_testing()
  foreach(test_name IN ITEMS test_icr_core test_imu_validator)
    add_executable(${test_name} test/${test_name}.cpp)
    target_link_libraries(${test_name} PRIVATE ${PROJECT_NAME}_core Eigen3::Eigen)
    add_test(NAME ${test_name} COMMAND ${test_name})
  endforeach()
endif()

ament_export_include_directories(include)
ament_export_libraries(${PROJECT_NAME}_core)
ament_export_dependencies(Eigen3)
ament_package()
