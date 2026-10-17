"""Compare a localizer's logged poses (eval_logger.py CSV) with the reference trajectory (GLIM traj_lidar.txt, TUM) of the same
LiDAR frame, optionally after a fixed map-to-map transform. Reports position/yaw error statistics against the acceptance
criteria (DEC-114: p95 position error <= 0.3 m, no divergence, a non-healthy flag whenever the error exceeds 0.5 m).
usage: python3 eval_compare.py <prefix> <ref_tum> [label] [base_yaw_in_lidar_deg=0]  (non-zero for poses of a forward-facing base frame at the LiDAR origin)"""
import sys, json, datetime, numpy as np

prefix, ref = sys.argv[1], sys.argv[2]; label = sys.argv[3] if len(sys.argv) > 3 else prefix
byaw = np.radians(float(sys.argv[4])) if len(sys.argv) > 4 else 0.0
P = np.genfromtxt(prefix + '_pose.csv', delimiter=',', names=True)
R = np.loadtxt(ref); rt = R[:, 0]


def yaw(q):  # q: (..., 4) xyzw
    x, y, z, w = q[..., 0], q[..., 1], q[..., 2], q[..., 3]
    return np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


st = P['stamp']; k = np.searchsorted(rt, st); k = np.clip(k, 0, len(rt) - 1)
ok = np.abs(rt[k] - st) < 1e-3
pe = np.c_[P['x'], P['y'], P['z']][ok]; re_ = R[k[ok], 1:4]
eh = np.linalg.norm(pe[:, :2] - re_[:, :2], axis=1); ez = np.abs(pe[:, 2] - re_[:, 2])
qy = yaw(np.c_[P['qx'], P['qy'], P['qz'], P['qw']][ok]); ry = yaw(R[k[ok], 4:8])
ey = np.degrees(np.abs((qy - ry - byaw + np.pi) % (2 * np.pi) - np.pi))
ts = st[ok]
print(f'== {label}: poses {len(P)}, matched to reference {ok.sum()} ({ts[0]-ts[0]:.0f}..{ts[-1]-ts[0]:.0f} s)')
if ok.sum() == 0: sys.exit()
print(f'  horizontal error: median {np.median(eh):.3f} m, p95 {np.percentile(eh,95):.3f} m, max {eh.max():.3f} m (at +{ts[np.argmax(eh)]-ts[0]:.1f} s); height error median {np.median(ez):.3f} m; yaw error median {np.median(ey):.2f} deg, p95 {np.percentile(ey,95):.2f} deg')
gaps = np.diff(ts); print(f'  pose output gaps > 0.5 s: {np.sum(gaps>0.5)} (max {gaps.max():.2f} s); pose rate {len(ts)/(ts[-1]-ts[0]):.2f} Hz')
# diagnostics -> a per-scan health category. A: /alignment_status failure_category. A3: ndt_scan_matcher scan_matching_status
# (level 0 = healthy; otherwise the message is reduced to keywords).
def a3_cat(msg):
    keys = [('exe time', 'slow'), ('iterations', 'iteration_limit'), ('oscillation', 'oscillation'), ('not activated', 'not_activated'),
            ('interpolate', 'no_initial_pose'), ('out of the map', 'out_of_map'), ('latency', 'latency'), ('score', 'low_score')]
    out = [k for s_, k in keys if s_ in msg.lower()]
    return '+'.join(out) if out else msg[:40]
cats = []
try:
    for l in open(prefix + '_diag.jsonl'):
        d = json.loads(l); v = d['values']
        if 'failure_category' in v: cats.append((d['t'], v['failure_category']))
        elif d['name'].endswith('scan_matching_status'): cats.append((d['t'], 'healthy' if d['level'] == 0 else a3_cat(d['message'])))
except FileNotFoundError:
    pass
if cats:
    ct = np.array([c[0] for c in cats]); cc = np.array([c[1] for c in cats])
    j = np.clip(np.searchsorted(ct, ts) - 1, 0, len(ct) - 1); flag = cc[j] != 'healthy'
    big = eh > 0.5
    u, n = np.unique(cc, return_counts=True); print('  health categories (per diagnostic message):', dict(zip(u.tolist(), n.tolist())))
    print(f'  errors > 0.5 m: {big.sum()} poses; flagged non-healthy among them: {np.sum(big & flag)}; non-healthy while error <= 0.5 m: {np.sum(~big & flag)} of {np.sum(~big)}')
crit = np.percentile(eh, 95) <= 0.3 and eh.max() < 2.0
print(f'  criteria: p95 <= 0.3 m: {"PASS" if np.percentile(eh,95) <= 0.3 else "FAIL"}; divergence (max error >= 2 m): {"none" if eh.max() < 2.0 else "YES"}')
