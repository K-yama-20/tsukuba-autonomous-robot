"""Forward/backward speed and yaw rate under combined stick input (2026-11-07 second recording, bin 210).

Usage: python3 analyze_turn.py <dir with imu.csv, esp32.csv, odom_lidar.txt>
Forward speed: GLIM displacement projected on the LiDAR -y axis (vehicle forward, intent.md), +-1 GLIM step.
Yaw rate: GLIM heading change, and the IMU gz averaged over +-0.15 s (gz correlates 1.0 with the GLIM yaw rate).
Prints one row every 0.3 s; the reading of the table is in README.md.
"""
import csv, math, statistics as st, sys, os, bisect
d = sys.argv[1]
e = [(float(r['t']), int(r['applied_y_q10000'] or 0) / 1e4, int(r['applied_x_q10000'] or 0) / 1e4) for r in csv.DictReader(open(os.path.join(d, 'esp32.csv')))]
t0 = e[0][0]
I = [(float(r['t']) - t0, float(r['gz'])) for r in csv.DictReader(open(os.path.join(d, 'imu.csv')))]
o = [list(map(float, l.split())) for l in open(os.path.join(d, 'odom_lidar.txt'))]
def yaw(q): x, y, z, w = q; return math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
def inp(t):
    v = (0, 0)
    for r in e:
        if r[0] - t0 <= t: v = r[1:]
        else: break
    return v
for i in range(1, len(o) - 1, 3):
    a, b = o[i - 1], o[i + 1]; dt = b[0] - a[0]; h = yaw(o[i][4:8]); dx, dy = b[1] - a[1], b[2] - a[2]
    v = (dx * math.sin(h) - dy * math.cos(h)) / dt
    w = ((yaw(b[4:8]) - yaw(a[4:8]) + math.pi) % (2 * math.pi) - math.pi) / dt
    t = o[i][0] - t0; y, x = inp(t)
    near = [r[1] for r in I if t - 0.15 <= r[0] <= t + 0.15]
    if not near: continue   # GLIM continues after the rosbag stopped
    gz = st.mean(near)
    print(f'{t:6.2f} in_y={y:+.3f} in_x={x:+.3f} v={v:+.3f} w_glim={w:+.3f} gz={gz:+.3f}')
