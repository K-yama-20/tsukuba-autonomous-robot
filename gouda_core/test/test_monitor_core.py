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
from gouda_core.monitor_core import MonitorCore, SensorConfig, freshness, Received, CONFIG_FIELDS  # noqa: E402


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


if __name__ == '__main__': unittest.main()
