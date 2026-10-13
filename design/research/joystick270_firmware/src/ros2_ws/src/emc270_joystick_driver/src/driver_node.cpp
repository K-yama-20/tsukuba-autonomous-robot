#include "emc270_joystick_driver/driver_node.hpp"

#include <diagnostic_msgs/msg/diagnostic_status.hpp>
#include <diagnostic_msgs/msg/key_value.hpp>

#include <algorithm>
#include <array>
#include <cmath>
#include <filesystem>
#include <functional>
#include <iomanip>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace emc270_joystick_driver {
namespace {

constexpr std::uint32_t kReconnectPeriodMs = 200;
constexpr std::uint32_t kHelloPeriodMs = 500;
constexpr std::uint32_t kCommandPeriodMs = 20;
// Keep the host neutral window longer than the ESP32's 500 ms requirement so
// timer and USB scheduling jitter cannot release a non-neutral command first.
constexpr std::uint32_t kRecoveryNeutralMs = 600;

std::string ModeName(emc270::Mode mode) {
  switch (mode) {
  case emc270::Mode::kBootSafe:
    return "BOOT_SAFE";
  case emc270::Mode::kManualSafe:
    return "MANUAL_SAFE";
  case emc270::Mode::kReady:
    return "READY";
  case emc270::Mode::kArming:
    return "ARMING";
  case emc270::Mode::kDrive:
    return "DRIVE";
  case emc270::Mode::kCalibrating:
    return "CALIBRATING";
  case emc270::Mode::kFailsafe:
    return "FAILSAFE";
  }
  return "UNKNOWN";
}

std::string EventName(emc270::EventCode code) {
  switch (code) {
  case emc270::EventCode::kBoot:
    return "boot";
  case emc270::EventCode::kConfigLoaded:
    return "configuration loaded";
  case emc270::EventCode::kConfigInvalid:
    return "configuration invalid";
  case emc270::EventCode::kPresetSaved:
    return "preset saved";
  case emc270::EventCode::kArmStarted:
    return "ARM started";
  case emc270::EventCode::kArmSucceeded:
    return "ARM succeeded";
  case emc270::EventCode::kArmRejected:
    return "ARM rejected; explicit re-ARM required";
  case emc270::EventCode::kArmPostSwitchMismatch:
    return "ARM output verification mismatch; explicit re-ARM required";
  case emc270::EventCode::kDisarmed:
    return "disarmed";
  case emc270::EventCode::kWatchdogExpired:
    return "command watchdog expired";
  case emc270::EventCode::kUsbReconnected:
    return "USB session connected";
  case emc270::EventCode::kEncoderStale:
    return "encoder UART stale";
  case emc270::EventCode::kAdcUnavailable:
    return "ADC unavailable";
  case emc270::EventCode::kOutputMismatch:
    return "commanded and measured output mismatch";
  case emc270::EventCode::kCalibrationStarted:
    return "calibration started";
  case emc270::EventCode::kCalibrationCompleted:
    return "calibration completed; explicit ARM required";
  case emc270::EventCode::kCalibrationAborted:
    return "calibration aborted; explicit re-ARM required";
  case emc270::EventCode::kCalibrationFailed:
    return "calibration failed; explicit re-ARM required";
  case emc270::EventCode::kLogUnavailable:
    return "calibration log unavailable";
  }
  return "unknown controller event";
}

diagnostic_msgs::msg::KeyValue KeyValue(const std::string &key,
                                        const std::string &value) {
  diagnostic_msgs::msg::KeyValue result;
  result.key = key;
  result.value = value;
  return result;
}

std::uint32_t NewSessionId() {
  const auto now = std::chrono::system_clock::now().time_since_epoch();
  return static_cast<std::uint32_t>(
      std::chrono::duration_cast<std::chrono::milliseconds>(now).count());
}

} // namespace

