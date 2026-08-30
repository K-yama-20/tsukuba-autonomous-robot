#pragma once

#include <cstddef>
#include <cstdint>
#include <deque>
#include <limits>

namespace adi_imu_tr_driver_ros2 {

enum class ClockState : std::uint8_t {
  kUnlocked = 0,
  kSoftwareLocked = 1,
  kPpsObserved = 2,
};

struct ClockEstimate {
  std::int64_t ros_time_ns{0};
  ClockState state{ClockState::kUnlocked};
  double residual_ms{std::numeric_limits<double>::infinity()};
  double slope_ns_per_us{1000.0};
};

struct AffineClockConfig {
  std::size_t minimum_samples{100};
  std::size_t maximum_samples{5000};
  std::size_t fit_interval_samples{20};
  std::uint64_t minimum_span_us{500000};
  double maximum_rms_residual_ns{2.0e6};
  double maximum_drift_ppm{5000.0};
  double huber_delta_ns{2.5e5};
  std::int64_t clock_jump_threshold_ns{100000000};
};

class AffineClockMapper {
 public:
  explicit AffineClockMapper(AffineClockConfig config = {});

  ClockEstimate AddSample(std::uint64_t mcu_time_us, std::int64_t receive_ros_time_ns,
                          std::uint64_t receive_steady_time_ns, bool pps_edge_observed);
  [[nodiscard]] ClockEstimate Estimate(std::uint64_t mcu_time_us) const;
  void Reset();
  [[nodiscard]] std::size_t sample_count() const { return samples_.size(); }

 private:
  struct Sample {
    std::uint64_t mcu_us;
    std::int64_t ros_ns;
  };

  void Fit();

  AffineClockConfig config_;
  std::deque<Sample> samples_;
  std::uint64_t last_mcu_us_{0};
  std::int64_t last_ros_ns_{0};
  std::uint64_t last_steady_ns_{0};
  bool have_last_{false};
  bool pps_observed_{false};
  bool fit_valid_{false};
  std::size_t samples_since_fit_{0};
  double slope_ns_per_us_{1000.0};
  double intercept_ns_{0.0};
  double residual_rms_ns_{std::numeric_limits<double>::infinity()};
};

}  // namespace adi_imu_tr_driver_ros2
