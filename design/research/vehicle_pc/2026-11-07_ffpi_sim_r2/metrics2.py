"""TEST ONLY: metrics of round 2 (<layer>_<scene>_vx<v>_<model>_<rep>). usage: python3 metrics2.py <runs dir>
Prints per-run rows, then one row per condition x scene (runs aggregated). A run whose Nav2 never sent a command (commands 0) is marked
invalid and left out of the aggregate."""
import csv, glob, json, os, re, statistics as st, sys
from collections import OrderedDict


def one(d):
    r = json.load(open(os.path.join(d, 'result.json')))
    rows = [dict((k, float(v)) for k, v in x.items()) for x in csv.DictReader(open(os.path.join(d, 'trace.csv')))]
    t_cmd = next((x['t'] for x in rows if x['cmd_v'] > 0.001), None)
    t_mov = next((x['t'] for x in rows if x['v'] > 0.05), None)
    tog = 0; m = None
    for x in rows:
        if x['cmd_v'] <= 0.001: m = None; continue
        now = abs(x['v']) > 0.03
        if m is not None and now != m: tog += 1
        m = now
    mv = [x for x in rows if x['v'] > 0.15]
    lg = r.get('log', {})
    return dict(run=os.path.basename(d), end=r.get('end'), goal=bool(r.get('completed')), progress=r.get('progress'), contacts=r.get('contacts') or 0,
                minclr=r.get('min_clearance_m'), duration=r.get('duration_s'), avg=r.get('avg_speed_mps'), vmax=max((x['v'] for x in rows), default=0.0),
                lat=r.get('max_lateral_m'), start=None if t_cmd is None or t_mov is None else t_mov - t_cmd,
                wstd=st.pstdev(x['w'] for x in mv) if len(mv) > 20 else None, toggles=tog,
                recov=(lg.get('spin', 0) + lg.get('backup', 0) + lg.get('wait', 0)), failed=lg.get('failed_progress', 0), cahead=lg.get('collision_ahead', 0),
                stopped=r.get('stopped_s'), load=r.get('load1'), commands=r.get('commands', 0))


def f(v, n=2):
    return '—' if v is None else (f'{v:.{n}f}' if isinstance(v, float) else str(v))


if __name__ == '__main__':
    runs = []
    for d in sorted(glob.glob(os.path.join(sys.argv[1], '*_vx*_*_[0-9]'))):
        if os.path.isdir(d) and os.path.exists(os.path.join(d, 'result.json')):
            try: runs.append(one(d))
            except Exception as e: print(d, 'ERR', e)
    print('## per run\n')
    print('| run | end | goal | progress | contact | min clearance m | time s | avg m/s | max m/s | max lateral m | start s | turn-rate std moving | stop-go | BT recoveries (spin+backup+wait) | failed progress | collision ahead | stopped s | load | commands |')
    print('|' + '---|' * 19)
    for m in runs:
        print(f"| {m['run']} | {m['end']} | {m['goal']} | {f(m['progress'])} | {m['contacts']} | {f(m['minclr'])} | {f(m['duration'],0)} | {f(m['avg'])} | {f(m['vmax'])} | {f(m['lat'])} | {f(m['start'])} | {f(m['wstd'],3)} | {m['toggles']} | {m['recov']} | {m['failed']} | {m['cahead']} | {f(m['stopped'],1)} | {f(m['load'],1)} | {m['commands']} |")
    groups = OrderedDict()
    for m in runs:
        key = re.sub(r'_[0-9]$', '', m['run'])
        groups.setdefault(key, []).append(m)
    print('\n## per condition x scene (valid runs only)\n')
    print('| condition_scene | valid runs | goal | contact runs | min clearance m (worst) | time to goal s (mean of goals) | avg m/s (mean) | max m/s | max lateral m (worst) | turn-rate std moving (mean) | stop-go (mean) | BT recoveries (sum) | failed progress (sum) | invalid |')
    print('|' + '---|' * 14)
    for k, ms in groups.items():
        ok = [m for m in ms if m['commands'] > 0]
        bad = len(ms) - len(ok)
        if not ok:
            print(f'| {k} | 0 | — | — | — | — | — | — | — | — | — | — | — | {bad} |'); continue
        g = [m for m in ok if m['goal']]
        clr = [m['minclr'] for m in ok if m['minclr'] is not None]
        ws = [m['wstd'] for m in ok if m['wstd'] is not None]
        print(f"| {k} | {len(ok)} | {len(g)}/{len(ok)} | {sum(1 for m in ok if m['contacts'])}/{len(ok)} | {f(min(clr)) if clr else '—'} | {f(st.mean(m['duration'] for m in g),0) if g else '—'} | "
              f"{f(st.mean(m['avg'] for m in ok))} | {f(max(m['vmax'] for m in ok))} | {f(max(m['lat'] for m in ok))} | {f(st.mean(ws),3) if ws else '—'} | "
              f"{f(st.mean(m['toggles'] for m in ok),1)} | {sum(m['recov'] for m in ok)} | {sum(m['failed'] for m in ok)} | {bad} |")
