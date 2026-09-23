#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
import os
import hashlib
import json
root=Path(os.environ.get('GOUDA_WORKSPACE',Path.home()/'gouda_ws'))
p=root/'src/ADI_IMU_TR_Driver_ROS2/lib/src/adis_rcv_bin.cpp'
old='  struct termios config;\n  cfmakeraw(&config);\n'
new='  struct termios config = defaults_;\n  cfmakeraw(&config);\n  config.c_cflag |= CLOCAL | CREAD;\n'
s=p.read_text()
if new in s:
    print('IMU termios fix already applied')
elif s.count(old)==1:
    audit=root/'patch_backups/imu';audit.mkdir(parents=True,exist_ok=True)
    backup=audit/'adis_rcv_bin.before_termios_fix.cpp'
    if backup.exists() and backup.read_text()!=s:
        raise RuntimeError('Original backup differs; refusing to overwrite')
    backup.write_text(s)
    result=s.replace(old,new)
    p.write_text(result)
    (audit/'imu_patch_hashes.json').write_text(json.dumps(dict(
        original=hashlib.sha256(s.encode()).hexdigest(),
        fixed=hashlib.sha256(result.encode()).hexdigest()),indent=2))
    print('Initialized termios; original source saved:',backup)
else:
    raise RuntimeError('Unexpected IMU source; refusing to change it')
PY
