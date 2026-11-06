"""Summarise xt32_fov.py output. usage: python3 -I xt32_fov_sum.py <fov.npz>
Vehicle azimuth (0 = forward, +90 = left) = sensor azimuth + 100 deg, from the /config of the recording
(lidar_axis_mapping "+x left, -y forward, +z up", lidar_mount_yaw_rad 0.1745; human input, not measured)."""
import sys, numpy as np
d = np.load(sys.argv[1]); elev, colaz, ret, near, maxr, gnd, meta = (d[k] for k in ('elev', 'colaz', 'ret', 'near', 'maxr', 'gnd', 'meta'))
NF = len(meta); OFF = 100.0
va = lambda a: (np.asarray(a) + OFF + 180) % 360 - 180
print(f'frames sampled {NF} (bag0 {int((meta[:,0]==0).sum())}, bag1 {int((meta[:,0]==1).sum())})')

print('\n== 1. beam elevation per ring (deg; median over frames of the per-frame median of returns 3..60 m; p5/p95 over frames)')
med = np.nanmedian(elev, 0); p5 = np.nanpercentile(elev, 5, 0); p95 = np.nanpercentile(elev, 95, 0)
for r in range(32): print(f'ring {r:2d}: {med[r]:+7.2f}  [{p5[r]:+7.2f} {p95[r]:+7.2f}]')
s = np.sort(med); print(f'lowest {s[0]:+.2f}, highest {s[-1]:+.2f}, span {s[-1]-s[0]:.2f}; spacing min {np.diff(s).min():.2f} max {np.diff(s).max():.2f} median {np.median(np.diff(s)):.2f}')

print('\n== 2. horizontal: column azimuth step and return ratio by vehicle azimuth')
ca = np.nanmedian(colaz, 0); st = np.diff(np.unwrap(np.radians(ca[np.isfinite(ca)])))
print(f'columns 2000, median step {np.degrees(np.median(np.abs(st))):.3f} deg, total span {np.degrees(np.abs(np.sum(st))):.1f} deg')
retf = ret.mean(0)                        # (2000 col, 32 ring) fraction of frames with a return
vb = va(ca); bins = np.arange(-180, 181, 10)
print('vehicle az bin: return ratio all rings / rings 16..31 (upper half by elevation) / lower 8 rings')
order = np.argsort(med); low8 = order[:8]; up16 = order[16:]
for lo in bins[:-1]:
    k = (vb >= lo) & (vb < lo + 10)
    if k.sum(): print(f'  {lo:+4d}..{lo+10:+4d}: {retf[k].mean():.3f}  {retf[k][:, up16].mean():.3f}  {retf[k][:, low8].mean():.3f}')

print('\n== 3. short-range returns (< 2 m): fraction of frames, by vehicle azimuth (10 deg) and range')
az, r3, el, rg = near.T
for lo in bins[:-1]:
    k = (va(az) >= lo) & (va(az) < lo + 10)
    h = [((r3[k] >= a) & (r3[k] < b)).sum() / NF for a, b in ((0, .5), (.5, 1), (1, 1.5), (1.5, 2))]
    if sum(h) > 0.5: print(f'  {lo:+4d}..{lo+10:+4d}: points/frame <0.5 {h[0]:7.1f}  0.5-1 {h[1]:7.1f}  1-1.5 {h[2]:7.1f}  1.5-2 {h[3]:7.1f}  min r {r3[k].min():.2f}  el {np.median(el[k]):+.1f}')
print(f'  smallest return range over all sampled frames {r3.min():.3f} m; returns < 0.5 m per frame {(r3 < .5).sum()/NF:.1f}')

print('\n== 4. range: per frame max, p99, p1 of returns; return ratio')
for i, n in enumerate(('max', 'p99', 'p1', 'return ratio')): print(f'  {n}: median {np.median(maxr[:,i]):.3f}  min {maxr[:,i].min():.3f}  max {maxr[:,i].max():.3f}')

print('\n== 5. ground: sensor height above the fitted plane and nearest ground return by vehicle azimuth')
h = meta[:, 2]; good = np.isfinite(h)
print(f'  planes {good.sum()}/{NF}; height median {np.nanmedian(h):.3f} m (p10 {np.nanpercentile(h,10):.3f}, p90 {np.nanpercentile(h,90):.3f})')
fi, gaz, grh, grg = gnd.T; fi = fi.astype(int); gv = va(gaz)
for lo in range(-180, 180, 30):
    vals = []
    for f in np.unique(fi):
        k = (fi == f) & (gv >= lo) & (gv < lo + 30)
        if k.sum() >= 20: vals.append(np.percentile(grh[k], 2))
    if vals: print(f'  {lo:+4d}..{lo+30:+4d}: nearest ground (p2 per frame) median {np.median(vals):.2f} m, p10 {np.percentile(vals,10):.2f}, p90 {np.percentile(vals,90):.2f}  (frames {len(vals)})')
lowest = s[0]; hm = np.nanmedian(h)
print(f'  calc: flat ground, no tilt: h / tan({-lowest:.2f} deg) = {hm/np.tan(np.radians(-lowest)):.2f} m')
for dd in (1.0, 1.5, 2.0, 2.5, 3.0, 4.0):
    print(f'  calc: lowest visible height at horizontal distance {dd} m = {hm + dd*np.tan(np.radians(lowest)):+.2f} m above ground; highest = {hm + dd*np.tan(np.radians(s[-1])):.2f} m')
