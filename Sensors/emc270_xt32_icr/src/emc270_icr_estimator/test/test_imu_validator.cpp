#include "emc270_icr_estimator/imu_lever_arm_validator.hpp"

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

}  // namespace

int main() {
  emc270::icr::ImuLeverArmValidator validator;
  const Eigen::Vector2d expected(0.42, -0.13);
  const double dt = 0.005;
  for (int index = 0; index < 400; ++index) {
    const double time = index * dt;
    const double omega = 0.5 + 0.25 * std::sin(2.0 * time);
    const double alpha = 0.5 * std::cos(2.0 * time);
    Eigen::Matrix2d model;
    model << -omega * omega, -alpha, alpha, -omega * omega;
    Eigen::Vector2d acceleration = model * expected;
    if (index == 211) acceleration += Eigen::Vector2d(5.0, -4.0);
    validator.AddSample({time, acceleration.x(), acceleration.y(), omega, alpha});
  }
  const auto result = validator.Estimate();
  Require(result.valid, "excited IMU motion must be observable");
  Require((result.center_to_imu_m - expected).norm() < 0.003,
          "Huber fit must reject the acceleration outlier");

  emc270::icr::ImuLeverArmValidator stationary;
  for (int index = 0; index < 400; ++index) {
    stationary.AddSample({index * dt, 0.0, 0.0, 0.0, 0.0});
  }
  Require(!stationary.Estimate().valid, "stationary acceleration cannot identify a lever arm");

  emc270::icr::ImuValidatorConfig strict_config;
  strict_config.maximum_fit_rms_m_s2 = 0.05;
  emc270::icr::ImuLeverArmValidator noisy(strict_config);
  for (int index = 0; index < 400; ++index) {
    const double time = index * dt;
    const double omega = 0.5 + 0.25 * std::sin(2.0 * time);
    const double alpha = 0.5 * std::cos(2.0 * time);
    Eigen::Matrix2d model;
    model << -omega * omega, -alpha, alpha, -omega * omega;
    const Eigen::Vector2d unmodelled(0.20 * std::sin(17.0 * time),
                                     0.20 * std::cos(13.0 * time));
    const Eigen::Vector2d acceleration = model * expected + unmodelled;
    noisy.AddSample({time, acceleration.x(), acceleration.y(), omega, alpha});
  }
  Require(!noisy.Estimate().valid,
          "high acceleration residual must not count as an independent validation");

  std::cout << "IMU validator tests passed\n";
  return 0;
}
