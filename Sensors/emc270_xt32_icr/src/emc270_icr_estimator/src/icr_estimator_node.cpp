#include "emc270_icr_estimator/icr_core.hpp"
#include "emc270_icr_estimator/imu_lever_arm_validator.hpp"
#include "emc270_icr_estimator/time_offset_estimator.hpp"

#include <diagnostic_msgs/msg/diagnostic_status.hpp>
#include <diagnostic_updater/diagnostic_updater.hpp>
#include <emc270_icr_msgs/msg/icr_estimate.hpp>
#include <emc270_icr_msgs/msg/imu_telemetry.hpp>
#include <geometry_msgs/msg/transform_stamped.hpp>
#include <nav_msgs/msg/odometry.hpp>
#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/point_cloud2.hpp>
#include <std_srvs/srv/trigger.hpp>
#include <tf2/LinearMath/Matrix3x3.h>
#include <tf2/LinearMath/Quaternion.h>
#include <tf2_ros/transform_broadcaster.h>

#include <Eigen/Cholesky>
#include <Eigen/Core>
#include <Eigen/Geometry>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <deque>
#include <exception>
#include <functional>
#include <iterator>
#include <limits>
#include <memory>
#include <optional>
#include <string>
#include <vector>

namespace emc270::icr {
namespace {

double StampToSeconds(const builtin_interfaces::msg::Time& stamp) {
  return static_cast<double>(stamp.sec) + static_cast<double>(stamp.nanosec) * 1.0e-9;
}

builtin_interfaces::msg::Time SecondsToStamp(const double seconds) {
  builtin_interfaces::msg::Time stamp;
  if (!std::isfinite(seconds) || seconds <= 0.0) return stamp;
  const double integral = std::floor(seconds);
  stamp.sec = static_cast<std::int32_t>(integral);
  stamp.nanosec = static_cast<std::uint32_t>(std::llround((seconds - integral) * 1.0e9));
  if (stamp.nanosec >= 1000000000U) {
    ++stamp.sec;
    stamp.nanosec -= 1000000000U;
  }
  return stamp;
}

std::optional<double> QuaternionYaw(const geometry_msgs::msg::Quaternion& quaternion) {
  const double norm_squared = quaternion.x * quaternion.x + quaternion.y * quaternion.y +
                              quaternion.z * quaternion.z + quaternion.w * quaternion.w;
  if (!std::isfinite(norm_squared) || norm_squared < 1.0e-12) return std::nullopt;
  tf2::Quaternion q(quaternion.x, quaternion.y, quaternion.z, quaternion.w);
  q.normalize();
  double roll = 0.0;
  double pitch = 0.0;
  double yaw = 0.0;
  tf2::Matrix3x3(q).getRPY(roll, pitch, yaw);
  return std::isfinite(yaw) ? std::optional<double>(yaw) : std::nullopt;
}

const char* StatusName(const Status status) {
  switch (status) {
    case Status::kValid: return "VALID";
    case Status::kLowYaw: return "LOW_YAW";
    case Status::kDegenerate: return "DEGENERATE";
    case Status::kStaleInput: return "STALE_INPUT";
    case Status::kOdomReset: return "ODOM_RESET";
    case Status::kExcessResidual: return "EXCESS_RESIDUAL";
    case Status::kSensorDisagreement: return "SENSOR_DISAGREEMENT";
    case Status::kUninitialized: return "UNINITIALIZED";
  }
  return "UNKNOWN";
}

double Percentile95(const std::deque<double>& samples) {
  if (samples.empty()) return std::numeric_limits<double>::quiet_NaN();
  std::vector<double> sorted(samples.begin(), samples.end());
  std::sort(sorted.begin(), sorted.end());
  const double index = 0.95 * static_cast<double>(sorted.size() - 1);
  const auto lower = static_cast<std::size_t>(std::floor(index));
  const auto upper = static_cast<std::size_t>(std::ceil(index));
  if (lower == upper) return sorted[lower];
  return sorted[lower] + (index - static_cast<double>(lower)) *
                             (sorted[upper] - sorted[lower]);
}

void PushMetric(std::deque<double>* samples, const double value) {
  if (samples == nullptr || !std::isfinite(value)) return;
  samples->push_back(value);
  while (samples->size() > 2000) samples->pop_front();
}

}  // namespace

class IcrEstimatorNode : public rclcpp::Node {
 public:
  IcrEstimatorNode()
  : Node("emc270_icr_estimator"),
    estimator_(ReadEstimatorConfig()),
    imu_validator_(ReadImuValidatorConfig()),
    time_offset_estimator_(ReadTimeOffsetConfig()),
    tf_broadcaster_(std::make_unique<tf2_ros::TransformBroadcaster>(*this)) {
    ReadParameters();

    fast_publisher_ = create_publisher<emc270_icr_msgs::msg::IcrEstimate>(
        "icr/fast", rclcpp::SensorDataQoS());
    smooth_publisher_ = create_publisher<emc270_icr_msgs::msg::IcrEstimate>(
        "icr/smoothed", rclcpp::SensorDataQoS());

    point_cloud_subscription_ = create_subscription<sensor_msgs::msg::PointCloud2>(
        point_cloud_topic_, rclcpp::SensorDataQoS(),
        std::bind(&IcrEstimatorNode::OnPointCloud, this, std::placeholders::_1));
    odom_subscription_ = create_subscription<nav_msgs::msg::Odometry>(
        odom_topic_, rclcpp::SensorDataQoS(),
        std::bind(&IcrEstimatorNode::OnOdometry, this, std::placeholders::_1));
    imu_subscription_ = create_subscription<emc270_icr_msgs::msg::ImuTelemetry>(
        imu_topic_, rclcpp::SensorDataQoS().keep_last(512),
        std::bind(&IcrEstimatorNode::OnImu, this, std::placeholders::_1));
    imu_clock_reset_client_ =
        create_client<std_srvs::srv::Trigger>("imu/reset_clock_model");

    reset_service_ = create_service<std_srvs::srv::Trigger>(
        "icr/reset", [this](const std::shared_ptr<std_srvs::srv::Trigger::Request>,
                            std::shared_ptr<std_srvs::srv::Trigger::Response> response) {
          const bool imu_reset_requested = imu_clock_reset_client_->service_is_ready();
          if (imu_reset_requested) {
            auto request = std::make_shared<std_srvs::srv::Trigger::Request>();
            imu_clock_reset_client_->async_send_request(
                request, [this](rclcpp::Client<std_srvs::srv::Trigger>::SharedFuture future) {
                  try {
                    const auto response = future.get();
                    if (!response->success) {
                      RCLCPP_WARN(get_logger(), "IMU clock reset failed: %s",
                                  response->message.c_str());
                    }
                  } catch (const std::exception& error) {
                    RCLCPP_WARN(get_logger(), "IMU clock reset service error: %s", error.what());
                  }
                });
          }
          ResetState();
          response->success = true;
          response->message = imu_reset_requested
              ? "Estimator reset; IMU affine clock reset requested"
              : "Estimator reset; IMU affine clock service unavailable";
        });

    diagnostics_ = std::make_unique<diagnostic_updater::Updater>(this);
    diagnostics_->setHardwareID("emc270_xt32_icr");
    diagnostics_->add("icr_estimator", this, &IcrEstimatorNode::ProduceDiagnostics);
    watchdog_timer_ = create_wall_timer(std::chrono::milliseconds(100),
                                        std::bind(&IcrEstimatorNode::Watchdog, this));
    diagnostic_timer_ = create_wall_timer(std::chrono::seconds(1), [this]() {
      diagnostics_->force_update();
    });
  }

