#include "emc270_joystick_driver/serial_port.hpp"

#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <termios.h>
#include <unistd.h>

#include <chrono>
#include <thread>

namespace emc270_joystick_driver {
namespace {

bool BaudConstant(int baud, speed_t *speed) {
  if (speed == nullptr)
    return false;
  switch (baud) {
  case 115200:
    *speed = B115200;
    return true;
#ifdef B230400
  case 230400:
    *speed = B230400;
    return true;
#endif
#ifdef B460800
  case 460800:
    *speed = B460800;
    return true;
#endif
#ifdef B921600
  case 921600:
    *speed = B921600;
    return true;
#endif
  default:
    return false;
  }
}

std::string ErrnoMessage(const std::string &operation) {
  return operation + ": " + std::strerror(errno);
}

} // namespace

SerialPort::~SerialPort() { Close(); }

bool SerialPort::Open(const std::string &device, int baud, std::string *error) {
  Close();
  speed_t speed = 0;
  if (!BaudConstant(baud, &speed)) {
    if (error != nullptr)
      *error = "unsupported baud rate";
    return false;
  }
  fd_ = open(device.c_str(), O_RDWR | O_NOCTTY | O_NONBLOCK | O_CLOEXEC);
  if (fd_ < 0) {
    if (error != nullptr)
      *error = ErrnoMessage("open " + device);
    return false;
  }

  termios settings{};
  if (tcgetattr(fd_, &settings) != 0) {
    if (error != nullptr)
      *error = ErrnoMessage("tcgetattr");
    Close();
    return false;
  }
  cfmakeraw(&settings);
  settings.c_cflag |= CLOCAL | CREAD;
  settings.c_cflag &= ~CSTOPB;
  settings.c_cflag &= ~CRTSCTS;
  settings.c_cflag &= ~PARENB;
  settings.c_cflag = (settings.c_cflag & ~CSIZE) | CS8;
  settings.c_cc[VMIN] = 0;
  settings.c_cc[VTIME] = 0;
  cfsetispeed(&settings, speed);
  cfsetospeed(&settings, speed);
  if (tcsetattr(fd_, TCSANOW, &settings) != 0) {
    if (error != nullptr)
      *error = ErrnoMessage("tcsetattr");
    Close();
    return false;
  }
  tcflush(fd_, TCIOFLUSH);
  return true;
}

void SerialPort::Close() {
  if (fd_ >= 0)
    close(fd_);
  fd_ = -1;
}

long SerialPort::Read(std::uint8_t *output, std::size_t capacity,
                      std::string *error) {
  if (fd_ < 0 || output == nullptr || capacity == 0)
    return 0;
  const auto count = read(fd_, output, capacity);
  if (count >= 0)
    return count;
  if (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR)
    return 0;
  if (error != nullptr)
    *error = ErrnoMessage("read");
  Close();
  return -1;
}

bool SerialPort::Write(const std::uint8_t *data, std::size_t size,
                       std::string *error) {
  if (fd_ < 0 || (data == nullptr && size != 0))
    return false;
  const auto deadline =
      std::chrono::steady_clock::now() + std::chrono::milliseconds(50);
  std::size_t written = 0;
  while (written < size) {
    const auto count = write(fd_, data + written, size - written);
    if (count > 0) {
      written += static_cast<std::size_t>(count);
      continue;
    }
    if (count < 0 &&
        (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR)) {
      if (std::chrono::steady_clock::now() >= deadline) {
        if (error != nullptr)
          *error = "serial write timed out after 50 ms";
        Close();
        return false;
      }
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
      continue;
    }
    if (error != nullptr)
      *error = ErrnoMessage("write");
    Close();
    return false;
  }
  return true;
}

} // namespace emc270_joystick_driver
