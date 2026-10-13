import sys, numpy as np
sys.path.insert(0, '/Users/AYARyoya/Desktop/自己学習/TsukubaChallenge/tsukuba-autonomous-robot/gouda_core')
from gouda_core import map_convert as mc
T = np.loadtxt('source/traj_lidar.txt'); P = T[:, 1:4]
f = np.load('frame.npz'); c, ax, lat = f['c'], f['ax'], f['lat']
tu = (P[:, :2] - c) @ ax
k, b = np.linalg.lstsq(np.c_[tu, np.ones(len(tu))], P[:, 2], rcond=None)[0]
subs = mc.read_dump('source'); pts = mc.world_points(subs)
u = (pts[:, :2] - c) @ ax; v = (pts[:, :2] - c) @ lat
rel = pts[:, 2] - (k * u + b)          # height relative to the sensor height line (sensor at 0; floor near -1.015 per /config)
inside = (abs(u) < 17) & (v > -1.0) & (v < 0.55)
print('points inside the corridor section: %d' % inside.sum())
h, e = np.histogram(rel[inside], bins=np.arange(-3.0, 2.01, 0.1))
for i in range(len(h)):
    if h[i]: print('  rel %+.1f..%+.1f m: %5d %s' % (e[i], e[i+1], h[i], '#' * min(60, h[i] // 10)))
s = {'map_resolution_m': 0.1, 'ground_band_max_m': 0.1, 'obstacle_band_min_m': 0.15, 'obstacle_band_max_m': 1.2, 'occupied_min_points': 1, 'ground_cell_m': 0.5, 'ground_max_slope_deg': 10, 'ground_fill_radius_m': 1.0}
g = mc.estimate_ground(pts, s['ground_cell_m'], s['ground_max_slope_deg'], s['ground_fill_radius_m'])
gz = g.at(pts[:, 0], pts[:, 1]) - (k * u + b)
print('estimated ground inside the corridor relative to the sensor line: median %.2f m, p10 %.2f, p90 %.2f' % tuple(np.nanpercentile(gz[inside], [50, 10, 90])))
