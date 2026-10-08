#pragma once

#include <diagnostic_msgs/msg/diagnostic_array.hpp>
#include <emc270_joystick_msgs/msg/calibration_sample.hpp>
#include <emc270_joystick_msgs/msg/controller_event.hpp>
#include <emc270_joystick_msgs/msg/joystick_status.hpp>
#include <emc270_joystick_msgs/msg/normalized_command.hpp>
#include <emc270_joystick_msgs/srv/set_preset.hpp>
#include <rclcpp/rclcpp.hpp>
#include <std_srvs/srv/trigger.hpp>

#include <chrono>
#include <cstdint>
#include <fstream>
#include <memory>
#include <string>

#include "emc270/messages.hpp"
#include "emc270/protocol.hpp"
#include "emc270_joystick_driver/serial_port.hpp"

namespace emc270_joystick_driver {

class DriverNode : public rclcpp::Node {
public:
  DriverNode();
  ~DriverNode() override;

private:
  using Trigger = std_srvs::srv::Trigger;
  using SetPreset = emc270_joystick_msgs::srv::SetPreset;

  void Tick();
  void TryOpen(std::uint32_t now_ms);
  void ReadFrames();
  void HandleSerialFailure(const std::string &error);
  void HandleFrame(const emc270::Frame &frame);
  void SendHello();
  void SendCommand(std::uint32_t now_ms);
  bool SendFrame(emc270::MessageType type, const std::uint8_t *payload,
                 std::uint16_t payload_size);
  void SendEmpty(emc270::MessageType type);
  void PublishStatus(const emc270::StatusPayload &status);
  void PublishEvent(const emc270::EventPayload &event);
  void PublishHostEvent(std::uint16_t code, std::uint8_t severity,
                        std::uint8_t mode, const std::string &description);
  void PublishCalibrationSample(const emc270::Frame &frame,
                                const emc270::CalibrationSamplePayload &sample);
  void PublishDiagnostics(const emc270::StatusPayload *status = nullptr);
  void HandleLogInfo(const emc270::Frame &frame);
  void HandleLogChunk(const emc270::Frame &frame);
  void RequestLogChunk(std::uint32_t offset);
  bool OpenCalibrationCsv(std::uint32_t session_id, std::string *error);
  void CloseCalibrationCsv();
  std::string LogPath(std::uint32_t session_id,
                      const std::string &extension) const;
  std::uint32_t SteadyNowMs() const;

  void OnCommand(
      const emc270_joystick_msgs::msg::NormalizedCommand::SharedPtr message);
  void OnArm(const std::shared_ptr<Trigger::Request> request,
             std::shared_ptr<Trigger::Response> response);
  void OnDisarm(const std::shared_ptr<Trigger::Request> request,
                std::shared_ptr<Trigger::Response> response);
  void OnStartCalibration(const std::shared_ptr<Trigger::Request> request,
                          std::shared_ptr<Trigger::Response> response);
  void OnAbortCalibration(const std::shared_ptr<Trigger::Request> request,
                          std::shared_ptr<Trigger::Response> response);
  void OnRecoverLog(const std::shared_ptr<Trigger::Request> request,
                    std::shared_ptr<Trigger::Response> response);
  void OnSetPreset(const std::shared_ptr<SetPreset::Request> request,
                   std::shared_ptr<SetPreset::Response> response);

  SerialPort serial_{};
  emc270::FrameParser parser_{};
  std::string device_;
  std::string log_directory_;
  int baud_{460800};
  int command_input_timeout_ms_{300};
  std::chrono::steady_clock::time_point steady_epoch_;
  std::uint32_t session_id_{0};
  std::uint32_t tx_sequence_{0};
  std::uint32_t last_open_attempt_ms_{0};
  std::uint32_t last_hello_ms_{0};
  std::uint32_t last_command_tx_ms_{0};
  std::uint32_t last_command_rx_ms_{0};
  std::uint32_t neutral_until_ms_{0};
  std::uint32_t calibration_session_id_{0};
  bool handshake_{false};
  bool arm_requested_{false};
  bool command_received_{false};
  bool command_was_stale_{true};
  bool calibration_active_{false};
  bool host_rearm_required_{false};
  bool recover_requested_{false};
  float command_x_{0.0F};
  float command_y_{0.0F};
  std::ofstream calibration_csv_{};
  std::ofstream recovered_log_{};
  std::uint32_t recovered_total_{0};
  std::uint32_t recovered_offset_{0};
  std::uint32_t observed_crc_errors_{0};
  std::uint32_t observed_format_errors_{0};
  std::string last_serial_error_;

  rclcpp::TimerBase::SharedPtr timer_;
  rclcpp::Subscription<emc270_joystick_msgs::msg::NormalizedCommand>::SharedPtr
      command_subscription_;
  rclcpp::Publisher<emc270_joystick_msgs::msg::JoystickStatus>::SharedPtr
      status_publisher_;
  rclcpp::Publisher<emc270_joystick_msgs::msg::ControllerEvent>::SharedPtr
      event_publisher_;
  rclcpp::Publisher<emc270_joystick_msgs::msg::CalibrationSample>::SharedPtr
      calibration_publisher_;
  rclcpp::Publisher<diagnostic_msgs::msg::DiagnosticArray>::SharedPtr
      diagnostics_publisher_;
  rclcpp::Service<Trigger>::SharedPtr arm_service_;
  rclcpp::Service<Trigger>::SharedPtr disarm_service_;
  rclcpp::Service<Trigger>::SharedPtr start_calibration_service_;
  rclcpp::Service<Trigger>::SharedPtr abort_calibration_service_;
  rclcpp::Service<Trigger>::SharedPtr recover_log_service_;
  rclcpp::Service<SetPreset>::SharedPtr set_preset_service_;
};

} // namespace emc270_joystick_driver
