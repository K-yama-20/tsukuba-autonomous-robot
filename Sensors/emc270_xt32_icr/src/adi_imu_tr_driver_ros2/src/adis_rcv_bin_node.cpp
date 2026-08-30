/*
The MIT License (MIT)
Copyright (c) 2019 Techno Road Inc.
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
*/

#include <memory>
#include <rclcpp/rclcpp.hpp>

#include "adis_rcv_bin_node.hpp"

int main(int argc, char** argv)
{
  rclcpp::init(argc, argv);

  rclcpp::NodeOptions options;
  auto imu_node = std::make_shared<ImuNodeRcvBin>(options);

  // The constructor blocks until the device opens. If shutdown was requested
  // during that wait (e.g. Ctrl-C with no IMU connected), spinning would try
  // to build an executor on an invalid context and throw. Guard and catch so
  // the process exits cleanly instead of aborting.
  try {
    if (rclcpp::ok()) {
      rclcpp::spin(imu_node);
    }
  } catch (const rclcpp::exceptions::RCLError& e) {
    RCLCPP_WARN(imu_node->get_logger(), "Shutdown during startup: %s", e.what());
  }
  rclcpp::shutdown();
  return 0;
}
