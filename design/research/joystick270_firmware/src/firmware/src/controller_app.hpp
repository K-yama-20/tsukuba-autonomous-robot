#pragma once

#include <Arduino.h>

#include <array>
#include <cstdint>

#include "calibration_log.hpp"
#include "config_store.hpp"
#include "emc270/calibration.hpp"
#include "emc270/control.hpp"
#include "emc270/messages.hpp"
#include "emc270/model.hpp"
#include "emc270/protocol.hpp"
#include "hardware.hpp"

namespace emc270::firmware {

class ControllerApp {
public:
  void Begin();
  void Loop();

private:
  enum class ArmStage : std::uint8_t {
    kNone,
    kCenterWritten,
    kRelaySettling,
  };

  void ReadPcFrames();
  void ReadEncoderFrames();
  void HandlePcFrame(const Frame &frame);
  void HandleEncoderFrame(const Frame &frame);
  void ControlTick(std::uint32_t now_ms);
  void UpdateDrive(std::uint32_t now_ms);
  void UpdateArming(std::uint32_t now_ms);
  void UpdateCalibration(std::uint32_t now_ms);
  void UpdateWarnings(std::uint32_t now_ms);

  bool BeginArmSequence(bool for_calibration, std::uint32_t now_ms,
                        std::uint16_t *reason);
  void RequestSafeRelease(Mode final_mode, EventCode event,
                          std::uint32_t now_ms, std::int32_t detail_a = 0,
                          std::int32_t detail_b = 0);
  void FinishSafeRelease(std::uint32_t now_ms);
  void Disarm(std::uint32_t now_ms, EventCode event = EventCode::kDisarmed);
  void FailCalibration(CalibrationFailure failure, std::uint32_t now_ms);
  bool EncoderFresh(std::uint32_t now_ms) const;
  bool CommandIsNeutral() const;
  std::uint16_t CenterX() const;
  std::uint16_t CenterY() const;

  void SendFrame(MessageType type, const std::uint8_t *payload,
                 std::uint16_t payload_size);
  void SendAck(MessageType request, bool accepted, std::uint16_t reason = 0,
               std::int32_t detail = 0);
  void SendStatus(std::uint32_t now_ms);
  void SendConfig();
  void SendEvent(EventCode code, std::uint8_t severity,
                 std::int32_t detail_a = 0, std::int32_t detail_b = 0);
  bool SendCalibrationSample(const CalibrationUpdate &update,
                             std::uint32_t now_ms);
  void SendLogInfo();
  void SendLogChunk(std::uint32_t offset);

  Hardware hardware_{};
  ConfigStore config_store_{};
  CalibrationLog calibration_log_{};
  HardwareSerial encoder_serial_{2};
  FrameParser pc_parser_{};
  FrameParser encoder_parser_{};
  ControllerConfig config_{};
  CalibrationEngine calibration_{};
  CommandWatchdog command_watchdog_{};
  SlewLimiter x_slew_{};
  SlewLimiter y_slew_{};

  Mode mode_{Mode::kBootSafe};
  ArmStage arm_stage_{ArmStage::kNone};
  bool arm_for_calibration_{false};
  bool arm_rearm_required_{false};
  bool release_pending_{false};
  Mode release_final_mode_{Mode::kManualSafe};
  std::uint32_t release_deadline_ms_{0};
  std::uint32_t arm_deadline_ms_{0};
  std::uint32_t neutral_command_since_ms_{0};
  std::uint32_t last_control_ms_{0};
  std::uint32_t last_status_ms_{0};
  std::uint32_t last_encoder_ms_{0};
  std::uint32_t tx_sequence_{0};
  std::uint32_t last_pc_sequence_{0};
  std::uint32_t last_encoder_sequence_{0};
  bool have_pc_sequence_{false};
  bool have_encoder_sequence_{false};
  std::uint32_t host_session_id_{0};
  std::uint32_t calibration_session_id_{0};
  std::uint32_t calibration_sample_index_{0};
  std::uint32_t warnings_{kWarningNone};
  std::uint32_t previous_pc_crc_errors_{0};
  std::uint32_t previous_encoder_crc_errors_{0};
  std::uint32_t previous_pc_format_errors_{0};
  std::uint32_t previous_encoder_format_errors_{0};
  CommandPayload command_{};
  EncoderSpeedPayload encoder_speed_{};
  AdcReading actual_{};
  std::uint16_t target_x_mv_{kDefaultCenterSeedMv};
  std::uint16_t target_y_mv_{kDefaultCenterSeedMv};
  CalibrationFailure last_calibration_failure_{CalibrationFailure::kNone};
};

} // namespace emc270::firmware
