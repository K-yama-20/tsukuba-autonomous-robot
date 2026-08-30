#include "adi_imu_tr_driver_ros2/affine_clock_mapper.hpp"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <vector>

namespace adi_imu_tr_driver_ros2 {

AffineClockMapper::AffineClockMapper(AffineClockConfig config) : config_(config) {}

void AffineClockMapper::Reset() {
  samples_.clear();
  last_mcu_us_ = 0;
  last_ros_ns_ = 0;
  last_steady_ns_ = 0;
  have_last_ = false;
  pps_observed_ = false;
  fit_valid_ = false;
  samples_since_fit_ = 0;
  slope_ns_per_us_ = 1000.0;
  intercept_ns_ = 0.0;
  residual_rms_ns_ = std::numeric_limits<double>::infinity();
}

ClockEstimate AffineClockMapper::AddSample(const std::uint64_t mcu_time_us,
                                           const std::int64_t receive_ros_time_ns,
                                           const std::uint64_t receive_steady_time_ns,
                                           const bool pps_edge_observed) {
  if (have_last_) {
    const bool mcu_reset = mcu_time_us < last_mcu_us_;
    const std::int64_t ros_delta = receive_ros_time_ns - last_ros_ns_;
    const std::int64_t steady_delta = static_cast<std::int64_t>(receive_steady_time_ns -
                                                                last_steady_ns_);
    const bool clock_jump = std::llabs(ros_delta - steady_delta) >
                            config_.clock_jump_threshold_ns;
    if (mcu_reset || clock_jump) Reset();
  }

  samples_.push_back({mcu_time_us, receive_ros_time_ns});
  while (samples_.size() > config_.maximum_samples) samples_.pop_front();
  last_mcu_us_ = mcu_time_us;
  last_ros_ns_ = receive_ros_time_ns;
  last_steady_ns_ = receive_steady_time_ns;
  have_last_ = true;
  pps_observed_ = pps_observed_ || pps_edge_observed;
  ++samples_since_fit_;
  const std::size_t interval = std::max<std::size_t>(1, config_.fit_interval_samples);
  if (samples_since_fit_ >= interval || samples_.size() == config_.minimum_samples) {
    Fit();
    samples_since_fit_ = 0;
  }
  return Estimate(mcu_time_us);
}

void AffineClockMapper::Fit() {
  fit_valid_ = false;
  if (samples_.size() < 2) return;

  const double x_origin = static_cast<double>(samples_.front().mcu_us);
  const double y_origin = static_cast<double>(samples_.front().ros_ns);
  std::vector<double> weights(samples_.size(), 1.0);
  double slope = 1000.0;
  double offset = 0.0;

  for (int iteration = 0; iteration < 8; ++iteration) {
    double weight_sum = 0.0;
    double mean_x = 0.0;
    double mean_y = 0.0;
    for (std::size_t i = 0; i < samples_.size(); ++i) {
      const double x = static_cast<double>(samples_[i].mcu_us) - x_origin;
      const double y = static_cast<double>(samples_[i].ros_ns) - y_origin;
      weight_sum += weights[i];
      mean_x += weights[i] * x;
      mean_y += weights[i] * y;
    }
    if (weight_sum <= 0.0) return;
    mean_x /= weight_sum;
    mean_y /= weight_sum;

    double numerator = 0.0;
    double denominator = 0.0;
    for (std::size_t i = 0; i < samples_.size(); ++i) {
      const double x = static_cast<double>(samples_[i].mcu_us) - x_origin;
      const double y = static_cast<double>(samples_[i].ros_ns) - y_origin;
      numerator += weights[i] * (x - mean_x) * (y - mean_y);
      denominator += weights[i] * (x - mean_x) * (x - mean_x);
    }
    if (denominator <= 1.0e-12) return;
    slope = numerator / denominator;
    offset = mean_y - slope * mean_x;

    for (std::size_t i = 0; i < samples_.size(); ++i) {
      const double x = static_cast<double>(samples_[i].mcu_us) - x_origin;
      const double y = static_cast<double>(samples_[i].ros_ns) - y_origin;
      const double residual = std::abs(y - (offset + slope * x));
      weights[i] = residual <= config_.huber_delta_ns
                       ? 1.0
                       : config_.huber_delta_ns / std::max(residual, 1.0);
    }
  }

  double squared_error = 0.0;
  double weight_sum = 0.0;
  for (std::size_t i = 0; i < samples_.size(); ++i) {
    const double x = static_cast<double>(samples_[i].mcu_us) - x_origin;
    const double y = static_cast<double>(samples_[i].ros_ns) - y_origin;
    const double residual = y - (offset + slope * x);
    squared_error += weights[i] * residual * residual;
    weight_sum += weights[i];
  }
  residual_rms_ns_ = std::sqrt(squared_error / std::max(weight_sum, 1.0));
  slope_ns_per_us_ = slope;
  intercept_ns_ = y_origin + offset - slope * x_origin;

  const std::uint64_t span = samples_.back().mcu_us - samples_.front().mcu_us;
  const double drift_ppm = std::abs(slope - 1000.0) / 1000.0 * 1.0e6;
  fit_valid_ = samples_.size() >= config_.minimum_samples &&
               span >= config_.minimum_span_us &&
               residual_rms_ns_ <= config_.maximum_rms_residual_ns &&
               drift_ppm <= config_.maximum_drift_ppm;
}

ClockEstimate AffineClockMapper::Estimate(const std::uint64_t mcu_time_us) const {
  ClockEstimate estimate;
  estimate.slope_ns_per_us = slope_ns_per_us_;
  estimate.residual_ms = residual_rms_ns_ * 1.0e-6;
  if (samples_.empty()) return estimate;

  if (fit_valid_) {
    estimate.ros_time_ns = static_cast<std::int64_t>(
        std::llround(intercept_ns_ + slope_ns_per_us_ * static_cast<double>(mcu_time_us)));
    estimate.state = pps_observed_ ? ClockState::kPpsObserved
                                   : ClockState::kSoftwareLocked;
  } else {
    estimate.ros_time_ns = samples_.back().ros_ns;
    estimate.state = ClockState::kUnlocked;
  }
  return estimate;
}

}  // namespace adi_imu_tr_driver_ros2
