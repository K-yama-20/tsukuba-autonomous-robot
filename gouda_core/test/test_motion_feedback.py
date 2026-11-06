"""Unit tests of the speed-feedback layer of motion_core (ND-11, REV-241, DEC-450; #65) without ROS.

Covered (the instruction's list): start from standstill, neutral at a zero target, integral saturation (anti-windup and the
integral limit), the switch to feedforward alone when the odometry is stale / not received, the integral reset on motion_hold,
on manual priority and on a sign change, and that the dead-band compensation of DEC-171 is not applied while the layer is on.

The feedforward points and the speed limits are read from the generated parameter file (DEC-445 values, PRM-150..160, and
PRM-39/40/78), so no vehicle value is typed here. Gains in these tests are test inputs, not proposals for the vehicle."""
import math
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core.motion_core import (MotionCore, MotionSettings, Compensation, Feedback, Feedforward, FeedforwardAxis,  # noqa: E402
                                    MODE_FF_PI, MODE_FF_ONLY, MODE_NEUTRAL, MODE_OFF, REASON_MANUAL_PRIORITY, REASON_HOLD_TRUE)

PARAMS = Path(__file__).resolve().parents[2] / 'design' / 'generated' / 'params'


def load_values():
    vals = {}
    for line in (PARAMS / 'gouda_motion_controller.yaml').read_text(encoding='utf-8').splitlines():
        m = re.match(r'\s+(\w+): ([-\d.]+)', line)
        if m: vals[m.group(1)] = float(m.group(2))
    return vals


def feedforward_from(v):
    return Feedforward(
        FeedforwardAxis(v['ff_forward_stop_stick'], v['ff_forward_move_stick'], v['ff_forward_min_speed_mps'], v['max_linear_speed_mps']),
        FeedforwardAxis(v['ff_reverse_stop_stick'], v['ff_reverse_move_stick'], v['ff_reverse_min_speed_mps'], v['max_reverse_speed_mps']),
        FeedforwardAxis(v['ff_turn_stop_stick'], v['ff_turn_move_stick'], v['ff_turn_min_speed_radps'], v['max_angular_speed_radps'],
                        v['ff_turn_mid_stick'], v['ff_turn_mid_speed_radps']))


