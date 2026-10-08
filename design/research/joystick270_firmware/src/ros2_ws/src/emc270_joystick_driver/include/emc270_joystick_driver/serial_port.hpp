#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

namespace emc270_joystick_driver {

class SerialPort {
public:
  SerialPort() = default;
  ~SerialPort();
  SerialPort(const SerialPort &) = delete;
  SerialPort &operator=(const SerialPort &) = delete;

  bool Open(const std::string &device, int baud, std::string *error);
  void Close();
  bool is_open() const { return fd_ >= 0; }
  long Read(std::uint8_t *output, std::size_t capacity, std::string *error);
  bool Write(const std::uint8_t *data, std::size_t size, std::string *error);

private:
  int fd_{-1};
};

} // namespace emc270_joystick_driver
