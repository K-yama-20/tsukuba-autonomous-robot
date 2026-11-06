"""Noise in bag_02 forward segments (README table rows 24.1-32.5 and 15.4-17.8). Usage: python3 -I b2_steady.py sig_b2.npz"""
import sys, numpy as np
z = np.load(sys.argv[1]); t = z['t']
for a, b in ((25.0, 32.0), (15.6, 17.6)):
    m = (t >= a) & (t <= b)
    out = f'{a}-{b}:'
    for k in ('Arel', 'Acen', 'B'):
        x = z[k][m]; tt = t[m]; r = x - np.polyval(np.polyfit(tt, x, 1), tt)
        out += f' {k} mean {x.mean():+.4f} detr sd {r.std()*1e3:.1f} dsd {np.sqrt(np.mean(np.diff(x)**2))*1e3:.1f} |'
    w = z['wA'][m]; g = z['gzi'][m]
    out += f' yaw wA-gz_int sd {np.std(w-g)*1e3:.2f} mrad/s'
    print(out)
