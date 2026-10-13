#pragma once

#include <cstdint>

#include "emc270/model.hpp"

namespace emc270 {

std::uint16_t MapNormalizedToMillivolts(std::int16_t normalized,
                                        const AxisProfile &axis);

class SlewLimiter {
public:
  void Reset(std::uint16_t value_mv, std::uint32_t now_ms);
  std::uint16_t Step(std::uint16_t target_mv, std::uint16_t full_scale_mv,
                     std::uint16_t full_scale_time_ms, std::uint32_t now_ms);
  std::uint16_t value_mv() const { return value_mv_; }

private:
  std::uint16_t value_mv_{kDefaultCenterSeedMv};
  std::uint32_t last_ms_{0};
  std::uint32_t fractional_{0};
  bool initialized_{false};
};

class CommandWatchdog {
public:
  void Observe(std::uint32_t now_ms) {
    last_observed_ms_ = now_ms;
    observed_ = true;
  }
  void Reset() {
    last_observed_ms_ = 0;
    observed_ = false;
  }
  bool Expired(std::uint32_t now_ms, std::uint16_t timeout_ms) const;
  std::uint32_t Age(std::uint32_t now_ms) const;

private:
  std::uint32_t last_observed_ms_{0};
  bool observed_{false};
};

} // namespace emc270
