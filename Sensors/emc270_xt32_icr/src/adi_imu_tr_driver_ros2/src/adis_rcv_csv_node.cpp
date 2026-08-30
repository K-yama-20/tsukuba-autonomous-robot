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
#include <tf2_ros/transform_broadcaster.h>

#include <adi_imu_tr_driver_ros2/srv/simple_cmd.hpp>
#include <chrono>
#include <diagnostic_updater/diagnostic_updater.hpp>
#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/imu.hpp>
#include <tf2_geometry_msgs/tf2_geometry_msgs.hpp>  // for use tf2::Quaternion
#include <tf2_msgs/msg/tf_message.hpp>

#include "adis_rcv_csv.h"

using SimpleCmd = adi_imu_tr_driver_ros2::srv::SimpleCmd;

using namespace std::chrono_literals;

class ImuNodeRcvCsv : public rclcpp::Node
{
public:
  explicit ImuNodeRcvCsv(const rclcpp::NodeOptions& op) : Node("adi_rcv_csv_node", op)
  {
    InitParam();

    std::chrono::milliseconds ms((int)(1.0 / rate_ * 1000));

    updater_ = std::make_unique<diagnostic_updater::Updater>(this);
    updater_->add("imu", this, &ImuNodeRcvCsv::Diagnostic);
    // Data publisher
    imu_data_pub_ = this->create_publisher<sensor_msgs::msg::Imu>("/imu/data_raw", 1);
    tf_br_ = this->create_publisher<tf2_msgs::msg::TFMessage>("/tf", 1);
    cmd_server_ = this->create_service<SimpleCmd>(
        "/imu/cmd_srv", std::bind(&ImuNodeRcvCsv::CmdCb, this, std::placeholders::_1,
                                  std::placeholders::_2, std::placeholders::_3));

    Prepare();

    timer_ = this->create_wall_timer(ms, std::bind(&ImuNodeRcvCsv::Spin, this));
  }

  ~ImuNodeRcvCsv()
  {
    RCLCPP_INFO(this->get_logger(), "destructor was called!");
    imu_.Stop();
    imu_.Close();
  }

  void Prepare()
  {
    std::chrono::seconds sec(1);
    rclcpp::Rate r(sec);

    while (rclcpp::ok() && !imu_.Open(device_)) {
      RCLCPP_WARN(this->get_logger(), "Keep trying to open [%s] in 1 second period...",
                  device_.c_str());
      r.sleep();
    }

    while (rclcpp::ok() && !imu_.Prepare()) {
      RCLCPP_WARN(this->get_logger(), "Keep trying to prepare the device in 1 second period...");
      r.sleep();
    }

    updater_->setHardwareID(imu_.GetProductIdStr());
  }

private:
  AdisRcvCsv imu_;
  rclcpp::TimerBase::SharedPtr timer_;
  rclcpp::Publisher<sensor_msgs::msg::Imu>::SharedPtr imu_data_pub_;
  rclcpp::Publisher<tf2_msgs::msg::TFMessage>::SharedPtr tf_br_;
  rclcpp::Service<SimpleCmd>::SharedPtr cmd_server_;
  std::unique_ptr<diagnostic_updater::Updater> updater_;

  std::string device_;
  std::string frame_id_;
  std::string parent_id_;
  double rate_;
  int cant_rcv_cnt_;

  void CmdCb(const std::shared_ptr<rmw_request_id_t> req_header,
             const std::shared_ptr<SimpleCmd::Request> req,
             const std::shared_ptr<SimpleCmd::Response> res)
  {
    (void)req_header;
    res->is_ok = true;

    if (req->cmd == "") {
      res->is_ok = false;
      res->msg = "You are sending an empty command.";
      return;
    }

    std::string args = "";
    for (size_t i = 0; i < req->args.size(); i++) {
      args += "," + req->args[i];
    }

    res->msg = imu_.SendAndRetCmd(req->cmd, args);
  }

  void InitParam()
  {
    // Set default value to variables
    device_ = "/dev/ttyACM0";
    frame_id_ = "imu";
    parent_id_ = "odom";
    rate_ = 100.0;

    // Read parameters
    std::string key = "device";
    if (this->get_parameter(key, device_)) {
      RCLCPP_INFO(this->get_logger(), "%s: %s", key.c_str(), device_.c_str());
    } else {
      RCLCPP_WARN(this->get_logger(), "Could not get param %s. Set default value: %s", key.c_str(),
                  device_.c_str());
    }

    key = "frame_id";
    if (this->get_parameter(key, frame_id_)) {
      RCLCPP_INFO(this->get_logger(), "%s: %s", key.c_str(), frame_id_.c_str());
    } else {
      RCLCPP_WARN(this->get_logger(), "Could not get param %s. Set default value: %s", key.c_str(),
                  frame_id_.c_str());
    }

    key = "parent_id";
    if (this->get_parameter(key, parent_id_)) {
      RCLCPP_INFO(this->get_logger(), "%s: %s", key.c_str(), parent_id_.c_str());
    } else {
      RCLCPP_WARN(this->get_logger(), "Could not get param %s. Set default value: %s", key.c_str(),
                  parent_id_.c_str());
    }

    key = "rate";
    if (this->get_parameter(key, rate_)) {
      RCLCPP_INFO(this->get_logger(), "%s: %.1f", key.c_str(), rate_);
    } else {
      RCLCPP_WARN(this->get_logger(), "Could not get param %s. Set default value: %.1f",
                  key.c_str(), rate_);
    }

    std::string mode_str = "Attitude";
    key = "mode";
    if (this->get_parameter(key, mode_str)) {
      RCLCPP_INFO(this->get_logger(), "%s: %s", key.c_str(), mode_str.c_str());
    } else {
      RCLCPP_WARN(this->get_logger(), "Could not get param %s. Set default value: %s", key.c_str(),
                  mode_str.c_str());
    }
    if (mode_str == "Attitude") {
      imu_.SetMode(AdisRcvCsv::Mode::ATTIUDE);
    } else if (mode_str == "Register") {
      imu_.SetMode(AdisRcvCsv::Mode::REGISTER);
    } else {
      RCLCPP_ERROR(this->get_logger(), "Unknown mode [%s]. We use the default Attitude mode.",
                   mode_str.c_str());
      imu_.SetMode(AdisRcvCsv::Mode::ATTIUDE);
      mode_str = "Attitude";
    }

    cant_rcv_cnt_ = 0;
  }

