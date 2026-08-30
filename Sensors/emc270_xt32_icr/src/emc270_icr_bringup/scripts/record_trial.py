#!/usr/bin/env python3
"""Record one labelled EMC-270 motion trial and an auditable manifest."""

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import pathlib
import platform
import shutil
import signal
import subprocess
import sys

import yaml


TOPICS = (
    "/lidar_points",
    "/kiss/odometry",
    "/imu/telemetry",
    "/icr/fast",
    "/icr/smoothed",
    "/icr/diagnostics",
    "/diagnostics",
    "/lidar_packets_loss",
    "/lidar_ptp",
    "/tf",
    "/tf_static",
)
YAW_BANDS = ("0.15-0.25", "0.30-0.45", "0.50-0.70")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--profile", required=True,
                        choices=("no_load", "representative_load"))
    parser.add_argument("--load-kg", required=True, type=float)
    parser.add_argument("--yaw-band", required=True, choices=YAW_BANDS)
    parser.add_argument("--direction", required=True, choices=("cw", "ccw"))
    parser.add_argument("--repeat", required=True, type=int, choices=(1, 2, 3))
    parser.add_argument("--front-pressure-kpa", required=True, type=float)
    parser.add_argument("--rear-pressure-kpa", required=True, type=float)
    parser.add_argument("--fixture-config", required=True)
    parser.add_argument("--hesai-config", required=True)
    parser.add_argument("--storage-id", default="mcap", choices=("mcap", "sqlite3"))
    parser.add_argument("--notes", default="")
    return parser.parse_args()


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def checked_file(path, label):
    resolved = os.path.realpath(path)
    if not os.path.isabs(path) or not os.path.isfile(resolved):
        raise ValueError(f"{label} must be an existing absolute file: {path}")
    return resolved


def contains_required(value):
    if isinstance(value, str):
        return "REQUIRED" in value
    if isinstance(value, dict):
        return any(contains_required(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_required(item) for item in value)
    return False


def find_correction_files(value):
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"correction_file_path", "firetimes_path"} and item:
                found.append(item)
            else:
                found.extend(find_correction_files(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(find_correction_files(item))
    return found


def validate_transform(transform, label):
    if not isinstance(transform, dict):
        raise ValueError(f"{label} must be an object")
    translation = transform.get("translation_m")
    rotation = transform.get("rotation_rpy_rad")
    if (not isinstance(translation, list) or len(translation) != 3 or
            not isinstance(rotation, list) or len(rotation) != 3 or
            not all(isinstance(value, (int, float)) and math.isfinite(value)
                    for value in translation + rotation)):
        raise ValueError(f"{label} must contain finite three-element translation and RPY")
    if any(abs(float(value)) > math.pi for value in rotation):
        raise ValueError(f"{label} RPY must be in radians within [-pi, pi]")
    return translation


def validate_fixture_config(config):
    if not isinstance(config, dict):
        raise ValueError("fixture config root must be an object")
    frames = config.get("frames")
    inspection = config.get("inspection")
    if not isinstance(frames, dict) or not isinstance(inspection, dict):
        raise ValueError("fixture config requires frames and inspection objects")
    native_translation = validate_transform(
        frames.get("xt32_to_native"), "frames.xt32_to_native")
    validate_transform(frames.get("xt32_to_imu"), "frames.xt32_to_imu")
    if math.sqrt(sum(float(value) ** 2 for value in native_translation)) > 1.0e-6:
        raise ValueError("xt32_link and hesai_lidar_native must share one geometric origin")
    horizontal = inspection.get("horizontal_origin_tolerance_m")
    angular = inspection.get("axis_angle_tolerance_rad")
    if (not isinstance(horizontal, (int, float)) or not math.isfinite(horizontal) or
            not 0.0 <= horizontal <= 0.002):
        raise ValueError("fixture horizontal tolerance must be within 0..0.002 m")
    if (not isinstance(angular, (int, float)) or not math.isfinite(angular) or
            not 0.0 <= angular <= 0.003491):
        raise ValueError("fixture axis-angle tolerance must be within 0..0.003491 rad")


def validate_hesai_config(config):
    if not isinstance(config, dict):
        raise ValueError("Hesai config root must be an object")
    lidars = config.get("lidar")
    if not isinstance(lidars, list) or len(lidars) != 1 or not isinstance(lidars[0], dict):
        raise ValueError("Hesai config must contain exactly one lidar")
    driver = lidars[0].get("driver", {})
    ros = lidars[0].get("ros", {})
    if not isinstance(driver, dict) or not isinstance(ros, dict):
        raise ValueError("Hesai lidar requires driver and ros objects")
    for key, expected in {
            "source_type": 1,
            "use_timestamp_type": 0,
            "transform_flag": False,
            "distance_correction_flag": True,
            "frame_frequency": 20.0,
    }.items():
        if driver.get(key) != expected:
            raise ValueError(f"Hesai {key} must be {expected!r}")
    if (ros.get("ros_frame_id") != "hesai_lidar_native" or
            ros.get("ros_send_point_cloud_topic") != "/lidar_points" or
            ros.get("send_point_cloud_ros") is not True):
        raise ValueError("Hesai ROS output must be /lidar_points in hesai_lidar_native")
    udp = driver.get("lidar_udp_type", {})
    if not isinstance(udp, dict):
        raise ValueError("Hesai lidar_udp_type must be an object")
    for key in ("device_ip_address", "host_ip_address"):
        if not isinstance(udp.get(key), str) or not udp[key]:
            raise ValueError(f"Hesai {key} is required")
    for key in ("correction_file_path", "firetimes_path"):
        path = udp.get(key)
        if not isinstance(path, str):
            raise ValueError(f"Hesai {key} must be an absolute file path")
        checked_file(path, f"Hesai {key}")


def git_state():
    try:
        root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], check=True,
            text=True, capture_output=True).stdout.strip()
        commit = subprocess.run(
            ["git", "-C", root, "rev-parse", "HEAD"], check=True,
            text=True, capture_output=True).stdout.strip()
        dirty = bool(subprocess.run(
            ["git", "-C", root, "status", "--porcelain"], check=True,
            text=True, capture_output=True).stdout.strip())
        return {"root": root, "commit": commit, "dirty": dirty}
    except (FileNotFoundError, subprocess.CalledProcessError):
        return {"root": None, "commit": None, "dirty": None}


