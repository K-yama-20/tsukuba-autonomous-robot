#pragma once

#include <cstddef>
#include <deque>

namespace emc270::icr {

struct AngularRateSample {
  double time_s{0.0};
  double rate_rad_s{0.0};
};

struct TimeOffsetResult {
  bool valid{false};
  double imu_time_correction_s{0.0};
  double correlation{0.0};
  std::size_t matched_samples{0};
};

struct TimeOffsetConfig {
  double window_s{5.0};
  double maximum_offset_s{0.050};
  double search_step_s{0.001};
  double minimum_rate_standard_deviation{0.05};
  double minimum_correlation{0.80};
  std::size_t minimum_matched_samples{20};
};

class TimeOffsetEstimator {
 public:
  explicit TimeOffsetEstimator(TimeOffsetConfig config = {});

  void AddLidarRate(const AngularRateSample& sample);
  void AddImuRate(const AngularRateSample& sample);
  void Reset();
  [[nodiscard]] TimeOffsetResult Estimate() const;

 private:
  TimeOffsetConfig config_;
  std::deque<AngularRateSample> lidar_;
  std::deque<AngularRateSample> imu_;
};

}  // namespace emc270::icr
