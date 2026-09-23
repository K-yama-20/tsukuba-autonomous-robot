import json
from pathlib import Path
import importlib.util
import subprocess
import sys

import pytest
from gouda_gui import paths

_spec = importlib.util.spec_from_file_location('configure_host_layout_test', Path(__file__).parents[1]/'scripts/configure_host.py')
configure_host = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(configure_host)


def test_paths_keep_maps_with_configured_workspace(tmp_path, monkeypatch):
    workspace = tmp_path/'robot workspace'
    monkeypatch.setenv('GOUDA_WORKSPACE', str(workspace))
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path/'old-config'))
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path/'old-data'))

    assert paths.config_dir() == workspace.resolve()/'bags/gouda'
    assert paths.data_dir() == workspace.resolve()
    assert paths.runtime_dir() == workspace.resolve()/'bags/gouda/runtime'
    assert paths.logs_dir() == workspace.resolve()/'bags/gouda/logs'


def test_legacy_host_config_is_copied_and_source_preserved(tmp_path, monkeypatch):
    workspace = tmp_path/'workspace'
    old_root = tmp_path/'config/gouda'
    old_root.mkdir(parents=True)
    cfg = {'workspace': str(workspace), 'imu_device': '/dev/serial/by-id/imu',
           'lidar_interface': 'enp3s0', 'hesai_config': str(tmp_path/'legacy-hesai.yaml')}
    (old_root/'host.json').write_text(json.dumps(cfg))
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path/'config'))

    new_root = configure_host.config_root(workspace)
    new_root.mkdir(parents=True)
    assert configure_host.load_or_migrate_config(workspace, new_root) == cfg
    assert json.loads((new_root/'host.json').read_text()) == cfg
    assert json.loads((old_root/'host.json').read_text()) == cfg


def test_conflicting_host_configs_are_not_overwritten(tmp_path, monkeypatch):
    workspace = tmp_path/'workspace'
    new_root = configure_host.config_root(workspace)
    new_root.mkdir(parents=True)
    legacy_root = tmp_path/'config/gouda'
    legacy_root.mkdir(parents=True)
    current = {'workspace': str(workspace), 'imu_device': '', 'lidar_interface': '', 'hesai_config': 'a'}
    other = dict(current, imu_device='/dev/ttyUSB0')
    (new_root/'host.json').write_text(json.dumps(current))
    (legacy_root/'host.json').write_text(json.dumps(other))
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path/'config'))

    with pytest.raises(ValueError, match='内容が異なります'):
        configure_host.load_or_migrate_config(workspace, new_root)
    assert json.loads((new_root/'host.json').read_text()) == current
    assert json.loads((legacy_root/'host.json').read_text()) == other


def test_maps_migrate_copy_only_and_preserve_legacy(tmp_path, monkeypatch):
    workspace = tmp_path/'workspace'
    legacy = tmp_path/'data/gouda'
    (legacy/'maps_sensor_slam').mkdir(parents=True)
    (legacy/'maps_sensor_slam/map.yaml').write_text('map content')
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path/'data'))
    monkeypatch.setattr(configure_host, 'running_gouda', lambda: False)

    configure_host.migrate_maps(workspace)
    assert (workspace/'maps_sensor_slam/map.yaml').read_text() == 'map content'
    assert (legacy/'maps_sensor_slam/map.yaml').read_text() == 'map content'


def test_map_collision_refuses_before_any_copy(tmp_path, monkeypatch):
    workspace = tmp_path/'workspace'
    legacy = tmp_path/'data/gouda'
    (legacy/'maps').mkdir(parents=True)
    (legacy/'maps/map.yaml').write_text('legacy')
    (legacy/'maps_sensor_slam').mkdir()
    (legacy/'maps_sensor_slam/map.yaml').write_text('legacy second map')
    (workspace/'maps_sensor_slam').mkdir(parents=True)
    (workspace/'maps_sensor_slam/map.yaml').write_text('existing')
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path/'data'))
    monkeypatch.setattr(configure_host, 'running_gouda', lambda: False)

    with pytest.raises(ValueError, match='競合'):
        configure_host.migrate_maps(workspace)
    assert not (workspace/'maps').exists()
    assert (workspace/'maps_sensor_slam/map.yaml').read_text() == 'existing'
    assert (legacy/'maps/map.yaml').read_text() == 'legacy'