 private:
  struct TimedImu {
    double raw_time_s{0.0};
    double gyro_z_rad_s{0.0};
    double acceleration_x_m_s2{0.0};
    double acceleration_y_m_s2{0.0};
    std::uint8_t clock_state{0};
    std::uint8_t mcu_error{0};
  };

  struct CloudTiming {
    double header_stamp_s{0.0};
    double end_stamp_s{0.0};
  };

  IcrEstimatorCore estimator_;
  ImuLeverArmValidator imu_validator_;
  TimeOffsetEstimator time_offset_estimator_;
  std::unique_ptr<tf2_ros::TransformBroadcaster> tf_broadcaster_;
  std::unique_ptr<diagnostic_updater::Updater> diagnostics_;

  rclcpp::Publisher<emc270_icr_msgs::msg::IcrEstimate>::SharedPtr fast_publisher_;
  rclcpp::Publisher<emc270_icr_msgs::msg::IcrEstimate>::SharedPtr smooth_publisher_;
  rclcpp::Subscription<sensor_msgs::msg::PointCloud2>::SharedPtr point_cloud_subscription_;
  rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr odom_subscription_;
  rclcpp::Subscription<emc270_icr_msgs::msg::ImuTelemetry>::SharedPtr imu_subscription_;
  rclcpp::Client<std_srvs::srv::Trigger>::SharedPtr imu_clock_reset_client_;
  rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr reset_service_;
  rclcpp::TimerBase::SharedPtr watchdog_timer_;
  rclcpp::TimerBase::SharedPtr diagnostic_timer_;

  std::string point_cloud_topic_;
  std::string point_cloud_frame_;
  std::string odom_topic_;
  std::string imu_topic_;
  std::string output_frame_;
  std::string fast_child_frame_;
  std::string smooth_child_frame_;
  bool publish_tf_{true};
  double stale_timeout_s_{0.30};
  double point_cloud_stale_timeout_s_{0.30};
  double point_cloud_gap_threshold_s_{0.15};
  double imu_stale_timeout_s_{0.10};
  bool require_point_timestamps_{true};
  double fixture_imu_x_m_{0.0};
  double fixture_imu_y_m_{0.0};
  double fixture_imu_roll_rad_{0.0};
  double fixture_imu_pitch_rad_{0.0};
  double fixture_imu_yaw_rad_{0.0};
  double fixture_xy_sigma_m_{0.002};
  double fixture_axis_angle_sigma_rad_{0.003491};
  bool enable_accel_validation_{true};
  bool acceleration_gravity_compensated_{true};
  std::size_t imu_bias_calibration_samples_{5000};
  double stationary_max_horizontal_accel_m_s2_{0.50};
  double disagreement_chi_square_{5.991};
  double time_offset_holdover_s_{120.0};
  double time_offset_validator_reset_threshold_s_{0.005};

  std::deque<TimedImu> imu_samples_;
  std::deque<CloudTiming> cloud_timings_;
  std::deque<double> usable_cloud_stamps_s_;
  std::deque<double> unusable_cloud_stamps_s_;
  std::optional<PlanarPose> previous_odom_;
  std::optional<TimedImu> previous_imu_;
  Eigen::Vector2d stationary_accel_bias_{Eigen::Vector2d::Zero()};
  std::size_t accel_bias_sample_count_{0};
  bool have_accel_bias_{false};
  double filtered_alpha_rad_s2_{0.0};
  double imu_time_correction_s_{0.0};
  TimeOffsetResult latest_offset_;
  TimeOffsetResult latest_offset_measurement_;
  std::chrono::steady_clock::time_point last_valid_offset_receive_{};
  bool time_offset_holdover_active_{false};
  Status latest_fast_status_{Status::kUninitialized};
  Status latest_smooth_status_{Status::kUninitialized};
  std::uint8_t latest_fast_source_mask_{kSourceLidar};
  std::uint8_t latest_smooth_source_mask_{kSourceLidar};
  double latest_fast_rms_m_{std::numeric_limits<double>::quiet_NaN()};
  double latest_smooth_rms_m_{std::numeric_limits<double>::quiet_NaN()};
  double latest_fast_condition_{std::numeric_limits<double>::infinity()};
  double latest_smooth_condition_{std::numeric_limits<double>::infinity()};
  double latest_fast_end_to_publish_ms_{std::numeric_limits<double>::quiet_NaN()};
  std::deque<double> fast_processing_ms_;
  std::deque<double> smooth_processing_ms_;
  std::deque<double> fast_end_to_publish_ms_;

  std::chrono::steady_clock::time_point last_point_cloud_receive_{};
  std::chrono::steady_clock::time_point last_imu_receive_{};
  double last_odom_stamp_s_{0.0};
  std::chrono::steady_clock::time_point last_odom_receive_{};
  bool have_point_cloud_{false};
  bool point_timestamps_usable_{false};
  bool point_time_domain_compatible_{false};
  bool point_cloud_frame_mismatch_{false};
  bool have_imu_{false};
  bool have_odom_{false};
  bool stale_published_{false};
  bool odom_frame_mismatch_{false};
  std::uint64_t point_cloud_count_{0};
  std::uint64_t point_cloud_gap_count_{0};
  std::uint64_t imu_gap_count_{0};
  std::uint64_t latest_point_count_{0};
  double previous_point_cloud_stamp_s_{0.0};
  double latest_point_timestamp_span_s_{0.0};
  double latest_point_cloud_stamp_s_{0.0};
  double latest_point_cloud_end_stamp_s_{0.0};
  bool have_imu_counter_{false};
  std::uint16_t last_imu_counter_{0};
  std::uint16_t latest_imu_dropped_{0};
  std::uint8_t latest_imu_clock_state_{0};
  std::uint8_t latest_imu_mcu_error_{0};
  bool latest_imu_gravity_compensated_{false};
  double latest_imu_clock_residual_ms_{std::numeric_limits<double>::infinity()};
  double latest_imu_normalized_residual_{std::numeric_limits<double>::quiet_NaN()};
  double latest_imu_fit_rms_m_s2_{std::numeric_limits<double>::quiet_NaN()};
  double latest_imu_condition_{std::numeric_limits<double>::infinity()};

