"""TEST COPY ONLY: let GOUDA_TEST_NAV2 set any Nav2 parameter: {"params": {"<section path>": {"key": value}}}, the section path being
the dotted path of the generated nav2_params dict (e.g. "controller_server" or "local_costmap.local_costmap"). For running Nav2 faster
than real time: controller_server runs on a wall-clock rate (#67), so the test raises its frequency by the speed factor."""
import sys
p = sys.argv[1]
s = open(p).read()
old = "    f.update(t.get('follow', {}))\n"
new = old + """    for path, kv in (t.get('params') or {}).items():   # TEST COPY: any section, dotted path
        sec = p
        for k in path.split('.'): sec = sec[k]
        (sec['ros__parameters'] if 'ros__parameters' in sec else sec).update(kv)
"""
assert s.count(old) == 1
open(p, 'w').write(s.replace(old, new))
print('patched')
