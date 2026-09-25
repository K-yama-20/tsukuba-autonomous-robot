import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).parents[1]


def test_signal_dependencies_are_in_existing_system_setup():
    setup = (ROOT / 'scripts/setup.sh').read_text()
    system_install = setup.split('if (( with_glim )); then', 1)[0]

    assert 'python3-opencv' in system_install
    assert 'python3-pyqt5' in system_install
    assert 'python3-numpy' in system_install
    assert 'pip install' not in system_install


def test_signal_package_is_in_the_default_colcon_and_rosdep_package_set():
    setup = (ROOT / 'scripts/setup.sh').read_text()
    package_setup = setup.split('if (( with_gazebo )); then packages+=', 1)[0]

    assert '"$repo"/gouda_signal' in package_setup
    assert 'rosdep install --from-paths "${packages[@]}"' in setup
    assert 'colcon build --symlink-install --base-paths "${packages[@]}"' in setup


@pytest.mark.parametrize(
    ('overrides', 'expected_domain', 'expected_discovery'),
    [
        ({}, '99', 'LOCALHOST'),
        ({'ROS_DOMAIN_ID': '42', 'ROS_AUTOMATIC_DISCOVERY_RANGE': 'SUBNET'}, '42', 'SUBNET'),
    ],
)
def test_signal_launcher_executes_app_with_arguments_and_ros_environment(
    tmp_path, overrides, expected_domain, expected_discovery
):
    ros_setup = Path('/opt/ros/jazzy/setup.bash')
    if not ros_setup.is_file():
        pytest.skip('ROS 2 Jazzy is not installed at /opt/ros/jazzy')

    real_python = shutil.which('python3')
    assert real_python is not None
    workspace = tmp_path / 'workspace with spaces'
    install = workspace / 'install'
    install.mkdir(parents=True)
    (install / 'setup.bash').write_text('# empty test overlay\n')
    stub_dir = tmp_path / 'bin'
    stub_dir.mkdir()
    stub = stub_dir / 'python3'
    stub.write_text(
        '''#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "-" ]]; then
  exec "$REAL_PYTHON3" "$@"
fi
if [[ "${1:-}" == "-m" && "${2:-}" == "gouda_signal.app" ]]; then
  shift 2
  exec "$REAL_PYTHON3" - "$@" <<'PYTHON'
import json
import os
import sys
print(json.dumps({
    "argv": sys.argv[1:],
    "ros_domain_id": os.environ.get("ROS_DOMAIN_ID"),
    "discovery_range": os.environ.get("ROS_AUTOMATIC_DISCOVERY_RANGE"),
}))
PYTHON
fi
printf 'Unexpected Python runtime invocation: %s\\n' "$*" >&2
exit 91
''',
        encoding='utf-8',
    )
    stub.chmod(0o755)

    camera = tmp_path / 'front camera sample.mp4'
    env = os.environ.copy()
    env['PATH'] = str(stub_dir) + os.pathsep + env['PATH']
    env['REAL_PYTHON3'] = real_python
    env['GOUDA_WORKSPACE'] = str(workspace)
    env.pop('ROS_DOMAIN_ID', None)
    env.pop('ROS_AUTOMATIC_DISCOVERY_RANGE', None)
    env.update(overrides)
    result = subprocess.run(
        [
            'bash',
            str(ROOT / 'scripts/gouda.sh'),
            'signal',
            '--camera',
            str(camera),
            '--no-ros',
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload['argv'] == ['--camera', str(camera), '--no-ros']
    assert payload['ros_domain_id'] == expected_domain
    assert payload['discovery_range'] == expected_discovery