  EstimatorConfig ReadEstimatorConfig() {
    EstimatorConfig config;
    config.fast_window_s = declare_parameter<double>("fast.window_s", 0.10);
    config.smooth_window_s = declare_parameter<double>("smooth.window_s", 2.0);
    config.fast_validity_s = declare_parameter<double>("fast.validity_s", 0.15);
    config.smooth_validity_s = declare_parameter<double>("smooth.validity_s", 0.25);
    config.minimum_yaw_rate_rad_s =
        declare_parameter<double>("minimum_yaw_rate_rad_s", 0.10);
    config.minimum_smooth_yaw_rad =
        declare_parameter<double>("smooth.minimum_yaw_rad", 0.2617993877991494);
    config.minimum_smooth_samples = static_cast<std::size_t>(
        declare_parameter<int>("smooth.minimum_samples", 8));
    config.huber_delta_m = declare_parameter<double>("smooth.huber_delta_m", 0.02);
    config.maximum_fit_rms_m = declare_parameter<double>("smooth.maximum_fit_rms_m", 0.05);
    config.maximum_condition_number =
        declare_parameter<double>("maximum_condition_number", 1.0e6);
    config.odom_reset_gap_s = declare_parameter<double>("odom_reset.gap_s", 1.0);
    config.odom_reset_translation_m =
        declare_parameter<double>("odom_reset.translation_m", 1.0);
    config.odom_reset_yaw_rad = declare_parameter<double>("odom_reset.yaw_rad", 1.0);
    config.velocity_sigma_m_s = declare_parameter<double>("fast.velocity_sigma_m_s", 0.02);
    config.yaw_rate_sigma_rad_s =
        declare_parameter<double>("fast.yaw_rate_sigma_rad_s", 0.02);
    config.imu_gyro_weight = declare_parameter<double>("imu.gyro_weight", 0.20);
    config.imu_gyro_max_disagreement_rad_s =
        declare_parameter<double>("imu.gyro_max_disagreement_rad_s", 0.10);
    return config;
  }

  ImuValidatorConfig ReadImuValidatorConfig() {
    ImuValidatorConfig config;
    config.window_s = declare_parameter<double>("imu.validation_window_s", 2.0);
    config.minimum_samples = static_cast<std::size_t>(
        declare_parameter<int>("imu.validation_minimum_samples", 50));
    config.minimum_yaw_rate_rad_s =
        declare_parameter<double>("imu.validation_minimum_yaw_rate_rad_s", 0.10);
    config.huber_delta_m_s2 =
        declare_parameter<double>("imu.validation_huber_delta_m_s2", 0.20);
    config.maximum_condition_number =
        declare_parameter<double>("imu.validation_maximum_condition_number", 1.0e5);
    config.maximum_fit_rms_m_s2 =
        declare_parameter<double>("imu.validation_maximum_fit_rms_m_s2", 0.50);
    config.maximum_position_stddev_m =
        declare_parameter<double>("imu.validation_maximum_position_stddev_m", 0.05);
    return config;
  }

  TimeOffsetConfig ReadTimeOffsetConfig() {
    TimeOffsetConfig config;
    config.window_s = declare_parameter<double>("time_offset.window_s", 5.0);
    config.maximum_offset_s = declare_parameter<double>("time_offset.maximum_s", 0.050);
    config.search_step_s = declare_parameter<double>("time_offset.step_s", 0.001);
    config.minimum_rate_standard_deviation =
        declare_parameter<double>("time_offset.minimum_rate_stddev", 0.05);
    config.minimum_correlation =
        declare_parameter<double>("time_offset.minimum_correlation", 0.80);
    config.minimum_matched_samples = static_cast<std::size_t>(
        declare_parameter<int>("time_offset.minimum_samples", 20));
    return config;
  }

  void ReadParameters() {
    point_cloud_topic_ = declare_parameter<std::string>("point_cloud_topic", "/lidar_points");
    point_cloud_frame_ =
        declare_parameter<std::string>("point_cloud_frame", "hesai_lidar_native");
    odom_topic_ = declare_parameter<std::string>("odom_topic", "/kiss/odometry");
    imu_topic_ = declare_parameter<std::string>("imu_topic", "/imu/telemetry");
    output_frame_ = declare_parameter<std::string>("output_frame", "xt32_link");
    fast_child_frame_ = declare_parameter<std::string>("fast_child_frame", "estimated_icr_fast");
    smooth_child_frame_ =
        declare_parameter<std::string>("smooth_child_frame", "estimated_icr_smoothed");
    publish_tf_ = declare_parameter<bool>("publish_tf", true);
    stale_timeout_s_ = declare_parameter<double>("stale_timeout_s", 0.30);
    point_cloud_stale_timeout_s_ =
        declare_parameter<double>("point_cloud_stale_timeout_s", 0.30);
    point_cloud_gap_threshold_s_ =
        declare_parameter<double>("point_cloud_gap_threshold_s", 0.15);
    imu_stale_timeout_s_ = declare_parameter<double>("imu_stale_timeout_s", 0.10);
    require_point_timestamps_ = declare_parameter<bool>("require_point_timestamps", true);
    fixture_imu_x_m_ = declare_parameter<double>("fixture.imu_x_m", 0.0);
    fixture_imu_y_m_ = declare_parameter<double>("fixture.imu_y_m", 0.0);
    fixture_imu_roll_rad_ = declare_parameter<double>("fixture.imu_roll_rad", 0.0);
    fixture_imu_pitch_rad_ = declare_parameter<double>("fixture.imu_pitch_rad", 0.0);
    fixture_imu_yaw_rad_ = declare_parameter<double>("fixture.imu_yaw_rad", 0.0);
    fixture_xy_sigma_m_ = declare_parameter<double>("fixture.xy_sigma_m", 0.002);
    fixture_axis_angle_sigma_rad_ =
        declare_parameter<double>("fixture.axis_angle_sigma_rad", 0.003491);
    enable_accel_validation_ = declare_parameter<bool>("imu.enable_accel_validation", true);
    acceleration_gravity_compensated_ =
        declare_parameter<bool>("imu.acceleration_gravity_compensated", true);
    imu_bias_calibration_samples_ = static_cast<std::size_t>(
        std::max(1, declare_parameter<int>("imu.bias_calibration_samples", 5000)));
    stationary_max_horizontal_accel_m_s2_ =
        declare_parameter<double>("imu.stationary_max_horizontal_accel_m_s2", 0.50);
    disagreement_chi_square_ = declare_parameter<double>("imu.disagreement_chi_square", 5.991);
    time_offset_holdover_s_ = declare_parameter<double>("time_offset.holdover_s", 120.0);
    time_offset_validator_reset_threshold_s_ =
        declare_parameter<double>("time_offset.validator_reset_threshold_s", 0.005);
    if (!acceleration_gravity_compensated_) {
      RCLCPP_WARN(get_logger(),
                  "Acceleration lever-arm validation disabled: gravity compensation is required");
      enable_accel_validation_ = false;
    }
  }

