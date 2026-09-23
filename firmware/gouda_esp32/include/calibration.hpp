#pragma once
#include "core.hpp"
#include "legacy_control.hpp"
#include "legacy_settings.hpp"
namespace calibration {
// Requested 2500 mV from the user's DualSense implementation; NOT a voltage measurement.
constexpr bool validated=false;
constexpr const char* revision="UNCALIBRATED-dualsense-reference";
inline std::array<gouda::Output,5> table(){
    const gouda::Output stop{motion::dacCode(motion::kNeutralMv,settings::kXFullScaleMv),
                            motion::dacCode(motion::kNeutralMv,settings::kYFullScaleMv)};
    return {{stop,stop,stop,stop,stop}};
}
}
