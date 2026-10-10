"""Unit tests of motion_core (ND-11) without ROS. Design tests: TS-07 (hold / hold expiry / cmd_vel stale -> neutral; only
hold=false AND fresh cmd_vel gives non-neutral) and the PC side of TS-13 (neutral at PRM-08 after cmd_vel stops).

Settings come from the generated files (approved PRM-08, trial PRM-39/40/42); no number is typed here that is a vehicle
value. The relation conditions of the model are asserted on the loaded values (PRM-42 < PRM-08)."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core.motion_core import MotionCore, MotionSettings, REASON_HOLD_NOT_RECEIVED, REASON_HOLD_TRUE, REASON_HOLD_EXPIRED, REASON_CMD_NOT_RECEIVED, REASON_CMD_STALE, REASON_CMD_NOT_FINITE, REASON_DRIVE  # noqa: E402

PARAMS = Path(__file__).resolve().parents[2] / 'design' / 'generated' / 'params'


def load_settings():
    """gouda_motion_controller.yaml (approved) + .trial.yaml (software trial values) -> MotionSettings."""
    import re
    vals = {}
    for name in ('gouda_motion_controller.yaml', 'gouda_motion_controller.trial.yaml'):
        for line in (PARAMS / name).read_text(encoding='utf-8').splitlines():
            m = re.match(r'\s+(\w+): ([-\d.]+)', line)
            if m: vals[m.group(1)] = float(m.group(2))
    return MotionSettings(vals['cmd_vel_timeout_s'], vals['max_linear_speed_mps'], vals['max_angular_speed_radps'], vals['motion_hold_timeout_s'])


class MotionCoreTests(unittest.TestCase):
    def setUp(self):
        self.s = load_settings(); self.core = MotionCore(self.s)
        self.assertLess(self.s.motion_hold_timeout_s, self.s.cmd_vel_timeout_s, 'PRM-42 must be shorter than PRM-08 (model relation)')

    def drive(self, t):
        self.core.on_motion_hold(False, 'mode=autonomy', 3, t); self.core.on_cmd_vel(self.s.max_linear_speed_mps / 2, 0.0, t)

    def test_neutral_until_hold_received(self):
        self.core.on_cmd_vel(0.1, 0.0, 0.0)
        o = self.core.output(0.0); self.assertTrue(o.neutral); self.assertEqual(o.reason, REASON_HOLD_NOT_RECEIVED)

    def test_hold_true_is_neutral_even_with_fresh_cmd(self):
        self.core.on_motion_hold(True, 'human_pause', 4, 0.0); self.core.on_cmd_vel(0.1, 0.2, 0.0)
        o = self.core.output(0.0); self.assertTrue(o.neutral); self.assertEqual((o.forward, o.turn), (0.0, 0.0)); self.assertEqual(o.reason, REASON_HOLD_TRUE); self.assertEqual(o.hold_reason, 'human_pause')

    def test_drive_only_with_hold_false_and_fresh_cmd(self):
        self.drive(0.0)
        o = self.core.output(0.01); self.assertFalse(o.neutral); self.assertEqual(o.reason, REASON_DRIVE); self.assertAlmostEqual(o.forward, 0.5); self.assertEqual(o.turn, 0.0)

    def test_hold_expiry_is_neutral(self):
        self.drive(0.0)
        self.assertFalse(self.core.output(self.s.motion_hold_timeout_s).neutral)
        self.core.on_cmd_vel(0.1, 0.0, self.s.motion_hold_timeout_s + 0.01)   # cmd stays fresh, hold expires
        o = self.core.output(self.s.motion_hold_timeout_s + 0.01); self.assertTrue(o.neutral); self.assertEqual(o.reason, REASON_HOLD_EXPIRED)

    def test_cmd_vel_stale_at_prm08(self):
        """TS-13 (PC side): the last non-neutral is replaced by neutral once cmd_vel is older than PRM-08."""
        self.drive(0.0)
        t = self.s.cmd_vel_timeout_s
        for k in range(1, 20):   # keep hold fresh, let cmd_vel age
            self.core.on_motion_hold(False, 'mode=autonomy', 3, t * k / 20)
        self.assertFalse(self.core.output(t).neutral, 'at exactly the timeout the command is still used')
        self.core.on_motion_hold(False, 'mode=autonomy', 3, t + 0.001)
        o = self.core.output(t + 0.001); self.assertTrue(o.neutral); self.assertEqual(o.reason, REASON_CMD_STALE)

    def test_cmd_vel_not_received_is_neutral(self):
        self.core.on_motion_hold(False, 'mode=autonomy', 3, 0.0)
        o = self.core.output(0.0); self.assertTrue(o.neutral); self.assertEqual(o.reason, REASON_CMD_NOT_RECEIVED)

    def test_non_finite_cmd_is_neutral(self):
        self.core.on_motion_hold(False, 'mode=autonomy', 3, 0.0); self.core.on_cmd_vel(math.nan, 0.0, 0.0)
        o = self.core.output(0.0); self.assertTrue(o.neutral); self.assertEqual(o.reason, REASON_CMD_NOT_FINITE)
        self.core.on_cmd_vel(0.1, math.inf, 0.0); self.assertTrue(self.core.output(0.0).neutral)

    def test_normalisation_saturates_and_never_adds_a_limit(self):
        self.core.on_motion_hold(False, 'mode=autonomy', 3, 0.0)
        self.core.on_cmd_vel(self.s.max_linear_speed_mps * 3, -self.s.max_angular_speed_radps * 2, 0.0)
        o = self.core.output(0.0); self.assertEqual((o.forward, o.turn), (1.0, -1.0))
        self.core.on_cmd_vel(-self.s.max_linear_speed_mps * 0.25, self.s.max_angular_speed_radps * 0.5, 0.0)
        o = self.core.output(0.0); self.assertAlmostEqual(o.forward, -0.25); self.assertAlmostEqual(o.turn, 0.5)

    def test_settings_must_be_positive(self):
        with self.assertRaises(ValueError): MotionSettings(0.0, 1, 1, 1).validate()
        with self.assertRaises(ValueError): MotionSettings(0.5, math.nan, 1, 1).validate()


if __name__ == '__main__':
    unittest.main()
