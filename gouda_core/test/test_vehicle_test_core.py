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
    imu = {'t': [], 'signal_accel': [], 'signal_yaw': []}
    while not seq.done and t < 200000:
        if t >= next_cmd:
            m.command(t, *pending)
            pending = seq.command(t); next_cmd += CMD_DT
        if t >= next_st:
            status['t_rx'].append(t + 0.002); status['uptime_ms'].append(round((t - 1000.0) * 1000)); status['dac_x'].append(m.turn); status['dac_y'].append(m.forward); next_st += STATUS_DT
        a, w = m.imu(t); seq.feed_imu(t, a, w)
        imu['t'].append(t); imu['signal_accel'].append(a); imu['signal_yaw'].append(w)
        t += IMU_DT
    clock = core.fit_clock(status['uptime_ms'], status['t_rx'])
    sigma = next(e['sigma'] for e in events if e['event'] == 'baseline_end')
    return motion_start.analyze({'trials': trials, 'events': events, 'status': status, 'clock': clock, 'sigma': sigma, 'axes': 'base_link', 'imu': imu}, p), events


def table(res, key):
    return next(t for t in res['tables'] if t['key'] == key)['rows']


class WaitReason(unittest.TestCase):
    def reason(self, source='pc', imu=0.0, status=0.0, waiting=None):
        return core.wait_reason(source, imu, status, 1.0, 1.0, waiting)

    def test_running(self):
        self.assertIsNone(self.reason())

    def test_gamepad_is_waited_for_and_does_not_end_the_test(self):
        self.assertEqual(self.reason(source='manual'), 'manual')

    def test_after_the_gamepad_it_waits_until_the_pc_is_the_source(self):
        self.assertEqual(self.reason(source='none', waiting='manual'), 'manual')
        self.assertIsNone(self.reason(source='pc', waiting='manual'))

    def test_no_source_alone_is_not_a_wait(self):
        self.assertIsNone(self.reason(source='none'))

    def test_lost_links(self):
        self.assertEqual(self.reason(imu=2.0), 'imu')
        self.assertEqual(self.reason(status=2.0), 'status')
        self.assertEqual(self.reason(source='pc', imu=2.0, waiting='manual'), 'imu')


class RetryAfterGamepad(unittest.TestCase):
    def test_interrupted_trial_is_measured_again_and_only_the_last_attempt_counts(self):
        p = params(sections=['delay'], repeats=1, settle_s=2.0, delay_angles_deg=[90], delay_amounts=[0.4])
        events = []; seq = core.Sequencer(motion_start.build_trials(p), p, events.append); t = 1000.0; retried = False
        while not seq.done and t < 2000:
            seq.command(t); seq.feed_imu(t, 0.001 * (int(t * 100) % 2), 0.001 * (int(t * 100) % 2))
            if not retried and seq.si >= 0:
                seq.retry(t); retried = True
            t += CMD_DT
        self.assertTrue(retried)
        self.assertEqual(sum(e['event'] == 'trial_retry' for e in events), 1)
        again = next(i for i, e in enumerate(events) if e['event'] == 'trial_retry')
        self.assertTrue(any(e['event'] == 'segment_start' for e in events[again:]))
        last = core.latest_attempt([e for e in events if e.get('trial') == events[again]['trial']])
        self.assertEqual(sum(e['event'] == 'segment_start' for e in last), 1)
        self.assertEqual(sum(e['event'] == 'segment_start' and e['trial'] == events[again]['trial'] for e in events), 2)


