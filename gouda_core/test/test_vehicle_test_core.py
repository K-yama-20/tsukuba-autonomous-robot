import sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vehicle_motion_model import Model, ModelValues   # noqa: E402
from gouda_core import vehicle_test_core as core       # noqa: E402
from gouda_core.vehicle_tests import TESTS, motion_start   # noqa: E402

DEF = Path(__file__).resolve().parents[1] / 'vehicle_tests' / 'motion_start.yaml'
IMU_DT, CMD_DT, STATUS_DT = 0.005, 0.05, 0.05


def params(**over):
    p, err = core.validate_params(core.load_definition(DEF), over)
    assert not err, err
    return p


def simulate(p, v=ModelValues(), root=None):
    """The runner's loop in simulated time. The command reaches the model on the next tick (a small fixed transport)."""
    events = []
    trials = motion_start.build_trials(p)
    seq = core.Sequencer(trials, p, events.append)
    m = Model(v); t = 1000.0; next_cmd = t; next_st = t; pending = (0.0, 0.0)
    status = {k: [] for k in ('t_rx', 'uptime_ms', 'dac_x', 'dac_y')}
    while not seq.done and t < 200000:
        if t >= next_cmd:
            m.command(t, *pending)
            pending = seq.command(t); next_cmd += CMD_DT
        if t >= next_st:
            status['t_rx'].append(t + 0.002); status['uptime_ms'].append(round((t - 1000.0) * 1000)); status['dac_x'].append(m.turn); status['dac_y'].append(m.forward); next_st += STATUS_DT
        a, w = m.imu(t); seq.feed_imu(t, a, w)
        t += IMU_DT
    clock = core.fit_clock(status['uptime_ms'], status['t_rx'])
    sigma = next(e['sigma'] for e in events if e['event'] == 'baseline_end')
    return motion_start.analyze({'trials': trials, 'events': events, 'status': status, 'clock': clock, 'sigma': sigma, 'axes': 'base_link'}, p), events


def table(res, key):
    return next(t for t in res['tables'] if t['key'] == key)['rows']


class Recover(unittest.TestCase):
    def test_threshold_is_found_in_every_direction(self):
        res, _ = simulate(params(sections=['threshold_up'], repeats=1, settle_s=2.0, threshold_angles_deg=[90, 270, 45, 0]))
        for row in table(res, 'threshold_up'):
            self.assertEqual(row['level'], [0.12], row)
            self.assertEqual(row['below'], [0.1], row)

    def test_delay_includes_the_model_delay_and_a_transport(self):
        res, _ = simulate(params(sections=['delay'], repeats=2, settle_s=2.0, delay_angles_deg=[90, 0], delay_amounts=[0.4]))
        for row in table(res, 'delay'):
            self.assertEqual(row['n'], 2)
            self.assertGreater(row['mean_s'], 0.3)
            self.assertLess(row['mean_s'], 0.3 + 3 * CMD_DT + 0.1)

    def test_shock_alone_is_not_taken_as_motion(self):
        res, _ = simulate(params(sections=['delay'], repeats=1, settle_s=2.0, delay_angles_deg=[0], delay_amounts=[0.4]))
        seg = next(r for r in res['rows'] if r['section'] == 'delay')['segments'][0]
        self.assertLess(seg['first_s'], seg['motion_s'])   # first = the shock, motion = sustained; both kept
        self.assertGreaterEqual(seg['motion_s'] - seg['first_s'], ModelValues.rise_s)

    def test_t_lock_turns_between_the_two_gaps_around_it(self):
        res, _ = simulate(params(sections=['delay', 't_lock'], repeats=1, settle_s=3.0, delay_angles_deg=[90], delay_amounts=[0.4], gaps_s=[0.25, 0.75, 1, 1.5, 2]))
        by = {r['gap_s']: r['locked'] for r in table(res, 't_lock')}
        self.assertEqual(by, {0.25: False, 0.75: False, 1: False, 1.5: True, 2: True})

    def test_pulse_shorter_than_the_delay_goes_back_to_the_lock(self):
        res, _ = simulate(params(sections=['delay', 'pulse'], repeats=1, settle_s=3.0, delay_angles_deg=[90], delay_amounts=[0.4], pulse_widths_s=[0.1, 0.2, 0.6], pulse_observe_s=0.5))
        by = {r['width_s']: r for r in table(res, 'pulse')}
        self.assertTrue(by[0.1]['locked']); self.assertTrue(by[0.2]['locked'])
        self.assertFalse(by[0.6]['locked']); self.assertEqual(by[0.6]['moved_in_pulse'], 1)

    def test_lock_threshold_is_found_going_down(self):
        res, _ = simulate(params(sections=['delay', 'threshold_down'], repeats=1, settle_s=3.0, delay_angles_deg=[90], delay_amounts=[0.4], lock_levels=[0.2, 0.15, 0.1, 0.05], lock_hold_s=2.0))
        by = {r['level']: r['locked'] for r in table(res, 'threshold_down')}
        self.assertEqual(by, {0.2: False, 0.15: False, 0.1: True, 0.05: True})


