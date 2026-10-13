#pragma once

#include <Preferences.h>

#include <array>
#include <cstddef>
#include <cstdint>

#include "emc270/model.hpp"

namespace emc270::firmware {

class ConfigStore {
public:
  bool Begin();
  bool Load(ControllerConfig *config);
  bool Save(ControllerConfig *config);

private:
  static constexpr std::size_t kRecordCapacity = 96;
  bool DecodeRecord(const std::uint8_t *data, std::size_t size,
                    ControllerConfig *config) const;
  bool EncodeRecord(const ControllerConfig &config,
                    std::array<std::uint8_t, kRecordCapacity> *data,
                    std::size_t *size) const;
  bool ReadSlot(const char *key, ControllerConfig *config);

  Preferences preferences_{};
  bool open_{false};
};

} // namespace emc270::firmware
