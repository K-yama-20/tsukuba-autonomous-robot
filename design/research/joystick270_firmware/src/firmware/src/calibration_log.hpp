#pragma once

#include <Arduino.h>
#include <FS.h>

#include <cstddef>
#include <cstdint>

#include "emc270/protocol.hpp"

namespace emc270::firmware {

class CalibrationLog {
public:
  bool Begin();
  bool StartSession(std::uint32_t session_id);
  bool Append(const EncodedFrame &frame);
  void EndSession();
  bool Clear();
  std::size_t Size() const;
  std::uint32_t session_id() const { return session_id_; }
  std::size_t Read(std::size_t offset, std::uint8_t *output,
                   std::size_t capacity) const;
  bool available() const { return mounted_; }

private:
  static constexpr const char *kPath = "/calibration.frames";
  bool mounted_{false};
  std::uint32_t session_id_{0};
  File file_{};
  std::uint32_t frames_since_flush_{0};
};

} // namespace emc270::firmware
