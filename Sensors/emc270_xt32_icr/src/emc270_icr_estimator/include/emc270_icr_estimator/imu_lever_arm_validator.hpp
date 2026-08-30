#pragma once

#include <Eigen/Core>

#include <cstddef>
#include <deque>
#include <limits>

namespace emc270::icr {

struct ImuKinematicSample {
  double time_s{0.0};
  double acceleration_x_m_s2{0.0};
  double acceleration_y_m_s2{0.0};
  double yaw_rate_rad_s{0.0};
  double yaw_acceleration_rad_s2{0.0};
};

struct LeverArmResult {
  bool valid{false};
  Eigen::Vector2d center_to_imu_m{Eigen::Vector2d::Zero()};
  Eigen::Matrix2d covariance_m2{Eigen::Matrix2d::Constant(
      std::numeric_limits<double>::quiet_NaN())};
  double fit_rms_m_s2{std::numeric_limits<double>::quiet_NaN()};
  double condition_number{std::numeric_limits<double>::infinity()};
};

struct ImuValidatorConfig {
  double window_s{2.0};
  std::size_t minimum_samples{50};
  double minimum_yaw_rate_rad_s{0.10};
  double huber_delta_m_s2{0.20};
  double maximum_condition_number{1.0e5};
  double maximum_fit_rms_m_s2{0.50};
  double maximum_position_stddev_m{0.05};
};

class ImuLeverArmValidator {
 public:
  explicit ImuLeverArmValidator(ImuValidatorConfig config = {});

  void AddSample(const ImuKinematicSample& sample);
  void Reset();
  [[nodiscard]] LeverArmResult Estimate() const;

 private:
  ImuValidatorConfig config_;
  std::deque<ImuKinematicSample> samples_;
};

}  // namespace emc270::icr