  void ResetState() {
    estimator_.Reset();
    imu_validator_.Reset();
    time_offset_estimator_.Reset();
    imu_samples_.clear();
    previous_odom_.reset();
    previous_imu_.reset();
    have_accel_bias_ = false;
    accel_bias_sample_count_ = 0;
    stationary_accel_bias_.setZero();
    filtered_alpha_rad_s2_ = 0.0;
    imu_time_correction_s_ = 0.0;
    latest_offset_ = {};
    latest_offset_measurement_ = {};
    time_offset_holdover_active_ = false;
    latest_fast_status_ = Status::kUninitialized;
    latest_smooth_status_ = Status::kUninitialized;
    latest_fast_source_mask_ = kSourceLidar;
    latest_smooth_source_mask_ = kSourceLidar;
    latest_fast_rms_m_ = std::numeric_limits<double>::quiet_NaN();
    latest_smooth_rms_m_ = std::numeric_limits<double>::quiet_NaN();
    latest_fast_condition_ = std::numeric_limits<double>::infinity();
    latest_smooth_condition_ = std::numeric_limits<double>::infinity();
    latest_fast_end_to_publish_ms_ = std::numeric_limits<double>::quiet_NaN();
    latest_imu_normalized_residual_ = std::numeric_limits<double>::quiet_NaN();
    latest_imu_fit_rms_m_s2_ = std::numeric_limits<double>::quiet_NaN();
    latest_imu_condition_ = std::numeric_limits<double>::infinity();
    cloud_timings_.clear();
    usable_cloud_stamps_s_.clear();
    unusable_cloud_stamps_s_.clear();
    fast_processing_ms_.clear();
    smooth_processing_ms_.clear();
    fast_end_to_publish_ms_.clear();
    have_odom_ = false;
    odom_frame_mismatch_ = false;
    point_cloud_frame_mismatch_ = false;
    last_odom_stamp_s_ = 0.0;
    stale_published_ = false;
  }

  std::optional<double> ReadPointTimestamp(
      const sensor_msgs::msg::PointCloud2& message,
      const sensor_msgs::msg::PointField& field, const std::size_t index) const {
    const std::size_t point_count = static_cast<std::size_t>(message.width) * message.height;
    if (index >= point_count || message.width == 0 || message.is_bigendian) return std::nullopt;
    const std::size_t row = index / message.width;
    const std::size_t column = index % message.width;
    const std::size_t offset = row * message.row_step + column * message.point_step + field.offset;
    if (field.datatype == sensor_msgs::msg::PointField::FLOAT64) {
      if (offset + sizeof(double) > message.data.size()) return std::nullopt;
      double value = 0.0;
      std::memcpy(&value, message.data.data() + offset, sizeof(value));
      return value;
    }
    if (field.datatype == sensor_msgs::msg::PointField::FLOAT32) {
      if (offset + sizeof(float) > message.data.size()) return std::nullopt;
      float value = 0.0F;
      std::memcpy(&value, message.data.data() + offset, sizeof(value));
      return static_cast<double>(value);
    }
    if (field.datatype == sensor_msgs::msg::PointField::UINT32) {
      if (offset + sizeof(std::uint32_t) > message.data.size()) return std::nullopt;
      std::uint32_t value = 0;
      std::memcpy(&value, message.data.data() + offset, sizeof(value));
      return static_cast<double>(value);
    }
    return std::nullopt;
  }

  void MarkPointCloudUnusable(const double stamp_s) {
    if (!require_point_timestamps_) return;
    unusable_cloud_stamps_s_.push_back(stamp_s);
    while (unusable_cloud_stamps_s_.size() > 50) unusable_cloud_stamps_s_.pop_front();
    // KISS can still publish odometry after disabling deskew. Remove every
    // pose that might have been derived from the unusable scan.
    estimator_.Reset();
    previous_odom_.reset();
    time_offset_estimator_.Reset();
    imu_validator_.Reset();
    latest_offset_ = {};
    latest_offset_measurement_ = {};
    imu_time_correction_s_ = 0.0;
    time_offset_holdover_active_ = false;
    latest_fast_status_ = Status::kDegenerate;
    latest_smooth_status_ = Status::kDegenerate;
  }

  void OnPointCloud(const sensor_msgs::msg::PointCloud2::SharedPtr message) {
    const auto now = std::chrono::steady_clock::now();
    const double stamp_s = StampToSeconds(message->header.stamp);
    if (previous_point_cloud_stamp_s_ > 0.0 && stamp_s > previous_point_cloud_stamp_s_ &&
        stamp_s - previous_point_cloud_stamp_s_ > point_cloud_gap_threshold_s_) {
      ++point_cloud_gap_count_;
    }
    previous_point_cloud_stamp_s_ = stamp_s;
    last_point_cloud_receive_ = now;
    have_point_cloud_ = true;
    ++point_cloud_count_;
    latest_point_count_ = static_cast<std::uint64_t>(message->width) * message->height;
    latest_point_cloud_stamp_s_ = stamp_s;
    latest_point_timestamp_span_s_ = 0.0;
    point_timestamps_usable_ = false;
    point_time_domain_compatible_ = false;
    point_cloud_frame_mismatch_ = message->header.frame_id != point_cloud_frame_;
    if (point_cloud_frame_mismatch_) {
      MarkPointCloudUnusable(stamp_s);
      return;
    }

    const auto field = std::find_if(message->fields.begin(), message->fields.end(),
        [](const sensor_msgs::msg::PointField& candidate) {
          return candidate.name == "t" || candidate.name == "timestamp" ||
                 candidate.name == "time" || candidate.name == "time_stamp";
        });
    if (field == message->fields.end() || latest_point_count_ < 2) {
      MarkPointCloudUnusable(stamp_s);
      return;
    }
    const bool supported = field->count == 1 &&
                           (field->datatype == sensor_msgs::msg::PointField::UINT32 ||
                            field->datatype == sensor_msgs::msg::PointField::FLOAT32 ||
                            field->datatype == sensor_msgs::msg::PointField::FLOAT64);
    if (!supported) {
      MarkPointCloudUnusable(stamp_s);
      return;
    }
    double minimum_timestamp = std::numeric_limits<double>::infinity();
    double maximum_timestamp = -std::numeric_limits<double>::infinity();
    for (std::size_t index = 0;
         index < static_cast<std::size_t>(latest_point_count_); ++index) {
      const auto timestamp = ReadPointTimestamp(*message, *field, index);
      if (!timestamp.has_value() || !std::isfinite(*timestamp)) {
        MarkPointCloudUnusable(stamp_s);
        return;
      }
      minimum_timestamp = std::min(minimum_timestamp, *timestamp);
      maximum_timestamp = std::max(maximum_timestamp, *timestamp);
    }
    latest_point_timestamp_span_s_ = maximum_timestamp - minimum_timestamp;
    point_timestamps_usable_ = latest_point_timestamp_span_s_ > 1.0e-12;
    if (point_timestamps_usable_) {
      usable_cloud_stamps_s_.push_back(stamp_s);
      while (usable_cloud_stamps_s_.size() > 50) usable_cloud_stamps_s_.pop_front();
    } else {
      MarkPointCloudUnusable(stamp_s);
      return;
    }

    // The Hesai driver publishes an absolute FLOAT64 timestamp for every
    // point. Retain its scan-end time for the live latency acceptance metric.
    if (field->datatype == sensor_msgs::msg::PointField::FLOAT64) {
      const double end_s = maximum_timestamp;
      if (std::isfinite(stamp_s) && std::abs(minimum_timestamp - stamp_s) < 1.0 &&
          end_s >= stamp_s && end_s - stamp_s < 1.0) {
        latest_point_cloud_end_stamp_s_ = end_s;
        point_time_domain_compatible_ = true;
        cloud_timings_.push_back({stamp_s, end_s});
        while (cloud_timings_.size() > 20) cloud_timings_.pop_front();
      }
    }
  }

