"""TEST COPY ONLY (round 3): add the static cones C01-C06 of the 30 patterns (第183便, repository SIM30) to a copy of drive_sim_core.py.
Same geometry as SIM30: route 25 m straight (waypoints every 5 m), cone r 0.15 h 0.7 present from the start, timeout 120 s."""
import sys
p = sys.argv[1]; s = open(p).read()
if "name == 'C01'" in s:
    print('already'); sys.exit(0)
a = "    if name == 'P22':"
assert s.count(a) == 1
cones = {'C01': (12, 0.0), 'C02': (12, 0.3), 'C03': (12, -0.3), 'C04': (12, 0.6), 'C05': (12, 1.0), 'C06': (15, 0.0)}
add = "    _SIM30_CONES = {" + ", ".join(f"'{k}': ({x}, {y})" for k, (x, y) in cones.items()) + "}   # TEST COPY (round 3): SIM30 C01-C06\n"
add += "    if name in _SIM30_CONES:\n        cx, cy = _SIM30_CONES[name]\n        return Scenario(name, _route(length=25.0, side=0.0), [Obstacle(cx, cy, name='cone', **CONE)], timeout_s=120.0)\n"
s = s.replace(a, add + a)
open(p, 'w').write(s); print('patched')
