#include "emc270/model.hpp"

#include <algorithm>

namespace emc270 {
namespace {

bool AxisPresetValid(const AxisProfile &axis, std::uint16_t full_scale_mv) {
  if (axis.negative_mv > full_scale_mv || axis.positive_mv > full_scale_mv ||
      axis.seed_mv > full_scale_mv) {
    return false;
  }
  const auto low = std::min(axis.negative_mv, axis.positive_mv);
  const auto high = std::max(axis.negative_mv, axis.positive_mv);
  return axis.negative_mv != axis.positive_mv && axis.seed_mv > low &&
         axis.seed_mv < high;
}

bool AxisNeutralValid(const AxisProfile &axis, std::uint16_t full_scale_mv) {
  const auto endpoint_low = std::min(axis.negative_mv, axis.positive_mv);
  const auto endpoint_high = std::max(axis.negative_mv, axis.positive_mv);
  return axis.neutral_high_mv <= full_scale_mv &&
         axis.neutral_low_mv >= endpoint_low &&
         axis.neutral_high_mv <= endpoint_high &&
         axis.neutral_low_mv <= axis.seed_mv &&
         axis.seed_mv <= axis.neutral_high_mv &&
         axis.neutral_low_mv <= axis.neutral_mid_mv &&
         axis.neutral_mid_mv <= axis.neutral_high_mv &&
         axis.neutral_low_mv < axis.neutral_high_mv &&
         axis.neutral_mid_mv ==
             static_cast<std::uint16_t>(
                 (static_cast<std::uint32_t>(axis.neutral_low_mv) +
                  axis.neutral_high_mv) /
                 2U);
}

} // namespace

ValidationResult ValidatePreset(const ControllerConfig &config) {
  if (config.schema_version != kConfigSchemaVersion)
    return {false, 1};
  if (config.dac_full_scale_mv < 4500 || config.dac_full_scale_mv > 5200) {
    return {false, 2};
  }
  if (!AxisPresetValid(config.x, config.dac_full_scale_mv))
    return {false, 3};
  if (!AxisPresetValid(config.y, config.dac_full_scale_mv))
    return {false, 4};
  if (config.watchdog_ms < 100 || config.watchdog_ms > 2000)
    return {false, 5};
  if (config.slew_full_scale_ms < 100 || config.slew_full_scale_ms > 10000) {
    return {false, 6};
  }
  if (config.motion_threshold_mm_s == 0 ||
      config.motion_threshold_mm_s > 1000) {
    return {false, 7};
  }
  if (config.output_warn_tolerance_mv < 4 ||
      config.output_warn_tolerance_mv > 500) {
    return {false, 8};
  }
  if (config.preset_valid == 0)
    return {false, 9};
  return {true, 0};
}

ValidationResult ValidateReadyConfig(const ControllerConfig &config) {
  const auto preset = ValidatePreset(config);
  if (!preset.valid)
    return preset;
  if (config.neutral_valid == 0)
    return {false, 10};
  if (!AxisNeutralValid(config.x, config.dac_full_scale_mv)) {
    return {false, 11};
  }
  if (!AxisNeutralValid(config.y, config.dac_full_scale_mv)) {
    return {false, 12};
  }
  return {true, 0};
}

} // namespace emc270