  void Diagnostic(diagnostic_updater::DiagnosticStatusWrapper& stat)
  {
    if (cant_rcv_cnt_ >= 1) {
      stat.summaryf(diagnostic_msgs::msg::DiagnosticStatus::ERROR,
                    "Data cannot be received for more than 1 second.");
    } else {
      stat.summaryf(diagnostic_msgs::msg::DiagnosticStatus::OK, "OK");
    }
  }

  void PubImuData()
  {
    auto data = std::make_shared<sensor_msgs::msg::Imu>();

    data->header.frame_id = frame_id_;
    data->header.stamp = this->now();

    double acc[3];
    double gyro[3];
    imu_.GetAcc(acc);
    imu_.GetGyro(gyro);

    // Linear acceleration
    data->linear_acceleration.x = acc[0];
    data->linear_acceleration.y = acc[1];
    data->linear_acceleration.z = acc[2];

    // Angular velocity
    data->angular_velocity.x = gyro[0];
    data->angular_velocity.y = gyro[1];
    data->angular_velocity.z = gyro[2];

    // Orientation (not provided)
    data->orientation.x = 0;
    data->orientation.y = 0;
    data->orientation.z = 0;
    data->orientation.w = 1;

    imu_data_pub_->publish(*data);
  }

  void BroadcastImuPose()
  {
    tf2_msgs::msg::TFMessage tf_msg;
    geometry_msgs::msg::TransformStamped tff;

    double ypr[3];
    imu_.GetYPR(ypr);

    tff.transform.translation.x = 0;
    tff.transform.translation.y = 0;
    tff.transform.translation.z = 0;

    tf2::Quaternion q;
    q.setRPY(ypr[2] * DEG2RAD, ypr[1] * DEG2RAD, ypr[0] * DEG2RAD);
    tff.transform.rotation.x = q.getX();
    tff.transform.rotation.y = q.getY();
    tff.transform.rotation.z = q.getZ();
    tff.transform.rotation.w = q.getW();

    tff.child_frame_id = frame_id_;
    tff.header.frame_id = parent_id_;
    tff.header.stamp = this->now();

    tf_msg.transforms.push_back(tff);
    tf_br_->publish(tf_msg);
  }

  void UpdateAndPubRegMode()
  {
    if (imu_.GetState() != AdisRcvCsv::State::RUNNING) return;

    int res = imu_.UpdateRegMode();
    if (res == IMU_OK) {
      PubImuData();
      cant_rcv_cnt_ = 0;
    } else {
      if (res == IMU_ERR_CANT_RCV_DATA) cant_rcv_cnt_++;

      PrintErrorCode(res);
      RCLCPP_ERROR(this->get_logger(), "Cannot update on register mode");
    }
  }

  void UpdateAndPubYprMode()
  {
    if (imu_.GetState() != AdisRcvCsv::State::RUNNING) return;

    int res = imu_.UpdateYprMode();
    if (res == IMU_OK) {
      BroadcastImuPose();
      cant_rcv_cnt_ = 0;
    } else {
      if (res == IMU_ERR_CANT_RCV_DATA) cant_rcv_cnt_++;

      PrintErrorCode(res);
      RCLCPP_ERROR(this->get_logger(), "Cannot update on attiude mode");
    }
  }

  void PrintErrorCode(const int& code)
  {
    switch (code) {
      case IMU_ERR_CANT_RCV_DATA:
        RCLCPP_ERROR(this->get_logger(), "Can not read data from port");
        break;
      case IMU_ERR_COULDNOT_FIND_PACKET:
        RCLCPP_ERROR(this->get_logger(), "Can not find packet");
        break;
      case IMU_ERR_INVALID_DATA:
        RCLCPP_ERROR(this->get_logger(), "Can not invalid data");
        break;
      case IMU_ERR_CHECKSUM:
        RCLCPP_ERROR(this->get_logger(), "Checksum error");
        break;
      default:
        break;
    }
  }

  void Spin()
  {
    switch (imu_.GetMode()) {
      case AdisRcvCsv::Mode::REGISTER:
        UpdateAndPubRegMode();
        break;
      case AdisRcvCsv::Mode::ATTIUDE:
        UpdateAndPubYprMode();
        break;
      default:
        RCLCPP_WARN(this->get_logger(), "Unknown imu mode");
        break;
    }
  }

};  // end of class

int main(int argc, char** argv)
{
  rclcpp::init(argc, argv);

  rclcpp::NodeOptions options;
  options.allow_undeclared_parameters(true);
  options.automatically_declare_parameters_from_overrides(true);

  auto imu_node = std::make_shared<ImuNodeRcvCsv>(options);

  rclcpp::spin(imu_node);
  rclcpp::shutdown();
  return 0;
}
