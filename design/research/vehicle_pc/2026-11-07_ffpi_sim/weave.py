import sys, math; sys.path.insert(0, '.')
from sweep import run
# MPPI-like small corrections while driving: w = 0.08 sin(2 pi t / 4) on top of v 0.6
prof = lambda t: (0.6 if t >= 1 else 0.0, 0.08 * math.sin(2 * math.pi * t / 4) if t >= 5 else 0.0)
for name, g in [('turn PI 0.5/1.0/0.15', (0.3, 0.5, 0.15, 0.5, 1.0, 0.15, 0.5)), ('turn PI 0.2/0.3/0.15', (0.3, 0.5, 0.15, 0.2, 0.3, 0.15, 0.5)), ('turn FF only', (0.3, 0.5, 0.15, 0.0, 0.0, 0.0, 0.5))]:
    for d in (0.1, 0.3):
        o = run(prof, g, d, T=30)
        late = [r for r in o if r[0] > 10]
        print(name, 'd', d, 'max|w| %.3f' % max(abs(r[4]) for r in late), 'mean|w-wt| %.3f' % (sum(abs(r[4]-r[2]) for r in late)/len(late)), 'max|turn stick| %.3f' % max(abs(r[6]) for r in late))
o = run(prof, None, 0.1, layer=False, T=30); late = [r for r in o if r[0] > 10]
print('off', 'max|w| %.3f' % max(abs(r[4]) for r in late), 'mean|w-wt| %.3f' % (sum(abs(r[4]-r[2]) for r in late)/len(late)))
