#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

namespace emc270 {

constexpr std::uint8_t kFrameSync0 = 0xA5;
constexpr std::uint8_t kFrameSync1 = 0x5A;
constexpr std::uint8_t kProtocolVersion = 1;
constexpr std::size_t kFrameHeaderSize = 14;
constexpr std::size_t kFrameCrcSize = 2;
constexpr std::size_t kMaxPayloadSize = 192;
constexpr std::size_t kMaxFrameSize =
    kFrameHeaderSize + kMaxPayloadSize + kFrameCrcSize;

enum class MessageType : std::uint8_t {
  kHello = 0x01,
  kCommand = 0x02,
  kSetPreset = 0x03,
  kArm = 0x04,
  kDisarm = 0x05,
  kStartCalibration = 0x06,
  kAbortCalibration = 0x07,
  kGetStatus = 0x08,
  kGetConfig = 0x09,
  kLogInfoRequest = 0x0A,
  kLogChunkRequest = 0x0B,
  kClearLog = 0x0C,
  kEncoderSpeed = 0x40,
  kHelloReply = 0x80,
  kStatus = 0x81,
  kEvent = 0x82,
  kCalibrationSample = 0x83,
  kConfig = 0x84,
  kAck = 0x85,
  kLogInfo = 0x86,
  kLogChunk = 0x87,
};

struct Frame {
  MessageType type{MessageType::kHello};
  std::uint32_t sequence{0};
  std::uint32_t sender_time_ms{0};
  std::uint16_t payload_size{0};
  std::array<std::uint8_t, kMaxPayloadSize> payload{};
};

struct EncodedFrame {
  std::size_t size{0};
  std::array<std::uint8_t, kMaxFrameSize> bytes{};
};

std::uint16_t Crc16Ccitt(const std::uint8_t *data, std::size_t size,
                         std::uint16_t initial = 0xFFFF);

bool EncodeFrame(MessageType type, std::uint32_t sequence,
                 std::uint32_t sender_time_ms, const std::uint8_t *payload,
                 std::uint16_t payload_size, EncodedFrame *output);

class FrameParser {
public:
  bool Feed(std::uint8_t byte, Frame *output);
  void Reset();
  std::uint32_t crc_errors() const { return crc_errors_; }
  std::uint32_t format_errors() const { return format_errors_; }

private:
  std::array<std::uint8_t, kMaxFrameSize> buffer_{};
  std::size_t used_{0};
  std::size_t expected_{0};
  std::uint32_t crc_errors_{0};
  std::uint32_t format_errors_{0};
};

class ByteWriter {
public:
  ByteWriter(std::uint8_t *data, std::size_t capacity)
      : data_(data), capacity_(capacity) {}

  bool U8(std::uint8_t value);
  bool I8(std::int8_t value) { return U8(static_cast<std::uint8_t>(value)); }
  bool U16(std::uint16_t value);
  bool I16(std::int16_t value) {
    return U16(static_cast<std::uint16_t>(value));
  }
  bool U32(std::uint32_t value);
  bool I32(std::int32_t value) {
    return U32(static_cast<std::uint32_t>(value));
  }
  bool Bytes(const std::uint8_t *value, std::size_t size);
  std::size_t size() const { return used_; }
  bool ok() const { return ok_; }

private:
  std::uint8_t *data_;
  std::size_t capacity_;
  std::size_t used_{0};
  bool ok_{true};
};

class ByteReader {
public:
  ByteReader(const std::uint8_t *data, std::size_t size)
      : data_(data), size_(size) {}

  bool U8(std::uint8_t *value);
  bool I8(std::int8_t *value);
  bool U16(std::uint16_t *value);
  bool I16(std::int16_t *value);
  bool U32(std::uint32_t *value);
  bool I32(std::int32_t *value);
  bool Bytes(std::uint8_t *value, std::size_t size);
  std::size_t remaining() const { return size_ - used_; }

private:
  const std::uint8_t *data_;
  std::size_t size_;
  std::size_t used_{0};
};

} // namespace emc270
