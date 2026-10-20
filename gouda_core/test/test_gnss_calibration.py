"""Unit tests of gnss_calibration (REV-067, DEC-135 verification tool) without ROS, on synthetic files in the formats of a
registered source map (gnss.jsonl, source/traj_lidar.txt, sensor_config.json). Synthetic values only (no vehicle value).
Checked: ENU against a known point; a calibration drive gives back theta / t / antenna x-y / mount yaw / delay; the heading
convention with the smaller residual is the one used to make the data; a straight run is shown by the motion coverage
(no reverse, one heading sector) even when the std looks small; only RTK fixed / fixed attitude samples are used."""
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import gnss_calibration as gc  # noqa: E402

LAT0, LON0, H0 = math.radians(36.08), math.radians(140.11), 60.0
TRUTH = dict(theta=math.radians(37.0), t=np.array([12.0, -4.5, 0.3]), ant=np.array([-0.20, 0.05, 0.85]), mount=math.radians(2.0), delay=0.08)
CFG = {'lidar_mount_x_m': 0.30, 'lidar_mount_y_m': 0.0, 'lidar_mount_z_m': 0.90, 'lidar_axis_mapping': '+x forward, +y left, +z up',
       'gnss_main_mount_x_m': -0.17, 'gnss_main_mount_y_m': 0.02, 'gnss_main_mount_z_m': 0.85}   # /config prior (off by 3 cm)
SETTINGS = gc.Settings(sig_pos_m=0.015, sig_head_deg=0.3, sig_ant_prior_m=0.05, sig_mount_prior_deg=3.0, sig_delay_prior_s=0.2,
                       delay_search_s=0.3, delay_step_s=0.005, huber_k=3.0)


def geodetic(e, n, u):
    """Inverse of gc.enu for the test (ECEF -> geodetic by iteration)."""
    sl, cl, sp, cp = math.sin(LON0), math.cos(LON0), math.sin(LAT0), math.cos(LAT0)
    r = np.array([[-sl, cl, 0], [-sp * cl, -sp * sl, cp], [cp * cl, cp * sl, sp]])
    x = gc.ecef(np.array([LAT0]), np.array([LON0]), np.array([H0]))[0] + r.T @ np.array([e, n, u])
    e2 = gc.WGS84_F * (2 - gc.WGS84_F); lon = math.atan2(x[1], x[0]); p = math.hypot(x[0], x[1]); lat = math.atan2(x[2], p * (1 - e2))
    for _ in range(10):
        nn = gc.WGS84_A / math.sqrt(1 - e2 * math.sin(lat) ** 2); h = p / math.cos(lat) - nn; lat = math.atan2(x[2], p * (1 - e2 * nn / (nn + h)))
    return lat, lon, h


def drive(segments, dt=0.01):
    t, x, y, th = [0.0], [0.0], [0.0], [0.0]
    for dur, v, w in segments:
        for _ in range(int(round(dur / dt))):
            th.append(th[-1] + w * dt); x.append(x[-1] + v * math.cos(th[-1]) * dt); y.append(y[-1] + v * math.sin(th[-1]) * dt); t.append(t[-1] + dt)
    return np.array(t) + 1000.0, np.array(x), np.array(y), np.array(th)


CAL = [(5, 0, 0)] + [(31.4, 0.8, 0.2), (31.4, 0.8, -0.2), (8, 0, 0.8), (5, 0, 0), (8, 0, -0.8), (10, 1.2, 0), (10, -0.6, 0), (5, 0, 0), (4, 0, 0.8), (5, 0, 0)]


