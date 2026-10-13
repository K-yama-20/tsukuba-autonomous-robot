#include <rclcpp/rclcpp.hpp>

#include <memory>

#include "emc270_joystick_driver/driver_node.hpp"

int main(int argc, char **argv) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<emc270_joystick_driver::DriverNode>());
  rclcpp::shutdown();
  return 0;
}
