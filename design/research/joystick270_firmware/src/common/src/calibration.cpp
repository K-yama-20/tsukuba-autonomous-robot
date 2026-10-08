#include "emc270/calibration.hpp"

#include <algorithm>
#include <cstdlib>

namespace emc270 {

bool CalibrationEngine::Start(const ControllerConfig &config,
                              std::uint32_t session_id, std::uint32_t now_ms) {
  if (!ValidatePreset(config).valid)
    return false;
  result_config_ = config;
  result_config_.neutral_valid = 0;
  session_id_ = session_id;
  session_started_ms_ = now_ms;
  phase_ = CalibrationPhase::kSeedCheck;
  failure_ = CalibrationFailure::kNone;
  axis_ = 0;
  direction_index_ = 0;
  pass_ = 0;
  boundaries_ = {};
  target_x_mv_ = result_config_.x.seed_mv;
  target_y_mv_ = result_config_.y.seed_mv;
  candidate_mv_ = Seed();
  last_stationary_mv_ = candidate_mv_;
  moving_bound_mv_ = candidate_mv_;
  candidate_set_ms_ = now_ms;
  stationary_since_ms_ = 0;
  moving_samples_ = 0;
  return true;
}

bool CalibrationEngine::active() const {
  return phase_ == CalibrationPhase::kSeedCheck ||
         phase_ == CalibrationPhase::kCoarseSearch ||
         phase_ == CalibrationPhase::kFineSearch;
}

CalibrationUpdate CalibrationEngine::Tick(const CalibrationInput &input) {
  auto update = Snapshot();
  if (!active())
    return update;
  if (input.now_ms - session_started_ms_ > kSessionTimeoutMs) {
    Fail(CalibrationFailure::kTimeout, &update);
    return update;
  }
  if (!input.encoder_valid) {
    Fail(CalibrationFailure::kEncoderUnavailable, &update);
    return update;
  }

  const bool moving = IsMoving(input);
  if (input.now_ms - candidate_set_ms_ < kSettleMs) {
    update.verdict = CalibrationVerdict::kSettling;
    return update;
  }

  if (moving) {
    stationary_since_ms_ = 0;
    if (moving_samples_ < 255)
      ++moving_samples_;
    update.verdict = CalibrationVerdict::kMotionDetected;
    if (moving_samples_ < kMovingSamplesRequired)
      return update;
    if (phase_ == CalibrationPhase::kSeedCheck) {
      Fail(CalibrationFailure::kSeedMoving, &update);
    } else {
      AcceptMoving(input.now_ms, &update);
    }
    return update;
  }

  moving_samples_ = 0;
  if (stationary_since_ms_ == 0)
    stationary_since_ms_ = input.now_ms;
  update.stationary_ms = input.now_ms - stationary_since_ms_;
  update.verdict = CalibrationVerdict::kStationaryAccumulating;
  if (update.stationary_ms >= kStationaryRequiredMs) {
    AcceptStationary(input.now_ms, &update);
  }
  return update;
}

void CalibrationEngine::Abort(CalibrationFailure reason) {
  if (!active())
    return;
  phase_ = CalibrationPhase::kAborted;
  failure_ = reason;
}

void CalibrationEngine::BeginBoundary(std::uint32_t now_ms) {
  phase_ = CalibrationPhase::kSeedCheck;
  SetCandidate(Seed(), now_ms);
}

void CalibrationEngine::SetCandidate(std::uint16_t value_mv,
                                     std::uint32_t now_ms) {
  candidate_mv_ = value_mv;
  if (axis_ == 0) {
    target_x_mv_ = value_mv;
    target_y_mv_ = result_config_.y.seed_mv;
  } else {
    target_x_mv_ = result_config_.x.seed_mv;
    target_y_mv_ = value_mv;
  }
  candidate_set_ms_ = now_ms;
  stationary_since_ms_ = 0;
  moving_samples_ = 0;
}

void CalibrationEngine::AcceptStationary(std::uint32_t now_ms,
                                         CalibrationUpdate *update) {
  update->verdict = CalibrationVerdict::kStationaryAccepted;
  if (phase_ == CalibrationPhase::kSeedCheck) {
    last_stationary_mv_ = Seed();
    phase_ = CalibrationPhase::kCoarseSearch;
    const auto next = NextOutward(last_stationary_mv_);
    if (next == last_stationary_mv_) {
      Fail(CalibrationFailure::kNoMotionBeforeEndpoint, update);
      return;
    }
    SetCandidate(next, now_ms);
    update->target_changed = true;
    update->phase = phase_;
    update->target_x_mv = target_x_mv_;
    update->target_y_mv = target_y_mv_;
    return;
  }

  if (phase_ == CalibrationPhase::kCoarseSearch) {
    last_stationary_mv_ = candidate_mv_;
    if (candidate_mv_ == Endpoint()) {
      Fail(CalibrationFailure::kNoMotionBeforeEndpoint, update);
      return;
    }
    SetCandidate(NextOutward(candidate_mv_), now_ms);
    update->target_changed = true;
  } else if (phase_ == CalibrationPhase::kFineSearch) {
    last_stationary_mv_ = candidate_mv_;
    if (std::abs(static_cast<int>(moving_bound_mv_) -
                 static_cast<int>(last_stationary_mv_)) <= kFineStepMv) {
      RecordBoundary(now_ms, update);
      return;
    }
    const auto midpoint = static_cast<std::uint16_t>(
        (static_cast<std::uint32_t>(last_stationary_mv_) + moving_bound_mv_) /
        2U);
    SetCandidate(midpoint, now_ms);
    update->target_changed = true;
  }
  update->phase = phase_;
  update->target_x_mv = target_x_mv_;
  update->target_y_mv = target_y_mv_;
}

void CalibrationEngine::AcceptMoving(std::uint32_t now_ms,
                                     CalibrationUpdate *update) {
  moving_bound_mv_ = candidate_mv_;
  if (phase_ == CalibrationPhase::kCoarseSearch) {
    phase_ = CalibrationPhase::kFineSearch;
  }
  if (std::abs(static_cast<int>(moving_bound_mv_) -
               static_cast<int>(last_stationary_mv_)) <= kFineStepMv) {
    RecordBoundary(now_ms, update);
    return;
  }
  const auto midpoint = static_cast<std::uint16_t>(
      (static_cast<std::uint32_t>(last_stationary_mv_) + moving_bound_mv_) /
      2U);
  SetCandidate(midpoint, now_ms);
  update->target_changed = true;
  update->phase = phase_;
  update->target_x_mv = target_x_mv_;
  update->target_y_mv = target_y_mv_;
}

void CalibrationEngine::RecordBoundary(std::uint32_t now_ms,
                                       CalibrationUpdate *update) {
  boundaries_[axis_][direction_index_][pass_] = last_stationary_mv_;
  update->verdict = CalibrationVerdict::kBoundaryRecorded;
  AdvanceBoundary(now_ms, update);
}

void CalibrationEngine::AdvanceBoundary(std::uint32_t now_ms,
                                        CalibrationUpdate *update) {
  if (++pass_ < 3) {
    BeginBoundary(now_ms);
  } else {
    pass_ = 0;
    if (direction_index_ == 0) {
      direction_index_ = 1;
      BeginBoundary(now_ms);
    } else if (axis_ == 0) {
      axis_ = 1;
      direction_index_ = 0;
      BeginBoundary(now_ms);
    } else {
      Complete(update);
      return;
    }
  }
  update->target_changed = true;
  update->phase = phase_;
  update->axis = axis_;
  update->direction = direction_index_ == 0 ? -1 : 1;
  update->pass = pass_;
  update->target_x_mv = target_x_mv_;
  update->target_y_mv = target_y_mv_;
}

void CalibrationEngine::Complete(CalibrationUpdate *update) {
  for (std::uint8_t axis_index = 0; axis_index < 2; ++axis_index) {
    auto &axis = axis_index == 0 ? result_config_.x : result_config_.y;
    const std::uint8_t low_direction = axis.negative_mv < axis.seed_mv ? 0 : 1;
    const std::uint8_t high_direction = low_direction == 0 ? 1 : 0;
    std::uint16_t low = boundaries_[axis_index][low_direction][0];
    std::uint16_t high = boundaries_[axis_index][high_direction][0];
    for (std::size_t pass = 1; pass < 3; ++pass) {
      low = std::max(low, boundaries_[axis_index][low_direction][pass]);
      high = std::min(high, boundaries_[axis_index][high_direction][pass]);
    }
    if (low >= high || axis.seed_mv < low || axis.seed_mv > high) {
      Fail(CalibrationFailure::kInternal, update);
      return;
    }
    axis.neutral_low_mv = low;
    axis.neutral_high_mv = high;
    axis.neutral_mid_mv = static_cast<std::uint16_t>(
        (static_cast<std::uint32_t>(low) + high) / 2U);
  }
  result_config_.neutral_valid = 1;
  phase_ = CalibrationPhase::kComplete;
  target_x_mv_ = result_config_.x.neutral_mid_mv;
  target_y_mv_ = result_config_.y.neutral_mid_mv;
  update->phase = phase_;
  update->target_x_mv = target_x_mv_;
  update->target_y_mv = target_y_mv_;
  update->target_changed = true;
  update->completed = true;
  update->failure = CalibrationFailure::kNone;
}

void CalibrationEngine::Fail(CalibrationFailure reason,
                             CalibrationUpdate *update) {
  phase_ = CalibrationPhase::kFailed;
  failure_ = reason;
  target_x_mv_ = result_config_.x.seed_mv;
  target_y_mv_ = result_config_.y.seed_mv;
  update->phase = phase_;
  update->target_x_mv = target_x_mv_;
  update->target_y_mv = target_y_mv_;
  update->target_changed = true;
  update->failed = true;
  update->failure = reason;
}

std::uint16_t CalibrationEngine::Seed() const {
  return axis_ == 0 ? result_config_.x.seed_mv : result_config_.y.seed_mv;
}

std::uint16_t CalibrationEngine::Endpoint() const {
  const auto &axis = axis_ == 0 ? result_config_.x : result_config_.y;
  return direction_index_ == 0 ? axis.negative_mv : axis.positive_mv;
}

int CalibrationEngine::NumericDirection() const {
  return Endpoint() < Seed() ? -1 : 1;
}

std::uint16_t CalibrationEngine::NextOutward(std::uint16_t from) const {
  const auto endpoint = Endpoint();
  if (NumericDirection() < 0) {
    if (from <= endpoint)
      return endpoint;
    const auto stepped = static_cast<std::uint16_t>(
        from > kCoarseStepMv ? from - kCoarseStepMv : 0);
    return std::max(endpoint, stepped);
  }
  return static_cast<std::uint16_t>(
      std::min<std::uint32_t>(endpoint, from + kCoarseStepMv));
}

bool CalibrationEngine::IsMoving(const CalibrationInput &input) const {
  const auto threshold = result_config_.motion_threshold_mm_s;
  return std::abs(input.left_mm_s) > threshold ||
         std::abs(input.right_mm_s) > threshold;
}

CalibrationUpdate CalibrationEngine::Snapshot() const {
  CalibrationUpdate update;
  update.phase = phase_;
  update.axis = axis_;
  update.direction = direction_index_ == 0 ? -1 : 1;
  update.pass = pass_;
  update.target_x_mv = target_x_mv_;
  update.target_y_mv = target_y_mv_;
  update.failure = failure_;
  update.completed = phase_ == CalibrationPhase::kComplete;
  update.failed = phase_ == CalibrationPhase::kFailed ||
                  phase_ == CalibrationPhase::kAborted;
  return update;
}

} // namespace emc270
