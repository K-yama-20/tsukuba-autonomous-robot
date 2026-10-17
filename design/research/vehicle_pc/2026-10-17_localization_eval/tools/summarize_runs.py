"""Summary table of localization evaluation runs (eval_logger.py outputs) against the GLIM reference trajectory.
Acceptance criteria (DEC-114): p95 horizontal error <= 0.3 m, no divergence (max error < 2 m after convergence), and a non-healthy
flag whenever the error exceeds 0.5 m. Convergence for perturbed starts: first time the error stays below 0.3 m for 5 s.
usage: python3 summarize_runs.py <ref_tum> <run>:<kind A|A3> [...]"""
import sys, json, numpy as np

ref = np.loadtxt(sys.argv[1]); rt = ref[:, 0]


def yaw(q):
    x, y, z, w = q[..., 0], q[..., 1], q[..., 2], q[..., 3]
    return np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


def a3_cat(msg):
    keys = [('exe time', 'slow'), ('iterations', 'iteration_limit'), ('oscillation', 'oscillation'), ('not activated', 'not_activated'),
            ('interpolate', 'no_initial_pose'), ('out of the map', 'out_of_map'), ('latency', 'latency'), ('score', 'low_score')]
    out = [k for s_, k in keys if s_ in msg.lower()]
    return '+'.join(out) if out else msg[:40]


rows = []
for arg in sys.argv[2:]:
    run, kind = arg.split(':'); byaw = np.radians(-99.2) if kind == 'A3' else 0.0
    P = np.genfromtxt(run + '_pose.csv', delimiter=',', names=True)
    st = P['stamp']; k = np.clip(np.searchsorted(rt, st), 0, len(rt) - 1); ok = np.abs(rt[k] - st) < 1e-3
    st = st[ok]; k = k[ok]; pe = np.c_[P['x'], P['y']][ok]
    if len(st) == 0:
        rows.append(dict(run=run, kind=kind, n=0)); continue
    eh = np.linalg.norm(pe - ref[k, 1:3], axis=1)
    ey = np.degrees(np.abs((yaw(np.c_[P['qx'], P['qy'], P['qz'], P['qw']][ok]) - yaw(ref[k, 4:8]) - byaw + np.pi) % (2 * np.pi) - np.pi))
    t = st - st[0]
    # convergence: first index after which error < 0.3 m for 5 s
    conv = None
    for i in range(len(t)):
        w = (t >= t[i]) & (t <= t[i] + 5)
        if np.all(eh[w] < 0.3): conv = i; break
    after = slice(conv, None) if conv is not None else slice(0, 0)
    # health per scan
    cats = []
    for l in open(run + '_diag.jsonl'):
        d = json.loads(l); v = d['values']
        if 'failure_category' in v: cats.append((float(v.get('scan_stamp', 'nan') or 'nan'), d['t'], v['failure_category'], float(v.get('alignment_time_sec', 'nan') or 'nan')))
        elif d['name'].endswith('scan_matching_status'):
            cats.append((float(v.get('topic_time_stamp', 'nan') or 'nan'), d['t'], 'healthy' if d['level'] == 0 else a3_cat(d['message']), float(v.get('execution_time', 'nan') or 'nan') / 1000))
    ct = np.array([c[1] for c in cats]); cc = np.array([c[2] for c in cats]); ex = np.array([c[3] for c in cats]); ex = ex[np.isfinite(ex)]
    j = np.clip(np.searchsorted(ct, st) - 1, 0, max(len(ct) - 1, 0)); flag = cc[j] != 'healthy' if len(ct) else np.zeros(len(st), bool)
    big = eh > 0.5
    cl = [l.split() for l in open(run + '_cpu.txt') if l.strip()]
    cpu = np.array([[float(x[-2]), float(x[-1])] for x in cl if len(x) == 3 or (len(x) == 4 and x[1] == 'ndt')]) if cl else np.zeros((0, 2))
    if cpu.size == 0: cpu = np.zeros((0, 2))
    rows.append(dict(run=run, kind=kind, n=len(st), dur=t[-1] if len(t) else 0, rate=len(st) / max(t[-1], 1e-9),
                     med=np.median(eh), p95=np.percentile(eh, 95), mx=eh.max(), conv=(t[conv] if conv is not None else None),
                     p95a=(np.percentile(eh[after], 95) if conv is not None else np.nan), mxa=(eh[after].max() if conv is not None else np.nan),
                     ymed=np.median(ey), big=int(big.sum()), big_flag=int((big & flag).sum()), small_flag=int((~big & flag).sum()),
                     gap=(np.diff(st).max() if len(st) > 1 else np.nan), ex50=np.median(ex) * 1000 if len(ex) else np.nan,
                     ex95=np.percentile(ex, 95) * 1000 if len(ex) else np.nan, cpu=np.median(cpu[:, 0]) if len(cpu) else np.nan,
                     rss=np.max(cpu[:, 1]) / 1024 if len(cpu) else np.nan,
                     cats=dict(zip(*np.unique(cc, return_counts=True))) if len(cc) else {}))
print('| run | kind | poses | span s | rate Hz | err med m | err p95 m | err max m | converged at s | p95 after conv | max after conv | yaw med deg | poses err>0.5 | flagged among them | flagged while err<=0.5 | max gap s | proc med/p95 ms | CPU % med (A3: NDT) | RSS MB max (A3: NDT) |')
print('|' + '---|' * 19)
for r in rows:
    if r['n'] == 0:
        print(f"| {r['run']} | {r['kind']} | 0 | no pose output |" + ' |' * 15); continue
    conv = f"{r['conv']:.1f}" if r['conv'] is not None else 'never'
    print(f"| {r['run']} | {r['kind']} | {r['n']} | {r['dur']:.0f} | {r['rate']:.2f} | {r['med']:.3f} | {r['p95']:.3f} | {r['mx']:.3f} | {conv} | {r['p95a']:.3f} | {r['mxa']:.3f} | {r['ymed']:.2f} | {r['big']} | {r['big_flag']} | {r['small_flag']} | {r['gap']:.2f} | {r['ex50']:.0f}/{r['ex95']:.0f} | {r['cpu']:.0f} | {r['rss']:.0f} |")
print()
for r in rows:
    if r['n']: print(r['run'], {str(k): int(v) for k, v in r['cats'].items()})