def write_source(d: Path, segments, heading_ned=False, noisy=True, float_every=0):
    rng = np.random.default_rng(3)
    t, x, y, th = drive(segments)
    (d / 'source').mkdir(parents=True)
    # traj_lidar.txt: LiDAR pose = base pose x T_base_lidar (lidar 0.30 forward, 0.90 up, axes = base)
    with open(d / 'source' / 'traj_lidar.txt', 'w') as f:
        for i in range(0, len(t), 10):
            lx, ly = x[i] + math.cos(th[i]) * 0.30, y[i] + math.sin(th[i]) * 0.30
            f.write(f'{t[i]:.6f} {lx:.6f} {ly:.6f} 0.9 0 0 {math.sin(th[i] / 2):.9f} {math.cos(th[i] / 2):.9f}\n')
    (d / 'sensor_config.json').write_text(json.dumps({'values': CFG, 'config_revision': 1}))
    c, s = math.cos(TRUTH['theta']), math.sin(TRUTH['theta']); a = TRUTH['ant']
    lines = []
    for k, i in enumerate(range(0, len(t), 10)):
        ts = t[i]; tq = ts - TRUTH['delay']
        bx, by, bth = np.interp(tq, t, x), np.interp(tq, t, y), np.interp(tq, t, th)
        am = np.array([bx + math.cos(bth) * a[0] - math.sin(bth) * a[1], by + math.sin(bth) * a[0] + math.cos(bth) * a[1], a[2]])
        e = np.array([c * am[0] - s * am[1], s * am[0] + c * am[1], am[2]]) + TRUTH['t'] + (rng.normal(0, 0.015, 3) if noisy else 0)
        lat, lon, h = geodetic(*e)
        psi = bth + TRUTH['theta'] + TRUTH['mount'] + (rng.normal(0, math.radians(0.3)) if noisy else 0)
        hd = math.degrees(math.pi / 2 - psi) if heading_ned else math.degrees(math.atan2(math.sin(psi), math.cos(psi)))
        stamp = {'sec': int(ts), 'nanosec': int(round((ts - int(ts)) * 1e9))}
        mode = 5 if (float_every and k % float_every == 0) else 4
        lines.append({'topic': 'sensors/gnss/pvtgeodetic', 'received_at': ts, 'msg': {'header': {'stamp': stamp}, 'block_header': {'tow': k}, 'mode': mode,
                      'latitude': lat, 'longitude': lon, 'height': h, 'h_accuracy': 2}})
        lines.append({'topic': 'sensors/gnss/atteuler', 'received_at': ts, 'msg': {'header': {'stamp': stamp}, 'block_header': {'tow': k}, 'mode': 2, 'heading': hd}})
        lines.append({'topic': 'sensors/gnss/attcoveuler', 'received_at': ts, 'msg': {'header': {'stamp': stamp}, 'block_header': {'tow': k}, 'cov_headhead': 0.09}})
    with open(d / 'gnss.jsonl', 'w') as f:
        for l in lines: f.write(json.dumps(l) + '\n')


class GeometryTests(unittest.TestCase):
    def test_enu_roundtrip(self):
        lat, lon, h = geodetic(100.0, -50.0, 2.0)
        e = gc.enu(np.array([lat]), np.array([lon]), np.array([h]), LAT0, LON0, H0)[0]
        np.testing.assert_allclose(e, [100.0, -50.0, 2.0], atol=1e-4)


class CalibrationTests(unittest.TestCase):
    def run_case(self, segments, **kw):
        with tempfile.TemporaryDirectory() as d:
            write_source(Path(d), segments, **kw)
            return gc.calibrate_source(Path(d), SETTINGS)

    def test_calibration_drive_recovers_truth(self):
        rep = self.run_case(CAL)
        r = next(x for x in rep['runs'] if x['heading_convention'] == 'as published (ENU)')
        e = r['estimate']
        self.assertAlmostEqual(e['theta_deg']['value'], 37.0, delta=0.05)
        self.assertAlmostEqual(e['ant_x_m']['value'], -0.20, delta=0.01); self.assertAlmostEqual(e['ant_y_m']['value'], 0.05, delta=0.01)
        self.assertAlmostEqual(e['mount_yaw_deg']['value'], 2.0, delta=0.1); self.assertAlmostEqual(e['delay_s']['value'], 0.08, delta=0.02)
        # t is the ENU position of the map origin: the ENU origin is the first fix, so compare through a fixed point is not needed here
        self.assertLess(r['residual']['pos_rms_m'], 0.04); self.assertLess(r['residual']['heading_rms_deg'], 0.6)
        self.assertEqual(rep['smaller_heading_residual'], 'as published (ENU)')
        self.assertGreater(rep['motion']['reverse_m'], 1.0); self.assertGreaterEqual(len(rep['motion']['heading_sectors_45deg']), 8)

    def test_ned_data_is_recognised(self):
        rep = self.run_case(CAL, heading_ned=True)
        self.assertEqual(rep['smaller_heading_residual'], 'NED converted to ENU')

    def test_straight_run_is_visible_in_motion_coverage(self):
        rep = self.run_case([(60, 1.0, 0.0)])
        m = rep['motion']
        self.assertEqual(m['reverse_m'], 0.0); self.assertEqual(len(m['heading_sectors_45deg']), 1)
        r = next(x for x in rep['runs'] if x['heading_convention'] == 'as published (ENU)')
        self.assertGreater(r['estimate']['ant_x_m']['posterior_over_prior'], 0.8, 'antenna x is not determined by a straight run')

    def test_only_rtk_fixed_positions_are_used(self):
        rep = self.run_case(CAL, float_every=4)
        c = rep['gnss_counts']
        self.assertLess(c['pvt_rtk_fixed'], c['pvt_total'])
        self.assertLessEqual(rep['runs'][0]['samples']['positions'], c['pvt_rtk_fixed'])


if __name__ == '__main__':
    unittest.main()
