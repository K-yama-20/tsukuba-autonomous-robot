#pragma once
#include "protocol.hpp"
#include <algorithm>
#include <cmath>
#include <cstdint>

namespace gouda_usb {
constexpr int16_t kAxisLimit = 1000;
constexpr uint32_t kLinkTimeoutMs = 250;
constexpr uint32_t kNeutralResumeMs = 200;
constexpr uint16_t kNeutralMv = 2500, kMinimumMv = 230, kMaximumMv = 4700;
constexpr uint16_t kDacFullScaleMv = 4700;
constexpr float kDeadzone = 0.08f;
struct Vector { float right = 0, forward = 0; };
struct Voltage { uint16_t x = kNeutralMv, y = kNeutralMv; };
struct Applied {
    uint8_t owner = Stopped;
    uint8_t reason = BootDisarmed;
    Vector value{};
    Voltage requested{};
    uint16_t dac_x = 0, dac_y = 0;
};
inline float clamp_axis(float v) { return std::max(-1.0f, std::min(1.0f, v)); }
inline Vector normalize_input(int32_t raw_x, int32_t raw_y) {
    float x = clamp_axis(static_cast<float>(raw_x) / 512.0f);
    float y = clamp_axis(static_cast<float>(-raw_y) / 512.0f);
    const float radius = std::sqrt(x * x + y * y);
    if (radius <= kDeadzone) return {};
    const float magnitude = (std::min(radius, 1.0f) - kDeadzone) / (1.0f - kDeadzone);
    return {x * magnitude / radius, y * magnitude / radius};
}
inline Vector command_vector(CommandValues c) {
    return {clamp_axis(c.right / 1000.0f), clamp_axis(c.forward / 1000.0f)};
}
inline bool is_neutral(CommandValues c) { return c.right == 0 && c.forward == 0; }
inline int16_t quantize(float v) {
    return static_cast<int16_t>(std::lround(clamp_axis(v) * kAxisLimit));
}
inline bool inside_circle(Voltage v) {
    const int64_t dx = 2 * int64_t(v.x) - (kMinimumMv + kMaximumMv);
    const int64_t dy = 2 * int64_t(v.y) - (kMinimumMv + kMaximumMv);
    const int64_t diameter = kMaximumMv - kMinimumMv;
    return dx * dx + dy * dy <= diameter * diameter;
}
inline Voltage map_voltage(Vector value) {
    float x = clamp_axis(value.right), y = clamp_axis(value.forward);
    const float magnitude = std::sqrt(x * x + y * y);
    if (magnitude == 0) return {kNeutralMv, kNeutralMv};
    x /= magnitude; y /= magnitude;
    constexpr float center = (kMinimumMv + kMaximumMv) / 2.0f;
    constexpr float radius = (kMaximumMv - kMinimumMv) / 2.0f;
    constexpr float offset = kNeutralMv - center;
    const float dot = offset * (x + y);
    const float distance = -dot + std::sqrt(dot * dot + radius * radius - 2 * offset * offset);
    const float travel = std::min(magnitude, 1.0f) * distance;
    Voltage out{static_cast<uint16_t>(std::lround(kNeutralMv + x * travel)),
                static_cast<uint16_t>(std::lround(kNeutralMv + y * travel))};
    while (!inside_circle(out)) {
        const int dx = 2 * int(out.x) - (kMinimumMv + kMaximumMv);
        const int dy = 2 * int(out.y) - (kMinimumMv + kMaximumMv);
        if (std::abs(dx) >= std::abs(dy)) out.x = static_cast<uint16_t>(int(out.x) + (dx > 0 ? -1 : 1));
        else out.y = static_cast<uint16_t>(int(out.y) + (dy > 0 ? -1 : 1));
    }
    return out;
}
inline uint16_t dac_code(uint16_t mv) {
    const uint32_t code = (uint32_t(mv) * 4095 + kDacFullScaleMv / 2) / kDacFullScaleMv;
    return static_cast<uint16_t>(std::min<uint32_t>(4095, code));
}
inline bool newer_sequence(uint32_t candidate, uint32_t previous) {
    const uint32_t delta = candidate - previous;
    return delta != 0 && delta < 0x80000000u;
}
inline uint32_t age_ms(uint32_t now, uint32_t then) { return uint32_t(now - then); }

class Core {
public:
    explicit Core(uint64_t boot_token) : token_(boot_token) {}
    uint64_t boot_token() const { return token_; }
    bool auto_enabled() const { return auto_enabled_; }
    bool bt_connected() const { return bt_connected_; }
    bool bt_fresh(uint32_t now) const { return bt_connected_ && have_report_ && age_ms(now, last_bt_ms_) < kLinkTimeoutMs; }
    bool bt_centered() const { return centered_; }

