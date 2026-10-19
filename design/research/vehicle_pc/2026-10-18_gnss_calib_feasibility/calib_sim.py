"""Analysis tool (not product code; DEC-132 re-examination, 2026-10-18): can the GNSS extrinsics be calibrated in software on
Gouda's data? Synthetic data only. The reference poses stand for the corrected GLIM trajectory of a mapping run (base_link in
the map frame), because ND-07 (NDT) does not exist yet; the method is the joint batch least squares of the research note
(design/research/gnss_calibration_research_2026-10-18.md): theta / t (map -> ENU, T1), lever arm l, mount yaw psi_m, time delay dt,
with priors on l and psi_m, Huber loss, and observability from the posterior std compared with the prior std.
Every number here is a SYNTHETIC test value (truth, noise, priors), not a vehicle value.
usage: /opt/anaconda3/bin/python3 calib_sim.py   (numpy, scipy)"""
import numpy as np
from scipy.optimize import least_squares

rng = np.random.default_rng(1)
NAMES = ['theta_deg', 'tx', 'ty', 'tz', 'ant_x', 'ant_y', 'ant_z', 'mount_yaw_deg', 'delay_s']
TRUTH = np.array([np.radians(37.0), 120.0, -45.0, 3.0, -0.20, 0.05, 0.85, np.radians(2.0), 0.08])
PRIOR_L, SIG_L = TRUTH[4:7] + np.array([0.03, -0.03, 0.02]), np.array([0.05, 0.05, 0.05])    # /config value with error
PRIOR_PSI, SIG_PSI = 0.0, np.radians(3.0)
PRIOR_DT, SIG_DT = 0.0, 0.2
SIG_POS, SIG_YAW = 0.015, np.radians(0.3)       # GNSS noise (synthetic)
REF_POS, REF_YAW = 0.02, np.radians(0.2)        # reference-trajectory noise (synthetic)


def wrap(a):
    return np.arctan2(np.sin(a), np.cos(a))


def drive(segments, dt=0.01):
    """Differential drive on flat ground: segments of (duration s, v m/s, w rad/s). Returns t, x, y, yaw at 100 Hz."""
    t, x, y, th = [0.0], [0.0], [0.0], [0.0]
    for dur, v, w in segments:
        for _ in range(int(round(dur / dt))):
            th.append(th[-1] + w * dt); x.append(x[-1] + v * np.cos(th[-1]) * dt); y.append(y[-1] + v * np.sin(th[-1]) * dt); t.append(t[-1] + dt)
    return np.array(t), np.array(x), np.array(y), np.array(th)


SCENARIOS = {
    'S1 一方向の直線だけ（一定速度）': [(120, 1.0, 0.0)],
    'S2 通常のコース（前進だけ、緩い曲がり、一定速度）': [(30, 1.0, 0.0), (15, 1.0, 0.1), (30, 1.0, 0.0), (15, 1.0, -0.1), (30, 1.0, 0.0)],
    'S3 較正の走行（8 の字、その場旋回、前進と後退、速度の変化、複数の向きで静止）': (
        [(10, 0.0, 0.0)] + [(31.4, 0.8, 0.2)] + [(31.4, 0.8, -0.2)] + [(8, 0.0, 0.8)] + [(10, 0.0, 0.0)] + [(8, 0.0, -0.8)]
        + [(10, 1.2, 0.0), (10, -0.6, 0.0), (10, 0.4, 0.0), (5, 0.0, 0.0), (4, 0.0, 0.8), (5, 0.0, 0.0), (4, 0.0, 0.8), (5, 0.0, 0.0)]),
}


def observations(t, x, y, th, heading_ned=False):
    """GNSS at 10 Hz: antenna position in ENU and heading, delayed by the true dt; reference poses (GLIM-like) at 10 Hz."""
    th_m, tx, ty, tz, lx, ly, lz, psi_m, delay = TRUTH
    idx = np.arange(0, len(t), 10)
    ts = t[idx]
    # truth at (ts - delay): the GNSS sample stamped ts describes the vehicle delay seconds earlier
    xd, yd, thd = np.interp(ts - delay, t, x), np.interp(ts - delay, t, y), np.interp(ts - delay, t, np.unwrap(th))
    ant_map = np.c_[xd + np.cos(thd) * lx - np.sin(thd) * ly, yd + np.sin(thd) * lx + np.cos(thd) * ly, np.full_like(xd, lz)]
    c, s = np.cos(th_m), np.sin(th_m)
    p_enu = np.c_[c * ant_map[:, 0] - s * ant_map[:, 1] + tx, s * ant_map[:, 0] + c * ant_map[:, 1] + ty, ant_map[:, 2] + tz] + rng.normal(0, SIG_POS, (len(ts), 3))
    psi_enu = wrap(thd + th_m + psi_m + rng.normal(0, SIG_YAW, len(ts)))
    if heading_ned:   # a convention mistake: NED heading (north 0, clockwise) used as ENU
        psi_enu = wrap(np.pi / 2 - psi_enu)
    ref = (t, x + rng.normal(0, REF_POS, len(t)), y + rng.normal(0, REF_POS, len(t)), np.unwrap(th) + rng.normal(0, REF_YAW, len(t)))
    return ts, p_enu, psi_enu, ref


