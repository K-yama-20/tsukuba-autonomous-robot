"""XT-32 visible range from recorded point clouds (/sensors/xt32/points, frame xt32_link). Read-only on the bags.
usage: python3 -I xt32_fov.py <scripts_dir_with_mcap_min> <out.npz> <every_k> <bag_0.mcap> [<bag_0.mcap> ...]
Per sampled frame (every k-th): per ring elevation (atan2(z, hypot(x, y)) of returns 3..60 m), per column azimuth and
return flag, short-range returns (< 2 m) by azimuth, max range, and ground points (RANSAC plane, as extract_bag.py)
with their horizontal distance by azimuth. A sampled frame that is not 32 x 2000 points is skipped and listed. No-return points are (0, 0, 0) in this driver output."""
import sys, numpy as np
sys.path.insert(0, sys.argv[1]); import mcap_min as m
OUT, EVERY, BAGS = sys.argv[2], int(sys.argv[3]), sys.argv[4:]
NR, NC = 32, 2000
rng = np.random.default_rng(0)


def plane(x, y, z):
    r = np.hypot(x, y); k = (r > 3) & (r < 10) & (z > -2.2) & (z < -0.2)
    P = np.c_[x[k], y[k], z[k]].astype(float)
    if len(P) < 300: return None
    if len(P) > 6000: P = P[rng.choice(len(P), 6000, replace=False)]
    best = None
    for _ in range(150):
        a, b, c = P[rng.choice(len(P), 3, replace=False)]
        n = np.cross(b - a, c - a); nn = np.linalg.norm(n)
        if nn < 1e-6: continue
        n /= nn; n = -n if n[2] < 0 else n
        if n[2] < np.cos(np.radians(20)): continue
        s = (np.abs((P - a) @ n) < 0.05).sum()
        if best is None or s > best[0]: best = (s, a, n)
    if best is None or best[0] < 800: return None
    s, a, n = best; Q = P[np.abs((P - a) @ n) < 0.05]; c = Q.mean(0); n = np.linalg.svd(Q - c)[2][2]
    n = -n if n[2] < 0 else n
    rms = np.sqrt(np.mean(((Q - c) @ n) ** 2))
    return (n, -(c @ n)) if rms < 0.03 else None


elev, colaz, ret, near, maxr, gnd, meta, skipped = [], [], [], [], [], [], [], []
for bi, bag in enumerate(BAGS):
    i = 0
    for t, lt, d in m.read(bag, {'/sensors/xt32/points'}):
        i += 1
        if (i - 1) % EVERY: continue
        st, fid, o, _ = m.cloud(d, ('x', 'y', 'z', 'ring'))
        x, y, z, ring = o['x'].astype(float), o['y'].astype(float), o['z'].astype(float), o['ring']
        if len(x) != NR * NC or not (ring[:NR] == np.arange(NR)).all():
            skipped.append((bi, st, len(x))); continue
        r3 = np.sqrt(x * x + y * y + z * z); rh = np.hypot(x, y); ok = r3 > 0
        az = np.degrees(np.arctan2(y, x)); el = np.degrees(np.arctan2(z, rh))
        R = lambda a: a.reshape(NC, NR)
        e = np.where((r3 > 3) & (r3 < 60), el, np.nan); elev.append(np.nanmedian(R(e), axis=0))
        colaz.append(np.nanmedian(R(np.where(ok, az, np.nan)), axis=1))
        ret.append(R(ok))
        k = ok & (r3 < 2.0); near.append(np.c_[az[k], r3[k], el[k], ring[k]].astype(np.float32))
        maxr.append((r3.max(), np.percentile(r3[ok], 99), np.percentile(r3[ok], 1), ok.mean()))
        p = plane(x, y, z)
        if p is not None:
            n, h = p; dist = np.c_[x, y, z] @ n + h        # height above the plane
            g = ok & (np.abs(dist) < 0.06) & (rh < 15)
            gnd.append(np.c_[np.full(g.sum(), len(meta)), az[g], rh[g], ring[g]].astype(np.float32))
            hh = h
        else:
            hh = np.nan
        meta.append((bi, st, hh))
    print('bag', bi, 'frames', i, 'skipped (not 32x2000)', [k for k in skipped if k[0] == bi], flush=True)
np.savez_compressed(OUT, elev=np.array(elev), colaz=np.array(colaz), ret=np.array(ret), near=np.concatenate(near),
                    maxr=np.array(maxr), gnd=np.concatenate(gnd), meta=np.array(meta), skipped=np.array(skipped).reshape(-1, 3))
print('done', OUT, len(meta))
