"""IMU gravity direction vs LiDAR ground normal (both in their own sensor frames; /config gives both the same axis mapping and
T_lidar_imu has no rotation). Static intervals and the whole run (terrain slopes average out over a closed loop).
Sensor axes (/config): +x left, -y forward, +z up. For an up vector u in a sensor frame: left side raised = asin(u_x), nose raised = asin(-u_y).
usage: python3 imu_lidar_tilt.py <bag.npz> [forward_x forward_y]   (forward axis in the sensor xy; default from the GLIM trajectory analysis)"""
import sys, datetime, numpy as np

d = np.load(sys.argv[1]); imu, gp = d['imu'], d['ground']
fwd = np.array([float(sys.argv[2]), float(sys.argv[3])]) if len(sys.argv) > 3 else np.array([-0.158, -0.987])
fwd /= np.linalg.norm(fwd); left = np.array([-fwd[1], fwd[0]])   # left = forward rotated +90 deg about +z
hms = lambda t: datetime.datetime.fromtimestamp(t).strftime('%H:%M:%S')
st = imu[:, 0]; w = imu[:, 2:5]; a = imu[:, 5:8]


def angles(u):
    u = u / np.linalg.norm(u, axis=-1, keepdims=True)
    lx, ny = np.degrees(np.arcsin(u[..., 0])), np.degrees(np.arcsin(-u[..., 1]))          # sensor axes
    vl = np.degrees(np.arcsin(u[..., :2] @ left)); vn = np.degrees(np.arcsin(u[..., :2] @ fwd))   # vehicle axes: left raised, nose raised
    return lx, ny, vl, vn


# ground samples
gt, n, h, inl, npts, rms = gp[:, 0], gp[:, 1:4], gp[:, 4], gp[:, 5], gp[:, 6], gp[:, 7]
good = np.isfinite(h) & (inl >= 800) & (rms < 0.03) & (h > 0.9) & (h < 1.5)
print(f'ground samples {len(gp)}, good {good.sum()} (inliers>=800, rms<0.03 m, height 0.9..1.5 m); sensor height above the plane: median {np.median(h[good]):.3f} m, p10 {np.percentile(h[good],10):.3f}, p90 {np.percentile(h[good],90):.3f}')

# IMU up at each ground sample: mean specific force over +-0.5 s
idx0 = np.searchsorted(st, gt - 0.5); idx1 = np.searchsorted(st, gt + 0.5)
uI = np.array([a[i:j].mean(0) if j > i else [np.nan] * 3 for i, j in zip(idx0, idx1)])
gyr = np.array([np.linalg.norm(w[i:j], axis=1).max() if j > i else np.nan for i, j in zip(idx0, idx1)])
k = good & np.isfinite(uI[:, 0])

# static: gyro max < 0.02 rad/s within +-0.5 s and |acc| within 0.05 of its median
amag = np.linalg.norm(uI, axis=1); stat = k & (gyr < 0.02) & (np.abs(amag - np.nanmedian(amag)) < 0.05)
# group static samples into intervals (gap > 1.5 s splits)
grp = []; cur = []
for i in np.where(stat)[0]:
    if cur and gt[i] - gt[cur[-1]] > 1.5: grp.append(cur); cur = []
    cur.append(i)
if cur: grp.append(cur)
print('static intervals (>= 2 s): IMU up vs LiDAR ground normal, angles in degrees [sensor: left-raised, nose-raised(-y)] [vehicle: left-raised, nose-raised]')
rows = []
for g in grp:
    if gt[g[-1]] - gt[g[0]] < 2.0: continue
    i0, i1 = np.searchsorted(st, gt[g[0]] - 0.5), np.searchsorted(st, gt[g[-1]] + 0.5)
    ui = a[i0:i1].mean(0); nl = np.median(n[g], axis=0)
    A, B = angles(ui), angles(nl)
    rows.append((A, B))
    print(f'  {hms(gt[g[0]])}-{hms(gt[g[-1]])} ({gt[g[-1]]-gt[g[0]]:.0f} s, {len(g)} planes): IMU [{A[0]:+.2f} {A[1]:+.2f}] [{A[2]:+.2f} {A[3]:+.2f}]  LiDAR [{B[0]:+.2f} {B[1]:+.2f}] [{B[2]:+.2f} {B[3]:+.2f}]  IMU-LiDAR vehicle [{A[2]-B[2]:+.2f} {A[3]-B[3]:+.2f}]  plane height {np.median(h[g]):.3f} m')

# whole run (moving and static), pairs with good planes
A = angles(uI[k]); B = angles(n[k])
print(f'whole run ({k.sum()} pairs): mean IMU vehicle [{A[2].mean():+.2f} {A[3].mean():+.2f}], mean LiDAR vehicle [{B[2].mean():+.2f} {B[3].mean():+.2f}]; '
      f'difference IMU-LiDAR per pair: left-raised median {np.median(A[2]-B[2]):+.2f} (p25 {np.percentile(A[2]-B[2],25):+.2f}, p75 {np.percentile(A[2]-B[2],75):+.2f}), '
      f'nose-raised median {np.median(A[3]-B[3]):+.2f} (p25 {np.percentile(A[3]-B[3],25):+.2f}, p75 {np.percentile(A[3]-B[3],75):+.2f})')
# rotation (small angle) that best maps LiDAR normals onto IMU up: Kabsch on the pairs
P = n[k] / np.linalg.norm(n[k], axis=1)[:, None]; Q = uI[k] / np.linalg.norm(uI[k], axis=1)[:, None]
U, S, Vt = np.linalg.svd(P.T @ Q); D = np.diag([1, 1, np.sign(np.linalg.det(U @ Vt))]); Rm = (U @ D @ Vt).T   # Q ~ Rm P
ez = Rm @ np.array([0, 0, 1.0]); print(f'Kabsch R (LiDAR normal -> IMU up): image of LiDAR +z in the IMU frame = ({ez[0]:+.4f}, {ez[1]:+.4f}, {ez[2]:+.4f}), angle {np.degrees(np.arccos(ez[2])):.2f} deg; '
      f'residual angle median {np.degrees(np.median(np.arccos(np.clip(np.sum((P@Rm.T)*Q,1),-1,1)))):.2f} deg')
