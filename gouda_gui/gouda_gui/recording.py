"""Safe lifecycle management for raw sensor and SLAM rosbag recordings.

ROS-independent so the GUI can own it without blocking its executor. Supply a
sensor_data_seen callback backed by actual ROS subscriptions before treating a
recording as useful; process creation alone is never a successful capture.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import threading
import time
from datetime import datetime, timezone

from .paths import workspace_dir

DEFAULT_TOPICS = ['/lidar_points', '/imu/data_raw', '/tf', '/tf_static']
OPTIONAL_TOPICS = ['/odom', '/clock']
TOPIC_RE = re.compile(r'^/(?:[A-Za-z][A-Za-z0-9_]*)(?:/[A-Za-z][A-Za-z0-9_]*)*$')
STORAGE_IDS = {'mcap', 'sqlite3'}


def validate_config(config):
    if not isinstance(config, dict):
        raise ValueError('Recording configuration must be an object')
    topics = config.get('topics', DEFAULT_TOPICS)
    if not isinstance(topics, list) or not topics or len(topics) > 32:
        raise ValueError('Choose between 1 and 32 topics')
    if any(not isinstance(topic, str) or len(topic) > 128 or not TOPIC_RE.fullmatch(topic) for topic in topics):
        raise ValueError('Topic names must be absolute ROS names with valid characters')
    if len(set(topics)) != len(topics):
        raise ValueError('Topic names must be unique')
    if not {'/lidar_points', '/imu/data_raw'}.issubset(topics):
        raise ValueError('Raw LiDAR and IMU topics are required')
    storage = config.get('storage_id', 'mcap')
    if storage not in STORAGE_IDS:
        raise ValueError('Storage must be mcap or sqlite3')
    duration = config.get('max_duration_sec', 3600)
    size = config.get('max_bag_size_mb', 2048)
    free = config.get('min_free_disk_mb', 2048)
    if type(duration) is not int or not 1 <= duration <= 43200:
        raise ValueError('Maximum duration must be 1 to 43200 seconds')
    if type(size) is not int or not 64 <= size <= 102400:
        raise ValueError('Maximum bag size must be 64 to 102400 MB')
    if type(free) is not int or not 256 <= free <= 1048576:
        raise ValueError('Minimum free disk must be 256 to 1048576 MB')
    return {'topics': list(topics), 'storage_id': storage,
            'max_duration_sec': duration, 'max_bag_size_mb': size,
            'min_free_disk_mb': free}


class RecordingManager:
    """Own at most one ros2 bag process and persist a validated config.

    ``sensor_data_seen(topics)`` must return True only after the GUI's
    subscriptions have observed at least one LiDAR or IMU message for this session.
    """
    def __init__(self, workspace=None, *, sensor_data_seen=None,
                 popen=subprocess.Popen, run=subprocess.run, clock=time.monotonic):
        self.workspace = Path(workspace or workspace_dir()).expanduser().resolve()
        self.config_path = self.workspace/'bags'/'gouda'/'recording.json'
        self.recordings_dir = self.workspace/'bags'/'recordings'
        self.sensor_data_seen = sensor_data_seen or (lambda: False)
        self._popen, self._run, self._clock = popen, run, clock
        self._lock = threading.RLock()
        self.process = None; self.log = None; self.directory = None
        self.started = None; self.phase = 'idle'; self.error = None; self._seen_data = False
        self.config = self._load_config()

    def _load_config(self):
        try:
            config = json.loads(self.config_path.read_text())
        except FileNotFoundError:
            return validate_config({})
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f'Cannot read recording configuration: {exc}') from exc
        try:
            return validate_config(config)
        except ValueError as exc:
            raise RuntimeError(f'Invalid saved recording configuration: {exc}') from exc

    def get_config(self):
        with self._lock:
            return dict(self.config, topics=list(self.config['topics']))

    def update_config(self, config):
        validated = validate_config(config)
        with self._lock:
            if self.process is not None and self.process.poll() is None:
                raise RuntimeError('Stop the active recording before changing its configuration')
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.config_path.with_suffix('.json.tmp')
            temporary.write_text(json.dumps(validated, indent=2)+'\n')
            os.replace(temporary, self.config_path)
            self.config = validated
            return self.get_config()

    def _ensure_storage(self, storage_id):
        if storage_id == 'mcap':
            # The CLI accepts an arbitrary ID even without the plugin, so use
            # the installed package metadata to detect rosbag2_storage_mcap.
            pkg = self._run(['ros2', 'pkg', 'prefix', 'rosbag2_storage_mcap'],
                            capture_output=True, text=True, timeout=10, check=False)
            if pkg.returncode != 0:
                raise RuntimeError('MCAP storage is unavailable. Install rosbag2-storage-mcap, then restart Gouda.')

    def _qos_file(self):
        # Per-topic override: lidar/IMU publishers are commonly best-effort;
        # /tf_static must request transient-local durability to receive latched TF.
        qos = self.directory/'qos_overrides.yaml'
        qos.write_text('''/lidar_points:\n  reliability: best_effort\n  durability: volatile\n  history: keep_last\n  depth: 10\n/imu/data_raw:\n  reliability: best_effort\n  durability: volatile\n  history: keep_last\n  depth: 100\n/tf_static:\n  reliability: reliable\n  durability: transient_local\n  history: keep_last\n  depth: 100\n''')
        return qos

    def start(self):
        with self._lock:
            self.status()
            if self.process is not None and self.process.poll() is None:
                raise RuntimeError('A recording is already active')
            self._ensure_storage(self.config['storage_id'])
            self.recordings_dir.mkdir(parents=True, exist_ok=True)
            free_mb = shutil.disk_usage(self.recordings_dir).free // (1024*1024)
            if free_mb < self.config['min_free_disk_mb']:
                raise RuntimeError(f'Insufficient free disk: {free_mb} MB available, '
                                   f'{self.config["min_free_disk_mb"]} MB required')
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            self.directory = self.recordings_dir/f'gouda_{stamp}'
            suffix = 1
            while self.directory.exists():
                self.directory = self.recordings_dir/f'gouda_{stamp}_{suffix:02d}'; suffix += 1
            self.directory.mkdir(mode=0o750)
            qos_path = self._qos_file()
            args = ['ros2', 'bag', 'record', '-s', self.config['storage_id'],
                    '-o', str(self.directory/'recording'),
                    '--max-bag-duration', str(self.config['max_duration_sec']),
                    '--max-bag-size', str(self.config['max_bag_size_mb']*1024*1024),
                    '--qos-profile-overrides-path', str(qos_path),
                    '--disable-keyboard-controls', '--topics'] + list(self.config['topics'])
            self.log = (self.directory/'recorder.log').open('ab')
            try:
                self.process = self._popen(args, stdin=subprocess.DEVNULL,
                                           stdout=self.log, stderr=subprocess.STDOUT,
                                           start_new_session=True, close_fds=True)
            except Exception:
                self.log.close(); self.log = None
                raise
            self.started = self._clock(); self.phase = 'awaiting_sensor_data'; self.error = None; self._seen_data = False
            return self.status()

    def _data_seen(self):
        return bool(self.sensor_data_seen(list(self.config['topics'])))

    def status(self):
        with self._lock:
            if self.process is not None:
                code = self.process.poll()
                if code is not None:
                    self._finish(code)
                elif self.started is not None:
                    elapsed = self._clock()-self.started
                    if self._data_seen():
                        self._seen_data = True
                        self.phase = 'recording'
                    elif elapsed >= 15:
                        self.phase = 'no_sensor_data'
                    else:
                        self.phase = 'awaiting_sensor_data'
                    if elapsed >= self.config['max_duration_sec']:
                        self.stop()
                    elif shutil.disk_usage(self.recordings_dir).free // (1024*1024) < self.config['min_free_disk_mb']:
                        self.error = 'Stopped because free disk fell below the configured minimum'
                        self.stop()
            return {'phase': self.phase, 'directory': str(self.directory) if self.directory else None,
                    'elapsed_sec': max(0, int(self._clock()-self.started)) if self.started else 0,
                    'sensor_data_seen': self._seen_data,
                    'return_code': getattr(self, '_return_code', None), 'error': self.error}

    def _finish(self, code):
        self._return_code = code
        if self.log:
            self.log.close(); self.log = None
        if code == 0 and self.phase == 'recording':
            self.phase = 'completed'
        elif self.phase == 'recording' or self.phase == 'awaiting_sensor_data' or self.phase == 'no_sensor_data':
            self.phase = 'failed' if code else 'no_sensor_data'
        if code and not self.error:
            self.error = f'ros2 bag recorder exited with status {code}; see recorder.log'
        self.process = None

    def stop(self):
        with self._lock:
            if self.process is None:
                return self.status()
            proc = self.process
            forced = False
            try:
                proc.send_signal(signal.SIGINT)
                try:
                    code = proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    forced = True
                    self.error = 'Recorder did not finalize after SIGINT; forced termination was required'
                    proc.terminate()
                    try: code = proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        proc.kill(); code = proc.wait(timeout=3)
                self._finish(code)
                if forced:
                    self.phase = 'failed'
                if self.phase == 'completed' and not self._seen_data:
                    self.phase = 'no_sensor_data'
            except Exception as exc:
                self.error = f'Could not stop recorder cleanly: {exc}'
                self.phase = 'failed'
                raise
            return self.status()

    def close(self):
        with self._lock:
            if self.process is not None:
                return self.stop()
            return self.status()
