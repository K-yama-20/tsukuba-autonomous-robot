#pragma once

#include <cmath>
#include <cstdint>

namespace motion {
constexpr uint16_t kNeutralMv = 2500;
constexpr uint16_t kMinimumMv = 230;
constexpr uint16_t kMaximumMv = 4700;
constexpr float kDeadzone = 0.08f;
constexpr uint32_t kReportTimeoutMs = 250;

struct Voltage {
    uint16_t x;
    uint16_t y;
};

// Positive x = right; positive y = forward. Polarity is applied after this step.
struct Vector {
    float x;
    float y;
};

inline Vector stick(int32_t rawX, int32_t rawY) {
    float x = fmaxf(-1.0f, fminf(1.0f, rawX / 512.0f));
    float y = fmaxf(-1.0f, fminf(1.0f, -rawY / 512.0f));
    const float radius = sqrtf(x * x + y * y);
    if (radius <= kDeadzone) return {0.0f, 0.0f};
    const float magnitude = (fminf(radius, 1.0f) - kDeadzone) / (1.0f - kDeadzone);
    return {x * magnitude / radius, y * magnitude / radius};
}

inline bool insideCircle(Voltage voltage) {
    // Doubled coordinates avoid floating-point or half-mV boundary ambiguity.
    const int64_t dx = 2 * int64_t(voltage.x) - (kMinimumMv + kMaximumMv);
    const int64_t dy = 2 * int64_t(voltage.y) - (kMinimumMv + kMaximumMv);
    const int64_t diameter = kMaximumMv - kMinimumMv;
    return dx * dx + dy * dy <= diameter * diameter;
}

// The voltage circle is centered at 2465 mV, but stop remains exactly 2500 mV.
// Cast a ray from stop to the circle and scale along it by stick magnitude.
inline Voltage map(Vector value, int rightPolarity, int forwardPolarity) {
    float x = value.x * rightPolarity;
    float y = value.y * forwardPolarity;
    const float magnitude = sqrtf(x * x + y * y);
    if (magnitude == 0) return {kNeutralMv, kNeutralMv};
    x /= magnitude;
    y /= magnitude;
    constexpr float center = (kMinimumMv + kMaximumMv) / 2.0f;
    constexpr float radius = (kMaximumMv - kMinimumMv) / 2.0f;
    constexpr float offset = kNeutralMv - center;
    const float dot = offset * (x + y);
    const float distance = -dot + sqrtf(dot * dot + radius * radius - 2 * offset * offset);
    const float travel = fminf(magnitude, 1.0f) * distance;
    Voltage out{uint16_t(lroundf(kNeutralMv + x * travel)),
                uint16_t(lroundf(kNeutralMv + y * travel))};
    // Rounding to integer mV can cross the boundary. Move inward by a mV
    // until the exact integer circle condition holds (normally zero or one step).
    while (!insideCircle(out)) {
        const int dx = 2 * int(out.x) - (kMinimumMv + kMaximumMv);
        const int dy = 2 * int(out.y) - (kMinimumMv + kMaximumMv);
        if (std::abs(dx) >= std::abs(dy)) out.x += dx > 0 ? -1 : 1;
        else out.y += dy > 0 ? -1 : 1;
    }
    return out;
}

inline uint16_t dacCode(uint16_t mv, uint16_t fullScaleMv) {
    const uint32_t code = (uint32_t(mv) * 4095 + fullScaleMv / 2) / fullScaleMv;
    return uint16_t(code > 4095 ? 4095 : code);
}

class Session {
public:
    void reset() {
        centered_ = false;
        haveReport_ = false;
        target_ = {0.0f, 0.0f};
    }

    void report(int32_t x, int32_t y, uint32_t now) {
        // A late packet must not revive the old command before recentering.
        if (haveReport_ && uint32_t(now - lastReport_) >= kReportTimeoutMs)
            centered_ = false;
        haveReport_ = true;
        lastReport_ = now;
        const Vector value = stick(x, y);
        if (!centered_ && value.x == 0 && value.y == 0) centered_ = true;
        target_ = centered_ ? value : Vector{0.0f, 0.0f};
    }

    Vector target(uint32_t now) {
        if (!haveReport_ || uint32_t(now - lastReport_) >= kReportTimeoutMs) {
            centered_ = false;
            target_ = {0.0f, 0.0f};
        }
        return target_;
    }

private:
    bool centered_ = false;
    bool haveReport_ = false;
    uint32_t lastReport_ = 0;
    Vector target_{0.0f, 0.0f};
};
}  // namespace motion