class Parts(unittest.TestCase):
    def test_defaults_are_valid_and_a_test_is_registered(self):
        self.assertIn('motion_start', TESTS)
        self.assertTrue(motion_start.build_trials(params()))

    def test_out_of_range_is_refused(self):
        _, err = core.validate_params(core.load_definition(DEF), {'probe_amount': 1.5, 'gaps_s': [-1], 'sections': ['nope']})
        self.assertEqual(len(err), 3)

    def test_turning_comes_before_translation(self):
        trials = motion_start.build_trials(params(sections=['threshold_up'], repeats=1))
        self.assertTrue(all(s.forward == 0 for s in trials[0].segments))

    def test_directions(self):
        self.assertEqual(core.stick(0, 0.5), (0.5, 0.0))
        self.assertEqual(core.stick(90, 0.5), (0.0, 0.5))
        self.assertEqual(core.stick(180, 0.5), (-0.5, 0.0))
        self.assertEqual(core.stick(270, 0.5), (0.0, -0.5))

    def test_clock_fit_recovers_offset_under_late_arrivals(self):
        ms = list(range(0, 10000, 50)); rx = [5 + m / 1000 + (0.03 if i % 7 == 0 else 0.001) for i, m in enumerate(ms)]
        c = core.fit_clock(ms, rx)
        self.assertAlmostEqual(c['a'] + c['b'] * 5000, 10.0, delta=0.01)
        self.assertGreaterEqual(c['late_max_s'], 0.02)

    def test_abort_ends_with_neutral(self):
        ev = []
        s = core.Sequencer(motion_start.build_trials(params(sections=['delay'], settle_s=0.0)), params(), ev.append)
        for i in range(400):
            t = i * 0.005; s.feed_imu(t, 0.0 + i % 2 * 1e-3, 0.0 + i % 2 * 1e-3); s.command(t)
        s.abort(5.0)
        self.assertEqual(s.command(5.1), (0.0, 0.0))

    def test_a_sample_older_than_the_segment_is_not_motion(self):
        p = params(sections=['delay'], settle_s=0.0, baseline_s=1.0, delay_angles_deg=[90], delay_amounts=[0.4], repeats=1)
        s = core.Sequencer(motion_start.build_trials(p), p, lambda e: None)
        for i in range(250):
            t = i * 0.005; s.feed_imu(t, i % 2 * 1e-3, i % 2 * 1e-3); s.command(t)
        self.assertIsNotNone(s.detector)
        s.feed_imu(s.t_seg - 0.1, 0.0, 5.0)
        self.assertIsNone(s.detector.first)

    def test_store_and_wave_keep_a_short_shock(self):
        with tempfile.TemporaryDirectory() as d:
            w = core.RunWriter(Path(d), 'motion_start', {}, {}, stamp='x')
            w.event({'t': 0.0, 'event': 'trial_start', 'trial': 'a'}); w.event({'t': 1.0, 'event': 'segment_start', 'trial': 'a', 'segment': 0, 'label': 's'}); w.event({'t': 2.0, 'event': 'trial_end', 'trial': 'a'})
            for i in range(2000):
                t = i / 1000; w.imu.writerow([t, 0, 0, 0, 0, 0, 0, 9.0 if i == 1234 else 0.0, 0.0])
            w.close(); w.write_result({'end_reason': 'completed'})
            s = core.RunStore(Path(d))
            self.assertEqual(s.list_runs()[0]['end_reason'], 'completed')
            wave = s.wave(w.run_id, 'a', 100)
            self.assertLess(len(wave['imu_accel']['t']), 300)
            self.assertIn(9.0, wave['imu_accel']['signal_accel'])
            with self.assertRaises(ValueError): s.wave('../x', 'a', 100)


if __name__ == '__main__':
    unittest.main()
