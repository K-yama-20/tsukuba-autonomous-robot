"""Compare (A) pose-difference speed with (B) GLIM v_world_imu, and (A) yaw rate with IMU gz.

Usage: python3 -I analyze_cmp.py <data/bX> <b1|b2>
Times: seconds from the first ESP32 status (README of 2026-11-07_min_speed).
A_rel : relay as implemented (odometry_core.body_twist): R_prev^T (p_cur - p_prev)/dt, stamped at t_cur.
A_cen : central difference R_i^T (p_{i+1} - p_{i-1}) / (t_{i+1} - t_{i-1}), stamped at t_i (offline only, needs the next frame).
B     : R_i^T v_world_imu_i (rotation of T_world_lidar = rotation of T_world_imu, T_lidar_imu has no rotation).
Forward = IMU/LiDAR -y.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from load import *

d, tag = sys.argv[1], sys.argv[2]
FWD = np.array([0, -1, 0])
te, ex, ey = load_esp(os.path.join(d, 'esp32.csv')); t0 = te[0]; te = te - t0
imu = load_imu(os.path.join(d, 'imu.csv')); ti = imu['t'] - t0; af = -imu['ay']; gz = imu['gz']
G = np.stack([imu['gx'], imu['gy'], imu['gz']], 1)
fr, _, _ = load_dump(os.path.join(d, 'dump', 'data.txt'))
tI, pI, RI = load_tum(os.path.join(d, 'dump', 'odom_imu.txt')); tL, pL, RL = load_tum(os.path.join(d, 'dump', 'odom_lidar.txt'))
t = tI - t0; n = len(t)
v = np.array([f['v'] for f in fr]); Rw = np.array([f['T_world_lidar'][:3, :3] for f in fr])
yaw = np.unwrap(np.array([yaw_of_R(R) for R in RI]))

def rel(p, R):
    o = np.full((n, 3), np.nan)
    for i in range(1, n): o[i] = R[i - 1].T @ (p[i] - p[i - 1]) / (t[i] - t[i - 1])
    return o
def cen(p, R):
    o = np.full((n, 3), np.nan)
    for i in range(1, n - 1): o[i] = R[i].T @ (p[i + 1] - p[i - 1]) / (t[i + 1] - t[i - 1])
    return o
Arel = rel(pI, RI); Acen = cen(pI, RI); ArelL = rel(pL, RL)
B3 = np.array([Rw[i].T @ v[i] for i in range(n)])
S = {'A_rel': Arel @ FWD, 'A_cen': Acen @ FWD, 'B': B3 @ FWD}
wA = np.full(n, np.nan); wA[1:] = np.diff(yaw) / np.diff(t)
wAc = np.full(n, np.nan); wAc[1:-1] = (yaw[2:] - yaw[:-2]) / (t[2:] - t[:-2])
# world-z angular rate from the IMU (gyro rotated by the GLIM attitude at the nearest frame)
idx = np.clip(np.searchsorted(t, ti), 0, n - 1)
wz_world = np.einsum('ij,ij->i', Rw[idx][:, 2, :], G)
inside = (ti >= t[0]) & (ti <= t[-1])
print(f'[{tag}] frames {n}, GLIM {t[0]:.2f}-{t[-1]:.2f} s, IMU {ti[0]:.2f}-{ti[-1]:.2f} s ({len(ti)/(ti[-1]-ti[0]):.1f} Hz)')
print(f'  A_rel IMU vs LiDAR file: max |diff| fwd {np.nanmax(np.abs((Arel-ArelL)@FWD)):.4f} m/s')
mv = np.abs(S['A_cen']) > 0.05
mf = mv & (S['A_cen'] > 0)
print(f'  axis check signed (A_cen>0.05): mean x/fwd A {np.nanmean(Acen[mf,0])/np.nanmean(Acen[mf]@FWD):+.3f}, B {np.mean(B3[mf,0])/np.mean(B3[mf]@FWD):+.3f}; reverse A {np.nanmean(Acen[mv&(S["A_cen"]<0),0])/np.nanmean(Acen[mv&(S["A_cen"]<0)]@FWD):+.3f}')
print(f'  axis check (|A_cen|>0.05): mean |lateral x|/|fwd| A {np.nanmean(np.abs(Acen[mv,0]))/np.nanmean(np.abs(Acen[mv]@FWD)):.3f}, B {np.mean(np.abs(B3[mv,0]))/np.mean(np.abs(B3[mv]@FWD)):.3f}')

# ---------- still windows: stick exactly 0, from 1.5 s after it became 0 to 0.2 s before it leaves 0
z = (ex == 0) & (ey == 0); W = []
i = 0
while i < len(te):
    if z[i]:
        j = i
        while j + 1 < len(te) and z[j + 1]: j += 1
        a, b = te[i] + 1.5, te[j] - 0.2
        if j + 1 < len(te): b = min(b, te[j + 1] - 0.2)
        a, b = max(a, t[0] + 0.3), min(b, t[-1] - 0.3)
        if b - a >= 1.5: W.append((a, b))
        i = j + 1
    else: i += 1

def stats(sig, a, b):
    m = (t >= a) & (t <= b) & ~np.isnan(sig); x = sig[m]
    return x
def pooled(sig, wins, detrend=False):
    xs, ds = [], []
    for a, b in wins:
        x = stats(sig, a, b); tt = t[(t >= a) & (t <= b) & ~np.isnan(sig)]
        if len(x) < 5: continue
        r = x - (np.polyval(np.polyfit(tt, x, 1), tt) if detrend else x.mean())
        xs.append(r); ds.append(np.diff(x))
    xs = np.concatenate(xs); ds = np.concatenate(ds)
    return np.sqrt(np.mean(xs ** 2)), np.sqrt(np.mean(ds ** 2)), len(xs)

quiet = []
for a, b in W:
    m = (ti >= a) & (ti <= b)
    quiet.append((a, b, np.std(gz[m]), np.std(af[m])))
print('  still windows (stick 0): ' + ', '.join(f'{a:.1f}-{b:.1f} (gz sd {g*1e3:.1f} mrad/s, a_f sd {s:.3f})' for a, b, g, s in quiet))
gzq = np.median([q[2] for q in quiet]); afq = np.median([q[3] for q in quiet])
Wq = [(a, b) for a, b, g, s in quiet if g < 2 * gzq and s < 2 * afq]
print(f'  quiet windows used: {len(Wq)}/{len(W)}, total {sum(b-a for a,b in Wq):.1f} s')
for k in ('A_rel', 'A_cen', 'B'):
    sd, dsd, nn = pooled(S[k], Wq)
    m = np.concatenate([stats(S[k], a, b) for a, b in Wq])
    print(f'  STILL fwd {k:6s}: sd {sd*1e3:6.2f} mm/s, diff sd {dsd*1e3:6.2f} mm/s, mean {np.mean(m)*1e3:+6.2f} mm/s, max|.| {np.max(np.abs(m))*1e3:5.1f}, n {nn}')
for k, sig in (('wA_rel', wA), ('wA_cen', wAc)):
    sd, dsd, nn = pooled(sig, Wq)
    print(f'  STILL yaw {k}: sd {sd*1e3:.2f} mrad/s, diff sd {dsd*1e3:.2f} mrad/s')
# IMU gz averaged over the frame intervals (what an ideal 10 Hz yaw rate would see)
cg = np.concatenate([[0], np.cumsum(0.5 * (gz[1:] + gz[:-1]) * np.diff(ti))])
def gz_mean(a, b): return (np.interp(b, ti, cg) - np.interp(a, ti, cg)) / (b - a)
gzi = np.full(n, np.nan); gzi[1:] = gz_mean(t[:-1], t[1:])
sd, dsd, _ = pooled(gzi, Wq); print(f'  STILL gz mean over frame intervals: sd {sd*1e3:.2f} mrad/s, diff sd {dsd*1e3:.2f}; raw gz sd (median window) {gzq*1e3:.2f} mrad/s')

# ---------- motion segments
def onoff(a, b, thr=0.03):
    m = (t >= a) & (t <= b) & (np.abs(S['A_cen']) > thr); tt = t[m]; return tt[0], tt[-1]
if tag == 'b1':
    SEC = {'fwd1': (9.4, 22), 'fwd2': (25.5, 38), 'rev1': (40.8, 52), 'rev2': (53.8, 84)}
    steady = {}
    for k, (a, b) in SEC.items():
        on, off = onoff(a, b); steady[k] = (on + 1.5, off - 0.5)
    for k, (a, b) in steady.items():
        line = f'  STEADY {k} {a:.1f}-{b:.1f}:'
        for s in ('A_rel', 'A_cen', 'B'):
            x = stats(S[s], a, b); sd, dsd, _ = pooled(S[s], [(a, b)]); sdt, _, _ = pooled(S[s], [(a, b)], True)
            line += f' {s} mean {x.mean():+.4f} sd {sd*1e3:.1f} (detr {sdt*1e3:.1f}) dsd {dsd*1e3:.1f} |'
        print(line + ' [m/s; sd, dsd in mm/s]')
    # B - A_cen difference during the steady segments
    for k, (a, b) in steady.items():
        m = (t >= a) & (t <= b)
        print(f'  STEADY {k}: mean(B - A_cen) {np.nanmean(S["B"][m]-S["A_cen"][m])*1e3:+.2f} mm/s, sd(B - A_cen) {np.nanstd(S["B"][m]-S["A_cen"][m])*1e3:.2f} mm/s')

# ---------- (a) lag between A and B: B(t) ~ X(t + tau); tau > 0 means X lags B
def lag_fit(x, y, tmask, taus=np.arange(-0.3, 0.3001, 0.001)):
    """returns tau minimising RMS(y(t) - x(t + tau)) over the frames in tmask, x linearly interpolated"""
    ok = ~np.isnan(x); best = None
    for tau in taus:
        xi = np.interp(t[tmask] + tau, t[ok], x[ok]); e = np.sqrt(np.nanmean((y[tmask] - xi) ** 2))
        if best is None or e < best[1]: best = (tau, e)
    return best
mot = np.zeros(n, bool)
for i in np.where(np.abs(S['A_cen']) > 0.02)[0]: mot[max(0, i - 15):i + 16] = True
mot &= (t > t[0] + 0.5) & (t < t[-1] - 0.5)
for k in ('A_rel', 'A_cen'):
    tau, e = lag_fit(S[k], S['B'], mot)
    e0 = np.sqrt(np.nanmean((S['B'][mot] - S[k][mot]) ** 2))
    print(f'  LAG fwd {k} vs B: tau {tau*1e3:+.0f} ms ({k} later than B if +), rms at tau {e*1e3:.1f} mm/s, rms at 0 {e0*1e3:.1f} mm/s, n {mot.sum()}')
# cross-correlation on a 1 ms grid (mean removed), motion region of whole run
g = np.arange(t[1] + 0.2, t[-2] - 0.2, 0.001)
def xc(x, y, maxlag=300):
    ok = ~np.isnan(x); xi = np.interp(g, t[ok], x[ok]); ok = ~np.isnan(y); yi = np.interp(g, t[ok], y[ok])
    xi -= xi.mean(); yi -= yi.mean(); best = None
    for L in range(-maxlag, maxlag + 1):
        c = np.dot(xi[max(0, L):len(xi) + min(0, L)], yi[max(0, -L):len(yi) - max(0, L)]) / (np.linalg.norm(xi) * np.linalg.norm(yi))
        if best is None or c > best[1]: best = (L, c)
    return best
for k in ('A_rel', 'A_cen'):
    L, c = xc(S[k], S['B']); print(f'  XCORR fwd {k} vs B: peak at {k} later by {L} ms, r {c:.4f}')

# ---------- (b) motion starts
cross = []
sa = np.abs(S['A_cen'])
for i in range(1, n - 1):
    if sa[i] > 0.03 and sa[i - 1] <= 0.03:
        w = (t >= t[i] - 2.3) & (t <= t[i] - 0.4)
        if t[i] - 2.3 > t[0] and np.all(sa[w] < 0.015): cross.append((i, t[i] - 2.3, t[i] - 0.1))
def first_cross(sig, a, sgn, thr=0.03):
    for i in range(1, n):
        if t[i] >= a and not np.isnan(sig[i - 1]) and not np.isnan(sig[i]) and sgn * sig[i] >= thr and sgn * sig[i - 1] < thr:
            return t[i - 1] + (thr - sgn * sig[i - 1]) / (sgn * sig[i] - sgn * sig[i - 1]) * (t[i] - t[i - 1])
    return np.nan
rows = []
for i, qs, ls in cross:
    sgn = np.sign(S['A_cen'][i])
    wa, wb = max(qs, ls - 3.0), ls - 0.5
    if wb - wa < 1.0: continue
    m = (ti >= wa) & (ti <= wb); mu, sd = af[m].mean(), af[m].std()
    seg = np.where((ti > wb) & (ti < t[i] + 1.0))[0]
    on = next((ti[seg[k]] for k in range(len(seg) - 3) if all(sgn * (af[seg[k + q]] - mu) > 6 * sd for q in range(3))), np.nan)
    vint = np.cumsum((af[seg] - mu) * np.r_[np.diff(ti[seg]), 0.01])
    kk = np.where(sgn * vint >= 0.03)[0]; tint = ti[seg[kk[0]]] if len(kk) else np.nan
    gxb = imu['gx'][m].mean(); dphi = np.cumsum((imu['gx'][seg] - gxb) * np.r_[np.diff(ti[seg]), 0.01])
    vint2 = np.cumsum((af[seg] + 9.80 * dphi - mu) * np.r_[np.diff(ti[seg]), 0.01])
    kk = np.where(sgn * vint2 >= 0.03)[0]; tint2 = ti[seg[kk[0]]] if len(kk) else np.nan
    jj = np.searchsorted(ti[seg], tint + 0.3); dph = np.degrees(dphi[min(jj, len(dphi) - 1)])
    cr = {k: first_cross(S[k], wb, sgn) for k in ('A_rel', 'A_cen', 'B')}
    rows.append((t[i], sgn, on, tint, cr))
    print(f'  START {"fwd" if sgn>0 else "rev"} near {t[i]:.2f}: a_f bias {mu:+.3f} sd {sd:.3f} m/s2 (window {wa:.1f}-{wb:.1f}); '
          f'accel 6sd onset {on:.3f}, int.accel 0.03 at {tint:.3f}; 0.03 m/s crossing A_rel {cr["A_rel"]:.3f}, A_cen {cr["A_cen"]:.3f}, B {cr["B"]:.3f}'
          f' | pitch-corr int 0.03 at {tint2:.3f} (pitch change {dph:+.2f} deg by +0.3 s)'
          f' | rel. to int.accel: A_rel {1e3*(cr["A_rel"]-tint):+.0f} ms, A_cen {1e3*(cr["A_cen"]-tint):+.0f}, B {1e3*(cr["B"]-tint):+.0f}, onset {1e3*(on-tint):+.0f}')

# ---------- (c) yaw rate vs gz
turn = np.zeros(n, bool)
for i in np.where(np.abs(gzi) > 0.03)[0]: turn[max(1, i - 10):i + 11] = True
turn &= (t > ti[0] + 0.5) & (t < min(ti[-1], t[-1]) - 0.5)
if turn.sum() > 20 and np.sum(np.abs(gzi) > 0.05) > 10:
    best = None
    for tau in np.arange(-0.3, 0.3001, 0.001):
        y = gz_mean(t[:-1] + tau, t[1:] + tau); e = np.sqrt(np.mean((wA[1:][turn[1:]] - y[turn[1:]]) ** 2))
        if best is None or e < best[1]: best = (tau, e)
    print(f'  YAW interval-matched: gz window shifted by {best[0]*1e3:+.0f} ms fits best (rms {best[1]*1e3:.1f} mrad/s; frames {turn.sum()})')
    # cross-correlation of the relay signal as stamped vs raw gz (and vs world-z rate)
    g = np.arange(max(t[1], ti[0]) + 0.3, min(t[-1], ti[-1]) - 0.3, 0.001)
    def xc2(x, y_t, y, maxlag=300):
        ok = ~np.isnan(x); xi = np.interp(g, t[ok], x[ok]); yi = np.interp(g, y_t, y); xi -= xi.mean(); yi -= yi.mean(); best = None
        for L in range(-maxlag, maxlag + 1):
            c = np.dot(xi[max(0, L):len(xi) + min(0, L)], yi[max(0, -L):len(yi) - max(0, L)]) / (np.linalg.norm(xi) * np.linalg.norm(yi))
            if best is None or c > best[1]: best = (L, c)
        return best
    for k, sig in (('wA_rel', wA), ('wA_cen', wAc)):
        L, c = xc2(sig, ti, gz); print(f'  YAW XCORR {k} vs raw gz: {k} later by {L} ms, r {c:.4f}')
    # amplitude: slope through origin of wA vs interval-mean gz and vs interval-mean world-z rate
    cw = np.concatenate([[0], np.cumsum(0.5 * (wz_world[1:] + wz_world[:-1]) * np.diff(ti))])
    wzi = np.full(n, np.nan); wzi[1:] = (np.interp(t[1:], ti, cw) - np.interp(t[:-1], ti, cw)) / np.diff(t)
    m = turn & (np.abs(gzi) > 0.05) & ~np.isnan(wA)
    k1 = np.sum(wA[m] * gzi[m]) / np.sum(gzi[m] ** 2); k2 = np.sum(wA[m] * wzi[m]) / np.sum(wzi[m] ** 2)
    print(f'  YAW amplitude (|gz|>0.05, frames {m.sum()}): wA_rel / gz(body z) {k1:.4f}, wA_rel / world-z rate {k2:.4f}; '
          f'rms(wA_rel - gz_int) {np.sqrt(np.mean((wA[m]-gzi[m])**2))*1e3:.1f} mrad/s, corr {np.corrcoef(wA[m], gzi[m])[0,1]:.4f}')
    # gz bias (still) and attitude tilt
    print(f'  gz mean in quiet windows: {np.mean(np.concatenate([gz[(ti>=a)&(ti<=b)] for a,b in Wq]))*1e3:+.2f} mrad/s')
# ---------- first-order low-pass (EMA at the frame rate) on the causal signals: noise in steady/still vs added lag
def ema(x, tau):
    y = np.full(n, np.nan); acc = None
    for i in range(n):
        if np.isnan(x[i]): continue
        dt_ = 0.1 if i == 0 else t[i] - t[i - 1]; al = dt_ / (tau + dt_)
        acc = x[i] if acc is None else acc + al * (x[i] - acc); y[i] = acc
    return y
stw = [steady[k] for k in ('fwd1', 'fwd2', 'rev1')] if tag == 'b1' else []
for tau in (0.0, 0.1, 0.2, 0.3, 0.5):
    line = f'  LPF tau {tau:.1f} s:'
    for k in ('A_rel', 'B'):
        y = ema(S[k], tau) if tau > 0 else S[k]
        lg = xc(y, S['A_cen'], 700)[0] / 1e3
        sdq, dq, _ = pooled(y, Wq)
        if stw: sds, ds, _ = pooled(y, stw, True); line += f' {k}: lag vs A_cen {lg*1e3:+.0f} ms, still sd {sdq*1e3:.2f}, steady detr sd {sds*1e3:.2f} dsd {ds*1e3:.2f} mm/s |'
        else: line += f' {k}: lag vs A_cen {lg*1e3:+.0f} ms, still sd {sdq*1e3:.2f} mm/s |'
    print(line)
np.savez(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', f'sig_{tag}.npz'), t=t, Arel=S['A_rel'], Acen=S['A_cen'], B=S['B'], wA=wA, gzi=gzi)