  void OnImu(const emc270_icr_msgs::msg::ImuTelemetry::SharedPtr message) {
    last_imu_receive_ = std::chrono::steady_clock::now();
    have_imu_ = true;
    latest_imu_clock_state_ = message->clock_state;
    latest_imu_clock_residual_ms_ = message->clock_residual_ms;
    latest_imu_mcu_error_ = message->mcu_error;
    latest_imu_gravity_compensated_ = message->gravity_compensated;
    latest_imu_dropped_ = message->imu_dropped;
    if (have_imu_counter_) {
      const std::uint16_t delta = static_cast<std::uint16_t>(message->imu_counter -
                                                             last_imu_counter_);
      if (delta > 1 && delta <= 32768U) imu_gap_count_ += delta - 1;
    }
    last_imu_counter_ = message->imu_counter;
    have_imu_counter_ = true;

    TimedImu sample;
    sample.raw_time_s = StampToSeconds(message->imu.header.stamp);
    const Eigen::Matrix3d imu_to_lidar =
        (Eigen::AngleAxisd(fixture_imu_yaw_rad_, Eigen::Vector3d::UnitZ()) *
         Eigen::AngleAxisd(fixture_imu_pitch_rad_, Eigen::Vector3d::UnitY()) *
         Eigen::AngleAxisd(fixture_imu_roll_rad_, Eigen::Vector3d::UnitX())).toRotationMatrix();
    const Eigen::Vector3d acceleration_imu(message->imu.linear_acceleration.x,
                                           message->imu.linear_acceleration.y,
                                           message->imu.linear_acceleration.z);
    const Eigen::Vector3d gyro_imu(message->imu.angular_velocity.x,
                                   message->imu.angular_velocity.y,
                                   message->imu.angular_velocity.z);
    const Eigen::Vector3d acceleration_lidar = imu_to_lidar * acceleration_imu;
    const Eigen::Vector3d gyro_lidar = imu_to_lidar * gyro_imu;
    sample.acceleration_x_m_s2 = acceleration_lidar.x();
    sample.acceleration_y_m_s2 = acceleration_lidar.y();
    sample.gyro_z_rad_s = gyro_lidar.z();
    sample.clock_state = message->clock_state;
    sample.mcu_error = message->mcu_error;
    if (!std::isfinite(sample.raw_time_s) || sample.raw_time_s <= 0.0) return;

    if (!imu_samples_.empty() && sample.raw_time_s <= imu_samples_.back().raw_time_s) {
      imu_samples_.clear();
      previous_imu_.reset();
      time_offset_estimator_.Reset();
      imu_validator_.Reset();
      latest_offset_ = {};
      latest_offset_measurement_ = {};
      imu_time_correction_s_ = 0.0;
      time_offset_holdover_active_ = false;
    }

    if (sample.clock_state != emc270_icr_msgs::msg::ImuTelemetry::CLOCK_UNLOCKED &&
        sample.mcu_error == 0 && std::isfinite(sample.gyro_z_rad_s)) {
      time_offset_estimator_.AddImuRate({sample.raw_time_s, sample.gyro_z_rad_s});
    }
    imu_samples_.push_back(sample);
    while (imu_samples_.size() > 2 &&
           imu_samples_.front().raw_time_s < sample.raw_time_s - 6.0) {
      imu_samples_.pop_front();
    }

    if (sample.mcu_error == 0 && std::abs(sample.gyro_z_rad_s) < 0.03 &&
        accel_bias_sample_count_ < imu_bias_calibration_samples_) {
      const Eigen::Vector2d acceleration(sample.acceleration_x_m_s2,
                                         sample.acceleration_y_m_s2);
      const bool horizontally_stationary =
          (accel_bias_sample_count_ == 0 &&
           acceleration.norm() < stationary_max_horizontal_accel_m_s2_) ||
          (accel_bias_sample_count_ > 0 &&
           (acceleration - stationary_accel_bias_).norm() <
               stationary_max_horizontal_accel_m_s2_);
      if (horizontally_stationary) {
        ++accel_bias_sample_count_;
        const double weight = 1.0 / static_cast<double>(accel_bias_sample_count_);
        stationary_accel_bias_ += weight * (acceleration - stationary_accel_bias_);
        have_accel_bias_ = accel_bias_sample_count_ >= imu_bias_calibration_samples_;
      }
    }

    if (previous_imu_.has_value()) {
      const double dt = sample.raw_time_s - previous_imu_->raw_time_s;
      if (dt > 1.0e-5 && dt < 0.1 &&
          message->clock_state != emc270_icr_msgs::msg::ImuTelemetry::CLOCK_UNLOCKED &&
          previous_imu_->clock_state !=
              emc270_icr_msgs::msg::ImuTelemetry::CLOCK_UNLOCKED &&
          message->mcu_error == 0 && previous_imu_->mcu_error == 0) {
        const double raw_alpha = (sample.gyro_z_rad_s - previous_imu_->gyro_z_rad_s) / dt;
        filtered_alpha_rad_s2_ = 0.9 * filtered_alpha_rad_s2_ + 0.1 * raw_alpha;
        const Eigen::Vector2d acceleration(sample.acceleration_x_m_s2,
                                           sample.acceleration_y_m_s2);
        const Eigen::Vector2d corrected = acceleration - stationary_accel_bias_;
        if (enable_accel_validation_ && acceleration_gravity_compensated_ &&
            message->gravity_compensated && have_accel_bias_ && latest_offset_.valid) {
          imu_validator_.AddSample({sample.raw_time_s + imu_time_correction_s_, corrected.x(),
                                    corrected.y(), sample.gyro_z_rad_s,
                                    filtered_alpha_rad_s2_});
        }
      }
    }
    previous_imu_ = sample;
  }

  std::optional<double> InterpolatedGyro(const double target_time_s) const {
    if (!latest_offset_.valid || imu_samples_.size() < 2) return std::nullopt;
    const double raw_target = target_time_s - imu_time_correction_s_;
    const auto upper = std::lower_bound(
        imu_samples_.begin(), imu_samples_.end(), raw_target,
        [](const TimedImu& sample, const double time) { return sample.raw_time_s < time; });
    if (upper == imu_samples_.begin() || upper == imu_samples_.end()) return std::nullopt;
    const auto lower = std::prev(upper);
    const double span = upper->raw_time_s - lower->raw_time_s;
    if (span <= 0.0 || span > 0.02 || lower->clock_state == 0 || upper->clock_state == 0 ||
        lower->mcu_error != 0 || upper->mcu_error != 0) {
      return std::nullopt;
    }
    const double fraction = (raw_target - lower->raw_time_s) / span;
    return lower->gyro_z_rad_s + fraction * (upper->gyro_z_rad_s - lower->gyro_z_rad_s);
  }

  bool ImuTimingUsable() const {
    if (!latest_offset_.valid || !have_imu_ || latest_imu_clock_state_ == 0 ||
        latest_imu_mcu_error_ != 0) {
      return false;
    }
    const double age_s = std::chrono::duration<double>(std::chrono::steady_clock::now() -
                                                       last_imu_receive_).count();
    return age_s <= imu_stale_timeout_s_;
  }

