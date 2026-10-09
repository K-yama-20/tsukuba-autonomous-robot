"""Unit tests of mode_core (ND-03 boot transitions) without ROS. Design test: TS-24 (stage 5-1).

Checked: TR-01 (no record / manual -> manual), TR-02 (autonomy / mapping / pause -> pause, no autonomy re-permission,
initial pose required: DEC-009, human pause/end flag preserved: RQ-I025), state_revision monotonic (IFD-01), unreadable
record treated as no record, atomic persistence.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import mode_core as mc  # noqa: E402


class ModeCoreTests(unittest.TestCase):
    def test_four_modes_only(self):
        self.assertEqual(len(mc.MODES), 4); self.assertEqual(sorted(mc.MODE_CODES.values()), [1, 2, 3, 4])

    def test_boot_without_record_is_manual(self):
        d = mc.decide_boot(None)
        self.assertEqual(d.transition_id, 'TR-01'); self.assertEqual(d.state.mode, mc.MODE_MANUAL)
        self.assertFalse(d.record_found); self.assertFalse(d.state.initial_pose_required); self.assertEqual(d.state.state_revision, 1)

    def test_boot_after_manual_is_manual(self):
        d = mc.decide_boot(mc.PreviousModeRecord(mode=mc.MODE_MANUAL, state_revision=7))
        self.assertEqual(d.transition_id, 'TR-01'); self.assertEqual(d.state.mode, mc.MODE_MANUAL); self.assertEqual(d.state.state_revision, 8)

    def test_boot_after_autonomy_mapping_pause_is_pause_without_resume(self):
        for prev in (mc.MODE_AUTONOMY, mc.MODE_MAPPING, mc.MODE_PAUSE):
            d = mc.decide_boot(mc.PreviousModeRecord(mode=prev, run_id='run-7', state_revision=3))
            self.assertEqual(d.transition_id, 'TR-02', prev); self.assertEqual(d.state.mode, mc.MODE_PAUSE)
            self.assertTrue(d.state.initial_pose_required)          # DEC-009: resume only after a human initial pose request
            self.assertEqual(d.state.run_id, 'run-7'); self.assertEqual(d.state.previous_mode, prev)
            self.assertEqual(d.state.state_revision, 4)
            self.assertIn('not re-permitted', d.reason)

    def test_human_pause_or_end_flag_survives_restart(self):
        d = mc.decide_boot(mc.PreviousModeRecord(mode=mc.MODE_PAUSE, human_pause_or_end=True))
        self.assertTrue(d.state.human_pause_or_end_recorded)
        self.assertTrue(mc.record_after_boot(d).human_pause_or_end)
        d2 = mc.decide_boot(mc.PreviousModeRecord(mode=mc.MODE_MANUAL, human_pause_or_end=True))
        self.assertTrue(d2.state.human_pause_or_end_recorded)

    def test_record_roundtrip_and_unreadable_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'state' / 'previous_mode_record.json'
            self.assertIsNone(mc.PreviousModeRecord.load(p))
            mc.PreviousModeRecord(mode=mc.MODE_AUTONOMY, human_pause_or_end=False, run_id='r1', state_revision=12).save(p)
            r = mc.PreviousModeRecord.load(p)
            self.assertEqual((r.mode, r.human_pause_or_end, r.run_id, r.state_revision), (mc.MODE_AUTONOMY, False, 'r1', 12))
            self.assertFalse(p.with_suffix('.json.tmp').exists())
            p.write_text('{"mode": "unknown"}')
            self.assertIsNone(mc.PreviousModeRecord.load(p))
            p.write_text('not json')
            self.assertIsNone(mc.PreviousModeRecord.load(p))

    def test_state_revision_never_decreases_across_boots(self):
        rec = None; last = 0
        for _ in range(3):
            d = mc.decide_boot(rec); self.assertGreater(d.state.state_revision, last); last = d.state.state_revision
            rec = mc.record_after_boot(d)


class HumanRequestTests(unittest.TestCase):
    """Stage 5-2: the mode operation services are evaluated against the transition table and guards."""
    def test_wrong_mode_is_refused_with_reason(self):
        s = mc.decide_boot(None).state
        for ev in ('pause', 'resume', 'end_autonomy', 'end_mapping'):
            r = mc.request_transition(ev, s); self.assertFalse(r.accepted, ev); self.assertIn('not accepted in mode manual', r.reason)

    def test_unimplemented_transition_is_refused_with_stage(self):
        s = mc.decide_boot(None).state
        r = mc.request_transition('start_mapping', s); self.assertFalse(r.accepted); self.assertEqual(r.transition_id, 'TR-03'); self.assertIn('5-3', r.reason)
        r = mc.request_transition('start_autonomy', s); self.assertFalse(r.accepted); self.assertEqual(r.transition_id, 'TR-05'); self.assertIn('5-6', r.reason)

    def test_resume_requires_initial_pose_after_restart(self):
        s = mc.decide_boot(mc.PreviousModeRecord(mode=mc.MODE_AUTONOMY)).state
        self.assertEqual(s.mode, mc.MODE_PAUSE); self.assertTrue(s.initial_pose_required)
        r = mc.request_transition('resume', s, frozenset({'TR-10'})); self.assertFalse(r.accepted); self.assertIn('DEC-009', r.reason)

    def test_implemented_transition_changes_mode_and_revision(self):
        s = mc.decide_boot(None).state
        r = mc.request_transition('start_mapping', s, frozenset({'TR-03'}))
        self.assertTrue(r.accepted); self.assertEqual(r.new_state.mode, mc.MODE_MAPPING); self.assertEqual(r.new_state.previous_mode, mc.MODE_MANUAL)
        self.assertEqual(r.new_state.state_revision, s.state_revision + 1)
        self.assertEqual(s.mode, mc.MODE_MANUAL)  # input state is not mutated

    def test_end_autonomy_from_pause_maps_to_tr12(self):
        s = mc.ModeState(mode=mc.MODE_PAUSE, state_revision=3)
        r = mc.request_transition('end_autonomy', s); self.assertEqual(r.transition_id, 'TR-12')
        r = mc.request_transition('end_autonomy', mc.ModeState(mode=mc.MODE_AUTONOMY)); self.assertEqual(r.transition_id, 'TR-11')


if __name__ == '__main__': unittest.main()
