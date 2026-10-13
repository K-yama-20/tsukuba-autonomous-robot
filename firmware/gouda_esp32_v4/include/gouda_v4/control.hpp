// Firmware core (ND-17): ownership arbitration, watchdogs, configuration handling and protocol replies.
// Design: design/docs/esp32_protocol_v4.md; same rules as the Python model gouda_core/gouda_core/esp32_sim.py.
// Header-only and hardware-free so it runs in the host test (test/host) and on the ESP32 (src/main.cpp).
//
// Contracts implemented here (DR-08): manual priority (RQ-I023), BT report timeout -> manual invalid (RQ-I024, PRM-21),
// PC command watchdog -> neutral (RQ-I068, PRM-13). Neutral is the DAC output whenever no source owns it. Without a valid
// configuration the DAC is never written (dac_written=false). No emergency-stop input exists (RQ-I072). No relay (DEC-037).
#pragma once
#include <cmath>
#include <cstdint>
#include <cstring>
#include "gouda_v4/protocol.hpp"
#include "gouda_v4/config.hpp"

namespace gouda_v4 {

enum Source : uint8_t { SRC_NONE = 0, SRC_MANUAL = 1, SRC_PC = 2 };
enum Reason : uint8_t { R_BOOT = 0, R_CONFIG_INVALID, R_BT_DISCONNECTED, R_BT_STALE, R_WAITING_CENTER, R_MANUAL_OVERRIDE, R_PC_DISABLED, R_PC_STALE,
                        R_NEUTRAL_RECOVERY_WAIT, R_PC_CONTROL, R_MANUAL_NEUTRAL };
enum EventCode : uint8_t { E_BOOT = 0, E_CONFIG_LOADED_NVS, E_CONFIG_LOADED_BUILD, E_CONFIG_SET, E_CONFIG_REJECTED, E_BT_CONNECTED, E_BT_DISCONNECTED,
                           E_BT_STALE, E_MANUAL_OVERRIDE_BEGIN, E_MANUAL_OVERRIDE_END, E_PC_ENABLED, E_PC_DISABLED_STALE, E_PC_DISABLED_REQUEST, E_PC_FRAME_REJECTED };
enum Flag : uint8_t { F_BT_CONNECTED = 1, F_BT_FRESH = 2, F_CENTERED = 4, F_PC_ENABLED = 8, F_PC_FRESH = 16, F_CONFIG_VALID = 32 };

struct Vec { float x = 0, y = 0; bool zero() const { return x == 0 && y == 0; } };
struct Applied { uint8_t source = SRC_NONE, reason = R_BOOT; Vec v; bool dac_written = false; uint16_t target_x_mv = 0, target_y_mv = 0, dac_x = 0, dac_y = 0; };

inline bool insideCircle(int32_t x, int32_t y, int32_t lo, int32_t hi) {
    int64_t dx = 2 * int64_t(x) - (lo + hi), dy = 2 * int64_t(y) - (lo + hi), d = hi - lo; return dx * dx + dy * dy <= d * d;
}
// Circle-limited mapping of the previous firmware, parametrised by the configuration (x right+, y forward+ in [-1, 1]).
inline void mapVoltage(float x, float y, uint16_t neutral, uint16_t lo, uint16_t hi, uint16_t& ox, uint16_t& oy) {
    float mag = std::sqrt(x * x + y * y);
    if (mag == 0) { ox = oy = neutral; return; }
    float ux = x / mag, uy = y / mag;
    float center = (lo + hi) / 2.0f, radius = (hi - lo) / 2.0f, offset = float(neutral) - center;
    float dot = offset * (ux + uy);
    float inner = dot * dot + radius * radius - 2 * offset * offset; if (inner < 0) inner = 0;
    float distance = -dot + std::sqrt(inner);
    float travel = (mag < 1 ? mag : 1) * distance;
    int32_t rx = int32_t(std::lround(neutral + ux * travel)), ry = int32_t(std::lround(neutral + uy * travel));
    while (!insideCircle(rx, ry, lo, hi)) {
        int32_t dx = 2 * rx - (lo + hi), dy = 2 * ry - (lo + hi);
        if (std::abs(dx) >= std::abs(dy)) rx += dx > 0 ? -1 : 1; else ry += dy > 0 ? -1 : 1;
    }
    ox = uint16_t(rx); oy = uint16_t(ry);
}
inline uint16_t dacCode(uint16_t mv, uint16_t full_scale) { uint32_t c = (uint32_t(mv) * 4095u + full_scale / 2) / full_scale; return c > 4095 ? 4095 : uint16_t(c); }
inline Vec manualVector(int16_t xq, int16_t yq, uint16_t deadzone_q) {
    float x = clampAxis(xq) / float(kAxisLimit), y = clampAxis(yq) / float(kAxisLimit);
    float r = std::sqrt(x * x + y * y), dz = deadzone_q / float(kAxisLimit);
    if (r <= dz) return {};
    float m = ((r < 1 ? r : 1) - dz) / (1 - dz);
    return {x * m / r, y * m / r};
}

class Core {
public:
    struct Event { uint8_t code, arg; uint32_t ms; };
    static constexpr size_t kTxCapacity = 1024;

