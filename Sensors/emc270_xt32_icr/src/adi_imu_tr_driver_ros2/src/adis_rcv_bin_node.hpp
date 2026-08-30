/*
The MIT License (MIT)
Copyright (c) 2019 Techno Road Inc.
Copyright (c) 2026 EMC-270 XT32 ICR contributors
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

#ifndef ADIS_RCV_BIN_NODE_HPP_
#define ADIS_RCV_BIN_NODE_HPP_

#include <adi_imu_tr_driver_ros2/srv/simple_cmd.hpp>
#include <diagnostic_msgs/msg/diagnostic_status.hpp>
#include <diagnostic_updater/diagnostic_updater.hpp>
#include <emc270_icr_msgs/msg/imu_telemetry.hpp>
#include <geometry_msgs/msg/transform_stamped.hpp>
#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/imu.hpp>
#include <std_srvs/srv/trigger.hpp>
#include <tf2_msgs/msg/tf_message.hpp>

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <exception>
#include <functional>
#include <limits>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include "adi_imu_tr_driver_ros2/affine_clock_mapper.hpp"
#include "adi_imu_tr_driver_ros2/sample_counter_tracker.hpp"
#include "adis_rcv_bin.h"

class ImuNodeRcvBin : public rclcpp::Node
{
 public:
  using SimpleCmd = adi_imu_tr_driver_ros2::srv::SimpleCmd;
  using ImuTelemetry = emc270_icr_msgs::msg::ImuTelemetry;

  explicit ImuNodeRcvBin(const rclcpp::NodeOptions& options)
  : Node("adi_rcv_bin_node", options), clock_mapper_(ReadClockConfig())
  {
    ReadParameters();

    updater_ = std::make_unique<diagnostic_updater::Updater>(this);
    updater_->add("imu", this, &ImuNodeRcvBin::Diagnostic);

    // Preserve the upstream reliable QoS on the legacy topic. The new
    // full-rate telemetry topic intentionally uses SensorData QoS.
    imu_data_pub_ = create_publisher<sensor_msgs::msg::Imu>("imu/data_raw", rclcpp::QoS(10));
    telemetry_pub_ = create_publisher<ImuTelemetry>(
        "imu/telemetry", rclcpp::SensorDataQoS().keep_last(telemetry_qos_depth_));
    if (publish_tf_) {
      tf_pub_ = create_publisher<tf2_msgs::msg::TFMessage>("tf", 10);
    }
    cmd_server_ = create_service<SimpleCmd>(
        "imu/cmd_srv", std::bind(&ImuNodeRcvBin::CmdCb, this, std::placeholders::_1,
                                  std::placeholders::_2, std::placeholders::_3));
    clock_reset_server_ = create_service<std_srvs::srv::Trigger>(
        "imu/reset_clock_model",
        [this](const std::shared_ptr<std_srvs::srv::Trigger::Request>,
               std::shared_ptr<std_srvs::srv::Trigger::Response> response) {
          std::lock_guard<std::mutex> lock(clock_mutex_);
          clock_mapper_.Reset();
          latest_clock_state_ = adi_imu_tr_driver_ros2::ClockState::kUnlocked;
          latest_clock_residual_ms_ = std::numeric_limits<double>::infinity();
          response->success = true;
          response->message = "MCU-to-ROS affine clock model reset";
        });

    Prepare();
    last_receive_steady_ = std::chrono::steady_clock::now();
    if (rclcpp::ok()) {
      poll_timer_ = create_wall_timer(std::chrono::microseconds(poll_period_us_),
                                      std::bind(&ImuNodeRcvBin::Poll, this));
      diagnostic_timer_ = create_wall_timer(std::chrono::seconds(1), [this]() {
        updater_->force_update();
      });
    }
  }

  ~ImuNodeRcvBin() override
  {
    imu_.StopTelemetry();
    imu_.Close();
  }

 private:
  AdisRcvBin imu_;
  // The upstream node normally uses a single-threaded executor, but hardware
  // tests and downstream compositions may use a multi-threaded executor. Keep
  // command-response reads from racing the high-rate telemetry drain.
  std::mutex serial_mutex_;
  std::mutex clock_mutex_;
  adi_imu_tr_driver_ros2::AffineClockMapper clock_mapper_;
  adi_imu_tr_driver_ros2::SampleCounterTracker counter_tracker_;
  rclcpp::TimerBase::SharedPtr poll_timer_;
  rclcpp::TimerBase::SharedPtr diagnostic_timer_;
  rclcpp::Publisher<sensor_msgs::msg::Imu>::SharedPtr imu_data_pub_;
  rclcpp::Publisher<ImuTelemetry>::SharedPtr telemetry_pub_;
  rclcpp::Publisher<tf2_msgs::msg::TFMessage>::SharedPtr tf_pub_;
  rclcpp::Service<SimpleCmd>::SharedPtr cmd_server_;
  rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr clock_reset_server_;
  std::unique_ptr<diagnostic_updater::Updater> updater_;

  std::string device_;
  std::string frame_id_;
  std::string parent_id_;
  double legacy_rate_hz_{100.0};
  bool publish_tf_{true};
  int poll_period_us_{500};
  int maximum_batch_size_{512};
  int telemetry_qos_depth_{256};
  double orientation_variance_{0.0};
  double angular_velocity_variance_{0.0};
  double linear_acceleration_variance_{0.0};

  bool imu_error_{false};
  bool settings_valid_{false};
  bool gravity_compensated_{false};
  bool last_pps_level_{false};
  bool have_seen_pps_low_{false};
  std::uint64_t published_count_{0};
  std::uint64_t counter_resync_count_{0};
  std::uint64_t last_seen_mcu_time_us_{0};
  bool have_seen_mcu_time_{false};
  rclcpp::Time last_legacy_publish_time_{0, 0, RCL_ROS_TIME};
  std::chrono::steady_clock::time_point last_receive_steady_;
  double latest_clock_residual_ms_{std::numeric_limits<double>::infinity()};
  adi_imu_tr_driver_ros2::ClockState latest_clock_state_{
      adi_imu_tr_driver_ros2::ClockState::kUnlocked};

  adi_imu_tr_driver_ros2::AffineClockConfig ReadClockConfig()
  {
    adi_imu_tr_driver_ros2::AffineClockConfig config;
    const int minimum_samples =
        std::max(2, declare_parameter<int>("clock.minimum_samples", 100));
    const int maximum_samples =
        std::max(minimum_samples, declare_parameter<int>("clock.maximum_samples", 5000));
    config.minimum_samples = static_cast<std::size_t>(minimum_samples);
    config.maximum_samples = static_cast<std::size_t>(maximum_samples);
    config.fit_interval_samples = static_cast<std::size_t>(
        std::max(1, declare_parameter<int>("clock.fit_interval_samples", 20)));
    config.minimum_span_us = static_cast<std::uint64_t>(
        std::max(1, declare_parameter<int>("clock.minimum_span_ms", 500))) * 1000ULL;
    config.maximum_rms_residual_ns =
        declare_parameter<double>("clock.maximum_rms_residual_ms", 2.0) * 1.0e6;
    config.maximum_drift_ppm = declare_parameter<double>("clock.maximum_drift_ppm", 5000.0);
    return config;
  }

  void ReadParameters()
  {
    device_ = declare_parameter<std::string>("device", "/dev/ttyACM0");
    frame_id_ = declare_parameter<std::string>("frame_id", "imu");
    parent_id_ = declare_parameter<std::string>("parent_id", "odom");
    legacy_rate_hz_ = declare_parameter<double>("rate", 100.0);
    publish_tf_ = declare_parameter<bool>("publish_tf", true);
    poll_period_us_ = declare_parameter<int>("poll_period_us", 500);
    maximum_batch_size_ = declare_parameter<int>("maximum_batch_size", 512);
    telemetry_qos_depth_ = declare_parameter<int>("telemetry_qos_depth", 256);
    orientation_variance_ = declare_parameter<double>("orientation_variance", 0.0);
    angular_velocity_variance_ = declare_parameter<double>("angular_velocity_variance", 0.0);
    linear_acceleration_variance_ =
        declare_parameter<double>("linear_acceleration_variance", 0.0);

    legacy_rate_hz_ = std::clamp(legacy_rate_hz_, 1.0, 1000.0);
    poll_period_us_ = std::clamp(poll_period_us_, 100, 10000);
    maximum_batch_size_ = std::clamp(maximum_batch_size_, 1, 4096);
    telemetry_qos_depth_ = std::clamp(telemetry_qos_depth_, 8, 4096);
  }

  void Prepare()
  {
    rclcpp::Rate retry_rate(1.0);
    while (rclcpp::ok() && !imu_.Open(device_)) {
      RCLCPP_WARN(get_logger(), "Waiting for IMU device %s", device_.c_str());
      retry_rate.sleep();
    }
    if (!rclcpp::ok()) return;

    imu_.StopTelemetry();
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
    bool settings_ok = false;
    for (int retry = 0; retry < 3 && rclcpp::ok(); ++retry) {
      if (imu_.ReadSettings()) {
        settings_ok = true;
        break;
      }
      retry_rate.sleep();
    }
    if (settings_ok) {
      settings_valid_ = true;
      const auto& settings = imu_.GetSettings();
      gravity_compensated_ = settings.grav_corr_en != 0;
      updater_->setHardwareID(imu_.GetProductIdStr());
      RCLCPP_INFO(get_logger(), "Product=%s sample_rate=%uHz filter=%u gravity_correction=%u",
                  imu_.GetProductIdStr().c_str(), settings.sample_rate, settings.filter_select,
                  settings.grav_corr_en);
    } else {
      updater_->setHardwareID("UNKNOWN");
      RCLCPP_ERROR(get_logger(), "Unable to read IMU settings; SI conversion is not trustworthy");
    }
    if (!imu_.StartTelemetry()) {
      RCLCPP_ERROR(get_logger(), "Unable to start periodic telemetry");
    }
  }

  static builtin_interfaces::msg::Time ToBuiltinTime(const rclcpp::Time& time)
  {
    builtin_interfaces::msg::Time result;
    result.sec = static_cast<std::int32_t>(time.nanoseconds() / 1000000000LL);
    result.nanosec = static_cast<std::uint32_t>(time.nanoseconds() % 1000000000LL);
    return result;
  }

  sensor_msgs::msg::Imu MakeImuMessage(const AdisRcvBin::TelemetryData& sample,
                                       const rclcpp::Time& capture_time) const
  {
    sensor_msgs::msg::Imu message;
    message.header.frame_id = frame_id_;
    message.header.stamp = ToBuiltinTime(capture_time);
    double acceleration[3];
    double gyro[3];
    double quaternion[4];
    imu_.ConvertAccSI(sample, acceleration);
    imu_.ConvertGyroSI(sample, gyro);
    AdisRcvBin::ConvertQuat(sample, quaternion);
    message.orientation.w = quaternion[0];
    message.orientation.x = quaternion[1];
    message.orientation.y = quaternion[2];
    message.orientation.z = quaternion[3];
    message.linear_acceleration.x = acceleration[0];
    message.linear_acceleration.y = acceleration[1];
    message.linear_acceleration.z = acceleration[2];
    message.angular_velocity.x = gyro[0];
    message.angular_velocity.y = gyro[1];
    message.angular_velocity.z = gyro[2];
    message.orientation_covariance[0] = orientation_variance_;
    message.orientation_covariance[4] = orientation_variance_;
    message.orientation_covariance[8] = orientation_variance_;
    message.angular_velocity_covariance[0] = angular_velocity_variance_;
    message.angular_velocity_covariance[4] = angular_velocity_variance_;
    message.angular_velocity_covariance[8] = angular_velocity_variance_;
    message.linear_acceleration_covariance[0] = linear_acceleration_variance_;
    message.linear_acceleration_covariance[4] = linear_acceleration_variance_;
    message.linear_acceleration_covariance[8] = linear_acceleration_variance_;
    return message;
  }

  bool AcceptCounter(const std::uint16_t counter)
  {
    return counter_tracker_.Observe(counter) ==
           adi_imu_tr_driver_ros2::CounterDecision::kAccepted;
  }

  void PublishTransform(const sensor_msgs::msg::Imu& imu_message)
  {
    if (!tf_pub_) return;
    geometry_msgs::msg::TransformStamped transform;
    transform.header = imu_message.header;
    transform.header.frame_id = parent_id_;
    transform.child_frame_id = frame_id_;
    transform.transform.rotation = imu_message.orientation;
    tf2_msgs::msg::TFMessage tf_message;
    tf_message.transforms.push_back(transform);
    tf_pub_->publish(tf_message);
  }

  void PublishSample(const AdisRcvBin::TelemetryData& sample)
  {
    const auto steady_now = std::chrono::steady_clock::now();
    const bool mcu_restarted = have_seen_mcu_time_ && sample.timestamp != 0 &&
                               sample.timestamp < last_seen_mcu_time_us_;
    const bool telemetry_was_stale = published_count_ > 0 &&
        std::chrono::duration<double>(steady_now - last_receive_steady_).count() > 1.0;
    if (mcu_restarted || telemetry_was_stale) {
      counter_tracker_.Resynchronize();
      ++counter_resync_count_;
    }
    last_seen_mcu_time_us_ = sample.timestamp;
    have_seen_mcu_time_ = true;
    if (!AcceptCounter(sample.imu_counter)) return;

    const rclcpp::Time receive_ros_time = get_clock()->now();
    const auto steady_ns = static_cast<std::uint64_t>(
        std::chrono::duration_cast<std::chrono::nanoseconds>(steady_now.time_since_epoch()).count());
    const bool pps_level = (sample.in0_port & 0x01U) != 0;
    if (!pps_level) have_seen_pps_low_ = true;
    const bool pps_edge = have_seen_pps_low_ && !last_pps_level_ && pps_level;
    last_pps_level_ = pps_level;
    adi_imu_tr_driver_ros2::ClockEstimate clock;
    {
      std::lock_guard<std::mutex> lock(clock_mutex_);
      clock = clock_mapper_.AddSample(sample.timestamp, receive_ros_time.nanoseconds(),
                                      steady_ns, pps_edge);
    }
    latest_clock_residual_ms_ = clock.residual_ms;
    latest_clock_state_ = clock.state;
    const rclcpp::Time capture_time(
        clock.state == adi_imu_tr_driver_ros2::ClockState::kUnlocked
            ? receive_ros_time.nanoseconds()
            : clock.ros_time_ns,
        get_clock()->get_clock_type());

    ImuTelemetry telemetry;
    telemetry.imu = MakeImuMessage(sample, capture_time);
    telemetry.receive_ros_time = ToBuiltinTime(receive_ros_time);
    telemetry.receive_steady_time_ns = steady_ns;
    telemetry.mcu_time_us = sample.timestamp;
    telemetry.send_counter = sample.send_counter;
    telemetry.imu_counter = sample.imu_counter;
    telemetry.imu_dropped = sample.imu_dropped;
    telemetry.computation_time_us = sample.computation_time_us;
    telemetry.spi_transaction_time_us = sample.spi_transaction_time_us;
    telemetry.pps_in_state = sample.in0_port;
    telemetry.mcu_error = sample.mpu_error;
    telemetry.temperature_c = static_cast<float>(AdisRcvBin::ConvertTemperature(sample));
    telemetry.gravity_compensated = gravity_compensated_;
    telemetry.clock_state = static_cast<std::uint8_t>(clock.state);
    telemetry.clock_residual_ms = static_cast<float>(clock.residual_ms);
    telemetry_pub_->publish(telemetry);
    ++published_count_;
    last_receive_steady_ = steady_now;

    imu_error_ = (sample.mpu_error & kMpuErrImuNotFound) != 0;
    if (imu_error_) return;
    const double period_s = 1.0 / legacy_rate_hz_;
    if (last_legacy_publish_time_.nanoseconds() == 0 ||
        (capture_time - last_legacy_publish_time_).seconds() >= period_s * 0.95) {
      imu_data_pub_->publish(telemetry.imu);
      PublishTransform(telemetry.imu);
      last_legacy_publish_time_ = capture_time;
    }
  }

  void Poll()
  {
    if (imu_.GetState() != AdisRcvBin::State::RUNNING) return;
    std::vector<AdisRcvBin::TelemetryData> samples;
    int result = kImuBinErrCantRcvData;
    {
      std::lock_guard<std::mutex> lock(serial_mutex_);
      result = imu_.ReadTelemetryBatch(&samples,
                                       static_cast<std::size_t>(maximum_batch_size_));
    }
    if (result == kImuBinOk) {
      for (const auto& sample : samples) PublishSample(sample);
    } else if (result != kImuBinErrCantRcvData && result != kImuBinErrCouldNotFindPkt) {
      RCLCPP_WARN_THROTTLE(get_logger(), *get_clock(), 1000,
                           "IMU packet parser returned error %d", result);
    }
  }

  void Diagnostic(diagnostic_updater::DiagnosticStatusWrapper& status)
  {
    const double age_s = std::chrono::duration<double>(std::chrono::steady_clock::now() -
                                                       last_receive_steady_).count();
    if (!settings_valid_) {
      status.summary(diagnostic_msgs::msg::DiagnosticStatus::ERROR,
                     "IMU settings unavailable; SI conversion is not trustworthy");
    } else if (imu_error_) {
      status.summary(diagnostic_msgs::msg::DiagnosticStatus::ERROR,
                     "IMU not recognized; downstream motion must stop");
    } else if (age_s > 1.0) {
      status.summary(diagnostic_msgs::msg::DiagnosticStatus::ERROR,
                     "No IMU telemetry for more than one second");
    } else if (latest_clock_state_ == adi_imu_tr_driver_ros2::ClockState::kUnlocked) {
      status.summary(diagnostic_msgs::msg::DiagnosticStatus::WARN,
                     "Telemetry OK; capture clock is not locked");
    } else {
      status.summary(diagnostic_msgs::msg::DiagnosticStatus::OK, "Telemetry and clock OK");
    }
    status.add("published_samples", published_count_);
    status.add("duplicates", counter_tracker_.duplicates());
    status.add("out_of_order", counter_tracker_.out_of_order());
    status.add("inferred_counter_drops", counter_tracker_.inferred_drops());
    status.add("counter_resynchronizations", counter_resync_count_);
    status.add("clock_residual_ms", latest_clock_residual_ms_);
    status.add("clock_state", static_cast<int>(latest_clock_state_));
    status.add("gravity_compensated", gravity_compensated_);
  }

  void CmdCb(const std::shared_ptr<rmw_request_id_t> request_header,
             const std::shared_ptr<SimpleCmd::Request> request,
             const std::shared_ptr<SimpleCmd::Response> response)
  {
    (void)request_header;
    if (request->cmd.empty()) {
      response->is_ok = false;
      response->msg = "Empty command";
      return;
    }
    std::uint8_t command = 0;
    try {
      command = static_cast<std::uint8_t>(std::stoul(request->cmd, nullptr, 0));
    } catch (const std::exception&) {
      response->is_ok = false;
      response->msg = "Invalid command ID: " + request->cmd;
      return;
    }
    std::array<std::uint8_t, 8> data{};
    for (std::size_t index = 0; index < request->args.size() && index < data.size(); ++index) {
      try {
        data[index] = static_cast<std::uint8_t>(std::stoul(request->args[index], nullptr, 0));
      } catch (const std::exception&) {
        response->is_ok = false;
        response->msg = "Invalid command argument";
        return;
      }
    }
    {
      std::lock_guard<std::mutex> lock(serial_mutex_);
      response->is_ok = imu_.SendCommand(command, data.data(), data.size());
    }
    if (command == 0xB0 || command == 0x33) {
      std::lock_guard<std::mutex> lock(clock_mutex_);
      clock_mapper_.Reset();
    }
    response->msg = response->is_ok ? "OK" : "Command failed";
  }
};

#endif  // ADIS_RCV_BIN_NODE_HPP_
