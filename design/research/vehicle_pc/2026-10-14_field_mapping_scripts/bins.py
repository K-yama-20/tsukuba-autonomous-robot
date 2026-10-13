import sys, numpy as np
sys.path.insert(0, '/Users/AYARyoya/Desktop/自己学習/TsukubaChallenge/tsukuba-autonomous-robot/gouda_core')
from gouda_core import map_convert as mc, png
T = np.loadtxt('source/traj_lidar.txt'); P = T[:, 1:4]
f = np.load('frame.npz'); c, ax, lat = f['c'], f['ax'], f['lat']
tu = (P[:, :2] - c) @ ax; tv = (P[:, :2] - c) @ lat
k, b = np.linalg.lstsq(np.c_[tu, np.ones(len(tu))], P[:, 2], rcond=None)[0]
subs = mc.read_dump('source')
floor_rel = -1.2   # floor peak relative to the sensor line (histogram above), analysis only
cols = [(66, 135, 245), (245, 166, 35), (80, 200, 120)]
res = 0.1; ur = (-19.0, 19.0); vr = (-1.6, 1.3); W = int((ur[1]-ur[0])/res)+1; H = int((vr[1]-vr[0])/res)+1
img = np.full((H, W, 3), 25, np.uint8)
cells = {}
for sm in subs:
    w = sm.points.astype(float) @ sm.t_world_origin[:3, :3].T + sm.t_world_origin[:3, 3]
    u = (w[:, :2] - c) @ ax; v = (w[:, :2] - c) @ lat; h = w[:, 2] - (k * u + b) - floor_rel
    floor = (abs(h) < 0.1); obj = (h > 0.15) & (h < 1.2)
    iu = ((u-ur[0])/res).astype(int); iv = ((v-vr[0])/res).astype(int); ok = (iu>=0)&(iu<W)&(iv>=0)&(iv<H)
    img[iv[ok & floor], iu[ok & floor]] = np.maximum(img[iv[ok & floor], iu[ok & floor]], 90)
    img[iv[ok & obj], iu[ok & obj]] = cols[sm.sid]
    for a, bb in zip(iu[ok & obj], iv[ok & obj]): cells.setdefault((a, bb), set()).add(sm.sid)
ti = ((tu-ur[0])/res).astype(int); tj = ((tv-vr[0])/res).astype(int); okt = (ti>=0)&(ti<W)&(tj>=0)&(tj<H); img[tj[okt], ti[okt]] = (255, 255, 255)
big = np.repeat(np.repeat(img[::-1], 5, axis=0), 5, axis=1); open('bins.png', 'wb').write(png.encode_rgb(big.shape[1], big.shape[0], big.tobytes()))
# objects inside the corridor away from the walls (wall rows at about v -1.2 and +0.7)
inner = {k_: s_ for k_, s_ in cells.items() if -0.95 < vr[0] + k_[1]*res < 0.45}
multi = {k_: s_ for k_, s_ in inner.items() if len(s_) >= 2}
print('inner object cells: %d, seen in >=2 submaps: %d' % (len(inner), len(multi)))
us = sorted(ur[0] + k_[0]*res for k_ in multi)
groups = []
for x in us:
    if groups and x - groups[-1][-1] <= 0.5: groups[-1].append(x)
    else: groups.append([x])
for g in groups:
    if len(g) >= 2:
        vs = [vr[0] + k_[1]*res for k_ in multi if g[0] - 1e-9 <= ur[0] + k_[0]*res <= g[-1] + 1e-9]
        print('  object u %.1f..%.1f m (%.1f m long), lateral %.1f..%.1f m, %d cells' % (g[0], g[-1], g[-1]-g[0]+res, min(vs), max(vs), len(g)))
print('image', big.shape[1], big.shape[0])
