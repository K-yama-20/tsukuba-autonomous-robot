"""Safe lifecycle management for raw sensor and SLAM rosbag recordings."""
from __future__ import annotations

import inspect
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

import yaml

from .paths import workspace_dir

DEFAULT_TOPICS = ['/lidar_points', '/imu/data_raw', '/tf', '/tf_static']
OPTIONAL_TOPICS = ['/kiss/odometry', '/glim_ros/lidar_odom', '/clock']
REQUIRED_TOPICS = tuple(DEFAULT_TOPICS)
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
    missing = sorted(set(REQUIRED_TOPICS)-set(topics))
    if missing:
        raise ValueError('Raw capture must retain LiDAR, IMU, /tf, and /tf_static topics')
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
    """Own one ros2 bag process, persist config, and verify finalized output.

    ``sensor_data_seen`` may accept a topic list or no arguments. It is a live,
    provisional indicator; successful completion requires verified finalized
    bag metadata containing messages for both raw sensor topics.
    """
    def __init__(self, workspace=None, *, sensor_data_seen=None,
                 popen=subprocess.Popen, run=subprocess.run, clock=time.monotonic,
                 disk_usage=shutil.disk_usage, killpg=os.killpg, use_sim_time=False):
        self.use_sim_time = bool(use_sim_time)
        self.workspace = Path(workspace or workspace_dir()).expanduser().resolve()
        self.config_path = self.workspace/'bags'/'gouda'/'recording.json'
        self.recordings_dir = self.workspace/'bags'/'recordings'
        self.sensor_data_seen = sensor_data_seen or (lambda _topics: False)
        try:
            self._probe_accepts_topics = len(inspect.signature(self.sensor_data_seen).parameters) != 0
        except (TypeError, ValueError):
            self._probe_accepts_topics = True
        self._popen, self._run, self._clock = popen, run, clock
        self._disk_usage, self._killpg = disk_usage, killpg
        self._lock = threading.RLock()
        self._watchdog_stop = threading.Event()
        self._watchdog = None
        self._finalizer = None
        self.started_at = None
        self._stopping = False
        self._finalized = threading.Event(); self._finalized.set()
        self.process = None; self.log = None; self.directory = None
        self.started = None; self._elapsed_final = 0
        self.phase = 'idle'; self.error = None; self._sensor_observed = False
        self._return_code = None; self._metadata_verified = False
        self._topic_counts = {}; self._bag_size_bytes = 0
        self.config_snapshot = None
        self.config = self._load_config()
        if self.use_sim_time and '/clock' not in self.config['topics']:
            self.config['topics'].append('/clock')

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
        if self.use_sim_time and '/clock' not in validated['topics']:
            validated['topics'].append('/clock')
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
            pkg = self._run(['ros2', 'pkg', 'prefix', 'rosbag2_storage_mcap'],
                            capture_output=True, text=True, timeout=10, check=False)
            if pkg.returncode != 0:
                raise RuntimeError('MCAP storage is unavailable. Install rosbag2-storage-mcap, then restart Gouda.')

    def _qos_file(self):
        qos = self.directory/'qos_overrides.yaml'
        qos.write_text('''/lidar_points:\n  reliability: best_effort\n  durability: volatile\n  history: keep_last\n  depth: 10\n/imu/data_raw:\n  reliability: best_effort\n  durability: volatile\n  history: keep_last\n  depth: 100\n/tf_static:\n  reliability: reliable\n  durability: transient_local\n  history: keep_last\n  depth: 100\n''')
        return qos

    def start(self):
        previous_watchdog = self._watchdog
        if previous_watchdog and previous_watchdog is not threading.current_thread():
            previous_watchdog.join(timeout=1)
            if previous_watchdog.is_alive():
                raise RuntimeError('Previous recording watchdog is still shutting down')
        with self._lock:
            if self.process is not None and self.process.poll() is None:
                raise RuntimeError('A recording is already active')
            self._ensure_storage(self.config['storage_id'])
            self.recordings_dir.mkdir(parents=True, exist_ok=True)
            free_mb = self._disk_usage(self.recordings_dir).free // (1024*1024)
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
            snapshot = dict(self.config, topics=list(self.config['topics']))
            args = ['ros2', 'bag', 'record', '-s', snapshot['storage_id'],
                    '-o', str(self.directory/'recording'),
                    '--max-bag-duration', str(snapshot['max_duration_sec']),
                    '--max-bag-size', str(snapshot['max_bag_size_mb']*1024*1024),
                    '--qos-profile-overrides-path', str(qos_path),
                    '--disable-keyboard-controls']
            if self.use_sim_time:
                args.append('--use-sim-time')
            args += ['--topics'] + snapshot['topics']
            self.log = (self.directory/'recorder.log').open('ab')
            try:
                self.process = self._popen(args, stdin=subprocess.DEVNULL,
                                           stdout=self.log, stderr=subprocess.STDOUT,
                                           start_new_session=True, close_fds=True)
            except Exception:
                self.log.close(); self.log = None
                raise
            self.config_snapshot = snapshot
            self.started_at = datetime.now(timezone.utc).isoformat()
            self.started = self._clock(); self._elapsed_final = 0
            self.phase = 'awaiting_sensor_data'; self.error = None
            self._sensor_observed = False; self._return_code = None
            self._metadata_verified = False; self._topic_counts = {}; self._bag_size_bytes = 0
            self._watchdog_stop.clear(); self._stopping = False; self._finalized.clear()
            self._watchdog = threading.Thread(target=self._watchdog_loop,
                                              name='gouda-recording-watchdog', daemon=True)
            self._write_manifest()
            self._watchdog.start()
            return self.status()

    def _data_seen(self):
        if self._probe_accepts_topics:
            return bool(self.sensor_data_seen(list(self.config_snapshot['topics'])))
        return bool(self.sensor_data_seen())

    def _watchdog_loop(self):
        while not self._watchdog_stop.wait(.5):
            proc_to_stop = None; force_error = False
            with self._lock:
                if self.process is None:
                    return
                if self._stopping:
                    continue
                try:
                    proc_to_stop, _ = self._refresh_locked()
                except Exception as exc:
                    self.error = f'Recording watchdog failed: {exc}'
                    self.phase = 'finalizing'; self._stopping = True
                    proc_to_stop = self.process; force_error = True
            if proc_to_stop is not None:
                self._terminate_process(proc_to_stop, force_error=force_error)

    def _refresh_locked(self):
        proc = self.process
        if proc is None:
            return None, None
        code = proc.poll()
        if code is not None:
            self.phase = 'finalizing'
            self._finish_locked(code)
            return None, None
        elapsed = max(0, self._clock()-self.started)
        if self._data_seen():
            self._sensor_observed = True
            self.phase = 'recording'
        elif elapsed >= 15:
            self.phase = 'no_sensor_data'
        else:
            self.phase = 'awaiting_sensor_data'
        self._measure_live_bag_locked()
        free_mb = self._disk_usage(self.recordings_dir).free // (1024*1024)
        reason = None
        if elapsed >= self.config_snapshot['max_duration_sec']:
            reason = 'Stopped at the configured maximum recording duration'
        elif free_mb < self.config_snapshot['min_free_disk_mb']:
            reason = 'Stopped because free disk fell below the configured minimum'
        if reason:
            self.error = reason
            self.phase = 'finalizing'; self._stopping = True
            return proc, reason
        return None, None

    def status(self):
        # Deliberately a cheap snapshot: monitoring and limit enforcement belong
        # to the watchdog, not browser/API polling threads.
        with self._lock:
            elapsed = self._elapsed_final
            if self.started is not None and self.process is not None:
                elapsed = max(0, int(self._clock()-self.started))
            return {'phase': self.phase,
                    'directory': str(self.directory) if self.directory else None,
                    'elapsed_sec': int(elapsed),
                    'sensor_data_seen': self._sensor_observed,
                    'return_code': self._return_code,
                    'error': self.error,
                    'config': dict(self.config_snapshot, topics=list(self.config_snapshot['topics'])) if self.config_snapshot else None,
                    'per_topic_counts': dict(self._topic_counts),
                    'metadata_verified': self._metadata_verified,
                    'bag_size_bytes': self._bag_size_bytes,
                    'bag_size_available': self._bag_size_bytes > 0}

    def _inspect_finalized_bag(self):
        if not self.directory:
            return False
        bag_dir = self.directory/'recording'
        metadata_paths = list(bag_dir.rglob('metadata.yaml')) if bag_dir.exists() else []
        if not metadata_paths:
            raise RuntimeError('Finalized metadata.yaml is missing; bag integrity is unverified')
        if len(metadata_paths) != 1:
            raise RuntimeError('Multiple metadata.yaml files found; bag integrity is ambiguous')
        metadata = yaml.safe_load(metadata_paths[0].read_text())
        if not isinstance(metadata, dict):
            raise RuntimeError('Finalized bag metadata is invalid')
        counts = {}
        for entry in metadata.get('rosbag2_bagfile_information', {}).get('topics_with_message_count', []):
            topic = entry.get('topic_metadata', {}).get('name')
            count = entry.get('message_count')
            if isinstance(topic, str) and type(count) is int and count >= 0:
                counts[topic] = count
        files = [p for p in bag_dir.rglob('*') if p.is_file() and p.suffix in ('.mcap', '.db3')]
        size = sum(p.stat().st_size for p in files if p.stat().st_size > 0)
        self._topic_counts = counts
        self._bag_size_bytes = size
        if not files or size <= 0:
            raise RuntimeError('Finalized bag has no nonempty MCAP or SQLite storage file')
        missing = [topic for topic in ('/lidar_points', '/imu/data_raw') if counts.get(topic, 0) <= 0]
        if missing:
            raise RuntimeError('Finalized bag is missing messages for required topic(s): '+', '.join(missing))
        return True

    def _finish_locked(self, code):
        self._return_code = code
        self._elapsed_final = max(0, int(self._clock()-self.started)) if self.started is not None else 0
        if self.log:
            self.log.close(); self.log = None
        self.process = None
        if code != 0:
            self.phase = 'failed'
            if not self.error:
                self.error = f'ros2 bag recorder exited with status {code}; see recorder.log'
        else:
            try:
                self._metadata_verified = self._inspect_finalized_bag()
                self.phase = 'completed' if self._metadata_verified else 'failed'
            except Exception as exc:
                self.phase = 'failed'
                self.error = str(exc)
        self._stopping = False
        self._finalized.set()
        self._watchdog_stop.set()
        self._write_manifest()

    def _signal_group(self, sig):
        if self.process is None:
            return
        try:
            self._killpg(self.process.pid, sig)
        except ProcessLookupError:
            pass

    def _measure_live_bag_locked(self):
        bag_dir = self.directory/'recording' if self.directory else None
        if not bag_dir or not bag_dir.is_dir():
            self._bag_size_bytes = 0
            return
        total = 0
        for path in bag_dir.iterdir():
            if path.is_file() and path.suffix in ('.mcap', '.db3'):
                try:
                    total += path.stat().st_size
                except OSError:
                    pass
        self._bag_size_bytes = total

    def _write_manifest(self):
        if not self.directory or not self.config_snapshot:
            return
        manifest = {'session_id': self.directory.name,
                    'started_at': self.started_at,
                    'ended_at': datetime.now(timezone.utc).isoformat() if self.process is None else None,
                    'phase': self.phase,
                    'elapsed_sec': self._elapsed_final if self.process is None else max(0, int(self._clock()-self.started)),
                    'config': self.config_snapshot,
                    'return_code': self._return_code,
                    'metadata_verified': self._metadata_verified,
                    'per_topic_counts': self._topic_counts,
                    'bag_size_bytes': self._bag_size_bytes,
                    'error': self.error}
        temporary = self.directory/'.session.json.tmp'
        temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
        os.replace(temporary, self.directory/'session.json')

    def _terminate_process(self, proc, *, force_error=False, already_signaled=False):
        forced = False
        code = None
        try:
            if not already_signaled:
                self._signal_group(signal.SIGINT)
            try:
                code = proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                forced = True
                if not self.error:
                    self.error = 'Recorder did not finalize after SIGINT; forced termination was required'
                self._signal_group(signal.SIGTERM)
                try:
                    code = proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self._signal_group(signal.SIGKILL)
                    code = proc.wait(timeout=3)
        except Exception as exc:
            with self._lock:
                self.error = f'Could not stop recorder cleanly: {exc}'
                self.phase = 'failed'
                self._stopping = False
                self._finalized.set()
                self._write_manifest()
            return
        with self._lock:
            if self.process is proc:
                self._finish_locked(code)
            if forced or force_error:
                self.phase = 'failed'
                self._metadata_verified = False
                if not self.error:
                    self.error = 'Recorder required forced termination; finalized data is unverified'
                self._write_manifest()

    def stop(self):
        proc = None
        with self._lock:
            if self.process is not None and not self._stopping:
                proc = self.process
                self.phase = 'finalizing'
                self._stopping = True
                self._write_manifest()
        if proc is not None:
            try:
                self._signal_group(signal.SIGINT)
                self._finalizer = threading.Thread(
                    target=self._terminate_process,
                    kwargs={'proc': proc, 'already_signaled': True},
                    name='gouda-recording-finalizer', daemon=True)
                self._finalizer.start()
            except Exception as exc:
                with self._lock:
                    self.error = f'Could not start recorder finalization: {exc}'
                    self.phase = 'failed'; self._stopping = False
                    self._finalized.set(); self._write_manifest()
        return self.status()

    def close(self):
        self._watchdog_stop.set()
        with self._lock:
            active = self.process is not None
        if active:
            self.stop()
            self._finalized.wait(timeout=24)
        if self._finalizer and self._finalizer is not threading.current_thread():
            self._finalizer.join(timeout=2)
        if self._watchdog and self._watchdog is not threading.current_thread():
            self._watchdog.join(timeout=2)
        return self.status()
