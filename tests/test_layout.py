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
    monkeypatch.setattr(configure_host, 'running_gouda', lambda *args: False)

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
    monkeypatch.setattr(configure_host, 'running_gouda', lambda *args: False)

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
    monkeypatch.setattr(configure_host, 'running_gouda', lambda *args: True)

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
    monkeypatch.setattr(configure_host, 'running_gouda', lambda *args: False)

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
    monkeypatch.setattr(configure_host, 'running_gouda', lambda *args: False)

    assert configure_host.archive_build_outputs(workspace, source) is None
    assert all((workspace/name/'marker').exists() for name in ('build', 'install', 'log'))


def test_build_archive_waits_for_live_process(tmp_path, monkeypatch):
    workspace = tmp_path/'workspace'
    source = tmp_path/'source'
    source.mkdir()
    (workspace/'build').mkdir(parents=True)
    monkeypatch.setattr(configure_host, 'running_gouda', lambda *args: True)

    with pytest.raises(ValueError, match='still running'):
        configure_host.archive_build_outputs(workspace, source)
    assert (workspace/'build').is_dir()


def test_map_migration_marker_makes_workspace_authoritative(tmp_path, monkeypatch):
    workspace = tmp_path/'workspace'
    legacy = tmp_path/'data/gouda'
    (legacy/'maps').mkdir(parents=True)
    (legacy/'maps/map.yaml').write_text('old')
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path/'data'))
    monkeypatch.setattr(configure_host, 'running_gouda', lambda *args: False)

    configure_host.migrate_maps(workspace)
    (workspace/'maps/map.yaml').write_text('new workspace edit')
    configure_host.migrate_maps(workspace)
    assert (workspace/'maps/map.yaml').read_text() == 'new workspace edit'
    assert (legacy/'maps/map.yaml').read_text() == 'old'


def test_current_workspace_process_registry_is_checked(tmp_path, monkeypatch):
    process = subprocess.Popen(['sleep', '10'], start_new_session=True)
    try:
        workspace = tmp_path/'workspace'
        registry = workspace/'bags/gouda/runtime/processes.json'
        registry.parent.mkdir(parents=True)
        fields = Path(f'/proc/{process.pid}/stat').read_text().rsplit(')', 1)[1].split()
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        identity = boot+':'+fields[19]
        registry.write_text(json.dumps({'mode':'observation','processes':{'viewer':{'pid':process.pid,'start':identity}}}))
        monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path/'empty-data'))
        monkeypatch.setenv('GOUDA_WORKSPACE', str(workspace))
        assert configure_host.running_gouda()
        registry.write_text(json.dumps({'mode':'observation','processes':{'viewer':{'pid':process.pid,'start':'stale'}}}))
        assert not configure_host.running_gouda()
    finally:
        process.terminate()
        process.wait(timeout=3)


def test_valid_legacy_sensor_files_are_copied_and_rewritten(tmp_path, monkeypatch):
    import yaml
    from gouda_sensors.hesai_config import checked_config
    legacy = tmp_path/'config/gouda'
    legacy.mkdir(parents=True)
    correction = legacy/'xt32.csv'
    correction.write_text('Laser id,Elevation,Azimuth\n'+''.join(f'{i},0,0\n' for i in range(1,33)))
    config = {'lidar':[{'driver':{'source_type':1,'transform_flag':False,'use_timestamp_type':1,
              'standby_mode':-1,'lidar_udp_type':{'device_ip_address':'192.168.1.201',
              'host_ip_address':'192.168.1.100','udp_port':2368,'ptc_port':9347,
              'standby_mode':-1,'speed':-1,'correction_file_path':str(correction),'firetimes_path':''}},
              'ros':{'ros_frame_id':'hesai_lidar','ros_send_point_cloud_topic':'/lidar_points',
              'send_point_cloud_ros':True}}]}
    old_profile = legacy/'hesai.yaml'
    old_profile.write_text(yaml.safe_dump(config))
    checked_config(old_profile, 'hardware')
    workspace = tmp_path/'workspace'
    root = configure_host.config_root(workspace)
    root.mkdir(parents=True)
    cfg = {'workspace':str(workspace),'imu_device':'','lidar_interface':'','hesai_config':str(old_profile)}
    monkeypatch.setenv('XDG_CONFIG_HOME',str(tmp_path/'config'))

    configure_host.migrate_legacy_sensor_config(cfg,workspace,root)
    copied = Path(cfg['hesai_config'])
    migrated = yaml.safe_load(copied.read_text())['lidar'][0]['driver']['lidar_udp_type']['correction_file_path']
    assert copied == root/'hesai.yaml'
    assert Path(migrated) == root/'xt32.csv'
    assert Path(migrated).read_text() == correction.read_text()
    assert correction.read_text().startswith('Laser id,Elevation,Azimuth\n')
    checked_config(copied, 'hardware')


