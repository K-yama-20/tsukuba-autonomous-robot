#include "emc270_icr_estimator/icr_core.hpp"

#include <Eigen/Cholesky>
#include <Eigen/SVD>

#include <algorithm>
#include <cmath>
#include <iterator>
#include <vector>

namespace emc270::icr {
namespace {

constexpr double kPi = 3.14159265358979323846;

Eigen::Matrix2d Rotation(const double yaw) {
  const double c = std::cos(yaw);
  const double s = std::sin(yaw);
  Eigen::Matrix2d rotation;
  rotation << c, -s, s, c;
  return rotation;
}

double UnwrappedYawSpan(const std::vector<PlanarPose>& poses) {
  if (poses.size() < 2) return 0.0;
  double unwrapped = poses.front().yaw_rad;
  double minimum = unwrapped;
  double maximum = unwrapped;
  double previous = poses.front().yaw_rad;
  for (std::size_t i = 1; i < poses.size(); ++i) {
    unwrapped += WrapAngle(poses[i].yaw_rad - previous);
    previous = poses[i].yaw_rad;
    minimum = std::min(minimum, unwrapped);
    maximum = std::max(maximum, unwrapped);
  }
  return maximum - minimum;
}

double FitYawRate(const std::vector<PlanarPose>& poses) {
  if (poses.size() < 2) return 0.0;
  const double t0 = poses.front().time_s;
  std::vector<double> yaw(poses.size());
  yaw[0] = poses.front().yaw_rad;
  for (std::size_t i = 1; i < poses.size(); ++i) {
    yaw[i] = yaw[i - 1] + WrapAngle(poses[i].yaw_rad - poses[i - 1].yaw_rad);
  }
  double mean_t = 0.0;
  double mean_yaw = 0.0;
  for (std::size_t i = 0; i < poses.size(); ++i) {
    mean_t += poses[i].time_s - t0;
    mean_yaw += yaw[i];
  }
  mean_t /= static_cast<double>(poses.size());
  mean_yaw /= static_cast<double>(poses.size());
  double numerator = 0.0;
  double denominator = 0.0;
  for (std::size_t i = 0; i < poses.size(); ++i) {
    const double dt = poses[i].time_s - t0 - mean_t;
    numerator += dt * (yaw[i] - mean_yaw);
    denominator += dt * dt;
  }
  return denominator > 1.0e-12 ? numerator / denominator : 0.0;
}

}  // namespace

double WrapAngle(double angle_rad) {
  while (angle_rad > kPi) angle_rad -= 2.0 * kPi;
  while (angle_rad < -kPi) angle_rad += 2.0 * kPi;
  return angle_rad;
}

IcrEstimatorCore::IcrEstimatorCore(EstimatorConfig config) : config_(config) {}

void IcrEstimatorCore::Reset() { poses_.clear(); }

Status IcrEstimatorCore::AddPose(const PlanarPose& pose) {
  if (!std::isfinite(pose.time_s) || !std::isfinite(pose.x_m) ||
      !std::isfinite(pose.y_m) || !std::isfinite(pose.yaw_rad)) {
    return Status::kDegenerate;
  }
  if (!poses_.empty()) {
    const auto& previous = poses_.back();
    const double dt = pose.time_s - previous.time_s;
    const double translation = std::hypot(pose.x_m - previous.x_m, pose.y_m - previous.y_m);
    const double yaw_change = std::abs(WrapAngle(pose.yaw_rad - previous.yaw_rad));
    if (dt <= 0.0 || dt > config_.odom_reset_gap_s ||
        translation > config_.odom_reset_translation_m ||
        yaw_change > config_.odom_reset_yaw_rad) {
      poses_.clear();
      poses_.push_back(pose);
      return Status::kOdomReset;
    }
  }
  poses_.push_back(pose);
  const double keep_after = pose.time_s - std::max(config_.smooth_window_s, config_.fast_window_s) - 0.1;
  while (poses_.size() > 2 && poses_.front().time_s < keep_after) poses_.pop_front();
  return Status::kUninitialized;
}

Estimate IcrEstimatorCore::FastEstimate(const double imu_gyro_z_rad_s,
                                        const bool imu_gyro_valid) const {
  Estimate result;
  if (poses_.size() < 2) return result;

  const auto& last = poses_.back();
  auto first_it = poses_.begin();
  const double threshold = last.time_s - config_.fast_window_s;
  while (std::next(first_it) != poses_.end() && std::next(first_it)->time_s <= threshold) {
    ++first_it;
  }
  const auto& first = *first_it;
  const double dt = last.time_s - first.time_s;
  result.window_s = dt;
  result.valid_until_s = last.time_s + config_.fast_validity_s;
  if (dt <= 1.0e-6) {
    result.status = Status::kDegenerate;
    return result;
  }

  const Eigen::Vector2d world_delta(last.x_m - first.x_m, last.y_m - first.y_m);
  const Eigen::Vector2d translation = Rotation(first.yaw_rad).transpose() * world_delta;
  const double theta = WrapAngle(last.yaw_rad - first.yaw_rad);

  Eigen::Vector2d integrated_velocity = translation;
  if (std::abs(theta) > 1.0e-8) {
    const double a = std::sin(theta) / theta;
    const double b = (1.0 - std::cos(theta)) / theta;
    const double determinant = a * a + b * b;
    Eigen::Matrix2d inverse_v;
    inverse_v << a, b, -b, a;
    integrated_velocity = inverse_v * translation / determinant;
  }
  const Eigen::Vector2d velocity = integrated_velocity / dt;
  const double lidar_yaw_rate = theta / dt;
  double yaw_rate = lidar_yaw_rate;
  result.source_mask = kSourceLidar;
  if (imu_gyro_valid && std::isfinite(imu_gyro_z_rad_s) &&
      std::abs(imu_gyro_z_rad_s - lidar_yaw_rate) <=
          config_.imu_gyro_max_disagreement_rad_s) {
    const double weight = std::clamp(config_.imu_gyro_weight, 0.0, 1.0);
    yaw_rate = (1.0 - weight) * lidar_yaw_rate + weight * imu_gyro_z_rad_s;
    result.source_mask |= kSourceImuGyro;
  }
  result.yaw_rate_rad_s = yaw_rate;
  if (std::abs(yaw_rate) < config_.minimum_yaw_rate_rad_s) {
    result.status = Status::kLowYaw;
    return result;
  }

  result.center_in_lidar_m = Eigen::Vector2d(-velocity.y() / yaw_rate,
                                             velocity.x() / yaw_rate);

  Eigen::Matrix<double, 2, 3> jacobian = Eigen::Matrix<double, 2, 3>::Zero();
  jacobian(0, 1) = -1.0 / yaw_rate;
  jacobian(0, 2) = velocity.y() / (yaw_rate * yaw_rate);
  jacobian(1, 0) = 1.0 / yaw_rate;
  jacobian(1, 2) = -velocity.x() / (yaw_rate * yaw_rate);
  Eigen::Matrix3d twist_covariance = Eigen::Matrix3d::Zero();
  twist_covariance(0, 0) = config_.velocity_sigma_m_s * config_.velocity_sigma_m_s;
  twist_covariance(1, 1) = config_.velocity_sigma_m_s * config_.velocity_sigma_m_s;
  twist_covariance(2, 2) = config_.yaw_rate_sigma_rad_s * config_.yaw_rate_sigma_rad_s;
  result.covariance_m2 = jacobian * twist_covariance * jacobian.transpose();
  result.fit_rms_m = 0.0;
  result.condition_number = 1.0 / std::max(std::abs(theta), 1.0e-12);
  result.status = Status::kValid;
  return result;
}

Estimate IcrEstimatorCore::SmoothedEstimate() const {
  Estimate result;
  if (poses_.size() < config_.minimum_smooth_samples) return result;

  const double newest = poses_.back().time_s;
  std::vector<PlanarPose> selected;
  selected.reserve(poses_.size());
  for (const auto& pose : poses_) {
    if (pose.time_s >= newest - config_.smooth_window_s) selected.push_back(pose);
  }
  if (selected.size() < config_.minimum_smooth_samples) return result;

  result.window_s = selected.back().time_s - selected.front().time_s;
  result.valid_until_s = selected.back().time_s + config_.smooth_validity_s;
  result.yaw_rate_rad_s = FitYawRate(selected);
  result.source_mask = kSourceLidar;
  if (std::abs(result.yaw_rate_rad_s) < config_.minimum_yaw_rate_rad_s ||
      UnwrappedYawSpan(selected) < config_.minimum_smooth_yaw_rad) {
    result.status = Status::kLowYaw;
    return result;
  }

  const Eigen::Index rows = static_cast<Eigen::Index>(selected.size() * 2);
  Eigen::MatrixXd design(rows, 4);
  Eigen::VectorXd observations(rows);
  for (std::size_t i = 0; i < selected.size(); ++i) {
    const double c = std::cos(selected[i].yaw_rad);
    const double s = std::sin(selected[i].yaw_rad);
    const Eigen::Index row = static_cast<Eigen::Index>(2 * i);
    design.row(row) << 1.0, 0.0, c, -s;
    design.row(row + 1) << 0.0, 1.0, s, c;
    observations(row) = selected[i].x_m;
    observations(row + 1) = selected[i].y_m;
  }

  Eigen::VectorXd pose_weights = Eigen::VectorXd::Ones(static_cast<Eigen::Index>(selected.size()));
  Eigen::Vector4d solution = Eigen::Vector4d::Zero();
  Eigen::MatrixXd weighted_design;
  Eigen::VectorXd weighted_observations;
  double condition_number = std::numeric_limits<double>::infinity();
  for (int iteration = 0; iteration < 8; ++iteration) {
    weighted_design = design;
    weighted_observations = observations;
    for (std::size_t i = 0; i < selected.size(); ++i) {
      const double scale = std::sqrt(pose_weights(static_cast<Eigen::Index>(i)));
      weighted_design.row(static_cast<Eigen::Index>(2 * i)) *= scale;
      weighted_design.row(static_cast<Eigen::Index>(2 * i + 1)) *= scale;
      weighted_observations(static_cast<Eigen::Index>(2 * i)) *= scale;
      weighted_observations(static_cast<Eigen::Index>(2 * i + 1)) *= scale;
    }
    Eigen::JacobiSVD<Eigen::MatrixXd> svd(weighted_design,
                                          Eigen::ComputeThinU | Eigen::ComputeThinV);
    const auto singular = svd.singularValues();
    if (singular.size() < 4 || singular(3) <= 1.0e-12) {
      result.status = Status::kDegenerate;
      return result;
    }
    condition_number = singular(0) / singular(3);
    solution = svd.solve(weighted_observations);
    const Eigen::VectorXd residual = observations - design * solution;
    for (std::size_t i = 0; i < selected.size(); ++i) {
      const double norm = residual.segment<2>(static_cast<Eigen::Index>(2 * i)).norm();
      pose_weights(static_cast<Eigen::Index>(i)) =
          norm <= config_.huber_delta_m ? 1.0 : config_.huber_delta_m / std::max(norm, 1.0e-12);
    }
  }

  result.condition_number = condition_number;
  if (!std::isfinite(condition_number) || condition_number > config_.maximum_condition_number) {
    result.status = Status::kDegenerate;
    return result;
  }

  const Eigen::VectorXd residual = observations - design * solution;
  double weighted_squared_error = 0.0;
  double weight_sum = 0.0;
  for (std::size_t i = 0; i < selected.size(); ++i) {
    const double weight = pose_weights(static_cast<Eigen::Index>(i));
    weighted_squared_error +=
        weight * residual.segment<2>(static_cast<Eigen::Index>(2 * i)).squaredNorm();
    weight_sum += 2.0 * weight;
  }
  // Huber weights protect the position fit from isolated scan-matching
  // outliers, but must not hide a genuinely moving ICR. Use the unweighted
  // residual for the constant-centre validity gate.
  result.fit_rms_m = residual.norm() / std::sqrt(static_cast<double>(residual.size()));
  if (!std::isfinite(result.fit_rms_m) || result.fit_rms_m > config_.maximum_fit_rms_m) {
    result.status = Status::kExcessResidual;
    return result;
  }

  result.center_in_lidar_m = -solution.segment<2>(2);
  Eigen::Matrix4d normal = Eigen::Matrix4d::Zero();
  for (std::size_t i = 0; i < selected.size(); ++i) {
    const Eigen::Index row = static_cast<Eigen::Index>(2 * i);
    normal += pose_weights(static_cast<Eigen::Index>(i)) *
              design.block<2, 4>(row, 0).transpose() * design.block<2, 4>(row, 0);
  }
  const double degrees_of_freedom = std::max(1.0, weight_sum - 4.0);
  const double variance = weighted_squared_error / degrees_of_freedom;
  Eigen::LDLT<Eigen::Matrix4d> decomposition(normal);
  if (decomposition.info() != Eigen::Success) {
    result.status = Status::kDegenerate;
    return result;
  }
  const Eigen::Matrix4d covariance = decomposition.solve(Eigen::Matrix4d::Identity()) * variance;
  result.covariance_m2 = covariance.block<2, 2>(2, 2);
  result.status = Status::kValid;
  return result;
}

}  // namespace emc270::icr
