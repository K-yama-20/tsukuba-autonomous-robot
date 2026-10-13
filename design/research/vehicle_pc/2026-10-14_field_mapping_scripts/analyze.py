import sys, numpy as np
sys.path.insert(0, '/Users/AYARyoya/Desktop/自己学習/TsukubaChallenge/tsukuba-autonomous-robot/gouda_core')
from gouda_core import map_convert as mc
T = np.loadtxt('source/traj_lidar.txt'); t, P = T[:, 0] - T[0, 0], T[:, 1:4]
xy = P[:, :2]
c = xy.mean(0); U, S, Vt = np.linalg.svd(xy - c, full_matrices=False); ax = Vt[0]; ax = ax if ax[0] >= 0 else -ax; lat = np.array([-ax[1], ax[0]])
u = (xy - c) @ ax; v = (xy - c) @ lat
print('trajectory: frames %d, span %.0f s' % (len(t), t[-1]))
print('extent along axis %.2f m (u %.2f..%.2f), lateral std %.2f m (range %.2f..%.2f), z range %.2f..%.2f m' % (u.max()-u.min(), u.min(), u.max(), v.std(), v.min(), v.max(), P[:,2].min(), P[:,2].max()))
steps = np.linalg.norm(np.diff(P, axis=0), axis=1); print('path length %.1f m; start-end distance %.2f m; max step %.2f m (at t=%.1f s)' % (steps.sum(), np.linalg.norm(P[-1]-P[0]), steps.max(), t[np.argmax(steps)+1]))
# legs: smooth u and find turnarounds
k = 15; us = np.convolve(u, np.ones(k)/k, mode='same')
d = np.sign(np.diff(us)); turns = [i for i in range(1, len(d)) if d[i] != d[i-1] and d[i] != 0]
# keep turnarounds separated by > 10 s and > 3 m of travel
legs = [0]
for i in turns:
    if t[i] - t[legs[-1]] > 10 and abs(us[i] - us[legs[-1]]) > 3: legs.append(i)
legs.append(len(t) - 1)
print('legs (time s, along-axis u m):', [(round(t[i], 1), round(u[i], 2)) for i in legs])
for a, b in zip(legs[:-1], legs[1:]):
    seg = slice(a, b + 1)
    print('  leg %5.1f-%5.1f s: u %6.2f -> %6.2f (%.1f m), lateral mean %.2f std %.2f, z mean %.2f' % (t[a], t[b], u[a], u[b], abs(u[b]-u[a]), v[seg].mean(), v[seg].std(), P[seg, 2].mean()))
# points in the corridor frame
subs = mc.read_dump('source'); pts = mc.world_points(subs)
pu = (pts[:, :2] - c) @ ax; pv = (pts[:, :2] - c) @ lat
print('points %d; along %.1f..%.1f, lateral %.1f..%.1f, z %.2f..%.2f' % (len(pts), pu.min(), pu.max(), pv.min(), pv.max(), pts[:,2].min(), pts[:,2].max()))
np.savez('frame.npz', c=c, ax=ax, lat=lat, legs=np.array(legs))