class Plant:
    """Test stand-in of the vehicle: the measured static map (dead band from the stop stick, the minimum speed from the move stick),
    a first-order lag and an odometry delay. Only for these tests."""

    def __init__(self, ff: Feedforward, tau=0.3, odom_delay=0.1):
        self.ff, self.tau, self.delay = ff, tau, odom_delay
        self.v = 0.0; self.moving = False; self.hist = []

    def speed_of(self, stick):
        a = self.ff.forward
        s = abs(stick)
        if s >= a.move_stick or (self.moving and s > a.stop_stick):
            pts = a.points()
            for (v0, k0), (v1, k1) in zip(pts[1:], pts[2:]):
                if s <= k1:
                    return max(a.min_speed, v0 + (v1 - v0) * (s - k0) / (k1 - k0))
            return a.full_speed
        return 0.0

    def step(self, t, dt, stick):
        target = self.speed_of(stick)
        self.v += (target - self.v) * (1 - math.exp(-dt / self.tau))
        self.moving = target > 0 and self.v > 0.01
        self.hist.append((t, self.v))

    def odom(self, t):
        old = [v for (tt, v) in self.hist if tt <= t - self.delay]
        return old[-1] if old else 0.0


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.v = load_values()
        self.s = MotionSettings(self.v['cmd_vel_timeout_s'], self.v['max_linear_speed_mps'], self.v['max_angular_speed_radps'],
                                self.v['motion_hold_timeout_s'], self.v['max_reverse_speed_mps'])
        self.ff = feedforward_from(self.v)
        self.assertEqual(self.ff.problems(), [])
        self.core = MotionCore(self.s, self.ff)
        self.period = self.v['command_publish_period_s']
        self.fb = Feedback(True, 0.5, 1.5, 0.3, 0.5, 1.0, 0.3, 0.5)   # test inputs

    def go(self, t, vx, wz=0.0, odom=None):
        self.core.on_motion_hold(False, 'mode=autonomy', 3, t); self.core.on_cmd_vel(vx, wz, t)
        if odom is not None: self.core.on_odometry(odom[0], odom[1], t)
        return self.core.output(t)

    def test_feedforward_passes_the_measured_points(self):
        a = self.ff.forward
        self.assertAlmostEqual(a.stick(a.min_speed), a.move_stick)
        self.assertAlmostEqual(a.stick(a.full_speed), 1)
        self.assertGreater(a.stick(a.min_speed / 2), a.stop_stick)        # below the minimum speed: inside the dead band
        self.assertLess(a.stick(a.min_speed / 2), a.move_stick)
        tr = self.ff.turn
        self.assertAlmostEqual(tr.stick(tr.mid_speed), tr.mid_stick)

    def test_disabled_is_the_old_path_with_compensation(self):
        self.core.set_compensation(Compensation(0.2, 0.01))
        o = self.go(0.0, self.s.max_linear_speed_mps / 2)
        self.assertEqual(o.feedback_mode, MODE_OFF)
        self.assertAlmostEqual(o.forward, 0.2 + 0.8 * 0.5)

    def test_enabled_does_not_compensate_twice(self):
        self.core.set_compensation(Compensation(0.2, 0.01))
        self.core.set_feedback(Feedback(True))          # PI values not set -> feedforward alone
        vx = self.ff.forward.min_speed
        o = self.go(0.0, vx)
        self.assertEqual(o.feedback_mode, MODE_FF_ONLY)
        self.assertAlmostEqual(o.forward, self.ff.forward.move_stick)   # the feedforward, not m + (1 - m) * ff

    def test_start_from_standstill_below_minimum_speed(self):
        """A target below the minimum speed starts in the dead band; the integral lifts it until the plant moves."""
        self.core.set_feedback(self.fb)
        plant = Plant(self.ff)
        target = self.ff.forward.min_speed / 2
        t = 0.0; started = None
        while t < 10:
            o = self.go(t, target, 0.0, (plant.odom(t), 0.0))
            plant.step(t, self.period, o.forward)
            if started is None and plant.v > 0.02: started = t
            t += self.period
        self.assertIsNotNone(started, 'the plant never started')
        self.assertLess(started, 3)

    def test_start_without_feedback_stays_in_dead_band(self):
        """The same target with the layer off (plain normalization) never starts: the reason for #61/#65."""
        plant = Plant(self.ff)
        target = self.ff.forward.min_speed / 2
        t = 0.0
        while t < 5:
            o = self.go(t, target)
            plant.step(t, self.period, o.forward); t += self.period
        self.assertLess(plant.v, 0.01)

    def test_zero_target_is_neutral_and_resets(self):
        self.core.set_feedback(self.fb)
        for k in range(20):
            self.go(k * self.period, self.ff.forward.min_speed, 0.0, (0.0, 0.0))
        self.assertGreater(self.core.pi_forward.i, 0)
        o = self.go(20 * self.period, 0.0, 0.0, (0.0, 0.0))
        self.assertTrue(o.neutral); self.assertEqual(o.feedback_mode, MODE_NEUTRAL)
        self.assertEqual((o.forward, o.turn), (0.0, 0.0)); self.assertEqual(self.core.pi_forward.i, 0.0)

    def test_integral_limit_and_saturation(self):
        self.core.set_feedback(self.fb)
        for k in range(200):   # 10 s with the vehicle not moving at all
            o = self.go(k * self.period, self.ff.forward.min_speed, 0.0, (0.0, 0.0))
        self.assertLessEqual(abs(self.core.pi_forward.i), self.fb.forward_i_limit + 1e-12)
        # saturation: a target above the full speed; the integral must not grow while the output is at the full stick
        core = MotionCore(self.s, self.ff); core.set_feedback(Feedback(True, 0.5, 1.5, 0.9, 0.5, 1.0, 0.3, 0.5))
        top = self.s.max_linear_speed_mps
        ivals = []
        for k in range(100):
            core.on_motion_hold(False, 'm', 3, k * self.period); core.on_cmd_vel(top, 0.0, k * self.period); core.on_odometry(0.0, 0.0, k * self.period)
            o = core.output(k * self.period); ivals.append(core.pi_forward.i)
        self.assertEqual(o.forward, 1)
        self.assertEqual(max(ivals), 0.0, 'the integral grew while the output was saturated')

    def test_odometry_stale_falls_back_to_feedforward(self):
        self.core.set_feedback(self.fb)
        for k in range(10):
            self.go(k * self.period, self.ff.forward.min_speed, 0.0, (0.0, 0.0))
        self.assertEqual(self.core.output(9 * self.period).feedback_mode, MODE_FF_PI)
        t = 9 * self.period + self.fb.odometry_timeout_s + self.period   # odometry stops; cmd_vel and hold continue
        o = self.go(t, self.ff.forward.min_speed)
        self.assertEqual(o.feedback_mode, MODE_FF_ONLY); self.assertIn('stale', o.feedback_reason)
        self.assertFalse(o.neutral)
        self.assertAlmostEqual(o.forward, self.ff.forward.move_stick)
        self.assertEqual(self.core.pi_forward.i, 0.0)

    def test_odometry_never_received_drives_on_feedforward(self):
        self.core.set_feedback(self.fb)
        o = self.go(0.0, self.ff.forward.min_speed)
        self.assertEqual(o.feedback_mode, MODE_FF_ONLY); self.assertFalse(o.neutral)

    def test_hold_resets_the_integral(self):
        self.core.set_feedback(self.fb)
        for k in range(20):
            self.go(k * self.period, self.ff.forward.min_speed, 0.0, (0.0, 0.0))
        self.assertGreater(self.core.pi_forward.i, 0)
        self.core.on_motion_hold(True, 'human_pause', 4, 1.0)
        o = self.core.output(1.0)
        self.assertTrue(o.neutral); self.assertEqual(o.reason, REASON_HOLD_TRUE); self.assertEqual(self.core.pi_forward.i, 0.0)
        o = self.go(1.05, self.ff.forward.min_speed, 0.0, (0.0, 0.0))
        self.assertAlmostEqual(o.forward_terms.i, 0.0)   # no dt yet after the reset: starts again from 0

    def test_manual_priority_is_neutral_and_resets(self):
        self.core.set_feedback(self.fb)
        for k in range(20):
            self.go(k * self.period, self.ff.forward.min_speed, 0.0, (0.0, 0.0))
        self.core.on_vehicle_source('manual')
        o = self.go(1.0, self.ff.forward.min_speed, 0.0, (0.0, 0.0))
        self.assertTrue(o.neutral); self.assertEqual(o.reason, REASON_MANUAL_PRIORITY); self.assertEqual(self.core.pi_forward.i, 0.0)
        self.core.on_vehicle_source('pc')
        self.assertFalse(self.go(1.05, self.ff.forward.min_speed, 0.0, (0.0, 0.0)).neutral)

    def test_manual_priority_ignored_when_disabled(self):
        self.core.on_vehicle_source('manual')
        self.assertFalse(self.go(0.0, self.ff.forward.min_speed).neutral)

    def test_never_reverses_and_resets_on_sign_change(self):
        self.core.set_feedback(self.fb)
        o = None
        for k in range(20):   # the vehicle is faster than asked: the PI may only reduce towards neutral
            o = self.go(k * self.period, self.ff.forward.min_speed, 0.0, (self.s.max_linear_speed_mps, 0.0))
        self.assertGreaterEqual(o.forward, 0.0)
        o = self.go(1.0, -self.ff.reverse.min_speed, 0.0, (0.0, 0.0))
        self.assertLess(o.forward, 0.0)
        self.assertLessEqual(o.forward_terms.i, 0.0)

    def test_turn_axis_feedback(self):
        self.core.set_feedback(self.fb)
        w = self.ff.turn.mid_speed
        o = None
        for k in range(20):
            o = self.go(k * self.period, 0.0, w, (0.0, 0.0))
        self.assertEqual(o.forward, 0.0)
        self.assertGreater(o.turn, self.ff.turn.mid_stick)   # the integral adds while the vehicle does not turn
        self.assertEqual(o.feedback_mode, MODE_FF_PI)

    def test_bad_feedback_values_are_not_used(self):
        bad = Feedback(True, -1.0)
        self.assertTrue(self.core.set_feedback(bad))
        self.assertFalse(self.core.feedback.enabled)


