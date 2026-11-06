"""TEST ONLY: pure-Python loop, m1107 plant (DEC-445 test copy) + ND-11 MotionCore (FF+PI). No Nav2.
usage: python3 sweep.py <path to gouda_core> [quick]"""
import itertools, math, sys
from collections import deque
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, '.')
import drive_sim_core as ds
from gouda_core.motion_core import MotionCore, MotionSettings, Feedback, Feedforward, FeedforwardAxis

MAXV, MAXW, MAXR = 1.25, 0.97, 0.472
FF = Feedforward(FeedforwardAxis(0.185, 0.21, 0.09, MAXV), FeedforwardAxis(0.215, 0.24, 0.075, MAXR),
                 FeedforwardAxis(0.184, 0.195, 0.075, MAXW, 0.28, 0.19))
SET = MotionSettings(0.7, MAXV, MAXW, 0.5, MAXR)
DT, CTRL, ODOM = 0.02, 0.05, 0.1


def profile(name):
    if name.startswith('step'):
        v = float(name[4:]); return lambda t: (v if t >= 1 else 0.0, 0.0)
    if name.startswith('turn'):
        w = float(name[4:]); return lambda t: (0.4 if t >= 1 else 0.0, w if t >= 8 else 0.0)
    if name == 'ramp':   # MPPI-like: +0.06 m/s per 0.1 s from the measured speed would stay small; this is the open-loop ramp to 0.6
        return lambda t: (min(0.6, max(0.0, (t - 1) * 0.6)), 0.0)
    if name == 'slow':   # MPPI closed-loop from standstill (#61): about 0.04 m/s until it moves
        return lambda t: (0.04 if t >= 1 else 0.0, 0.0)
    raise ValueError(name)


def run(prof, gains, delay, layer=True, T=20.0):
    p = ds.Plant(m1107=True)
    core = MotionCore(SET, FF)
    if layer:
        core.set_feedback(Feedback(True, *gains))
    q = deque(); t = 0.0; nxt_c = 0.0; nxt_o = 0.0; f = s = 0.0
    out = []
    while t < T:
        tv, tw = prof(t)
        q.append((t, p.v, p.w))
        while q and q[0][0] < t - delay - 1: q.popleft()
        if t >= nxt_o:
            old = [x for x in q if x[0] <= t - delay]
            if old: core.on_odometry(old[-1][1], old[-1][2], t)
            nxt_o += ODOM
        if t >= nxt_c:
            core.on_motion_hold(False, 'sim', 3, t); core.on_cmd_vel(tv, tw, t)
            o = core.output(t); f, s = o.forward, o.turn
            nxt_c += CTRL
        if layer:
            cv, cw = f * (MAXV if f >= 0 else MAXR), s * MAXW
        else:
            cv, cw = tv, tw
        p.step(t, DT, cv, cw)
        out.append((t, tv, tw, p.v, p.w, f, s))
        t += DT
    return out


def metrics(out, axis='v'):
    k, tk = (3, 1) if axis == 'v' else (4, 2)
    start = next((r[0] for r in out if abs(r[k]) > (0.05 if axis == 'v' else 0.05)), None)
    t_on = next((r[0] for r in out if r[tk] != 0), None)
    t_start = None if start is None or t_on is None else start - t_on
    late = [r for r in out if r[0] >= out[-1][0] - 6]   # the last 6 s
    err = sum(abs(r[tk] - r[k]) for r in late) / len(late)
    sd = (sum((r[k] - sum(x[k] for x in late) / len(late)) ** 2 for r in late) / len(late)) ** 0.5
    toggles = 0; moving = None
    for r in out:
        if r[tk] == 0: continue
        m = abs(r[k]) > 0.03
        if moving is not None and m != moving: toggles += 1
        moving = m
    return t_start, err, sd, toggles


if __name__ == '__main__':
    quick = len(sys.argv) > 2
    profs_v = ['slow', 'step0.04', 'step0.12', 'step0.3', 'step0.6', 'ramp']
    print('# layer off')
    for d in (0.1,):
        for pr in profs_v + ['turn0.2', 'turn0.5']:
            o = run(profile(pr), None, d, layer=False)
            print('off', pr, 'v', [None if x is None else round(x, 3) for x in metrics(o, 'v')], 'w', [None if x is None else round(x, 3) for x in metrics(o, 'w')] if pr.startswith('turn') else '')
    res = []
    grid_v = list(itertools.product([0.2, 0.5, 1.0], [0.3, 1.0, 2.0], [0.15, 0.3]))
    grid_w = list(itertools.product([0.2, 0.5], [0.3, 1.0], [0.15, 0.3]))
    for (kpv, kiv, ilv) in grid_v:
        score = 0; rows = []
        for d in (0.1, 0.3):
            for pr in profs_v:
                ts, err, sd, tog = metrics(run(profile(pr), (kpv, kiv, ilv, 0.3, 0.5, 0.3, 0.5), d), 'v')
                rows.append((d, pr, ts, err, sd, tog))
        res.append(((kpv, kiv, ilv), rows))
    def summ(rows):
        ts = [r[2] if r[2] is not None else 99 for r in rows]
        return (max(ts), sum(r[3] for r in rows) / len(rows), max(r[4] for r in rows), sum(r[5] for r in rows))
    print('# forward grid: (kp, ki, i_limit) -> worst start s, mean |err| last 6 s, worst std last 6 s, total toggles')
    for g, rows in sorted(res, key=lambda x: (summ(x[1])[3] > 6, summ(x[1])[0] + 5 * summ(x[1])[1] + 5 * summ(x[1])[2])):
        print(g, [round(x, 3) for x in summ(rows)])
    best = sorted(res, key=lambda x: (summ(x[1])[3] > 6, summ(x[1])[0] + 5 * summ(x[1])[1] + 5 * summ(x[1])[2]))[0]
    print('# best forward', best[0])
    for r in best[1]:
        print('  d', r[0], r[1], 'start', None if r[2] is None else round(r[2], 2), 'err', round(r[3], 3), 'std', round(r[4], 3), 'toggles', r[5])
    kpv, kiv, ilv = best[0]
    print('# turn grid (forward fixed at best): (kp, ki, i_limit) -> worst start s, mean |err|, worst std, toggles')
    resw = []
    for (kpw, kiw, ilw) in grid_w:
        rows = []
        for d in (0.1, 0.3):
            for pr in ('turn0.2', 'turn0.5'):
                ts, err, sd, tog = metrics(run(profile(pr), (kpv, kiv, ilv, kpw, kiw, ilw, 0.5), d), 'w')
                rows.append((d, pr, ts, err, sd, tog))
        resw.append(((kpw, kiw, ilw), rows))
    for g, rows in sorted(resw, key=lambda x: (summ(x[1])[3] > 4, summ(x[1])[0] + 5 * summ(x[1])[1] + 5 * summ(x[1])[2])):
        print(g, [round(x, 3) for x in summ(rows)])
        for r in rows:
            print('   d', r[0], r[1], 'start', None if r[2] is None else round(r[2], 2), 'err', round(r[3], 3), 'std', round(r[4], 3), 'toggles', r[5])
