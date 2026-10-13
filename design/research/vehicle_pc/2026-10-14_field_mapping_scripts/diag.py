import sys, numpy as np
sys.path.insert(0, '/Users/AYARyoya/Desktop/自己学習/TsukubaChallenge/tsukuba-autonomous-robot/gouda_core')
from gouda_core import map_convert as mc
T = np.loadtxt('source/traj_lidar.txt'); t = T[:, 0] - T[0, 0]; P = T[:, 1:4]
# z over time and the jump
for s in (0, 5, 10, 13, 15, 20, 30, 60, 120, 180, 237):
    i = np.searchsorted(t, s); print('t=%5.1f s  pos=(%.2f, %.2f, %.2f)' % (t[i], *P[i]))
# floor plane per submap in the world frame: lowest points within 3 m of the trajectory below the sensor
subs = mc.read_dump('source')
for sm in subs:
    w = sm.points.astype(float) @ sm.t_world_origin[:3, :3].T + sm.t_world_origin[:3, 3]
    o = sm.t_world_origin[:3, 3]
    near = np.linalg.norm(w[:, :2] - o[:2], axis=1) < 6
    q = w[near]
    if len(q) < 50: print('submap', sm.sid, 'too few points'); continue
    low = q[q[:, 2] < np.percentile(q[:, 2], 25)]
    A = np.c_[low[:, 0], low[:, 1], np.ones(len(low))]; coef, *_ = np.linalg.lstsq(A, low[:, 2], rcond=None)
    n = np.array([-coef[0], -coef[1], 1.0]); n /= np.linalg.norm(n)
    tilt = np.degrees(np.arccos(n[2]))
    # the submap's own up axis vs world up
    up = sm.t_world_origin[:3, 2]; ang = np.degrees(np.arccos(np.clip(up[2], -1, 1)))
    print('submap %d origin z %.2f: floor-like plane tilt %.1f deg (from %d low points within 6 m); submap frame tilt %.1f deg' % (sm.sid, o[2], tilt, len(low), ang))