DriverNode::DriverNode()
    : Node("emc270_joystick_driver"),
      steady_epoch_(std::chrono::steady_clock::now()),
      session_id_(NewSessionId()) {
  device_ =
      declare_parameter<std::string>("device", "/dev/serial/by-id/REQUIRED");
  baud_ = declare_parameter<int>("baud", 460800);
  command_input_timeout_ms_ =
      declare_parameter<int>("command_input_timeout_ms", 300);
  log_directory_ = declare_parameter<std::string>(
      "log_directory", std::filesystem::absolute("calibration_logs").string());
  if (device_.empty() || device_.find("REQUIRED") != std::string::npos ||
      !std::filesystem::path(device_).is_absolute()) {
    throw std::invalid_argument(
        "device must be a completed absolute /dev/serial/by-id path");
  }
  if (baud_ != 460800) {
    throw std::invalid_argument("baud must be 460800 for this firmware");
  }
  if (command_input_timeout_ms_ < 100 || command_input_timeout_ms_ > 2000) {
    throw std::invalid_argument("command_input_timeout_ms must be 100..2000");
  }
  if (log_directory_.empty() ||
      !std::filesystem::path(log_directory_).is_absolute()) {
    throw std::invalid_argument("log_directory must be an absolute path");
  }

  const auto command_qos = rclcpp::QoS(rclcpp::KeepLast(1)).reliable();
  command_subscription_ =
      create_subscription<emc270_joystick_msgs::msg::NormalizedCommand>(
          "~/command", command_qos,
          std::bind(&DriverNode::OnCommand, this, std::placeholders::_1));
  status_publisher_ =
      create_publisher<emc270_joystick_msgs::msg::JoystickStatus>("~/status",
                                                                  10);
  event_publisher_ =
      create_publisher<emc270_joystick_msgs::msg::ControllerEvent>("~/event",
                                                                   50);
  calibration_publisher_ =
      create_publisher<emc270_joystick_msgs::msg::CalibrationSample>(
          "~/calibration_sample", 100);
  diagnostics_publisher_ =
      create_publisher<diagnostic_msgs::msg::DiagnosticArray>("/diagnostics",
                                                              10);

  arm_service_ = create_service<Trigger>(
      "~/arm", std::bind(&DriverNode::OnArm, this, std::placeholders::_1,
                         std::placeholders::_2));
  disarm_service_ = create_service<Trigger>(
      "~/disarm", std::bind(&DriverNode::OnDisarm, this, std::placeholders::_1,
                            std::placeholders::_2));
  start_calibration_service_ = create_service<Trigger>(
      "~/start_calibration",
      std::bind(&DriverNode::OnStartCalibration, this, std::placeholders::_1,
                std::placeholders::_2));
  abort_calibration_service_ = create_service<Trigger>(
      "~/abort_calibration",
      std::bind(&DriverNode::OnAbortCalibration, this, std::placeholders::_1,
                std::placeholders::_2));
  recover_log_service_ = create_service<Trigger>(
      "~/recover_log", std::bind(&DriverNode::OnRecoverLog, this,
                                 std::placeholders::_1, std::placeholders::_2));
  set_preset_service_ = create_service<SetPreset>(
      "~/set_preset", std::bind(&DriverNode::OnSetPreset, this,
                                std::placeholders::_1, std::placeholders::_2));

  timer_ = create_wall_timer(std::chrono::milliseconds(5),
                             std::bind(&DriverNode::Tick, this));
}

DriverNode::~DriverNode() {
  if (serial_.is_open()) {
    arm_requested_ = false;
    SendEmpty(emc270::MessageType::kDisarm);
  }
  CloseCalibrationCsv();
  if (recovered_log_.is_open())
    recovered_log_.close();
}

void DriverNode::Tick() {
  const auto now_ms = SteadyNowMs();
  if (!serial_.is_open()) {
    TryOpen(now_ms);
    return;
  }
  ReadFrames();
  if (!serial_.is_open())
    return;
  if (!handshake_) {
    if (now_ms - last_hello_ms_ >= kHelloPeriodMs)
      SendHello();
    return;
  }
  if (now_ms - last_command_tx_ms_ >= kCommandPeriodMs) {
    SendCommand(now_ms);
  }
}

void DriverNode::TryOpen(std::uint32_t now_ms) {
  if (now_ms - last_open_attempt_ms_ < kReconnectPeriodMs)
    return;
  last_open_attempt_ms_ = now_ms;
  std::string error;
  if (!serial_.Open(device_, baud_, &error)) {
    if (error != last_serial_error_) {
      RCLCPP_WARN(get_logger(), "%s", error.c_str());
      last_serial_error_ = error;
      PublishDiagnostics();
    }
    return;
  }
  last_serial_error_.clear();
  parser_.Reset();
  handshake_ = false;
  neutral_until_ms_ = now_ms + kRecoveryNeutralMs;
  SendHello();
  RCLCPP_INFO(get_logger(), "Opened %s at %d baud", device_.c_str(), baud_);
}

