from pathlib import Path


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


def test_signal_launcher_passes_arguments_and_limits_default_ros_discovery():
    launcher = (ROOT / 'scripts/gouda.sh').read_text()
    signal_route = launcher.split('if [[ "${1:-}" == signal ]]; then', 1)[1].split('\nfi', 1)[0]

    assert 'shift' in signal_route
    assert 'ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-99}"' in signal_route
    assert 'ROS_AUTOMATIC_DISCOVERY_RANGE="${ROS_AUTOMATIC_DISCOVERY_RANGE:-LOCALHOST}"' in signal_route
    assert 'exec python3 -m gouda_signal.app "$@"' in signal_route
    assert 'stop' not in signal_route
