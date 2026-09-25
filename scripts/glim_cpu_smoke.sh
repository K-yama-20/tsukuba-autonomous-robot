#!/usr/bin/env bash
# Software-only GLIM CPU smoke. The temporary upstream sample transform is not
# Gouda calibration; no sensor topics are published and no map may be accepted.
set -eo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
workspace="${GOUDA_WORKSPACE:-$HOME/gouda_ws}"
[[ -f /opt/ros/jazzy/setup.bash ]] || { echo 'ROS 2 Jazzy is required' >&2; exit 2; }
[[ -f "$workspace/install/setup.bash" ]] || { echo 'Build the Gouda workspace first' >&2; exit 2; }
source /opt/ros/jazzy/setup.bash
source "$workspace/install/setup.bash"
ros2 pkg prefix glim >/dev/null
ros2 pkg prefix glim_ros >/dev/null
ros2 pkg prefix gouda_navigation >/dev/null
# Domain 97 is reserved for this isolated smoke; it never opens the observation HTTP ports.
export ROS_DOMAIN_ID=97
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export PYTHONPATH="$repo/gouda_navigation:$repo/gouda_gui${PYTHONPATH:+:$PYTHONPATH}"
smoke_root="$(mktemp -d "${TMPDIR:-/tmp}/gouda-glim-smoke.XXXXXX")"
export GLIM_SMOKE_ROOT="$smoke_root"
if /usr/bin/python3 - <<'PY'
import os
import json
from pathlib import Path
import time
import rclpy
from rclpy.node import Node
from gouda_navigation.mapping import DEFAULT_SETTINGS, GlimSession

root = Path(os.environ['GLIM_SMOKE_ROOT'])
os.environ['GOUDA_WORKSPACE'] = str(root)
config = root/'bags/gouda'
config.mkdir(parents=True)
(config/'hesai.yaml').write_text(json.dumps({'lidar':[{'driver':{'source_type':1,'use_timestamp_type':0}}]}))
(config/'host.json').write_text(json.dumps({'hesai_config':str(config/'hesai.yaml')}))
# Test-only upstream Ouster example transform. It is never saved to workspace settings,
# and there are no LiDAR/IMU publishers in domain 97.
settings = {
    **DEFAULT_SETTINGS,
    'backend': 'glim_imu', 'compute': 'cpu',
    'clock_policy': 'host_mapped', 'clock_evidence': 'No-input synthetic fixture; no hardware clock claim',
    'extrinsic_lidar_imu': {
        'translation_m': [0.006, -0.012, 0.008],
        'quaternion_xyzw': [0.0, 0.0, 0.0, 1.0],
    },
    'point_time_field': 'timestamp', 'point_time_datatype': 'float64',
    'point_time_mode': 'relative', 'point_time_unit': 'seconds',
    'imu_accel_unit': 'm/s^2', 'imu_gyro_unit': 'rad/s',
    'imu_clock_offset_sec': 0.0, 'lidar_clock_offset_sec': 0.0,
}
rclpy.init()
node = Node('glim_cpu_no_input_smoke')
session = GlimSession(node, root / 'output')
try:
    session.start(settings, root / 'output')
    deadline = time.monotonic() + 20.0
    required = ('load libodometry_estimation_cpu.so', 'load libglobal_mapping.so', 'load librviz_viewer.so')
    while time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.1)
        if session.log_path and session.log_path.exists():
            log = session.log_path.read_text(errors='replace')
            if all(token in log for token in required):
                break
        if session.status() == 'failed':
            raise RuntimeError('GLIM launch exited before all CPU modules loaded')
        time.sleep(0.1)
    else:
        raise TimeoutError('GLIM CPU modules did not load; inspect the unique GLIM log')
    if session.status() != 'preflight_error':
        raise AssertionError(f'no-input GLIM state was {session.status()}, expected preflight_error (missing clock evidence)')
    print('Loaded CPU odometry, global mapping, and RViz modules; no sensor messages were received.')
    print(f'GLIM log: {session.log_path}')
    try:
        session.close(timeout=45.0)
    except RuntimeError:
        # No input frames must not be accepted as a saved map.
        if session.status() != 'failed':
            raise
    if session.status() != 'failed':
        raise AssertionError('empty no-input GLIM session was incorrectly marked saved')
    process = session.process
    if process is None or process.poll() is None:
        raise AssertionError('GLIM launch supervisor did not exit')
    try:
        os.killpg(process.pid, 0)
    except ProcessLookupError:
        pass
    else:
        raise AssertionError('GLIM launch process group still has a process after graceful close')
    graph = root / 'output' / 'graph.txt'
    if graph.is_file() and ('num_submaps: 0' not in graph.read_text() or 'num_all_frames: 0' not in graph.read_text()):
        raise AssertionError('no-input smoke unexpectedly produced a populated map')
    print('Graceful close left no GLIM process; empty session was not accepted as a map.')
finally:
    if session.process and session.process.poll() is None:
        session.close(timeout=45.0)
    node.destroy_node()
    rclpy.shutdown()
PY
then
  rm -rf "$smoke_root"
else
  echo "Smoke failed; temporary output retained at $smoke_root" >&2
  exit 1
fi