  void UpdateTimeOffset() {
    latest_offset_measurement_ = time_offset_estimator_.Estimate();
    if (latest_offset_measurement_.valid) {
      if (!latest_offset_.valid ||
          std::abs(latest_offset_measurement_.imu_time_correction_s -
                   imu_time_correction_s_) > time_offset_validator_reset_threshold_s_) {
        imu_validator_.Reset();
      }
      latest_offset_ = latest_offset_measurement_;
      imu_time_correction_s_ = latest_offset_.imu_time_correction_s;
      last_valid_offset_receive_ = std::chrono::steady_clock::now();
      time_offset_holdover_active_ = false;
      return;
    }
    if (latest_offset_.valid) {
      const double holdover_age_s = std::chrono::duration<double>(
          std::chrono::steady_clock::now() - last_valid_offset_receive_).count();
      if (holdover_age_s <= time_offset_holdover_s_) {
        time_offset_holdover_active_ = true;
        return;
      }
    }
    if (latest_offset_.valid) imu_validator_.Reset();
    latest_offset_ = latest_offset_measurement_;
    imu_time_correction_s_ = 0.0;
    time_offset_holdover_active_ = false;
  }

  bool HasUsablePointTimestamps(const double header_stamp_s) const {
    return std::any_of(usable_cloud_stamps_s_.rbegin(), usable_cloud_stamps_s_.rend(),
        [header_stamp_s](const double stamp_s) {
          return std::abs(stamp_s - header_stamp_s) < 1.0e-6;
        });
  }

  bool HasUnusablePointTimestamps(const double header_stamp_s) const {
    return std::any_of(unusable_cloud_stamps_s_.rbegin(), unusable_cloud_stamps_s_.rend(),
        [header_stamp_s](const double stamp_s) {
          return std::abs(stamp_s - header_stamp_s) < 1.0e-6;
        });
  }

  void ApplyPointCloudGate(Estimate* estimate, const double pose_stamp_s) const {
    if (estimate == nullptr || !estimate->valid() || !require_point_timestamps_) return;
    if (!have_point_cloud_) {
      estimate->status = Status::kStaleInput;
      return;
    }
    const double age_s = std::chrono::duration<double>(std::chrono::steady_clock::now() -
                                                       last_point_cloud_receive_).count();
    if (age_s > point_cloud_stale_timeout_s_) {
      estimate->status = Status::kStaleInput;
    } else if (!HasUsablePointTimestamps(pose_stamp_s)) {
      estimate->status = Status::kDegenerate;
    }
  }

  std::optional<double> CloudEndStamp(const double header_stamp_s) const {
    const auto match = std::find_if(cloud_timings_.rbegin(), cloud_timings_.rend(),
        [header_stamp_s](const CloudTiming& timing) {
          return std::abs(timing.header_stamp_s - header_stamp_s) < 1.0e-6;
        });
    if (match == cloud_timings_.rend()) return std::nullopt;
    return match->end_stamp_s;
  }

  void UpdateLatest(const Estimate& fast, const Estimate& smooth) {
    latest_fast_status_ = fast.status;
    latest_smooth_status_ = smooth.status;
    latest_fast_rms_m_ = fast.fit_rms_m;
    latest_smooth_rms_m_ = smooth.fit_rms_m;
    latest_fast_condition_ = fast.condition_number;
    latest_smooth_condition_ = smooth.condition_number;
    latest_fast_source_mask_ = fast.source_mask;
    latest_smooth_source_mask_ = smooth.source_mask;
  }

  void OnOdometry(const nav_msgs::msg::Odometry::SharedPtr message) {
    const auto callback_start = std::chrono::steady_clock::now();
    const double stamp_s = StampToSeconds(message->header.stamp);
    const auto yaw = QuaternionYaw(message->pose.pose.orientation);
    PlanarPose pose{stamp_s, message->pose.pose.position.x, message->pose.pose.position.y,
                    yaw.value_or(std::numeric_limits<double>::quiet_NaN())};
    odom_frame_mismatch_ = message->child_frame_id != output_frame_;
    const bool finite_pose = stamp_s > 0.0 && std::isfinite(stamp_s) &&
                             std::isfinite(pose.x_m) && std::isfinite(pose.y_m) &&
                             std::isfinite(pose.yaw_rad);
    const bool unusable_deskew_input =
        require_point_timestamps_ && HasUnusablePointTimestamps(stamp_s);
    const Status add_status = (finite_pose && !odom_frame_mismatch_ &&
                               !unusable_deskew_input)
                                  ? estimator_.AddPose(pose)
                                  : Status::kDegenerate;

    last_odom_stamp_s_ = stamp_s;
    last_odom_receive_ = std::chrono::steady_clock::now();
    have_odom_ = true;
    stale_published_ = false;

    if (add_status == Status::kOdomReset) {
      time_offset_estimator_.Reset();
      imu_validator_.Reset();
      latest_offset_ = {};
      latest_offset_measurement_ = {};
      time_offset_holdover_active_ = false;
      imu_time_correction_s_ = 0.0;
      previous_odom_ = pose;
    } else if (add_status == Status::kDegenerate) {
      estimator_.Reset();
      time_offset_estimator_.Reset();
      imu_validator_.Reset();
      latest_offset_ = {};
      latest_offset_measurement_ = {};
      time_offset_holdover_active_ = false;
      imu_time_correction_s_ = 0.0;
      previous_odom_.reset();
    } else if (previous_odom_.has_value()) {
      const double dt = pose.time_s - previous_odom_->time_s;
      if (dt > 1.0e-5 && dt < 1.0) {
        const double yaw_rate = WrapAngle(pose.yaw_rad - previous_odom_->yaw_rad) / dt;
        time_offset_estimator_.AddLidarRate({pose.time_s, yaw_rate});
        UpdateTimeOffset();
      }
      previous_odom_ = pose;
    } else {
      previous_odom_ = pose;
    }

    Estimate fast;
    Estimate smooth;
    if (add_status == Status::kOdomReset) {
      fast.status = Status::kOdomReset;
      smooth.status = Status::kOdomReset;
    } else if (add_status == Status::kDegenerate) {
      fast.status = Status::kDegenerate;
      smooth.status = Status::kDegenerate;
    } else {
      const auto gyro = InterpolatedGyro(stamp_s);
      fast = estimator_.FastEstimate(gyro.value_or(0.0), gyro.has_value());
      ApplyPointCloudGate(&fast, stamp_s);
    }

    PublishEstimate(fast, message->header.stamp, fast_child_frame_, fast_publisher_);
    const auto fast_published = std::chrono::steady_clock::now();
    PushMetric(&fast_processing_ms_,
               std::chrono::duration<double, std::milli>(fast_published - callback_start).count());
    latest_fast_end_to_publish_ms_ = std::numeric_limits<double>::quiet_NaN();
    const auto cloud_end = CloudEndStamp(stamp_s);
    if (cloud_end.has_value()) {
      const double latency_ms = (get_clock()->now().seconds() - *cloud_end) * 1000.0;
      if (std::isfinite(latency_ms) && latency_ms >= 0.0 && latency_ms < 10000.0) {
        latest_fast_end_to_publish_ms_ = latency_ms;
        PushMetric(&fast_end_to_publish_ms_, latency_ms);
      }
    }

    if (add_status != Status::kOdomReset && add_status != Status::kDegenerate) {
      smooth = estimator_.SmoothedEstimate();
      ApplyPointCloudGate(&smooth, stamp_s);
      ValidateWithImu(&smooth);
    }
    PublishEstimate(smooth, message->header.stamp, smooth_child_frame_, smooth_publisher_);
    PushMetric(&smooth_processing_ms_,
               std::chrono::duration<double, std::milli>(
                   std::chrono::steady_clock::now() - callback_start).count());
    UpdateLatest(fast, smooth);
  }

