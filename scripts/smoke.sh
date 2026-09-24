#!/usr/bin/env bash
set -eo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p /tmp/gouda-smoke
# Simulate a Wayland desktop environment alongside the XWayland display used by CI.
export WAYLAND_DISPLAY=wayland-0
workspace=$HOME/gouda_ws
if test -n "$GOUDA_WORKSPACE"; then workspace=$GOUDA_WORKSPACE; fi
source /opt/ros/jazzy/setup.bash
source "$workspace/install/setup.bash"
bash "$repo/scripts/gouda.sh" view
trap 'bash "$repo/scripts/gouda.sh" stop' EXIT
python3 - <<'PY'
import json,pathlib
from gouda_gui.paths import runtime_dir
p=runtime_dir()/'processes.json'
pathlib.Path('/tmp/gouda-smoke/processes-before.json').write_bytes(p.read_bytes())
PY
node "$repo/tests/browser.cjs"
node "$repo/gouda_gui/test/browser_recording.cjs" http://127.0.0.1:8766
bash "$repo/scripts/gouda.sh" view
python3 - <<'PY'
import json,pathlib,socket
from gouda_gui.paths import runtime_dir
p=runtime_dir()/'processes.json'
assert json.loads(p.read_text())==json.loads(pathlib.Path('/tmp/gouda-smoke/processes-before.json').read_text()), 'Repeated start or browser reconnect restarted processes'
for port in (6080,5907):
    with socket.socket() as sock:
        sock.settimeout(.2)
        assert sock.connect_ex(('127.0.0.1',port)) != 0, f'legacy screen-transfer port {port} is listening'
pathlib.Path('/tmp/gouda-smoke/pre-viewer-restart.json').write_bytes(p.read_bytes())
PY
bash "$repo/scripts/gouda.sh" viewer
python3 - <<'PY'
import json,pathlib
from gouda_gui.paths import runtime_dir
before=json.loads(pathlib.Path('/tmp/gouda-smoke/pre-viewer-restart.json').read_text())['processes']
after=json.loads((runtime_dir()/'processes.json').read_text())['processes']
assert all(before[k]==after[k] for k in before if k!='viewer'), 'RViz restart changed another process'
assert before['viewer']['pid']!=after['viewer']['pid'], 'RViz restart did not replace the RViz child'
PY
python3 - <<'PY'
import json,pathlib
from gouda_gui.paths import runtime_dir
state=json.loads((runtime_dir()/'processes.json').read_text())
viewer=state['processes']['viewer']
with open(f'/proc/{viewer["pid"]}/cmdline','rb') as f:
    cmd=f.read().replace(b'\0',b' ').decode()
assert 'rviz2' in cmd.lower(), cmd
PY
xwininfo -root -tree | grep -i rviz
bash "$repo/scripts/gouda.sh" doctor > /tmp/gouda-smoke/doctor.json