class MonitorFieldTests(unittest.TestCase):
    """REV-241: the /config 「自律走行の出力」 fields of the speed feedback (IFD-52)."""

    def test_fields_and_kinds(self):
        import tempfile
        from gouda_core.monitor_core import SensorConfig, MOTION_COMPENSATION_FIELDS, UNKNOWN
        with tempfile.TemporaryDirectory() as d:
            c = SensorConfig(Path(d) / 'motion_compensation.json', MOTION_COMPENSATION_FIELDS)
            self.assertEqual(c.values['speed_feedback_enabled'], UNKNOWN)
            ok, msg = c.update({'speed_feedback_enabled': 'true', 'forward_kp': '0', 'forward_ki': '1.5', 'forward_i_limit': '0.3',
                                'odometry_timeout_s': '0.5'}, 1.0)
            self.assertTrue(ok, msg)
            self.assertIs(c.values['speed_feedback_enabled'], True); self.assertEqual(c.values['forward_kp'], 0.0)
            for bad in ({'forward_kp': '-0.1'}, {'turn_i_limit': '1.5'}, {'odometry_timeout_s': '0'}, {'speed_feedback_enabled': 'yes'}):
                ok, msg = c.update(bad, 2.0)
                self.assertFalse(ok, bad)
            again = SensorConfig(Path(d) / 'motion_compensation.json', MOTION_COMPENSATION_FIELDS)
            self.assertIs(again.values['speed_feedback_enabled'], True)


if __name__ == '__main__':
    unittest.main()
