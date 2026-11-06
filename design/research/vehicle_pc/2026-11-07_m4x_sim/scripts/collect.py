"""Collect result.json of run4x.sh output dirs into a table (TEST ONLY)."""
import glob, json, os, sys, collections
rows = []
for root in sys.argv[1:]:
    for f in glob.glob(os.path.join(root, '**', 'result.json'), recursive=True):
        r = json.load(open(f)); name = os.path.basename(os.path.dirname(f))
        m, rest = name.split('_', 1); sc, rep = rest.rsplit('_', 1)
        rows.append(dict(set=os.path.relpath(os.path.dirname(os.path.dirname(f)), os.path.dirname(root.rstrip('/'))), method=m, scene=sc, rep=rep,
                         end=r.get('end'), done=r.get('completed'), prog=r.get('progress'), dur=r.get('duration_s'), v=r.get('avg_speed_mps'),
                         vmax=r.get('max_speed_mps'), stop=r.get('stopped_s'), lstop=r.get('longest_stop_s'), contacts=r.get('contacts'),
                         gap=r.get('min_gap_m'), lat=r.get('max_lateral_m'), first=r.get('first_cmd_s'), log=r.get('log', {})))
json.dump(rows, open(os.environ.get('OUT', '/dev/stdout') if os.environ.get('OUT') else sys.stdout.fileno(), 'w'), ensure_ascii=False, indent=0) if os.environ.get('JSON') else None
g = collections.defaultdict(list)
for r in rows: g[(r['set'], r['method'], r['scene'])].append(r)
for k in sorted(g):
    rs = g[k]; ok = sum(1 for r in rs if r['done'])
    f = lambda key: ','.join('-' if r[key] is None else (f"{r[key]:.2f}" if isinstance(r[key], float) else str(r[key])) for r in rs)
    print(f"{k[0]:<10} {k[1]:<6} {k[2]:<18} goal {ok}/{len(rs)} end={','.join(str(r['end']) for r in rs)} v={f('v')} stop={f('stop')} contact={f('contacts')} lat={f('lat')} gap={f('gap')} first={f('first')} miss={','.join(str(r['log'].get('control_loop_missed')) for r in rs)}")
