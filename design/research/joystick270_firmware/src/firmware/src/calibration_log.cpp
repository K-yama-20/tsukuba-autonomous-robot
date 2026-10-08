#include "calibration_log.hpp"

#include <LittleFS.h>

namespace emc270::firmware {

bool CalibrationLog::Begin() {
  // Never auto-format: a mount failure must preserve evidence and be reported.
  mounted_ = LittleFS.begin(false);
  return mounted_;
}

bool CalibrationLog::StartSession(std::uint32_t session_id) {
  if (!mounted_)
    return false;
  if (file_)
    file_.close();
  file_ = LittleFS.open(kPath, FILE_WRITE);
  if (!file_)
    return false;
  session_id_ = session_id;
  frames_since_flush_ = 0;
  return true;
}

bool CalibrationLog::Append(const EncodedFrame &frame) {
  if (!file_ || frame.size == 0)
    return false;
  if (file_.write(frame.bytes.data(), frame.size) != frame.size)
    return false;
  if (++frames_since_flush_ >= 50) {
    file_.flush();
    frames_since_flush_ = 0;
  }
  return true;
}

void CalibrationLog::EndSession() {
  if (file_) {
    file_.flush();
    file_.close();
  }
}

bool CalibrationLog::Clear() {
  if (!mounted_)
    return false;
  EndSession();
  session_id_ = 0;
  return !LittleFS.exists(kPath) || LittleFS.remove(kPath);
}

std::size_t CalibrationLog::Size() const {
  if (!mounted_ || !LittleFS.exists(kPath))
    return 0;
  File input = LittleFS.open(kPath, FILE_READ);
  if (!input)
    return 0;
  const auto size = input.size();
  input.close();
  return size;
}

std::size_t CalibrationLog::Read(std::size_t offset, std::uint8_t *output,
                                 std::size_t capacity) const {
  if (!mounted_ || output == nullptr || capacity == 0 ||
      !LittleFS.exists(kPath)) {
    return 0;
  }
  File input = LittleFS.open(kPath, FILE_READ);
  if (!input || !input.seek(offset))
    return 0;
  const auto read = input.read(output, capacity);
  input.close();
  return read;
}

} // namespace emc270::firmware
