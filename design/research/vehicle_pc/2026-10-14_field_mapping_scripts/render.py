import sys, numpy as np
sys.path.insert(0, '/Users/AYARyoya/Desktop/自己学習/TsukubaChallenge/tsukuba-autonomous-robot/gouda_core')
from gouda_core import map_convert as mc, png
T = np.loadtxt('source/traj_lidar.txt'); t = T[:, 0] - T[0, 0]; P = T[:, 1:4]
f = np.load('frame.npz'); c, ax, lat = f['c'], f['ax'], f['lat']
subs = mc.read_dump('source')
cols = [(66, 135, 245), (245, 166, 35), (80, 200, 120), (235, 87, 87), (180, 120, 230)]
def canvas(xr, yr, ppm):
    w = int((xr[1] - xr[0]) * ppm) + 1; h = int((yr[1] - yr[0]) * ppm) + 1
    return np.full((h, w, 3), 18, np.uint8), w, h
def plot(img, x, y, xr, yr, ppm, col, r=0):
    h, w = img.shape[:2]
    ix = ((x - xr[0]) * ppm).astype(int); iy = (h - 1 - (y - yr[0]) * ppm).astype(int)
    for dx in range(-r, r + 1):
        for dy in range(-r, r + 1):
            jx, jy = ix + dx, iy + dy; ok = (jx >= 0) & (jx < w) & (jy >= 0) & (jy < h)
            img[jy[ok], jx[ok]] = col
def grid(img, xr, yr, ppm, step=10):
    h, w = img.shape[:2]
    for gx in np.arange(np.ceil(xr[0] / step) * step, xr[1], step): img[:, int((gx - xr[0]) * ppm)] = (50, 50, 50)
    for gy in np.arange(np.ceil(yr[0] / step) * step, yr[1], step): img[h - 1 - int((gy - yr[0]) * ppm), :] = (50, 50, 50)
ppm = 8
W = [ (sm.points.astype(float) @ sm.t_world_origin[:3, :3].T + sm.t_world_origin[:3, 3]) for sm in subs ]
allp = np.concatenate(W); u = (allp[:, :2] - c) @ ax; v = (allp[:, :2] - c) @ lat
tu = (P[:, :2] - c) @ ax; tv = (P[:, :2] - c) @ lat
xr = (min(u.min(), tu.min()) - 2, max(u.max(), tu.max()) + 2); yr = (min(v.min(), tv.min()) - 2, max(v.max(), tv.max()) + 2)
img, w, h = canvas(xr, yr, ppm); grid(img, xr, yr, ppm)
for k, wp in enumerate(W):
    plot(img, (wp[:, :2] - c) @ ax, (wp[:, :2] - c) @ lat, xr, yr, ppm, cols[k % len(cols)])
plot(img, tu, tv, xr, yr, ppm, (255, 255, 255), r=1)
plot(img, tu[:1], tv[:1], xr, yr, ppm, (255, 255, 0), r=4)
open('top_view.png', 'wb').write(png.encode_rgb(w, h, img.tobytes())); print('top', w, h)
# side view: along-axis vs z
zr = (min(allp[:, 2].min(), P[:, 2].min()) - 2, max(allp[:, 2].max(), P[:, 2].max()) + 2)
img2, w2, h2 = canvas(xr, zr, ppm); grid(img2, xr, zr, ppm)
for k, wp in enumerate(W):
    plot(img2, (wp[:, :2] - c) @ ax, wp[:, 2], xr, zr, ppm, cols[k % len(cols)])
plot(img2, tu, P[:, 2], xr, zr, ppm, (255, 255, 255), r=1)
plot(img2, tu[:1], P[:1, 2], xr, zr, ppm, (255, 255, 0), r=4)
open('side_view.png', 'wb').write(png.encode_rgb(w2, h2, img2.tobytes())); print('side', w2, h2)
