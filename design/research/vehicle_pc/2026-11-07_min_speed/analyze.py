"""Speed of EMC-270 near the dead band (2026-11-07 measurement, bin 210).

Inputs (not in the repository): imu.csv and esp32.csv written by extract.py from the rosbag, and GLIM's
odom_lidar.txt (TUM: t x y z qx qy qz qw) of the map made during the same recording.
Usage: python3 analyze.py <dir with imu.csv, esp32.csv, odom_lidar.txt>
Speed = |displacement| over +-1 GLIM step (0.1 s). Motion = speed > 0.03 m/s. IMU onset = 3 samples beyond 6 sigma of
the 3 s before the section. The IMU integral is printed only for comparison (tilt makes it unusable).
"""
import csv, math, statistics as st, sys, os
d = sys.argv[1]
e = [(float(r['t']), int(r['applied_y_q10000'] or 0) / 1e4, int(r['applied_x_q10000'] or 0) / 1e4) for r in csv.DictReader(open(os.path.join(d, 'esp32.csv')))]
t0 = e[0][0]
I = [tuple(map(float, (r['t'], r['ax'], r['ay'], r['az'], r['gz']))) for r in csv.DictReader(open(os.path.join(d, 'imu.csv')))]
o = [list(map(float, l.split())) for l in open(os.path.join(d, 'odom_lidar.txt'))]
sp = [(o[i][0] - t0, math.hypot(o[i + 1][1] - o[i - 1][1], o[i + 1][2] - o[i - 1][2]) / (o[i + 1][0] - o[i - 1][0])) for i in range(1, len(o) - 1)]
def inp(t):
    v = (0, 0)
    for r in e:
        if r[0] - t0 <= t: v = r[1:]
        else: break
    return v
SECTIONS = [(9.4, 22), (25.5, 38), (40.8, 52), (53.8, 84)]   # seconds from the first ESP32 status, read from the input timeline
for a, b in SECTIONS:
    S = [(t, s) for t, s in sp if a <= t <= b]
    mv = [t for t, s in S if s > 0.03]; on, off = mv[0], mv[-1]
    steady = [s for t, s in S if on + 1.5 <= t <= off - 0.5]
    pre = [r for r in I if a - 3 <= r[0] - t0 < a]
    m = [st.mean(r[i] for r in pre) for i in (1, 2)]; sd = [st.pstdev(r[i] for r in pre) for i in (1, 2)]
    seg = [r for r in I if a <= r[0] - t0 <= b]
    onset = next(seg[i][0] - t0 for i in range(len(seg) - 3) if all(max(abs(seg[i + j][1] - m[0]) / sd[0], abs(seg[i + j][2] - m[1]) / sd[1]) > 6 for j in range(3)))
    lvl = inp(on)[0]; reach = next(r[0] - t0 for r in e if a <= r[0] - t0 and abs(r[1]) >= abs(lvl) - 1e-6)
    print(f'section {a}-{b}: input at GLIM motion {lvl:+.3f}, reached at {reach:.2f}, IMU onset {onset:.2f} (delay {onset - reach:.2f} s), '
          f'GLIM motion {on:.2f}-{off:.2f}, steady {st.mean(steady):.3f} m/s ({min(steady):.3f}-{max(steady):.3f}), distance {sum(s * 0.1 for t, s in S):.2f} m, '
          f'input at stop {inp(off)[0]:+.3f}, gravity in IMU y before {m[1]:+.3f} m/s2')
