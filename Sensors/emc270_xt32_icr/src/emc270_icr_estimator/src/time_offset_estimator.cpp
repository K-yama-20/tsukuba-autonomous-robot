#include "emc270_icr_estimator/time_offset_estimator.hpp"

#include <algorithm>
#include <cmath>
#include <iterator>
#include <optional>
#include <vector>

namespace emc270::icr {
namespace {

std::optional<double> Interpolate(const std::deque<AngularRateSample>& samples,
                                  const double time_s) {
  if (samples.size() < 2 || time_s < samples.front().time_s || time_s > samples.back().time_s) {
    return std::nullopt;
  }
  const auto upper = std::lower_bound(
      samples.begin(), samples.end(), time_s,
      [](const AngularRateSample& sample, const double value) { return sample.time_s < value; });
  if (upper == samples.begin()) return upper->rate_rad_s;
  if (upper == samples.end()) return samples.back().rate_rad_s;
  const auto lower = std::prev(upper);
  const double span = upper->time_s - lower->time_s;
  if (span <= 0.0) return std::nullopt;
  const double fraction = (time_s - lower->time_s) / span;
  return lower->rate_rad_s + fraction * (upper->rate_rad_s - lower->rate_rad_s);
}

double Correlation(const std::vector<double>& lhs, const std::vector<double>& rhs,
                   double* standard_deviation) {
  if (lhs.size() != rhs.size() || lhs.size() < 2) return 0.0;
  double lhs_mean = 0.0;
  double rhs_mean = 0.0;
  for (std::size_t i = 0; i < lhs.size(); ++i) {
    lhs_mean += lhs[i];
    rhs_mean += rhs[i];
  }
  lhs_mean /= static_cast<double>(lhs.size());
  rhs_mean /= static_cast<double>(rhs.size());
  double cross = 0.0;
  double lhs_squared = 0.0;
  double rhs_squared = 0.0;
  for (std::size_t i = 0; i < lhs.size(); ++i) {
    const double l = lhs[i] - lhs_mean;
    const double r = rhs[i] - rhs_mean;
    cross += l * r;
    lhs_squared += l * l;
    rhs_squared += r * r;
  }
  *standard_deviation = std::sqrt(lhs_squared / static_cast<double>(lhs.size()));
  const double denominator = std::sqrt(lhs_squared * rhs_squared);
  return denominator > 1.0e-12 ? cross / denominator : 0.0;
}

}  // namespace

TimeOffsetEstimator::TimeOffsetEstimator(TimeOffsetConfig config) : config_(config) {}

void TimeOffsetEstimator::Reset() {
  lidar_.clear();
  imu_.clear();
}

void TimeOffsetEstimator::AddLidarRate(const AngularRateSample& sample) {
  if (!std::isfinite(sample.time_s) || !std::isfinite(sample.rate_rad_s)) return;
  if (!lidar_.empty() && sample.time_s <= lidar_.back().time_s) return;
  lidar_.push_back(sample);
  while (lidar_.size() > 2 && lidar_.front().time_s < sample.time_s - config_.window_s) {
    lidar_.pop_front();
  }
}

void TimeOffsetEstimator::AddImuRate(const AngularRateSample& sample) {
  if (!std::isfinite(sample.time_s) || !std::isfinite(sample.rate_rad_s)) return;
  if (!imu_.empty() && sample.time_s <= imu_.back().time_s) return;
  imu_.push_back(sample);
  while (imu_.size() > 2 && imu_.front().time_s < sample.time_s - config_.window_s -
                                                     config_.maximum_offset_s) {
    imu_.pop_front();
  }
}

TimeOffsetResult TimeOffsetEstimator::Estimate() const {
  TimeOffsetResult best;
  if (!std::isfinite(config_.maximum_offset_s) || config_.maximum_offset_s < 0.0 ||
      !std::isfinite(config_.search_step_s) || config_.search_step_s <= 0.0) {
    return best;
  }
  if (lidar_.size() < config_.minimum_matched_samples || imu_.size() < 2) return best;

  for (double correction = -config_.maximum_offset_s;
       correction <= config_.maximum_offset_s + 0.5 * config_.search_step_s;
       correction += config_.search_step_s) {
    std::vector<double> lidar_values;
    std::vector<double> imu_values;
    lidar_values.reserve(lidar_.size());
    imu_values.reserve(lidar_.size());
    for (const auto& lidar_sample : lidar_) {
      // Corrected IMU time is raw_time + correction. Therefore the raw sample
      // corresponding to a LiDAR time is queried at lidar_time - correction.
      const auto imu_value = Interpolate(imu_, lidar_sample.time_s - correction);
      if (!imu_value.has_value()) continue;
      lidar_values.push_back(lidar_sample.rate_rad_s);
      imu_values.push_back(*imu_value);
    }
    if (lidar_values.size() < config_.minimum_matched_samples) continue;
    double standard_deviation = 0.0;
    const double correlation = Correlation(lidar_values, imu_values, &standard_deviation);
    if (correlation > best.correlation) {
      best.correlation = correlation;
      best.imu_time_correction_s = correction;
      best.matched_samples = lidar_values.size();
      best.valid = standard_deviation >= config_.minimum_rate_standard_deviation &&
                   correlation >= config_.minimum_correlation;
    }
  }
  return best;
}

}  // namespace emc270::icr
