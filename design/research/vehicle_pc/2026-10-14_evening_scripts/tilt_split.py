"""Separate a world-fixed map tilt from a sensor-fixed attitude error using the GLIM trajectory.
Per 5 m piece (no LiDAR gap): path slope dz/ds and heading; LiDAR forward-axis elevation and left-axis elevation in the map.
The forward axis in the LiDAR frame is taken from the motion itself (median of the unit displacement in the LiDAR frame).
usage: python3 tilt_split.py <maps_dir> <origin_id> [...]"""
import sys, numpy as np
from traj_judge import quat_to_R


def run(maps, oid):
    a = np.loadtxt(f'{maps}/{oid}/source/traj_lidar.txt')
    t, P, Q = a[:, 0], a[:, 1:4], a[:, 4:8]
    R = np.array([quat_to_R(q) for q in Q]); dt = np.diff(t); step = np.linalg.norm(np.diff(P, axis=0), axis=1)
    mv = (dt <= 0.15) & (step > 0.05)
    dL = np.einsum('nji,nj->ni', R[:-1][mv], np.diff(P, axis=0)[mv])   # displacement in the LiDAR frame
    dL /= np.linalg.norm(dL, axis=1)[:, None]
    f = np.median(dL, axis=0); f[2] = 0; f /= np.linalg.norm(f)        # horizontal forward axis in the LiDAR frame
    up = np.array([0, 0, 1.0]); l = np.cross(up, f)
    back = np.mean(dL @ f < 0)
    print(f'===== {oid}: forward axis in LiDAR frame ({f[0]:+.3f}, {f[1]:+.3f}) = azimuth {np.degrees(np.arctan2(f[1], f[0])):.1f} deg in LiDAR xy; motion backward share {100*back:.1f} %')
    s = np.r_[0, np.cumsum(step)]; edges = np.arange(0, s[-1], 5.0); idx = np.searchsorted(s, edges)
    rows = []
    for i0, i1 in zip(idx[:-1], idx[1:]):
        if i1 <= i0 or np.any(dt[i0:i1] > 0.5): continue
        d = P[i1] - P[i0]; ds = np.hypot(d[0], d[1])
        if ds < 3.0: continue
        Rm = R[i0:i1 + 1]
        fe = np.degrees(np.arcsin(np.clip((Rm @ f)[:, 2], -1, 1))).mean()      # LiDAR forward elevation in the map
        le = np.degrees(np.arcsin(np.clip((Rm @ l)[:, 2], -1, 1))).mean()      # LiDAR left elevation in the map
        rows.append((np.degrees(np.arctan(d[2] / ds)), np.arctan2(d[1], d[0]), fe, le))
    r = np.array(rows); slope, head, fe, le = r.T
    M = np.c_[np.ones(len(r)), np.cos(head), np.sin(head)]
    def fit(y, name):
        c, *_ = np.linalg.lstsq(M, y, rcond=None); res = y - M @ c
        print(f'  {name:34s}: const {c[0]:+.2f} deg, world-fixed {np.hypot(c[1],c[2]):.2f} deg toward az {np.degrees(np.arctan2(c[2],c[1])):.0f}, residual std {res.std():.2f} deg')
    fit(slope, 'path slope')
    fit(fe, 'LiDAR forward elevation')
    fit(fe - slope, 'forward elevation - path slope')
    # left elevation vs the world tilt in the lateral direction (heading + 90 deg)
    Ml = np.c_[np.ones(len(r)), np.cos(head + np.pi / 2), np.sin(head + np.pi / 2)]
    c, *_ = np.linalg.lstsq(Ml, le, rcond=None)
    print(f'  {"LiDAR left elevation (lateral fit)":34s}: const {c[0]:+.2f} deg, world-fixed {np.hypot(c[1],c[2]):.2f} deg toward az {np.degrees(np.arctan2(c[2],c[1])):.0f}, residual std {(le-Ml@c).std():.2f} deg')
    # heading bins
    hb = ((np.degrees(head) + 360) % 360 // 45).astype(int)
    print('  by heading (45 deg bins): n, mean path slope, mean forward elevation, mean (fe - slope), mean left elevation')
    for b in range(8):
        k = hb == b
        if k.sum() >= 2:
            print(f'    {b*45:3d}-{b*45+45:3d}: {k.sum():3d}  {slope[k].mean():+6.2f}  {fe[k].mean():+6.2f}  {(fe-slope)[k].mean():+6.2f}  {le[k].mean():+6.2f}')


if __name__ == '__main__':
    for oid in sys.argv[2:]:
        run(sys.argv[1], oid)
