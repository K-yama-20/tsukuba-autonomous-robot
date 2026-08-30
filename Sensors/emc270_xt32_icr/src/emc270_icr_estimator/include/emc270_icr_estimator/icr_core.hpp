#pragma once

#include <Eigen/Core>

#include <cstddef>
#include <cstdint>
#include <deque>
#include <limits>

namespace emc270::icr {

enum class Status : std::uint8_t {
  kUninitialized = 0,
  kValid = 1,
  kLowYaw = 2,
  kDegenerate = 3,
  kStaleInput = 4,
  kOdomReset = 5,
  kExcessResidual = 6,
  kSensorDisagreement = 7,
};

enum SourceMask : std::uint8_t {
  kSourceLidar = 1,
  kSourceImuGyro = 2,
  kSourceImuAccel = 4,
};

struct PlanarPose {
  double time_s{0.0};
  double x_m{0.0};
  double y_m{0.0};
  double yaw_rad{0.0};
};

struct Estimate {
  Status status{Status::kUninitialized};
  Eigen::Vector2d center_in_lidar_m{Eigen::Vector2d::Constant(
      std::numeric_limits<double>::quiet_NaN())};
  Eigen::Matrix2d covariance_m2{Eigen::Matrix2d::Constant(
      std::numeric_limits<double>::quiet_NaN())};
  double yaw_rate_rad_s{0.0};
  double window_s{0.0};
  double valid_until_s{0.0};
  double fit_rms_m{std::numeric_limits<double>::quiet_NaN()};
  double condition_number{std::numeric_limits<double>::infinity()};
  std::uint8_t source_mask{kSourceLidar};

  [[nodiscard]] bool valid() const { return status == Status::kValid; }
};

struct EstimatorConfig {
  double fast_window_s{0.10};
  double smooth_window_s{2.0};
  double fast_validity_s{0.15};
  double smooth_validity_s{0.25};
  double minimum_yaw_rate_rad_s{0.10};
  double minimum_smooth_yaw_rad{0.2617993877991494};  // 15 degrees
  std::size_t minimum_smooth_samples{8};
  double huber_delta_m{0.02};
  double maximum_fit_rms_m{0.05};
  double maximum_condition_number{1.0e6};
  double odom_reset_gap_s{1.0};
  double odom_reset_translation_m{1.0};
  double odom_reset_yaw_rad{1.0};
  double velocity_sigma_m_s{0.02};
  double yaw_rate_sigma_rad_s{0.02};
  double imu_gyro_weight{0.20};
  double imu_gyro_max_disagreement_rad_s{0.10};
};

class IcrEstimatorCore {
 public:
  explicit IcrEstimatorCore(EstimatorConfig config = {});

  Status AddPose(const PlanarPose& pose);
  void Reset();

  [[nodiscard]] Estimate FastEstimate(double imu_gyro_z_rad_s = 0.0,
                                      bool imu_gyro_valid = false) const;
  [[nodiscard]] Estimate SmoothedEstimate() const;
  [[nodiscard]] std::size_t pose_count() const { return poses_.size(); }

 private:
  EstimatorConfig config_;
  std::deque<PlanarPose> poses_;
};

double WrapAngle(double angle_rad);

}  // namespace emc270::icr
