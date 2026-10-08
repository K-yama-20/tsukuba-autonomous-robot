#include "emc270/protocol.hpp"

#include <algorithm>
#include <cstring>

namespace emc270 {
namespace {

void PutU16(std::uint8_t *output, std::uint16_t value) {
  output[0] = static_cast<std::uint8_t>(value & 0xFFU);
  output[1] = static_cast<std::uint8_t>((value >> 8U) & 0xFFU);
}

void PutU32(std::uint8_t *output, std::uint32_t value) {
  for (std::size_t index = 0; index < 4; ++index) {
    output[index] = static_cast<std::uint8_t>((value >> (index * 8U)) & 0xFFU);
  }
}

std::uint16_t GetU16(const std::uint8_t *input) {
  return static_cast<std::uint16_t>(input[0]) |
         (static_cast<std::uint16_t>(input[1]) << 8U);
}

std::uint32_t GetU32(const std::uint8_t *input) {
  std::uint32_t value = 0;
  for (std::size_t index = 0; index < 4; ++index) {
    value |= static_cast<std::uint32_t>(input[index]) << (index * 8U);
  }
  return value;
}

} // namespace

std::uint16_t Crc16Ccitt(const std::uint8_t *data, std::size_t size,
                         std::uint16_t initial) {
  std::uint16_t crc = initial;
  for (std::size_t index = 0; index < size; ++index) {
    crc ^= static_cast<std::uint16_t>(data[index]) << 8U;
    for (int bit = 0; bit < 8; ++bit) {
      crc = (crc & 0x8000U) != 0
                ? static_cast<std::uint16_t>((crc << 1U) ^ 0x1021U)
                : static_cast<std::uint16_t>(crc << 1U);
    }
  }
  return crc;
}

bool EncodeFrame(MessageType type, std::uint32_t sequence,
                 std::uint32_t sender_time_ms, const std::uint8_t *payload,
                 std::uint16_t payload_size, EncodedFrame *output) {
  if (output == nullptr || payload_size > kMaxPayloadSize ||
      (payload_size != 0 && payload == nullptr)) {
    return false;
  }
  auto &bytes = output->bytes;
  bytes[0] = kFrameSync0;
  bytes[1] = kFrameSync1;
  bytes[2] = kProtocolVersion;
  bytes[3] = static_cast<std::uint8_t>(type);
  PutU16(bytes.data() + 4, payload_size);
  PutU32(bytes.data() + 6, sequence);
  PutU32(bytes.data() + 10, sender_time_ms);
  if (payload_size != 0) {
    std::memcpy(bytes.data() + kFrameHeaderSize, payload, payload_size);
  }
  const auto crc = Crc16Ccitt(bytes.data() + 2, 12 + payload_size);
  PutU16(bytes.data() + kFrameHeaderSize + payload_size, crc);
  output->size = kFrameHeaderSize + payload_size + kFrameCrcSize;
  return true;
}

bool FrameParser::Feed(std::uint8_t byte, Frame *output) {
  if (used_ == 0) {
    if (byte == kFrameSync0)
      buffer_[used_++] = byte;
    return false;
  }
  if (used_ == 1) {
    if (byte == kFrameSync1) {
      buffer_[used_++] = byte;
    } else if (byte != kFrameSync0) {
      used_ = 0;
    }
    return false;
  }

  if (used_ >= buffer_.size()) {
    ++format_errors_;
    Reset();
    return false;
  }
  buffer_[used_++] = byte;

  if (used_ == 6) {
    const auto payload_size = GetU16(buffer_.data() + 4);
    if (payload_size > kMaxPayloadSize) {
      ++format_errors_;
      Reset();
      return false;
    }
    expected_ = kFrameHeaderSize + payload_size + kFrameCrcSize;
  }
  if (expected_ == 0 || used_ < expected_)
    return false;
  if (used_ != expected_ || buffer_[2] != kProtocolVersion) {
    ++format_errors_;
    Reset();
    return false;
  }

  const auto payload_size = GetU16(buffer_.data() + 4);
  const auto expected_crc =
      GetU16(buffer_.data() + kFrameHeaderSize + payload_size);
  const auto actual_crc = Crc16Ccitt(buffer_.data() + 2, 12 + payload_size);
  if (actual_crc != expected_crc) {
    ++crc_errors_;
    Reset();
    return false;
  }
  if (output == nullptr) {
    Reset();
    return false;
  }

  output->type = static_cast<MessageType>(buffer_[3]);
  output->sequence = GetU32(buffer_.data() + 6);
  output->sender_time_ms = GetU32(buffer_.data() + 10);
  output->payload_size = payload_size;
  if (payload_size != 0) {
    std::copy_n(buffer_.data() + kFrameHeaderSize, payload_size,
                output->payload.begin());
  }
  Reset();
  return true;
}

void FrameParser::Reset() {
  used_ = 0;
  expected_ = 0;
}

bool ByteWriter::U8(std::uint8_t value) {
  if (!ok_ || used_ >= capacity_)
    return ok_ = false;
  data_[used_++] = value;
  return true;
}

bool ByteWriter::U16(std::uint16_t value) {
  if (!ok_ || capacity_ - used_ < 2)
    return ok_ = false;
  PutU16(data_ + used_, value);
  used_ += 2;
  return true;
}

bool ByteWriter::U32(std::uint32_t value) {
  if (!ok_ || capacity_ - used_ < 4)
    return ok_ = false;
  PutU32(data_ + used_, value);
  used_ += 4;
  return true;
}

bool ByteWriter::Bytes(const std::uint8_t *value, std::size_t size) {
  if (!ok_ || value == nullptr || capacity_ - used_ < size)
    return ok_ = false;
  std::memcpy(data_ + used_, value, size);
  used_ += size;
  return true;
}

bool ByteReader::U8(std::uint8_t *value) {
  if (value == nullptr || used_ >= size_)
    return false;
  *value = data_[used_++];
  return true;
}

bool ByteReader::I8(std::int8_t *value) {
  std::uint8_t raw = 0;
  if (value == nullptr || !U8(&raw))
    return false;
  *value = static_cast<std::int8_t>(raw);
  return true;
}

bool ByteReader::U16(std::uint16_t *value) {
  if (value == nullptr || size_ - used_ < 2)
    return false;
  *value = GetU16(data_ + used_);
  used_ += 2;
  return true;
}

bool ByteReader::I16(std::int16_t *value) {
  std::uint16_t raw = 0;
  if (value == nullptr || !U16(&raw))
    return false;
  *value = static_cast<std::int16_t>(raw);
  return true;
}

bool ByteReader::U32(std::uint32_t *value) {
  if (value == nullptr || size_ - used_ < 4)
    return false;
  *value = GetU32(data_ + used_);
  used_ += 4;
  return true;
}

bool ByteReader::I32(std::int32_t *value) {
  std::uint32_t raw = 0;
  if (value == nullptr || !U32(&raw))
    return false;
  *value = static_cast<std::int32_t>(raw);
  return true;
}

bool ByteReader::Bytes(std::uint8_t *value, std::size_t size) {
  if (value == nullptr || size_ - used_ < size)
    return false;
  std::memcpy(value, data_ + used_, size);
  used_ += size;
  return true;
}

} // namespace emc270