    Core(uint32_t boot_token, const Config* initial, bool from_nvs, uint32_t now) : token_(boot_token), now_(now) {
        if (initial) { cfg_ = *initial; have_cfg_ = true; }
        event(E_BOOT, 0);
        if (initial) event(from_nvs ? E_CONFIG_LOADED_NVS : E_CONFIG_LOADED_BUILD, cfg_.valid() ? 1 : 0);
    }
    uint32_t bootToken() const { return token_; }
    const Config& config() const { return cfg_; }
    bool configValid() const { return have_cfg_ && cfg_.valid(); }
    uint8_t configGeneration() const { return cfg_gen_; }
    bool pcEnabled() const { return pc_enabled_; }
    bool centered() const { return centered_; }
    // Set by SET_CONFIG; main.cpp persists the configuration to NVS and clears it.
    bool configChanged() const { return cfg_changed_; }
    void clearConfigChanged() { cfg_changed_ = false; }
    void setConfigGeneration(uint8_t g) { cfg_gen_ = g; }

    // ---- outgoing bytes (STATUS / EVENT / replies); drained by the caller ----
    size_t txSize() const { return tx_n_; }
    const uint8_t* txData() const { return tx_; }
    void txClear() { tx_n_ = 0; }
    // ---- events (ring of the last few, for the host test and logging) ----
    const Event* events() const { return ev_; } size_t eventCount() const { return ev_n_; } size_t eventTotal() const { return ev_total_; }

    // ---- Bluetooth gamepad inputs (x right+, y forward+, q10000) ----
    void btConnect(uint32_t now) { now_ = now; bt_connected_ = true; bt_have_report_ = false; centered_ = false; manual_ = {}; bt_stale_flagged_ = false; event(E_BT_CONNECTED, 0); }
    void btDisconnect(uint32_t now) { now_ = now; bt_connected_ = false; bt_have_report_ = false; centered_ = false; manual_ = {}; event(E_BT_DISCONNECTED, 0); }
    void btReport(int16_t xq, int16_t yq, uint32_t now) {
        now_ = now;
        if (!bt_connected_) return;
        if (configValid() && bt_have_report_ && uint32_t(now - bt_last_ms_) >= cfg_.bt_report_timeout_ms) { centered_ = false; manual_ = {}; }
        bt_last_ms_ = now; bt_have_report_ = true; bt_stale_flagged_ = false;
        Vec v = manualVector(xq, yq, configValid() ? cfg_.manual_deadzone_q10000 : uint16_t(kAxisLimit));
        if (!centered_ && v.zero()) centered_ = true;
        manual_ = centered_ ? v : Vec{};
    }

    // ---- serial input ----
    void feed(const uint8_t* data, size_t n, uint32_t now) { now_ = now; Frame f; for (size_t i = 0; i < n; i++) if (parser_.feed(data[i], f)) handle(f); }
    uint32_t rejectedFrames() const { return parser_.rejected; }

    // ---- periodic (call at the control period) ----
    void tick(uint32_t now) {
        now_ = now;
        if (!configValid()) return;
        if (bt_connected_ && bt_have_report_ && !btFresh() && !bt_stale_flagged_) { centered_ = false; manual_ = {}; bt_stale_flagged_ = true; event(E_BT_STALE, 0); }
        if (pc_enabled_ && !pcFresh()) { pc_enabled_ = false; event(E_PC_DISABLED_STALE, 0); }
        Applied a = applied();
        bool manual_active = a.source == SRC_MANUAL;
        if (manual_active) { last_manual_active_ms_ = now; have_manual_active_ = true; }
        if (manual_active != manual_active_prev_) { event(manual_active ? E_MANUAL_OVERRIDE_BEGIN : E_MANUAL_OVERRIDE_END, 0); manual_active_prev_ = manual_active; }
        if (cfg_.status_period_ms > 0 && (!status_sent_ || uint32_t(now - status_last_ms_) >= cfg_.status_period_ms)) { sendStatus(); status_last_ms_ = now; status_sent_ = true; }
    }

