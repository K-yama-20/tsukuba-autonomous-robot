#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <iomanip>
#include <sstream>
#include <string>

#include "adi_imu_tr_driver_ros2/affine_clock_mapper.hpp"

int main()
{
  adi_imu_tr_driver_ros2::AffineClockConfig config;
  config.minimum_samples = 20;
  config.maximum_samples = 100;
  config.fit_interval_samples = 1;
  config.minimum_span_us = 500000;
  config.maximum_rms_residual_ns = 2.0e6;
  config.maximum_drift_ppm = 5000.0;
  adi_imu_tr_driver_ros2::AffineClockMapper mapper(config);

  constexpr std::int64_t host_epoch_ns = 1'800'000'000'000'000'000LL;
  constexpr std::int64_t fixed_usb_bias_ns = 40'000'000LL;
  adi_imu_tr_driver_ros2::ClockEstimate estimate;
  for (std::uint64_t i = 0; i < 80; ++i) {
    const std::uint64_t mcu_us = i * 10000;
    const std::int64_t receive_ns = host_epoch_ns +
        static_cast<std::int64_t>(mcu_us * 1000) + fixed_usb_bias_ns;
    estimate = mapper.AddSample(mcu_us, receive_ns, i * 10000000ULL, false);
    if (i < 19) assert(estimate.state == adi_imu_tr_driver_ros2::ClockState::kUnlocked);
  }

  assert(estimate.state == adi_imu_tr_driver_ros2::ClockState::kSoftwareLocked);
  assert(estimate.residual_ms < 0.01);
  const auto expected_mapped_ns = host_epoch_ns + 790000000LL + fixed_usb_bias_ns;
  assert(std::llabs(estimate.ros_time_ns - expected_mapped_ns) < 1000);

  const auto pps = mapper.AddSample(800000, host_epoch_ns + 840000000LL,
                                     800000000ULL, true);
  assert(pps.state == adi_imu_tr_driver_ros2::ClockState::kPpsObserved);
  assert(std::llabs(pps.ros_time_ns - (host_epoch_ns + 840000000LL)) < 1000);

  // The JSON status uses the same nanosecond-to-double conversion and
  // setprecision(17) as the ROS driver; ensure epoch values round-trip closely
  // enough to pair status with the Imu header stamp.
  const std::int64_t ros_stamp_ns = 1800000000123456789LL;
  std::ostringstream status;
  status << std::setprecision(17) << (ros_stamp_ns * 1.0e-9);
  const double status_seconds = std::stod(status.str());
  const double imu_seconds = ros_stamp_ns * 1.0e-9;
  assert(std::abs(status_seconds - imu_seconds) < 1.0e-6);

  mapper.Reset();
  assert(mapper.sample_count() == 0);
  const auto unlocked = mapper.Estimate(1);
  assert(unlocked.state == adi_imu_tr_driver_ros2::ClockState::kUnlocked);
  std::cout << "affine mapper synthetic clock checks passed\n";
}