def calibrate(ts, p_enu, psi_enu, ref, with_delay=True):
    rt, rx, ry, rth = ref

    def fun(p):
        th_m, tx, ty, tz, lx, ly, lz, psi_m, delay = p if with_delay else (*p, 0.0)
        bx, by, bth = np.interp(ts - delay, rt, rx), np.interp(ts - delay, rt, ry), np.interp(ts - delay, rt, rth)
        am = np.c_[bx + np.cos(bth) * lx - np.sin(bth) * ly, by + np.sin(bth) * lx + np.cos(bth) * ly, np.full_like(bx, lz)]
        c, s = np.cos(th_m), np.sin(th_m)
        pred = np.c_[c * am[:, 0] - s * am[:, 1] + tx, s * am[:, 0] + c * am[:, 1] + ty, am[:, 2] + tz]
        r = [((pred - p_enu) / SIG_POS).ravel(), wrap(psi_enu - bth - th_m - psi_m) / SIG_YAW,
             (np.array([lx, ly, lz]) - PRIOR_L) / SIG_L, [wrap(psi_m - PRIOR_PSI) / SIG_PSI]]
        if with_delay: r.append([(delay - PRIOR_DT) / SIG_DT])
        return np.concatenate(r)

    # T1 start value from positions only (Kabsch on 2D), as the research note does
    x0 = np.r_[0.0, p_enu[:, 0].mean(), p_enu[:, 1].mean(), p_enu[:, 2].mean(), PRIOR_L, PRIOR_PSI, PRIOR_DT]
    bx, by = np.interp(ts, rt, rx), np.interp(ts, rt, ry)
    A, B = np.c_[bx, by] - [bx.mean(), by.mean()], p_enu[:, :2] - p_enu[:, :2].mean(0)
    x0[0] = np.arctan2((A[:, 0] * B[:, 1] - A[:, 1] * B[:, 0]).sum(), (A * B).sum())
    c, s = np.cos(x0[0]), np.sin(x0[0]); x0[1:3] = p_enu[:, :2].mean(0) - [c * bx.mean() - s * by.mean(), s * bx.mean() + c * by.mean()]
    if with_delay:
        # Start value of the delay from a 1-D search on the heading (in turns a delay is a large heading error that the Huber
        # loss would treat as outliers; starting at 0 the solver stayed in a wrong minimum: first run of this tool, 2026-10-18)
        grid = np.arange(-0.3, 0.3001, 0.005)
        cost = [np.mean(wrap(psi_enu - np.interp(ts - d, rt, rth) - x0[0]) ** 2 - np.mean(wrap(psi_enu - np.interp(ts - d, rt, rth) - x0[0])) ** 2) for d in grid]
        x0[8] = grid[int(np.argmin(cost))]
    else:
        x0 = x0[:-1]
    res = least_squares(fun, x0, loss='huber', f_scale=3.0)
    std = np.sqrt(np.diag(np.linalg.inv(res.jac.T @ res.jac)))
    yaw_res = wrap(psi_enu - np.interp(ts - (res.x[8] if with_delay else 0), rt, rth) - res.x[0] - res.x[7])
    return res.x, std, np.degrees(np.sqrt(np.mean(yaw_res ** 2)))


def report(name, est, std):
    prior = {'ant_x': SIG_L[0], 'ant_y': SIG_L[1], 'ant_z': SIG_L[2], 'mount_yaw_deg': SIG_PSI, 'delay_s': SIG_DT}
    print(f'  {"param":14s} {"truth":>9s} {"estimate":>9s} {"error":>8s} {"std":>8s}  judgement')
    for i, n in enumerate(NAMES[:len(est)]):
        k = np.degrees if n.endswith('deg') else (lambda v: v)
        tr, e, s = k(TRUTH[i]), k(est[i]), k(std[i])
        flag = ''
        if n in prior and std[i] > 0.8 * prior[n]: flag = 'データからほぼ決まらない（事前の値のまま）'
        print(f'  {n:14s} {tr:9.4f} {e:9.4f} {e - tr:8.4f} {s:8.4f}  {flag}')


if __name__ == '__main__':
    for name, seg in SCENARIOS.items():
        t, x, y, th = drive(seg)
        ts, p, psi, ref = observations(t, x, y, th)
        est, std, yrms = calibrate(ts, p, psi, ref)
        print(f'== {name}: {len(ts)} samples, path {np.hypot(np.diff(x), np.diff(y)).sum():.0f} m; heading residual RMS {yrms:.2f} deg')
        report(name, est, std)
    print('== S3 with the heading convention mistaken (NED used as ENU): the heading residual exposes it')
    t, x, y, th = drive(SCENARIOS['S3 較正の走行（8 の字、その場旋回、前進と後退、速度の変化、複数の向きで静止）'])
    ts, p, psi, ref = observations(t, x, y, th, heading_ned=True)
    est, std, yrms = calibrate(ts, p, psi, ref)
    print(f'  heading residual RMS {yrms:.1f} deg (correct convention: about the GNSS heading noise)')
