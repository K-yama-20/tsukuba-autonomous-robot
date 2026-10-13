#include "controller_app.hpp"

#include <esp_task_wdt.h>

#include <algorithm>
#include <cmath>

#include "hardware_config.hpp"

namespace emc270::firmware {
namespace {

constexpr std::uint16_t kAckMalformedPayload = 1;
constexpr std::uint16_t kAckInvalidState = 2;
constexpr std::uint16_t kAckInvalidConfig = 3;
constexpr std::uint16_t kAckEncoderUnavailable = 4;
constexpr std::uint16_t kAckAdcUnavailable = 5;
constexpr std::uint16_t kAckLogUnavailable = 6;
constexpr std::uint16_t kAckConfigStoreUnavailable = 7;
constexpr std::uint16_t kAckArmVerification = 8;
constexpr std::size_t kLogChunkBytes = 128;

bool MillivoltsClose(std::uint16_t actual, std::uint16_t target,
                     std::uint16_t tolerance) {
  return std::abs(static_cast<int>(actual) - static_cast<int>(target)) <=
         tolerance;
}

} // namespace

void ControllerApp::Begin() {
  hardware_.Begin();
  Serial.setRxBufferSize(2048);
  Serial.begin(hw::kPcBaud);
  encoder_serial_.setRxBufferSize(1024);
  encoder_serial_.begin(hw::kEncoderBaud, SERIAL_8N1, hw::kEncoderUartRxPin,
                        hw::kEncoderUartTxPin);

  const bool store_ready = config_store_.Begin();
  const bool config_loaded = store_ready && config_store_.Load(&config_);
  if (!store_ready)
    warnings_ |= kWarningConfigStore;
  if (!calibration_log_.Begin())
    warnings_ |= kWarningLogUnavailable;

  mode_ = config_loaded && ValidateReadyConfig(config_).valid
              ? Mode::kReady
              : Mode::kManualSafe;
  target_x_mv_ = CenterX();
  target_y_mv_ = CenterY();
  hardware_.WriteDacMillivolts(target_x_mv_, target_y_mv_,
                               config_.dac_full_scale_mv);
  x_slew_.Reset(target_x_mv_, millis());
  y_slew_.Reset(target_y_mv_, millis());

  esp_task_wdt_init(2, true);
  esp_task_wdt_add(nullptr);
  delay(20);
  SendEvent(EventCode::kBoot, 0, static_cast<std::int32_t>(config_.generation),
            config_loaded ? 1 : 0);
  SendEvent(config_loaded ? EventCode::kConfigLoaded
                          : EventCode::kConfigInvalid,
            config_loaded ? 0 : 1);
}

void ControllerApp::Loop() {
  ReadPcFrames();
  ReadEncoderFrames();
  const auto now_ms = millis();
  FinishSafeRelease(now_ms);
  if (static_cast<std::uint32_t>(now_ms - last_control_ms_) >=
      hw::kControlPeriodMs) {
    last_control_ms_ = now_ms;
    ControlTick(now_ms);
  }
  if (static_cast<std::uint32_t>(now_ms - last_status_ms_) >=
      hw::kStatusPeriodMs) {
    last_status_ms_ = now_ms;
    SendStatus(now_ms);
  }
  esp_task_wdt_reset();
  delay(1);
}

void ControllerApp::ReadPcFrames() {
  Frame frame;
  while (Serial.available() > 0) {
    const auto byte = static_cast<std::uint8_t>(Serial.read());
    if (pc_parser_.Feed(byte, &frame))
      HandlePcFrame(frame);
  }
  if (pc_parser_.crc_errors() != previous_pc_crc_errors_ ||
      pc_parser_.format_errors() != previous_pc_format_errors_) {
    previous_pc_crc_errors_ = pc_parser_.crc_errors();
    previous_pc_format_errors_ = pc_parser_.format_errors();
    warnings_ |= kWarningFrameCrc;
  }
}

void ControllerApp::ReadEncoderFrames() {
  Frame frame;
  while (encoder_serial_.available() > 0) {
    const auto byte = static_cast<std::uint8_t>(encoder_serial_.read());
    if (encoder_parser_.Feed(byte, &frame))
      HandleEncoderFrame(frame);
  }
  if (encoder_parser_.crc_errors() != previous_encoder_crc_errors_ ||
      encoder_parser_.format_errors() != previous_encoder_format_errors_) {
    previous_encoder_crc_errors_ = encoder_parser_.crc_errors();
    previous_encoder_format_errors_ = encoder_parser_.format_errors();
    warnings_ |= kWarningFrameCrc;
  }
}

void ControllerApp::HandlePcFrame(const Frame &frame) {
  if (have_pc_sequence_ && frame.sequence != last_pc_sequence_ + 1U) {
    warnings_ |= kWarningSequenceGap;
  }
  have_pc_sequence_ = true;
  last_pc_sequence_ = frame.sequence;
  const auto now_ms = millis();

  switch (frame.type) {
  case MessageType::kHello: {
    HelloPayload hello;
    if (!DecodeHelloPayload(frame, &hello)) {
      SendAck(frame.type, false, kAckMalformedPayload);
      return;
    }
    host_session_id_ = hello.session_id;
    have_pc_sequence_ = false;
    std::array<std::uint8_t, kMaxPayloadSize> payload{};
    std::uint16_t size = 0;
    const HelloPayload reply{host_session_id_, kHelloOptionAutoResume};
    EncodeHelloPayload(reply, payload.data(), payload.size(), &size);
    SendFrame(MessageType::kHelloReply, payload.data(), size);
    SendEvent(EventCode::kUsbReconnected, 0,
              static_cast<std::int32_t>(host_session_id_));
    return;
  }
  case MessageType::kCommand: {
    CommandPayload command;
    if (!DecodeCommandPayload(frame, &command)) {
      SendAck(frame.type, false, kAckMalformedPayload);
      return;
    }
    command.x_q10000 = std::clamp<std::int16_t>(
        command.x_q10000, -kNormalizedFullScale, kNormalizedFullScale);
    command.y_q10000 = std::clamp<std::int16_t>(
        command.y_q10000, -kNormalizedFullScale, kNormalizedFullScale);
    command_ = command;
    command_watchdog_.Observe(now_ms);
    if ((command.flags & kCommandFlagArm) == 0) {
      arm_rearm_required_ = false;
      if (!release_pending_ &&
          (hardware_.relay_energized() || mode_ == Mode::kDrive ||
           mode_ == Mode::kArming || mode_ == Mode::kCalibrating)) {
        Disarm(now_ms);
      }
    }
    return;
  }
  case MessageType::kSetPreset: {
    if (mode_ == Mode::kDrive || mode_ == Mode::kCalibrating ||
        mode_ == Mode::kArming || release_pending_) {
      SendAck(frame.type, false, kAckInvalidState);
      return;
    }
    PresetPayload preset;
    if (!DecodePresetPayload(frame, &preset)) {
      SendAck(frame.type, false, kAckMalformedPayload);
      return;
    }
    auto proposed = ConfigFromPreset(preset, config_.generation);
    const auto validation = ValidatePreset(proposed);
    if (!validation.valid) {
      SendAck(frame.type, false, kAckInvalidConfig, validation.reason);
      return;
    }
    if (!config_store_.Save(&proposed)) {
      warnings_ |= kWarningConfigStore;
      SendAck(frame.type, false, kAckConfigStoreUnavailable);
      SendEvent(EventCode::kConfigInvalid, 2, kAckConfigStoreUnavailable);
      return;
    }
    config_ = proposed;
    mode_ = Mode::kManualSafe;
    target_x_mv_ = config_.x.seed_mv;
    target_y_mv_ = config_.y.seed_mv;
    hardware_.WriteDacMillivolts(target_x_mv_, target_y_mv_,
                                 config_.dac_full_scale_mv);
    SendAck(frame.type, true);
    SendEvent(EventCode::kPresetSaved, 0,
              static_cast<std::int32_t>(config_.generation));
    return;
  }
  case MessageType::kArm: {
    if (!ValidateReadyConfig(config_).valid) {
      SendAck(frame.type, false, kAckInvalidConfig);
      return;
    }
    arm_rearm_required_ = false;
    SendAck(frame.type, true);
    return;
  }
  case MessageType::kDisarm:
    Disarm(now_ms);
    SendAck(frame.type, true);
    return;
  case MessageType::kStartCalibration: {
    ByteReader reader(frame.payload.data(), frame.payload_size);
    std::uint32_t session_id = 0;
    if (!reader.U32(&session_id) || reader.remaining() != 0) {
      SendAck(frame.type, false, kAckMalformedPayload);
      return;
    }
    if (!ValidatePreset(config_).valid || mode_ == Mode::kDrive ||
        mode_ == Mode::kCalibrating || mode_ == Mode::kArming ||
        release_pending_) {
      SendAck(frame.type, false, kAckInvalidState);
      return;
    }
    if (!EncoderFresh(now_ms)) {
      SendAck(frame.type, false, kAckEncoderUnavailable);
      return;
    }
    if (!hardware_.adc_available()) {
      SendAck(frame.type, false, kAckAdcUnavailable);
      return;
    }
    if (!calibration_log_.available()) {
      SendAck(frame.type, false, kAckLogUnavailable);
      return;
    }
    calibration_session_id_ = session_id;
    calibration_sample_index_ = 0;
    if (!calibration_log_.StartSession(calibration_session_id_)) {
      warnings_ |= kWarningLogUnavailable;
      SendAck(frame.type, false, kAckLogUnavailable);
      SendEvent(EventCode::kLogUnavailable, 2,
                static_cast<std::int32_t>(calibration_session_id_));
      return;
    }
    arm_rearm_required_ = false;
    std::uint16_t reason = 0;
    if (!BeginArmSequence(true, now_ms, &reason)) {
      const auto failure = reason == kAckEncoderUnavailable
                               ? CalibrationFailure::kEncoderUnavailable
                           : reason == kAckAdcUnavailable
                               ? CalibrationFailure::kAdcUnavailable
                               : CalibrationFailure::kInternal;
      FailCalibration(failure, now_ms);
      SendAck(frame.type, false, reason);
      return;
    }
    SendAck(frame.type, true);
    return;
  }
  case MessageType::kAbortCalibration:
    if (mode_ == Mode::kCalibrating ||
        (mode_ == Mode::kArming && arm_for_calibration_)) {
      FailCalibration(CalibrationFailure::kAbortedByHost, now_ms);
      SendAck(frame.type, true);
    } else {
      SendAck(frame.type, false, kAckInvalidState);
    }
    return;
  case MessageType::kGetStatus:
    SendStatus(now_ms);
    return;
  case MessageType::kGetConfig:
    SendConfig();
    return;
  case MessageType::kLogInfoRequest:
    SendLogInfo();
    return;
  case MessageType::kLogChunkRequest: {
    ByteReader reader(frame.payload.data(), frame.payload_size);
    std::uint32_t offset = 0;
    if (!reader.U32(&offset) || reader.remaining() != 0) {
      SendAck(frame.type, false, kAckMalformedPayload);
    } else {
      SendLogChunk(offset);
    }
    return;
  }
  case MessageType::kClearLog:
    if (mode_ == Mode::kCalibrating ||
        (mode_ == Mode::kArming && arm_for_calibration_)) {
      SendAck(frame.type, false, kAckInvalidState);
    } else {
      SendAck(frame.type, calibration_log_.Clear(),
              calibration_log_.available() ? 0 : kAckLogUnavailable);
    }
    return;
  default:
    SendAck(frame.type, false, kAckInvalidState);
    return;
  }
}

void ControllerApp::HandleEncoderFrame(const Frame &frame) {
  if (frame.type != MessageType::kEncoderSpeed)
    return;
  EncoderSpeedPayload speed;
  if (!DecodeEncoderSpeedPayload(frame, &speed))
    return;
  if (have_encoder_sequence_ && frame.sequence != last_encoder_sequence_ + 1U) {
    warnings_ |= kWarningSequenceGap;
  }
  have_encoder_sequence_ = true;
  last_encoder_sequence_ = frame.sequence;
  encoder_speed_ = speed;
  last_encoder_ms_ = millis();
}

void ControllerApp::ControlTick(std::uint32_t now_ms) {
  actual_ = hardware_.ReadActualMillivolts();
  UpdateWarnings(now_ms);

  if (mode_ == Mode::kArming) {
    UpdateArming(now_ms);
    return;
  }
  if (mode_ == Mode::kCalibrating) {
    UpdateCalibration(now_ms);
    return;
  }
  if (mode_ == Mode::kDrive) {
    if (command_watchdog_.Expired(now_ms, config_.watchdog_ms)) {
      warnings_ |= kWarningUsbWatchdog;
      RequestSafeRelease(Mode::kFailsafe, EventCode::kWatchdogExpired, now_ms,
                         command_watchdog_.Age(now_ms));
      return;
    }
    UpdateDrive(now_ms);
    return;
  }

  if ((command_.flags & kCommandFlagArm) != 0 && !arm_rearm_required_ &&
      !command_watchdog_.Expired(now_ms, config_.watchdog_ms) &&
      ValidateReadyConfig(config_).valid) {
    if (CommandIsNeutral()) {
      if (neutral_command_since_ms_ == 0)
        neutral_command_since_ms_ = now_ms;
      if (now_ms - neutral_command_since_ms_ >= hw::kArmNeutralHoldMs) {
        std::uint16_t reason = 0;
        BeginArmSequence(false, now_ms, &reason);
        neutral_command_since_ms_ = 0;
      }
    } else {
      neutral_command_since_ms_ = 0;
    }
  } else {
    neutral_command_since_ms_ = 0;
  }
}

void ControllerApp::UpdateDrive(std::uint32_t now_ms) {
  const auto requested_x =
      MapNormalizedToMillivolts(command_.x_q10000, config_.x);
  const auto requested_y =
      MapNormalizedToMillivolts(command_.y_q10000, config_.y);
  target_x_mv_ = x_slew_.Step(requested_x, config_.dac_full_scale_mv,
                              config_.slew_full_scale_ms, now_ms);
  target_y_mv_ = y_slew_.Step(requested_y, config_.dac_full_scale_mv,
                              config_.slew_full_scale_ms, now_ms);
  hardware_.WriteDacMillivolts(target_x_mv_, target_y_mv_,
                               config_.dac_full_scale_mv);
}

void ControllerApp::UpdateArming(std::uint32_t now_ms) {
  if (command_watchdog_.Expired(now_ms, config_.watchdog_ms)) {
    warnings_ |= kWarningUsbWatchdog;
    if (arm_for_calibration_) {
      FailCalibration(CalibrationFailure::kHostWatchdog, now_ms);
    } else {
      RequestSafeRelease(Mode::kFailsafe, EventCode::kWatchdogExpired, now_ms);
    }
    return;
  }
  if (arm_for_calibration_ && !EncoderFresh(now_ms)) {
    FailCalibration(CalibrationFailure::kEncoderUnavailable, now_ms);
    return;
  }
  if (arm_for_calibration_) {
    CalibrationUpdate arming;
    arming.phase = CalibrationPhase::kArming;
    arming.verdict = CalibrationVerdict::kSettling;
    arming.target_x_mv = target_x_mv_;
    arming.target_y_mv = target_y_mv_;
    if (!SendCalibrationSample(arming, now_ms)) {
      warnings_ |= kWarningLogUnavailable;
      SendEvent(EventCode::kLogUnavailable, 2,
                static_cast<std::int32_t>(calibration_session_id_),
                static_cast<std::int32_t>(calibration_sample_index_));
      FailCalibration(CalibrationFailure::kLogUnavailable, now_ms);
      return;
    }
  }
  if (now_ms < arm_deadline_ms_)
    return;
  if (arm_stage_ == ArmStage::kCenterWritten) {
    hardware_.SetRelay(true);
    arm_stage_ = ArmStage::kRelaySettling;
    arm_deadline_ms_ = now_ms + hw::kRelaySettleMs;
    return;
  }
  if (arm_stage_ != ArmStage::kRelaySettling)
    return;

  actual_ = hardware_.ReadActualMillivolts();
  const bool verified = actual_.valid &&
                        MillivoltsClose(actual_.x_mv, target_x_mv_,
                                        config_.output_warn_tolerance_mv) &&
                        MillivoltsClose(actual_.y_mv, target_y_mv_,
                                        config_.output_warn_tolerance_mv);
  if (!verified) {
    warnings_ |= kWarningArmVerification;
    arm_rearm_required_ = true;
    command_.flags = 0;
    SendEvent(EventCode::kArmPostSwitchMismatch, 2,
              static_cast<std::int32_t>(actual_.x_mv),
              static_cast<std::int32_t>(actual_.y_mv));
    hardware_.SetRelay(false);
    arm_stage_ = ArmStage::kNone;
    if (arm_for_calibration_) {
      FailCalibration(CalibrationFailure::kArmVerification, now_ms);
    } else {
      mode_ =
          ValidateReadyConfig(config_).valid ? Mode::kReady : Mode::kManualSafe;
      SendEvent(EventCode::kArmRejected, 2, kAckArmVerification);
    }
    return;
  }

  arm_stage_ = ArmStage::kNone;
  x_slew_.Reset(target_x_mv_, now_ms);
  y_slew_.Reset(target_y_mv_, now_ms);
  if (arm_for_calibration_) {
    if (!calibration_.Start(config_, calibration_session_id_, now_ms)) {
      FailCalibration(CalibrationFailure::kInternal, now_ms);
      return;
    }
    mode_ = Mode::kCalibrating;
    SendEvent(EventCode::kCalibrationStarted, 0,
              static_cast<std::int32_t>(calibration_session_id_));
  } else {
    mode_ = Mode::kDrive;
    SendEvent(EventCode::kArmSucceeded, 0);
  }
}

void ControllerApp::UpdateCalibration(std::uint32_t now_ms) {
  if (command_watchdog_.Expired(now_ms, config_.watchdog_ms)) {
    FailCalibration(CalibrationFailure::kHostWatchdog, now_ms);
    return;
  }
  CalibrationInput input;
  input.now_ms = now_ms;
  input.encoder_valid = EncoderFresh(now_ms);
  input.left_mm_s = encoder_speed_.left_mm_s;
  input.right_mm_s = encoder_speed_.right_mm_s;
  const auto update = calibration_.Tick(input);
  target_x_mv_ = update.target_x_mv;
  target_y_mv_ = update.target_y_mv;
  if (update.target_changed) {
    hardware_.WriteDacMillivolts(target_x_mv_, target_y_mv_,
                                 config_.dac_full_scale_mv);
  }
  if (!SendCalibrationSample(update, now_ms)) {
    warnings_ |= kWarningLogUnavailable;
    SendEvent(EventCode::kLogUnavailable, 2,
              static_cast<std::int32_t>(calibration_session_id_),
              static_cast<std::int32_t>(calibration_sample_index_));
    FailCalibration(CalibrationFailure::kLogUnavailable, now_ms);
    return;
  }

  if (update.completed) {
    config_ = calibration_.result_config();
    if (!config_store_.Save(&config_)) {
      warnings_ |= kWarningConfigStore;
      SendEvent(EventCode::kConfigInvalid, 2, kAckConfigStoreUnavailable);
      FailCalibration(CalibrationFailure::kConfigStoreUnavailable, now_ms);
      return;
    }
    calibration_log_.EndSession();
    last_calibration_failure_ = CalibrationFailure::kNone;
    arm_for_calibration_ = false;
    RequestSafeRelease(Mode::kReady, EventCode::kCalibrationCompleted, now_ms,
                       static_cast<std::int32_t>(config_.generation));
  } else if (update.failed) {
    FailCalibration(update.failure, now_ms);
  }
}

void ControllerApp::UpdateWarnings(std::uint32_t now_ms) {
  const auto previous_mismatch =
      warnings_ & (kWarningOutputMismatchX | kWarningOutputMismatchY);
  if (!actual_.valid) {
    if ((warnings_ & kWarningAdcUnavailable) == 0) {
      SendEvent(EventCode::kAdcUnavailable, 1);
    }
    warnings_ |= kWarningAdcUnavailable;
  } else {
    warnings_ &= ~kWarningAdcUnavailable;
    if (hardware_.relay_energized() && mode_ != Mode::kArming) {
      if (!MillivoltsClose(actual_.x_mv, target_x_mv_,
                           config_.output_warn_tolerance_mv)) {
        warnings_ |= kWarningOutputMismatchX;
      } else {
        warnings_ &= ~kWarningOutputMismatchX;
      }
      if (!MillivoltsClose(actual_.y_mv, target_y_mv_,
                           config_.output_warn_tolerance_mv)) {
        warnings_ |= kWarningOutputMismatchY;
      } else {
        warnings_ &= ~kWarningOutputMismatchY;
      }
    } else {
      warnings_ &= ~(kWarningOutputMismatchX | kWarningOutputMismatchY);
    }
  }

  const auto current_mismatch =
      warnings_ & (kWarningOutputMismatchX | kWarningOutputMismatchY);
  const auto new_mismatch = current_mismatch & ~previous_mismatch;
  if (new_mismatch != 0) {
    SendEvent(EventCode::kOutputMismatch, 1,
              static_cast<std::int32_t>(new_mismatch));
  }

  if (!EncoderFresh(now_ms)) {
    if ((warnings_ & kWarningEncoderStale) == 0) {
      SendEvent(EventCode::kEncoderStale, 1,
                static_cast<std::int32_t>(now_ms - last_encoder_ms_));
    }
    warnings_ |= kWarningEncoderStale;
  } else {
    warnings_ &= ~kWarningEncoderStale;
  }
}

bool ControllerApp::BeginArmSequence(bool for_calibration, std::uint32_t now_ms,
                                     std::uint16_t *reason) {
  const auto validation =
      for_calibration ? ValidatePreset(config_) : ValidateReadyConfig(config_);
  if (!validation.valid) {
    if (reason != nullptr)
      *reason = kAckInvalidConfig;
    SendEvent(EventCode::kArmRejected, 2, validation.reason);
    return false;
  }
  if (!hardware_.adc_available()) {
    if (reason != nullptr)
      *reason = kAckAdcUnavailable;
    SendEvent(EventCode::kArmRejected, 2, kAckAdcUnavailable);
    return false;
  }
  if (for_calibration && !EncoderFresh(now_ms)) {
    if (reason != nullptr)
      *reason = kAckEncoderUnavailable;
    return false;
  }

  arm_for_calibration_ = for_calibration;
  target_x_mv_ = for_calibration ? config_.x.seed_mv : CenterX();
  target_y_mv_ = for_calibration ? config_.y.seed_mv : CenterY();
  hardware_.SetRelay(false);
  hardware_.WriteDacMillivolts(target_x_mv_, target_y_mv_,
                               config_.dac_full_scale_mv);
  arm_stage_ = ArmStage::kCenterWritten;
  arm_deadline_ms_ = now_ms + hw::kControlPeriodMs;
  mode_ = Mode::kArming;
  if (reason != nullptr)
    *reason = 0;
  SendEvent(EventCode::kArmStarted, 0, for_calibration ? 1 : 0);
  return true;
}

void ControllerApp::RequestSafeRelease(Mode final_mode, EventCode event,
                                       std::uint32_t now_ms,
                                       std::int32_t detail_a,
                                       std::int32_t detail_b) {
  target_x_mv_ = CenterX();
  target_y_mv_ = CenterY();
  hardware_.WriteDacMillivolts(target_x_mv_, target_y_mv_,
                               config_.dac_full_scale_mv);
  release_pending_ = true;
  release_final_mode_ = final_mode;
  release_deadline_ms_ = now_ms + hw::kFailsafeRelayDelayMs;
  mode_ = final_mode;
  const std::uint8_t severity = event == EventCode::kWatchdogExpired ||
                                        event == EventCode::kCalibrationFailed
                                    ? 2
                                    : 0;
  SendEvent(event, severity, detail_a, detail_b);
}

void ControllerApp::FinishSafeRelease(std::uint32_t now_ms) {
  if (!release_pending_ || now_ms < release_deadline_ms_)
    return;
  hardware_.SetRelay(false);
  release_pending_ = false;
  mode_ = release_final_mode_;
  arm_stage_ = ArmStage::kNone;
  x_slew_.Reset(target_x_mv_, now_ms);
  y_slew_.Reset(target_y_mv_, now_ms);
}

void ControllerApp::Disarm(std::uint32_t now_ms, EventCode event) {
  if (mode_ == Mode::kCalibrating ||
      (mode_ == Mode::kArming && arm_for_calibration_)) {
    FailCalibration(CalibrationFailure::kAbortedByHost, now_ms);
    command_.flags = 0;
    neutral_command_since_ms_ = 0;
    return;
  }
  arm_rearm_required_ = false;
  const auto final_mode =
      ValidateReadyConfig(config_).valid ? Mode::kReady : Mode::kManualSafe;
  RequestSafeRelease(final_mode, event, now_ms);
  command_.flags = 0;
  neutral_command_since_ms_ = 0;
}

void ControllerApp::FailCalibration(CalibrationFailure failure,
                                    std::uint32_t now_ms) {
  calibration_.Abort(failure);
  last_calibration_failure_ = failure;
  warnings_ |= kWarningCalibrationFailed;
  arm_rearm_required_ = true;
  CalibrationUpdate terminal;
  terminal.phase = failure == CalibrationFailure::kAbortedByHost
                       ? CalibrationPhase::kAborted
                       : CalibrationPhase::kFailed;
  terminal.failed = true;
  terminal.failure = failure;
  terminal.target_x_mv = target_x_mv_;
  terminal.target_y_mv = target_y_mv_;
  SendCalibrationSample(terminal, now_ms);
  calibration_log_.EndSession();
  arm_for_calibration_ = false;
  command_.flags = 0;
  const auto event = failure == CalibrationFailure::kAbortedByHost
                         ? EventCode::kCalibrationAborted
                         : EventCode::kCalibrationFailed;
  RequestSafeRelease(Mode::kManualSafe, event, now_ms,
                     static_cast<std::int32_t>(failure));
}

bool ControllerApp::EncoderFresh(std::uint32_t now_ms) const {
  return have_encoder_sequence_ &&
         (encoder_speed_.status & kEncoderStatusValid) != 0 &&
         static_cast<std::uint32_t>(now_ms - last_encoder_ms_) <=
             hw::kEncoderStaleMs;
}

bool ControllerApp::CommandIsNeutral() const {
  return std::abs(command_.x_q10000) <= hw::kArmNeutralCommandLimit &&
         std::abs(command_.y_q10000) <= hw::kArmNeutralCommandLimit;
}

std::uint16_t ControllerApp::CenterX() const {
  return config_.neutral_valid != 0 ? config_.x.neutral_mid_mv
                                    : config_.x.seed_mv;
}

std::uint16_t ControllerApp::CenterY() const {
  return config_.neutral_valid != 0 ? config_.y.neutral_mid_mv
                                    : config_.y.seed_mv;
}

void ControllerApp::SendFrame(MessageType type, const std::uint8_t *payload,
                              std::uint16_t payload_size) {
  EncodedFrame frame;
  if (!EncodeFrame(type, ++tx_sequence_, millis(), payload, payload_size,
                   &frame)) {
    return;
  }
  Serial.write(frame.bytes.data(), frame.size);
}

void ControllerApp::SendAck(MessageType request, bool accepted,
                            std::uint16_t reason, std::int32_t detail) {
  const AckPayload ack{request, static_cast<std::uint8_t>(accepted), reason,
                       detail};
  std::array<std::uint8_t, kMaxPayloadSize> payload{};
  std::uint16_t size = 0;
  if (EncodeAckPayload(ack, payload.data(), payload.size(), &size)) {
    SendFrame(MessageType::kAck, payload.data(), size);
  }
}

void ControllerApp::SendStatus(std::uint32_t now_ms) {
  StatusPayload status;
  status.mode = mode_;
  status.relay_energized = hardware_.relay_energized();
  status.config_valid = ValidateReadyConfig(config_).valid;
  status.encoder_valid = EncoderFresh(now_ms);
  status.rearm_required = arm_rearm_required_;
  status.warnings = warnings_;
  status.command_age_ms = command_watchdog_.Age(now_ms);
  status.encoder_age_ms =
      have_encoder_sequence_
          ? static_cast<std::uint32_t>(now_ms - last_encoder_ms_)
          : UINT32_MAX;
  status.command_x_q10000 = command_.x_q10000;
  status.command_y_q10000 = command_.y_q10000;
  status.target_x_mv = target_x_mv_;
  status.target_y_mv = target_y_mv_;
  status.actual_x_mv = actual_.x_mv;
  status.actual_y_mv = actual_.y_mv;
  status.left_mm_s = encoder_speed_.left_mm_s;
  status.right_mm_s = encoder_speed_.right_mm_s;
  status.config_generation = config_.generation;
  status.last_calibration_failure = last_calibration_failure_;
  std::array<std::uint8_t, kMaxPayloadSize> payload{};
  std::uint16_t size = 0;
  if (EncodeStatusPayload(status, payload.data(), payload.size(), &size)) {
    SendFrame(MessageType::kStatus, payload.data(), size);
  }
}

void ControllerApp::SendConfig() {
  std::array<std::uint8_t, kMaxPayloadSize> payload{};
  std::uint16_t size = 0;
  if (EncodeControllerConfigPayload(config_, payload.data(), payload.size(),
                                    &size)) {
    SendFrame(MessageType::kConfig, payload.data(), size);
  }
}

void ControllerApp::SendEvent(EventCode code, std::uint8_t severity,
                              std::int32_t detail_a, std::int32_t detail_b) {
  EventPayload event;
  event.code = code;
  event.severity = severity;
  event.mode = mode_;
  event.detail_a = detail_a;
  event.detail_b = detail_b;
  event.target_x_mv = target_x_mv_;
  event.target_y_mv = target_y_mv_;
  event.actual_x_mv = actual_.x_mv;
  event.actual_y_mv = actual_.y_mv;
  std::array<std::uint8_t, kMaxPayloadSize> payload{};
  std::uint16_t size = 0;
  if (EncodeEventPayload(event, payload.data(), payload.size(), &size)) {
    SendFrame(MessageType::kEvent, payload.data(), size);
  }
}

bool ControllerApp::SendCalibrationSample(const CalibrationUpdate &update,
                                          std::uint32_t now_ms) {
  CalibrationSamplePayload sample;
  sample.session_id = calibration_session_id_;
  sample.sample_index = calibration_sample_index_++;
  sample.phase = static_cast<std::uint8_t>(update.phase);
  sample.axis = update.axis;
  sample.direction = update.direction;
  sample.verdict = static_cast<std::uint8_t>(update.verdict);
  sample.target_x_mv = target_x_mv_;
  sample.target_y_mv = target_y_mv_;
  sample.actual_x_mv = actual_.x_mv;
  sample.actual_y_mv = actual_.y_mv;
  sample.left_mm_s = encoder_speed_.left_mm_s;
  sample.right_mm_s = encoder_speed_.right_mm_s;
  sample.stationary_ms = update.stationary_ms;
  sample.failure = update.failure;
  std::array<std::uint8_t, kMaxPayloadSize> payload{};
  std::uint16_t size = 0;
  if (!EncodeCalibrationSamplePayload(sample, payload.data(), payload.size(),
                                      &size)) {
    return false;
  }
  EncodedFrame frame;
  if (!EncodeFrame(MessageType::kCalibrationSample, ++tx_sequence_, now_ms,
                   payload.data(), size, &frame)) {
    return false;
  }
  Serial.write(frame.bytes.data(), frame.size);
  if (!calibration_log_.Append(frame)) {
    warnings_ |= kWarningLogUnavailable;
    return false;
  }
  return true;
}

void ControllerApp::SendLogInfo() {
  std::array<std::uint8_t, kMaxPayloadSize> payload{};
  ByteWriter writer(payload.data(), payload.size());
  writer.U32(calibration_log_.session_id());
  writer.U32(static_cast<std::uint32_t>(calibration_log_.Size()));
  writer.U8(calibration_log_.available());
  if (writer.ok()) {
    SendFrame(MessageType::kLogInfo, payload.data(), writer.size());
  }
}

void ControllerApp::SendLogChunk(std::uint32_t offset) {
  std::array<std::uint8_t, kMaxPayloadSize> payload{};
  std::array<std::uint8_t, kLogChunkBytes> chunk{};
  const auto read = calibration_log_.Read(offset, chunk.data(), chunk.size());
  ByteWriter writer(payload.data(), payload.size());
  writer.U32(static_cast<std::uint32_t>(calibration_log_.Size()));
  writer.U32(offset);
  writer.U16(static_cast<std::uint16_t>(read));
  if (read != 0)
    writer.Bytes(chunk.data(), read);
  if (writer.ok()) {
    SendFrame(MessageType::kLogChunk, payload.data(), writer.size());
  }
}

} // namespace emc270::firmware
