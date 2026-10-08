#include <unity.h>

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>

#include "emc270/calibration.hpp"
#include "emc270/control.hpp"
#include "emc270/messages.hpp"
#include "emc270/model.hpp"
#include "emc270/protocol.hpp"

using namespace emc270;

void setUp() {}
void tearDown() {}

namespace {

ControllerConfig TestConfig() {
  PresetPayload preset;
  preset.x_negative_mv = 500;
  preset.x_positive_mv = 4500;
  preset.y_negative_mv = 600;
  preset.y_positive_mv = 4400;
  preset.x_seed_mv = 2500;
  preset.y_seed_mv = 2500;
  return ConfigFromPreset(preset, 1);
}

void TestCrcKnownVector() {
  const char *input = "123456789";
  TEST_ASSERT_EQUAL_HEX16(
      0x29B1, Crc16Ccitt(reinterpret_cast<const std::uint8_t *>(input),
                         std::strlen(input)));
}

void TestFrameRoundTripAndCrcRejection() {
  CommandPayload command;
  command.x_q10000 = -2345;
  command.y_q10000 = 9876;
  command.flags = kCommandFlagArm;
  std::array<std::uint8_t, kMaxPayloadSize> payload{};
  std::uint16_t payload_size = 0;
  TEST_ASSERT_TRUE(EncodeCommandPayload(command, payload.data(), payload.size(),
                                        &payload_size));
  EncodedFrame encoded;
  TEST_ASSERT_TRUE(EncodeFrame(MessageType::kCommand, 42, 1234, payload.data(),
                               payload_size, &encoded));

  FrameParser parser;
  Frame parsed;
  bool complete = false;
  for (std::size_t index = 0; index < encoded.size; ++index) {
    complete = parser.Feed(encoded.bytes[index], &parsed) || complete;
  }
  TEST_ASSERT_TRUE(complete);
  TEST_ASSERT_EQUAL_UINT8(static_cast<std::uint8_t>(MessageType::kCommand),
                          static_cast<std::uint8_t>(parsed.type));
  TEST_ASSERT_EQUAL_UINT32(42, parsed.sequence);
  CommandPayload decoded;
  TEST_ASSERT_TRUE(DecodeCommandPayload(parsed, &decoded));
  TEST_ASSERT_EQUAL_INT16(command.x_q10000, decoded.x_q10000);
  TEST_ASSERT_EQUAL_INT16(command.y_q10000, decoded.y_q10000);
  TEST_ASSERT_EQUAL_UINT8(command.flags, decoded.flags);

  encoded.bytes[14] ^= 0x01;
  complete = false;
  for (std::size_t index = 0; index < encoded.size; ++index) {
    complete = parser.Feed(encoded.bytes[index], &parsed) || complete;
  }
  TEST_ASSERT_FALSE(complete);
  TEST_ASSERT_EQUAL_UINT32(1, parser.crc_errors());
}

void TestStatusPayloadRoundTrip() {
  StatusPayload status;
  status.mode = Mode::kFailsafe;
  status.relay_energized = 1;
  status.config_valid = 1;
  status.encoder_valid = 0;
  status.rearm_required = 1;
  status.warnings = kWarningUsbWatchdog | kWarningEncoderStale;
  status.target_x_mv = 2470;
  status.actual_x_mv = 2460;
  status.left_mm_s = -12;
  status.last_calibration_failure = CalibrationFailure::kHostWatchdog;

  std::array<std::uint8_t, kMaxPayloadSize> payload{};
  std::uint16_t size = 0;
  TEST_ASSERT_TRUE(
      EncodeStatusPayload(status, payload.data(), payload.size(), &size));
  TEST_ASSERT_EQUAL_UINT16(43, size);
  Frame frame;
  frame.payload_size = size;
  std::copy_n(payload.begin(), size, frame.payload.begin());
  StatusPayload decoded;
  TEST_ASSERT_TRUE(DecodeStatusPayload(frame, &decoded));
  TEST_ASSERT_EQUAL_UINT8(1, decoded.rearm_required);
  TEST_ASSERT_EQUAL_UINT32(status.warnings, decoded.warnings);
  TEST_ASSERT_EQUAL_INT32(status.left_mm_s, decoded.left_mm_s);
  TEST_ASSERT_EQUAL_UINT16(
      static_cast<std::uint16_t>(status.last_calibration_failure),
      static_cast<std::uint16_t>(decoded.last_calibration_failure));
}

void TestAsymmetricIndependentMapping() {
  AxisProfile axis;
  axis.negative_mv = 700;
  axis.positive_mv = 4300;
  axis.neutral_mid_mv = 2475;
  TEST_ASSERT_EQUAL_UINT16(2475, MapNormalizedToMillivolts(0, axis));
  TEST_ASSERT_EQUAL_UINT16(700, MapNormalizedToMillivolts(-10000, axis));
  TEST_ASSERT_EQUAL_UINT16(4300, MapNormalizedToMillivolts(10000, axis));
  TEST_ASSERT_EQUAL_UINT16(3388, MapNormalizedToMillivolts(5000, axis));
  TEST_ASSERT_EQUAL_UINT16(1587, MapNormalizedToMillivolts(-5000, axis));

  AxisProfile reversed;
  reversed.negative_mv = 4300;
  reversed.positive_mv = 700;
  reversed.neutral_mid_mv = 2475;
  TEST_ASSERT_EQUAL_UINT16(4300, MapNormalizedToMillivolts(-10000, reversed));
  TEST_ASSERT_EQUAL_UINT16(700, MapNormalizedToMillivolts(10000, reversed));
}

void TestSlewAndWatchdog() {
  SlewLimiter limiter;
  limiter.Reset(2500, 1000);
  TEST_ASSERT_EQUAL_UINT16(2999, limiter.Step(4500, 4990, 1000, 1100));
  TEST_ASSERT_EQUAL_UINT16(3498, limiter.Step(4500, 4990, 1000, 1200));
  limiter.Reset(2500, 2000);
  TEST_ASSERT_EQUAL_UINT16(2001, limiter.Step(500, 4990, 1000, 2100));

  CommandWatchdog watchdog;
  TEST_ASSERT_TRUE(watchdog.Expired(0, 300));
  watchdog.Observe(100);
  TEST_ASSERT_FALSE(watchdog.Expired(400, 300));
  TEST_ASSERT_TRUE(watchdog.Expired(401, 300));
}

void TestPresetValidationRequiresCalibrationForReady() {
  auto config = TestConfig();
  TEST_ASSERT_TRUE(ValidatePreset(config).valid);
  TEST_ASSERT_FALSE(ValidateReadyConfig(config).valid);
  config.x.neutral_low_mv = 2450;
  config.x.neutral_high_mv = 2550;
  config.x.neutral_mid_mv = 2500;
  config.y.neutral_low_mv = 2470;
  config.y.neutral_high_mv = 2530;
  config.y.neutral_mid_mv = 2500;
  config.neutral_valid = 1;
  TEST_ASSERT_TRUE(ValidateReadyConfig(config).valid);
  config.x.neutral_mid_mv = 2501;
  TEST_ASSERT_FALSE(ValidateReadyConfig(config).valid);
}

void TestCalibrationFindsConservativeNeutralBox() {
  auto config = TestConfig();
  CalibrationEngine engine;
  TEST_ASSERT_TRUE(engine.Start(config, 77, 0));
  auto update = CalibrationUpdate{};
  std::uint16_t target_x = 2500;
  std::uint16_t target_y = 2500;
  for (std::uint32_t now = 0; now < 500000 && engine.active(); now += 20) {
    const bool moving = target_x < 2450 || target_x > 2550 || target_y < 2470 ||
                        target_y > 2530;
    CalibrationInput input;
    input.now_ms = now;
    input.encoder_valid = true;
    input.left_mm_s = moving ? 40 : 0;
    input.right_mm_s = moving ? 40 : 0;
    update = engine.Tick(input);
    target_x = update.target_x_mv;
    target_y = update.target_y_mv;
  }
  TEST_ASSERT_EQUAL_UINT8(
      static_cast<std::uint8_t>(CalibrationPhase::kComplete),
      static_cast<std::uint8_t>(engine.phase()));
  const auto &result = engine.result_config();
  TEST_ASSERT_TRUE(result.neutral_valid != 0);
  TEST_ASSERT_GREATER_OR_EQUAL_UINT16(2450, result.x.neutral_low_mv);
  TEST_ASSERT_LESS_OR_EQUAL_UINT16(2550, result.x.neutral_high_mv);
  TEST_ASSERT_GREATER_OR_EQUAL_UINT16(2470, result.y.neutral_low_mv);
  TEST_ASSERT_LESS_OR_EQUAL_UINT16(2530, result.y.neutral_high_mv);
  TEST_ASSERT_TRUE(ValidateReadyConfig(result).valid);
}

void TestCalibrationRejectsMovingSeed() {
  CalibrationEngine engine;
  TEST_ASSERT_TRUE(engine.Start(TestConfig(), 10, 0));
  CalibrationUpdate update;
  for (std::uint32_t now = 0; now < 1000 && engine.active(); now += 20) {
    update = engine.Tick({now, true, 100, 100});
  }
  TEST_ASSERT_EQUAL_UINT8(static_cast<std::uint8_t>(CalibrationPhase::kFailed),
                          static_cast<std::uint8_t>(engine.phase()));
  TEST_ASSERT_EQUAL_UINT16(
      static_cast<std::uint16_t>(CalibrationFailure::kSeedMoving),
      static_cast<std::uint16_t>(engine.failure()));
}

} // namespace

int main(int, char **) {
  UNITY_BEGIN();
  RUN_TEST(TestCrcKnownVector);
  RUN_TEST(TestFrameRoundTripAndCrcRejection);
  RUN_TEST(TestStatusPayloadRoundTrip);
  RUN_TEST(TestAsymmetricIndependentMapping);
  RUN_TEST(TestSlewAndWatchdog);
  RUN_TEST(TestPresetValidationRequiresCalibrationForReady);
  RUN_TEST(TestCalibrationFindsConservativeNeutralBox);
  RUN_TEST(TestCalibrationRejectsMovingSeed);
  return UNITY_END();
}
