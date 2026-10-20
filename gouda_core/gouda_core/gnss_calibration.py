"""GNSS extrinsic calibration from a mapping run (REV-067, DEC-135: approved for now, to be verified on real data; dropped if it
does not estimate well). No ROS dependency; numpy only (no scipy on the vehicle PC).

Inputs of one registered source map (maps/<origin>/): gnss.jsonl (DEC-126), source/traj_lidar.txt (GLIM, loop-closure corrected,
TUM: stamp x y z qx qy qz qw of the LiDAR in the map frame) and sensor_config.json (the /config of the run, for base_link ->
xt32_link and the antenna position prior). Method (design/research/gnss_calibration_research_2026-10-18.md, proposal
gnss_initial_pose_design.md §11): one robust batch least squares of
  theta, t      map -> local ENU (yaw and translation; scale 1)
  ant_x, ant_y  main antenna in base_link (ant_z is fixed to /config: it is not observable on flat ground)
  mount_yaw     remaining yaw between the receiver heading and base_link
  delay         GNSS time stamps late by delay
with priors on the antenna position and mount_yaw, Huber loss, the delay started from a 1-D heading search (without it the solver
stayed in a wrong minimum: FILE-GNSS-CALIB-FEASIBILITY). Both heading conventions are solved (as ENU, and as NED converted to
ENU) because the driver's AttEuler convention is not confirmed (proposal §10); the heading residual tells which one is right.
Observability is reported two ways: posterior / prior std, and the motion actually driven (heading range, reverse distance,
turns in both directions), because the std alone misjudged a straight run (feasibility S1).
Selection: RTK fixed positions (PVTGeodetic mode type 4) and fixed attitude (AttEuler mode 2 or 4), as in the reference spec §7.
Accuracy thresholds, sample spacing and the judgement values are unresolved: the caller passes them, the report records them.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from gouda_core import sensor_extrinsics as se

WGS84_A, WGS84_F = 6378137.0, 1 / 298.257223563
PVT_RTK_FIXED = 4                      # SBF PVTGeodetic mode type: RTK with fixed ambiguities (原本未照合: SBF reference)
ATT_FIXED = (2, 4)                     # SBF AttEuler mode: heading with fixed ambiguities (原本未照合)
SBF_DNU = -2e10                        # SBF do-not-use value of float fields
NAMES = ['theta_deg', 'tx_m', 'ty_m', 'tz_m', 'ant_x_m', 'ant_y_m', 'mount_yaw_deg', 'delay_s']


# ---------------------------------------------------------------------------------------------------------- geometry
def ecef(lat, lon, h):
    e2 = WGS84_F * (2 - WGS84_F)
    n = WGS84_A / np.sqrt(1 - e2 * np.sin(lat) ** 2)
    return np.c_[(n + h) * np.cos(lat) * np.cos(lon), (n + h) * np.cos(lat) * np.sin(lon), (n * (1 - e2) + h) * np.sin(lat)]


def enu(lat, lon, h, lat0, lon0, h0):
    """Local ENU (m) of geodetic points (rad, rad, m ellipsoidal) around the reference point (no projection: spec §3)."""
    d = ecef(lat, lon, h) - ecef(np.array([lat0]), np.array([lon0]), np.array([h0]))
    sl, cl, sp, cp = math.sin(lon0), math.cos(lon0), math.sin(lat0), math.cos(lat0)
    r = np.array([[-sl, cl, 0], [-sp * cl, -sp * sl, cp], [cp * cl, cp * sl, sp]])
    return d @ r.T


def wrap(a):
    return np.arctan2(np.sin(a), np.cos(a))


def quat_to_rot(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


# ---------------------------------------------------------------------------------------------------------- inputs
@dataclass
class GnssData:
    t_pos: np.ndarray            # PVT time (s, header stamp)
    lat: np.ndarray              # rad
    lon: np.ndarray
    h: np.ndarray                # m (ellipsoidal)
    h_acc: np.ndarray            # m (PVTGeodetic h_accuracy; nan when do-not-use)
    t_head: np.ndarray
    heading_deg: np.ndarray      # as published by the driver (convention to be confirmed)
    head_std_deg: np.ndarray     # from AttCovEuler cov_headhead (nan when missing)
    counts: dict = field(default_factory=dict)


def _stamp(m):
    s = m.get('header', {}).get('stamp', {})
    return s.get('sec', 0) + s.get('nanosec', 0) * 1e-9


def load_gnss(path: Path) -> GnssData:
    pos, head, cov = [], {}, {}
    counts = {'pvt_total': 0, 'pvt_rtk_fixed': 0, 'att_total': 0, 'att_fixed': 0}
    with open(path, encoding='utf-8') as f:
        for line in f:
            d = json.loads(line); m = d.get('msg', {}); topic = d.get('topic', '')
            if topic.endswith('pvtgeodetic'):
                counts['pvt_total'] += 1
                if int(m.get('mode', 0)) & 0x0F == PVT_RTK_FIXED and m.get('latitude', SBF_DNU) > SBF_DNU / 2:
                    counts['pvt_rtk_fixed'] += 1
                    acc = m.get('h_accuracy', 0xFFFF)
                    pos.append((_stamp(m), m['latitude'], m['longitude'], m['height'], np.nan if acc == 0xFFFF else acc / 100))
            elif topic.endswith('atteuler'):
                counts['att_total'] += 1
                if int(m.get('mode', 0)) in ATT_FIXED and m.get('heading', SBF_DNU) > SBF_DNU / 2:
                    counts['att_fixed'] += 1
                    tow = m.get('block_header', {}).get('tow')
                    head[(tow, _stamp(m))] = m['heading']
            elif topic.endswith('attcoveuler'):
                tow = m.get('block_header', {}).get('tow')
                c = m.get('cov_headhead', SBF_DNU)
                if c > SBF_DNU / 2: cov[tow] = math.sqrt(max(c, 0.0))
    p = np.array(pos) if pos else np.zeros((0, 5))
    hk = sorted(head, key=lambda k: k[1])
    return GnssData(p[:, 0], p[:, 1], p[:, 2], p[:, 3], p[:, 4], np.array([k[1] for k in hk]), np.array([head[k] for k in hk]),
                    np.array([cov.get(k[0], np.nan) for k in hk]), counts)


def load_traj(path: Path):
    """TUM rows (stamp, x, y, z, qx, qy, qz, qw) of the LiDAR in the map frame."""
    a = np.loadtxt(path, ndmin=2)
    return a[np.argsort(a[:, 0])]


def base_trajectory(traj: np.ndarray, config_values: dict):
    """(t, xyz (N,3), R (N,3,3), yaw (N,)) of base_link in the map frame: T_map_base = T_map_lidar x inv(T_base_lidar)."""
    r_bl, t_bl, _, _ = se.sensor_pose(config_values, 'lidar')
    r_bl = np.array(r_bl); t_bl = np.array(t_bl)
    r_lb = r_bl.T; t_lb = -r_lb @ t_bl
    R = np.array([quat_to_rot(q) @ r_lb for q in traj[:, 4:8]])
    p = traj[:, 1:4] + np.einsum('nij,j->ni', np.array([quat_to_rot(q) for q in traj[:, 4:8]]), t_lb)
    yaw = np.unwrap(np.arctan2(R[:, 1, 0], R[:, 0, 0]))
    return traj[:, 0], p, R, yaw


# ---------------------------------------------------------------------------------------------------------- solver
@dataclass
class Settings:
    sig_pos_m: float                 # GNSS position noise used to weight (tbd: the caller passes it)
    sig_head_deg: float              # GNSS heading noise
    sig_ant_prior_m: float           # prior std of the /config antenna position
    sig_mount_prior_deg: float       # prior std of mount_yaw (prior 0)
    sig_delay_prior_s: float         # prior std of the delay (prior 0)
    delay_search_s: float            # half range of the 1-D delay search
    delay_step_s: float
    huber_k: float                   # Huber threshold in normalised units
    max_iter: int = 50


def _interp_base(tq, bt, bp, byaw, bR):
    """base_link position, yaw and rotation at times tq (linear; rotation of the nearest earlier pose)."""
    p = np.c_[[np.interp(tq, bt, bp[:, k]) for k in range(3)]].T
    yaw = np.interp(tq, bt, byaw)
    idx = np.clip(np.searchsorted(bt, tq) - 1, 0, len(bt) - 1)
    return p, yaw, bR[idx]


def solve(g: GnssData, base, ant_prior, s: Settings, heading_ned: bool) -> dict:
    bt, bp, bR, byaw = base
    inside_p = (g.t_pos > bt[0]) & (g.t_pos < bt[-1]); inside_h = (g.t_head > bt[0]) & (g.t_head < bt[-1])
    tp, th = g.t_pos[inside_p], g.t_head[inside_h]
    if len(tp) < 3 or len(th) < 3:
        return {'ok': False, 'reason': f'too few samples inside the trajectory (positions {len(tp)}, headings {len(th)})'}
    lat0, lon0, h0 = g.lat[inside_p][0], g.lon[inside_p][0], g.h[inside_p][0]
    pe = enu(g.lat[inside_p], g.lon[inside_p], g.h[inside_p], lat0, lon0, h0)
    hd = np.radians(g.heading_deg[inside_h])
    psi = wrap(np.pi / 2 - hd) if heading_ned else wrap(hd)
    lz = ant_prior[2]

    def model(x):
        th_, tx, ty, tz, ax, ay, pm, dl = x
        p, _, R = _interp_base(tp - dl, bt, bp, byaw, bR)
        am = p + np.einsum('nij,j->ni', R, np.array([ax, ay, lz]))
        c, sn = math.cos(th_), math.sin(th_)
        pred = np.c_[c * am[:, 0] - sn * am[:, 1] + tx, sn * am[:, 0] + c * am[:, 1] + ty, am[:, 2] + tz]
        _, yh, _ = _interp_base(th - dl, bt, bp, byaw, bR)
        r = [((pred - pe) / s.sig_pos_m).ravel(), wrap(psi - yh - th_ - pm) / math.radians(s.sig_head_deg),
             (np.array([ax, ay]) - ant_prior[:2]) / s.sig_ant_prior_m, [pm / math.radians(s.sig_mount_prior_deg)], [dl / s.sig_delay_prior_s]]
        return np.concatenate(r)

    # start values: theta / t by 2-D Kabsch on positions, delay by the heading search
    p0, _, _ = _interp_base(tp, bt, bp, byaw, bR)
    A, B = p0[:, :2] - p0[:, :2].mean(0), pe[:, :2] - pe[:, :2].mean(0)
    th0 = math.atan2(float((A[:, 0] * B[:, 1] - A[:, 1] * B[:, 0]).sum()), float((A * B).sum()))
    c, sn = math.cos(th0), math.sin(th0)
    t0 = pe.mean(0) - np.array([c * p0[:, 0].mean() - sn * p0[:, 1].mean(), sn * p0[:, 0].mean() + c * p0[:, 1].mean(), p0[:, 2].mean() + lz])
    grid = np.arange(-s.delay_search_s, s.delay_search_s + s.delay_step_s / 2, s.delay_step_s)
    def spread(dl):
        _, yh, _ = _interp_base(th - dl, bt, bp, byaw, bR)
        e = wrap(psi - yh - th0); return float(np.mean(wrap(e - math.atan2(np.sin(e).mean(), np.cos(e).mean())) ** 2))
    d0 = float(grid[int(np.argmin([spread(d) for d in grid]))])
    x = np.array([th0, *t0, ant_prior[0], ant_prior[1], 0.0, d0])

    # Levenberg-Marquardt with Huber weights (IRLS) and a numerical Jacobian
    lam = 1e-3
    def cost(x):
        r = model(x); a = np.abs(r); w = np.where(a <= s.huber_k, 1, s.huber_k / np.maximum(a, 1e-12))
        return r, w, float(np.sum(np.where(a <= s.huber_k, r * r, 2 * s.huber_k * a - s.huber_k ** 2)))
    r, w, f = cost(x)
    for _ in range(s.max_iter):
        J = np.empty((len(r), len(x)))
        for k in range(len(x)):
            dx = np.zeros(len(x)); dx[k] = 1e-6 * max(1, abs(x[k])); J[:, k] = (model(x + dx) - r) / dx[k]
        Jw = J * w[:, None]
        H = J.T @ Jw; g_ = J.T @ (w * r)
        step = -np.linalg.solve(H + lam * np.diag(np.diag(H)), g_)
        r2, w2, f2 = cost(x + step)
        if f2 < f:
            x, r, w, f, lam = x + step, r2, w2, f2, lam / 3
            if np.max(np.abs(step)) < 1e-9: break
        else:
            lam *= 4
    J = np.empty((len(r), len(x)))
    for k in range(len(x)):
        dx = np.zeros(len(x)); dx[k] = 1e-6 * max(1, abs(x[k])); J[:, k] = (model(x + dx) - r) / dx[k]
    std = np.sqrt(np.diag(np.linalg.pinv(J.T @ (J * w[:, None]))))
    n_pos = len(tp) * 3
    res_pos = r[:n_pos].reshape(-1, 3) * s.sig_pos_m
    res_head = r[n_pos:n_pos + len(th)] * s.sig_head_deg
    prior_std = {'ant_x_m': s.sig_ant_prior_m, 'ant_y_m': s.sig_ant_prior_m, 'mount_yaw_deg': s.sig_mount_prior_deg, 'delay_s': s.sig_delay_prior_s}
    out = {}
    for i, n in enumerate(NAMES):
        v, sd = (math.degrees(x[i]), math.degrees(std[i])) if n.endswith('_deg') else (float(x[i]), float(std[i]))
        e = {'value': v, 'std': sd}
        if n in prior_std: e['posterior_over_prior'] = sd / prior_std[n]
        out[n] = e
    return {'ok': True, 'heading_convention': 'NED converted to ENU' if heading_ned else 'as published (ENU)', 'enu_origin': {'lat_rad': lat0, 'lon_rad': lon0, 'h_m': h0},
            'samples': {'positions': len(tp), 'headings': len(th)}, 'estimate': out, 'ant_z_fixed_m': lz, 'delay_start_s': d0,
            'residual': {'pos_rms_m': float(np.sqrt(np.mean(np.sum(res_pos[:, :2] ** 2, 1)))), 'pos_max_m': float(np.max(np.hypot(res_pos[:, 0], res_pos[:, 1]))),
                         'z_rms_m': float(np.sqrt(np.mean(res_pos[:, 2] ** 2))), 'heading_rms_deg': float(np.sqrt(np.mean(res_head ** 2)))}}


def motion_coverage(base) -> dict:
    """What was driven: heading range (8 sectors of 45 degrees visited), reverse distance, turning in both directions."""
    bt, bp, bR, byaw = base
    d = np.diff(bp[:, :2], axis=0); fwd = np.c_[np.cos(byaw[:-1]), np.sin(byaw[:-1])]
    along = np.sum(d * fwd, 1); dyaw = np.diff(byaw)
    sectors = sorted(set(int(v) for v in np.floor(np.mod(byaw, 2 * np.pi) / (np.pi / 4))))
    return {'duration_s': float(bt[-1] - bt[0]), 'path_m': float(np.sum(np.hypot(d[:, 0], d[:, 1]))), 'forward_m': float(along[along > 0].sum()),
            'reverse_m': float(-along[along < 0].sum()), 'turn_left_deg': float(np.degrees(dyaw[dyaw > 0].sum())),
            'turn_right_deg': float(np.degrees(-dyaw[dyaw < 0].sum())), 'heading_sectors_45deg': sectors}


def calibrate_source(source_map_dir: Path, s: Settings, config_values: Optional[dict] = None) -> dict:
    """Run both heading conventions on one registered source map; the caller writes the report."""
    d = Path(source_map_dir)
    if config_values is None:
        cfg = d / 'sensor_config.json'
        config_values = json.loads(cfg.read_text(encoding='utf-8')).get('values', {}) if cfg.is_file() else {}
    g = load_gnss(d / 'gnss.jsonl')
    base = base_trajectory(load_traj(d / 'source' / 'traj_lidar.txt'), config_values)
    ap, defaulted = se.antenna_position(config_values, 'gnss_main')
    runs = [solve(g, base, np.array(ap), s, heading_ned=False), solve(g, base, np.array(ap), s, heading_ned=True)]
    ok = [r for r in runs if r.get('ok')]
    better = min(ok, key=lambda r: r['residual']['heading_rms_deg'])['heading_convention'] if ok else None
    return {'source_map': str(d), 'settings': s.__dict__, 'gnss_counts': g.counts, 'antenna_prior_m': list(ap), 'antenna_prior_unknown_fields': defaulted,
            'motion': motion_coverage(base), 'runs': runs, 'smaller_heading_residual': better,
            'note': 'judgement values are unresolved (proposal §11.3); this report is the material for them and for the go / no-go of DEC-135'}


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description='GNSS extrinsic calibration of one source map (DEC-135 verification tool)')
    ap.add_argument('source_map_dir'); ap.add_argument('--out', required=True)
    for k in ('sig_pos_m', 'sig_head_deg', 'sig_ant_prior_m', 'sig_mount_prior_deg', 'sig_delay_prior_s', 'delay_search_s', 'delay_step_s', 'huber_k'):
        ap.add_argument('--' + k, type=float, required=True)   # no defaults: unresolved values are given by the person running it
    a = ap.parse_args(argv)
    s = Settings(**{k: getattr(a, k) for k in ('sig_pos_m', 'sig_head_deg', 'sig_ant_prior_m', 'sig_mount_prior_deg', 'sig_delay_prior_s', 'delay_search_s', 'delay_step_s', 'huber_k')})
    rep = calibrate_source(Path(a.source_map_dir), s)
    Path(a.out).write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=float) + '\n', encoding='utf-8')
    for r in rep['runs']:
        if not r.get('ok'): print(r.get('heading_convention', ''), r['reason']); continue
        print(f"[{r['heading_convention']}] samples {r['samples']} residual {r['residual']}")
        for n, e in r['estimate'].items(): print(f"  {n:14s} {e['value']:12.4f}  std {e['std']:.4f}" + (f"  post/prior {e['posterior_over_prior']:.2f}" if 'posterior_over_prior' in e else ''))
    print('motion', rep['motion']); print('smaller heading residual:', rep['smaller_heading_residual'])


if __name__ == '__main__':
    main()
