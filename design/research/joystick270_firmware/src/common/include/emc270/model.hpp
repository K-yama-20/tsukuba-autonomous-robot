#pragma once

#include <cstdint>

namespace emc270 {

constexpr std::uint16_t kConfigSchemaVersion = 1;
constexpr std::int16_t kNormalizedFullScale = 10000;
constexpr std::uint16_t kDefaultCenterSeedMv = 2500;
constexpr std::uint16_t kDefaultDacFullScaleMv = 4990;
constexpr std::uint16_t kDefaultWatchdogMs = 300;
constexpr std::uint16_t kDefaultSlewFullScaleMs = 1000;
constexpr std::uint16_t kDefaultMotionThresholdMmS = 10;
constexpr std::uint16_t kDefaultOutputWarnToleranceMv = 40;

enum class Mode : std::uint8_t {
  kBootSafe = 0,
  kManualSafe = 1,
  kReady = 2,
  kArming = 3,
  kDrive = 4,
  kCalibrating = 5,
  kFailsafe = 6,
};

enum Warning : std::uint32_t {
  kWarningNone = 0,
  kWarningAdcUnavailable = 1U << 0,
  kWarningOutputMismatchX = 1U << 1,
  kWarningOutputMismatchY = 1U << 2,
  kWarningEncoderStale = 1U << 3,
  kWarningLogUnavailable = 1U << 4,
  kWarningConfigStore = 1U << 5,
  kWarningUsbWatchdog = 1U << 6,
  kWarningFrameCrc = 1U << 7,
  kWarningSequenceGap = 1U << 8,
  kWarningArmVerification = 1U << 9,
  kWarningCalibrationFailed = 1U << 10,
};

enum class EventCode : std::uint16_t {
  kBoot = 1,
  kConfigLoaded = 2,
  kConfigInvalid = 3,
  kPresetSaved = 4,
  kArmStarted = 10,
  kArmSucceeded = 11,
  kArmRejected = 12,
  kArmPostSwitchMismatch = 13,
  kDisarmed = 14,
  kWatchdogExpired = 20,
  kUsbReconnected = 21,
  kEncoderStale = 22,
  kAdcUnavailable = 23,
  kOutputMismatch = 24,
  kCalibrationStarted = 30,
  kCalibrationCompleted = 31,
  kCalibrationAborted = 32,
  kCalibrationFailed = 33,
  kLogUnavailable = 40,
};

enum class CalibrationFailure : std::uint16_t {
  kNone = 0,
  kInvalidPreset = 1,
  kEncoderUnavailable = 2,
  kSeedMoving = 3,
  kNoMotionBeforeEndpoint = 4,
  kTimeout = 5,
  kHostWatchdog = 6,
  kAbortedByHost = 7,
  kArmVerification = 8,
  kInternal = 9,
  kAdcUnavailable = 10,
  kLogUnavailable = 11,
  kConfigStoreUnavailable = 12,
};

struct AxisProfile {
  std::uint16_t negative_mv{0};
  std::uint16_t positive_mv{0};
  std::uint16_t seed_mv{kDefaultCenterSeedMv};
  std::uint16_t neutral_low_mv{0};
  std::uint16_t neutral_high_mv{0};
  std::uint16_t neutral_mid_mv{kDefaultCenterSeedMv};
};

struct ControllerConfig {
  std::uint16_t schema_version{kConfigSchemaVersion};
  std::uint32_t generation{0};
  AxisProfile x{};
  AxisProfile y{};
  std::uint16_t dac_full_scale_mv{kDefaultDacFullScaleMv};
  std::uint16_t watchdog_ms{kDefaultWatchdogMs};
  std::uint16_t slew_full_scale_ms{kDefaultSlewFullScaleMs};
  std::uint16_t motion_threshold_mm_s{kDefaultMotionThresholdMmS};
  std::uint16_t output_warn_tolerance_mv{kDefaultOutputWarnToleranceMv};
  std::uint8_t preset_valid{0};
  std::uint8_t neutral_valid{0};
};

struct ValidationResult {
  bool valid{false};
  std::uint16_t reason{0};
};

ValidationResult ValidatePreset(const ControllerConfig &config);
ValidationResult ValidateReadyConfig(const ControllerConfig &config);

} // namespace emc270