void DriverNode::ReadFrames() {
  std::array<std::uint8_t, 1024> input{};
  std::string error;
  const auto count = serial_.Read(input.data(), input.size(), &error);
  if (count < 0) {
    HandleSerialFailure(error);
    return;
  }
  emc270::Frame frame;
  for (long index = 0; index < count; ++index) {
    if (parser_.Feed(input[static_cast<std::size_t>(index)], &frame)) {
      HandleFrame(frame);
    }
  }
  if (parser_.crc_errors() != observed_crc_errors_ ||
      parser_.format_errors() != observed_format_errors_) {
    observed_crc_errors_ = parser_.crc_errors();
    observed_format_errors_ = parser_.format_errors();
    RCLCPP_WARN(get_logger(), "USB frame errors: crc=%u format=%u",
                observed_crc_errors_, observed_format_errors_);
  }
}

void DriverNode::HandleSerialFailure(const std::string &error) {
  handshake_ = false;
  last_serial_error_ = error;
  if (recovered_log_.is_open()) {
    recovered_log_.close();
    recovered_log_.clear();
    recovered_offset_ = 0;
  }
  if (calibration_active_) {
    calibration_active_ = false;
    arm_requested_ = false;
    host_rearm_required_ = true;
    CloseCalibrationCsv();
    PublishHostEvent(
        emc270_joystick_msgs::msg::ControllerEvent::
            EVENT_HOST_CALIBRATION_LINK_LOST,
        2, static_cast<std::uint8_t>(emc270::Mode::kCalibrating),
        "USB link lost during calibration; restart calibration and re-ARM");
    RCLCPP_ERROR(get_logger(),
                 "USB link lost during calibration; automatic ARM is blocked");
  }
  PublishDiagnostics();
}

void DriverNode::HandleFrame(const emc270::Frame &frame) {
  switch (frame.type) {
  case emc270::MessageType::kHelloReply: {
    emc270::HelloPayload reply;
    if (!emc270::DecodeHelloPayload(frame, &reply))
      return;
    handshake_ = true;
    neutral_until_ms_ = SteadyNowMs() + kRecoveryNeutralMs;
    SendEmpty(emc270::MessageType::kGetStatus);
    SendEmpty(emc270::MessageType::kGetConfig);
    SendEmpty(emc270::MessageType::kLogInfoRequest);
    RCLCPP_INFO(get_logger(), "ESP32 handshake complete (session=%u)",
                reply.session_id);
    return;
  }
  case emc270::MessageType::kStatus: {
    emc270::StatusPayload status;
    if (!emc270::DecodeStatusPayload(frame, &status))
      return;
    calibration_active_ =
        status.mode == emc270::Mode::kCalibrating ||
        (status.mode == emc270::Mode::kArming && calibration_active_);
    PublishStatus(status);
    PublishDiagnostics(&status);
    return;
  }
  case emc270::MessageType::kEvent: {
    emc270::EventPayload event;
    if (!emc270::DecodeEventPayload(frame, &event))
      return;
    PublishEvent(event);
    if (event.code == emc270::EventCode::kBoot ||
        event.code == emc270::EventCode::kWatchdogExpired) {
      if (arm_requested_ && !host_rearm_required_) {
        neutral_until_ms_ = SteadyNowMs() + kRecoveryNeutralMs;
      }
    }
    if (event.code == emc270::EventCode::kArmRejected ||
        event.code == emc270::EventCode::kArmPostSwitchMismatch) {
      host_rearm_required_ = true;
      arm_requested_ = false;
    }
    if (event.code == emc270::EventCode::kCalibrationCompleted ||
        event.code == emc270::EventCode::kCalibrationFailed ||
        event.code == emc270::EventCode::kCalibrationAborted) {
      calibration_active_ = false;
      arm_requested_ = false;
      host_rearm_required_ = true;
      CloseCalibrationCsv();
    }
    return;
  }
  case emc270::MessageType::kCalibrationSample: {
    emc270::CalibrationSamplePayload sample;
    if (emc270::DecodeCalibrationSamplePayload(frame, &sample)) {
      PublishCalibrationSample(frame, sample);
    }
    return;
  }
  case emc270::MessageType::kAck: {
    emc270::AckPayload ack;
    if (!emc270::DecodeAckPayload(frame, &ack))
      return;
    if (ack.accepted == 0) {
      RCLCPP_ERROR(
          get_logger(), "ESP32 rejected request 0x%02x: reason=%u detail=%d",
          static_cast<unsigned>(ack.request_type), ack.reason, ack.detail);
      if (ack.request_type == emc270::MessageType::kArm) {
        host_rearm_required_ = true;
        arm_requested_ = false;
      }
      if (ack.request_type == emc270::MessageType::kStartCalibration) {
        calibration_active_ = false;
        arm_requested_ = false;
        host_rearm_required_ = true;
        CloseCalibrationCsv();
      }
    }
    return;
  }
  case emc270::MessageType::kLogInfo:
    HandleLogInfo(frame);
    return;
  case emc270::MessageType::kLogChunk:
    HandleLogChunk(frame);
    return;
  default:
    return;
  }
}