class Recover(unittest.TestCase):
    def test_threshold_is_found_in_every_direction(self):
        res, _ = simulate(params(sections=['threshold_up'], repeats=1, settle_s=2.0, threshold_angles_deg=[90, 270, 45, 0]))
        for row in table(res, 'threshold_up'):
            self.assertEqual(row['level'], [0.12], row)
            self.assertEqual(row['below'], [0.1], row)

    def test_delay_includes_the_model_delay_and_a_transport(self):
        res, _ = simulate(params(sections=['delay'], repeats=2, settle_s=2.0, delay_angles_deg=[90, 0], delay_amounts=[0.4]))
        for row in table(res, 'delay'):
            self.assertEqual(row['n'], 4)   # two trials of the direction in each repeat (DEC-464)
            self.assertGreater(row['mean_s'], 0.3)
            self.assertLess(row['mean_s'], 0.3 + 3 * CMD_DT + 0.1)

    def test_delay_goes_twice_each_way_and_comes_back(self):
        trials = motion_start.build_trials(params(sections=['delay'], repeats=2, delay_angles_deg=[90, 270], delay_amounts=[0.4]))
        self.assertEqual([t.info['angle'] for t in trials], [90, 90, 270, 270, 90, 90, 270, 270])
        self.assertEqual(len({t.id for t in trials}), len(trials))

    def test_delay_table_keeps_the_first_trial_of_a_direction_apart(self):
        res, _ = simulate(params(sections=['delay'], repeats=2, settle_s=2.0, delay_angles_deg=[90, 270], delay_amounts=[0.4]))
        steps = {r['trial']: r['segments'][0]['motion_s'] for r in res['rows'] if r['section'] == 'delay'}
        for row in table(res, 'delay'):
            a = f"{row['angle']:g}"
            self.assertAlmostEqual(row['changed_mean_s'], (steps[f'delay_{a}_0.4_0'] + steps[f'delay_{a}_0.4_2']) / 2)
            self.assertAlmostEqual(row['same_mean_s'], (steps[f'delay_{a}_0.4_1'] + steps[f'delay_{a}_0.4_3']) / 2)

    def test_shock_alone_is_not_taken_as_motion(self):
        res, _ = simulate(params(sections=['delay'], repeats=1, settle_s=2.0, delay_angles_deg=[0], delay_amounts=[0.4]))
        seg = next(r for r in res['rows'] if r['section'] == 'delay')['segments'][0]
        self.assertLess(seg['first_s'], seg['motion_s'])   # first = the shock, motion = sustained; both kept
        self.assertGreaterEqual(seg['motion_s'] - seg['first_s'], ModelValues.rise_s)

    def test_t_lock_turns_between_the_two_gaps_around_it(self):
        res, _ = simulate(params(sections=['delay', 't_lock'], repeats=1, settle_s=3.0, delay_angles_deg=[90], delay_amounts=[0.4], gaps_s=[0.25, 0.75, 1, 1.5, 2]))
        by = {r['gap_s']: r['locked'] for r in table(res, 't_lock')}
        # a gap shorter than the window still holds the drive in it, so its delay cannot be read (DEC-466)
        self.assertEqual(by, {0.25: None, 0.75: None, 1: None, 1.5: True, 2: True})

    def test_t_lock_table_is_per_direction(self):
        res, _ = simulate(params(sections=['t_lock'], repeats=2, settle_s=3.0, probe_angle_deg=90, gaps_s=[0.25, 2]))
        rows = table(res, 't_lock')
        self.assertEqual(sorted((r['gap_s'], r['angle']) for r in rows), [(0.25, 90), (0.25, 270), (2, 90), (2, 270)])
        for r in rows:
            self.assertEqual(r['locked'], True if r['gap_s'] == 2 else None, r)

    def test_a_moving_vehicle_gives_no_delay_and_no_lock_result(self):
        p = params(sections=['t_lock'], repeats=1, settle_s=3.0, gaps_s=[0.25])
        trials = motion_start.build_trials(p)
        probe = next(s for s in trials[0].segments if s.label == 'probe')
        rows = [{'section': 't_lock', 'ran': True, 'value': 0.25, 'segments': [{'label': 'probe', 'forward': probe.forward, 'turn': probe.turn, 'motion_s': 0.06,
                                                                               'before': {'yaw': 0.3, 'accel_spread': 0.0, 'moving': True}}]}]
        row = motion_start._t_lock_table(rows, [], p['locked_fraction'])[0]
        self.assertEqual((row['n'], row['moving']), (0, 1))
        self.assertIsNone(row['locked'])

    def test_stopping_is_read_before_the_probe_on_its_signal(self):
        p = params(baseline_tail_s=1.0, noise_k=6.0)
        t = [i * 0.01 for i in range(100)]
        run = {'sigma': {'accel': 0.02, 'yaw': 0.001}, 'imu': {'t': t, 'signal_yaw': [0.3] * 100, 'signal_accel': [0.0, 1.0] * 50}}
        self.assertTrue(motion_start._before(run, p, 1.0, 0.0, 0.7)['moving'])    # turning
        self.assertTrue(motion_start._before(run, p, 1.0, 0.7, 0.0)['moving'])    # driving straight: the spread
        run['imu'] = {'t': t, 'signal_yaw': [0.001] * 100, 'signal_accel': [0.5] * 100}
        self.assertFalse(motion_start._before(run, p, 1.0, 0.0, 0.7)['moving'])
        self.assertFalse(motion_start._before(run, p, 1.0, 0.7, 0.0)['moving'])   # a constant offset is not motion
        self.assertIsNone(motion_start._before({'sigma': run['sigma']}, p, 1.0, 0.0, 0.7))

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

    def _sequencer(self, **over):
        p = params(sections=['delay'], baseline_s=1.0, settle_s=0.5, repeats=1, delay_angles_deg=[0], delay_amounts=[0.5], sustain_s=0.0, **over)
        events = []
        seq = core.Sequencer(motion_start.build_trials(p), p, events.append)
        t = 0.0
        while seq.collecting or seq.si < 0:   # quiet IMU until the step begins
            seq.feed_imu(t, 0.01 * (-1) ** int(t * 100), 0.0); seq.command(t); t += 0.01
        return seq, events, t

    def test_input_continues_after_motion(self):  # DEC-414
        seq, events, t = self._sequencer(after_motion_s=1.0)
        t_move = None
        while not seq.done and seq.ti == 0:
            seq.feed_imu(t, 5.0, 0.0)
            f, _ = seq.command(t)
            if seq.ti == 0 and t_move is None and seq.t_moved is not None: t_move = t
            if seq.ti == 0 and t_move is not None and t - t_move < 0.95: self.assertGreater(f, 0)
            t += 0.01
        self.assertAlmostEqual(next(e for e in events if e['event'] == 'trial_end')['t'] - t_move, 1.0, delta=0.05)

    def test_largest_level_is_held_longer(self):  # DEC-414
        p = params(sections=['threshold_up'], threshold_angles_deg=[0], repeats=1, threshold_levels=[0.5, 1.0], stair_hold_s=2.0, top_hold_s=4.0)
        segs = motion_start.build_trials(p)[0].segments
        self.assertEqual([s.duration_s for s in segs], [2.0, 4.0])

    def test_retry_repeats_the_trial_and_only_the_last_attempt_counts(self):  # DEC-414
        seq, events, t = self._sequencer(after_motion_s=0.0)
        self.assertNotEqual(seq.command(t)[0], 0.0)
        seq.retry(t + 1)
        self.assertEqual((seq.si, seq.forward), (-1, 0.0))
        self.assertEqual(seq.command(t + 1.1), (0.0, 0.0))
        tid = seq.trials[0].id
        kept = core.latest_attempt([e for e in events if e.get('trial') == tid])
        self.assertEqual(kept, [])    # nothing of the first attempt stays
        self.assertTrue(any(e['event'] == 'trial_retry' for e in events))

    def test_retry_in_the_first_neutral_starts_the_noise_again(self):  # DEC-414
        p = params(sections=['delay'], baseline_s=1.0)
        seq = core.Sequencer(motion_start.build_trials(p), p, lambda e: None)
        seq.command(0.0); seq.feed_imu(0.0, 9.0, 9.0)
        seq.retry(0.5)
        self.assertEqual(seq.baseline.noise[core.SIG_ACCEL], [])
        self.assertTrue(seq.collecting); self.assertIsNone(seq.t0)

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
