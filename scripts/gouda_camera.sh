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
workspace="${GOUDA_WORKSPACE:-$default_workspace}"
[[ -f "$workspace/install/setup.bash" ]] || { echo 'First run: bash scripts/setup.sh'; exit 1; }
[[ -n "${GOUDA_IPHONE_STREAM_URL:-}" ]] || {
  echo 'Set GOUDA_IPHONE_STREAM_URL to the stream URL shown by the iPhone camera app.' >&2
  echo "Example: export GOUDA_IPHONE_STREAM_URL='rtsp://172.20.10.1:8554/live'" >&2
  exit 2
}
source /opt/ros/jazzy/setup.bash
source "$workspace/install/setup.bash"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-99}"
export ROS_AUTOMATIC_DISCOVERY_RANGE="${ROS_AUTOMATIC_DISCOVERY_RANGE:-LOCALHOST}"
exec ros2 launch gouda_camera iphone_stream.launch.py "$@"
