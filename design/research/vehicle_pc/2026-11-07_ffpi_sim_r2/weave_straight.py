"""TEST ONLY: weaving on the straight part (2 < x < 26 m, |y| < 3 m, v > 0.15) of drive_sim traces. usage: weave_straight.py <dir>..."""
import csv, glob, os, statistics as st, sys
print('| run | straight s | w std | cmd_w std | w sign flips per min | max abs(w) |')
print('|---|---|---|---|---|---|')
for pat in sys.argv[1:]:
    for d in sorted(glob.glob(pat)):
        p = d + '/trace.csv'
        if not os.path.exists(p): continue
        rows = [dict((k, float(v)) for k, v in r.items()) for r in csv.DictReader(open(p))]
        s = [r for r in rows if r['v'] > 0.15 and 2 < r['x'] < 26 and abs(r['y']) < 3]
        if len(s) < 40: continue
        flips = sum(1 for a, b in zip(s, s[1:]) if (a['w'] > 0.05 and b['w'] < -0.05) or (a['w'] < -0.05 and b['w'] > 0.05))
        dur = len(s) / 20
        print(f"| {os.path.basename(d)} | {dur:.1f} | {st.pstdev(r['w'] for r in s):.3f} | {st.pstdev(r['cmd_w'] for r in s):.3f} | {flips / dur * 60:.1f} | {max(abs(r['w']) for r in s):.2f} |")
