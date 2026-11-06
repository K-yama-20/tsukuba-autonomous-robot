"""Consistency checks: frames, axes, odom vs world poses. Usage: python3 -I explore.py <data/bX>"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from load import *

d = sys.argv[1]
fr, n, dup = load_dump(os.path.join(d, 'dump', 'data.txt'))
print(f'frames in data.txt: {n}, duplicates by stamp: {dup}, unique {len(fr)}')
tI, pI, RI = load_tum(os.path.join(d, 'dump', 'odom_imu.txt'))
tL, pL, RL = load_tum(os.path.join(d, 'dump', 'odom_lidar.txt'))
ts = np.array([f['stamp'] for f in fr])
print('odom_imu rows', len(tI), 'stamps equal to dump:', len(tI) == len(ts) and np.allclose(tI, ts, atol=1e-6))
dt = np.diff(ts); print(f'frame dt: median {np.median(dt)*1e3:.1f} ms, min {dt.min()*1e3:.1f}, max {dt.max()*1e3:.1f}')
To = np.array([f['T_odom_lidar'] for f in fr]); Tw = np.array([f['T_world_lidar'] for f in fr]); v = np.array([f['v'] for f in fr])
print('max |p_odom_lidar(dump) - p(odom_lidar.txt)| =', np.abs(To[:, :3, 3] - pL).max())
dpw = np.linalg.norm(To[:, :3, 3] - Tw[:, :3, 3], axis=1); print(f'|p_odom - p_world| : max {dpw.max():.4f} m, final {dpw[-1]:.4f} m')
# IMU position from lidar pose: T_world_imu = T_world_lidar * T_lidar_imu, T_lidar_imu = (0,0,-0.08), R = I
pIw = To[:, :3, 3] + To[:, :3, :3] @ np.array([0, 0, -0.08])
print('max |p_imu(from T_odom_lidar) - odom_imu.txt| =', np.abs(pIw - pI).max())
# displacement in the IMU frame over whole run, by axis, for frames with motion
dpb = np.array([RI[i].T @ (pI[i + 1] - pI[i]) for i in range(len(tI) - 1)])
print('sum of |displacement| per IMU axis (x, y, z) [m]:', np.abs(dpb).sum(axis=0).round(3), ' signed:', dpb.sum(axis=0).round(3))
vb = np.array([Tw[i, :3, :3].T @ v[i] for i in range(len(v))])
print('sum |v_body| per axis (B) *0.1 s:', (np.abs(vb).sum(axis=0) * 0.1).round(3))
# rotation odom vs world
ang = [np.degrees(np.arccos(np.clip((np.trace(To[i, :3, :3].T @ Tw[i, :3, :3]) - 1) / 2, -1, 1))) for i in range(len(fr))]
print(f'rotation odom vs world: max {max(ang):.3f} deg')
