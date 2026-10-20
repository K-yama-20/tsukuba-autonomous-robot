"""Analysis only (plan check for G-FLOOR-REFLECTION, version with a prior): per submap, the ground peak searched only within
+-W of an expected sensor height H0; reports the found height, how sharp the peak is, and the points far below it."""
import re, sys, numpy as np
sys.path.insert(0, '/Users/AYARyoya/Desktop/自己学習/TsukubaChallenge/tsukuba-autonomous-robot/gouda_core')
from gouda_core import map_convert as mc
from pathlib import Path
H0, W = float(sys.argv[3]), float(sys.argv[4])
def frames(d):
    t = (Path(d) / 'data.txt').read_text().splitlines(); out = []
    for i, l in enumerate(t):
        if l.startswith('T_world_lidar:'):
            out.append([float(t[i + 1].split()[3]), float(t[i + 2].split()[3]), float(t[i + 3].split()[3])])
    return np.array(out)
src = Path(sys.argv[1]); H = []; share = []; below = []
for sd in sorted(x for x in src.iterdir() if x.is_dir() and re.match(r'^\d{6}$', x.name)):
    sm = mc.read_submap(sd); F = frames(sd)
    if len(F) == 0 or len(sm.points) == 0: continue
    Fs = F[::max(1, len(F) // 30)]
    w = sm.points.astype(float) @ sm.t_world_origin[:3, :3].T + sm.t_world_origin[:3, 3]
    d2 = ((w[:, None, :2] - Fs[None, :, :2]) ** 2).sum(-1); j = d2.argmin(1); r = np.sqrt(d2[np.arange(len(w)), j]); dz = w[:, 2] - Fs[j, 2]
    near = (r > 1.0) & (r < 8)
    m = near & (dz > -H0 - W) & (dz < -H0 + W)
    if m.sum() < 15: continue
    h, e = np.histogram(dz[m], bins=np.arange(-H0 - W, -H0 + W + 1e-9, 0.05)); k = h.argmax(); peak = (e[k] + e[k + 1]) / 2
    H.append(-peak); share.append(h[max(0, k - 1):k + 2].sum() / m.sum())
    below.append((near & (dz < peak - 0.3)).sum() / max(1, near.sum()))
H = np.array(H); share = np.array(share); below = np.array(below)
print('%s (search %.2f +- %.2f m): submaps %d; ground below the sensor: median %.2f m, p10 %.2f, p90 %.2f; points within +-0.075 m of the peak: median %.0f %% of the window; points >0.3 m below the ground (1..8 m from the path): median %.1f %%, p90 %.1f %%' % (
    sys.argv[2], H0, W, len(H), np.median(H), np.percentile(H, 10), np.percentile(H, 90), 100 * np.median(share), 100 * np.median(below), 100 * np.percentile(below, 90)))
