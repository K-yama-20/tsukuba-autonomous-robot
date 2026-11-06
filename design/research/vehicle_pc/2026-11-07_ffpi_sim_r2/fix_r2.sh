#!/bin/bash
cd ~/ffpi_runs
mkdir -p r2_speedmask1.25
for d in r2/onv_free_vx0.4_A_1 r2/onv_P22_vx0.4_A_1; do [ -d $d ] && mv $d r2_speedmask1.25/; done
[ -d r2 ] && mv r2 r2_aborted_$(date +%H%M)
F=$HOME/gouda_ws_ffpi/src/tsukuba-autonomous-robot/gouda_core/test/drive_sim_fixture.py
python3 - "$F" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
a = "[sc.limit_mps] * (len(sc.route) - 2)"
if 'SIM_LIMIT_MPS' not in s:
    assert s.count(a) == 1
    s = s.replace(a, "[float(__import__('os').environ.get('SIM_LIMIT_MPS') or sc.limit_mps)] * (len(sc.route) - 2)")
    open(p, 'w').write(s)
print('fixture ok')
PY
python3 - <<'PY'
p = 'run3.sh'; s = open(p).read()
if 'SIM_LIMIT_MPS' not in s:
    s = s.replace('  echo "{\\"mppi_vx_max_mps\\": $vx}" > $out.values.json', '  export SIM_LIMIT_MPS=$vx   # the section speed limit of the speed mask = vx_max (else MPPI rescales vx_max, vx_min, wz)\n  echo "{\\"mppi_vx_max_mps\\": $vx}" > $out.values.json')
    assert 'SIM_LIMIT_MPS' in s
    open(p, 'w').write(s)
print('run3 ok')
PY
grep -n SIM_LIMIT run3.sh
