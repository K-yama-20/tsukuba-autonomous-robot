#!/usr/bin/env bash
set -euo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export GOUDA_BUILD_WORKSPACE="${GOUDA_BUILD_WORKSPACE:-${GOUDA_WORKSPACE:-$HOME/gouda_ws}}"
python3 - "$repo" <<'PY'
import json,os,signal,subprocess,sys
from pathlib import Path
repo=Path(sys.argv[1]);out=Path('/tmp/gouda-gazebo-acceptance');out.mkdir(exist_ok=True)
server=subprocess.Popen(['bash',str(repo/'scripts/gazebo.sh'),'run'],stdout=(out/'server.log').open('w'),stderr=subprocess.STDOUT,start_new_session=True)
try:
 result=subprocess.run(['bash',str(repo/'scripts/gazebo.sh'),'scenarios','-p','report:='+str(out/'report.json')],stdout=(out/'scenarios.log').open('w'),stderr=subprocess.STDOUT,timeout=240)
 print((out/'scenarios.log').read_text())
 result.check_returncode()
 report=json.loads((out/'report.json').read_text())
 assert report['passed'] and len(report['results'])==10
 print('Gazebo 10-case acceptance PASS')
finally:
 if server.poll() is None:os.killpg(server.pid,signal.SIGINT)
 try:server.wait(timeout=25)
 except subprocess.TimeoutExpired:
  os.killpg(server.pid,signal.SIGTERM);server.wait(timeout=10)
PY
