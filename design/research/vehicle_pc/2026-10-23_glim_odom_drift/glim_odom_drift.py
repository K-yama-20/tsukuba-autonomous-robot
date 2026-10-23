# ANALYSIS ONLY (bin 142): drift of GLIM's odometry (odom_lidar.txt) relative to GLIM's own optimized trajectory
# (traj_lidar.txt, after the global mapping's submap optimization) in the same mapping dump.
# The reference is not ground truth: where the global mapping found no extra constraint, both agree and the drift is
# under-estimated (inside one submap the two agree exactly, so short windows read 0). Usage: python3 -I glim_odom_drift.py <dump dir> [<dump dir> ...]
import math

GAP_S = 1.5   # the dumps hold keyframe-like rows (about 2..10 per s), so only longer gaps are listed
import sys
from pathlib import Path


def read(path):
    rows = []
    for line in Path(path).read_text().splitlines():
        f = line.split()
        if len(f) == 8:
            rows.append(tuple(float(v) for v in f))
    return rows


def qmul(a, b):
    ax, ay, az, aw = a; bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz)


def rot(q, v):
    r = qmul(qmul(q, (*v, 0.0)), (-q[0], -q[1], -q[2], q[3]))
    return r[:3]


def rel(p0, p1):
    """p0^-1 * p1 (translation in p0's frame, quaternion)."""
    qi = (-p0[3], -p0[4], -p0[5], p0[6])
    d = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
    return (*rot(qi, d), *qmul(qi, p1[3:]))


def yaw(q):
    x, y, z, w = q
    return math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


def wrap(a):
    return math.atan2(math.sin(a), math.cos(a))


def pct(v, p):
    if not v:
        return float('nan')
    s = sorted(v)
    return s[min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))]


def errors(odom, traj, i, j):
    ro, rt = rel(odom[i][1:], odom[j][1:]), rel(traj[i][1:], traj[j][1:])
    # express both relative translations in the traj start frame (same as odom start frame by construction of rel)
    dt = math.hypot(ro[0] - rt[0], ro[1] - rt[1])
    dyaw = abs(wrap(yaw(ro[3:]) - yaw(rt[3:])))
    return dt, math.degrees(dyaw)


def main(dirs):
    for d in dirs:
        odom, traj = read(Path(d) / 'odom_lidar.txt'), read(Path(d) / 'traj_lidar.txt')
        n = min(len(odom), len(traj))
        same_t = all(abs(odom[k][0] - traj[k][0]) < 1e-6 for k in range(n))
        odom, traj = odom[:n], traj[:n]
        t0 = traj[0][0]
        s = [0.0]
        for k in range(1, n):
            s.append(s[-1] + math.hypot(traj[k][1] - traj[k - 1][1], traj[k][2] - traj[k - 1][2]))
        gaps = [(traj[k - 1][0] - t0, traj[k][0] - traj[k - 1][0]) for k in range(1, n) if traj[k][0] - traj[k - 1][0] > GAP_S]
        end = errors(odom, traj, 0, n - 1)
        print(f'== {Path(d).resolve().name}  rows {n} ({n / max(traj[-1][0] - t0, 1e-9):.1f} per s)  same stamps {same_t}  duration {traj[-1][0] - t0:.1f} s  path {s[-1]:.1f} m')
        print(f'   whole run (start aligned): horizontal {end[0]:.3f} m, yaw {end[1]:.2f} deg')
        print(f'   row gaps > {GAP_S} s: {len(gaps)}' + ''.join(f'\n     at {g[0]:.1f} s: {g[1]:.2f} s' for g in gaps))
        for L in (5, 10, 20, 50):
            et, ey, j = [], [], 0
            for i in range(n):
                while j < n and s[j] - s[i] < L:
                    j += 1
                if j >= n:
                    break
                e = errors(odom, traj, i, j); et.append(e[0]); ey.append(e[1])
            if et:
                print(f'   over {L:>3} m ({len(et)} windows): horiz med {pct(et, 50):.3f} p95 {pct(et, 95):.3f} max {max(et):.3f} m '
                      f'(p95 {100 * pct(et, 95) / L:.2f} %), yaw med {pct(ey, 50):.2f} p95 {pct(ey, 95):.2f} max {max(ey):.2f} deg')
            else:
                print(f'   over {L:>3} m: no window (path too short)')
        for T in (3, 10, 30, 60):
            et, ey, j = [], [], 0
            for i in range(n):
                while j < n and traj[j][0] - traj[i][0] < T:
                    j += 1
                if j >= n:
                    break
                e = errors(odom, traj, i, j); et.append(e[0]); ey.append(e[1])
            if et:
                print(f'   over {T:>3} s ({len(et)} windows): horiz med {pct(et, 50):.3f} p95 {pct(et, 95):.3f} max {max(et):.3f} m, '
                      f'yaw p95 {pct(ey, 95):.2f} max {max(ey):.2f} deg')
        for g0, glen in gaps:
            i = max(k for k in range(n) if traj[k][0] - t0 <= g0)
            j = min(n - 1, i + 1)
            e = errors(odom, traj, max(0, i - 10), min(n - 1, j + 10))
            print(f'   across the gap at {g0:.1f} s (1 s before to 1 s after): horiz {e[0]:.3f} m, yaw {e[1]:.2f} deg; '
                  f'moved {s[min(n - 1, j + 10)] - s[max(0, i - 10)]:.2f} m')


if __name__ == '__main__':
    main(sys.argv[1:])
