#!/usr/bin/env python3
"""Export valid smoothed ICR samples from one ROS 2 bag to a labelled CSV."""

import argparse
import csv
import hashlib
import json
import os


YAW_BANDS = {
    "0.15-0.25": (0.15, 0.25),
    "0.30-0.45": (0.30, 0.45),
    "0.50-0.70": (0.50, 0.70),
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bag", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--profile", required=True,
                        choices=("no_load", "representative_load"))
    parser.add_argument("--yaw-band", required=True,
                        choices=("0.15-0.25", "0.30-0.45", "0.50-0.70"))
    parser.add_argument("--direction", required=True, choices=("cw", "ccw"))
    parser.add_argument("--repeat", required=True, type=int, choices=(1, 2, 3))
    parser.add_argument("--topic", default="/icr/smoothed")
    parser.add_argument("--storage-id", default="mcap",
                        help="mcap or sqlite3")
    parser.add_argument("--manifest",
                        help="defaults to trial_manifest.json beside the bag directory")
    parser.add_argument("--allow-missing-manifest", action="store_true",
                        help="replay commissioning only; output cannot pass repeatability")
    parser.add_argument("--allow-lidar-only", action="store_true",
                        help="commissioning only; output cannot pass the acceptance report")
    return parser.parse_args()


def main():
    args = parse_args()
    if not os.path.isabs(args.bag) or not os.path.exists(args.bag):
        raise SystemExit(f"bag must be an existing absolute path: {args.bag}")

    manifest_path = args.manifest or os.path.join(
        os.path.dirname(os.path.realpath(args.bag)), "trial_manifest.json")
    if os.path.isfile(manifest_path):
        try:
            with open(manifest_path, encoding="utf-8") as stream:
                manifest = json.load(stream)
        except (OSError, json.JSONDecodeError) as error:
            raise SystemExit(f"invalid trial manifest: {error}")
        if not isinstance(manifest, dict):
            raise SystemExit("trial manifest root must be an object")
        trial = manifest.get("trial", {})
        expected = {
            "profile": args.profile,
            "yaw_band_rad_s": args.yaw_band,
            "direction": args.direction,
            "repeat": args.repeat,
        }
        mismatched = [key for key, value in expected.items()
                      if trial.get(key) != value]
        recorded_bag = manifest.get("bag", {})
        if os.path.realpath(recorded_bag.get("path", "")) != os.path.realpath(args.bag):
            mismatched.append("bag.path")
        if recorded_bag.get("storage_id") != args.storage_id:
            mismatched.append("bag.storage_id")
        if (manifest.get("schema_version") != 1 or
                manifest.get("status") != "COMPLETE" or mismatched):
            raise SystemExit(
                f"trial manifest is incomplete or labels disagree: {mismatched}")
        with open(manifest_path, "rb") as stream:
            manifest_hash = hashlib.sha256(stream.read()).hexdigest()
        secured_load_kg = trial.get("secured_load_kg")
        inputs = manifest.get("inputs", {})
        fixture_hash = inputs.get("fixture_config", {}).get("sha256", "")
        hesai_hash = inputs.get("hesai_config", {}).get("sha256", "")
        correction_hashes = sorted(
            item.get("sha256", "") for item in inputs.get("correction_files", []))
        correction_bundle_hash = hashlib.sha256(
            json.dumps(correction_hashes, separators=(",", ":")).encode()).hexdigest()
        software_version_hash = manifest.get("software", {}).get(
            "version_manifest_sha256", "")
        software_artifact_hashes = sorted(
            item.get("sha256", "")
            for group in ("binary_artifacts", "bringup_artifacts")
            for item in manifest.get("software", {}).get(group, []))
        software_artifact_bundle_hash = hashlib.sha256(
            json.dumps(software_artifact_hashes, separators=(",", ":")).encode()).hexdigest()
    elif args.allow_missing_manifest:
        manifest_hash = "MISSING_ALLOWED"
        secured_load_kg = "UNKNOWN"
        fixture_hash = "MISSING_ALLOWED"
        hesai_hash = "MISSING_ALLOWED"
        correction_bundle_hash = "MISSING_ALLOWED"
        software_version_hash = "MISSING_ALLOWED"
        software_artifact_bundle_hash = "MISSING_ALLOWED"
    else:
        raise SystemExit(
            f"trial manifest not found: {manifest_path}; use --allow-missing-manifest only for replay")
    try:
        import rosbag2_py
        from emc270_icr_msgs.msg import IcrEstimate
        from rclpy.serialization import deserialize_message
        from rosidl_runtime_py.utilities import get_message
    except ImportError as error:
        raise SystemExit(
            "Run this exporter inside the sourced ROS 2 Jazzy workspace: " + str(error))

    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=args.bag, storage_id=args.storage_id),
        rosbag2_py.ConverterOptions(input_serialization_format="",
                                    output_serialization_format=""),
    )
    topic_types = {item.name: item.type for item in reader.get_all_topics_and_types()}
    if args.topic not in topic_types:
        raise SystemExit(f"topic {args.topic} not present in bag")
    message_type = get_message(topic_types[args.topic])

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    count = 0
    rejected_motion = 0
    rejected_without_imu_validation = 0
    lower_rate, upper_rate = YAW_BANDS[args.yaw_band]
    with open(args.output, "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "profile", "yaw_band", "direction", "repeat", "time_s",
            "trial_manifest_sha256",
            "secured_load_kg", "fixture_config_sha256", "hesai_config_sha256",
            "correction_bundle_sha256",
            "software_version_manifest_sha256",
            "software_artifact_bundle_sha256",
            "x_m", "y_m", "cov_xx", "cov_xy", "cov_yx", "cov_yy",
            "yaw_rate_rad_s", "fit_rms_m", "condition_number", "source_mask",
        ])
        writer.writeheader()
        while reader.has_next():
            topic, serialized, _ = reader.read_next()
            if topic != args.topic:
                continue
            message = deserialize_message(serialized, message_type)
            if message.status != IcrEstimate.STATUS_VALID:
                continue
            if (not args.allow_lidar_only and
                    not (message.source_mask & IcrEstimate.SOURCE_IMU_ACCEL)):
                rejected_without_imu_validation += 1
                continue
            yaw_rate = message.yaw_rate_rad_s
            direction_matches = ((args.direction == "ccw" and yaw_rate > 0.0) or
                                 (args.direction == "cw" and yaw_rate < 0.0))
            if not direction_matches or not lower_rate <= abs(yaw_rate) <= upper_rate:
                rejected_motion += 1
                continue
            writer.writerow({
                "profile": args.profile,
                "yaw_band": args.yaw_band,
                "direction": args.direction,
                "repeat": args.repeat,
                "trial_manifest_sha256": manifest_hash,
                "secured_load_kg": secured_load_kg,
                "fixture_config_sha256": fixture_hash,
                "hesai_config_sha256": hesai_hash,
                "correction_bundle_sha256": correction_bundle_hash,
                "software_version_manifest_sha256": software_version_hash,
                "software_artifact_bundle_sha256": software_artifact_bundle_hash,
                "time_s": message.header.stamp.sec + message.header.stamp.nanosec * 1e-9,
                "x_m": message.center_in_lidar.x,
                "y_m": message.center_in_lidar.y,
                "cov_xx": message.covariance_xy[0],
                "cov_xy": message.covariance_xy[1],
                "cov_yx": message.covariance_xy[2],
                "cov_yy": message.covariance_xy[3],
                "yaw_rate_rad_s": message.yaw_rate_rad_s,
                "fit_rms_m": message.fit_rms_m,
                "condition_number": message.condition_number,
                "source_mask": message.source_mask,
            })
            count += 1
    if count == 0:
        os.unlink(args.output)
        raise SystemExit("bag contained no VALID smoothed ICR samples")
    print(f"exported {count} valid samples to {args.output}")
    print(f"rejected {rejected_motion} VALID samples outside the labelled motion condition")
    print(f"rejected {rejected_without_imu_validation} samples without IMU acceleration validation")


if __name__ == "__main__":
    main()
