"""Figure: horizontal error vs time for full runs of candidates A and A3 (same rosbag, same map), with the LiDAR dropout marked.
usage: python3 plot_runs.py <ref_tum> <out.png> <run>:<label> [...] [--mark t_abs ...]"""
import sys, numpy as np, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
ref = np.loadtxt(sys.argv[1]); rt = ref[:, 0]; out = sys.argv[2]
args = sys.argv[3:]; marks = [float(x) for x in args[args.index('--mark') + 1:]] if '--mark' in args else []
runs = [a for a in (args[:args.index('--mark')] if '--mark' in args else args)]
fig, ax = plt.subplots(len(runs), 1, figsize=(10, 2.4 * len(runs)), sharex=True)
ax = np.atleast_1d(ax); t0 = None
for a, arg in zip(ax, runs):
    run, label = arg.split(':', 1); P = np.genfromtxt(run + '_pose.csv', delimiter=',', names=True)
    st = P['stamp']; k = np.clip(np.searchsorted(rt, st), 0, len(rt) - 1); ok = np.abs(rt[k] - st) < 1e-3
    e = np.hypot(P['x'][ok] - ref[k[ok], 1], P['y'][ok] - ref[k[ok], 2]); t0 = t0 or st[ok][0]
    a.plot(st[ok] - t0, e, lw=0.6, color='#2a6f97'); a.axhline(0.3, color='#c0392b', lw=0.8, ls='--'); a.set_ylim(0, max(0.6, float(np.percentile(e, 99.5)) * 1.2))
    for m in marks: a.axvline(m - t0, color='#e1a100', lw=1.0)
    a.set_ylabel('error [m]'); a.set_title(f'{label}: median {np.median(e):.3f} m, p95 {np.percentile(e,95):.3f} m, max {e.max():.3f} m', fontsize=9)
ax[-1].set_xlabel('time from the first pose [s] (dashed red: 0.3 m criterion; amber: LiDAR dropout)')
plt.tight_layout(); plt.savefig(out, dpi=110); print('wrote', out)