    bool btFresh() const { return configValid() && bt_connected_ && bt_have_report_ && uint32_t(now_ - bt_last_ms_) < cfg_.bt_report_timeout_ms; }
    bool pcFresh() const { return configValid() && pc_have_cmd_ && uint32_t(now_ - pc_last_ms_) < cfg_.pc_command_watchdog_ms; }

    // ---- arbitration: pure function of the state ----
    Applied applied() const {
        Applied a;
        if (!configValid()) { a.source = SRC_NONE; a.reason = R_CONFIG_INVALID; a.dac_written = false; return a; }
        bool bt_fresh = btFresh();
        bool manual_active = bt_fresh && centered_ && !manual_.zero();
        if (manual_active) { a.source = SRC_MANUAL; a.reason = R_MANUAL_OVERRIDE; a.v = manual_; }
        else {
            bool release_ok = !have_manual_active_ || uint32_t(now_ - last_manual_active_ms_) >= cfg_.manual_release_neutral_ms;
            if (pc_enabled_ && pcFresh()) {
                if (release_ok) { a.source = SRC_PC; a.reason = R_PC_CONTROL; a.v = {pc_x_ / float(kAxisLimit), pc_y_ / float(kAxisLimit)}; }
                else { a.source = SRC_NONE; a.reason = R_NEUTRAL_RECOVERY_WAIT; }
            } else {
                a.source = SRC_NONE;
                if (bt_connected_ && bt_have_report_ && !bt_fresh) a.reason = R_BT_STALE;
                else if (bt_connected_ && bt_fresh && !centered_) a.reason = R_WAITING_CENTER;
                else if (pc_have_cmd_ && !pcFresh()) a.reason = R_PC_STALE;
                else if (bt_fresh && centered_) a.reason = R_MANUAL_NEUTRAL;
                else if (!bt_connected_ && !pc_have_cmd_) a.reason = R_BT_DISCONNECTED;
                else a.reason = R_PC_DISABLED;
            }
        }
        mapVoltage(a.v.x, a.v.y, cfg_.dac_neutral_mv, cfg_.dac_min_mv, cfg_.dac_max_mv, a.target_x_mv, a.target_y_mv);
        a.dac_x = dacCode(a.target_x_mv, cfg_.dac_full_scale_mv); a.dac_y = dacCode(a.target_y_mv, cfg_.dac_full_scale_mv); a.dac_written = true;
        return a;
    }

