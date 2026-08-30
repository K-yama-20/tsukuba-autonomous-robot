cmake_minimum_required(VERSION 3.16)
project(emc270_xt32_icr_standalone LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Eigen3 REQUIRED NO_MODULE)

add_library(icr_core
  src/emc270_icr_estimator/src/icr_core.cpp
  src/emc270_icr_estimator/src/imu_lever_arm_validator.cpp
  src/emc270_icr_estimator/src/time_offset_estimator.cpp
  src/adi_imu_tr_driver_ros2/src/affine_clock_mapper.cpp
)
target_include_directories(icr_core PUBLIC
  src/emc270_icr_estimator/include
  src/adi_imu_tr_driver_ros2/include
)
target_link_libraries(icr_core PUBLIC Eigen3::Eigen)
target_compile_options(icr_core PRIVATE -Wall -Wextra -Wpedantic)

enable_testing()
foreach(test_name IN ITEMS test_icr_core test_imu_validator test_time_sync test_counter_tracker)
  add_executable(${test_name} src/emc270_icr_estimator/test/${test_name}.cpp)
  target_link_libraries(${test_name} PRIVATE icr_core Eigen3::Eigen)
  target_compile_options(${test_name} PRIVATE -Wall -Wextra -Wpedantic)
  add_test(NAME ${test_name} COMMAND ${test_name})
endforeach()

find_package(Python3 COMPONENTS Interpreter REQUIRED)
add_test(
  NAME test_repeatability_report
  COMMAND ${Python3_EXECUTABLE}
          ${CMAKE_CURRENT_SOURCE_DIR}/src/emc270_icr_bringup/test/test_repeatability_report.py
)
add_test(
  NAME test_compare_icr_csv
  COMMAND ${Python3_EXECUTABLE}
          ${CMAKE_CURRENT_SOURCE_DIR}/src/emc270_icr_bringup/test/test_compare_icr_csv.py
)
add_test(
  NAME test_record_validation
  COMMAND ${Python3_EXECUTABLE}
          ${CMAKE_CURRENT_SOURCE_DIR}/src/emc270_icr_bringup/test/test_record_validation.py
)
