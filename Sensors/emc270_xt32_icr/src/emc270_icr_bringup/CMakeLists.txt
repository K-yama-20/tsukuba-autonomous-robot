cmake_minimum_required(VERSION 3.16)
project(emc270_icr_bringup)

find_package(ament_cmake REQUIRED)

install(DIRECTORY config launch
  DESTINATION share/${PROJECT_NAME}
  PATTERN "__pycache__" EXCLUDE
  PATTERN "*.pyc" EXCLUDE
)
install(PROGRAMS
  scripts/check_runtime_acceptance.py
  scripts/compare_icr_csv.py
  scripts/export_icr_csv.py
  scripts/generate_repeatability_report.py
  scripts/record_trial.py
  DESTINATION lib/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_repeatability_report
    test/test_repeatability_report.py
  )
  ament_add_pytest_test(test_compare_icr_csv
    test/test_compare_icr_csv.py
  )
  ament_add_pytest_test(test_record_validation
    test/test_record_validation.py
  )
endif()

ament_package()
