#include "config_store.hpp"

#include <algorithm>

#include "emc270/messages.hpp"
#include "emc270/protocol.hpp"

namespace emc270::firmware {
namespace {

constexpr std::uint32_t kRecordMagic = 0x31474643U; // "CFG1" little-endian.

} // namespace

bool ConfigStore::Begin() {
  open_ = preferences_.begin("emc270", false);
  return open_;
}

bool ConfigStore::Load(ControllerConfig *config) {
  if (!open_ || config == nullptr)
    return false;
  ControllerConfig a;
  ControllerConfig b;
  const bool valid_a = ReadSlot("cfg_a", &a);
  const bool valid_b = ReadSlot("cfg_b", &b);
  if (!valid_a && !valid_b)
    return false;
  *config = valid_a && (!valid_b || a.generation >= b.generation) ? a : b;
  return true;
}

bool ConfigStore::Save(ControllerConfig *config) {
  if (!open_ || config == nullptr)
    return false;
  ControllerConfig next = *config;
  ++next.generation;
  std::array<std::uint8_t, kRecordCapacity> record{};
  std::size_t size = 0;
  if (!EncodeRecord(next, &record, &size))
    return false;
  const char *key = (next.generation & 1U) != 0 ? "cfg_a" : "cfg_b";
  if (preferences_.putBytes(key, record.data(), size) != size)
    return false;
  ControllerConfig verified;
  if (!ReadSlot(key, &verified) || verified.generation != next.generation) {
    return false;
  }
  *config = next;
  return true;
}

bool ConfigStore::DecodeRecord(const std::uint8_t *data, std::size_t size,
                               ControllerConfig *config) const {
  if (data == nullptr || config == nullptr || size < 10)
    return false;
  ByteReader reader(data, size);
  std::uint32_t magic = 0;
  std::uint16_t payload_size = 0;
  if (!reader.U32(&magic) || !reader.U16(&payload_size) ||
      magic != kRecordMagic || payload_size > kMaxPayloadSize ||
      size != 6U + payload_size + 2U) {
    return false;
  }
  Frame frame;
  frame.payload_size = payload_size;
  if (!reader.Bytes(frame.payload.data(), payload_size))
    return false;
  std::uint16_t stored_crc = 0;
  if (!reader.U16(&stored_crc) || reader.remaining() != 0)
    return false;
  if (Crc16Ccitt(data, 6U + payload_size) != stored_crc)
    return false;
  return DecodeControllerConfigPayload(frame, config) &&
         ValidatePreset(*config).valid;
}

bool ConfigStore::EncodeRecord(const ControllerConfig &config,
                               std::array<std::uint8_t, kRecordCapacity> *data,
                               std::size_t *size) const {
  if (data == nullptr || size == nullptr)
    return false;
  std::array<std::uint8_t, kMaxPayloadSize> payload{};
  std::uint16_t payload_size = 0;
  if (!EncodeControllerConfigPayload(config, payload.data(), payload.size(),
                                     &payload_size)) {
    return false;
  }
  ByteWriter writer(data->data(), data->size());
  writer.U32(kRecordMagic);
  writer.U16(payload_size);
  writer.Bytes(payload.data(), payload_size);
  if (!writer.ok())
    return false;
  const auto crc = Crc16Ccitt(data->data(), writer.size());
  writer.U16(crc);
  if (!writer.ok())
    return false;
  *size = writer.size();
  return true;
}

bool ConfigStore::ReadSlot(const char *key, ControllerConfig *config) {
  const auto size = preferences_.getBytesLength(key);
  if (size == 0 || size > kRecordCapacity)
    return false;
  std::array<std::uint8_t, kRecordCapacity> record{};
  if (preferences_.getBytes(key, record.data(), size) != size)
    return false;
  return DecodeRecord(record.data(), size, config);
}

} // namespace emc270::firmware