void DriverNode::SendHello() {
  emc270::HelloPayload hello;
  hello.session_id = session_id_;
  hello.options = emc270::kHelloOptionAutoResume;
  std::array<std::uint8_t, emc270::kMaxPayloadSize> payload{};
  std::uint16_t size = 0;
  if (emc270::EncodeHelloPayload(hello, payload.data(), payload.size(),
                                 &size)) {
    SendFrame(emc270::MessageType::kHello, payload.data(), size);
    last_hello_ms_ = SteadyNowMs();
  }
}

void DriverNode::SendCommand(std::uint32_t now_ms) {
  const bool fresh = command_received_ &&
                     now_ms - last_command_rx_ms_ <=
                         static_cast<std::uint32_t>(command_input_timeout_ms_);
  if (fresh && command_was_stale_ && arm_requested_) {
    neutral_until_ms_ = now_ms + kRecoveryNeutralMs;
  }
  command_was_stale_ = !fresh;

  emc270::CommandPayload command;
  const bool keep_alive_for_calibration = calibration_active_;
  const bool effective_arm =
      arm_requested_ && (fresh || keep_alive_for_calibration);
  if (effective_arm && now_ms >= neutral_until_ms_ &&
      !keep_alive_for_calibration) {
    command.x_q10000 = static_cast<std::int16_t>(
        std::lround(std::clamp(command_x_, -1.0F, 1.0F) * 10000.0F));
    command.y_q10000 = static_cast<std::int16_t>(
        std::lround(std::clamp(command_y_, -1.0F, 1.0F) * 10000.0F));
  }
  command.flags = effective_arm ? emc270::kCommandFlagArm : 0;

  std::array<std::uint8_t, emc270::kMaxPayloadSize> payload{};
  std::uint16_t size = 0;
  if (emc270::EncodeCommandPayload(command, payload.data(), payload.size(),
                                   &size)) {
    SendFrame(emc270::MessageType::kCommand, payload.data(), size);
    last_command_tx_ms_ = now_ms;
  }
}

bool DriverNode::SendFrame(emc270::MessageType type,
                           const std::uint8_t *payload,
                           std::uint16_t payload_size) {
  if (!serial_.is_open())
    return false;
  emc270::EncodedFrame frame;
  if (!emc270::EncodeFrame(type, ++tx_sequence_, SteadyNowMs(), payload,
                           payload_size, &frame)) {
    return false;
  }
  std::string error;
  if (!serial_.Write(frame.bytes.data(), frame.size, &error)) {
    HandleSerialFailure(error);
    return false;
  }
  return true;
}

void DriverNode::SendEmpty(emc270::MessageType type) {
  SendFrame(type, nullptr, 0);
}

