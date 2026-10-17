"""Trajectory judgement of a GLIM dump (traj_lidar.txt): rate/gaps, jumps, return to start, revisit height
consistency, and the tilt of the map (world-fixed plane vs vehicle-fixed climb).
usage: python3 traj_judge.py <maps_dir> <origin_id> [...]"""
import sys, datetime, numpy as np
from scipy.spatial import cKDTree


def quat_to_R(q):  # qx qy qz qw
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def hms(t):
    return datetime.datetime.fromtimestamp(t).strftime('%H:%M:%S')


def judge(maps, oid):
    a = np.loadtxt(f'{maps}/{oid}/source/traj_lidar.txt')
    t, P, Q = a[:, 0], a[:, 1:4], a[:, 4:8]
    dt = np.diff(t); step = np.linalg.norm(np.diff(P, axis=0), axis=1)
    print(f'===== {oid}  {hms(t[0])}-{hms(t[-1])}')
    print(f'GLIM frames {len(t)} over {t[-1]-t[0]:.1f} s = {len(t)/(t[-1]-t[0]):.2f} Hz; gaps >0.15 s {np.sum(dt>0.15)}, >0.5 s {np.sum(dt>0.5)}, max {dt.max():.2f} s')
    for i in np.where(dt > 0.5)[0]:
        print(f'  gap {dt[i]:.2f} s at {hms(t[i])} (t={t[i]-t[0]:.1f} s), moved {step[i]:.2f} m')
    print(f'path {step.sum():.1f} m; start-end xy {np.linalg.norm(P[-1,:2]-P[0,:2]):.2f} m, dz {P[-1,2]-P[0,2]:+.2f} m; z {P[:,2].min():.2f}..{P[:,2].max():.2f}')
    speed = step / np.maximum(dt, 1e-3)
    for i in np.argsort(step)[::-1][:3]:
        print(f'  step {step[i]:.2f} m in {dt[i]:.2f} s at {hms(t[i])} (t={t[i]-t[0]:.1f} s)')
    print(f'  speed (frames with dt<=0.15 s): median {np.median(speed[dt<=0.15]):.2f} m/s, p95 {np.percentile(speed[dt<=0.15],95):.2f}')
    # revisits: same xy (<1.5 m), more than 60 s apart
    tree = cKDTree(P[:, :2]); pairs = tree.query_pairs(1.5, output_type='ndarray')
    pairs = pairs[np.abs(t[pairs[:, 0]] - t[pairs[:, 1]]) > 60] if len(pairs) else pairs
    if len(pairs):
        dz = np.abs(P[pairs[:, 0], 2] - P[pairs[:, 1], 2])
        print(f'revisits (xy<1.5 m, >60 s apart): {len(pairs)} pairs; |dz| median {np.median(dz):.2f} p95 {np.percentile(dz,95):.2f} max {dz.max():.2f} m')
    else:
        print('revisits (xy<1.5 m, >60 s apart): none')
    # world-fixed plane fit of trajectory height
    A = np.c_[P[:, 0], P[:, 1], np.ones(len(P))]; coef, *_ = np.linalg.lstsq(A, P[:, 2], rcond=None)
    res = P[:, 2] - A @ coef; g = np.hypot(coef[0], coef[1])
    h0 = P[min(len(P)-1, np.searchsorted(np.cumsum(np.r_[0, step]), 5.0)), :2] - P[0, :2]; head0 = np.degrees(np.arctan2(h0[1], h0[0]))
    print(f'trajectory plane z = a x + b y: tilt {np.degrees(np.arctan(g)):.2f} deg, uphill azimuth {np.degrees(np.arctan2(coef[1],coef[0])):.0f} deg (initial heading {head0:.0f} deg), residual std {res.std():.2f} m, max |res| {np.abs(res).max():.2f} m')
    # per 5 m pieces: climb rate vs heading -> dz/ds = A + B cos(h) + C sin(h)
    s = np.r_[0, np.cumsum(step)]; edges = np.arange(0, s[-1], 5.0); idx = np.searchsorted(s, edges)
    rows = []
    for i0, i1 in zip(idx[:-1], idx[1:]):
        if i1 <= i0: continue
        if np.any(dt[i0:i1] > 0.5): continue  # skip pieces with a LiDAR gap
        d = P[i1] - P[i0]; ds = np.hypot(d[0], d[1])
        if ds < 3.0: continue
        rows.append((d[2] / ds, np.arctan2(d[1], d[0])))
    if len(rows) > 10:
        r = np.array(rows); M = np.c_[np.ones(len(r)), np.cos(r[:, 1]), np.sin(r[:, 1])]; c, *_ = np.linalg.lstsq(M, r[:, 0], rcond=None)
        print(f'climb per 5 m piece ({len(r)} pieces): heading-independent {np.degrees(np.arctan(c[0])):+.2f} deg (vehicle-fixed), world-fixed tilt {np.degrees(np.arctan(np.hypot(c[1],c[2]))):.2f} deg toward azimuth {np.degrees(np.arctan2(c[2],c[1])):.0f} deg, residual std {np.degrees(np.std(r[:,0]-M@c)):.2f} deg')
    # LiDAR up axis in the world
    R = np.array([quat_to_R(q) for q in Q]); up = R[:, :, 2]
    tilt = np.degrees(np.arccos(np.clip(up[:, 2], -1, 1)))
    print(f'LiDAR z axis vs world z: median {np.median(tilt):.2f} deg (p10 {np.percentile(tilt,10):.2f}, p90 {np.percentile(tilt,90):.2f}); first frame {tilt[0]:.2f} deg')
    # decompose the LiDAR up-axis lean into the vehicle frame: forward = -y of the LiDAR (axis mapping), left = +x
    fwd = -R[:, :, 1]; left = R[:, :, 0]
    lean_fwd = np.degrees(np.arcsin(np.clip(fwd[:, 2], -1, 1)))   # >0: LiDAR forward axis points up (nose up)
    lean_left = np.degrees(np.arcsin(np.clip(left[:, 2], -1, 1)))
    print(f'LiDAR attitude in the map: forward axis elevation median {np.median(lean_fwd):+.2f} deg (p10 {np.percentile(lean_fwd,10):+.2f}, p90 {np.percentile(lean_fwd,90):+.2f}); left axis elevation median {np.median(lean_left):+.2f} deg')
    return t, P


if __name__ == '__main__':
    for oid in sys.argv[2:]:
        judge(sys.argv[1], oid)
