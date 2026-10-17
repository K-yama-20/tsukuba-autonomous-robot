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
        self.assertEqual(self.bag_calls, [('start', self.root / 'S1' / 'rosbag' / 'bag_01')])   # one folder per start (G-REC-ROSBAG-RESTART)
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
        ok, msg = self.core.stop_auto(); self.assertTrue(ok); self.assertIn('手動開始のため停止しない', msg)   # no-op is the intended outcome
        self.assertTrue(self.core.status()['log_active']); self.assertEqual(self.core.status()['log_started_by'], TRIGGER_HUMAN)
        ok, _ = self.core.stop_log(TRIGGER_HUMAN); self.assertTrue(ok)

    def test_duplicate_start_keeps_origin_and_answers_recording(self):
        self.core.start_log(TRIGGER_HUMAN)
        ok, msg = self.core.start_log(TRIGGER_AUTO_MAP_START); self.assertTrue(ok); self.assertIn('記録中', msg)
        self.assertEqual(self.core.status()['log_started_by'], TRIGGER_HUMAN)      # not relabelled as auto-started
        self.assertEqual(self.core.status()['auto_started_by'], '')
        events = [json.loads(l)['kind'] for l in (self.root / 'S1' / 'log' / 'events.jsonl').read_text().splitlines()]
        self.assertEqual(events.count('record_start'), 1)

    def test_stop_auto_stops_only_auto_started_log(self):
        self.core.start_log(TRIGGER_AUTO_MAP_START)
        self.assertEqual(self.core.status()['auto_started_by'], TRIGGER_AUTO_MAP_START)
        ok, _ = self.core.stop_auto(); self.assertTrue(ok); self.assertFalse(self.core.status()['log_active'])
        ok, msg = self.core.stop_auto(); self.assertTrue(ok); self.assertIn('not active', msg)

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

    def test_last_received_state_is_written_as_snapshot_when_log_starts(self):
        # mode/state arrived (transient_local) before the human pressed Record: it is not recorded then (log inactive),
        # but when the log starts the last received value is written as a snapshot with its original receive time.
        self.assertFalse(self.core.record('input', 'mode/state', 90.0, {'mode': 1, 'state_revision': 1}))
        self.core.start_log(TRIGGER_HUMAN)
        events = [json.loads(l) for l in (self.root / 'S1' / 'log' / 'events.jsonl').read_text().splitlines()]
        self.assertEqual([e['kind'] for e in events], ['record_start', 'snapshot'])
        self.assertEqual(events[1]['topic'], 'mode/state'); self.assertEqual(events[1]['t'], 90.0); self.assertEqual(events[1]['data']['mode'], 1)
        self.assertEqual(events[1]['written_at'], self.clock())

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


    # ---- G-REC-ROSBAG-RESTART: a rosbag restart in the same session was silently lost (2026-10-14, origin 181044) ----
    def test_rosbag_restart_in_same_session_writes_a_new_folder(self):
        self.core.start_rosbag(TRIGGER_HUMAN); self.clock.advance(5); self.core.stop_rosbag(TRIGGER_HUMAN)
        self.clock.advance(2); ok, msg = self.core.start_rosbag(TRIGGER_HUMAN); self.assertTrue(ok, msg)
        starts = [c[1] for c in self.bag_calls if c[0] == 'start']
        self.assertEqual(starts, [self.root / 'S1' / 'rosbag' / 'bag_01', self.root / 'S1' / 'rosbag' / 'bag_02'])
        self.assertIn('bag_02', msg); self.assertTrue(self.core.status()['rosbag_output'].endswith('bag_02'))
        outs = json.loads((self.root / 'S1' / 'session.json').read_text())['rosbag_outputs']
        self.assertEqual([o['result'] for o in outs], ['stopped', 'recording']); self.assertEqual(outs[0]['stopped_at'], 105.0)

    def test_rosbag_start_skips_an_existing_folder(self):
        (self.root / 'S1' / 'rosbag' / 'bag_01').mkdir(parents=True)
        self.core.start_rosbag(TRIGGER_HUMAN)
        self.assertEqual(self.bag_calls[-1], ('start', self.root / 'S1' / 'rosbag' / 'bag_02'))

    def test_rosbag_exit_without_stop_request_is_reported_and_logged(self):
        self.core.start_log(TRIGGER_HUMAN); self.core.start_rosbag(TRIGGER_HUMAN); self.clock.advance(1)
        ok, msg = self.core.rosbag_exited(1, "last output: Output folder 'bag_01' already exists.")
        self.assertTrue(ok); self.assertIn('exit code 1', msg)
        st = self.core.status()
        self.assertFalse(st['rosbag_active']); self.assertEqual(st['failures'], 1); self.assertIn('already exists', st['last_failure'])
        self.assertEqual(st['rosbag_output'], '')
        sj = json.loads((self.root / 'S1' / 'session.json').read_text())
        self.assertEqual(sj['failures'][-1]['what'], 'rosbag_exited'); self.assertEqual(sj['rosbag_outputs'][-1]['result'], 'failed')
        events = [json.loads(l) for l in (self.root / 'S1' / 'log' / 'events.jsonl').read_text().splitlines()]
        self.assertEqual(events[-1]['kind'], 'record_failure'); self.assertEqual(events[-1]['what'], 'rosbag_exited')
        ok, _ = self.core.start_rosbag(TRIGGER_HUMAN); self.assertTrue(ok)   # the human can record again, into a new folder
        self.assertEqual(self.bag_calls[-1], ('start', self.root / 'S1' / 'rosbag' / 'bag_02'))

    def test_rosbag_exit_after_a_stop_request_is_not_a_failure(self):
        self.core.start_rosbag(TRIGGER_HUMAN); self.core.stop_rosbag(TRIGGER_HUMAN)
        ok, _ = self.core.rosbag_exited(0); self.assertFalse(ok)
        self.assertEqual(self.core.status()['failures'], 0); self.assertEqual(self.core.status()['last_failure'], '')


if __name__ == '__main__': unittest.main()
