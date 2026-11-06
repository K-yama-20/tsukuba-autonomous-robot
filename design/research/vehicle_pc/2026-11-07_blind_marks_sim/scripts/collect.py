"""TEST ONLY (issue #90 stage 2): one row per run from the run folders of blind_run.sh. No ROS.
usage: python3 collect.py <runs dir> <results.csv>
Columns from result.json (drive_sim.sh) plus, from costmap_marks.csv / obstacles.csv / trace.csv:
  first_mark_s / first_mark_gap_m: when the first lethal cell of each obstacle layer appeared, and how far the vehicle's centre was
  from the obstacle's centre then; lost_s: seconds with no lethal cell in the layer while the obstacle existed within 3 m, after
  the first mark; stale_cell_s: the sum over the samples (about 1 s apart) of the stale cells; stale_near_cell_s: the same within 2 m.
"""
import csv
import json
import math
import os
import sys

LAYERS = ('costmap', 'obstacle_layer', 'mid360_layer')
NEAR_OBSTACLE_M = 3.0


def nearest(rows, t):
    return min(rows, key=lambda r: abs(float(r['t']) - t))


def run_row(path):
    name = os.path.basename(path)
    variant, rest = name.split('_', 1)
    scenario, seed = rest.rsplit('_r', 1)
    row = {'run': name, 'variant': variant, 'scenario': scenario, 'seed': seed}
    rp = os.path.join(path, 'result.json')
    if not os.path.exists(rp):
        row['end'] = 'no_result'
        return row
    r = json.load(open(rp, encoding='utf-8'))
    for k in ('end', 'completed', 'progress', 'duration_s', 'avg_speed_mps', 'stopped_s', 'longest_stop_s', 'max_lateral_m', 'extra_path_ratio',
              'min_clearance_m', 'contacts', 'load1'):
        row[k] = r.get(k)
    for k, v in (r.get('log') or {}).items():
        row[k] = v
    mp, op, tp = (os.path.join(path, f) for f in ('costmap_marks.csv', 'obstacles.csv', 'trace.csv'))
    if not all(os.path.exists(p) for p in (mp, op, tp)):
        return row
    marks = list(csv.DictReader(open(mp, encoding='utf-8')))
    obstacles = [o for o in csv.DictReader(open(op, encoding='utf-8')) if o['name'] != 'block']
    trace = list(csv.DictReader(open(tp, encoding='utf-8')))
    for layer in LAYERS:
        rows = [m for m in marks if m['topic'].endswith('/' + layer)]
        row[f'{layer}_samples'] = len(rows)
        first = next((m for m in rows if int(m['lethal']) > 0), None)
        row[f'{layer}_max_stale'] = max((int(m['stale']) for m in rows), default=None)
        row[f'{layer}_max_stale_near'] = max((int(m['stale_near']) for m in rows), default=None)
        row[f'{layer}_last_stale'] = int(rows[-1]['stale']) if rows else None
        row[f'{layer}_stale_cell_s'] = sum(int(m['stale']) for m in rows)
        row[f'{layer}_stale_near_cell_s'] = sum(int(m['stale_near']) for m in rows)
        if first is None or not obstacles or not trace:
            row[f'{layer}_first_mark_s'] = row[f'{layer}_first_mark_gap_m'] = row[f'{layer}_lost_s'] = None
            continue
        t0 = float(first['t'])
        o, v = nearest(obstacles, t0), nearest(trace, t0)
        row[f'{layer}_first_mark_s'] = round(t0, 1)
        row[f'{layer}_first_mark_gap_m'] = round(math.hypot(float(o['x']) - float(v['x']), float(o['y']) - float(v['y'])), 2)
        lost = 0
        for m in rows:
            t = float(m['t'])
            if t <= t0 or int(m['lethal']) > 0:
                continue
            v = nearest(trace, t)
            near = [o for o in obstacles if abs(float(o['t']) - t) < 0.6 and o['exists'] == '1'
                    and math.hypot(float(o['x']) - float(v['x']), float(o['y']) - float(v['y'])) <= NEAR_OBSTACLE_M]
            lost += 1 if near else 0
        row[f'{layer}_lost_s'] = lost
    return row


def main(runs, out):
    rows = [run_row(os.path.join(runs, d)) for d in sorted(os.listdir(runs))
            if os.path.isdir(os.path.join(runs, d)) and d.split('_', 1)[0] in ('S0', 'S2')]
    keys = []
    for r in rows:
        keys += [k for k in r if k not in keys]
    with open(out, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader(); w.writerows(rows)
    print(len(rows), 'runs ->', out)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