    void sendStatus() {
        Applied a = applied(); uint8_t p[kStatusPayload]{};
        uint8_t flags = (bt_connected_ ? F_BT_CONNECTED : 0) | (btFresh() ? F_BT_FRESH : 0) | (centered_ ? F_CENTERED : 0) | (pc_enabled_ ? F_PC_ENABLED : 0) | (pcFresh() ? F_PC_FRESH : 0) | (configValid() ? F_CONFIG_VALID : 0);
        p[0] = a.source; p[1] = a.reason; p[2] = flags; p[3] = cfg_gen_;
        put16(p + 4, uint16_t(q(manual_.x))); put16(p + 6, uint16_t(q(manual_.y))); put16(p + 8, uint16_t(pc_x_)); put16(p + 10, uint16_t(pc_y_));
        put16(p + 12, uint16_t(q(a.v.x))); put16(p + 14, uint16_t(q(a.v.y)));
        put16(p + 16, a.dac_written ? a.target_x_mv : 0); put16(p + 18, a.dac_written ? a.target_y_mv : 0); put16(p + 20, a.dac_written ? a.dac_x : 0); put16(p + 22, a.dac_written ? a.dac_y : 0);
        put32(p + 24, pc_have_cmd_ ? uint32_t(now_ - pc_last_ms_) : kNever); put32(p + 28, bt_have_report_ ? uint32_t(now_ - bt_last_ms_) : kNever);
        put32(p + 32, pc_have_seq_ ? pc_last_seq_ : 0); put32(p + 36, now_); put16(p + 40, 0);
        send(STATUS, p, sizeof p);
    }

private:
    static int16_t q(float v) { return int16_t(std::lround((v > 1 ? 1 : v < -1 ? -1 : v) * kAxisLimit)); }
    void send(uint8_t kind, const uint8_t* payload, size_t n) {
        if (tx_n_ + kMaxFrame > kTxCapacity) return;   // never block; a dropped STATUS is replaced by the next one
        tx_n_ += encodeFrame(tx_ + tx_n_, kind, ++tx_seq_, now_, payload, n);
    }
    void ack(uint8_t req, uint8_t result) { uint8_t p[kAckPayload] = {req, result}; send(ACK, p, sizeof p); }
    void event(uint8_t code, uint8_t arg) {
        ev_[ev_n_ < kEvents ? ev_n_ : kEvents - 1] = {code, arg, now_}; if (ev_n_ < kEvents) ev_n_++; else { memmove(ev_, ev_ + 1, (kEvents - 1) * sizeof(Event)); ev_[kEvents - 1] = {code, arg, now_}; }
        ev_total_++;
        uint8_t p[kEventPayload]; p[0] = code; p[1] = arg; put32(p + 2, now_); send(EVENT, p, sizeof p);
    }
    void handle(const Frame& f) {
        if (f.kind == HELLO) {
            if (f.length != kHelloPayload) { ack(f.kind, ACK_PAYLOAD); return; }
            uint8_t p[kHelloReplyPayload]; put32(p, get32(f.payload)); put32(p + 4, token_); p[8] = configValid() ? 1 : 0; p[9] = cfg_gen_; put16(p + 10, kVersion);
            send(HELLO_REPLY, p, sizeof p); return;
        }
        if (f.length < 4) { ack(f.kind, ACK_PAYLOAD); return; }
        if (get32(f.payload) != token_) { event(E_PC_FRAME_REJECTED, ACK_TOKEN); ack(f.kind, ACK_TOKEN); return; }
        switch (f.kind) {
        case COMMAND: {
            if (f.length != kCommandPayload) { ack(f.kind, ACK_PAYLOAD); return; }
            if (pc_have_seq_ && !newerSequence(f.seq, pc_last_seq_)) { event(E_PC_FRAME_REJECTED, 5); return; }
            pc_last_seq_ = f.seq; pc_have_seq_ = true;
            pc_x_ = clampAxis(int16_t(get16(f.payload + 4))); pc_y_ = clampAxis(int16_t(get16(f.payload + 6))); pc_have_cmd_ = true; pc_last_ms_ = now_;
            bool want = f.payload[8] & kFlagPcEnableRequest;
            if (want && !pc_enabled_ && pc_x_ == 0 && pc_y_ == 0) { pc_enabled_ = true; event(E_PC_ENABLED, 0); }
            else if (!want && pc_enabled_) { pc_enabled_ = false; event(E_PC_DISABLED_REQUEST, 0); }
            return;
        }
        case SET_CONFIG: {
            if (f.length != kSetConfigPayload) { ack(f.kind, ACK_PAYLOAD); return; }
            Config c = Config::fromBytes(f.payload + 4);
            if (!c.valid()) { event(E_CONFIG_REJECTED, 0); ack(f.kind, ACK_CONFIG); return; }
            cfg_ = c; have_cfg_ = true; cfg_gen_ = uint8_t(cfg_gen_ + 1); cfg_changed_ = true; event(E_CONFIG_SET, cfg_gen_); ack(f.kind, ACK_OK); return;
        }
        case GET_STATUS: sendStatus(); return;
        case GET_CONFIG: { uint8_t p[kConfigPayload]; p[0] = configValid() ? 1 : 0; p[1] = cfg_gen_; cfg_.toBytes(p + 2); send(CONFIG, p, sizeof p); return; }
        default: return;   // unknown kinds are ignored after CRC validation
        }
    }

    static constexpr size_t kEvents = 32;
    uint32_t token_; uint32_t now_;
    Config cfg_{}; bool have_cfg_ = false; uint8_t cfg_gen_ = 0; bool cfg_changed_ = false;
    bool bt_connected_ = false, bt_have_report_ = false, centered_ = false, bt_stale_flagged_ = false; uint32_t bt_last_ms_ = 0; Vec manual_;
    bool pc_enabled_ = false, pc_have_cmd_ = false, pc_have_seq_ = false; uint32_t pc_last_ms_ = 0, pc_last_seq_ = 0; int16_t pc_x_ = 0, pc_y_ = 0;
    bool have_manual_active_ = false, manual_active_prev_ = false; uint32_t last_manual_active_ms_ = 0;
    bool status_sent_ = false; uint32_t status_last_ms_ = 0; uint32_t tx_seq_ = 0;
    Parser parser_;
    uint8_t tx_[kTxCapacity]{}; size_t tx_n_ = 0;
    Event ev_[kEvents]{}; size_t ev_n_ = 0, ev_total_ = 0;
};

}  // namespace gouda_v4
