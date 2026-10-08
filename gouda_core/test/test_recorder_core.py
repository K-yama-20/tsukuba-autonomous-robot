"""Unit tests of RecorderCore (ND-04) without ROS. Design tests: TS-23 (stage 5-1).

Checked requirements: RQ-I015 (auto-start only by map start / autonomy start; boot, recovery, resume never start; failure never
raises; gaps recorded), RQ-I016 (rosbag independent, human only, same session dir with separate folders), RQ-I017 (a
human-started log is not stopped automatically), RQ-I034 (gap ranges).
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core.recorder_core import (RecorderCore, TRIGGER_HUMAN, TRIGGER_AUTO_MAP_START, TRIGGER_AUTO_AUTONOMY_START)  # noqa: E402


class FakeClock:
    def __init__(self): self.t = 100.0
    def __call__(self): return self.t
    def advance(self, dt): self.t += dt


class RecorderCoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.clock = FakeClock(); self.bag_calls = []
        self.core = RecorderCore(self.root, clock=self.clock, rosbag_start=lambda d: self.bag_calls.append(('start', d)),
                                 rosbag_stop=lambda: self.bag_calls.append(('stop',)), session_id_factory=lambda: 'S1')

    def tearDown(self): self.tmp.cleanup()

    def test_nothing_recorded_at_boot(self):
        st = self.core.status()
        self.assertFalse(st['log_active']); self.assertFalse(st['rosbag_active']); self.assertEqual(st['session_dir'], '')
        self.assertFalse(self.core.record('input', 'mode/state', self.clock(), {'mode': 1}))

    def test_boot_recovery_resume_never_auto_start(self):
        for ev in ('boot', 'fault_recovery', 'resume', 'monitor_reconnect', 'pc_restart'):
            self.assertFalse(self.core.auto_start_allowed(ev), ev)
            ok, msg = self.core.start_log(ev); self.assertFalse(ok, msg)
        self.assertTrue(self.core.auto_start_allowed(TRIGGER_AUTO_MAP_START))
        self.assertTrue(self.core.auto_start_allowed(TRIGGER_AUTO_AUTONOMY_START))

    def test_log_and_rosbag_are_independent_and_share_session_dir(self):
        ok, _ = self.core.start_log(TRIGGER_HUMAN); self.assertTrue(ok)
        st = self.core.status(); self.assertTrue(st['log_active']); self.assertFalse(st['rosbag_active'])
        ok, _ = self.core.start_rosbag(TRIGGER_HUMAN); self.assertTrue(ok)
        self.assertEqual(self.bag_calls, [('start', self.root / 'S1' / 'rosbag')])
        self.assertTrue((self.root / 'S1' / 'log').is_dir()); self.assertTrue((self.root / 'S1' / 'rosbag').is_dir())
        ok, _ = self.core.stop_log(TRIGGER_HUMAN); self.assertTrue(ok)
        st = self.core.status(); self.assertFalse(st['log_active']); self.assertTrue(st['rosbag_active'])
        ok, _ = self.core.stop_rosbag(TRIGGER_HUMAN); self.assertTrue(ok); self.assertEqual(self.bag_calls[-1], ('stop',))

    def test_rosbag_is_never_auto_started(self):
        for trig in (TRIGGER_AUTO_MAP_START, TRIGGER_AUTO_AUTONOMY_START, 'boot'):
            ok, _ = self.core.start_rosbag(trig); self.assertFalse(ok)
        self.assertEqual(self.bag_calls, [])

    def test_human_started_log_not_stopped_automatically(self):
        self.core.start_log(TRIGGER_HUMAN)
        ok, msg = self.core.stop_log('auto:map_end'); self.assertFalse(ok, msg)
        self.assertTrue(self.core.status()['log_active'])
        ok, _ = self.core.stop_log(TRIGGER_HUMAN); self.assertTrue(ok)

    def test_auto_started_log_is_stopped_by_auto_stop_and_status_reports_trigger(self):
        self.core.start_log(TRIGGER_AUTO_AUTONOMY_START)
        self.assertEqual(self.core.status()['auto_started_by'], TRIGGER_AUTO_AUTONOMY_START)
        ok, _ = self.core.stop_log('auto:autonomy_end'); self.assertTrue(ok)
        self.assertFalse(self.core.status()['log_active'])

    def test_gap_ranges_recorded_for_stopped_period(self):
        self.core.start_log(TRIGGER_HUMAN); self.clock.advance(5)
        self.core.stop_log(TRIGGER_HUMAN); self.clock.advance(7)
        self.assertIn('stopped', self.core.status()['last_gap']); self.assertIn('open', self.core.status()['last_gap'])
        self.core.start_log(TRIGGER_HUMAN)
        gaps = [json.loads(l) for l in (self.root / 'S1' / 'log' / 'gaps.jsonl').read_text().splitlines()]
        self.assertEqual(len(gaps), 1); self.assertEqual(gaps[0]['kind'], 'stopped')
        self.assertAlmostEqual(gaps[0]['end'] - gaps[0]['start'], 7)

    def test_only_received_values_are_written(self):
        self.core.start_log(TRIGGER_HUMAN)
        self.assertTrue(self.core.record('input', 'mode/state', 101.5, {'mode': 1, 'state_revision': 3}))
        events = [json.loads(l) for l in (self.root / 'S1' / 'log' / 'events.jsonl').read_text().splitlines()]
        kinds = [e['kind'] for e in events]; self.assertEqual(kinds, ['record_start', 'input'])
        self.assertEqual(events[1]['t'], 101.5); self.assertEqual(events[1]['data'], {'mode': 1, 'state_revision': 3})

    def test_write_failure_is_reported_as_gap_and_does_not_raise(self):
        self.core.start_log(TRIGGER_HUMAN)
        events = self.root / 'S1' / 'log' / 'events.jsonl'
        os.chmod(events, 0o400)   # make appends to the existing log file fail
        try:
            self.assertFalse(self.core.record('input', 'x', self.clock(), {'a': 1}))
            st = self.core.status(); self.assertGreaterEqual(st['failures'], 1); self.assertIn('failure', st['last_gap'])
            self.assertTrue(st['log_active'])   # recording failure never stops anything (RQ-I015)
        finally:
            os.chmod(events, 0o600)
        self.assertTrue(self.core.record('input', 'x', self.clock(), {'a': 2}))   # recovered: failure gap closed
        self.assertNotIn('open', self.core.status()['last_gap'])

    def test_rosbag_start_failure_is_reported_not_raised(self):
        def boom(d): raise RuntimeError('ros2 bag missing')
        core = RecorderCore(self.root, clock=self.clock, rosbag_start=boom, session_id_factory=lambda: 'S2')
        ok, msg = core.start_rosbag(TRIGGER_HUMAN); self.assertFalse(ok); self.assertIn('ros2 bag missing', msg)
        self.assertFalse(core.status()['rosbag_active']); self.assertEqual(core.status()['failures'], 1)


if __name__ == '__main__': unittest.main()
