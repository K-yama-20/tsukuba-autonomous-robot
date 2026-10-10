// Firmware configuration (SO-11 axis_config): registered by the PC with SET_CONFIG (apply_timing=runtime_set), persisted in
// NVS, or taken from the generated build-time header. Design: docs/esp32_protocol_v4.md §5. Items: PRM-43..46 (DAC mV),
// PRM-13 (PC watchdog), PRM-21 (BT timeout), PRM-47/48 (manual arbitration), PRM-49 (STATUS period). Nothing is defaulted here.
#pragma once
#include <cstdint>
#include "gouda_v4/protocol.hpp"

namespace gouda_v4 {

struct Config {
    uint16_t dac_neutral_mv = 0, dac_min_mv = 0, dac_max_mv = 0, dac_full_scale_mv = 0;
    uint16_t pc_command_watchdog_ms = 0, bt_report_timeout_ms = 0;
    uint16_t manual_deadzone_q10000 = 0, manual_release_neutral_ms = 0, status_period_ms = 0, reserved = 0;

    bool valid() const {
        return dac_min_mv > 0 && dac_min_mv < dac_neutral_mv && dac_neutral_mv < dac_max_mv && dac_max_mv <= dac_full_scale_mv &&
               pc_command_watchdog_ms > 0 && bt_report_timeout_ms > 0 && manual_deadzone_q10000 < uint16_t(kAxisLimit);
    }
    void toItems(uint16_t* it) const {
        it[0] = dac_neutral_mv; it[1] = dac_min_mv; it[2] = dac_max_mv; it[3] = dac_full_scale_mv; it[4] = pc_command_watchdog_ms;
        it[5] = bt_report_timeout_ms; it[6] = manual_deadzone_q10000; it[7] = manual_release_neutral_ms; it[8] = status_period_ms; it[9] = reserved;
    }
    static Config fromItems(const uint16_t* it) {
        Config c; c.dac_neutral_mv = it[0]; c.dac_min_mv = it[1]; c.dac_max_mv = it[2]; c.dac_full_scale_mv = it[3]; c.pc_command_watchdog_ms = it[4];
        c.bt_report_timeout_ms = it[5]; c.manual_deadzone_q10000 = it[6]; c.manual_release_neutral_ms = it[7]; c.status_period_ms = it[8]; c.reserved = it[9];
        return c;
    }
    void toBytes(uint8_t* p) const { uint16_t it[10]; toItems(it); for (int i = 0; i < 10; i++) put16(p + 2 * i, it[i]); }
    static Config fromBytes(const uint8_t* p) { uint16_t it[10]; for (int i = 0; i < 10; i++) it[i] = get16(p + 2 * i); return fromItems(it); }
};

}  // namespace gouda_v4
