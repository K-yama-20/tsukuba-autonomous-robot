import json
import math

import pytest

from gouda_navigation.mapping import (
    DEFAULT_SETTINGS,
    save_mapping_settings,
    static_tf_args,
    make_glim_config,
    mapping_phase,
    saved_glim_map_complete,
    validate_mapping_settings,
)


def valid_glim_settings():
    return {
        **DEFAULT_SETTINGS,
        "backend": "glim_imu",
        "clock_policy": "host_mapped",
        "clock_evidence": "Test fixture: sensor time aligned with host",
        "extrinsic_lidar_imu": {
            "translation_m": [0.12, -0.03, 0.21],
            "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
        },
        "point_time_field": "timestamp",
        "point_time_datatype": "uint32",
        "point_time_mode": "relative",
        "point_time_unit": "nanoseconds",
        "imu_accel_unit": "m/s^2",
        "imu_gyro_unit": "rad/s",
        "imu_clock_offset_sec": 0.0,
        "lidar_clock_offset_sec": 0.0,
    }


def test_unknown_calibration_can_be_saved_as_draft_but_cannot_start_glim(tmp_path):
    unknown = {
        **DEFAULT_SETTINGS,
        "clock_policy": "unknown",
        "extrinsic_lidar_imu": None,
        "point_time_field": "unknown",
        "point_time_datatype": "unknown",
        "point_time_mode": "unknown",
        "point_time_unit": "unknown",
        "imu_accel_unit": "unknown",
        "imu_gyro_unit": "unknown",
        "imu_clock_offset_sec": None,
        "lidar_clock_offset_sec": None,
    }
    path = save_mapping_settings(unknown, tmp_path / "mapping.json")
    assert json.loads(path.read_text())["extrinsic_lidar_imu"] is None
    errors = validate_mapping_settings(unknown, require_ready=True)
    assert any("T_lidar_imu is UNKNOWN" in error for error in errors)
    assert any("point_time_field is UNKNOWN" in error for error in errors)


def test_real_sensor_defaults_match_measured_mount_and_driver_contract():
    assert DEFAULT_SETTINGS["backend"] == "glim_imu"
    assert DEFAULT_SETTINGS["extrinsic_lidar_imu"] == {
        "translation_m": [0.0, 0.0, -0.0514],
        "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
    }
    assert DEFAULT_SETTINGS["point_time_field"] == "timestamp"
    assert DEFAULT_SETTINGS["point_time_datatype"] == "float64"
    assert DEFAULT_SETTINGS["point_time_mode"] == "absolute"
    assert DEFAULT_SETTINGS["point_time_unit"] == "seconds"
    assert DEFAULT_SETTINGS["imu_accel_unit"] == "m/s^2"
    assert DEFAULT_SETTINGS["imu_gyro_unit"] == "rad/s"
    assert DEFAULT_SETTINGS["clock_policy"] == "host_mapped"
    assert DEFAULT_SETTINGS["imu_clock_offset_sec"] == 0.0
    assert DEFAULT_SETTINGS["lidar_clock_offset_sec"] == 0.0
    assert validate_mapping_settings(DEFAULT_SETTINGS, require_ready=True) == []


def test_glim_settings_require_explicit_transform_units_and_offsets():
    assert validate_mapping_settings(valid_glim_settings(), require_ready=True) == []
    cfg = valid_glim_settings()
    cfg["imu_clock_offset_sec"] = None
    cfg["point_time_unit"] = "unknown"
    errors = validate_mapping_settings(cfg, require_ready=True)
    assert any("imu_clock_offset_sec is UNKNOWN" in error for error in errors)
    assert any("point_time_unit is UNKNOWN" in error for error in errors)


def test_uint32_point_time_cannot_be_declared_seconds():
    cfg = valid_glim_settings()
    cfg["point_time_unit"] = "seconds"
    assert any("UINT32" in error for error in validate_mapping_settings(cfg, require_ready=True))


def test_calibrated_tf_args_use_inverse_transform_translation():
    cfg = valid_glim_settings()
    cfg["extrinsic_lidar_imu"] = {
        "translation_m": [1.0, 2.0, 3.0],
        "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
    }
    args = static_tf_args(cfg)
    values = {args[index]: args[index + 1] for index in range(0, len(args), 2)}
    assert [float(values[key]) for key in ("--x", "--y", "--z")] == [-1.0, -2.0, -3.0]
    assert values["--frame-id"] == "imu_link"
    assert values["--child-frame-id"] == "hesai_lidar"


def test_readiness_requires_both_sensor_streams_and_local_odometry():
    state = {"lidar": "ready", "imu": "ready", "odometry": "waiting"}
    phase, _ = mapping_phase(state, [], {"lidar": 10, "imu": 10}, now=10)
    assert phase == "processing"
    state["odometry"] = "ready"
    phase, _ = mapping_phase(state, [], {"lidar": 10, "imu": 10, "odometry": 10}, now=10)
    assert phase == "mapping"


def test_readiness_goes_stale_and_preflight_errors_block_mapping():
    state = {"lidar": "ready", "imu": "ready", "odometry": "ready"}
    phase, updated = mapping_phase(state, [], {"lidar": 0, "imu": 10, "odometry": 10}, now=3)
    assert phase == "waiting_for_sensors"
    assert updated["lidar"] == "stale"
    phase, _ = mapping_phase(state, ["LiDAR frame mismatch"], {"lidar": 10, "imu": 10, "odometry": 10}, now=10)
    assert phase == "preflight_error"


def test_generated_time_scale_respects_upstream_uint32_nanosecond_conversion(tmp_path, monkeypatch):
    from pathlib import Path
    upstream = Path('/opt/ros/jazzy/share/glim/config')
    if not upstream.is_dir():
        pytest.skip('GLIM CPU package is not installed')
    u32 = make_glim_config(valid_glim_settings(), tmp_path / 'u32', upstream)
    config = json.loads((u32 / 'config_sensors.json').read_text())
    assert config['sensors']['perpoint_time_scale'] == 1.0
    f64_settings = valid_glim_settings()
    f64_settings['point_time_datatype'] = 'float64'
    f64 = make_glim_config(f64_settings, tmp_path / 'f64', upstream)
    config = json.loads((f64 / 'config_sensors.json').read_text())
    assert config['sensors']['perpoint_time_scale'] == 1e-9


def test_static_transform_is_inverse_of_configured_lidar_from_imu():
    cfg = valid_glim_settings()
    half = math.sqrt(0.5)
    cfg['extrinsic_lidar_imu'] = {
        'translation_m': [1.0, 2.0, 3.0],
        'quaternion_xyzw': [0.0, 0.0, half, half],
    }
    args = static_tf_args(cfg)
    values = {args[index]: float(args[index + 1]) for index in range(0, len(args), 2)
              if args[index] not in ('--frame-id', '--child-frame-id')}
    assert values['--x'] == pytest.approx(-2.0)
    assert values['--y'] == pytest.approx(1.0)
    assert values['--z'] == pytest.approx(-3.0)
    assert values['--qz'] == pytest.approx(-half)
    assert values['--qw'] == pytest.approx(half)


def test_empty_native_glim_graph_is_not_marked_saved(tmp_path):
    (tmp_path / 'graph.bin').write_bytes(b'graph')
    (tmp_path / 'values.bin').write_bytes(b'values')
    (tmp_path / 'graph.txt').write_text('num_submaps: 0\nnum_all_frames: 0\n')
    assert not saved_glim_map_complete(tmp_path)
    (tmp_path / 'graph.txt').write_text('num_submaps: 1\nnum_all_frames: 4\n')
    assert saved_glim_map_complete(tmp_path)
