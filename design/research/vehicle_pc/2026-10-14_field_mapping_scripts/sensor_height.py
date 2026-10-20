"""Analysis only (plan check for G-FLOOR-REFLECTION): per submap, the height of the dominant ground surface below the sensor,
from the submap's own frames (data.txt T_world_lidar) and points 1.5..6 m around them."""
import re, sys, numpy as np
sys.path.insert(0, '/Users/AYARyoya/Desktop/自己学習/TsukubaChallenge/tsukuba-autonomous-robot/gouda_core')
from gouda_core import map_convert as mc
from pathlib import Path
def frames(d):
    t = (Path(d) / 'data.txt').read_text().splitlines(); out = []
    for i, l in enumerate(t):
        if l.startswith('T_world_lidar:'):
            out.append([float(x) for x in t[i + 1 + 0].split()][3:4] + [float(x) for x in t[i + 2].split()][3:4] + [float(x) for x in t[i + 3].split()][3:4])
    return np.array(out)
src = Path(sys.argv[1]); H = []; outl = []
for sd in sorted(x for x in src.iterdir() if x.is_dir() and re.match(r'^\d{6}$', x.name)):
    sm = mc.read_submap(sd); F = frames(sd)
    if len(F) == 0 or len(sm.points) == 0: continue
    w = sm.points.astype(float) @ sm.t_world_origin[:3, :3].T + sm.t_world_origin[:3, 3]
    d2 = ((w[:, None, :2] - F[None, ::max(1, len(F) // 30), :2]) ** 2).sum(-1); j = d2.argmin(1); r = np.sqrt(d2[np.arange(len(w)), j])
    Fs = F[::max(1, len(F) // 30)]; dz = w[:, 2] - Fs[j, 2]
    m = (r > 1.5) & (r < 6) & (dz < -0.3) & (dz > -3.0)
    if m.sum() < 30: continue
    h, e = np.histogram(dz[m], bins=np.arange(-3.0, -0.3 + 1e-9, 0.05)); k = h.argmax(); peak = (e[k] + e[k + 1]) / 2
    H.append(-peak); outl.append(((dz[m] < peak - 0.3)).mean())
H = np.array(H); outl = np.array(outl)
print('%s: submaps used %d; sensor height above the dominant ground: median %.2f m, p10 %.2f, p90 %.2f, min %.2f, max %.2f; share of points >0.3 m below that ground (1.5..6 m around the path): median %.1f %%, p90 %.1f %%' % (
    sys.argv[2], len(H), np.median(H), np.percentile(H, 10), np.percentile(H, 90), H.min(), H.max(), 100 * np.median(outl), 100 * np.percentile(outl, 90)))
