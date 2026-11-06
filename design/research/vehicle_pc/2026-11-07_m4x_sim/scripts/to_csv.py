"""TEST ONLY (第214便): the metrics of run4x.sh output folders (result.json) as one CSV row per run. Poses and logs are left out.
usage: python3 to_csv.py <host label> <set label> <folder> >> results.csv"""
import csv, glob, json, os, sys
host, label, root = sys.argv[1:4]
keys = ('end', 'completed', 'progress', 'duration_s', 'avg_speed_mps', 'stopped_s', 'longest_stop_s', 'max_lateral_m', 'extra_path_ratio',
        'min_clearance_m', 'contacts', 'turn_changes_per_min', 'w_cmd_rate_rms', 'commands', 'load1')
logk = ('collision_ahead', 'failed_progress', 'patience_exceeded', 'spin', 'backup', 'wait', 'control_loop_missed', 'planner_loop_missed', 'tf_errors')
w = csv.writer(sys.stdout)
if os.environ.get('HEADER'): w.writerow(('host', 'set', 'method', 'scene', 'rep') + keys + logk)
for f in sorted(glob.glob(os.path.join(root, '*', 'result.json'))):
    r = json.load(open(f)); m, rest = os.path.basename(os.path.dirname(f)).split('_', 1); sc, rep = rest.rsplit('_', 1)
    w.writerow((host, label, m, sc, rep) + tuple(r.get(k) for k in keys) + tuple((r.get('log') or {}).get(k) for k in logk))
