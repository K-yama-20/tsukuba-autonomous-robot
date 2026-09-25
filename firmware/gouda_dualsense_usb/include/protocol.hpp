#pragma once
#include <array>
#include <cstddef>
#include <cstdint>

namespace gouda_usb {
constexpr size_t kFrameSize = 64;
constexpr uint8_t kVersion = 3;
enum Kind : uint8_t { Command = 1, Arm = 2, Disarm = 3, Status = 128 };
enum Owner : uint8_t { Stopped = 0, Manual = 1, Autonomous = 2 };
enum Reason : uint8_t {
    StoppedReason = 0,
    BootDisarmed = 1,
    BluetoothDisconnected = 2,
    BluetoothStale = 3,
    WaitingForCenter = 4,
    ManualOverride = 5,
    PcStale = 6,
    NeutralRecoveryWait = 7,
    AutonomousControl = 8,
};
constexpr uint16_t kFlagConnected = 1u << 0;
constexpr uint16_t kFlagFresh = 1u << 1;
constexpr uint16_t kFlagCentered = 1u << 2;
constexpr uint16_t kFlagAutoEnabled = 1u << 3;
constexpr uint32_t kNeverSeenAgeMs = 0xffffffffu;

struct Frame {
    uint8_t kind = Command;
    uint64_t boot_token = 0;
    uint32_t sender_seq = 0;
    uint32_t sender_monotonic_ms = 0;
    std::array<uint8_t, 40> payload{};
};
struct CommandValues { int16_t right = 0; int16_t forward = 0; };
struct StatusValues {
    uint8_t owner = Stopped;
    uint8_t reason = StoppedReason;
    uint16_t flags = 0;
    int16_t raw_x = 0, raw_y = 0;
    int16_t manual_right = 0, manual_forward = 0;
    int16_t pc_right = 0, pc_forward = 0;
    int16_t applied_right = 0, applied_forward = 0;
    uint16_t dac_x = 0, dac_y = 0;
    uint16_t requested_mv_x = 2500, requested_mv_y = 2500;
    uint32_t last_accepted_pc_seq = 0;
    uint32_t bluetooth_age_ms = kNeverSeenAgeMs;
    uint32_t pc_age_ms = kNeverSeenAgeMs;
};

inline uint16_t crc16_ccitt_false(const uint8_t* data, size_t length) {
    uint16_t crc = 0xffff;
    while (length--) {
        crc ^= static_cast<uint16_t>(*data++) << 8;
        for (int bit = 0; bit < 8; ++bit)
            crc = (crc & 0x8000u) ? static_cast<uint16_t>((crc << 1) ^ 0x1021u)
                                   : static_cast<uint16_t>(crc << 1);
    }
    return crc;
}
inline uint16_t get_u16(const uint8_t* p) { return uint16_t(p[0]) | (uint16_t(p[1]) << 8); }
inline uint32_t get_u32(const uint8_t* p) {
    return uint32_t(p[0]) | (uint32_t(p[1]) << 8) | (uint32_t(p[2]) << 16) | (uint32_t(p[3]) << 24);
}
inline uint64_t get_u64(const uint8_t* p) { return uint64_t(get_u32(p)) | (uint64_t(get_u32(p + 4)) << 32); }
inline int16_t get_i16(const uint8_t* p) { return static_cast<int16_t>(get_u16(p)); }
inline void put_u16(uint8_t* p, uint16_t v) { p[0] = uint8_t(v); p[1] = uint8_t(v >> 8); }
inline void put_u32(uint8_t* p, uint32_t v) {
    for (int i = 0; i < 4; ++i) p[i] = uint8_t(v >> (8 * i));
}
inline void put_u64(uint8_t* p, uint64_t v) {
    for (int i = 0; i < 8; ++i) p[i] = uint8_t(v >> (8 * i));
}
inline void put_i16(uint8_t* p, int16_t v) { put_u16(p, static_cast<uint16_t>(v)); }
inline bool zero_bytes(const uint8_t* p, size_t n) {
    for (size_t i = 0; i < n; ++i) if (p[i] != 0) return false;
    return true;
}
inline bool valid_payload(const Frame& f) {
    switch (f.kind) {
    case Command:
        return get_i16(f.payload.data()) >= -1000 && get_i16(f.payload.data()) <= 1000 &&
               get_i16(f.payload.data() + 2) >= -1000 && get_i16(f.payload.data() + 2) <= 1000 &&
               zero_bytes(f.payload.data() + 4, 36);
    case Arm:
    case Disarm:
        return zero_bytes(f.payload.data(), f.payload.size());
    case Status:
        return f.payload[0] <= Autonomous && f.payload[1] <= AutonomousControl &&
               (get_u16(f.payload.data() + 2) & ~uint16_t(0x000f)) == 0 &&
               get_i16(f.payload.data() + 4) >= -512 && get_i16(f.payload.data() + 4) <= 511 &&
               get_i16(f.payload.data() + 6) >= -512 && get_i16(f.payload.data() + 6) <= 511 &&
               get_i16(f.payload.data() + 8) >= -1000 && get_i16(f.payload.data() + 8) <= 1000 &&
               get_i16(f.payload.data() + 10) >= -1000 && get_i16(f.payload.data() + 10) <= 1000 &&
               get_i16(f.payload.data() + 12) >= -1000 && get_i16(f.payload.data() + 12) <= 1000 &&
               get_i16(f.payload.data() + 14) >= -1000 && get_i16(f.payload.data() + 14) <= 1000 &&
               get_i16(f.payload.data() + 16) >= -1000 && get_i16(f.payload.data() + 16) <= 1000 &&
               get_i16(f.payload.data() + 18) >= -1000 && get_i16(f.payload.data() + 18) <= 1000 &&
               get_u16(f.payload.data() + 20) <= 4095 && get_u16(f.payload.data() + 22) <= 4095 &&
               get_u16(f.payload.data() + 24) <= 4700 && get_u16(f.payload.data() + 26) <= 4700;
    default: return false;
    }
}
inline std::array<uint8_t, kFrameSize> encode(const Frame& frame) {
    std::array<uint8_t, kFrameSize> out{};
    out[0] = 0xa5; out[1] = 0x5a; out[2] = kVersion; out[3] = frame.kind;
    put_u64(out.data() + 4, frame.boot_token);
    put_u32(out.data() + 12, frame.sender_seq);
    put_u32(out.data() + 16, frame.sender_monotonic_ms);
    for (size_t i = 0; i < frame.payload.size(); ++i) out[20 + i] = frame.payload[i];
    const uint16_t crc = crc16_ccitt_false(out.data(), 62);
    put_u16(out.data() + 62, crc);
    return out;
}
inline bool decode(const uint8_t* bytes, Frame& frame) {
    if (bytes[0] != 0xa5 || bytes[1] != 0x5a || bytes[2] != kVersion ||
        get_u16(bytes + 60) != 0 || get_u16(bytes + 62) != crc16_ccitt_false(bytes, 62)) return false;
    Frame parsed;
    parsed.kind = bytes[3];
    parsed.boot_token = get_u64(bytes + 4);
    parsed.sender_seq = get_u32(bytes + 12);
    parsed.sender_monotonic_ms = get_u32(bytes + 16);
    for (size_t i = 0; i < parsed.payload.size(); ++i) parsed.payload[i] = bytes[20 + i];
    if (!valid_payload(parsed)) return false;
    frame = parsed;
    return true;
}
inline Frame make_command(uint64_t token, uint32_t sequence, uint32_t sender_ms, CommandValues v) {
    Frame f; f.kind = Command; f.boot_token = token; f.sender_seq = sequence; f.sender_monotonic_ms = sender_ms;
    put_i16(f.payload.data(), v.right); put_i16(f.payload.data() + 2, v.forward); return f;
}
inline Frame make_control(uint8_t kind, uint64_t token, uint32_t sequence, uint32_t sender_ms) {
    Frame f; f.kind = kind; f.boot_token = token; f.sender_seq = sequence; f.sender_monotonic_ms = sender_ms; return f;
}
inline Frame make_status(uint64_t token, uint32_t device_sequence, uint32_t device_ms, const StatusValues& v) {
    Frame f; f.kind = Status; f.boot_token = token; f.sender_seq = device_sequence; f.sender_monotonic_ms = device_ms;
    uint8_t* p = f.payload.data();
    p[0] = v.owner; p[1] = v.reason; put_u16(p + 2, v.flags);
    put_i16(p + 4, v.raw_x); put_i16(p + 6, v.raw_y);
    put_i16(p + 8, v.manual_right); put_i16(p + 10, v.manual_forward);
    put_i16(p + 12, v.pc_right); put_i16(p + 14, v.pc_forward);
    put_i16(p + 16, v.applied_right); put_i16(p + 18, v.applied_forward);
    put_u16(p + 20, v.dac_x); put_u16(p + 22, v.dac_y);
    put_u16(p + 24, v.requested_mv_x); put_u16(p + 26, v.requested_mv_y);
    put_u32(p + 28, v.last_accepted_pc_seq); put_u32(p + 32, v.bluetooth_age_ms); put_u32(p + 36, v.pc_age_ms);
    return f;
}
inline CommandValues command_values(const Frame& f) {
    return {get_i16(f.payload.data()), get_i16(f.payload.data() + 2)};
}
inline StatusValues status_values(const Frame& f) {
    StatusValues v; const uint8_t* p = f.payload.data();
    v.owner = p[0]; v.reason = p[1]; v.flags = get_u16(p + 2);
    v.raw_x = get_i16(p + 4); v.raw_y = get_i16(p + 6);
    v.manual_right = get_i16(p + 8); v.manual_forward = get_i16(p + 10);
    v.pc_right = get_i16(p + 12); v.pc_forward = get_i16(p + 14);
    v.applied_right = get_i16(p + 16); v.applied_forward = get_i16(p + 18);
    v.dac_x = get_u16(p + 20); v.dac_y = get_u16(p + 22);
    v.requested_mv_x = get_u16(p + 24); v.requested_mv_y = get_u16(p + 26);
    v.last_accepted_pc_seq = get_u32(p + 28); v.bluetooth_age_ms = get_u32(p + 32); v.pc_age_ms = get_u32(p + 36);
    return v;
}

// Fixed storage and bounded work: at most one 64-byte frame is examined per feed call.
class Parser {
public:
    bool feed(uint8_t byte, Frame& out) {
        if (size_ < kFrameSize) buffer_[size_++] = byte;
        while (size_ >= 2 && (buffer_[0] != 0xa5 || buffer_[1] != 0x5a)) discard_one();
        if (size_ < kFrameSize) return false;
        if (decode(buffer_.data(), out)) { size_ = 0; return true; }
        discard_one();
        while (size_ >= 2 && (buffer_[0] != 0xa5 || buffer_[1] != 0x5a)) discard_one();
        return false;
    }
    size_t buffered() const { return size_; }
private:
    void discard_one() {
        for (size_t i = 1; i < size_; ++i) buffer_[i - 1] = buffer_[i];
        if (size_) --size_;
    }
    std::array<uint8_t, kFrameSize> buffer_{};
    size_t size_ = 0;
};
} // namespace gouda_usb
