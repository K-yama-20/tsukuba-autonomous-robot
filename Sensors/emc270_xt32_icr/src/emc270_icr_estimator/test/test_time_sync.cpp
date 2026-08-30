#include "adi_imu_tr_driver_ros2/affine_clock_mapper.hpp"
#include "emc270_icr_estimator/time_offset_estimator.hpp"

#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <iostream>

namespace {

void Require(const bool condition, const char* message) {
  if (!condition) {
    std::cerr << "FAILED: " << message << '\n';
    std::exit(1);
  }
}

}  // namespace

int main() {
  using adi_imu_tr_driver_ros2::AffineClockMapper;
  using adi_imu_tr_driver_ros2::ClockState;

  AffineClockMapper mapper;
  constexpr std::int64_t base_ns = 1'800'000'000'000'000'000LL;
  constexpr double slope = 1000.02;
  adi_imu_tr_driver_ros2::ClockEstimate estimate;
  for (std::uint64_t index = 0; index < 1200; ++index) {
    const std::uint64_t mcu_us = index * 1000;
    const std::int64_t jitter = static_cast<std::int64_t>(40000.0 * std::sin(index * 0.1));
    const std::int64_t outlier = index % 211 == 0 ? 5'000'000 : 0;
    const std::int64_t ros_ns = base_ns + static_cast<std::int64_t>(slope * mcu_us) +
                                jitter + outlier;
    const std::uint64_t steady_ns = 5'000'000'000ULL + index * 1'000'000ULL;
    estimate = mapper.AddSample(mcu_us, ros_ns, steady_ns, index == 1000);
  }
  Require(estimate.state == ClockState::kPpsObserved,
          "PPS edge must be reported without claiming hardware discipline");
  Require(std::abs(estimate.slope_ns_per_us - slope) < 0.05,
          "affine clock drift estimate must be accurate");
  const auto projected = mapper.Estimate(1'500'000);
  const auto expected = base_ns + static_cast<std::int64_t>(slope * 1'500'000);
  Require(std::llabs(projected.ros_time_ns - expected) < 300'000,
          "mapped capture time must be within 0.3 ms");

  const auto reset_by_jump = mapper.AddSample(
      1'201'000, base_ns + static_cast<std::int64_t>(slope * 1'201'000) + 500'000'000,
      5'000'000'000ULL + 1'201'000'000ULL, false);
  Require(reset_by_jump.state == ClockState::kUnlocked && mapper.sample_count() == 1,
          "host ROS clock jump must reset the affine model");

  const auto reset_by_mcu = mapper.AddSample(
      1000, base_ns + 2'000'000'000LL, 7'000'000'000ULL, false);
  Require(reset_by_mcu.state == ClockState::kUnlocked && mapper.sample_count() == 1,
          "MCU reboot/wrap must reset the affine model");

  emc270::icr::TimeOffsetEstimator offset_estimator;
  constexpr double reported_delay = 0.018;
  for (int index = 0; index <= 1000; ++index) {
    const double true_time = index * 0.005;
    const double signal = std::sin(2.3 * true_time) + 0.4 * std::sin(5.1 * true_time);
    offset_estimator.AddImuRate({true_time + reported_delay, signal});
    if (index % 10 == 0) {
      offset_estimator.AddLidarRate({true_time, signal});
    }
  }
  const auto offset = offset_estimator.Estimate();
  Require(offset.valid, "excited angular-rate signals must synchronize");
  Require(std::abs(offset.imu_time_correction_s + reported_delay) <= 0.002,
          "time correction must cancel the simulated IMU timestamp delay");

  emc270::icr::TimeOffsetEstimator unexcited;
  for (int index = 0; index < 100; ++index) {
    const double time = index * 0.05;
    unexcited.AddImuRate({time, 0.2});
    unexcited.AddLidarRate({time, 0.2});
  }
  Require(!unexcited.Estimate().valid,
          "constant angular rate cannot identify a residual time offset");

  emc270::icr::TimeOffsetConfig invalid_config;
  invalid_config.search_step_s = 0.0;
  emc270::icr::TimeOffsetEstimator invalid(invalid_config);
  Require(!invalid.Estimate().valid,
          "an invalid search step must fail closed instead of looping");

  std::cout << "Time synchronization tests passed\n";
  return 0;
}
