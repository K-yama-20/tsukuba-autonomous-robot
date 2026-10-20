"""One pass over a rosbag2 MCAP: IMU (all), LiDAR frame statistics (all), packet loss (all), and the ground plane
in the LiDAR frame for every k-th LiDAR frame (RANSAC on low points in an annulus).
usage: python3 extract_bag.py <bag_0.mcap> <out.npz> [every_k=5]"""
import sys, struct, numpy as np
import mcap_min as m

R_IN, R_OUT, Z_LO, Z_HI = 3.0, 10.0, -2.2, -0.2       # annulus [m] and height window below the sensor [m]
MAX_TILT_DEG, INLIER_M, ITERS, MIN_INLIERS = 20.0, 0.05, 150, 300
rng = np.random.default_rng(0)


def ground_plane(x, y, z):
    r = np.hypot(x, y); k = (r > R_IN) & (r < R_OUT) & (z > Z_LO) & (z < Z_HI) & np.isfinite(z)
    P = np.c_[x[k], y[k], z[k]].astype(np.float64)
    if len(P) < MIN_INLIERS: return None
    if len(P) > 6000: P = P[rng.choice(len(P), 6000, replace=False)]
    best = None; cmax = np.cos(np.radians(MAX_TILT_DEG))
    for _ in range(ITERS):
        a, b, c = P[rng.choice(len(P), 3, replace=False)]
        n = np.cross(b - a, c - a); nn = np.linalg.norm(n)
        if nn < 1e-6: continue
        n /= nn
        if n[2] < 0: n = -n
        if n[2] < cmax: continue
        d = (P - a) @ n; inl = np.abs(d) < INLIER_M; s = inl.sum()
        if best is None or s > best[0]: best = (s, inl)
    if best is None or best[0] < MIN_INLIERS: return None
    Q = P[best[1]]; c = Q.mean(0); _, _, Vt = np.linalg.svd(Q - c); n = Vt[2]
    if n[2] < 0: n = -n
    h = -(c @ n)   # sensor height above the plane (origin to plane distance)
    rms = np.sqrt(np.mean(((Q - c) @ n) ** 2))
    return n, h, best[0], len(P), rms


def main(bag, out, every=5):
    imu = []; fr = []; loss = []; gp = []; nfr = 0
    for topic, lt, d in m.read(bag, {'/sensors/imu/data', '/sensors/xt32/points', '/lidar_packets_loss'}):
        if topic == '/sensors/imu/data':
            st, q, w, a = m.imu(d); imu.append((st, lt * 1e-9, *w, *a))
        elif topic == '/lidar_packets_loss':
            tot, lo = struct.unpack_from('<II', d, 4); loss.append((lt * 1e-9, tot, lo))
        else:
            want = ('x', 'y', 'z', 'timestamp') if nfr % every == 0 else ('timestamp',)
            st, fid, o, _ = m.cloud(d, want)
            ts = o['timestamp']; fr.append((st, lt * 1e-9, len(ts), float(ts.min()), float(ts.max())))
            if nfr % every == 0:
                g = ground_plane(o['x'], o['y'], o['z'])
                gp.append((st, *(g[0] if g else (np.nan,) * 3), *(g[1:] if g else (np.nan,) * 4)))
            nfr += 1
            if nfr % 1000 == 0: print(nfr, flush=True)
    np.savez(out, imu=np.array(imu), frames=np.array(fr), loss=np.array(loss), ground=np.array(gp))
    print('done', out, len(imu), len(fr), len(loss), len(gp))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 5)
