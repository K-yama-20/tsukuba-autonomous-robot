#include "emc270/control.hpp"

#include <algorithm>
#include <cstdint>

namespace emc270 {

std::uint16_t MapNormalizedToMillivolts(std::int16_t normalized,
                                        const AxisProfile &axis) {
  const auto clamped = std::clamp<std::int32_t>(
      normalized, -kNormalizedFullScale, kNormalizedFullScale);
  const auto center = static_cast<std::int32_t>(axis.neutral_mid_mv);
  const auto endpoint = static_cast<std::int32_t>(
      clamped >= 0 ? axis.positive_mv : axis.negative_mv);
  const auto magnitude =
      static_cast<std::int32_t>(clamped >= 0 ? clamped : -clamped);
  const auto delta = endpoint - center;
  const auto rounded =
      delta >= 0 ? kNormalizedFullScale / 2 : -kNormalizedFullScale / 2;
  const auto value =
      center + (delta * magnitude + rounded) / kNormalizedFullScale;
  return static_cast<std::uint16_t>(std::max<std::int32_t>(0, value));
}

void SlewLimiter::Reset(std::uint16_t value_mv, std::uint32_t now_ms) {
  value_mv_ = value_mv;
  last_ms_ = now_ms;
  fractional_ = 0;
  initialized_ = true;
}

std::uint16_t SlewLimiter::Step(std::uint16_t target_mv,
                                std::uint16_t full_scale_mv,
                                std::uint16_t full_scale_time_ms,
                                std::uint32_t now_ms) {
  if (!initialized_) {
    Reset(target_mv, now_ms);
    return value_mv_;
  }
  const std::uint32_t elapsed = now_ms - last_ms_;
  last_ms_ = now_ms;
  if (full_scale_time_ms == 0 || elapsed == 0)
    return value_mv_;

  const std::uint64_t numerator =
      static_cast<std::uint64_t>(full_scale_mv) * elapsed + fractional_;
  std::uint32_t allowed =
      static_cast<std::uint32_t>(numerator / full_scale_time_ms);
  fractional_ = static_cast<std::uint32_t>(numerator % full_scale_time_ms);
  if (allowed == 0 && target_mv != value_mv_)
    return value_mv_;

  if (target_mv > value_mv_) {
    value_mv_ = static_cast<std::uint16_t>(
        std::min<std::uint32_t>(target_mv, value_mv_ + allowed));
  } else {
    value_mv_ = static_cast<std::uint16_t>(
        target_mv < value_mv_ && value_mv_ - target_mv > allowed
            ? value_mv_ - allowed
            : target_mv);
  }
  return value_mv_;
}

bool CommandWatchdog::Expired(std::uint32_t now_ms,
                              std::uint16_t timeout_ms) const {
  return !observed_ ||
         static_cast<std::uint32_t>(now_ms - last_observed_ms_) > timeout_ms;
}

std::uint32_t CommandWatchdog::Age(std::uint32_t now_ms) const {
  return observed_ ? static_cast<std::uint32_t>(now_ms - last_observed_ms_)
                   : UINT32_MAX;
}

} // namespace emc270
