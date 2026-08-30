#!/usr/bin/env python3
"""Compare two replay exports and reject non-deterministic ICR output."""

import argparse
import csv
import json
import math
import os


NUMERIC_FIELDS = (
    "time_s", "x_m", "y_m", "cov_xx", "cov_xy", "cov_yx", "cov_yy",
    "yaw_rate_rad_s", "fit_rms_m", "condition_number",
)
LABEL_FIELDS = ("profile", "yaw_band", "direction", "repeat", "source_mask",
                "trial_manifest_sha256", "secured_load_kg", "fixture_config_sha256",
                "hesai_config_sha256", "correction_bundle_sha256",
                "software_version_manifest_sha256", "software_artifact_bundle_sha256")


def read(path):
    with open(path, newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def compare(lhs, rhs, tolerance):
    maximum = {field: 0.0 for field in NUMERIC_FIELDS}
    mismatches = []
    if not lhs and not rhs:
        mismatches.append("both inputs contain no rows")
    if len(lhs) != len(rhs):
        mismatches.append(f"row_count {len(lhs)} != {len(rhs)}")
    for index, (left, right) in enumerate(zip(lhs, rhs)):
        for field in LABEL_FIELDS:
            if left.get(field) != right.get(field):
                mismatches.append(f"row {index} label {field} differs")
        for field in NUMERIC_FIELDS:
            try:
                delta = abs(float(left[field]) - float(right[field]))
            except (KeyError, TypeError, ValueError):
                mismatches.append(f"row {index} invalid numeric field {field}")
                continue
            if not math.isfinite(delta):
                mismatches.append(f"row {index} non-finite delta {field}")
                continue
            maximum[field] = max(maximum[field], delta)
            if delta > tolerance:
                mismatches.append(
                    f"row {index} {field} delta {delta:.17g} > {tolerance:.17g}")
    return {
        "classification": "DETERMINISTIC_PASS" if not mismatches else "DETERMINISTIC_FAIL",
        "row_count_left": len(lhs),
        "row_count_right": len(rhs),
        "absolute_tolerance": tolerance,
        "maximum_absolute_delta": maximum,
        "mismatch_count": len(mismatches),
        "first_mismatches": mismatches[:20],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("left")
    parser.add_argument("right")
    parser.add_argument("--absolute-tolerance", type=float, default=1e-10)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.absolute_tolerance < 0.0:
        raise SystemExit("absolute tolerance must be non-negative")
    report = compare(read(args.left), read(args.right), args.absolute_tolerance)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    print(report["classification"])
    print(args.output)
    return 0 if report["classification"] == "DETERMINISTIC_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
