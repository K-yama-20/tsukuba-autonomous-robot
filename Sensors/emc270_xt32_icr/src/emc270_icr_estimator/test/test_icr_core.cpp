#include "emc270_icr_estimator/icr_core.hpp"

#include <Eigen/Core>

#include <cmath>
#include <cstdlib>
#include <iostream>

namespace {

void Require(const bool condition, const char* message) {
  if (!condition) {
    std::cerr << "FAILED: " << message << '\n';
    std::exit(1);
  }
}

emc270::icr::PlanarPose CircularPose(const double time_s, const double yaw_rate,
                                     const Eigen::Vector2d& world_center,
                                     const Eigen::Vector2d& center_to_lidar) {
  const double yaw = yaw_rate * time_s;
  Eigen::Matrix2d rotation;
  rotation << std::cos(yaw), -std::sin(yaw), std::sin(yaw), std::cos(yaw);
  const Eigen::Vector2d position = world_center + rotation * center_to_lidar;
  return {time_s, position.x(), position.y(), yaw};
}

}  // namespace

int main() {
  using emc270::icr::IcrEstimatorCore;
  using emc270::icr::PlanarPose;
  using emc270::icr::Status;

  const Eigen::Vector2d center(1.0, -0.5);
  const Eigen::Vector2d center_to_lidar(0.30, -0.20);
  IcrEstimatorCore estimator;
  for (int index = 0; index < 100; ++index) {
    estimator.AddPose(CircularPose(index * 0.05, 0.55, center, center_to_lidar));
  }
  const auto smooth = estimator.SmoothedEstimate();
  Require(smooth.status == Status::kValid, "clean circle must be observable");
  Require((smooth.center_in_lidar_m + center_to_lidar).norm() < 1.0e-6,
          "smoothed clean-circle error must be below one micrometre");
  const auto fast = estimator.FastEstimate(0.55, true);
  Require(fast.status == Status::kValid, "fast clean circle must be valid");
  Require((fast.center_in_lidar_m + center_to_lidar).norm() < 1.0e-6,
          "fast clean-circle error must be below one micrometre");
  Require((fast.source_mask & emc270::icr::kSourceImuGyro) != 0,
          "locked gyro must be recorded as a source");
  const auto rejected_gyro = estimator.FastEstimate(1.2, true);
  Require((rejected_gyro.source_mask & emc270::icr::kSourceImuGyro) == 0,
          "disagreeing gyro must not affect the fast estimate");
  Require((rejected_gyro.center_in_lidar_m + center_to_lidar).norm() < 1.0e-6,
          "rejected gyro must leave the LiDAR estimate unchanged");

  IcrEstimatorCore clockwise;
  for (int index = 0; index < 100; ++index) {
    clockwise.AddPose(CircularPose(index * 0.05, -0.45, center, center_to_lidar));
  }
  const auto clockwise_result = clockwise.SmoothedEstimate();
  Require(clockwise_result.valid(), "clockwise motion must be valid");
  Require((clockwise_result.center_in_lidar_m + center_to_lidar).norm() < 1.0e-6,
          "clockwise sign must be correct");

  IcrEstimatorCore straight;
  for (int index = 0; index < 50; ++index) {
    straight.AddPose({index * 0.05, index * 0.01, 0.0, 0.0});
  }
  const auto straight_fast = straight.FastEstimate();
  Require(straight_fast.status == Status::kLowYaw,
          "straight motion must not produce a finite ICR");
  Require(!straight_fast.center_in_lidar_m.allFinite(),
          "invalid estimates must not expose a plausible zero centre");
  Require(straight.SmoothedEstimate().status == Status::kLowYaw,
          "straight smooth estimate must be invalid");

  IcrEstimatorCore stopped;
  for (int index = 0; index < 50; ++index) {
    stopped.AddPose({index * 0.05, 0.0, 0.0, 0.0});
  }
  Require(stopped.FastEstimate().status == Status::kLowYaw,
          "stopped motion must not produce a finite ICR");
  Require(stopped.SmoothedEstimate().status == Status::kLowYaw,
          "stopped smooth estimate must be invalid");

  IcrEstimatorCore changing;
  for (int index = 0; index < 100; ++index) {
    const double time = index * 0.05;
    const Eigen::Vector2d moving_center = center + Eigen::Vector2d(0.15 * std::sin(5.0 * time), 0.0);
    changing.AddPose(CircularPose(time, 0.55, moving_center, center_to_lidar));
  }
  Require(changing.SmoothedEstimate().status == Status::kExcessResidual,
          "rapidly moving ICR must fail the constant-window model");

  IcrEstimatorCore reset;
  reset.AddPose({0.0, 0.0, 0.0, 0.0});
  Require(reset.AddPose({2.0, 0.0, 0.0, 0.0}) == Status::kOdomReset,
          "one-second input gap must reset odometry history");
  Require(reset.pose_count() == 1, "reset must discard the pre-gap pose window");

  IcrEstimatorCore backwards_time;
  backwards_time.AddPose({1.0, 0.0, 0.0, 0.0});
  Require(backwards_time.AddPose({0.9, 0.0, 0.0, 0.0}) == Status::kOdomReset,
          "non-monotonic KISS time must reset odometry history");

  std::cout << "ICR core tests passed\n";
  return 0;
}
