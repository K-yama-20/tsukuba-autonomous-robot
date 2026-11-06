import sys; sys.path.insert(0, ".")
sys.argv = [sys.argv[0], sys.argv[1]]
from sweep import run, profile, metrics
import itertools
for g in itertools.product([0.3, 0.5], [0.5, 1.0], [0.15, 0.3]):
    line = []
    for d in (0.1, 0.3):
        for pr in ('step0.04', 'step0.12', 'step0.3', 'step0.6', 'step0.8', 'ramp'):
            o = run(profile(pr), g + (0.5, 1.0, 0.3, 0.5), d)
            tgt = profile(pr)(19)[0]
            ov = max(r[3] for r in o) - tgt
            ts, err, sd, tog = metrics(o, 'v')
            line.append(f'{pr}@{d}:st{ts if ts is None else round(ts,2)} ov{ov:+.2f} e{err:.3f} tg{tog}')
    print(g, ' '.join(line))
print('off', ' '.join(f"{pr}:ov{max(r[3] for r in run(profile(pr), None, 0.1, layer=False)) - profile(pr)(19)[0]:+.2f}" for pr in ('step0.3','step0.6','step0.8')))
