#!/usr/bin/env bash
set -eo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p /tmp/gouda-smoke
bash "$repo/scripts/gouda.sh" view
trap 'bash "$repo/scripts/gouda.sh" stop' EXIT
python3 - <<'PY'
import json,os,pathlib
p=pathlib.Path(os.environ.get('XDG_DATA_HOME',str(pathlib.Path.home()/'.local/share')))/'gouda/runtime/processes.json'
pathlib.Path('/tmp/gouda-smoke/processes-before.json').write_bytes(p.read_bytes())
PY
node "$repo/tests/browser.cjs"
bash "$repo/scripts/gouda.sh" view
python3 - <<'PY'
import json,os,pathlib
p=pathlib.Path(os.environ.get('XDG_DATA_HOME',str(pathlib.Path.home()/'.local/share')))/'gouda/runtime/processes.json'
assert json.loads(p.read_text())==json.loads(pathlib.Path('/tmp/gouda-smoke/processes-before.json').read_text()), 'Repeated start or browser reconnect restarted processes'
PY
bash "$repo/scripts/gouda.sh" doctor > /tmp/gouda-smoke/doctor.json
