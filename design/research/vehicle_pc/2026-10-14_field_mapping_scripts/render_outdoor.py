import sys, numpy as np
sys.path.insert(0, '/Users/AYARyoya/Desktop/自己学習/TsukubaChallenge/tsukuba-autonomous-robot/gouda_core')
from gouda_core import map_convert as mc, png
T = np.loadtxt('source/traj_lidar.txt'); t = T[:, 0] - T[0, 0]; P = T[:, 1:4]
subs = mc.read_dump('source'); n = len(subs)
def ramp(f):   # blue (early) -> green -> red (late)
    f = np.clip(f, 0, 1); r = np.where(f < 0.5, 40, 40 + (f - 0.5) * 2 * 210); g = np.where(f < 0.5, 90 + f * 2 * 140, 230 - (f - 0.5) * 2 * 190); b = np.where(f < 0.5, 240 - f * 2 * 200, 40)
    return np.stack([r, g, b], -1).astype(np.uint8)
ppm = 4; pad = 5
allp = mc.world_points(subs)
xr = (min(allp[:, 0].min(), P[:, 0].min()) - pad, max(allp[:, 0].max(), P[:, 0].max()) + pad)
yr = (min(allp[:, 1].min(), P[:, 1].min()) - pad, max(allp[:, 1].max(), P[:, 1].max()) + pad)
# keep the view to 60 m around the path so that far points do not shrink the picture
xr = (max(xr[0], P[:, 0].min() - 60), min(xr[1], P[:, 0].max() + 60)); yr = (max(yr[0], P[:, 1].min() - 60), min(yr[1], P[:, 1].max() + 60))
W = int((xr[1] - xr[0]) * ppm) + 1; H = int((yr[1] - yr[0]) * ppm) + 1
img = np.full((H, W, 3), 18, np.uint8)
for gx in np.arange(np.ceil(xr[0] / 20) * 20, xr[1], 20): img[:, int((gx - xr[0]) * ppm)] = (50, 50, 50)
for gy in np.arange(np.ceil(yr[0] / 20) * 20, yr[1], 20): img[H - 1 - int((gy - yr[0]) * ppm), :] = (50, 50, 50)
def put(x, y, col, r=0):
    ix = ((x - xr[0]) * ppm).astype(int); iy = (H - 1 - (y - yr[0]) * ppm).astype(int)
    for dx in range(-r, r + 1):
        for dy in range(-r, r + 1):
            jx, jy = ix + dx, iy + dy; ok = (jx >= 0) & (jx < W) & (jy >= 0) & (jy < H); img[jy[ok], jx[ok]] = col if np.ndim(col) == 1 else col[ok]
for k, sm in enumerate(subs):
    w = sm.points.astype(float) @ sm.t_world_origin[:3, :3].T + sm.t_world_origin[:3, 3]
    put(w[:, 0], w[:, 1], ramp(k / max(n - 1, 1)))
put(P[:, 0], P[:, 1], np.array([255, 255, 255], np.uint8), r=1)
for s0 in (238.8, 352.6, 586.2):
    i = np.searchsorted(t, s0); put(P[i:i+1, 0], P[i:i+1, 1], np.array([255, 230, 0], np.uint8), r=5)
put(P[:1, 0], P[:1, 1], np.array([255, 0, 255], np.uint8), r=6)
open('outdoor_top.png', 'wb').write(png.encode_rgb(W, H, img.tobytes())); print('top', W, H)
# height over time
pw, ph, tz = 1000, 300, (P[:, 2].min() - 1, P[:, 2].max() + 1)
img2 = np.full((ph, pw, 3), 18, np.uint8)
for zz in np.arange(np.ceil(tz[0]), tz[1], 2): img2[ph - 1 - int((zz - tz[0]) / (tz[1] - tz[0]) * (ph - 1)), :] = (50, 50, 50)
for tt in range(0, int(t[-1]) + 1, 60): img2[:, int(tt / t[-1] * (pw - 1))] = (50, 50, 50)
for s0 in (238.8, 352.6, 586.2): img2[:, int(s0 / t[-1] * (pw - 1))] = (120, 110, 0)
ix = (t / t[-1] * (pw - 1)).astype(int); iy = (ph - 1 - (P[:, 2] - tz[0]) / (tz[1] - tz[0]) * (ph - 1)).astype(int)
for d in (-1, 0, 1): img2[np.clip(iy + d, 0, ph - 1), ix] = (255, 255, 255)
open('outdoor_height.png', 'wb').write(png.encode_rgb(pw, ph, img2.tobytes())); print('height', pw, ph, 'z range', tz)
