#pragma once

#include <cstdint>

namespace settings {
// Confirmed: increasing R1 voltage turns right; increasing R2 moves forward.
constexpr int kRightPolarity = 1;
constexpr int kForwardPolarity = 1;

// Provisional calibration inherited from the working serial-control project.
constexpr uint16_t kXFullScaleMv = 4700;
constexpr uint16_t kYFullScaleMv = 4700;
static_assert(kRightPolarity == 1 || kRightPolarity == -1, "Invalid steering polarity");
static_assert(kForwardPolarity == 1 || kForwardPolarity == -1, "Invalid drive polarity");
static_assert(kXFullScaleMv >= 4700 && kYFullScaleMv >= 4700, "Full scale below requested range");
}  // namespace settings
