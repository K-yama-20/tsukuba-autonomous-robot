import json
from pathlib import Path
import signal
import subprocess
import threading
import time

import pytest

from gouda_gui.recording import OPTIONAL_TOPICS, RecordingManager, validate_config


class Result:
    returncode = 0
    stdout = '/opt/ros/jazzy'
    stderr = ''


class FakeProcess:
    _next_pid = 5000
    def __init__(self, output_dir):
        self.code = None
        self.output_dir = Path(output_dir)
        self.pid = FakeProcess._next_pid; FakeProcess._next_pid += 1
        self.block_wait = False
        self.wait_entered = threading.Event()
        self.allow_wait = threading.Event()
    def poll(self): return self.code
    def wait(self, timeout=None):
        self.wait_entered.set()
        if self.block_wait and not self.allow_wait.wait(timeout):
            raise subprocess.TimeoutExpired('ros2 bag record', timeout)
        if self.code is None:
            raise subprocess.TimeoutExpired('ros2 bag record', timeout)
        return self.code
    def finalize(self, counts=None, nonempty=True):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if counts is not None:
            lidar, imu = counts
            (self.output_dir/'metadata.yaml').write_text(
                'rosbag2_bagfile_information:\n'
                '  topics_with_message_count:\n'
                '  - topic_metadata: {name: /lidar_points}\n'
                f'    message_count: {lidar}\n'
                '  - topic_metadata: {name: /imu/data_raw}\n'
                f'    message_count: {imu}\n')
        if nonempty:
            (self.output_dir/'recording_0.mcap').write_bytes(b'mock-bag-bytes')


class Harness:
    def __init__(self, tmp_path, seen=lambda *_: False, counts=(3, 4), nonempty=True):
        self.tmp_path = tmp_path
        self.seen = seen
        self.counts = counts
        self.nonempty = nonempty
        self.calls = []
        self.processes = []
        self.kill_calls = []
        def run(args, **kwargs):
            self.calls.append(args)
            return Result()
        def popen(args, **kwargs):
            output = Path(args[args.index('-o')+1])
            proc = FakeProcess(output)
            self.processes.append((proc, args, kwargs))
            return proc
        def killpg(pid, sig):
            self.kill_calls.append((pid, sig))
            proc = next(p for p, _, _ in self.processes if p.pid == pid)
            if sig == signal.SIGINT:
                proc.finalize(self.counts, self.nonempty)
                proc.code = 0
            elif sig in (signal.SIGTERM, signal.SIGKILL):
                proc.code = -int(sig)
        self.manager = RecordingManager(tmp_path, sensor_data_seen=seen,
                                        popen=popen, run=run, killpg=killpg)


def test_defaults_retain_raw_sensor_and_tf_topics():
    cfg = validate_config({})
    assert cfg['topics'] == ['/lidar_points', '/imu/data_raw', '/tf', '/tf_static']
    assert cfg['storage_id'] == 'mcap'
    assert cfg['min_free_disk_mb'] == 2048
    assert '/kiss/odometry' in OPTIONAL_TOPICS
    assert '/glim_ros/lidar_odom' in OPTIONAL_TOPICS
    assert '/odom' not in OPTIONAL_TOPICS
    for missing in ('/lidar_points', '/imu/data_raw', '/tf', '/tf_static'):
        with pytest.raises(ValueError):
            validate_config(dict(cfg, topics=[t for t in cfg['topics'] if t != missing]))