    void bluetooth_connected(uint32_t now) {
        if (bt_connected_) bluetooth_disconnected(now);
        bt_connected_ = true; have_report_ = false; centered_ = false; manual_ = {};
        neutral_tracking_ = false; bt_stale_latched_ = false;
    }
    void bluetooth_disconnected(uint32_t) {
        bt_connected_ = false; have_report_ = false; centered_ = false;
        raw_x_ = raw_y_ = 0; manual_ = {}; neutral_tracking_ = false;
        auto_enabled_ = false; rearm_required_ = true; bt_stale_latched_ = false;
    }
    void bluetooth_report(int32_t raw_x, int32_t raw_y, uint32_t now) {
        if (!bt_connected_) return;
        if (have_report_ && age_ms(now, last_bt_ms_) >= kLinkTimeoutMs) {
            centered_ = false; manual_ = {}; neutral_tracking_ = false;
            auto_enabled_ = false; rearm_required_ = true; bt_stale_latched_ = true;
        }
        raw_x_ = static_cast<int16_t>(std::max(-512, std::min(511, raw_x)));
        raw_y_ = static_cast<int16_t>(std::max(-512, std::min(511, raw_y)));
        last_bt_ms_ = now; have_report_ = true; bt_stale_latched_ = false;
        const Vector next = normalize_input(raw_x_, raw_y_);
        if (!centered_ && next.right == 0.0f && next.forward == 0.0f) centered_ = true;
        manual_ = centered_ ? next : Vector{};
        if (manual_.right != 0.0f || manual_.forward != 0.0f) neutral_tracking_ = false;
    }

    bool receive(const Frame& f, uint32_t now) {
        tick(now);
        if (f.boot_token != token_ || !valid_payload(f) ||
            (f.kind != Command && f.kind != Arm && f.kind != Disarm)) return false;
        if (have_pc_seq_ && !newer_sequence(f.sender_seq, last_pc_seq_)) return false;
        if (f.kind == Arm) {
            const bool command_fresh = have_command_ && age_ms(now, last_command_ms_) < kLinkTimeoutMs;
            if (auto_enabled_ || !command_fresh || !is_neutral(command_) || !bt_fresh(now) || !centered_ || manual_.right != 0 || manual_.forward != 0) return false;
        }
        last_pc_seq_ = f.sender_seq; have_pc_seq_ = true; last_pc_ms_ = now; have_pc_traffic_ = true;
        if (f.kind == Command) {
            command_ = command_values(f); last_command_ms_ = now; have_command_ = true;
        } else if (f.kind == Arm) {
            auto_enabled_ = true; rearm_required_ = false;
            neutral_tracking_ = false;
        } else {
            auto_enabled_ = false; rearm_required_ = true;
            neutral_tracking_ = false;
        }
        return true;
    }