void DriverNode::PublishStatus(const emc270::StatusPayload &status) {
  emc270_joystick_msgs::msg::JoystickStatus message;
  message.header.stamp = now();
  message.mode = static_cast<std::uint8_t>(status.mode);
  message.relay_energized = status.relay_energized != 0;
  message.config_valid = status.config_valid != 0;
  message.encoder_valid = status.encoder_valid != 0;
  message.rearm_required = status.rearm_required != 0 || host_rearm_required_;
  message.warnings = status.warnings;
  message.command_age_ms = status.command_age_ms;
  message.encoder_age_ms = status.encoder_age_ms;
  message.command_x = status.command_x_q10000 / 10000.0F;
  message.command_y = status.command_y_q10000 / 10000.0F;
  message.target_x_mv = status.target_x_mv;
  message.target_y_mv = status.target_y_mv;
  message.actual_x_mv = status.actual_x_mv;
  message.actual_y_mv = status.actual_y_mv;
  message.left_mm_s = status.left_mm_s;
  message.right_mm_s = status.right_mm_s;
  message.config_generation = status.config_generation;
  message.last_calibration_failure =
      static_cast<std::uint16_t>(status.last_calibration_failure);
  status_publisher_->publish(message);
}

void DriverNode::PublishEvent(const emc270::EventPayload &event) {
  emc270_joystick_msgs::msg::ControllerEvent message;
  message.header.stamp = now();
  message.code = static_cast<std::uint16_t>(event.code);
  message.severity = event.severity;
  message.mode = static_cast<std::uint8_t>(event.mode);
  message.description = EventName(event.code);
  message.detail_a = event.detail_a;
  message.detail_b = event.detail_b;
  message.target_x_mv = event.target_x_mv;
  message.target_y_mv = event.target_y_mv;
  message.actual_x_mv = event.actual_x_mv;
  message.actual_y_mv = event.actual_y_mv;
  event_publisher_->publish(message);
  if (event.severity >= 2) {
    RCLCPP_ERROR(get_logger(), "ESP32 %s (event=%u) detail=(%d,%d)",
                 message.description.c_str(), message.code, message.detail_a,
                 message.detail_b);
  } else if (event.severity == 1) {
    RCLCPP_WARN(get_logger(), "ESP32 %s (event=%u) detail=(%d,%d)",
                message.description.c_str(), message.code, message.detail_a,
                message.detail_b);
  } else {
    RCLCPP_INFO(get_logger(), "ESP32 %s (event=%u) detail=(%d,%d)",
                message.description.c_str(), message.code, message.detail_a,
                message.detail_b);
  }
}

void DriverNode::PublishHostEvent(std::uint16_t code, std::uint8_t severity,
                                  std::uint8_t mode,
                                  const std::string &description) {
  emc270_joystick_msgs::msg::ControllerEvent message;
  message.header.stamp = now();
  message.code = code;
  message.severity = severity;
  message.mode = mode;
  message.description = description;
  event_publisher_->publish(message);
}

void DriverNode::PublishCalibrationSample(
    const emc270::Frame &frame,
    const emc270::CalibrationSamplePayload &sample) {
  emc270_joystick_msgs::msg::CalibrationSample message;
  message.header.stamp = now();
  message.session_id = sample.session_id;
  message.sample_index = sample.sample_index;
  message.phase = sample.phase;
  message.axis = sample.axis;
  message.direction = sample.direction;
  message.verdict = sample.verdict;
  message.target_x_mv = sample.target_x_mv;
  message.target_y_mv = sample.target_y_mv;
  message.actual_x_mv = sample.actual_x_mv;
  message.actual_y_mv = sample.actual_y_mv;
  message.left_mm_s = sample.left_mm_s;
  message.right_mm_s = sample.right_mm_s;
  message.stationary_ms = sample.stationary_ms;
  message.failure = static_cast<std::uint16_t>(sample.failure);
  calibration_publisher_->publish(message);

  if (calibration_csv_.is_open()) {
    calibration_csv_ << frame.sender_time_ms << ',' << sample.session_id << ','
                     << sample.sample_index << ','
                     << static_cast<unsigned>(sample.phase) << ','
                     << static_cast<unsigned>(sample.axis) << ','
                     << static_cast<int>(sample.direction) << ','
                     << static_cast<unsigned>(sample.verdict) << ','
                     << sample.target_x_mv << ',' << sample.target_y_mv << ','
                     << sample.actual_x_mv << ',' << sample.actual_y_mv << ','
                     << sample.left_mm_s << ',' << sample.right_mm_s << ','
                     << sample.stationary_ms << ','
                     << static_cast<std::uint16_t>(sample.failure) << '\n';
    calibration_csv_.flush();
  }
}