@pytest.mark.parametrize('change', [
    {'topics': ['/lidar_points;touch /tmp/pwn', '/imu/data_raw', '/tf', '/tf_static']},
    {'topics': ['/lidar_points', '/imu/data_raw', '/tf', '/tf_static', '/bad topic']},
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
    h = Harness(tmp_path)
    cfg = h.manager.get_config()
    cfg['topics'].append('/kiss/odometry')
    saved = h.manager.update_config(cfg)
    assert json.loads((tmp_path/'bags/gouda/recording.json').read_text()) == saved
    cfg['topics'].remove('/tf_static')
    with pytest.raises(ValueError): h.manager.update_config(cfg)


def test_defaults_probe_accepts_topic_argument_and_success_uses_metadata(tmp_path):
    # None uses a safe topics-accepting default callback, avoiding a call-time TypeError.
    h = Harness(tmp_path, seen=None, counts=(12, 8))
    h.manager.start()
    proc, args, kwargs = h.processes[0]
    assert h.manager.status()['phase'] == 'awaiting_sensor_data'
    assert '--topics' in args and all(t in args for t in ('/lidar_points', '/imu/data_raw', '/tf', '/tf_static'))
    assert kwargs['start_new_session'] is True
    assert any('rosbag2_storage_mcap' in call for call in h.calls)
    response = h.manager.stop()
    assert response['phase'] in ('finalizing', 'completed', 'failed')
    assert h.manager._finalized.wait(2)
    final = h.manager.status()
    assert final['phase'] == 'completed'
    assert final['metadata_verified'] is True
    assert final['per_topic_counts'] == {'/lidar_points': 12, '/imu/data_raw': 8}
    assert final['bag_size_bytes'] > 0
    assert final['config']['storage_id'] == 'mcap'
    assert final['return_code'] == 0
    manifest = json.loads((Path(final['directory'])/'session.json').read_text())
    assert manifest['config'] == final['config']
    assert manifest['metadata_verified'] is True
    assert manifest['per_topic_counts']['/imu/data_raw'] == 8
    assert h.kill_calls == [(proc.pid, signal.SIGINT)]
    h.manager._watchdog.join(timeout=1)
    assert not h.manager._watchdog.is_alive()


def test_live_bag_size_is_reported_by_watchdog(tmp_path):
    h = Harness(tmp_path)
    state = h.manager.start()
    assert state['bag_size_available'] is False
    proc = h.processes[0][0]
    with pytest.raises(RuntimeError):
        h.manager.update_config(h.manager.get_config())
    proc.output_dir.mkdir(parents=True, exist_ok=True)
    (proc.output_dir/'recording_0.mcap').write_bytes(b'live-bytes')
    deadline = time.monotonic()+2
    while h.manager.status()['bag_size_bytes'] == 0 and time.monotonic() < deadline:
        time.sleep(.05)
    assert h.manager.status()['bag_size_available'] is True
    assert h.manager.status()['bag_size_bytes'] == len(b'live-bytes')
    h.manager.close()


def test_missing_one_sensor_topic_in_final_metadata_fails(tmp_path):
    h = Harness(tmp_path, seen=lambda *_: True, counts=(5, 0))
    h.manager.start()
    # Live GUI observation is provisional and cannot override the finalized bag.
    assert h.manager.status()['sensor_data_seen'] is False
    response = h.manager.stop()
    assert response['phase'] in ('finalizing', 'completed', 'failed')
    assert h.manager._finalized.wait(2)
    final = h.manager.status()
    assert final['phase'] == 'failed'
    assert final['metadata_verified'] is False
    assert final['per_topic_counts']['/imu/data_raw'] == 0
    assert 'missing messages' in final['error']


def test_empty_bag_storage_fails_even_with_sensor_callback(tmp_path):
    h = Harness(tmp_path, seen=lambda *_: True, counts=(1, 1), nonempty=False)
    h.manager.start()
    response = h.manager.stop()
    assert response['phase'] in ('finalizing', 'completed', 'failed')
    assert h.manager._finalized.wait(2)
    final = h.manager.status()
    assert final['phase'] == 'failed'
    assert final['bag_size_bytes'] == 0
    assert 'nonempty' in final['error']


def test_watchdog_enforces_duration_without_status_polling(tmp_path):
    h = Harness(tmp_path, counts=(2, 3))
    cfg = h.manager.get_config(); cfg['max_duration_sec'] = 1
    h.manager.update_config(cfg)
    h.manager.start()
    # Intentionally do not call status; watchdog owns the stop deadline.
    deadline = time.monotonic()+4
    while h.manager.process is not None and time.monotonic() < deadline:
        time.sleep(.05)
    h.manager._watchdog.join(timeout=1)
    final = h.manager.status()
    assert h.manager.process is None
    assert final['phase'] == 'completed'
    assert 'maximum recording duration' in final['error']
    assert not h.manager._watchdog.is_alive()


def test_finalizing_phase_is_visible_during_graceful_shutdown(tmp_path):
    h = Harness(tmp_path, counts=(2, 2))
    h.manager.start()
    proc = h.processes[0][0]
    proc.block_wait = True
    stopping = threading.Thread(target=h.manager.stop)
    stopping.start()
    assert proc.wait_entered.wait(2)
    assert h.manager.status()['phase'] == 'finalizing'
    proc.allow_wait.set()
    stopping.join(timeout=3)
    assert not stopping.is_alive()
    assert h.manager._finalized.wait(2)
    assert h.manager.status()['phase'] == 'completed'


def test_close_stops_process_group_and_freezes_elapsed_and_config(tmp_path):
    h = Harness(tmp_path, counts=(2, 2))
    h.manager.start()
    proc = h.processes[0][0]
    final = h.manager.close()
    elapsed = final['elapsed_sec']
    assert final['phase'] == 'completed'
    assert final['config']['topics'] == ['/lidar_points', '/imu/data_raw', '/tf', '/tf_static']
    assert h.kill_calls == [(proc.pid, signal.SIGINT)]
    time.sleep(.02)
    assert h.manager.status()['elapsed_sec'] == elapsed
    assert not h.manager._watchdog.is_alive()


def test_new_session_resets_summary_and_replaces_watchdog(tmp_path):
    h = Harness(tmp_path, counts=(1, 1))
    h.manager.start()
    first = h.manager.stop()
    assert first['phase'] in ('finalizing', 'completed', 'failed')
    assert h.manager._finalized.wait(2)
    old_watchdog = h.manager._watchdog
    old_watchdog.join(timeout=1)
    h.manager.start()
    assert h.manager.status()['return_code'] is None
    assert h.manager.status()['metadata_verified'] is False
    assert h.manager.status()['per_topic_counts'] == {}
    assert h.manager._watchdog is not old_watchdog
    h.manager.close()
