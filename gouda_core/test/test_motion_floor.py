"""Unit tests of the dead-band floor of motion_core (ND-11, REV-285, DEC-507) without ROS.

Every branch of the floor (0 -> neutral, below V_move / 2 -> neutral, V_move / 2 .. V_move -> the move stick, from V_move the
table), the hysteresis around V_move / 2 (no chatter), the turn axis, the reverse axis, the reset on the neutral reasons and on a
sign change, the DEC-171 compensation per direction, the feedback layer's targets, and that nothing changes without PRM-166.
The table, the limits and the hysteresis are read from the generated parameter file (PRM-150..160, PRM-39/40/78, PRM-166)."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gouda_core.motion_core import (MotionCore, MotionSettings, Compensation, Feedback, MODE_FLOOR, MODE_OFF,  # noqa: E402
                                    FLOOR_ZERO, FLOOR_LOW, FLOOR_MOVE, FLOOR_TABLE, FLOOR_COMPENSATION)
from test_motion_feedback import load_values, feedforward_from  # noqa: E402


class FloorTests(unittest.TestCase):
    def setUp(self):
        self.v = load_values()
        self.h = self.v['floor_hysteresis_mps']
        self.s = MotionSettings(self.v['cmd_vel_timeout_s'], self.v['max_linear_speed_mps'], self.v['max_angular_speed_radps'],
                                self.v['motion_hold_timeout_s'], self.v['max_reverse_speed_mps'])
        self.ff = feedforward_from(self.v)
        self.core = MotionCore(self.s, self.ff, self.h)
        self.core.on_motion_hold(False, '', 2, 0.0)
        self.t = 0.0
        self.vm = self.ff.forward.min_speed

    def out(self, vx, wz=0.0):
        self.t += 0.05
        self.core.on_motion_hold(False, '', 2, self.t)
        self.core.on_cmd_vel(vx, wz, self.t)
        return self.core.output(self.t)

    def test_branches_forward(self):
        o = self.out(0.0); self.assertEqual((o.forward, o.floor_forward, o.feedback_mode), (0.0, FLOOR_ZERO, MODE_FLOOR)); self.assertTrue(o.neutral)
        o = self.out(self.vm / 2 - self.h); self.assertEqual((o.forward, o.floor_forward), (0.0, FLOOR_LOW)); self.assertTrue(o.neutral)
        o = self.out(self.vm / 2 + self.h); self.assertEqual(o.floor_forward, FLOOR_MOVE)
        self.assertAlmostEqual(o.forward, self.ff.forward.move_stick)
        o = self.out(self.vm * 0.9); self.assertAlmostEqual(o.forward, self.ff.forward.move_stick)
        o = self.out(self.vm); self.assertEqual(o.floor_forward, FLOOR_TABLE); self.assertAlmostEqual(o.forward, self.ff.forward.move_stick)
        o = self.out(0.5); self.assertEqual(o.floor_forward, FLOOR_TABLE); self.assertAlmostEqual(o.forward, self.ff.forward.stick(0.5))
        self.assertGreater(o.forward, self.ff.forward.move_stick)
        o = self.out(self.v['max_linear_speed_mps'] * 2); self.assertEqual(o.forward, 1.0)

    def test_hysteresis_no_chatter(self):
        half = self.vm / 2
        self.assertEqual(self.out(half).floor_forward, FLOOR_LOW, 'from neutral the threshold is V_move/2 + h/2')
        self.assertEqual(self.out(half + self.h / 2).floor_forward, FLOOR_MOVE)
        seq = [half + d for d in (self.h * 0.4, -self.h * 0.4, self.h * 0.4, -self.h * 0.4)]
        self.assertEqual([self.out(v).floor_forward for v in seq], [FLOOR_MOVE] * 4, 'hovering at the threshold stays moving')
        self.assertEqual(self.out(half - self.h / 2 - 1e-6).floor_forward, FLOOR_LOW)
        self.assertEqual([self.out(v).floor_forward for v in seq], [FLOOR_LOW] * 4, 'and stays neutral once stopped')

    def test_reverse_and_sign_change(self):
        vr = self.ff.reverse.min_speed
        o = self.out(-vr * 0.9); self.assertEqual(o.floor_forward, FLOOR_MOVE); self.assertAlmostEqual(o.forward, -self.ff.reverse.move_stick)
        o = self.out(-0.3); self.assertAlmostEqual(o.forward, -self.ff.reverse.stick(0.3))
        self.out(self.vm / 2 + self.h * 0.6)   # a new direction starts from neutral: the higher threshold
        self.assertEqual(self.out(self.vm / 2 + self.h * 0.4).floor_forward, FLOOR_MOVE, 'once moving forward the lower threshold')
        self.assertEqual(self.out(-(vr / 2 + self.h * 0.4)).floor_forward, FLOOR_LOW, 'a sign change starts from neutral')

    def test_turn_axis_same_scheme(self):
        wm, ht = self.ff.turn.min_speed, self.h * self.ff.turn.min_speed / self.ff.forward.min_speed
        o = self.out(0.0, wm / 2 - ht); self.assertEqual((o.turn, o.floor_turn), (0.0, FLOOR_LOW))
        o = self.out(0.0, wm / 2 + ht); self.assertEqual(o.floor_turn, FLOOR_MOVE); self.assertAlmostEqual(o.turn, self.ff.turn.move_stick)
        o = self.out(0.0, -0.3); self.assertEqual(o.floor_turn, FLOOR_TABLE); self.assertAlmostEqual(o.turn, -self.ff.turn.stick(0.3))
        self.assertFalse(o.neutral); self.assertEqual(o.forward, 0.0, 'turning in place: forward neutral')
        self.assertEqual(self.out(0.0, wm / 2 + ht * 0.4).floor_turn, FLOOR_LOW, 'left after right: from neutral again')

    def test_neutral_reasons_reset_the_floor(self):
        self.out(self.vm / 2 + self.h * 0.6)
        self.core.on_motion_hold(True, 'test', 2, self.t)
        self.assertTrue(self.core.output(self.t).neutral)
        self.t += 0.05; self.core.on_cmd_vel(self.vm / 2 + self.h * 0.4, 0.0, self.t); self.core.on_motion_hold(False, '', 2, self.t)
        self.assertEqual(self.core.output(self.t).floor_forward, FLOOR_LOW, 'after the hold the axis starts from neutral')

    def test_compensation_per_direction_wins(self):
        self.core.set_compensation(Compensation(forward_min=0.25, forward_threshold=0.01))
        o = self.out(0.03, 0.3)
        self.assertEqual(o.floor_forward, FLOOR_COMPENSATION); self.assertGreater(o.forward, 0.25 - 1e-9)
        self.assertEqual(o.floor_turn, FLOOR_TABLE, 'the turn has no compensation set: the floor')

    def test_feedback_layer_targets_are_floored(self):
        self.core.set_feedback(Feedback(True))   # on, PI values not set: feedforward alone
        o = self.out(self.vm / 2 - self.h)
        self.assertEqual((o.forward, o.floor_forward), (0.0, FLOOR_LOW))
        o = self.out(self.vm * 0.8); self.assertEqual(o.floor_forward, FLOOR_MOVE)
        self.assertAlmostEqual(o.forward, self.ff.forward.move_stick); self.assertAlmostEqual(o.forward_terms.target, self.vm)

    def test_without_hysteresis_value_nothing_changes(self):
        core = MotionCore(self.s, self.ff, None)
        core.on_motion_hold(False, '', 2, 1.0); core.on_cmd_vel(0.03, 0.0, 1.0)
        o = core.output(1.0)
        self.assertEqual(o.feedback_mode, MODE_OFF); self.assertEqual(o.floor_forward, '')
        self.assertAlmostEqual(o.forward, 0.03 / self.v['max_linear_speed_mps'])
        self.assertFalse(MotionCore(self.s, None, self.h).floor_ready(), 'no usable table: no floor')
        self.assertTrue(math.isfinite(self.h) and self.h >= 0)


if __name__ == '__main__':
    unittest.main()