  void ValidateWithImu(Estimate* estimate) {
    latest_imu_normalized_residual_ = std::numeric_limits<double>::quiet_NaN();
    latest_imu_fit_rms_m_s2_ = std::numeric_limits<double>::quiet_NaN();
    latest_imu_condition_ = std::numeric_limits<double>::infinity();
    if (estimate == nullptr || !estimate->valid() || !enable_accel_validation_ ||
        !acceleration_gravity_compensated_ || !latest_imu_gravity_compensated_ ||
        !ImuTimingUsable()) return;
    const auto imu_result = imu_validator_.Estimate();
    latest_imu_fit_rms_m_s2_ = imu_result.fit_rms_m_s2;
    latest_imu_condition_ = imu_result.condition_number;
    if (!imu_result.valid) return;

    const Eigen::Vector2d lidar_to_imu(fixture_imu_x_m_, fixture_imu_y_m_);
    const Eigen::Vector2d predicted_center_to_imu = lidar_to_imu - estimate->center_in_lidar_m;
    const Eigen::Vector2d difference = imu_result.center_to_imu_m - predicted_center_to_imu;
    Eigen::Matrix2d covariance = estimate->covariance_m2 + imu_result.covariance_m2;
    const double angular_position_sigma =
        fixture_axis_angle_sigma_rad_ * predicted_center_to_imu.norm();
    covariance += Eigen::Matrix2d::Identity() *
                  (fixture_xy_sigma_m_ * fixture_xy_sigma_m_ +
                   angular_position_sigma * angular_position_sigma);
    if (!covariance.allFinite()) return;
    const Eigen::LLT<Eigen::Matrix2d> decomposition(covariance);
    if (decomposition.info() != Eigen::Success) return;
    const double normalized_residual = difference.dot(decomposition.solve(difference));
    latest_imu_normalized_residual_ = normalized_residual;
    estimate->source_mask |= kSourceImuAccel;
    if (!std::isfinite(normalized_residual) || normalized_residual > disagreement_chi_square_) {
      estimate->status = Status::kSensorDisagreement;
    }
  }

  emc270_icr_msgs::msg::IcrEstimate ToMessage(
      const Estimate& estimate, const builtin_interfaces::msg::Time& stamp) const {
    emc270_icr_msgs::msg::IcrEstimate message;
    message.header.stamp = stamp;
    message.header.frame_id = output_frame_;
    message.center_in_lidar.x = estimate.center_in_lidar_m.x();
    message.center_in_lidar.y = estimate.center_in_lidar_m.y();
    message.center_in_lidar.z = 0.0;
    message.covariance_xy[0] = estimate.covariance_m2(0, 0);
    message.covariance_xy[1] = estimate.covariance_m2(0, 1);
    message.covariance_xy[2] = estimate.covariance_m2(1, 0);
    message.covariance_xy[3] = estimate.covariance_m2(1, 1);
    message.yaw_rate_rad_s = estimate.yaw_rate_rad_s;
    const std::int64_t window_ns = static_cast<std::int64_t>(estimate.window_s * 1.0e9);
    message.window.sec = static_cast<std::int32_t>(window_ns / 1000000000LL);
    message.window.nanosec = static_cast<std::uint32_t>(window_ns % 1000000000LL);
    message.valid_until = SecondsToStamp(estimate.valid_until_s);
    message.fit_rms_m = estimate.fit_rms_m;
    message.condition_number = estimate.condition_number;
    message.status = static_cast<std::uint8_t>(estimate.status);
    message.source_mask = estimate.source_mask;
    return message;
  }

  void PublishEstimate(
      const Estimate& estimate, const builtin_interfaces::msg::Time& stamp,
      const std::string& child_frame,
      const rclcpp::Publisher<emc270_icr_msgs::msg::IcrEstimate>::SharedPtr& publisher) {
    publisher->publish(ToMessage(estimate, stamp));
    if (!publish_tf_ || !estimate.valid()) return;
    geometry_msgs::msg::TransformStamped transform;
    transform.header.stamp = stamp;
    transform.header.frame_id = output_frame_;
    transform.child_frame_id = child_frame;
    transform.transform.translation.x = estimate.center_in_lidar_m.x();
    transform.transform.translation.y = estimate.center_in_lidar_m.y();
    transform.transform.translation.z = 0.0;
    transform.transform.rotation.w = 1.0;
    tf_broadcaster_->sendTransform(transform);
  }

  void Watchdog() {
    if (!have_odom_ || stale_published_) return;
    const double age_s = std::chrono::duration<double>(std::chrono::steady_clock::now() -
                                                       last_odom_receive_).count();
    if (age_s <= stale_timeout_s_) return;
    Estimate stale;
    stale.status = Status::kStaleInput;
    const auto stamp = SecondsToStamp(last_odom_stamp_s_ + age_s);
    PublishEstimate(stale, stamp, fast_child_frame_, fast_publisher_);
    PublishEstimate(stale, stamp, smooth_child_frame_, smooth_publisher_);
    latest_fast_status_ = Status::kStaleInput;
    latest_smooth_status_ = Status::kStaleInput;
    stale_published_ = true;
  }

