"""Travel direction expressed in the LiDAR frame (elevation; negative = the LiDAR's front points above the travel direction) and the
azimuth of the trajectory-plane tilt relative to the initial forward heading (+90 = left).
usage: python3 tilt_extra.py <maps_dir> <origin_id> [...]"""
import sys, numpy as np
from traj_judge import quat_to_R
for oid in sys.argv[2:]:
    a = np.loadtxt(f'{sys.argv[1]}/{oid}/source/traj_lidar.txt'); t, P, Q = a[:, 0], a[:, 1:4], a[:, 4:8]
    R = np.array([quat_to_R(q) for q in Q]); dt = np.diff(t); st = np.linalg.norm(np.diff(P, axis=0), axis=1)
    mv = (dt <= 0.15) & (st > 0.05)
    dL = np.einsum('nji,nj->ni', R[:-1][mv], np.diff(P, axis=0)[mv]); dL /= np.linalg.norm(dL, axis=1)[:, None]
    pitch = np.degrees(np.arcsin(dL[:, 2]))
    f = np.median(dL, axis=0); f[2] = 0; f /= np.linalg.norm(f)
    fw = R[0] @ f; h0 = np.degrees(np.arctan2(fw[1], fw[0]))
    A = np.c_[P[:, 0], P[:, 1], np.ones(len(P))]; c, *_ = np.linalg.lstsq(A, P[:, 2], rcond=None)
    az = np.degrees(np.arctan2(c[1], c[0])); g = np.degrees(np.arctan(np.hypot(c[0], c[1])))
    up0 = R[0][:, 2]; tilt0 = np.degrees(np.arccos(up0[2]))
    print(f'{oid}: travel direction elevation in the LiDAR frame median {np.median(pitch):+.2f} deg (p25 {np.percentile(pitch,25):+.2f}, p75 {np.percentile(pitch,75):+.2f}); '
          f'initial forward heading {h0:.0f} deg; plane tilt {g:.2f} deg, uphill az {az:.0f} = {((az-h0+180)%360)-180:+.0f} deg from the initial heading; first-frame LiDAR z tilt {tilt0:.2f} deg')