void DriverNode::PublishDiagnostics(const emc270::StatusPayload *status) {
  diagnostic_msgs::msg::DiagnosticArray array;
  array.header.stamp = now();
  diagnostic_msgs::msg::DiagnosticStatus diagnostic;
  diagnostic.name = "EMC-270 joystick controller";
  diagnostic.hardware_id = device_;
  if (!serial_.is_open() || !handshake_) {
    diagnostic.level = diagnostic_msgs::msg::DiagnosticStatus::ERROR;
    diagnostic.message =
        last_serial_error_.empty() ? "not connected" : last_serial_error_;
  } else if (status != nullptr &&
             (status->warnings != 0 || status->config_valid == 0 ||
              status->rearm_required != 0 || host_rearm_required_)) {
    diagnostic.level = diagnostic_msgs::msg::DiagnosticStatus::WARN;
    diagnostic.message = status->config_valid == 0 ? "configuration not ready"
                         : status->rearm_required != 0 || host_rearm_required_
                             ? "explicit re-ARM required"
                             : "controller warning";
  } else {
    diagnostic.level = diagnostic_msgs::msg::DiagnosticStatus::OK;
    diagnostic.message = "connected";
  }
  diagnostic.values.push_back(KeyValue("device", device_));
  diagnostic.values.push_back(
      KeyValue("handshake", handshake_ ? "true" : "false"));
  diagnostic.values.push_back(
      KeyValue("host_crc_errors", std::to_string(observed_crc_errors_)));
  diagnostic.values.push_back(
      KeyValue("host_format_errors", std::to_string(observed_format_errors_)));
  if (status != nullptr) {
    diagnostic.values.push_back(KeyValue("mode", ModeName(status->mode)));
    diagnostic.values.push_back(
        KeyValue("warnings", std::to_string(status->warnings)));
    diagnostic.values.push_back(KeyValue(
        "rearm_required", status->rearm_required != 0 || host_rearm_required_
                              ? "true"
                              : "false"));
    diagnostic.values.push_back(
        KeyValue("target_mv", std::to_string(status->target_x_mv) + "," +
                                  std::to_string(status->target_y_mv)));
    diagnostic.values.push_back(
        KeyValue("actual_mv", std::to_string(status->actual_x_mv) + "," +
                                  std::to_string(status->actual_y_mv)));
  }
  array.status.push_back(std::move(diagnostic));
  diagnostics_publisher_->publish(array);
}

void DriverNode::HandleLogInfo(const emc270::Frame &frame) {
  emc270::ByteReader reader(frame.payload.data(), frame.payload_size);
  std::uint32_t session = 0;
  std::uint32_t size = 0;
  std::uint8_t available = 0;
  if (!reader.U32(&session) || !reader.U32(&size) || !reader.U8(&available) ||
      reader.remaining() != 0 || !recover_requested_) {
    return;
  }
  if (available == 0 || size == 0) {
    recover_requested_ = false;
    RCLCPP_WARN(get_logger(), "ESP32 has no recoverable calibration log");
    return;
  }
  std::error_code error;
  std::filesystem::create_directories(log_directory_, error);
  const auto path = LogPath(session, ".recovered.frames");
  recovered_log_.clear();
  recovered_log_.open(path, std::ios::binary | std::ios::trunc);
  if (!recovered_log_) {
    recover_requested_ = false;
    RCLCPP_ERROR(get_logger(), "Cannot open recovered log %s", path.c_str());
    return;
  }
  recovered_total_ = size;
  recovered_offset_ = 0;
  RequestLogChunk(0);
}

