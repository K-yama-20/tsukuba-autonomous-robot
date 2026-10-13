"""Unit tests of the PC–ESP32 protocol v4 codec, the bridge core (ND-12) and the Python firmware model (ND-17 stub).

Design tests: TS-29 (codec golden vectors, shared with the C++ host test), TS-13 (bridge keeps sending at PRM-14 and sends
neutral when joystick_command is stale), TS-19 (PC source neutral PRM-13 after the last VALID frame; invalid frames do not
extend), TS-17 (manual priority while the gamepad is active, PC resumes after PRM-48), TS-18 (BT report gap PRM-21 ->
manual invalid -> neutral; PC does not take over immediately). The firmware-side checks run against the Python model here
and against the C++ core in firmware/gouda_esp32_v4/test/host (same rules).

All numbers come from the generated parameter files (approved PRM-13/21, trial values of the rest)."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import esp32_protocol as p  # noqa: E402
from gouda_core import esp32_sim as sim  # noqa: E402
from gouda_core.vehicle_core import BridgeCore, BridgeSettings, REASON_INACTIVE, REASON_JOY_NOT_RECEIVED, REASON_JOY_STALE, REASON_FORWARD  # noqa: E402

PARAMS = Path(__file__).resolve().parents[2] / 'design' / 'generated' / 'params'
GOLDEN_COMMAND = 'a55a04020900030000004e61bc00cdab23015af16a1801adce'   # header(14) + payload(9) + crc; see test_golden_vector and the design doc
TOKEN = 0x0123ABCD


def load_yaml_flat(*names):
    import re
    vals = {}
    for name in names:
        for line in (PARAMS / name).read_text(encoding='utf-8').splitlines():
            m = re.match(r'\s*(\w+): ([-\d.]+)', line)
            if m: vals[m.group(1)] = float(m.group(2))
    return vals


def firmware_config():
    return p.config_from_params(load_yaml_flat('firmware_config.yaml', 'firmware_config.trial.yaml'))


def bridge_settings():
    v = load_yaml_flat('vehicle_bridge.yaml', 'vehicle_bridge.trial.yaml')
    return BridgeSettings(v['joystick_timeout_s'], v['send_period_s'])


class CodecTests(unittest.TestCase):
    def test_crc_check_value(self):
        self.assertEqual(p.crc16(b'123456789'), 0x29B1)

    def test_golden_vector(self):
        """TS-29 golden COMMAND: seq 3, sender_ms 12345678, token 0x0123ABCD, x -3750, y 6250, flags 1."""
        frame = p.encode_command(3, 12345678, TOKEN, -3750, 6250, 1)
        self.assertEqual(frame.hex(), GOLDEN_COMMAND)
        frames = p.Parser().feed(frame)
        self.assertEqual(len(frames), 1); f = frames[0]
        self.assertEqual((f.kind, f.seq, f.sender_ms), (p.COMMAND, 3, 12345678))
        self.assertEqual(p.decode_command(f.payload), {'boot_token': TOKEN, 'x_q10000': -3750, 'y_q10000': 6250, 'flags': 1})

    def test_parser_rejects_and_resyncs(self):
        good = p.encode_command(1, 0, TOKEN, 0, 0, 1)
        bad_crc = bytearray(good); bad_crc[-1] ^= 0xFF
        bad_ver = bytearray(good); bad_ver[2] = 3
        pr = p.Parser()
        out = pr.feed(b'\x00\xa5' + bytes(bad_crc) + bytes(bad_ver) + b'garbage' + good)
        self.assertEqual(len(out), 1); self.assertGreaterEqual(pr.rejected, 2)
        # split delivery
        pr = p.Parser(); self.assertEqual(pr.feed(good[:7]), []); self.assertEqual(len(pr.feed(good[7:])), 1)

    def test_status_roundtrip(self):
        payload = p.STATUS_STRUCT.pack(2, 9, 0b111000, 3, 0, 0, -3750, 6250, -3750, 6250, 1200, 3900, 1045, 3398, 17, p.NEVER, 42, 123456, 0)
        d = p.decode_status(payload)
        self.assertEqual(d['source'], 'pc'); self.assertEqual(d['reason'], 'pc_control'); self.assertTrue(d['pc_enabled']); self.assertTrue(d['config_valid'])
        self.assertFalse(d['bt_connected']); self.assertEqual(d['bt_age_ms'], None); self.assertEqual(d['pc_age_ms'], 17); self.assertEqual(d['last_pc_seq'], 42)

    def test_config_from_generated_files(self):
        cfg = firmware_config()
        self.assertEqual(cfg['pc_command_watchdog_ms'], 1000, 'PRM-13 1.0 s -> ms'); self.assertEqual(cfg['bt_report_timeout_ms'], 250, 'PRM-21 0.25 s -> ms')
        self.assertTrue(sim.config_valid(cfg))
        approved_only = p.config_from_params(load_yaml_flat('firmware_config.yaml'))
        self.assertNotIn('dac_neutral_mv', approved_only, 'DAC values are unresolved (DEC-077): never filled in')
        self.assertFalse(sim.config_valid(approved_only))
        items = p.config_items(cfg); self.assertEqual(len(items), 10); self.assertEqual(p.decode_config_items(items), {k: cfg[k] for k in p.CONFIG_KEYS})

    def test_newer_sequence(self):
        self.assertTrue(p.newer_sequence(2, 1)); self.assertFalse(p.newer_sequence(1, 1)); self.assertFalse(p.newer_sequence(1, 2))
        self.assertTrue(p.newer_sequence(0, 0xFFFFFFFF)); self.assertFalse(p.newer_sequence(0x80000000, 0))


class BridgeCoreTests(unittest.TestCase):
    def setUp(self):
        self.s = bridge_settings(); self.core = BridgeCore(self.s)

    def test_relations_from_model(self):
        cfg = firmware_config()
        self.assertLessEqual(self.s.send_period_s, cfg['pc_command_watchdog_ms'] / 1000 / 5, 'PRM-14 <= PRM-13 / 5 (model condition)')
        self.assertGreater(self.s.joystick_timeout_s, self.s.send_period_s, 'PRM-09 > PRM-14')

    def test_inactive_sends_nothing(self):
        self.core.on_joystick(0.5, 0.0, 0.0)
        d = self.core.command(0.0, False); self.assertFalse(d.send); self.assertEqual(d.reason, REASON_INACTIVE)

    def test_active_sends_neutral_without_joystick(self):
        d = self.core.command(0.0, True); self.assertTrue(d.send); self.assertEqual((d.x_q10000, d.y_q10000), (0, 0)); self.assertEqual(d.flags, p.FLAG_PC_ENABLE_REQUEST); self.assertEqual(d.reason, REASON_JOY_NOT_RECEIVED)

    def test_forward_and_sign_mapping(self):
        self.core.on_joystick(0.625, 0.375, 0.0)     # forward 0.625, turn left 0.375
        d = self.core.command(0.01, True); self.assertEqual(d.reason, REASON_FORWARD)
        self.assertEqual((d.x_q10000, d.y_q10000), (-3750, 6250), 'x is right-positive: turn left -> negative x')

    def test_stale_joystick_is_neutral_and_never_resent(self):
        """TS-13: after joystick_command stops, the bridge keeps sending (caller's timer) but the value is neutral after PRM-09."""
        self.core.on_joystick(0.625, 0.375, 0.0)
        self.assertEqual(self.core.command(self.s.joystick_timeout_s, True).reason, REASON_FORWARD)
        d = self.core.command(self.s.joystick_timeout_s + 0.001, True)
        self.assertTrue(d.send); self.assertEqual((d.x_q10000, d.y_q10000), (0, 0)); self.assertEqual(d.reason, REASON_JOY_STALE)

    def test_hello_and_reboot_detection(self):
        self.assertTrue(self.core.on_hello_reply({'boot_token': 5, 'config_valid': True, 'config_generation': 1}))
        self.assertFalse(self.core.on_hello_reply({'boot_token': 5, 'config_valid': True, 'config_generation': 1}))
        self.assertFalse(self.core.on_status({'uptime_ms': 1000, 'config_valid': True})); self.assertTrue(self.core.on_status({'uptime_ms': 10, 'config_valid': False}))
        self.assertEqual(self.core.config_valid, False)


class FirmwareModelTests(unittest.TestCase):
    """Firmware rules against the Python model (the C++ host test repeats these with the same configuration)."""

    def setUp(self):
        self.cfg = firmware_config(); self.fw = sim.Esp32Sim(boot_token=TOKEN, config=dict(self.cfg)); self.fw.drain()
        self.seq = 0
        self.W = self.cfg['pc_command_watchdog_ms']; self.BT = self.cfg['bt_report_timeout_ms']; self.REL = self.cfg['manual_release_neutral_ms']
        self.neutral = (self.cfg['dac_neutral_mv'], self.cfg['dac_neutral_mv'])

    def cmd(self, now, x, y, flags=1, seq=None, token=TOKEN):
        if seq is None: self.seq += 1; seq = self.seq
        return self.fw.feed(p.encode_command(seq, now, token, x, y, flags), now)

    def applied(self, now):
        self.fw.tick(now); return self.fw.applied()

    def enable_pc(self, now=0):
        self.cmd(now, 0, 0); a = self.applied(now); self.assertTrue(self.fw.pc_enabled); return a

    def test_without_config_dac_is_not_written(self):
        fw = sim.Esp32Sim(boot_token=1, config=None)
        a = fw.applied(); self.assertEqual(a.source, sim.SRC_NONE); self.assertEqual(a.reason, sim.R_CONFIG_INVALID); self.assertIsNone(a.dac)
        approved_only = p.config_from_params(load_yaml_flat('firmware_config.yaml'))
        fw2 = sim.Esp32Sim(boot_token=1, config=approved_only); self.assertIsNone(fw2.applied().dac)

    def test_boot_is_neutral_and_pc_disabled(self):
        a = self.applied(0); self.assertEqual(a.source, sim.SRC_NONE); self.assertEqual(a.target_mv, self.neutral); self.assertFalse(self.fw.pc_enabled)

    def test_pc_enable_requires_neutral_command(self):
        self.cmd(0, 5000, 0); self.applied(0); self.assertFalse(self.fw.pc_enabled, 'a non-neutral first command does not enable the PC source')
        self.assertEqual(self.fw.applied().target_mv, self.neutral)
        self.enable_pc(10); self.cmd(20, 5000, 0); a = self.applied(20); self.assertEqual(a.source, sim.SRC_PC); self.assertNotEqual(a.target_mv, self.neutral)

    def test_ts19_pc_stale_after_watchdog_and_invalid_frames_do_not_extend(self):
        """TS-19: neutral PRM-13 after the LAST VALID frame; bad CRC / wrong token / replayed seq do not count."""
        self.enable_pc(0); self.cmd(100, 5000, 2000); self.assertEqual(self.applied(100).source, sim.SRC_PC)
        last_valid = 100
        t = last_valid + 1
        while t < last_valid + self.W + 200:
            bad = bytearray(p.encode_command(self.seq + 1, t, TOKEN, 5000, 2000, 1)); bad[-1] ^= 0xFF; self.fw.feed(bytes(bad), t)   # bad CRC
            self.fw.feed(p.encode_command(self.seq + 1, t, TOKEN ^ 1, 5000, 2000, 1), t)   # wrong boot token (does not consume a sequence)
            self.fw.feed(p.encode_command(self.seq, t, TOKEN, 5000, 2000, 1), t)   # replayed sequence
            a = self.applied(t)
            if t - last_valid < self.W:
                self.assertEqual(a.source, sim.SRC_PC, f'still PC at {t - last_valid} ms')
            else:
                self.assertEqual(a.source, sim.SRC_NONE, f'neutral at {t - last_valid} ms'); self.assertEqual(a.target_mv, self.neutral); self.assertFalse(self.fw.pc_enabled)
            t += 50
        self.assertIn(sim.E_PC_DISABLED_STALE, [e[0] for e in self.fw.events])
        # re-enable needs a neutral command again
        self.cmd(t, 5000, 0); self.assertFalse(self.fw.pc_enabled); self.cmd(t + 1, 0, 0); self.assertTrue(self.fw.pc_enabled)

    def test_ts17_manual_priority_and_return_after_release(self):
        """TS-17: while the gamepad stick is active, manual owns the DAC; PC returns only after PRM-48 of neutral."""
        self.fw.bt_connect(0); self.fw.bt_report(0, 0, 0)          # centered report after connect
        self.enable_pc(0); self.cmd(10, 5000, 0); self.assertEqual(self.applied(10).source, sim.SRC_PC)
        t = 20
        while t < 400:   # manual pushes forward, PC keeps commanding right turn
            self.fw.bt_report(0, 8000, t); self.cmd(t, 5000, 0); a = self.applied(t)
            self.assertEqual(a.source, sim.SRC_MANUAL); self.assertEqual(a.target_mv[0], self.cfg['dac_neutral_mv']); self.assertGreater(a.target_mv[1], self.cfg['dac_neutral_mv'])
            t += 20
        release_start = t
        while t < release_start + self.REL + 100:   # stick back to center, PC still commanding
            self.fw.bt_report(0, 0, t); self.cmd(t, 5000, 0); a = self.applied(t)
            if t - self.fw.last_manual_active_ms < self.REL:   # the wait starts when manual became inactive (last active tick)
                self.assertEqual(a.source, sim.SRC_NONE, 'no immediate switch to PC'); self.assertEqual(a.reason, sim.R_NEUTRAL_RECOVERY_WAIT); self.assertEqual(a.target_mv, self.neutral)
            else:
                self.assertEqual(a.source, sim.SRC_PC)
            t += 20
        self.assertGreaterEqual(t - release_start, self.REL, 'the release phase covered the whole wait')
        self.assertTrue(self.fw.pc_enabled, 'manual override does not clear the PC source enable')

    def test_ts18_bt_gap_invalidates_manual(self):
        """TS-18: BT report gap of PRM-21 -> manual invalid -> neutral, with and without PC commands; PC waits PRM-48."""
        for with_pc in (False, True):
            self.setUp()
            self.fw.bt_connect(0); self.fw.bt_report(0, 0, 0)
            if with_pc: self.enable_pc(0)
            t = 10
            while t < 200:
                self.fw.bt_report(6000, 0, t)
                if with_pc: self.cmd(t, 0, 5000)
                self.assertEqual(self.applied(t).source, sim.SRC_MANUAL); t += 10
            last_report = t - 10
            while t < last_report + self.BT + self.REL + 100:   # reports stop; PC keeps commanding when with_pc
                if with_pc: self.cmd(t, 0, 5000)
                a = self.applied(t)
                if t - last_report < self.BT:
                    self.assertEqual(a.source, sim.SRC_MANUAL, f'manual still valid at {t - last_report} ms')
                elif t - self.fw.last_manual_active_ms < self.REL:   # BT stale -> manual invalid -> neutral; PC waits PRM-48 from the last active tick
                    self.assertEqual(a.source, sim.SRC_NONE, f'neutral at {t - last_report} ms'); self.assertEqual(a.target_mv, self.neutral)
                    if with_pc: self.assertEqual(a.reason, sim.R_NEUTRAL_RECOVERY_WAIT)
                else:
                    self.assertEqual(a.source, sim.SRC_PC if with_pc else sim.SRC_NONE, f'at {t - last_report} ms')
                t += 10
            self.assertIn(sim.E_BT_STALE, [e[0] for e in self.fw.events])
            # a report after the gap must be centered before manual is accepted again
            self.fw.bt_report(6000, 0, t); self.applied(t); self.assertFalse(self.fw.centered); self.fw.bt_report(0, 0, t + 1); self.assertTrue(self.fw.centered)

    def test_bt_disconnect_is_neutral(self):
        self.fw.bt_connect(0); self.fw.bt_report(0, 0, 0); self.fw.bt_report(0, 9000, 10); self.assertEqual(self.applied(10).source, sim.SRC_MANUAL)
        self.fw.bt_disconnect(20); a = self.applied(20); self.assertEqual(a.source, sim.SRC_NONE); self.assertEqual(a.target_mv, self.neutral)

    def test_status_and_hello_reply_frames(self):
        out = self.fw.feed(p.encode_hello(1, 0, 77), 0)
        frames = p.Parser().feed(out); kinds = [f.kind for f in frames]; self.assertIn(p.HELLO_REPLY, kinds)
        r = p.decode_hello_reply(next(f for f in frames if f.kind == p.HELLO_REPLY).payload)
        self.assertEqual(r['boot_token'], TOKEN); self.assertTrue(r['config_valid']); self.assertEqual(r['session_id'], 77); self.assertEqual(r['protocol_version'], 4)
        out = self.fw.feed(p.encode_get(p.GET_STATUS, 2, 0, TOKEN), 0)
        st = [f for f in p.Parser().feed(out) if f.kind == p.STATUS]; self.assertEqual(len(st), 1)
        d = p.decode_status(st[0].payload); self.assertEqual(d['source'], 'none'); self.assertTrue(d['config_valid']); self.assertEqual(d['target_x_mv'], self.cfg['dac_neutral_mv'])
        # periodic STATUS at status_period_ms
        self.fw.drain(); n = 0
        for t in range(0, 1000, 10):
            n += sum(1 for f in p.Parser().feed(self.fw.tick(t)) if f.kind == p.STATUS)
        self.assertEqual(n, 1000 // self.cfg['status_period_ms'])

    def test_set_config_validation_and_generation(self):
        bad = dict(self.cfg); bad['dac_min_mv'] = bad['dac_max_mv']
        out = self.fw.feed(p.encode_set_config(1, 0, TOKEN, bad), 0)
        acks = [p.decode_ack(f.payload) for f in p.Parser().feed(out) if f.kind == p.ACK]; self.assertEqual(acks[-1]['result_name'], 'config_invalid'); self.assertEqual(self.fw.config, self.cfg)
        out = self.fw.feed(p.encode_set_config(2, 0, TOKEN, self.cfg), 0)
        acks = [p.decode_ack(f.payload) for f in p.Parser().feed(out) if f.kind == p.ACK]; self.assertEqual(acks[-1]['result_name'], 'accepted'); self.assertEqual(self.fw.config_generation, 1)
        out = self.fw.feed(p.encode_get(p.GET_CONFIG, 3, 0, TOKEN), 0)
        c = p.decode_config(next(f for f in p.Parser().feed(out) if f.kind == p.CONFIG).payload); self.assertEqual(c['dac_neutral_mv'], self.cfg['dac_neutral_mv']); self.assertEqual(c['config_generation'], 1)

    def test_voltage_mapping_matches_previous_firmware_table(self):
        n, lo, hi = self.cfg['dac_neutral_mv'], self.cfg['dac_min_mv'], self.cfg['dac_max_mv']
        self.assertEqual(sim.map_voltage(0, 0, n, lo, hi), (n, n))
        x, y = sim.map_voltage(1, 0, n, lo, hi); self.assertEqual(y, n); self.assertLessEqual(x, hi); self.assertGreater(x, hi - 5)
        x, y = sim.map_voltage(-1, 0, n, lo, hi); self.assertEqual(y, n); self.assertGreaterEqual(x, lo); self.assertLess(x, lo + 5)
        x, y = sim.map_voltage(1, 1, n, lo, hi); self.assertTrue(sim.inside_circle(x, y, lo, hi)); self.assertEqual(x, y)
        self.assertEqual(sim.dac_code(self.cfg['dac_full_scale_mv'], self.cfg['dac_full_scale_mv']), 4095)


if __name__ == '__main__':
    unittest.main()