  void ProduceDiagnostics(diagnostic_updater::DiagnosticStatusWrapper& diagnostic) {
    const auto now = std::chrono::steady_clock::now();
    const double cloud_age_s = have_point_cloud_
        ? std::chrono::duration<double>(now - last_point_cloud_receive_).count()
        : std::numeric_limits<double>::infinity();
    const double odom_age_s = have_odom_
        ? std::chrono::duration<double>(now - last_odom_receive_).count()
        : std::numeric_limits<double>::infinity();
    const double imu_age_s = have_imu_
        ? std::chrono::duration<double>(now - last_imu_receive_).count()
        : std::numeric_limits<double>::infinity();

    const char* tracking_state = "OUTPUT_ALIVE_DERIVED";
    if (!have_point_cloud_) {
      tracking_state = "WAITING_FOR_POINTCLOUD";
    } else if (cloud_age_s > point_cloud_stale_timeout_s_) {
      tracking_state = "POINTCLOUD_STALE";
    } else if (point_cloud_frame_mismatch_) {
      tracking_state = "POINTCLOUD_FRAME_MISMATCH";
    } else if (!have_odom_) {
      tracking_state = "WAITING_FOR_KISS_ODOMETRY";
    } else if (odom_frame_mismatch_) {
      tracking_state = "ODOMETRY_FRAME_MISMATCH";
    } else if (odom_age_s > stale_timeout_s_) {
      tracking_state = "KISS_OUTPUT_STALLED_DERIVED";
    } else if (latest_smooth_status_ == Status::kOdomReset) {
      tracking_state = "ODOMETRY_RESET_DETECTED";
    }

    const bool critical_imu_error = (latest_imu_mcu_error_ & (1U << 4)) != 0;
    const bool imu_available = ImuTimingUsable() &&
        (!enable_accel_validation_ ||
         ((latest_smooth_source_mask_ & kSourceImuAccel) != 0 &&
          acceleration_gravity_compensated_ && latest_imu_gravity_compensated_));
    const double fast_processing_p95_ms = Percentile95(fast_processing_ms_);
    const double smooth_processing_p95_ms = Percentile95(smooth_processing_ms_);
    const double fast_end_latency_p95_ms = Percentile95(fast_end_to_publish_ms_);

    if (critical_imu_error) {
      diagnostic.summary(diagnostic_msgs::msg::DiagnosticStatus::ERROR,
                         "IMU not recognized by its MCU");
    } else if (point_cloud_frame_mismatch_) {
      diagnostic.summary(diagnostic_msgs::msg::DiagnosticStatus::ERROR,
                         "LiDAR point cloud frame mismatch");
    } else if (require_point_timestamps_ && have_point_cloud_ &&
               !point_timestamps_usable_) {
      diagnostic.summary(diagnostic_msgs::msg::DiagnosticStatus::ERROR,
                         "Per-point timestamps unusable; deskew contract failed");
    } else if (cloud_age_s > point_cloud_stale_timeout_s_ && have_point_cloud_) {
      diagnostic.summary(diagnostic_msgs::msg::DiagnosticStatus::ERROR,
                         "LiDAR point cloud is stale");
    } else if (odom_frame_mismatch_) {
      diagnostic.summary(diagnostic_msgs::msg::DiagnosticStatus::ERROR,
                         "KISS odometry child frame mismatch");
    } else if (!have_odom_) {
      diagnostic.summary(diagnostic_msgs::msg::DiagnosticStatus::WARN,
                         "Waiting for LiDAR odometry");
    } else if (latest_fast_status_ == Status::kStaleInput) {
      diagnostic.summary(diagnostic_msgs::msg::DiagnosticStatus::ERROR,
                         "LiDAR odometry is stale");
    } else if (latest_smooth_status_ == Status::kSensorDisagreement) {
      diagnostic.summary(diagnostic_msgs::msg::DiagnosticStatus::ERROR,
                         "LiDAR and IMU lever-arm estimates disagree");
    } else if (latest_smooth_status_ == Status::kValid) {
      if (!imu_available) {
        diagnostic.summary(diagnostic_msgs::msg::DiagnosticStatus::WARN,
                           "Smoothed ICR valid in LiDAR-only mode");
      } else if ((fast_end_to_publish_ms_.size() >= 20 &&
                  fast_end_latency_p95_ms >= 100.0) ||
                 (smooth_processing_ms_.size() >= 20 &&
                  smooth_processing_p95_ms >= 200.0)) {
        diagnostic.summary(diagnostic_msgs::msg::DiagnosticStatus::WARN,
                           "ICR valid but runtime acceptance target is exceeded");
      } else {
        diagnostic.summary(diagnostic_msgs::msg::DiagnosticStatus::OK, "Smoothed ICR valid");
      }
    } else {
      diagnostic.summary(diagnostic_msgs::msg::DiagnosticStatus::WARN,
                         StatusName(latest_smooth_status_));
    }
    diagnostic.add("fast_status", StatusName(latest_fast_status_));
    diagnostic.add("smoothed_status", StatusName(latest_smooth_status_));
    diagnostic.add("fast_source_mask", static_cast<int>(latest_fast_source_mask_));
    diagnostic.add("smoothed_source_mask", static_cast<int>(latest_smooth_source_mask_));
    diagnostic.add("fast_fit_rms_m", latest_fast_rms_m_);
    diagnostic.add("smoothed_fit_rms_m", latest_smooth_rms_m_);
    diagnostic.add("fast_condition_number", latest_fast_condition_);
    diagnostic.add("smoothed_condition_number", latest_smooth_condition_);
    diagnostic.add("fast_processing_p95_ms", fast_processing_p95_ms);
    diagnostic.add("smoothed_processing_p95_ms", smooth_processing_p95_ms);
    diagnostic.add("processing_sample_count", static_cast<int>(smooth_processing_ms_.size()));
    diagnostic.add("fast_scan_end_to_publish_latest_ms", latest_fast_end_to_publish_ms_);
    diagnostic.add("fast_scan_end_to_publish_p95_ms", fast_end_latency_p95_ms);
    diagnostic.add("fast_scan_end_latency_sample_count",
                   static_cast<int>(fast_end_to_publish_ms_.size()));
    diagnostic.add("point_cloud_age_s", cloud_age_s);
    diagnostic.add("point_cloud_count", point_cloud_count_);
    diagnostic.add("point_cloud_gap_count", point_cloud_gap_count_);
    diagnostic.add("latest_point_count", latest_point_count_);
    diagnostic.add("point_timestamp_usable", point_timestamps_usable_);
    diagnostic.add("point_cloud_frame_mismatch", point_cloud_frame_mismatch_);
    diagnostic.add("point_cloud_expected_frame", point_cloud_frame_);
    diagnostic.add("point_timestamp_span", latest_point_timestamp_span_s_);
    diagnostic.add("point_time_domain_compatible", point_time_domain_compatible_);
    diagnostic.add("kiss_tracking_state", tracking_state);
    diagnostic.add("kiss_tracking_state_source",
                   "derived from cloud/odometry freshness; KISS-ICP v1.3.0 has no status API");
    diagnostic.add("odometry_age_s", odom_age_s);
    diagnostic.add("odometry_frame_mismatch", odom_frame_mismatch_);
    diagnostic.add("odometry_expected_child_frame", output_frame_);
    diagnostic.add("imu_age_s", imu_age_s);
    diagnostic.add("imu_gap_count", imu_gap_count_);
    diagnostic.add("imu_device_dropped", latest_imu_dropped_);
    diagnostic.add("imu_clock_state", static_cast<int>(latest_imu_clock_state_));
    diagnostic.add("imu_clock_residual_ms", latest_imu_clock_residual_ms_);
    diagnostic.add("imu_mcu_error", static_cast<int>(latest_imu_mcu_error_));
    diagnostic.add("imu_gravity_compensated", latest_imu_gravity_compensated_);
    diagnostic.add("imu_accel_bias_calibrated", have_accel_bias_);
    diagnostic.add("imu_accel_bias_sample_count",
                   static_cast<int>(accel_bias_sample_count_));
    diagnostic.add("imu_time_correction_ms", imu_time_correction_s_ * 1000.0);
    diagnostic.add("imu_lidar_rate_correlation", latest_offset_measurement_.correlation);
    diagnostic.add("time_offset_valid", latest_offset_.valid);
    diagnostic.add("time_offset_holdover_active", time_offset_holdover_active_);
    diagnostic.add("imu_lidar_normalized_residual", latest_imu_normalized_residual_);
    diagnostic.add("imu_lever_arm_fit_rms_m_s2", latest_imu_fit_rms_m_s2_);
    diagnostic.add("imu_lever_arm_condition_number", latest_imu_condition_);
    diagnostic.add("pose_count", static_cast<int>(estimator_.pose_count()));
  }
};

}  // namespace emc270::icr

int main(int argc, char** argv) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<emc270::icr::IcrEstimatorNode>());
  rclcpp::shutdown();
  return 0;
}
