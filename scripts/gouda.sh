#!/usr/bin/env bash
set -eo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
workspace="${GOUDA_WORKSPACE:-$(python3 -c 'import json,os,pathlib; p=pathlib.Path(os.environ.get("XDG_CONFIG_HOME",str(pathlib.Path.home()/".config")))/"gouda/host.json"; print(json.loads(p.read_text())["workspace"] if p.exists() else str(pathlib.Path.home()/"gouda_ws"))')}"
export GOUDA_WORKSPACE="$workspace"
if [[ "${1:-}" == configure ]]; then
  source /opt/ros/jazzy/setup.bash
  source "$workspace/install/setup.bash"
  exec python3 "$repo/scripts/configure_host.py" --workspace "$workspace"
fi
[[ -f "$workspace/install/setup.bash" ]] || { echo 'First run: bash scripts/setup.sh'; exit 1; }
source /opt/ros/jazzy/setup.bash
source "$workspace/install/setup.bash"
exec python3 -m gouda_gui.runtime "$@"
