import json
from pathlib import Path
import signal
import subprocess

import pytest

from gouda_gui.recording import RecordingManager, validate_config


class Result:
    returncode = 0
    stdout = '/opt/ros/jazzy'
    stderr = ''


class FakeProcess:
    def __init__(self, **_):
        self.code = None
        self.signals = []
    def poll(self): return self.code
    def send_signal(self, value): self.signals.append(value); self.code = 0
    def wait(self, timeout=None): return self.code
    def terminate(self): self.code = -15
    def kill(self): self.code = -9


def manager(tmp_path, seen=lambda *_: False):
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        return Result()
    processes = []
    def popen(*args, **kwargs):
        proc = FakeProcess()
        processes.append((proc, args[0], kwargs))
        return proc
    mgr = RecordingManager(tmp_path, sensor_data_seen=seen, popen=popen, run=run)
    return mgr, calls, processes


def test_defaults_include_raw_sensors_tf_and_safe_limits():
    cfg = validate_config({})
    assert cfg['topics'] == ['/lidar_points', '/imu/data_raw', '/tf', '/tf_static']
    assert cfg['storage_id'] == 'mcap'
    assert cfg['min_free_disk_mb'] == 2048


@pytest.mark.parametrize('change', [
    {'topics': ['/lidar_points;touch /tmp/pwn', '/imu/data_raw']},
    {'topics': ['/lidar_points', '/imu/data_raw', '/bad topic']},
    {'topics': ['/lidar_points']},
    {'storage_id': '../mcap'},
    {'max_duration_sec': True},
    {'max_bag_size_mb': 1},
    {'min_free_disk_mb': -1},
])
def test_rejects_invalid_or_injectable_config(change):
    cfg = validate_config({})
    cfg.update(change)
    with pytest.raises(ValueError): validate_config(cfg)


def test_update_persists_only_validated_config(tmp_path):
    mgr, _, _ = manager(tmp_path)
    cfg = mgr.get_config()
    cfg['topics'].append('/odom')
    saved = mgr.update_config(cfg)
    assert json.loads((tmp_path/'bags/gouda/recording.json').read_text()) == saved
    with pytest.raises(ValueError): mgr.update_config({'topics': ['/bad;command']})


def test_start_waits_for_real_sensor_data_and_stop_finalizes(tmp_path):
    data = {'seen': False}
    mgr, calls, processes = manager(tmp_path, lambda *_: data['seen'])
    state = mgr.start()
    proc, args, kwargs = processes[0]
    assert state['phase'] == 'awaiting_sensor_data'
    assert state['sensor_data_seen'] is False
    assert args[0:4] == ['ros2', 'bag', 'record', '-s']
    assert '--topics' in args
    assert '/lidar_points' in args and '/imu/data_raw' in args
    assert kwargs['start_new_session'] is True
    assert any('rosbag2_storage_mcap' in call for call in calls)
    assert Path(state['directory'], 'qos_overrides.yaml').is_file()
    data['seen'] = True
    assert mgr.status()['phase'] == 'recording'
    final = mgr.stop()
    assert proc.signals == [signal.SIGINT]
    assert final['phase'] == 'completed'
    assert final['sensor_data_seen'] is True
    assert final['return_code'] == 0


def test_empty_capture_never_reports_success(tmp_path):
    mgr, _, _ = manager(tmp_path)
    mgr.start()
    final = mgr.stop()
    assert final['phase'] == 'no_sensor_data'
    assert final['sensor_data_seen'] is False


def test_single_recorder_and_config_locked_while_active(tmp_path):
    mgr, _, _ = manager(tmp_path)
    mgr.start()
    with pytest.raises(RuntimeError): mgr.start()
    with pytest.raises(RuntimeError): mgr.update_config(mgr.get_config())
    mgr.close()
    assert mgr.status()['phase'] == 'completed' or mgr.status()['phase'] == 'no_sensor_data'
