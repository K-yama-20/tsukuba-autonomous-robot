"""Are the short-range returns fixed (vehicle body / mount) or moving (environment)? usage: python3 -I xt32_near_persist.py <fov.npz>
Per (vehicle azimuth 1 deg, ring) cell: mean returns per frame below 0.5 m and 0.5..1.2 m. A cell holds ~5.6 columns, so ~5.6
means a return in every frame. Vehicle azimuth = sensor azimuth + 100 deg (/config of the recording, see xt32_fov_sum.py)."""
import sys, numpy as np
d = np.load(sys.argv[1]); near = d['near']; NF = len(d['meta'])
az, r, el, rg = near.T; va = ((az + 100 + 180) % 360 - 180)
for lo, hi in ((0, .5), (.5, 1.2)):
    k = (r >= lo) & (r < hi)
    H, _, _ = np.histogram2d(va[k], rg[k], bins=[np.arange(-180, 181, 1), np.arange(-.5, 32, 1)])
    H /= NF; p = H > 4.0   # >~70 % of frames
    i = np.unravel_index(H.argmax(), H.shape)
    print(f'range {lo}-{hi} m: persistent cells (>4 returns/frame of ~5.6) {int(p.sum())}; largest cell {H.max():.2f} returns/frame at vehicle az {i[0]-180:+d} ring {i[1]}; cells > 1.0: {int((H > 1).sum())}')
    if p.any():
        a, rr = np.nonzero(p); azs = a - 180
        for ring in np.unique(rr):
            s = azs[rr == ring]
            print(f'  ring {ring:2d}: vehicle az {s.min():+4d}..{s.max()+1:+4d} ({len(s)} deg)  median r {np.median(r[k & (rg == ring) & (va >= s.min()) & (va < s.max()+1)]):.2f} m')
