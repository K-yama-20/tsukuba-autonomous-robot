"""stop_distance.py の単体試験（合成の軌跡。実測ではない）。 usage: python3 -m unittest test_stop_distance  （このフォルダで）"""
import math
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stop_distance as sd  # noqa: E402

DT = 0.1


def run_track(v, t_signal, coast_m, t_coast, t_total, heading=0.0, t0=100.0, wobble=0.0):
    """Constant speed v until t_signal, then a linear slow-down over t_coast that covers coast_m, then rest."""
    pts, n = [], int(round(t_total / DT))
    for i in range(n + 1):
        t = i * DT
        if t <= t_signal:
            s = v * t
        else:
            a = min((t - t_signal) / t_coast, 1.0)
            s = v * t_signal + coast_m * (2 * a - a * a)   # speed falls linearly to zero
        if wobble and t > t_signal + t_coast:
            s += wobble * math.sin(2 * math.pi * 4 * t)
        pts.append((t0 + t, s * math.cos(heading), s * math.sin(heading)))
    return pts


class Tests(unittest.TestCase):
    def test_stop_distance_along_the_heading(self):
        track = run_track(v=0.5, t_signal=3.0, coast_m=0.30, t_coast=1.2, t_total=10.0, heading=math.radians(30))
        e = sd.analyze(track, [(103.0, 'x')], [])[0]
        self.assertEqual(e['verdict'], '算出')
        self.assertAlmostEqual(e['v0_mps'], 0.5, places=3)
        self.assertAlmostEqual(e['d_along_m'], 0.30, places=3)
        self.assertAlmostEqual(e['d_lateral_m'], 0.0, places=3)
        self.assertTrue(0.8 <= e['t_stop_s'] <= 1.3, e['t_stop_s'])

    def test_reverse_run_gives_a_positive_distance_along_the_travel(self):
        track = run_track(v=-0.2, t_signal=3.0, coast_m=-0.10, t_coast=0.8, t_total=9.0)
        e = sd.analyze(track, [(103.0, '')], [])[0]
        self.assertEqual(e['verdict'], '算出')
        self.assertAlmostEqual(e['d_along_m'], 0.10, places=3)

    def test_window_ends_at_the_restart_and_short_windows_are_undetermined(self):
        track = run_track(v=0.5, t_signal=3.0, coast_m=0.30, t_coast=1.2, t_total=10.0)
        e = sd.analyze(track, [(103.0, '')], [104.5])[0]
        self.assertEqual(e['verdict'], '未判定')
        self.assertIn('短い', e['reason'])
        self.assertNotIn('d_along_m', e)

    def test_not_moving_before_the_signal_is_undetermined(self):
        track = [(100.0 + i * DT, 1.0, 2.0) for i in range(100)]
        e = sd.analyze(track, [(103.0, '')], [])[0]
        self.assertEqual(e['verdict'], '未判定')
        self.assertIn('動いていない', e['reason'])

    def test_signal_outside_the_track_is_undetermined(self):
        track = run_track(v=0.5, t_signal=3.0, coast_m=0.3, t_coast=1.0, t_total=10.0)
        e = sd.analyze(track, [(50.0, '')], [])[0]
        self.assertEqual((e['verdict'], 'v0_mps' in e), ('未判定', False))

    def test_still_moving_at_the_end_of_the_window_is_undetermined(self):
        track = run_track(v=0.5, t_signal=3.0, coast_m=3.0, t_coast=20.0, t_total=12.0)
        e = sd.analyze(track, [(103.0, '')], [])[0]
        self.assertEqual(e['verdict'], '未判定')

    def test_small_wobble_after_the_stop_is_reported(self):
        track = run_track(v=0.5, t_signal=3.0, coast_m=0.30, t_coast=1.2, t_total=10.0, wobble=0.005)
        e = sd.analyze(track, [(103.0, '')], [])[0]
        self.assertEqual(e['verdict'], '算出')
        self.assertTrue(0.003 <= e['settle_max_m'] <= 0.011, e['settle_max_m'])
        self.assertAlmostEqual(e['d_along_m'], 0.30, delta=0.006)

    def test_hold_edges(self):
        rows = [{'t': str(t), 'stamp': str(t), 'hold': h, 'reason': r} for t, h, r in
                [(1, '1', 'boot'), (2, '0', ''), (5, '1', 'mode=autonomy stop_reason=rule_stop'), (6, '1', 'again'), (9, '0', '')]]
        rising, falling = sd.hold_edges(rows)
        self.assertEqual(rising, [(5.0, 'mode=autonomy stop_reason=rule_stop')])
        self.assertEqual(falling, [2.0, 9.0])

    def test_neutral_edges(self):
        rows = [{'t': str(t), 'stamp': str(t), 'applied_y_q10000': y} for t, y in [(1, '0'), (2, '2100'), (3, '2500'), (4, '0'), (5, ''), (6, '0'), (7, '-2400'), (8, '0')]]
        to_zero, from_zero = sd.neutral_edges(rows)
        self.assertEqual([t for t, _ in to_zero], [4.0, 8.0])
        self.assertIn('+0.250', to_zero[0][1])
        self.assertEqual(from_zero, [2.0, 7.0])

    def test_tum_and_csv_tracks_and_the_decision_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / 'odom_lidar.txt').write_text('# comment\n1.0 0.0 0.0 0 0 0 0 1\n2.0 1.0 0.5 0 0 0 0 1\n', encoding='utf-8')
            (tmp / 'odom.csv').write_text('t,stamp,x,y,yaw\n11.0,1.0,0.0,0.0,0\n12.0,2.0,1.0,0.5,0\n', encoding='utf-8')
            self.assertEqual(sd.load_track(tmp / 'odom_lidar.txt'), [(1.0, 0.0, 0.0), (2.0, 1.0, 0.5)])
            self.assertEqual(sd.load_track(tmp / 'odom.csv'), [(1.0, 0.0, 0.0), (2.0, 1.0, 0.5)])
            self.assertEqual(sd.load_track(tmp / 'odom.csv', 'receive')[0][0], 11.0)
        events = [{'t': 5.0, 'verdict': '算出'}, {'t': 20.0, 'verdict': '算出'}]
        sd.attach_decisions(events, [{'t': '5.2', 'stamp': '5.2', 'details': '{"waypoint": 6, "distance_m": 0.69}'}])
        self.assertEqual((events[0]['stop_waypoint'], events[0]['distance_to_stop_point_m']), (6, 0.69))
        self.assertNotIn('stop_waypoint', events[1])
        self.assertIn('| 0.00 |', sd.table(events, 5.0))


if __name__ == '__main__':
    unittest.main()