def test_build_state_archives_when_source_path_changes(tmp_path, monkeypatch):
    workspace = tmp_path/'workspace'
    old_source = tmp_path/'old-source'
    new_source = tmp_path/'new-source'
    old_source.mkdir(); new_source.mkdir()
    (workspace/'build').mkdir(parents=True)
    (workspace/'build/cache').write_text('old source cache')
    configure_host.record_build_state(workspace, old_source)
    monkeypatch.setattr(configure_host, 'running_gouda', lambda *args: False)

    archive = configure_host.archive_build_outputs(workspace, new_source)
    assert archive is not None
    assert (archive/'build/cache').read_text() == 'old source cache'
    assert not (workspace/'build').exists()


def test_sensor_migration_recovers_after_host_save_before_marker(tmp_path, monkeypatch):
    import yaml
    from gouda_sensors.hesai_config import checked_config
    legacy = tmp_path/'config/gouda'
    legacy.mkdir(parents=True)
    correction = legacy/'xt32.csv'
    correction.write_text('Laser id,Elevation,Azimuth\n'+''.join(f'{i},0,0\n' for i in range(1,33)))
    config = {'lidar':[{'driver':{'source_type':1,'transform_flag':False,'use_timestamp_type':1,
              'standby_mode':-1,'lidar_udp_type':{'device_ip_address':'192.168.1.201',
              'host_ip_address':'192.168.1.100','udp_port':2368,'ptc_port':9347,
              'standby_mode':-1,'speed':-1,'correction_file_path':str(correction),'firetimes_path':''}},
              'ros':{'ros_frame_id':'hesai_lidar','ros_send_point_cloud_topic':'/lidar_points',
              'send_point_cloud_ros':True}}]}
    profile=legacy/'hesai.yaml'
    profile.write_text(yaml.safe_dump(config))
    checked_config(profile,'hardware')
    workspace=tmp_path/'workspace'
    root=configure_host.config_root(workspace)
    root.mkdir(parents=True)
    cfg={'workspace':str(workspace),'imu_device':'','lidar_interface':'','hesai_config':str(profile)}
    monkeypatch.setenv('XDG_CONFIG_HOME',str(tmp_path/'config'))
    original_writer=configure_host.write_migration_marker
    monkeypatch.setattr(configure_host,'write_migration_marker',
                        lambda *args: (_ for _ in ()).throw(OSError('simulated interruption')))

    with pytest.raises(OSError,match='simulated interruption'):
        configure_host.migrate_legacy_sensor_config(cfg,workspace,root)
    persisted=json.loads((root/'host.json').read_text())
    assert Path(persisted['hesai_config']) == root/'hesai.yaml'
    assert not (root/'.sensor-migration-complete').exists()

    monkeypatch.setattr(configure_host,'write_migration_marker',original_writer)
    configure_host.migrate_legacy_sensor_config(persisted,workspace,root)
    assert (root/'.sensor-migration-complete').exists()
    checked_config(persisted['hesai_config'],'hardware')
    assert profile.is_file() and correction.is_file()
