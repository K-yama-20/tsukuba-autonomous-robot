cmake_minimum_required(VERSION 3.8)
project(emc270_joystick_msgs)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/NormalizedCommand.msg"
  "msg/JoystickStatus.msg"
  "msg/CalibrationSample.msg"
  "msg/ControllerEvent.msg"
  "srv/SetPreset.srv"
  DEPENDENCIES std_msgs
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
