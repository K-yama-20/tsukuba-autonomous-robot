"""TEST ONLY: metrics of the FF+PI drive_sim runs. usage: python3 metrics.py <runs dir>"""
import csv, glob, json, os, statistics as st, sys


def one(d):
    r = json.load(open(os.path.join(d, 'result.json')))
    rows = [dict((k, float(v)) for k, v in x.items()) for x in csv.DictReader(open(os.path.join(d, 'trace.csv')))]
    t_cmd = next((x['t'] for x in rows if x['cmd_v'] > 0.001), None)
    t_mov = next((x['t'] for x in rows if x['v'] > 0.05), None)
    start = None if t_cmd is None or t_mov is None else t_mov - t_cmd
    mv = [x for x in rows if t_mov is not None and x['t'] > t_mov and abs(x['cmd_v']) > 0.001]
    ev = st.mean(abs(x['cmd_v'] - x['v']) for x in mv) if mv else None
    ew = st.mean(abs(x['cmd_w'] - x['w']) for x in mv) if mv else None
    tog = 0; m = None
    for x in rows:
        if x['cmd_v'] <= 0.001: m = None; continue
        now = abs(x['v']) > 0.03
        if m is not None and now != m: tog += 1
        m = now
    sds = []
    for i in range(0, len(rows) - 40, 20):
        w = rows[i:i + 40]
        cv = [x['cmd_v'] for x in w]
        if st.mean(cv) > 0.1 and st.pstdev(cv) < 0.02:
            sds.append(st.pstdev(x['v'] for x in w))
    ff = os.path.join(d, 'ffpi.csv'); modes = {}
    if os.path.exists(ff):
        for x in csv.DictReader(open(ff)):
            modes[x['mode']] = modes.get(x['mode'], 0) + 1
    return dict(run=os.path.basename(d), end=r.get('end'), completed=r.get('completed'), progress=r.get('progress'), contacts=r.get('contacts'),
                duration=r.get('duration_s'), avg=r.get('avg_speed_mps'), vmax=max(x['v'] for x in rows), lat=r.get('max_lateral_m'),
                minclr=r.get('min_clearance_m'), start=start, ev=ev, ew=ew, toggles=tog, sd_steady=st.mean(sds) if sds else None,
                spins=r.get('log', {}).get('spin'), load=r.get('load1'), modes=modes)


def f(v, n=2):
    return '—' if v is None else (f'{v:.{n}f}' if isinstance(v, float) else str(v))


if __name__ == '__main__':
    out = []
    for d in sorted(glob.glob(os.path.join(sys.argv[1], '*_*_*_d*_*'))):
        if not os.path.exists(os.path.join(d, 'result.json')): continue
        try: out.append(one(d))
        except Exception as e: print(d, 'ERR', e)
    print('| run | end | goal | progress | contact | s | avg m/s | max m/s | max lateral m | min clearance m | start s | mean abs(v err) | mean abs(w err) | stop-go toggles | steady v std | spins | load | modes |')
    print('|' + '---|' * 18)
    for m in out:
        print(f"| {m['run']} | {m['end']} | {m['completed']} | {f(m['progress'])} | {m['contacts']} | {f(m['duration'],0)} | {f(m['avg'])} | {f(m['vmax'])} | {f(m['lat'])} | {f(m['minclr'])} | {f(m['start'])} | {f(m['ev'],3)} | {f(m['ew'],3)} | {m['toggles']} | {f(m['sd_steady'],3)} | {m['spins']} | {f(m['load'],1)} | {m['modes'] or ''} |")
