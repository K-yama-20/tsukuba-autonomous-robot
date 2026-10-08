#pragma once

#include <cstddef>
#include <cstdint>

#include "emc270/model.hpp"
#include "emc270/protocol.hpp"

namespace emc270 {

constexpr std::uint8_t kCommandFlagArm = 1U << 0;
constexpr std::uint8_t kHelloOptionAutoResume = 1U << 0;
constexpr std::uint16_t kEncoderStatusValid = 1U << 0;

struct HelloPayload {
  std::uint32_t session_id{0};
  std::uint8_t options{0};
};

struct CommandPayload {
  std::int16_t x_q10000{0};
  std::int16_t y_q10000{0};
  std::uint8_t flags{0};
};

struct PresetPayload {
  std::uint16_t x_negative_mv{0};
  std::uint16_t x_positive_mv{0};
  std::uint16_t y_negative_mv{0};
  std::uint16_t y_positive_mv{0};
  std::uint16_t x_seed_mv{kDefaultCenterSeedMv};
  std::uint16_t y_seed_mv{kDefaultCenterSeedMv};
  std::uint16_t dac_full_scale_mv{kDefaultDacFullScaleMv};
  std::uint16_t watchdog_ms{kDefaultWatchdogMs};
  std::uint16_t slew_full_scale_ms{kDefaultSlewFullScaleMs};
  std::uint16_t motion_threshold_mm_s{kDefaultMotionThresholdMmS};
  std::uint16_t output_warn_tolerance_mv{kDefaultOutputWarnToleranceMv};
};

struct EncoderSpeedPayload {
  std::int32_t left_mm_s{0};
  std::int32_t right_mm_s{0};
  std::uint16_t status{0};
};

struct EventPayload {
  EventCode code{EventCode::kBoot};
  std::uint8_t severity{0};
  Mode mode{Mode::kBootSafe};
  std::int32_t detail_a{0};
  std::int32_t detail_b{0};
  std::uint16_t target_x_mv{0};
  std::uint16_t target_y_mv{0};
  std::uint16_t actual_x_mv{0};
  std::uint16_t actual_y_mv{0};
};

struct StatusPayload {
  Mode mode{Mode::kBootSafe};
  std::uint8_t relay_energized{0};
  std::uint8_t config_valid{0};
  std::uint8_t encoder_valid{0};
  std::uint8_t rearm_required{0};
  std::uint32_t warnings{0};
  std::uint32_t command_age_ms{UINT32_MAX};
  std::uint32_t encoder_age_ms{UINT32_MAX};
  std::int16_t command_x_q10000{0};
  std::int16_t command_y_q10000{0};
  std::uint16_t target_x_mv{0};
  std::uint16_t target_y_mv{0};
  std::uint16_t actual_x_mv{0};
  std::uint16_t actual_y_mv{0};
  std::int32_t left_mm_s{0};
  std::int32_t right_mm_s{0};
  std::uint32_t config_generation{0};
  CalibrationFailure last_calibration_failure{CalibrationFailure::kNone};
};

struct AckPayload {
  MessageType request_type{MessageType::kHello};
  std::uint8_t accepted{0};
  std::uint16_t reason{0};
  std::int32_t detail{0};
};

struct CalibrationSamplePayload {
  std::uint32_t session_id{0};
  std::uint32_t sample_index{0};
  std::uint8_t phase{0};
  std::uint8_t axis{0};
  std::int8_t direction{0};
  std::uint8_t verdict{0};
  std::uint16_t target_x_mv{0};
  std::uint16_t target_y_mv{0};
  std::uint16_t actual_x_mv{0};
  std::uint16_t actual_y_mv{0};
  std::int32_t left_mm_s{0};
  std::int32_t right_mm_s{0};
  std::uint32_t stationary_ms{0};
  CalibrationFailure failure{CalibrationFailure::kNone};
};

bool EncodeHelloPayload(const HelloPayload &value, std::uint8_t *output,
                        std::size_t capacity, std::uint16_t *size);
bool DecodeHelloPayload(const Frame &frame, HelloPayload *value);
bool EncodeCommandPayload(const CommandPayload &value, std::uint8_t *output,
                          std::size_t capacity, std::uint16_t *size);
bool DecodeCommandPayload(const Frame &frame, CommandPayload *value);
bool EncodePresetPayload(const PresetPayload &value, std::uint8_t *output,
                         std::size_t capacity, std::uint16_t *size);
bool DecodePresetPayload(const Frame &frame, PresetPayload *value);
bool EncodeEncoderSpeedPayload(const EncoderSpeedPayload &value,
                               std::uint8_t *output, std::size_t capacity,
                               std::uint16_t *size);
bool DecodeEncoderSpeedPayload(const Frame &frame, EncoderSpeedPayload *value);
bool EncodeEventPayload(const EventPayload &value, std::uint8_t *output,
                        std::size_t capacity, std::uint16_t *size);
bool DecodeEventPayload(const Frame &frame, EventPayload *value);
bool EncodeStatusPayload(const StatusPayload &value, std::uint8_t *output,
                         std::size_t capacity, std::uint16_t *size);
bool DecodeStatusPayload(const Frame &frame, StatusPayload *value);
bool EncodeAckPayload(const AckPayload &value, std::uint8_t *output,
                      std::size_t capacity, std::uint16_t *size);
bool DecodeAckPayload(const Frame &frame, AckPayload *value);
bool EncodeCalibrationSamplePayload(const CalibrationSamplePayload &value,
                                    std::uint8_t *output, std::size_t capacity,
                                    std::uint16_t *size);
bool DecodeCalibrationSamplePayload(const Frame &frame,
                                    CalibrationSamplePayload *value);
bool EncodeControllerConfigPayload(const ControllerConfig &value,
                                   std::uint8_t *output, std::size_t capacity,
                                   std::uint16_t *size);
bool DecodeControllerConfigPayload(const Frame &frame, ControllerConfig *value);

ControllerConfig ConfigFromPreset(const PresetPayload &preset,
                                  std::uint32_t generation);
PresetPayload PresetFromConfig(const ControllerConfig &config);

} // namespace emc270
