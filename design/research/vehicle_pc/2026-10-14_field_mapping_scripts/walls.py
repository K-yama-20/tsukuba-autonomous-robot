import sys, numpy as np
sys.path.insert(0, '/Users/AYARyoya/Desktop/自己学習/TsukubaChallenge/tsukuba-autonomous-robot/gouda_core')
from gouda_core import map_convert as mc
T = np.loadtxt('source/traj_lidar.txt'); t = T[:, 0] - T[0, 0]; P = T[:, 1:4]
f = np.load('frame.npz'); c, ax, lat = f['c'], f['ax'], f['lat']
i = int(np.argmax(np.linalg.norm(np.diff(P, axis=0), axis=1))); print('largest step %.2f m between t=%.2f and %.2f s (gap %.2f s)' % (np.linalg.norm(P[i+1]-P[i]), t[i], t[i+1], t[i+1]-t[i]))
tu = (P[:, :2] - c) @ ax
# trajectory height vs position along the corridor (slope)
A = np.c_[tu, np.ones(len(tu))]; k, b = np.linalg.lstsq(A, P[:, 2], rcond=None)[0]
res = P[:, 2] - (k * tu + b)
print('trajectory height along the corridor: slope %.3f (%.2f deg), residual std %.3f m, max |res| %.3f m' % (k, np.degrees(np.arctan(k)), res.std(), abs(res).max()))
subs = mc.read_dump('source')
mount = 1.015   # lidar_mount_z_m from /config (human input), only to place the floor band for this analysis
for sm in subs:
    w = sm.points.astype(float) @ sm.t_world_origin[:3, :3].T + sm.t_world_origin[:3, 3]
    u = (w[:, :2] - c) @ ax; v = (w[:, :2] - c) @ lat
    sens = k * u + b                            # local sensor height along the corridor
    hag = w[:, 2] - (sens - mount)              # height above the floor estimated from the trajectory
    sel = (abs(u) < 15) & (hag > 0.3) & (hag < 1.8)
    hist, edges = np.histogram(v[sel], bins=np.arange(-6, 6.01, 0.05))
    cen = (edges[:-1] + edges[1:]) / 2
    left = cen[cen < 0][np.argmax(hist[cen < 0])]; right = cen[cen > 0][np.argmax(hist[cen > 0])]
    fl = (abs(u) < 15) & (abs(v) < 1.0) & (hag > -0.3) & (hag < 0.3)
    print('submap %d: walls at lateral %.2f / %.2f m (width %.2f m); floor points near path %d, floor height above est. %.3f +- %.3f m' % (sm.sid, left, right, right - left, fl.sum(), np.median(hag[fl]) if fl.any() else float('nan'), hag[fl].std() if fl.any() else float('nan')))
