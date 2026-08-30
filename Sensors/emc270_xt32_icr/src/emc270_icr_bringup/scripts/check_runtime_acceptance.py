#!/usr/bin/env python3
"""Evaluate the latency gates recorded on /icr/diagnostics."""

import argparse
import hashlib
import json
import math
import os


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bag", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--topic", default="/icr/diagnostics")
    parser.add_argument("--storage-id", default="mcap", choices=("mcap", "sqlite3"))
    parser.add_argument("--manifest",
                        help="defaults to trial_manifest.json beside the bag directory")
    parser.add_argument("--minimum-samples", type=int, default=20)
    return parser.parse_args()


def as_float(values, key):
    try:
        value = float(values[key])
    except (KeyError, TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def main():
    args = parse_args()
    if not os.path.isabs(args.bag) or not os.path.exists(args.bag):
        raise SystemExit(f"bag must be an existing absolute path: {args.bag}")
    if args.minimum_samples < 1:
        raise SystemExit("minimum-samples must be positive")
    manifest_path = args.manifest or os.path.join(
        os.path.dirname(os.path.realpath(args.bag)), "trial_manifest.json")
    if not os.path.isfile(manifest_path):
        raise SystemExit(f"completed trial manifest not found: {manifest_path}")
    try:
        with open(manifest_path, encoding="utf-8") as stream:
            manifest = json.load(stream)
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"invalid trial manifest: {error}")
    if not isinstance(manifest, dict):
        raise SystemExit("trial manifest root must be an object")
    recorded_bag = manifest.get("bag", {})
    if (manifest.get("schema_version") != 1 or manifest.get("status") != "COMPLETE" or
            os.path.realpath(recorded_bag.get("path", "")) != os.path.realpath(args.bag) or
            recorded_bag.get("storage_id") != args.storage_id):
        raise SystemExit("trial manifest is incomplete or does not match the requested bag")
    with open(manifest_path, "rb") as stream:
        manifest_hash = hashlib.sha256(stream.read()).hexdigest()
    try:
        import rosbag2_py
        from rclpy.serialization import deserialize_message
        from rosidl_runtime_py.utilities import get_message
    except ImportError as error:
        raise SystemExit(
            "Run inside the sourced ROS 2 Jazzy workspace: " + str(error))

    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=args.bag, storage_id=args.storage_id),
        rosbag2_py.ConverterOptions(input_serialization_format="",
                                    output_serialization_format=""),
    )
    types = {item.name: item.type for item in reader.get_all_topics_and_types()}
    if args.topic not in types:
        raise SystemExit(f"topic {args.topic} not present in bag")
    message_type = get_message(types[args.topic])
    latest = None
    while reader.has_next():
        topic, serialized, _ = reader.read_next()
        if topic != args.topic:
            continue
        message = deserialize_message(serialized, message_type)
        for status in message.status:
            values = {item.key: item.value for item in status.values}
            if "fast_scan_end_to_publish_p95_ms" in values:
                latest = values

    if latest is None:
        raise SystemExit("no ICR estimator metrics found in diagnostics")
    samples = int(float(latest.get("processing_sample_count", "0")))
    latency_samples = int(float(latest.get(
        "fast_scan_end_latency_sample_count", "0")))
    fast_p95 = as_float(latest, "fast_scan_end_to_publish_p95_ms")
    smooth_p95 = as_float(latest, "smoothed_processing_p95_ms")
    time_domain = latest.get("point_time_domain_compatible", "False").lower() == "true"
    measurement_valid = (samples >= args.minimum_samples and
                         latency_samples >= args.minimum_samples and
                         fast_p95 is not None and smooth_p95 is not None and
                         time_domain)
    passed = measurement_valid and fast_p95 < 100.0 and smooth_p95 < 200.0
    report = {
        "classification": ("RUNTIME_PASS" if passed else
                           "RUNTIME_FAIL" if measurement_valid else
                           "RUNTIME_MEASUREMENT_INVALID"),
        "trial_manifest_sha256": manifest_hash,
        "measurement_valid": measurement_valid,
        "processing_sample_count": samples,
        "fast_latency_sample_count": latency_samples,
        "fast_scan_end_to_publish_p95_ms": fast_p95,
        "fast_limit_ms_exclusive": 100.0,
        "smoothed_processing_p95_ms": smooth_p95,
        "smoothed_limit_ms_exclusive": 200.0,
        "point_time_domain_compatible": time_domain,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    print(report["classification"])
    print(args.output)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