def write_manifest(path, manifest):
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    os.replace(temporary, path)


def validate(args):
    if not os.path.isabs(args.output_root):
        raise ValueError("output-root must be absolute")
    if not 230.0 <= args.front_pressure_kpa <= 250.0:
        raise ValueError("front pressure must be within 230-250 kPa")
    if not 200.0 <= args.rear_pressure_kpa <= 220.0:
        raise ValueError("rear pressure must be within 200-220 kPa")
    if args.profile == "no_load" and args.load_kg != 0.0:
        raise ValueError("no_load requires --load-kg 0")
    if args.profile == "representative_load" and args.load_kg <= 0.0:
        raise ValueError("representative_load requires a positive secured load")
    if shutil.which("ros2") is None:
        raise ValueError("ros2 is not available; source the ROS 2 Jazzy workspace")


def main():
    args = parse_args()
    try:
        from ament_index_python.packages import (get_package_prefix,
                                                 get_package_share_directory)
        validate(args)
        fixture = checked_file(args.fixture_config, "fixture-config")
        hesai = checked_file(args.hesai_config, "hesai-config")
        with open(fixture, encoding="utf-8") as stream:
            fixture_yaml = yaml.safe_load(stream)
        with open(hesai, encoding="utf-8") as stream:
            hesai_yaml = yaml.safe_load(stream)
        if contains_required(fixture_yaml) or contains_required(hesai_yaml):
            raise ValueError("configuration still contains REQUIRED placeholders")
        validate_fixture_config(fixture_yaml)
        validate_hesai_config(hesai_yaml)
        correction_paths = sorted(set(find_correction_files(hesai_yaml)))
        corrections = []
        for path in correction_paths:
            resolved = checked_file(path, "Hesai correction/firetime file")
            corrections.append({"path": resolved, "sha256": sha256(resolved)})

        bringup_share = get_package_share_directory("emc270_icr_bringup")
        bringup_prefix = get_package_prefix("emc270_icr_bringup")
        version_manifest = checked_file(
            os.path.join(bringup_share, "config", "software_versions.yaml"),
            "software version manifest")
        with open(version_manifest, encoding="utf-8") as stream:
            pinned_versions = yaml.safe_load(stream)

        binary_artifacts = []
        for package, executable in (
                ("emc270_icr_estimator", "icr_estimator_node"),
                ("adi_imu_tr_driver_ros2", "adis_rcv_bin_node"),
                ("kiss_icp", "kiss_icp_node"),
                ("hesai_ros_driver", "hesai_ros_driver_node")):
            path = checked_file(
                os.path.join(get_package_prefix(package), "lib", package, executable),
                f"{package} executable")
            binary_artifacts.append(
                {"package": package, "path": path, "sha256": sha256(path)})

        bringup_artifacts = []
        for path in (
                os.path.join(bringup_share, "config", "estimator.yaml"),
                os.path.join(bringup_share, "config", "imu.yaml"),
                os.path.join(bringup_share, "config", "kiss_icp.yaml"),
                os.path.join(bringup_share, "launch", "icr_live.launch.py"),
                os.path.join(bringup_share, "launch", "icr_replay.launch.py"),
                os.path.join(bringup_prefix, "lib", "emc270_icr_bringup",
                             "record_trial.py")):
            resolved = checked_file(path, "installed bringup artifact")
            bringup_artifacts.append(
                {"path": resolved, "sha256": sha256(resolved)})
    except (ImportError, ValueError, OSError, yaml.YAMLError) as error:
        raise SystemExit(str(error))

    started = dt.datetime.now(dt.timezone.utc)
    timestamp = started.strftime("%Y%m%dT%H%M%SZ")
    trial_name = (f"{timestamp}_{args.profile}_{args.yaw_band}_{args.direction}_"
                  f"r{args.repeat}")
    trial_dir = os.path.join(os.path.realpath(args.output_root), trial_name)
    try:
        pathlib.Path(args.output_root).mkdir(parents=True, exist_ok=True)
        pathlib.Path(trial_dir).mkdir()
    except FileExistsError:
        raise SystemExit(f"refusing to overwrite existing trial: {trial_dir}")

    bag_dir = os.path.join(trial_dir, "bag")
    command = ["ros2", "bag", "record", "--storage", args.storage_id,
               "--output", bag_dir, *TOPICS]
    manifest = {
        "schema_version": 1,
        "status": "RECORDING",
        "trial": {
            "profile": args.profile,
            "secured_load_kg": args.load_kg,
            "yaw_band_rad_s": args.yaw_band,
            "direction": args.direction,
            "repeat": args.repeat,
            "planned_complete_rotations": 2,
            "front_pressure_kpa": args.front_pressure_kpa,
            "rear_pressure_kpa": args.rear_pressure_kpa,
            "notes": args.notes,
        },
        "started_utc": started.isoformat(),
        "ended_utc": None,
        "host": {"platform": platform.platform(),
                 "ros_distro": os.environ.get("ROS_DISTRO")},
        "software": {
            "pinned_dependencies": pinned_versions,
            "version_manifest_sha256": sha256(version_manifest),
            "binary_artifacts": binary_artifacts,
            "bringup_artifacts": bringup_artifacts,
            "invocation_working_tree": git_state(),
        },
        "inputs": {
            "fixture_config": {"path": fixture, "sha256": sha256(fixture)},
            "hesai_config": {"path": hesai, "sha256": sha256(hesai)},
            "correction_files": corrections,
        },
        "topics": list(TOPICS),
        "bag": {"path": bag_dir, "storage_id": args.storage_id},
        "command": command,
        "return_code": None,
        "stop_reason": None,
    }
    manifest_path = os.path.join(trial_dir, "trial_manifest.json")
    write_manifest(manifest_path, manifest)
    print(f"recording {trial_dir}", flush=True)

    try:
        process = subprocess.Popen(command)
    except OSError as error:
        manifest["ended_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
        manifest["status"] = "FAILED"
        manifest["stop_reason"] = f"recorder_start_failed: {error}"
        write_manifest(manifest_path, manifest)
        raise SystemExit(f"failed to start rosbag recorder: {error}")
    interrupted = False
    try:
        return_code = process.wait()
    except KeyboardInterrupt:
        interrupted = True
        process.send_signal(signal.SIGINT)
        return_code = process.wait()

    manifest["ended_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    manifest["return_code"] = return_code
    manifest["stop_reason"] = "operator_sigint" if interrupted else "recorder_exit"
    if return_code == 0:
        manifest["status"] = "COMPLETE"
    elif interrupted:
        manifest["status"] = "INTERRUPTED"
    else:
        manifest["status"] = "FAILED"
    write_manifest(manifest_path, manifest)
    print(f"{manifest['status']}: {manifest_path}")
    return 0 if return_code == 0 else return_code


if __name__ == "__main__":
    sys.exit(main())
