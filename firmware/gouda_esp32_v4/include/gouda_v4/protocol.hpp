// PC–ESP32 serial protocol v4 codec (IFD-17 / IFD-43). Design: design/docs/esp32_protocol_v4.md (REV-027).
// Byte-identical with gouda_core/gouda_core/esp32_protocol.py (TS-29 golden vectors). Header-only, no Arduino dependency.
#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace gouda_v4 {

constexpr uint8_t kSync0 = 0xA5, kSync1 = 0x5A, kVersion = 4;
constexpr size_t kHeaderSize = 14, kMaxPayload = 64, kCrcSize = 2, kMaxFrame = kHeaderSize + kMaxPayload + kCrcSize;
constexpr int16_t kAxisLimit = 10000;
constexpr uint8_t kFlagPcEnableRequest = 0x01;
constexpr uint32_t kNever = 0xFFFFFFFFu;

enum Kind : uint8_t { HELLO = 0x01, COMMAND = 0x02, SET_CONFIG = 0x03, GET_STATUS = 0x08, GET_CONFIG = 0x09,
                      HELLO_REPLY = 0x80, STATUS = 0x81, EVENT = 0x82, CONFIG = 0x84, ACK = 0x85 };
enum AckResult : uint8_t { ACK_OK = 0, ACK_PAYLOAD = 1, ACK_TOKEN = 2, ACK_CONFIG = 3, ACK_STORE = 4 };
constexpr size_t kCommandPayload = 9, kHelloPayload = 4, kSetConfigPayload = 4 + 20, kStatusPayload = 42, kHelloReplyPayload = 12,
                 kEventPayload = 6, kConfigPayload = 22, kAckPayload = 2;

inline uint16_t crc16(const uint8_t* p, size_t n) {   // CRC-16/CCITT-FALSE; crc16("123456789") == 0x29B1
    uint16_t c = 0xFFFF;
    while (n--) { c ^= uint16_t(*p++) << 8; for (int i = 0; i < 8; i++) c = (c & 0x8000) ? uint16_t((c << 1) ^ 0x1021) : uint16_t(c << 1); }
    return c;
}
inline void put16(uint8_t* p, uint16_t v) { p[0] = uint8_t(v); p[1] = uint8_t(v >> 8); }
inline void put32(uint8_t* p, uint32_t v) { p[0] = uint8_t(v); p[1] = uint8_t(v >> 8); p[2] = uint8_t(v >> 16); p[3] = uint8_t(v >> 24); }
inline uint16_t get16(const uint8_t* p) { return uint16_t(p[0] | (uint16_t(p[1]) << 8)); }
inline uint32_t get32(const uint8_t* p) { return uint32_t(p[0]) | (uint32_t(p[1]) << 8) | (uint32_t(p[2]) << 16) | (uint32_t(p[3]) << 24); }
inline int16_t clampAxis(int32_t v) { return int16_t(v > kAxisLimit ? kAxisLimit : v < -kAxisLimit ? -kAxisLimit : v); }

struct Frame { uint8_t kind = 0; uint32_t seq = 0; uint32_t sender_ms = 0; uint8_t payload[kMaxPayload]{}; size_t length = 0; };

// Encodes into out (>= kMaxFrame bytes). Returns the frame size.
inline size_t encodeFrame(uint8_t* out, uint8_t kind, uint32_t seq, uint32_t sender_ms, const uint8_t* payload, size_t n) {
    if (n > kMaxPayload) n = kMaxPayload;
    out[0] = kSync0; out[1] = kSync1; out[2] = kVersion; out[3] = kind; put16(out + 4, uint16_t(n)); put32(out + 6, seq); put32(out + 10, sender_ms);
    if (n) memcpy(out + kHeaderSize, payload, n);
    put16(out + kHeaderSize + n, crc16(out + 2, kHeaderSize - 2 + n));
    return kHeaderSize + n + kCrcSize;
}

inline size_t encodeCommand(uint8_t* out, uint32_t seq, uint32_t ms, uint32_t boot_token, int16_t x, int16_t y, uint8_t flags) {
    uint8_t p[kCommandPayload]; put32(p, boot_token); put16(p + 4, uint16_t(clampAxis(x))); put16(p + 6, uint16_t(clampAxis(y))); p[8] = flags;
    return encodeFrame(out, COMMAND, seq, ms, p, sizeof p);
}

inline bool newerSequence(uint32_t candidate, uint32_t previous) { uint32_t d = candidate - previous; return d != 0 && d < 0x80000000u; }

// Stream parser: resynchronises on the sync bytes; invalid frames (version, length, CRC) are dropped and counted.
class Parser {
    uint8_t buf_[2 * kMaxFrame]{}; size_t n_ = 0;
public:
    uint32_t rejected = 0;
    // Feed one byte; returns true when a valid frame is complete (copied into f).
    bool feed(uint8_t b, Frame& f) {
        if (n_ == sizeof buf_) { memmove(buf_, buf_ + 1, --n_); }
        buf_[n_++] = b;
        for (;;) {
            size_t i = 0; while (i + 1 < n_ && !(buf_[i] == kSync0 && buf_[i + 1] == kSync1)) i++;
            if (i + 1 >= n_) { if (n_ && buf_[n_ - 1] != kSync0) n_ = 0; else if (n_ > 1) { buf_[0] = buf_[n_ - 1]; n_ = 1; } return false; }
            if (i) { memmove(buf_, buf_ + i, n_ - i); n_ -= i; }
            if (n_ < kHeaderSize) return false;
            uint8_t ver = buf_[2]; uint16_t len = get16(buf_ + 4);
            if (ver != kVersion || len > kMaxPayload) { rejected++; memmove(buf_, buf_ + 1, --n_); continue; }
            size_t total = kHeaderSize + len + kCrcSize;
            if (n_ < total) return false;
            if (crc16(buf_ + 2, kHeaderSize - 2 + len) != get16(buf_ + kHeaderSize + len)) { rejected++; memmove(buf_, buf_ + 1, --n_); continue; }
            f.kind = buf_[3]; f.seq = get32(buf_ + 6); f.sender_ms = get32(buf_ + 10); f.length = len; memcpy(f.payload, buf_ + kHeaderSize, len);
            memmove(buf_, buf_ + total, n_ - total); n_ -= total;
            return true;
        }
    }
};

}  // namespace gouda_v4
