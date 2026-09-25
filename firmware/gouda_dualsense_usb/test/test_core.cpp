#include "control.hpp"
#include <array>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <string>
using namespace gouda_usb;

static Frame make_command_for(uint32_t seq, int16_t right, int16_t forward, uint32_t now = 0) {
    return make_command(0x0123456789abcdefULL, seq, now, {right, forward});
}
static void connect_centered(Core& c, uint32_t now) {
    c.bluetooth_connected(now);
    c.bluetooth_report(0, 0, now + 1);
}
static bool arm(Core& c, uint32_t seq, uint32_t now) {
    return c.receive(make_control(Arm, c.boot_token(), seq, now), now);
}
static void test_crc_golden_and_layout() {
    const uint8_t vector[] = "123456789";
    assert(crc16_ccitt_false(vector, 9) == 0x29b1);
    Frame f = make_command_for(3, -375, 625, 0x12345678);
    const auto bytes = encode(f);
    const uint8_t expected[] = {
        0xa5,0x5a,0x03,0x01,0xef,0xcd,0xab,0x89,0x67,0x45,0x23,0x01,
        0x03,0x00,0x00,0x00,0x78,0x56,0x34,0x12,0x89,0xfe,0x71,0x02,
        0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
        0,0,0,0,0,0,0,0,0,0,0,0,0,0,0x83,0x60
    };
    static_assert(sizeof(expected) == kFrameSize);
    for (size_t i = 0; i < kFrameSize; ++i) assert(bytes[i] == expected[i]);
    Frame decoded;
    assert(decode(bytes.data(), decoded));
    assert(decoded.boot_token == f.boot_token && decoded.sender_seq == 3);
    assert(command_values(decoded).right == -375 && command_values(decoded).forward == 625);
}
static void test_status_offsets_and_age_fields() {
    StatusValues v;
    v.owner = Manual; v.reason = ManualOverride; v.flags = kFlagConnected | kFlagFresh | kFlagCentered;
    v.raw_x = -512; v.raw_y = 511; v.manual_right = -1000; v.manual_forward = 999;
    v.pc_right = 123; v.pc_forward = -456; v.applied_right = -1000; v.applied_forward = 999;
    v.dac_x = 2012; v.dac_y = 4095; v.requested_mv_x = 230; v.requested_mv_y = 4700;
    v.last_accepted_pc_seq = 0xfedcba98; v.bluetooth_age_ms = 17; v.pc_age_ms = 249;
    auto b = encode(make_status(42, 7, 0x11223344, v));
    assert(get_u64(b.data() + 4) == 42 && get_u32(b.data() + 12) == 7);
    assert(b[20] == Manual && b[21] == ManualOverride && get_u16(b.data() + 22) == 7);
    assert(get_i16(b.data() + 24) == -512 && get_i16(b.data() + 26) == 511);
    assert(get_i16(b.data() + 28) == -1000 && get_i16(b.data() + 30) == 999);
    assert(get_i16(b.data() + 32) == 123 && get_i16(b.data() + 34) == -456);
    assert(get_i16(b.data() + 36) == -1000 && get_i16(b.data() + 38) == 999);
    assert(get_u16(b.data() + 40) == 2012 && get_u16(b.data() + 42) == 4095);
    assert(get_u16(b.data() + 44) == 230 && get_u16(b.data() + 46) == 4700);
    assert(get_u32(b.data() + 48) == 0xfedcba98 && get_u32(b.data() + 52) == 17 && get_u32(b.data() + 56) == 249);
    Frame d; assert(decode(b.data(), d));
    const auto roundtrip = status_values(d);
    assert(roundtrip.pc_forward == -456 && roundtrip.pc_age_ms == 249 && roundtrip.bluetooth_age_ms == 17);
}
static void test_parser_partial_corrupt_and_resync() {
    Parser p; Frame out;
    auto good = encode(make_command_for(10, 1, -2));
    for (size_t i = 0; i < 15; ++i) assert(!p.feed(good[i], out));
    for (size_t i = 15; i < good.size(); ++i) assert(p.feed(good[i], out) == (i == good.size() - 1));
    assert(out.sender_seq == 10);
    auto corrupt = good; corrupt[38] ^= 0x40;
    for (uint8_t b : corrupt) assert(!p.feed(b, out));
    bool found = false;
    for (uint8_t b : good) if (p.feed(b, out)) found = true;
    assert(found && out.sender_seq == 10);
    auto reserved = good; reserved[60] = 1;
    for (uint8_t b : reserved) assert(!p.feed(b, out));
    auto overrange = encode(make_command_for(11, 1001, 0));
    assert(!decode(overrange.data(), out));
    auto trailing = good; trailing[24] = 1; put_u16(trailing.data() + 62, crc16_ccitt_false(trailing.data(), 62));
    assert(!decode(trailing.data(), out));
}
static void test_boot_manual_and_both_axis_ownership() {
    Core c(77); assert(!c.auto_enabled());
    auto s = c.status(0); assert(s.owner == Stopped && (s.flags & kFlagAutoEnabled) == 0);
    connect_centered(c, 10);
    c.bluetooth_report(512, 0, 20);
    auto a = c.output(20);
    assert(a.owner == Manual && a.value.right > .99f && a.value.forward == 0);
    // PC candidate commands forward. Manual right takes both axes, so forward is zero.
    assert(c.receive(make_command(77, 1, 21, {0, 1000}), 21));
    c.bluetooth_report(512, 0, 30);
    a = c.output(30);
    assert(a.owner == Manual && a.value.right > .99f && a.value.forward == 0);
    assert(c.receive(make_command(77, 2, 31, {0, 0}), 31));
    assert(!arm(c, 3, 31)); // currently displaced manual stick cannot ARM
    c.bluetooth_report(0, 0, 31);
    assert(arm(c, 3, 31));
    assert(c.receive(make_command(77, 4, 32, {0, 1000}), 32));
    c.bluetooth_report(300, 0, 33);
    c.bluetooth_report(0, 0, 40);
    c.output(41);
    assert(c.output(239).reason == NeutralRecoveryWait);
    a = c.output(241);
    assert(a.owner == Autonomous && a.value.forward > .99f && a.value.right == 0);
}
static void test_arm_contract_and_sequence_wrap() {
    Core c(99); connect_centered(c, 0);
    assert(!arm(c, 1, 2)); // no neutral COMMAND yet
    assert(c.receive(make_command(99, 1, 3, {1, 0}), 3));
    assert(!arm(c, 2, 4)); // latest command non-neutral
    assert(c.receive(make_command(99, 3, 5, {0, 0}), 5));
    assert(arm(c, 4, 6));
    assert(!c.receive(make_command(99, 4, 7, {0, 0}), 7)); // duplicate sequence
    assert(!c.receive(make_command(99, 0x80000004u, 8, {0, 0}), 8)); // half-range is ambiguous/old
    assert(c.receive(make_command(99, 5, 9, {0, 0}), 9));
    Core wrap(99); connect_centered(wrap, 0);
    assert(wrap.receive(make_command(99, 0xfffffffeu, 1, {0,0}), 1));
    assert(wrap.receive(make_command(99, 0xffffffffu, 2, {0,0}), 2));
    assert(wrap.receive(make_command(99, 0, 3, {0,0}), 3));
    assert(!wrap.receive(make_command(99, 0xffffffffu, 4, {0,0}), 4));
    auto wrong = make_command(100, 1, 4, {0,0}); assert(!wrap.receive(wrong, 4));
}
static void test_manual_override_return_after_neutral_200ms() {
    Core c(123); connect_centered(c, 0);
    assert(c.receive(make_command(123, 1, 1, {0,0}), 1)); assert(arm(c, 2, 2));
    assert(c.receive(make_command(123, 3, 3, {-600, 0}), 3));
    c.bluetooth_report(300, 0, 10);
    auto a = c.output(10); assert(a.owner == Manual);
    c.bluetooth_report(0, 0, 20); c.output(21);
    assert(c.output(220).reason == NeutralRecoveryWait);
    assert(c.output(221).owner == Autonomous);
    c.bluetooth_report(300, 0, 222); assert(c.output(222).owner == Manual);
    assert(c.receive(make_command(123, 4, 223, {-600, 0}), 223));
    c.bluetooth_report(0, 0, 224); c.output(225);
    assert(c.output(424).reason == NeutralRecoveryWait);
    assert(c.output(425).owner == Autonomous);
}
static void test_pc_timeout_does_not_disable_manual_but_requires_rearm() {
    Core c(123); connect_centered(c, 0);
    assert(c.receive(make_command(123, 1, 1, {0,0}), 1)); assert(arm(c, 2, 2));
    assert(c.receive(make_command(123, 3, 3, {500,0}), 3));
    c.bluetooth_report(0, 0, 10); c.output(11); assert(c.output(211).owner == Autonomous);
    c.bluetooth_report(300, 0, 211);
    auto a=c.output(260); assert(a.owner == Manual && !c.auto_enabled());
    c.bluetooth_report(0, 0, 261);
    assert(c.receive(make_command(123, 4, 262, {0,0}), 262));
    assert(!c.auto_enabled()); // a fresh PC command does not auto-resume
    assert(c.output(461).owner == Stopped);
    c.bluetooth_report(0, 0, 450);
    assert(c.receive(make_command(123, 5, 450, {0,0}), 450));
    assert(arm(c, 6, 451));
    c.output(452);
    assert(c.output(651).reason == NeutralRecoveryWait);
    assert(c.output(652).owner == Autonomous);
}
static void test_bluetooth_fault_stops_and_needs_center_and_rearm() {
    Core c(123); connect_centered(c, 0);
    assert(c.receive(make_command(123, 1, 1, {0,0}), 1)); assert(arm(c, 2, 2));
    assert(c.receive(make_command(123, 3, 3, {0,800}), 3));
    c.output(4); assert(c.output(210).owner == Autonomous);
    c.tick(251); auto a=c.output(251);
    assert(a.owner == Stopped && !c.auto_enabled() && a.reason == BluetoothStale);
    c.bluetooth_report(300, 0, 260);
    assert(c.output(260).owner == Stopped); // must center after stale input
    c.bluetooth_report(0, 0, 270);
    c.bluetooth_report(0, 0, 450);
    assert(c.receive(make_command(123, 4, 450, {0,0}), 450));
    assert(arm(c, 5, 451));
    assert(c.receive(make_command(123, 6, 452, {0,800}), 452));
    c.output(453);
    assert(c.output(651).reason == NeutralRecoveryWait);
    assert(c.output(652).owner == Autonomous);
    c.bluetooth_disconnected(672);
    a=c.output(672); assert(a.owner == Stopped && !c.auto_enabled() && a.reason == BluetoothDisconnected);
}
static void test_disarm_preserves_manual() {
    Core c(88); connect_centered(c, 0);
    assert(c.receive(make_command(88, 1, 1, {0,0}), 1)); assert(arm(c, 2, 2));
    c.bluetooth_report(300, 0, 3); assert(c.output(3).owner == Manual);
    assert(c.receive(make_control(Disarm, 88, 3, 4), 4));
    auto a = c.output(4);
    assert(!c.auto_enabled() && a.owner == Manual);
    c.bluetooth_report(0, 0, 5); assert(c.output(5).owner == Stopped);
}
static void test_circle_mapping_and_timeout_wrap() {
    assert(map_voltage({0,0}).x == 2500 && map_voltage({0,0}).y == 2500);
    for (int x=-1000; x<=1000; x+=25) for (int y=-1000; y<=1000; y+=25) {
        const Voltage v=map_voltage({x/1000.0f,y/1000.0f});
        assert(v.x>=230 && v.x<=4700 && v.y>=230 && v.y<=4700 && inside_circle(v));
        assert(dac_code(v.x)<=4095 && dac_code(v.y)<=4095);
    }
    Core c(6); connect_centered(c, 0xfffffff0u);
    assert(c.receive(make_command(6, 1, 0, {0,0}), 0xfffffff2u)); assert(arm(c,2,0xfffffff3u));
    assert(c.receive(make_command(6,3,1,{0,500}),0xfffffff4u));
    for (uint32_t dt = 1; dt <= 203; ++dt) c.tick(uint32_t(0xfffffff4u + dt));
    assert(c.output(0xc1u).owner == Autonomous);
    auto stopped=c.output(0x180u);
    assert(stopped.owner == Stopped && !c.auto_enabled());
}
int main() {
    test_crc_golden_and_layout(); test_status_offsets_and_age_fields();
    test_parser_partial_corrupt_and_resync(); test_boot_manual_and_both_axis_ownership();
    test_arm_contract_and_sequence_wrap(); test_manual_override_return_after_neutral_200ms();
    test_pc_timeout_does_not_disable_manual_but_requires_rearm();
    test_bluetooth_fault_stops_and_needs_center_and_rearm(); test_disarm_preserves_manual();
    test_circle_mapping_and_timeout_wrap();
    std::cout << "USB firmware v3 protocol, arbitration, watchdog and DAC boundary tests passed\n";
}
