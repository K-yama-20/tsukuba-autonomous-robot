#include "emc270_icr_estimator/imu_lever_arm_validator.hpp"

#include <Eigen/Cholesky>
#include <Eigen/SVD>

#include <algorithm>
#include <cmath>

namespace emc270::icr {

ImuLeverArmValidator::ImuLeverArmValidator(ImuValidatorConfig config) : config_(config) {}

void ImuLeverArmValidator::Reset() { samples_.clear(); }

void ImuLeverArmValidator::AddSample(const ImuKinematicSample& sample) {
  if (!std::isfinite(sample.time_s) || !std::isfinite(sample.acceleration_x_m_s2) ||
      !std::isfinite(sample.acceleration_y_m_s2) ||
      !std::isfinite(sample.yaw_rate_rad_s) ||
      !std::isfinite(sample.yaw_acceleration_rad_s2)) {
    return;
  }
  if (!samples_.empty() && sample.time_s <= samples_.back().time_s) return;
  samples_.push_back(sample);
  while (samples_.size() > 2 && samples_.front().time_s < sample.time_s - config_.window_s) {
    samples_.pop_front();
  }
}

LeverArmResult ImuLeverArmValidator::Estimate() const {
  LeverArmResult result;
  if (samples_.size() < config_.minimum_samples) return result;

  const Eigen::Index rows = static_cast<Eigen::Index>(samples_.size() * 2);
  Eigen::MatrixXd design(rows, 2);
  Eigen::VectorXd observations(rows);
  std::size_t excited = 0;
  for (std::size_t i = 0; i < samples_.size(); ++i) {
    const auto& sample = samples_[i];
    const double omega_squared = sample.yaw_rate_rad_s * sample.yaw_rate_rad_s;
    const double alpha = sample.yaw_acceleration_rad_s2;
    const Eigen::Index row = static_cast<Eigen::Index>(2 * i);
    design.row(row) << -omega_squared, -alpha;
    design.row(row + 1) << alpha, -omega_squared;
    observations(row) = sample.acceleration_x_m_s2;
    observations(row + 1) = sample.acceleration_y_m_s2;
    if (std::abs(sample.yaw_rate_rad_s) >= config_.minimum_yaw_rate_rad_s) ++excited;
  }
  if (excited < config_.minimum_samples / 2) return result;

  Eigen::VectorXd sample_weights = Eigen::VectorXd::Ones(
      static_cast<Eigen::Index>(samples_.size()));
  Eigen::Vector2d solution = Eigen::Vector2d::Zero();
  double condition_number = std::numeric_limits<double>::infinity();
  for (int iteration = 0; iteration < 8; ++iteration) {
    Eigen::MatrixXd weighted_design = design;
    Eigen::VectorXd weighted_observations = observations;
    for (std::size_t i = 0; i < samples_.size(); ++i) {
      const double scale = std::sqrt(sample_weights(static_cast<Eigen::Index>(i)));
      weighted_design.block<2, 2>(static_cast<Eigen::Index>(2 * i), 0) *= scale;
      weighted_observations.segment<2>(static_cast<Eigen::Index>(2 * i)) *= scale;
    }
    Eigen::JacobiSVD<Eigen::MatrixXd> svd(weighted_design,
                                          Eigen::ComputeThinU | Eigen::ComputeThinV);
    const auto singular = svd.singularValues();
    if (singular.size() < 2 || singular(1) <= 1.0e-12) return result;
    condition_number = singular(0) / singular(1);
    solution = svd.solve(weighted_observations);
    const Eigen::VectorXd residual = observations - design * solution;
    for (std::size_t i = 0; i < samples_.size(); ++i) {
      const double norm = residual.segment<2>(static_cast<Eigen::Index>(2 * i)).norm();
      sample_weights(static_cast<Eigen::Index>(i)) =
          norm <= config_.huber_delta_m_s2
              ? 1.0
              : config_.huber_delta_m_s2 / std::max(norm, 1.0e-12);
    }
  }
  result.condition_number = condition_number;
  if (condition_number > config_.maximum_condition_number) return result;

  const Eigen::VectorXd residual = observations - design * solution;
  double squared_error = 0.0;
  double weight_sum = 0.0;
  Eigen::Matrix2d normal = Eigen::Matrix2d::Zero();
  for (std::size_t i = 0; i < samples_.size(); ++i) {
    const double weight = sample_weights(static_cast<Eigen::Index>(i));
    const Eigen::Index row = static_cast<Eigen::Index>(2 * i);
    squared_error += weight * residual.segment<2>(row).squaredNorm();
    normal += weight * design.block<2, 2>(row, 0).transpose() * design.block<2, 2>(row, 0);
    weight_sum += 2.0 * weight;
  }
  result.fit_rms_m_s2 = std::sqrt(squared_error / std::max(weight_sum, 1.0));
  if (!std::isfinite(result.fit_rms_m_s2) ||
      result.fit_rms_m_s2 > config_.maximum_fit_rms_m_s2) {
    return result;
  }
  Eigen::LDLT<Eigen::Matrix2d> decomposition(normal);
  if (decomposition.info() != Eigen::Success) return result;
  const double variance = squared_error / std::max(1.0, weight_sum - 2.0);
  result.covariance_m2 = decomposition.solve(Eigen::Matrix2d::Identity()) * variance;
  result.center_to_imu_m = solution;
  const double trace = result.covariance_m2.trace();
  const double determinant = result.covariance_m2(0, 0) * result.covariance_m2(1, 1) -
                             result.covariance_m2(0, 1) * result.covariance_m2(1, 0);
  const double discriminant = std::max(0.0, trace * trace - 4.0 * determinant);
  const double largest_variance = 0.5 * (trace + std::sqrt(discriminant));
  result.valid = result.center_to_imu_m.allFinite() && result.covariance_m2.allFinite() &&
                 std::isfinite(largest_variance) && largest_variance >= 0.0 &&
                 std::sqrt(largest_variance) <= config_.maximum_position_stddev_m;
  return result;
}

}  // namespace emc270::icr
