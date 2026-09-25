#!/usr/bin/env bash
set -eo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
default_workspace="$(python3 - "$repo" <<'PYWORKSPACE'
import sys
from pathlib import Path
repo=Path(sys.argv[1]).resolve()
print(repo.parent.parent if repo.name == 'tsukuba-autonomous-robot' and repo.parent.name == 'src' else Path.home()/'gouda_ws')
PYWORKSPACE
)"
workspace="${GOUDA_WORKSPACE:-$(python3 - "$default_workspace" <<'PYCONFIG'
import json, os, sys
from pathlib import Path
workspace=Path(sys.argv[1])
current=workspace/'bags/gouda/host.json'
legacy=Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))/'gouda/host.json'
config=current if current.exists() else legacy
print(json.loads(config.read_text())['workspace'] if config.exists() else workspace)
PYCONFIG
)}"
export GOUDA_WORKSPACE="$workspace"
if [[ "${1:-}" == configure ]]; then
  source /opt/ros/jazzy/setup.bash
  source "$workspace/install/setup.bash"
  exec python3 "$repo/scripts/configure_host.py" --workspace "$workspace"
fi
[[ -f "$workspace/install/setup.bash" ]] || { echo 'First run: bash scripts/setup.sh'; exit 1; }
source /opt/ros/jazzy/setup.bash
source "$workspace/install/setup.bash"
if [[ "${1:-}" == signal ]]; then
  shift
  export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-99}"
  export ROS_AUTOMATIC_DISCOVERY_RANGE="${ROS_AUTOMATIC_DISCOVERY_RANGE:-LOCALHOST}"
  exec python3 -m gouda_signal.app "$@"
fi
exec python3 -m gouda_gui.runtime "$@"
