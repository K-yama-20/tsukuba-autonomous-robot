#include <Arduino.h>

#include <array>
#include <cstdint>

#include "emc270/messages.hpp"
#include "emc270/protocol.hpp"

namespace {

constexpr int kControllerRxPin = 16;
constexpr int kControllerTxPin = 17;
constexpr std::uint32_t kControllerBaud = 230400;
constexpr std::uint32_t kPeriodMs = 20;

HardwareSerial controller_uart(2);
std::int32_t left_mm_s = 0;
std::int32_t right_mm_s = 0;
std::uint32_t sequence = 0;
std::uint32_t last_tx_ms = 0;
String line;

void ReadUsbCommand() {
  while (Serial.available() > 0) {
    const char value = static_cast<char>(Serial.read());
    if (value == '\n' || value == '\r') {
      if (!line.isEmpty()) {
        long left = 0;
        long right = 0;
        if (sscanf(line.c_str(), "%ld %ld", &left, &right) == 2) {
          left_mm_s = static_cast<std::int32_t>(left);
          right_mm_s = static_cast<std::int32_t>(right);
          Serial.printf("speed left=%ld right=%ld mm/s\n", left, right);
        } else {
          Serial.println("enter: <left_mm_s> <right_mm_s>");
        }
      }
      line.clear();
    } else if (line.length() < 64) {
      line += value;
    }
  }
}

void SendSpeed(std::uint32_t now_ms) {
  emc270::EncoderSpeedPayload speed;
  speed.left_mm_s = left_mm_s;
  speed.right_mm_s = right_mm_s;
  speed.status = emc270::kEncoderStatusValid;
  std::array<std::uint8_t, emc270::kMaxPayloadSize> payload{};
  std::uint16_t payload_size = 0;
  if (!emc270::EncodeEncoderSpeedPayload(speed, payload.data(), payload.size(),
                                         &payload_size)) {
    return;
  }
  emc270::EncodedFrame frame;
  if (emc270::EncodeFrame(emc270::MessageType::kEncoderSpeed, ++sequence,
                          now_ms, payload.data(), payload_size, &frame)) {
    controller_uart.write(frame.bytes.data(), frame.size);
  }
}

} // namespace

void setup() {
  Serial.begin(115200);
  controller_uart.begin(kControllerBaud, SERIAL_8N1, kControllerRxPin,
                        kControllerTxPin);
  Serial.println("EMC-270 encoder UART mock");
  Serial.println("enter: <left_mm_s> <right_mm_s>");
}

void loop() {
  ReadUsbCommand();
  const auto now_ms = millis();
  if (now_ms - last_tx_ms >= kPeriodMs) {
    last_tx_ms = now_ms;
    SendSpeed(now_ms);
  }
  delay(1);
}