void DriverNode::HandleLogChunk(const emc270::Frame &frame) {
  if (!recover_requested_ || !recovered_log_.is_open())
    return;
  emc270::ByteReader reader(frame.payload.data(), frame.payload_size);
  std::uint32_t total = 0;
  std::uint32_t offset = 0;
  std::uint16_t size = 0;
  std::array<std::uint8_t, emc270::kMaxPayloadSize> data{};
  if (!reader.U32(&total) || !reader.U32(&offset) || !reader.U16(&size) ||
      size > reader.remaining() || size > data.size() ||
      !reader.Bytes(data.data(), size) || reader.remaining() != 0 ||
      total != recovered_total_ || offset != recovered_offset_) {
    RCLCPP_ERROR(get_logger(), "Invalid recovered log chunk");
    recover_requested_ = false;
    recovered_log_.close();
    return;
  }
  recovered_log_.write(reinterpret_cast<const char *>(data.data()), size);
  recovered_offset_ += size;
  if (size == 0 || recovered_offset_ >= recovered_total_) {
    recovered_log_.close();
    recover_requested_ = false;
    RCLCPP_INFO(get_logger(), "Recovered %u bytes of calibration log",
                recovered_offset_);
  } else {
    RequestLogChunk(recovered_offset_);
  }
}

void DriverNode::RequestLogChunk(std::uint32_t offset) {
  std::array<std::uint8_t, 4> payload{};
  emc270::ByteWriter writer(payload.data(), payload.size());
  writer.U32(offset);
  SendFrame(emc270::MessageType::kLogChunkRequest, payload.data(),
            static_cast<std::uint16_t>(writer.size()));
}

bool DriverNode::OpenCalibrationCsv(std::uint32_t session_id,
                                    std::string *error) {
  std::error_code file_error;
  std::filesystem::create_directories(log_directory_, file_error);
  if (file_error) {
    if (error != nullptr)
      *error = file_error.message();
    return false;
  }
  const auto path = LogPath(session_id, ".csv");
  calibration_csv_.open(path, std::ios::trunc);
  if (!calibration_csv_) {
    if (error != nullptr)
      *error = "cannot open " + path;
    return false;
  }
  calibration_csv_
      << "device_time_ms,session_id,sample_index,phase,axis,direction,verdict,"
         "target_x_mv,target_y_mv,actual_x_mv,actual_y_mv,left_mm_s,right_mm_s,"
         "stationary_ms,failure\n";
  return true;
}

void DriverNode::CloseCalibrationCsv() {
  if (calibration_csv_.is_open()) {
    calibration_csv_.flush();
    calibration_csv_.close();
  }
}

std::string DriverNode::LogPath(std::uint32_t session_id,
                                const std::string &extension) const {
  return (std::filesystem::path(log_directory_) /
          ("calibration_" + std::to_string(session_id) + extension))
      .string();
}

std::uint32_t DriverNode::SteadyNowMs() const {
  return static_cast<std::uint32_t>(
      std::chrono::duration_cast<std::chrono::milliseconds>(
          std::chrono::steady_clock::now() - steady_epoch_)
          .count());
}

void DriverNode::OnCommand(
    const emc270_joystick_msgs::msg::NormalizedCommand::SharedPtr message) {
  if (!std::isfinite(message->x) || !std::isfinite(message->y)) {
    RCLCPP_ERROR(get_logger(), "Rejected non-finite joystick command");
    command_received_ = false;
    arm_requested_ = false;
    host_rearm_required_ = true;
    command_x_ = 0.0F;
    command_y_ = 0.0F;
    SendEmpty(emc270::MessageType::kDisarm);
    return;
  }
  command_x_ = std::clamp(message->x, -1.0F, 1.0F);
  command_y_ = std::clamp(message->y, -1.0F, 1.0F);
  command_received_ = true;
  last_command_rx_ms_ = SteadyNowMs();
  if (!message->arm) {
    if (arm_requested_ || host_rearm_required_) {
      SendEmpty(emc270::MessageType::kDisarm);
    }
    arm_requested_ = false;
    host_rearm_required_ = false;
    return;
  }
  if (host_rearm_required_) {
    arm_requested_ = false;
    return;
  }
  if (!arm_requested_) {
    neutral_until_ms_ = last_command_rx_ms_ + kRecoveryNeutralMs;
    SendEmpty(emc270::MessageType::kArm);
  }
  arm_requested_ = true;
}

void DriverNode::OnArm(const std::shared_ptr<Trigger::Request>,
                       std::shared_ptr<Trigger::Response> response) {
  if (!handshake_) {
    response->success = false;
    response->message = "ESP32 is not connected";
    return;
  }
  host_rearm_required_ = false;
  arm_requested_ = true;
  neutral_until_ms_ = SteadyNowMs() + kRecoveryNeutralMs;
  SendEmpty(emc270::MessageType::kArm);
  response->success = true;
  response->message =
      "ARM queued; a fresh command stream is required and neutral is held "
      "for 600 ms";
}