def test_map_migration_waits_for_running_gui(tmp_path, monkeypatch):
    workspace = tmp_path/'workspace'
    legacy = tmp_path/'data/gouda'
    (legacy/'maps').mkdir(parents=True)
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path/'data'))
    monkeypatch.setattr(configure_host, 'running_gouda', lambda: True)

    with pytest.raises(ValueError, match='稼働中'):
        configure_host.migrate_maps(workspace)
    assert not (workspace/'maps').exists()
    assert (legacy/'maps').is_dir()


def make_setup_source(root, *, worktree=False):
    source = root/'installer'
    (source/'third_party').mkdir(parents=True)
    (source/'third_party/external.repos').write_text('repositories: {}\n')
    (source/'README.md').write_text('source')
    if worktree:
        (source/'.git').write_text('gitdir: /some/worktree\n')
    return source


def test_source_installs_as_real_canonical_directory(tmp_path):
    source = make_setup_source(tmp_path)
    workspace = tmp_path/'workspace'
    result = subprocess.run([sys.executable, str(Path(__file__).parents[1]/'scripts/prepare_sources.py'),
                             str(source), str(workspace)], text=True, capture_output=True)
    canonical = workspace/'src/tsukuba-autonomous-robot'

    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()) == canonical
    assert canonical.is_dir() and not canonical.is_symlink()
    assert (canonical/'README.md').read_text() == 'source'


def test_source_refuses_worktree_without_removing_known_alias(tmp_path):
    source = make_setup_source(tmp_path, worktree=True)
    workspace = tmp_path/'workspace'
    source_root = workspace/'src'
    source_root.mkdir(parents=True)
    alias = source_root/'tsukuba-autonomous-robot'
    alias.symlink_to(source, target_is_directory=True)
    result = subprocess.run([sys.executable, str(Path(__file__).parents[1]/'scripts/prepare_sources.py'),
                             str(source), str(workspace)], text=True, capture_output=True)

    assert result.returncode != 0
    assert 'worktree' in result.stderr
    assert alias.is_symlink() and alias.resolve() == source


def test_source_preserves_unrelated_canonical_checkout(tmp_path):
    source = make_setup_source(tmp_path)
    workspace = tmp_path/'workspace'
    canonical = workspace/'src/tsukuba-autonomous-robot'
    canonical.mkdir(parents=True)
    (canonical/'README.md').write_text('user checkout')
    result = subprocess.run([sys.executable, str(Path(__file__).parents[1]/'scripts/prepare_sources.py'),
                             str(source), str(workspace)], text=True, capture_output=True)

    assert result.returncode != 0
    assert (canonical/'README.md').read_text() == 'user checkout'


def test_build_state_archives_regular_install_before_symlink_mode(tmp_path, monkeypatch):
    workspace = tmp_path/'workspace'
    source = tmp_path/'source'
    source.mkdir()
    for name in ('build', 'install', 'log'):
        (workspace/name).mkdir(parents=True)
        (workspace/name/'marker').write_text(name)
    state = {'source': str(source), 'install_mode': 'regular'}
    (workspace/'.gouda-build-state.json').write_text(json.dumps(state))
    monkeypatch.setattr(configure_host, 'running_gouda', lambda: False)

    archive = configure_host.archive_build_outputs(workspace, source)
    assert archive is not None
    for name in ('build', 'install', 'log'):
        assert not (workspace/name).exists()
        assert (archive/name/'marker').read_text() == name


def test_build_state_is_idempotent_when_source_and_mode_match(tmp_path, monkeypatch):
    workspace = tmp_path/'workspace'
    source = tmp_path/'source'
    source.mkdir()
    for name in ('build', 'install', 'log'):
        (workspace/name).mkdir(parents=True)
        (workspace/name/'marker').write_text(name)
    configure_host.record_build_state(workspace, source)
    monkeypatch.setattr(configure_host, 'running_gouda', lambda: False)

    assert configure_host.archive_build_outputs(workspace, source) is None
    assert all((workspace/name/'marker').exists() for name in ('build', 'install', 'log'))


def test_build_archive_waits_for_live_process(tmp_path, monkeypatch):
    workspace = tmp_path/'workspace'
    source = tmp_path/'source'
    source.mkdir()
    (workspace/'build').mkdir(parents=True)
    monkeypatch.setattr(configure_host, 'running_gouda', lambda: True)

    with pytest.raises(ValueError, match='still running'):
        configure_host.archive_build_outputs(workspace, source)
    assert (workspace/'build').is_dir()
