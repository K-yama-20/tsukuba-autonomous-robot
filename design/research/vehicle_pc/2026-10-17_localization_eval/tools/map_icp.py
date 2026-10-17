"""Do two GLIM maps show the same place? Point-to-point ICP between voxelized maps (1 m), started from a top-view candidate
(yaw, shift about the structure-point centroids, as found by map_overlap.py) and, for calibration, from deliberately wrong starts.
usage: python3 map_icp.py <A.pcd> <B.pcd> <dumpA> <dumpB> <yaw_deg> <shift_x> <shift_y>"""
import sys, numpy as np
from scipy.spatial import cKDTree
sys.path.insert(0, '/Users/AYARyoya/Desktop/自己学習/TsukubaChallenge/tsukuba-autonomous-robot/gouda_core')
from gouda_core import map_convert as mc  # noqa: E402


def structure_xy(dump, H=1.18):  # same definition as map_overlap.py (structure points 0.5..2.2 m above trajectory height - H)
    pts = mc.world_points(mc.read_dump(dump)); T = np.loadtxt(f'{dump}/traj_lidar.txt')[:, 1:4]
    d, j = cKDTree(T[:, :2]).query(pts[:, :2]); hag = pts[:, 2] - (T[j, 2] - H)
    k = (d < 20) & (hag > 0.5) & (hag < 2.2)
    return pts[k, :2], T[:, :2]


def read_pcd(path):
    b = open(path, 'rb').read(); i = b.index(b'DATA binary\n') + len(b'DATA binary\n')
    return np.frombuffer(b[i:], dtype=np.float32).reshape(-1, 3).astype(np.float64)


def vox(p, v):
    _, idx = np.unique(np.floor(p / v).astype(np.int64), axis=0, return_index=True); return p[idx]


def icp(A, B, T, dists=(5.0, 3.0, 2.0, 1.0, 0.6), iters=12):
    tree = cKDTree(A)
    for dmax in dists:
        for _ in range(iters):
            Bt = B @ T[:3, :3].T + T[:3, 3]; d, j = tree.query(Bt, distance_upper_bound=dmax); m = np.isfinite(d)
            if m.sum() < 100: return T, 0.0, np.inf
            P, Q = Bt[m], A[j[m]]; cp, cq = P.mean(0), Q.mean(0); H = (P - cp).T @ (Q - cq)
            U, S, Vt = np.linalg.svd(H); D = np.diag([1, 1, np.sign(np.linalg.det(Vt.T @ U.T))]); R = Vt.T @ D @ U.T
            dT = np.eye(4); dT[:3, :3] = R; dT[:3, 3] = cq - R @ cp; T = dT @ T
    Bt = B @ T[:3, :3].T + T[:3, 3]; d, _ = tree.query(Bt)
    return T, np.mean(d < 0.5), np.sqrt(np.mean(np.minimum(d, 1.0) ** 2))


A = vox(read_pcd(sys.argv[1]), 1.0); B = vox(read_pcd(sys.argv[2]), 1.0)
sa, _ = structure_xy(sys.argv[3]); sb, _ = structure_xy(sys.argv[4]); cA, cB = sa.mean(0), sb.mean(0)
yaw, sh = np.radians(float(sys.argv[5])), np.array([float(sys.argv[6]), float(sys.argv[7])])


def init(yaw, sh):
    R2 = np.array([[np.cos(yaw), -np.sin(yaw)], [np.sin(yaw), np.cos(yaw)]]); T = np.eye(4); T[:2, :2] = R2; T[:2, 3] = sh + cA - R2 @ cB
    T[2, 3] = np.median(A[:, 2]) - np.median(B[:, 2]); return T


print(f'A {len(A)} pts, B {len(B)} pts (1 m voxels)')
T, inl, rms = icp(A, B, init(yaw, sh))
ang = np.degrees(np.arctan2(T[1, 0], T[0, 0])); tilt = np.degrees(np.arccos(np.clip(T[2, 2], -1, 1)))
print(f'candidate start: inliers(<0.5 m) {100*inl:.1f} %, rms {rms:.3f} m; result yaw {ang:.1f} deg, tilt {tilt:.2f} deg, t ({T[0,3]:.1f}, {T[1,3]:.1f}, {T[2,3]:.1f})')
rng = np.random.default_rng(1); base = []
for k in range(6):
    T2, i2, r2 = icp(A, B, init(yaw + np.radians(rng.uniform(40, 320)), sh + rng.uniform(-30, 30, 2)))
    base.append(i2)
print(f'wrong starts (6): inliers {", ".join(f"{100*x:.1f}" for x in base)} %')
np.save(sys.argv[2] + '.T_A_B.npy', T)