void DriverNode::OnDisarm(const std::shared_ptr<Trigger::Request>,
                          std::shared_ptr<Trigger::Response> response) {
  arm_requested_ = false;
  host_rearm_required_ = false;
  response->success = SendFrame(emc270::MessageType::kDisarm, nullptr, 0);
  calibration_active_ = false;
  response->message =
      response->success ? "DISARM queued" : "ESP32 is not connected";
}

void DriverNode::OnStartCalibration(
    const std::shared_ptr<Trigger::Request>,
    std::shared_ptr<Trigger::Response> response) {
  if (!handshake_) {
    response->success = false;
    response->message = "ESP32 is not connected";
    return;
  }
  host_rearm_required_ = false;
  calibration_session_id_ = NewSessionId();
  std::string error;
  if (!OpenCalibrationCsv(calibration_session_id_, &error)) {
    response->success = false;
    response->message = error;
    return;
  }
  calibration_active_ = true;
  arm_requested_ = true;
  neutral_until_ms_ = SteadyNowMs() + kRecoveryNeutralMs;
  SendCommand(SteadyNowMs());
  std::array<std::uint8_t, 4> payload{};
  emc270::ByteWriter writer(payload.data(), payload.size());
  writer.U32(calibration_session_id_);
  response->success = SendFrame(emc270::MessageType::kStartCalibration,
                                payload.data(), writer.size());
  response->message = response->success
                          ? "calibration queued; samples are being logged"
                          : "failed to send calibration request";
  if (!response->success) {
    calibration_active_ = false;
    arm_requested_ = false;
    CloseCalibrationCsv();
  }
}

void DriverNode::OnAbortCalibration(
    const std::shared_ptr<Trigger::Request>,
    std::shared_ptr<Trigger::Response> response) {
  response->success =
      SendFrame(emc270::MessageType::kAbortCalibration, nullptr, 0);
  response->message =
      response->success ? "calibration abort queued" : "ESP32 is not connected";
  arm_requested_ = false;
  host_rearm_required_ = true;
}

void DriverNode::OnRecoverLog(const std::shared_ptr<Trigger::Request>,
                              std::shared_ptr<Trigger::Response> response) {
  if (!handshake_ || recover_requested_) {
    response->success = false;
    response->message = recover_requested_ ? "log recovery already active"
                                           : "ESP32 is not connected";
    return;
  }
  recover_requested_ = true;
  SendEmpty(emc270::MessageType::kLogInfoRequest);
  response->success = true;
  response->message = "log recovery requested";
}

void DriverNode::OnSetPreset(const std::shared_ptr<SetPreset::Request> request,
                             std::shared_ptr<SetPreset::Response> response) {
  if (!handshake_) {
    response->queued = false;
    response->reason = "ESP32 is not connected";
    return;
  }
  emc270::PresetPayload preset;
  preset.x_negative_mv = request->x_negative_mv;
  preset.x_positive_mv = request->x_positive_mv;
  preset.y_negative_mv = request->y_negative_mv;
  preset.y_positive_mv = request->y_positive_mv;
  preset.x_seed_mv = request->x_seed_mv;
  preset.y_seed_mv = request->y_seed_mv;
  preset.dac_full_scale_mv = request->dac_full_scale_mv;
  preset.watchdog_ms = request->watchdog_ms;
  preset.slew_full_scale_ms = request->slew_full_scale_ms;
  preset.motion_threshold_mm_s = request->motion_threshold_mm_s;
  preset.output_warn_tolerance_mv = request->output_warn_tolerance_mv;
  std::array<std::uint8_t, emc270::kMaxPayloadSize> payload{};
  std::uint16_t size = 0;
  response->queued =
      emc270::EncodePresetPayload(preset, payload.data(), payload.size(),
                                  &size) &&
      SendFrame(emc270::MessageType::kSetPreset, payload.data(), size);
  response->reason = response->queued ? "preset queued; verify ACK/event topic"
                                      : "failed to encode or send preset";
}

} // namespace emc270_joystick_driver
