import sys, numpy as np
sys.path.insert(0, '/Users/AYARyoya/Desktop/自己学習/TsukubaChallenge/tsukuba-autonomous-robot/gouda_core')
from gouda_core import map_convert as mc, png
s = {'map_resolution_m': 0.1, 'ground_band_max_m': 0.1, 'obstacle_band_min_m': 0.15, 'obstacle_band_max_m': 1.2, 'occupied_min_points': 1,
     'ground_cell_m': 0.5, 'ground_max_slope_deg': 10, 'ground_fill_radius_m': 1.0}
T = np.loadtxt('source/traj_lidar.txt'); P = T[:, 1:4]
f = np.load('frame.npz'); c, ax, lat = f['c'], f['ax'], f['lat']
subs = mc.read_dump('source'); pts = mc.world_points(subs)
sid = np.concatenate([np.full(len(sm.points), sm.sid) for sm in subs])
g = mc.estimate_ground(pts, s['ground_cell_m'], s['ground_max_slope_deg'], s['ground_fill_radius_m'])
hag, gnd, obst = mc.classify(pts, g, s)
u = (pts[:, :2] - c) @ ax; v = (pts[:, :2] - c) @ lat
tu = (P[:, :2] - c) @ ax; tv = (P[:, :2] - c) @ lat
# corridor-frame raster (u along, v across), 0.1 m, only the driven section +- 2 m
res = 0.1; ur = (tu.min() - 2, tu.max() + 2); vr = (-3.0, 3.0)
W = int((ur[1] - ur[0]) / res) + 1; H = int((vr[1] - vr[0]) / res) + 1
iu = ((u - ur[0]) / res).astype(int); iv = ((v - vr[0]) / res).astype(int); ok = (iu >= 0) & (iu < W) & (iv >= 0) & (iv < H)
occ = np.zeros((H, W), int); free = np.zeros((H, W), int); top = np.full((H, W), np.nan)
np.add.at(occ, (iv[ok & obst], iu[ok & obst]), 1); np.add.at(free, (iv[ok & gnd], iu[ok & gnd]), 1)
img = np.full((H, W, 3), 128, np.uint8); img[free > 0] = (250, 250, 250); img[occ > 0] = (0, 0, 0)
ti = ((tu - ur[0]) / res).astype(int); tj = ((tv - vr[0]) / res).astype(int); okt = (ti >= 0) & (ti < W) & (tj >= 0) & (tj < H)
img[tj[okt], ti[okt]] = (220, 40, 40)
big = np.repeat(np.repeat(img[::-1], 4, axis=0), 4, axis=1)
open('corridor_2d.png', 'wb').write(png.encode_rgb(big.shape[1], big.shape[0], big.tobytes()))
# height view in the corridor frame
hv = np.full((H, W), -np.inf); kk = ok & np.isfinite(hag) & (hag <= s['obstacle_band_max_m']); np.maximum.at(hv, (iv[kk], iu[kk]), hag[kk])
rgb = mc.colour_scale(np.where(np.isfinite(hv), hv, np.nan), s['obstacle_band_max_m']); rgb[np.isfinite(hv) & (hv <= s['ground_band_max_m'])] = (60, 90, 60)
rgb[tj[okt], ti[okt]] = (255, 255, 255)
big2 = np.repeat(np.repeat(rgb[::-1], 4, axis=0), 4, axis=1)
open('corridor_height.png', 'wb').write(png.encode_rgb(big2.shape[1], big2.shape[0], big2.tobytes()))
print('raster', W, H, '(u %.1f..%.1f, v %.1f..%.1f)' % (*ur, *vr))
# walls: occupied columns per lateral row inside the driven section
rows = occ[:, int((-15 - ur[0]) / res):int((15 - ur[0]) / res)]
prof = (rows > 0).mean(axis=1); vv = vr[0] + np.arange(H) * res
print('lateral rows occupied >40% of the length (walls):', [round(x, 1) for x in vv[prof > 0.4]])
# obstacles inside the corridor (between walls), clusters along u
inside = ok & obst & (v > -0.9) & (v < 0.5) & (abs(u) < 17)
print('obstacle points inside the corridor:', inside.sum())
if inside.any():
    order = np.argsort(u[inside]); uu = u[inside][order]; vv2 = v[inside][order]; hh = hag[inside][order]; ss = sid[inside][order]
    groups = np.split(np.arange(len(uu)), np.where(np.diff(uu) > 0.5)[0] + 1)
    for gi in groups:
        if len(gi) < 5: continue
        print('  cluster u %.1f..%.1f m, v %.2f..%.2f m, height %.2f..%.2f m, %d pts, submaps %s' % (uu[gi].min(), uu[gi].max(), vv2[gi].min(), vv2[gi].max(), hh[gi].min(), hh[gi].max(), len(gi), sorted(set(ss[gi].tolist()))))
