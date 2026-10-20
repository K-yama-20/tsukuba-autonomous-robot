"""Do two GLIM source maps cover the same place? Top-view occupancy of structure points (0.5..2.2 m above the local ground,
the ground taken as trajectory height - sensor height), then an exhaustive yaw search with FFT cross-correlation.
usage: python3 map_overlap.py <dump_A> <dump_B> [sensor_height=1.18] [cell=0.5]"""
import sys, numpy as np
from scipy.spatial import cKDTree
sys.path.insert(0, '/Users/AYARyoya/Desktop/自己学習/TsukubaChallenge/tsukuba-autonomous-robot/gouda_core')
from gouda_core import map_convert as mc

H = float(sys.argv[3]) if len(sys.argv) > 3 else 1.18
CELL = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5


def structure_xy(dump):
    pts = mc.world_points(mc.read_dump(dump)); T = np.loadtxt(f'{dump}/traj_lidar.txt')[:, 1:4]
    d, j = cKDTree(T[:, :2]).query(pts[:, :2])
    hag = pts[:, 2] - (T[j, 2] - H)
    k = (d < 20) & (hag > 0.5) & (hag < 2.2)
    return pts[k, :2], T[:, :2]


def raster(xy, origin, shape):
    ij = np.floor((xy - origin) / CELL).astype(int); ok = (ij[:, 0] >= 0) & (ij[:, 1] >= 0) & (ij[:, 0] < shape[0]) & (ij[:, 1] < shape[1])
    img = np.zeros(shape); np.add.at(img, (ij[ok, 0], ij[ok, 1]), 1); return (img >= 2).astype(float)


A, TA = structure_xy(sys.argv[1]); B, TB = structure_xy(sys.argv[2])
cA, cB = A.mean(0), B.mean(0); A0, B0 = A - cA, B - cB
R = max(np.abs(A0).max(), np.abs(B0).max()) + 5; n = int(2 ** np.ceil(np.log2(4 * R / CELL)))
shape = (n, n); org = np.array([-n * CELL / 2, -n * CELL / 2])
IA = raster(A0, org, shape); FA = np.fft.rfft2(IA)
best = []
for deg in np.arange(0, 360, 1.0):
    th = np.radians(deg); Rm = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    IB = raster(B0 @ Rm.T, org, shape)
    C = np.fft.irfft2(FA * np.conj(np.fft.rfft2(IB)), s=shape)
    k = np.unravel_index(np.argmax(C), C.shape); s = C[k]
    sh = np.array(k, dtype=float); sh[sh > n / 2] -= n
    best.append((s / min(IA.sum(), IB.sum()), deg, sh * CELL))
best.sort(key=lambda x: -x[0])
print(f'A {sys.argv[1].split("/")[-2]}: {len(A)} structure points, {IA.sum():.0f} cells; B {sys.argv[2].split("/")[-2]}: {len(B)} points')
for s, deg, sh in best[:5]:
    print(f'  yaw {deg:5.1f} deg, shift ({sh[0]:+.1f}, {sh[1]:+.1f}) m: overlap {100*s:.1f} % of the smaller map')
# trajectory overlap at the best alignment
s, deg, sh = best[0]; th = np.radians(deg); Rm = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
TBa = (TB - cB) @ Rm.T + sh + cA
d, _ = cKDTree(TA).query(TBa)
print(f'  at the best alignment: B trajectory within 2 m of A trajectory {100*np.mean(d<2):.0f} %, within 5 m {100*np.mean(d<5):.0f} %')
med = np.median([b[0] for b in best]); print(f'  median overlap over all yaws {100*med:.1f} % (background)')
