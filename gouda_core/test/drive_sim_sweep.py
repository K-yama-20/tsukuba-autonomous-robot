"""TEST ONLY (第179便): run named sets of /config 「Nav2」 values over the scenarios with drive_sim.sh and rank them by the mean score.
usage: python3 drive_sim_sweep.py <sets.json> <out_dir> [--scenarios a,b,c] [--repeat N]
sets.json: {"label": {"key": value, ..., "_sim_args": "--delay 0.3"}}. The score only ranks: see drive_sim_core.Scorer."""
import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import drive_sim_core as ds  # noqa: E402
RETRIES = 3
COLUMNS = ('completed', 'progress', 'duration_s', 'avg_speed_mps', 'stopped_s', 'longest_stop_s', 'contacts', 'min_clearance_m', 'max_lateral_m',
           'turn_changes_per_min', 'w_cmd_rate_rms', 'score')


def summary(rows: list) -> list:
    """[(label, mean score, runs, completed runs)] best first; a run without a score counts as 0."""
    by = {}
    for r in rows:
        by.setdefault(r['set'], []).append(r)
    out = [(k, round(statistics.mean(x.get('score') or 0 for x in v), 1), len(v), sum(1 for x in v if x.get('completed'))) for k, v in by.items()]
    return sorted(out, key=lambda s: -s[1])


def markdown(rows: list) -> str:
    lines = ['| set | mean score | runs | completed |', '|---|---|---|---|'] + [f'| {a} | {b} | {c} | {d} |' for a, b, c, d in summary(rows)]
    lines += ['', '| set | scenario | end | ' + ' | '.join(COLUMNS) + ' |', '|---|---|---|' + '---|' * len(COLUMNS)]
    lines += ['| ' + ' | '.join(str(x) for x in [r['set'], r.get('scenario'), r.get('end')] + [r.get(c) for c in COLUMNS]) + ' |' for r in rows]
    return '\n'.join(lines) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('sets'); ap.add_argument('out')
    ap.add_argument('--scenarios', default=','.join(ds.SCENARIOS)); ap.add_argument('--repeat', type=int, default=1)
    a = ap.parse_args()
    sets = json.load(open(a.sets, encoding='utf-8'))
    rows = []
    for label, values in sets.items():
        values = dict(values); sim_args = values.pop('_sim_args', '')
        for sc in a.scenarios.split(','):
            for rep in range(a.repeat):
                out = os.path.join(a.out, label, f'{sc}_{rep}')
                os.makedirs(out, exist_ok=True)
                with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
                    json.dump(values, f)
                path = os.path.join(out, 'result.json')
                for _ in range(RETRIES):      # a run that never got a command is the harness's failure (discovery), not a result of the settings
                    subprocess.run(['bash', os.path.join(HERE, 'drive_sim.sh'), sc, out, f.name], env=dict(os.environ, SIM_ARGS=sim_args), timeout=400, check=False)
                    r = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {'scenario': sc, 'end': 'no result'}
                    if r.get('commands'):
                        break
                os.unlink(f.name)
                rows.append(dict(r, set=label))
                with open(os.path.join(a.out, 'summary.md'), 'w', encoding='utf-8') as f:
                    f.write(markdown(rows))
    print(markdown(rows))


if __name__ == '__main__':
    main()
