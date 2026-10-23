"""Unit tests of monitor_core (ND-02) without ROS. Design test: TS-25 (stage 5-2).

Checked: never show NOT_RECEIVED as OK; freshness verdict without an unresolved threshold; STALE vs RECEIVED when a
threshold exists; identical events keep count and last time; /config persists across reloads, keeps UNKNOWN, validates
values and bumps the revision; external displays and ESP32 report UNAVAILABLE / NOT_RECEIVED instead of invented data.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core.monitor_core import MOTION_COMPENSATION_FIELDS, NAV2_RECOVERY_FIELDS, MonitorCore, SensorConfig, freshness, Received, CONFIG_FIELDS  # noqa: E402
from gouda_core import monitor_core  # noqa: E402


class Clock:
    def __init__(self): self.t = 1000.0
    def __call__(self): return self.t


class MonitorCoreTests(unittest.TestCase):
    def setUp(self): self.clock = Clock(); self.core = MonitorCore(clock=self.clock)

    def test_nothing_received_is_not_ok(self):
        s = self.core.snapshot()
        self.assertEqual(s['mode']['freshness']['status'], 'NOT_RECEIVED'); self.assertEqual(s['mode']['name'], 'UNKNOWN')
        self.assertEqual(s['record']['freshness']['status'], 'NOT_RECEIVED'); self.assertEqual(s['esp32']['freshness']['status'], 'NOT_RECEIVED')
        self.assertEqual(s['external_displays']['navigation']['status'], 'UNAVAILABLE')
        self.assertEqual(s['nodes']['names'], []); self.assertIsNone(s['nodes']['at'])

    def test_freshness_without_threshold_reports_age_only(self):
        f = freshness(Received({}, 990.0), 1000.0, None)
        self.assertEqual(f.status, 'RECEIVED'); self.assertAlmostEqual(f.age_s, 10.0); self.assertIn('未確定', f.verdict)

    def test_freshness_with_threshold_distinguishes_stale(self):
        self.assertEqual(freshness(Received({}, 990.0), 1000.0, 20.0).status, 'RECEIVED')
        self.assertEqual(freshness(Received({}, 970.0), 1000.0, 20.0).status, 'STALE')

    def test_mode_snapshot_and_labels(self):
        self.core.on_mode({'mode': 4, 'state_revision': 6, 'initial_pose_required': True}); self.clock.t += 2.5
        s = self.core.snapshot()
        self.assertEqual(s['mode']['name'], 'PAUSE'); self.assertEqual(s['mode']['label'], '一時停止')
        self.assertAlmostEqual(s['mode']['freshness']['age_s'], 2.5); self.assertEqual(s['mode']['fields']['state_revision'], 6)

    def test_identical_events_keep_count_and_last_time(self):
        ev = {'node': 'gouda_mode_manager', 'event': 'human_request', 'transition_id': 'TR-06', 'reason': 'refused: x'}
        self.core.on_decision(ev, 1001.0); self.core.on_decision(dict(ev), 1005.0); self.core.on_decision({**ev, 'reason': 'other'}, 1006.0)
        s = self.core.snapshot()['events']
        self.assertEqual(len(s), 2); self.assertEqual(s[0]['reason'], 'other')
        agg = next(x for x in s if x['reason'] == 'refused: x'); self.assertEqual(agg['count'], 2); self.assertEqual(agg['last_at'], 1005.0); self.assertEqual(agg['first_at'], 1001.0)

    def test_event_buffer_is_bounded(self):
        core = MonitorCore(clock=self.clock, max_events=3)
        for i in range(5): core.on_decision({'node': 'n', 'event': f'e{i}', 'transition_id': '', 'reason': ''})
        self.assertEqual(len(core.snapshot()['events']), 3)

    def test_revision_changes_on_input(self):
        r0 = self.core.connection_revision; self.core.on_record({'log_active': 'False'}); self.assertGreater(self.core.connection_revision, r0)


class GnssDisplayTests(unittest.TestCase):
    """REV-061 (DEC-123): the GNSS row is display only; the mapping-start warning stays about GLIM's inputs (DEC-088)."""

    def test_gnss_row_and_detail(self):
        c = MonitorCore(clock=Clock())
        snap = c.sensors_snapshot()
        self.assertEqual(snap['gnss']['status'], 'NOT_RECEIVED'); self.assertEqual(snap['gnss']['detail'], '')
        c.on_gnss_detail('quality', monitor_core.gnss_quality_text(4, 21, 1))
        c.on_gnss_detail('attitude', monitor_core.gnss_attitude_text(2, 87.25))
        detail = c.sensors_snapshot()['gnss']['detail']
        self.assertIn('RTK fix', detail); self.assertIn('衛星 21', detail); self.assertIn('0.01 m', detail); self.assertIn('87.2', detail)

    def test_quality_and_attitude_texts(self):
        self.assertTrue(monitor_core.gnss_quality_text(0x85, 9, 0xFFFF).startswith('RTK float'))   # upper bits are flags
        self.assertNotIn('水平精度', monitor_core.gnss_quality_text(1, 9, 0xFFFF))                      # do-not-use accuracy is not shown
        self.assertIn('不明（9）', monitor_core.gnss_quality_text(9, 0, None))
        self.assertEqual(monitor_core.gnss_attitude_text(0, 12.0), '向きなし')
        self.assertNotIn('heading', monitor_core.gnss_attitude_text(2, -2e10))

    def test_mapping_start_warning_ignores_gnss(self):
        c = MonitorCore(clock=Clock())
        c.on_sensor('points', c.clock()); c.on_sensor('imu', c.clock())
        self.assertIsNone(c.mapping_start_warning())


