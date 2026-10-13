#pragma once

#include <array>
#include <cstdint>

#include "emc270/model.hpp"

namespace emc270 {

enum class CalibrationPhase : std::uint8_t {
  kIdle = 0,
  kSeedCheck = 1,
  kCoarseSearch = 2,
  kFineSearch = 3,
  kComplete = 4,
  kFailed = 5,
  kAborted = 6,
  kArming = 7,
};

enum class CalibrationVerdict : std::uint8_t {
  kNone = 0,
  kSettling = 1,
  kStationaryAccumulating = 2,
  kStationaryAccepted = 3,
  kMotionDetected = 4,
  kBoundaryRecorded = 5,
};

struct CalibrationInput {
  std::uint32_t now_ms{0};
  bool encoder_valid{false};
  std::int32_t left_mm_s{0};
  std::int32_t right_mm_s{0};
};

struct CalibrationUpdate {
  CalibrationPhase phase{CalibrationPhase::kIdle};
  CalibrationVerdict verdict{CalibrationVerdict::kNone};
  std::uint8_t axis{0};
  std::int8_t direction{-1};
  std::uint8_t pass{0};
  std::uint16_t target_x_mv{kDefaultCenterSeedMv};
  std::uint16_t target_y_mv{kDefaultCenterSeedMv};
  std::uint32_t stationary_ms{0};
  bool target_changed{false};
  bool completed{false};
  bool failed{false};
  CalibrationFailure failure{CalibrationFailure::kNone};
};

class CalibrationEngine {
public:
  static constexpr std::uint16_t kCoarseStepMv = 20;
  static constexpr std::uint16_t kFineStepMv = 2;
  static constexpr std::uint16_t kSettleMs = 250;
  static constexpr std::uint16_t kStationaryRequiredMs = 2000;
  static constexpr std::uint8_t kMovingSamplesRequired = 3;
  static constexpr std::uint32_t kSessionTimeoutMs = 600000;

  bool Start(const ControllerConfig &config, std::uint32_t session_id,
             std::uint32_t now_ms);
  CalibrationUpdate Tick(const CalibrationInput &input);
  void Abort(CalibrationFailure reason);

  bool active() const;
  CalibrationPhase phase() const { return phase_; }
  CalibrationFailure failure() const { return failure_; }
  std::uint32_t session_id() const { return session_id_; }
  const ControllerConfig &result_config() const { return result_config_; }

private:
  void BeginBoundary(std::uint32_t now_ms);
  void SetCandidate(std::uint16_t value_mv, std::uint32_t now_ms);
  void AcceptStationary(std::uint32_t now_ms, CalibrationUpdate *update);
  void AcceptMoving(std::uint32_t now_ms, CalibrationUpdate *update);
  void RecordBoundary(std::uint32_t now_ms, CalibrationUpdate *update);
  void AdvanceBoundary(std::uint32_t now_ms, CalibrationUpdate *update);
  void Complete(CalibrationUpdate *update);
  void Fail(CalibrationFailure reason, CalibrationUpdate *update);
  std::uint16_t Seed() const;
  std::uint16_t Endpoint() const;
  int NumericDirection() const;
  std::uint16_t NextOutward(std::uint16_t from) const;
  bool IsMoving(const CalibrationInput &input) const;
  CalibrationUpdate Snapshot() const;

  ControllerConfig result_config_{};
  std::uint32_t session_id_{0};
  std::uint32_t session_started_ms_{0};
  CalibrationPhase phase_{CalibrationPhase::kIdle};
  CalibrationFailure failure_{CalibrationFailure::kNone};
  std::uint8_t axis_{0};
  std::uint8_t direction_index_{0};
  std::uint8_t pass_{0};
  std::uint16_t target_x_mv_{kDefaultCenterSeedMv};
  std::uint16_t target_y_mv_{kDefaultCenterSeedMv};
  std::uint16_t candidate_mv_{kDefaultCenterSeedMv};
  std::uint16_t last_stationary_mv_{kDefaultCenterSeedMv};
  std::uint16_t moving_bound_mv_{kDefaultCenterSeedMv};
  std::uint32_t candidate_set_ms_{0};
  std::uint32_t stationary_since_ms_{0};
  std::uint8_t moving_samples_{0};
  std::array<std::array<std::array<std::uint16_t, 3>, 2>, 2> boundaries_{};
};

} // namespace emc270
