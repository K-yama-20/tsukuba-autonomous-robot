"""TEST COPY ONLY: add the scene P22 of the 30 patterns (第183便): a person steps out 3 m ahead on a straight 25 m route and stands 8 s.
Same geometry as the repository's SIM30['P22'] (Obstacle(12, 0, trigger 3.0 m, dwell 8 s, person r 0.25 h 1.7), route 25 m straight, timeout 120 s)."""
import sys
p = sys.argv[1]; s = open(p).read()
a = "    r = _route()\n    if name == 'free':"
assert s.count(a) == 1
s = s.replace(a, "    if name == 'P22':   # TEST COPY (round 2): SIM30 P22\n        return Scenario(name, _route(length=25.0, side=0.0), [Obstacle(12, 0.0, trigger_m=3.0, dwell_s=8.0, name='person', **PERSON)], timeout_s=120.0)\n" + a)
open(p, 'w').write(s); print('patched')