class SensorConfigTests(unittest.TestCase):
    def test_defaults_are_unknown_and_persist_across_reload(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'config' / 'sensor_config.json'
            c = SensorConfig(p)
            self.assertTrue(all(v == 'UNKNOWN' for v in c.values.values())); self.assertEqual(c.config_revision, 0)
            ok, msg = c.update({'lidar_mount_z_m': '0.95', 'lidar_axis_mapping': '-y forward, +x right, +z up'}, 1234.0)
            self.assertTrue(ok, msg); self.assertEqual(c.config_revision, 1); self.assertEqual(c.values['lidar_mount_z_m'], 0.95)
            c2 = SensorConfig(p)   # reload (tab change / page reload / node restart)
            self.assertEqual(c2.values['lidar_mount_z_m'], 0.95); self.assertEqual(c2.values['imu_mount_x_m'], 'UNKNOWN'); self.assertEqual(c2.config_revision, 1)
            self.assertEqual(c2.snapshot()['unknown_count'], len(CONFIG_FIELDS) - 2)

    def test_invalid_values_are_refused_as_a_whole(self):
        with tempfile.TemporaryDirectory() as d:
            c = SensorConfig(Path(d) / 'cfg.json')
            ok, msg = c.update({'lidar_mount_x_m': 'abc'}, 10.0); self.assertFalse(ok); self.assertIn('not a number', msg); self.assertEqual(c.config_revision, 0)
            ok, msg = c.update({'no_such_field': 1}, 10.0); self.assertFalse(ok); self.assertIn('unknown config field', msg)
            ok, msg = c.update({'imu_mount_y_m': ''}, 10.0); self.assertTrue(ok); self.assertEqual(c.values['imu_mount_y_m'], 'UNKNOWN')

    def test_unreadable_file_is_treated_as_empty(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'cfg.json'; p.write_text('{broken')
            c = SensorConfig(p); self.assertEqual(c.config_revision, 0); self.assertTrue(all(v == 'UNKNOWN' for v in c.values.values()))


class MotionCompensationConfigTests(unittest.TestCase):
    """/config 「自律走行の出力」 (REV-118, DEC-181, IFD-52, TS-40): its own file, values are stick amounts in [0, 1)."""

    def test_saved_values_persist_in_their_own_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'config' / 'motion_compensation.json'
            c = SensorConfig(p, MOTION_COMPENSATION_FIELDS)
            self.assertEqual(list(c.values), list(MOTION_COMPENSATION_FIELDS)); self.assertTrue(all(v == 'UNKNOWN' for v in c.values.values()))
            ok, msg = c.update({'forward_min': '0.2', 'forward_threshold': '0'}, 5.0); self.assertTrue(ok, msg)
            c2 = SensorConfig(p, MOTION_COMPENSATION_FIELDS)
            self.assertEqual((c2.values['forward_min'], c2.values['forward_threshold'], c2.values['turn_min']), (0.2, 0.0, 'UNKNOWN'))
            self.assertEqual(c2.config_revision, 1)
            self.assertFalse((Path(d) / 'config' / 'sensor_config.json').exists(), 'the sensor /config is not touched')

    def test_out_of_range_and_sensor_fields_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            c = SensorConfig(Path(d) / 'mc.json', MOTION_COMPENSATION_FIELDS)
            for bad in ('1', '1.5', '-0.1', 'nan', 'inf'):
                ok, msg = c.update({'reverse_min': bad}, 1.0); self.assertFalse(ok, bad)
            self.assertEqual(c.config_revision, 0)
            ok, msg = c.update({'lidar_mount_x_m': '0.1'}, 1.0); self.assertFalse(ok); self.assertIn('unknown config field', msg)
            ok, msg = c.update({'turn_threshold': '0.05', 'turn_min': ''}, 2.0); self.assertTrue(ok, msg); self.assertEqual(c.values['turn_min'], 'UNKNOWN')

    def test_out_of_range_value_on_disk_is_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'mc.json'; p.write_text('{"values": {"forward_min": 2, "turn_min": 0.3}, "config_revision": 7}')
            c = SensorConfig(p, MOTION_COMPENSATION_FIELDS)
            self.assertEqual(c.values['forward_min'], 'UNKNOWN', 'out of range on disk -> UNKNOWN'); self.assertEqual(c.values['turn_min'], 0.3)


class Nav2RecoveryConfigTests(unittest.TestCase):
    """/config 「Nav2」 (REV-132, DEC-209, IFD-54, TS-45): a whole number from 1 to the upper limit (PRM-18); nothing without a limit."""
    KEY = 'recovery_number_of_retries'

    def test_whole_numbers_within_the_limits_only(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'nav2_recovery.json'
            c = SensorConfig(p, NAV2_RECOVERY_FIELDS, {self.KEY: (1, 9999999)})
            for bad in ('0', '-3', '10000000', '2.5', 'many', 'nan'):
                ok, msg = c.update({self.KEY: bad}, 1.0); self.assertFalse(ok, bad)
            self.assertEqual(c.config_revision, 0)
            for good, want in (('1', 1), ('9999999', 9999999), ('12.0', 12)):
                ok, msg = c.update({self.KEY: good}, 2.0); self.assertTrue(ok, msg); self.assertEqual(c.values[self.KEY], want)
            c2 = SensorConfig(p, NAV2_RECOVERY_FIELDS, {self.KEY: (1, 9999999)})
            self.assertEqual((c2.values[self.KEY], c2.config_revision), (12, 3))
            ok, msg = c.update({self.KEY: ''}, 3.0); self.assertTrue(ok, msg); self.assertEqual(c.values[self.KEY], 'UNKNOWN')

    def test_inflate_around_unknown_is_true_or_false(self):
        """REV-134 (DEC-217): the tab's boolean overrides PRM-98."""
        with tempfile.TemporaryDirectory() as d:
            c = SensorConfig(Path(d) / 'n.json', NAV2_RECOVERY_FIELDS, {self.KEY: (1, 9999999)})
            for bad in ('yes', '1', '0.5'):
                ok, msg = c.update({'inflate_around_unknown': bad}, 1.0); self.assertFalse(ok, bad)
            ok, msg = c.update({'inflate_around_unknown': 'True'}, 2.0); self.assertTrue(ok, msg); self.assertIs(c.values['inflate_around_unknown'], True)
            ok, msg = c.update({'inflate_around_unknown': 'false'}, 3.0); self.assertTrue(ok, msg); self.assertIs(c.values['inflate_around_unknown'], False)
            ok, msg = c.update({'inflate_around_unknown': ''}, 4.0); self.assertTrue(ok, msg); self.assertEqual(c.values['inflate_around_unknown'], 'UNKNOWN')

    def test_replan_rate_is_a_number_above_zero(self):
        """REV-167 (DEC-347): the tab's replanning rate overrides PRM-103."""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'n.json'
            c = SensorConfig(p, NAV2_RECOVERY_FIELDS, {self.KEY: (1, 9999999)})
            for bad in ('0', '-1', 'fast', 'nan', 'inf', True):
                ok, msg = c.update({'replan_rate_hz': bad}, 1.0); self.assertFalse(ok, bad)
            self.assertEqual(c.config_revision, 0)
            ok, msg = c.update({'replan_rate_hz': '2'}, 2.0); self.assertTrue(ok, msg); self.assertEqual(c.values['replan_rate_hz'], 2.0)
            ok, msg = c.update({'replan_rate_hz': '0.5'}, 3.0); self.assertTrue(ok, msg); self.assertEqual(c.values['replan_rate_hz'], 0.5)
            self.assertEqual(SensorConfig(p, NAV2_RECOVERY_FIELDS, {self.KEY: (1, 9999999)}).values['replan_rate_hz'], 0.5)
            ok, msg = c.update({'replan_rate_hz': ''}, 4.0); self.assertTrue(ok, msg); self.assertEqual(c.values['replan_rate_hz'], 'UNKNOWN')

    def test_nothing_is_saved_without_the_upper_limit(self):
        with tempfile.TemporaryDirectory() as d:
            c = SensorConfig(Path(d) / 'n.json', NAV2_RECOVERY_FIELDS)   # PRM-18 unresolved
            ok, msg = c.update({self.KEY: '5'}, 1.0); self.assertFalse(ok); self.assertIn('PRM-18', msg)


if __name__ == '__main__': unittest.main()