    void tick(uint32_t now) {
        if (bt_connected_ && have_report_ && age_ms(now, last_bt_ms_) >= kLinkTimeoutMs) {
            centered_ = false; manual_ = {}; neutral_tracking_ = false;
            bt_stale_latched_ = true; auto_enabled_ = false; rearm_required_ = true;
        }
        if (auto_enabled_ && (!have_command_ || age_ms(now, last_command_ms_) >= kLinkTimeoutMs)) {
            auto_enabled_ = false; rearm_required_ = true; neutral_tracking_ = false;
        }
        if (!bt_fresh(now) || !centered_ || manual_.right != 0 || manual_.forward != 0) {
            neutral_tracking_ = false;
        } else if (!neutral_tracking_) {
            neutral_since_ms_ = now; neutral_tracking_ = true;
        }
    }

    Applied output(uint32_t now) {
        tick(now);
        Applied out;
        if (!bt_connected_) out.reason = BluetoothDisconnected;
        else if (!bt_fresh(now)) out.reason = BluetoothStale;
        else if (!centered_) out.reason = WaitingForCenter;
        else if (manual_.right != 0 || manual_.forward != 0) {
            out.owner = Manual; out.reason = ManualOverride; out.value = manual_;
        } else if (!auto_enabled_) {
            out.reason = rearm_required_ ? (have_pc_traffic_ ? (age_ms(now, last_pc_ms_) >= kLinkTimeoutMs ? PcStale : BootDisarmed) : BootDisarmed) : BootDisarmed;
        } else if (!have_command_ || age_ms(now, last_command_ms_) >= kLinkTimeoutMs) {
            out.reason = PcStale;
        } else if (!neutral_tracking_ || age_ms(now, neutral_since_ms_) < kNeutralResumeMs) {
            out.reason = NeutralRecoveryWait;
        } else {
            out.owner = Autonomous; out.reason = AutonomousControl; out.value = command_vector(command_);
        }
        out.requested = map_voltage(out.value);
        out.dac_x = dac_code(out.requested.x); out.dac_y = dac_code(out.requested.y);
        return out;
    }

    StatusValues status(uint32_t now) {
        const Applied applied = output(now);
        StatusValues v;
        v.owner = applied.owner; v.reason = applied.reason;
        if (bt_connected_) v.flags |= kFlagConnected;
        if (bt_fresh(now)) v.flags |= kFlagFresh;
        if (bt_fresh(now) && centered_) v.flags |= kFlagCentered;
        if (auto_enabled_) v.flags |= kFlagAutoEnabled;
        v.raw_x = raw_x_; v.raw_y = raw_y_;
        v.manual_right = quantize(manual_.right); v.manual_forward = quantize(manual_.forward);
        v.pc_right = have_command_ ? command_.right : 0; v.pc_forward = have_command_ ? command_.forward : 0;
        v.applied_right = quantize(applied.value.right); v.applied_forward = quantize(applied.value.forward);
        v.dac_x = applied.dac_x; v.dac_y = applied.dac_y;
        v.requested_mv_x = applied.requested.x; v.requested_mv_y = applied.requested.y;
        v.last_accepted_pc_seq = have_pc_seq_ ? last_pc_seq_ : 0;
        v.bluetooth_age_ms = have_report_ ? age_ms(now, last_bt_ms_) : kNeverSeenAgeMs;
        v.pc_age_ms = have_pc_traffic_ ? age_ms(now, last_pc_ms_) : kNeverSeenAgeMs;
        return v;
    }

private:
    uint64_t token_;
    uint32_t last_pc_seq_ = 0, last_pc_ms_ = 0, last_command_ms_ = 0, last_bt_ms_ = 0, neutral_since_ms_ = 0;
    bool have_pc_seq_ = false, have_pc_traffic_ = false, have_command_ = false;
    bool bt_connected_ = false, have_report_ = false, centered_ = false, bt_stale_latched_ = false;
    bool auto_enabled_ = false, rearm_required_ = true, neutral_tracking_ = false;
    int16_t raw_x_ = 0, raw_y_ = 0;
    CommandValues command_{};
    Vector manual_{};
};
} // namespace gouda_usb
