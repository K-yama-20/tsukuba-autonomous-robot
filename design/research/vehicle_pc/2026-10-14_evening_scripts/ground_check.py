"""DEC-107 premise check on a GLIM dump, with the loop-corrected trajectory (traj_lidar.txt matched by stamp; FILE-GROUND-DESIGN-CHECK):
per submap, the ground peak below the sensor searched within H0 +- W (points 1..8 m from the submap's frame positions),
the sharpness of the peak, points > 0.3 m below the peak, and a plane fitted in the annulus r_in..r_out (tilt vs world z).
usage: python3 ground_check.py <dump_dir> <label> <H0> <W> [r_in r_out]"""
import re, sys, numpy as np
from pathlib import Path
sys.path.insert(0, '/Users/AYARyoya/Desktop/自己学習/TsukubaChallenge/tsukuba-autonomous-robot/gouda_core')
from gouda_core import map_convert as mc

src = Path(sys.argv[1]); label = sys.argv[2]; H0, W = float(sys.argv[3]), float(sys.argv[4])
r_in, r_out = (float(sys.argv[5]), float(sys.argv[6])) if len(sys.argv) > 6 else (1.0, 4.0)
T = np.loadtxt(src / 'traj_lidar.txt'); traj = {round(s, 4): p for s, p in zip(T[:, 0], T[:, 1:4])}
H, share, below, tilt, matched, total = [], [], [], [], 0, 0
for sd in sorted(x for x in src.iterdir() if x.is_dir() and re.match(r'^\d{6}$', x.name)):
    stamps = [float(l.split()[1]) for l in (sd / 'data.txt').read_text().splitlines() if l.startswith('stamp:')]
    F = np.array([traj[round(s, 4)] for s in stamps if round(s, 4) in traj]); matched += len(F); total += len(stamps)
    sm = mc.read_submap(sd)
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
    a = (r > r_in) & (r < r_out) & (np.abs(dz - peak) < 0.15)
    if a.sum() >= 30:
        P = w[a]; c = P.mean(0); _, _, Vt = np.linalg.svd(P - c); n = Vt[2] * np.sign(Vt[2][2]); tilt.append(np.degrees(np.arccos(n[2])))
H, share, below, tilt = map(np.array, (H, share, below, tilt))
print(f'{label} (search {H0:.2f} +- {W:.2f} m, stamps matched {matched}/{total}): submaps {len(H)}; ground below the sensor: median {np.median(H):.2f} m, p10 {np.percentile(H,10):.2f}, p90 {np.percentile(H,90):.2f}; '
      f'points within +-0.075 m of the peak: median {100*np.median(share):.0f} % of the window; points >0.3 m below the ground (1..8 m): median {100*np.median(below):.1f} %, p90 {100*np.percentile(below,90):.1f} %; '
      f'annulus {r_in:.0f}..{r_out:.0f} m plane tilt vs map z: median {np.median(tilt):.1f} deg, p90 {np.percentile(tilt,90):.1f} ({len(tilt)} submaps)')
