"""Persisted sensor-mapping settings and the optional GLIM process manager."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time
from typing import Any

SCHEMA_VERSION = 1
DEFAULT_SETTINGS = {
    "schema_version": SCHEMA_VERSION,
    "backend": "glim_imu",
    "compute": "cpu",
    "clock_policy": "host_mapped",
    "clock_evidence": "No sync wiring; MCU acquisition time mapped to PC clock. Offsets 0 s are provisional and synchronization accuracy is unverified.",
    "lidar_topic": "/lidar_points",
    "imu_topic": "/imu/data_raw",
    "lidar_frame": "hesai_lidar",
    "imu_frame": "imu_link",
    "extrinsic_lidar_imu": {
        "translation_m": [0.0, 0.0, -0.0514],
        "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
    },
    "point_time_field": "timestamp",
    "point_time_datatype": "float64",
    "point_time_mode": "absolute",
    "point_time_unit": "seconds",
    "imu_accel_unit": "m/s^2",
    "imu_gyro_unit": "rad/s",
    "imu_clock_offset_sec": 0.0,
    "lidar_clock_offset_sec": 0.0,
}


def mapping_config_path() -> Path:
    """Return the workspace settings path shared with MissionControl."""
    workspace = Path(os.environ.get("GOUDA_WORKSPACE", Path.home() / "gouda_ws")).expanduser()
    return workspace / "bags" / "gouda" / "mapping.json"


def load_mapping_settings(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path else mapping_config_path()
    if not target.exists():
        return dict(DEFAULT_SETTINGS)
    value = json.loads(target.read_text())
    if not isinstance(value, dict):
        raise ValueError("mapping settings must be a JSON object")
    return {**DEFAULT_SETTINGS, **value}


def save_mapping_settings(settings: dict[str, Any], path: str | Path | None = None) -> Path:
    """Validate and atomically persist settings; UNKNOWN calibration is allowed as a draft."""
    if not isinstance(settings, dict):
        raise ValueError("mapping settings must be an object")
    value = {**DEFAULT_SETTINGS, **settings, "schema_version": SCHEMA_VERSION}
    errors = validate_mapping_settings(value, require_ready=False)
    if errors:
        raise ValueError("; ".join(errors))
    target = Path(path) if path else mapping_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    os.chmod(temp, 0o600)
    temp.replace(target)
    return target


def validate_mapping_settings(settings: dict[str, Any], require_ready: bool = False) -> list[str]:
    """Return human-readable errors. require_ready gates GLIM start, never draft saving."""
    errors: list[str] = []
    if not isinstance(settings, dict):
        return ["mapping settings must be an object"]
    cfg = {**DEFAULT_SETTINGS, **settings}
    if cfg.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
        errors.append("unsupported mapping settings schema_version")
    if cfg["backend"] not in ("kiss_icp", "glim_imu"):
        errors.append("backend must be kiss_icp or glim_imu")
    if cfg["compute"] != "cpu":
        errors.append("GLIM CUDA is not enabled in this build; select CPU")
    for key in ("lidar_topic", "imu_topic", "lidar_frame", "imu_frame"):
        if not isinstance(cfg[key], str) or not cfg[key].strip():
            errors.append(f"{key} must be a non-empty string")
    if cfg["clock_policy"] not in ("unknown", "host_mapped", "external_common", "simulation"):
        errors.append("clock_policy must be unknown, host_mapped, external_common, or simulation")
    if not isinstance(cfg["clock_evidence"], str):
        errors.append("clock_evidence must be a string")
    if cfg["backend"] == "glim_imu":
        enums = {
            "point_time_field": ("unknown", "t", "time", "time_stamp", "timestamp"),
            "point_time_mode": ("unknown", "relative", "absolute"),
            "point_time_datatype": ("unknown", "uint32", "float32", "float64"),
            "point_time_unit": ("unknown", "seconds", "nanoseconds"),
            "imu_accel_unit": ("unknown", "m/s^2", "g"),
            "imu_gyro_unit": ("unknown", "rad/s", "deg/s"),
        }
        for key, allowed in enums.items():
            if cfg[key] not in allowed:
                errors.append(f"{key} must be one of {', '.join(allowed)}")
        for key in ("imu_clock_offset_sec", "lidar_clock_offset_sec"):
            value = cfg.get(key)
            if value is not None and not _finite_number(value):
                errors.append(f"{key} must be a finite number of seconds or null")
        ext = cfg.get("extrinsic_lidar_imu")
        if ext is not None:
            if not isinstance(ext, dict):
                errors.append("extrinsic_lidar_imu must be null or a transform object")
            else:
                translation = ext.get("translation_m")
                quaternion = ext.get("quaternion_xyzw")
                if translation is not None and not _finite_vector(translation, 3):
                    errors.append("T_lidar_imu.translation_m must contain three finite values in metres")
                if quaternion is not None and not _finite_vector(quaternion, 4):
                    errors.append("T_lidar_imu.quaternion_xyzw must contain four finite values")
                elif _finite_vector(quaternion, 4) and abs(math.sqrt(sum(float(v) ** 2 for v in quaternion)) - 1.0) > 1e-3:
                    errors.append("T_lidar_imu quaternion must be normalized")
    if cfg["backend"] == "glim_imu" and require_ready:
        if cfg["clock_policy"] == "unknown":
            errors.append("Clock configuration is UNKNOWN; inspect device settings before GLIM")
        if cfg["clock_policy"] == "external_common":
            errors.append("External IMU clock is not supported by the current USB driver; PPS observation alone is insufficient")
        if not isinstance(cfg["clock_evidence"], str) or not cfg["clock_evidence"].strip():
            errors.append("clock_evidence is required: record terminals, LiDAR clock source/lock and PC clock relationship")
        ext = cfg.get("extrinsic_lidar_imu")
        if not isinstance(ext, dict):
            errors.append("T_lidar_imu is UNKNOWN; measure and enter the LiDAR/IMU transform")
        else:
            translation = ext.get("translation_m")
            quaternion = ext.get("quaternion_xyzw")
            if not _finite_vector(translation, 3):
                errors.append("T_lidar_imu.translation_m must contain three finite measured values in metres")
            if not _finite_vector(quaternion, 4):
                errors.append("T_lidar_imu.quaternion_xyzw must contain four finite measured values")
            elif abs(math.sqrt(sum(float(v) ** 2 for v in quaternion)) - 1.0) > 1e-3:
                errors.append("T_lidar_imu quaternion must be normalized")
        if cfg["point_time_field"] not in ("t", "time", "time_stamp", "timestamp"):
            errors.append("point_time_field is UNKNOWN; select a GLIM-supported field present in PointCloud2")
        if cfg["point_time_mode"] not in ("relative", "absolute"):
            errors.append("point_time_mode is UNKNOWN; select relative or absolute")
        if cfg["point_time_unit"] not in ("seconds", "nanoseconds"):
            errors.append("point_time_unit is UNKNOWN; select seconds or nanoseconds")
        if cfg["point_time_datatype"] not in ("uint32", "float32", "float64"):
            errors.append("point_time_datatype is UNKNOWN; select uint32, float32, or float64")
        if cfg["point_time_datatype"] == "uint32" and cfg["point_time_unit"] == "seconds":
            errors.append("GLIM reads UINT32 point-time fields as nanoseconds; select nanoseconds or use floating-point seconds")
        if cfg["imu_accel_unit"] not in ("m/s^2", "g"):
            errors.append("imu_accel_unit is UNKNOWN; select m/s^2 or g")
        if cfg["imu_gyro_unit"] not in ("rad/s", "deg/s"):
            errors.append("imu_gyro_unit is UNKNOWN; select rad/s or deg/s")
        for key in ("imu_clock_offset_sec", "lidar_clock_offset_sec"):
            if not _finite_number(cfg.get(key)):
                errors.append(f"{key} is UNKNOWN; enter a measured or validated offset in seconds")
    return errors


def mapping_phase(input_state: dict[str, str], errors: list[str], received_at: dict[str, float],
                  now: float | None = None, max_age: float = 2.0) -> tuple[str, dict[str, str]]:
    """Pure readiness gate used by the process manager and tested without ROS hardware."""
    now = time.monotonic() if now is None else now
    state = dict(input_state)
    for key, received in received_at.items():
        if now - received > max_age and state.get(key) == "ready":
            state[key] = "stale"
    if errors:
        return "preflight_error", state
    required = ("lidar", "imu", "odometry")
    if all(state.get(key) == "ready" for key in required):
        return "mapping", state
    if all(state.get(key) == "ready" for key in ("lidar", "imu")):
        return "processing", state
    return "waiting_for_sensors", state


def saved_glim_map_complete(directory: str | Path) -> bool:
    """Require nonempty serialized graph and at least one mapped submap/frame."""
    root = Path(directory)
    graph = root / "graph.txt"
    if not graph.is_file():
        return False
    if any(not (root / name).is_file() or (root / name).stat().st_size == 0
           for name in ("graph.bin", "values.bin")):
        return False
    counts = {}
    for line in graph.read_text(errors="replace").splitlines():
        key, separator, value = line.partition(":")
        if separator:
            try:
                counts[key.strip()] = int(value.strip())
            except ValueError:
                continue
    return counts.get("num_submaps", 0) > 0 and counts.get("num_all_frames", 0) > 0


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _finite_vector(value: Any, length: int) -> bool:
    return isinstance(value, (list, tuple)) and len(value) == length and all(_finite_number(v) for v in value)


def _json_write(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def make_glim_config(settings: dict[str, Any], config_dir: str | Path, upstream_config_dir: str | Path | None = None) -> Path:
    """Materialize the upstream CPU config set with validated sensor-specific values."""
    errors = validate_mapping_settings(settings, require_ready=True)
    if errors:
        raise ValueError("; ".join(errors))
    cfg = {**DEFAULT_SETTINGS, **settings}
    root = Path(config_dir)
    root.mkdir(parents=True, exist_ok=True)
    if upstream_config_dir is None:
        from ament_index_python.packages import get_package_share_directory
        upstream = Path(get_package_share_directory("glim")) / "config"
    else:
        upstream = Path(upstream_config_dir)
    for name in ("config_logging.json", "config_viewer.json", "config_preprocess.json",
                 "config_odometry_cpu.json", "config_sub_mapping_cpu.json", "config_global_mapping_cpu.json"):
        source = upstream / name
        if not source.is_file():
            raise RuntimeError(f"GLIM CPU config not installed: {source}")
        (root / name).write_bytes(source.read_bytes())

    _json_write(root / "config.json", {"global": {
        "config_path": "", "config_ros": "config_ros.json", "config_logging": "config_logging.json",
        "config_viewer": "config_viewer.json", "config_sensors": "config_sensors.json",
        "config_preprocess": "config_preprocess.json", "config_odometry": "config_odometry_cpu.json",
        "config_sub_mapping": "config_sub_mapping_cpu.json", "config_global_mapping": "config_global_mapping_cpu.json",
    }})
    accel = 9.80665 if cfg["imu_accel_unit"] == "g" else 1.0
    gyro = math.pi / 180.0 if cfg["imu_gyro_unit"] == "deg/s" else 1.0
    _json_write(root / "config_ros.json", {"glim_ros": {
        "enable_local_mapping": True, "enable_global_mapping": True, "keep_raw_points": False,
        "imu_time_offset": float(cfg["imu_clock_offset_sec"]),
        "points_time_offset": float(cfg["lidar_clock_offset_sec"]),
        "acc_scale": accel, "ang_scale": gyro,
        "imu_frame_id": cfg["imu_frame"], "lidar_frame_id": cfg["lidar_frame"],
        "base_frame_id": cfg["lidar_frame"], "odom_frame_id": "odom_lidar", "map_frame_id": "glim_map",
        "publish_imu2lidar": False, "tf_time_offset": 0.000001,
        "extension_modules": ["librviz_viewer.so"],
        "imu_topic": "/gouda/synced/imu", "points_topic": "/gouda/synced/points", "image_topic": "/gouda/glim/image_unused",
        "imu_qos": {"profile": "sensor_data", "depth": 1000},
        "points_qos": {"profile": "sensor_data"},
    }})
    ext = cfg["extrinsic_lidar_imu"]
    _json_write(root / "config_sensors.json", {"sensors": {
        "imu_acc_noise": 0.05, "imu_gyro_noise": 0.02, "imu_int_noise": 0.001,
        "imu_bias_noise_acc": 1e-5, "imu_bias_noise_gyro": 1e-6,
        "global_shutter_lidar": False,
        "T_lidar_imu": [*map(float, ext["translation_m"]), *map(float, ext["quaternion_xyzw"])],
        "intensity_field": "intensity", "ring_field": "",
        "autoconf_perpoint_times": False, "autoconf_prefer_frame_time": False,
        "perpoint_relative_time": cfg["point_time_mode"] == "relative",
        "perpoint_time_scale": 1.0 if cfg["point_time_unit"] == "seconds" or cfg["point_time_datatype"] == "uint32" else 1e-9,
    }})
    return root


def static_tf_args(settings: dict[str, Any]) -> list[str]:
    """Return imu_link parent -> LiDAR child transform, inverse of T_lidar_imu."""
    ext = settings["extrinsic_lidar_imu"]
    x, y, z, qx, qy, qz, qw = map(float, [*ext["translation_m"], *ext["quaternion_xyzw"]])
    # T_imu_lidar = inverse(T_lidar_imu)
    r00 = 1 - 2 * (qy*qy + qz*qz); r01 = 2 * (qx*qy - qz*qw); r02 = 2 * (qx*qz + qy*qw)
    r10 = 2 * (qx*qy + qz*qw); r11 = 1 - 2 * (qx*qx + qz*qz); r12 = 2 * (qy*qz - qx*qw)
    r20 = 2 * (qx*qz - qy*qw); r21 = 2 * (qy*qz + qx*qw); r22 = 1 - 2 * (qx*qx + qy*qy)
    tx, ty, tz = -(r00*x + r10*y + r20*z), -(r01*x + r11*y + r21*z), -(r02*x + r12*y + r22*z)
    return ["--x", str(tx), "--y", str(ty), "--z", str(tz),
            "--qx", str(-qx), "--qy", str(-qy), "--qz", str(-qz), "--qw", str(qw),
            "--frame-id", settings["imu_frame"], "--child-frame-id", settings["lidar_frame"]]


class GlimSession:
    """Own one CPU GLIM mapping process; SIGINT causes durable native graph save."""
    def __init__(self, node: Any, directory: str | Path):
        self.node = node
        self.directory = Path(directory)
        self.process: subprocess.Popen | None = None
        self.log = None
        self.phase = "idle"
        self.active_backend: str | None = None
        self.map_output_directory: Path | None = None
        self.log_path: Path | None = None
        self._subscriptions = []
        self.input_state = {"lidar": "waiting", "imu": "waiting", "odometry": "waiting", "errors": []}
        self._received_at = {}
        self._settings: dict[str, Any] | None = None

    def start(self, settings: dict[str, Any], output_directory: str | Path, use_sim_time: bool = False) -> None:
        if self.status() == "mapping":
            raise RuntimeError("GLIM is already running")
        errors = validate_mapping_settings(settings, require_ready=True)
        if errors:
            raise ValueError("; ".join(errors))
        try:
            from ament_index_python.packages import get_package_share_directory
            from gouda_gui.paths import logs_dir
        except ImportError as exc:
            raise RuntimeError("ROS 2 Jazzy and gouda_gui are required for GLIM") from exc
        output = Path(output_directory).expanduser().resolve()
        if output.exists() and any(output.iterdir()):
            raise ValueError("GLIM output directory already contains data")
        output.mkdir(parents=True, exist_ok=True)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._settings = {**DEFAULT_SETTINGS, **settings}
        self.input_state = {"lidar": "waiting", "imu": "waiting", "odometry": "waiting", "errors": []}
        self._received_at = {}
        self._ensure_monitors(self._settings)
        # Keep generated launch config separate from GLIM's native output/config snapshot.
        runtime_config = self.directory / ".glim_runtime" if self.directory.resolve() == output else self.directory
        runtime_config.mkdir(parents=True, exist_ok=True)
        config_path = runtime_config / "config"
        make_glim_config(settings, config_path)
        get_package_share_directory("glim_ros")
        logs = Path(logs_dir()); logs.mkdir(parents=True, exist_ok=True)
        import uuid
        self.log_path = logs / f"glim-{uuid.uuid4().hex}.log"
        self.log = self.log_path.open("w")
        settings_path = runtime_config / "settings.json"
        _json_write(settings_path, settings)
        cmd = ["ros2", "launch", "gouda_navigation", "glim_mapping.launch.py",
               f"settings_file:={settings_path}", f"config_path:={config_path}", f"dump_path:={output}",
               f"use_sim_time:={str(bool(use_sim_time)).lower()}"]
        env = dict(os.environ, ROS_DOMAIN_ID=os.environ.get("ROS_DOMAIN_ID", "99"),
                   ROS_AUTOMATIC_DISCOVERY_RANGE=os.environ.get("ROS_AUTOMATIC_DISCOVERY_RANGE", "LOCALHOST"))
        env.pop("ROS_LOCALHOST_ONLY", None)
        self.process = subprocess.Popen(cmd, env=env, stdin=subprocess.DEVNULL, stdout=self.log,
                                        stderr=subprocess.STDOUT, start_new_session=True)
        self.phase = "waiting_for_sensors"
        self.active_backend = "glim_imu"
        self.map_output_directory = output
        # Startup is deliberately non-blocking: sensor streams may be started later.
        time.sleep(0.15)
        if self.process.poll() is not None:
            self.phase = "failed"
            self.active_backend = None
            tail = self.log_path.read_text(errors="replace")[-1500:]
            raise RuntimeError(f"GLIM launch failed: {tail or self.process.returncode}")
        return

    def _ensure_monitors(self, settings: dict[str, Any]) -> None:
        if self._subscriptions:
            return
        from sensor_msgs.msg import PointCloud2, Imu
        from nav_msgs.msg import Odometry
        from std_msgs.msg import String
        from rclpy.qos import qos_profile_sensor_data
        self._replace_input_errors("clock", ["Waiting for clock provenance checks"])
        self._subscriptions = [
            self.node.create_subscription(String, "/gouda/time_sync/state", self._on_sync_state, 10),
            self.node.create_subscription(PointCloud2, settings["lidar_topic"], self._on_points, qos_profile_sensor_data),
            self.node.create_subscription(Imu, settings["imu_topic"], self._on_imu, qos_profile_sensor_data),
            self.node.create_subscription(Odometry, "/glim_ros/lidar_odom", self._on_odom, 10),
        ]

    def _on_sync_state(self, msg: Any) -> None:
        if not self._settings or self.process is None or self.process.poll() is not None:
            return
        try:
            state = json.loads(msg.data)
            valid = state.get('status') in ('host_mapped', 'simulation')
            self._replace_input_errors('clock', [] if valid else state.get('errors') or ['Clock gate blocked'])
            self._received_at['clock'] = time.monotonic()
        except (ValueError, AttributeError, TypeError):
            self._replace_input_errors('clock', ['Invalid clock status'])
        self._refresh_phase()

    def _on_points(self, msg: Any) -> None:
        if not self._settings or self.process is None or self.process.poll() is not None:
            return
        cfg = self._settings
        names = [f.name for f in msg.fields]
        aliases = [name for name in names if name in ("t", "time", "time_stamp", "timestamp")]
        selected = cfg["point_time_field"]
        actual = next((f for f in msg.fields if f.name == selected), None)
        datatype_names = {6: "uint32", 7: "float32", 8: "float64"}
        problems = []
        if msg.header.frame_id != cfg["lidar_frame"]:
            problems.append(f"LiDAR frame is {msg.header.frame_id!r}, expected {cfg['lidar_frame']!r}")
        if not aliases:
            problems.append("PointCloud2 has no GLIM-supported point-time field")
        elif aliases[-1] != selected:
            problems.append(f"GLIM selects the last recognized time field {aliases[-1]!r}, not {selected!r}")
        if actual is None:
            problems.append(f"selected point-time field {selected!r} is absent")
        elif datatype_names.get(actual.datatype) != cfg["point_time_datatype"]:
            problems.append(f"point-time field type is {datatype_names.get(actual.datatype, actual.datatype)!r}, expected {cfg['point_time_datatype']!r}")
        self.input_state["lidar"] = "error" if problems else "ready"
        self._received_at["lidar"] = time.monotonic()
        self._replace_input_errors("lidar", problems)
        self._refresh_phase()

    def _on_imu(self, msg: Any) -> None:
        if not self._settings or self.process is None or self.process.poll() is not None:
            return
        expected = self._settings["imu_frame"]
        problems = [] if msg.header.frame_id == expected else [f"IMU frame is {msg.header.frame_id!r}, expected {expected!r}"]
        self.input_state["imu"] = "ready" if not problems else "error"
        self._received_at["imu"] = time.monotonic()
        self._replace_input_errors("imu", problems)
        self._refresh_phase()

    def _on_odom(self, msg: Any) -> None:
        if not self._settings or self.process is None or self.process.poll() is not None:
            return
        expected_parent = "odom_lidar"
        expected_child = self._settings["lidar_frame"]
        problems = [] if (msg.header.frame_id == expected_parent and msg.child_frame_id == expected_child) else [
            f"GLIM odometry frames are {msg.header.frame_id!r}->{msg.child_frame_id!r}, expected {expected_parent!r}->{expected_child!r}"]
        self.input_state["odometry"] = "ready" if not problems else "error"
        self._received_at["odometry"] = time.monotonic()
        self._replace_input_errors("odometry", problems)
        self._refresh_phase()

    def _replace_input_errors(self, group: str, values: list[str]) -> None:
        self.input_state["errors"] = [e for e in self.input_state["errors"] if not e.startswith(group + ":")]
        self.input_state["errors"].extend(group + ": " + e for e in values)

    def _refresh_phase(self) -> None:
        if self.phase in ("stopping", "stopped", "failed", "idle"):
            return
        if self._settings and time.monotonic()-self._received_at.get("clock", 0) > 2.0:
            self._replace_input_errors("clock", ["Clock status is stale or missing"])
        self.phase, self.input_state = mapping_phase(
            self.input_state, self.input_state["errors"], self._received_at)

    def stop(self, wait: bool = False, timeout: float = 45.0) -> None:
        """Request graceful graph save. Default returns immediately for HTTP callers."""
        process = self.process
        if process is None:
            return
        if process.poll() is None and self.phase != "stopping":
            self.phase = "stopping"
            process.send_signal(signal.SIGINT)
            import threading
            self._stop_thread = threading.Thread(target=self._finish_process, args=(timeout,), daemon=True)
            self._stop_thread.start()
        if wait:
            thread = getattr(self, "_stop_thread", None)
            if thread:
                thread.join(timeout + 12)
            if self.phase == "stopping":
                raise TimeoutError("GLIM is still saving its session; check status before retrying")
            if self.phase == "failed":
                raise RuntimeError(f"GLIM save failed; see {self.log_path}")

    def _finish_process(self, timeout: float) -> None:
        process = self.process
        if process is None:
            return
        try:
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            if self.log:
                self.log.close()
                self.log = None
            if process.returncode != 0:
                self.phase = "failed"
                self.active_backend = None
                return
            output = self.map_output_directory
            if not output or not saved_glim_map_complete(output):
                self.phase = "failed"
                self.active_backend = None
                return
            self.phase = "stopped"
            self.active_backend = None
        except Exception:
            self.phase = "failed"
            self.active_backend = None

    def status(self) -> str:
        self._refresh_phase()
        if self.process and self.process.poll() is not None and self.phase not in ("failed", "idle", "stopped", "stopping"):
            self.phase = "failed"
            self.active_backend = None
        return self.phase

    def close(self, timeout: float = 45.0) -> None:
        """Finalize the session on application shutdown and wait for native graph files."""
        self.stop(wait=True, timeout=timeout)
