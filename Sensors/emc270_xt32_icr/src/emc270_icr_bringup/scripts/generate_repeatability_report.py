#!/usr/bin/env python3
"""Generate repeatability PASS/FAIL JSON and Markdown from labelled ICR CSVs."""

import argparse
import csv
import itertools
import json
import math
import os
import random
import re
import statistics


CHI_SQUARE_2D_95 = 5.991
PROFILES = ("no_load", "representative_load")
YAW_BANDS = ("0.15-0.25", "0.30-0.45", "0.50-0.70")
DIRECTIONS = ("cw", "ccw")
EXPECTED_CONDITIONS = {
    (profile, yaw_band, direction)
    for profile in PROFILES
    for yaw_band in YAW_BANDS
    for direction in DIRECTIONS
}


def percentile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        return math.inf
    position = fraction * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (position - lower) * (ordered[upper] - ordered[lower])


def coordinate_median(points):
    return (statistics.median(point[0] for point in points),
            statistics.median(point[1] for point in points))


def distance(lhs, rhs):
    return math.hypot(lhs[0] - rhs[0], lhs[1] - rhs[1])


def finite_or_none(value):
    return value if math.isfinite(value) else None


def covariance_radius_95(row):
    xx = float(row["cov_xx"])
    xy = 0.5 * (float(row["cov_xy"]) + float(row["cov_yx"]))
    yy = float(row["cov_yy"])
    if not all(math.isfinite(value) for value in (xx, xy, yy)):
        return math.inf
    discriminant = max(0.0, (xx - yy) ** 2 + 4.0 * xy * xy)
    largest = 0.5 * (xx + yy + math.sqrt(discriminant))
    smallest = 0.5 * (xx + yy - math.sqrt(discriminant))
    if not math.isfinite(largest) or largest < 0.0 or smallest < -1.0e-15:
        return math.inf
    return math.sqrt(CHI_SQUARE_2D_95 * largest)


def bootstrap_radius(points, iterations, rng):
    centre = coordinate_median(points)
    radii = []
    for _ in range(iterations):
        draw = [rng.choice(points) for _ in points]
        radii.append(distance(coordinate_median(draw), centre))
    return percentile(radii, 0.95)


def integrated_yaw(samples, maximum_gap_s):
    ordered = sorted(samples, key=lambda sample: sample["time_s"])
    total = 0.0
    for previous, current in zip(ordered, ordered[1:]):
        delta_time = current["time_s"] - previous["time_s"]
        if not 0.0 < delta_time <= maximum_gap_s:
            continue
        total += 0.5 * (abs(previous["yaw_rate_rad_s"]) +
                       abs(current["yaw_rate_rad_s"])) * delta_time
    return total


def read_rows(paths):
    rows = []
    seen_paths = set()
    seen_samples = set()
    manifest_labels = {}
    required = {
        "profile", "yaw_band", "direction", "repeat", "time_s", "x_m", "y_m",
        "cov_xx", "cov_xy", "cov_yx", "cov_yy",
        "yaw_rate_rad_s", "fit_rms_m", "condition_number", "source_mask",
        "trial_manifest_sha256",
        "secured_load_kg", "fixture_config_sha256", "hesai_config_sha256",
        "correction_bundle_sha256",
        "software_version_manifest_sha256",
        "software_artifact_bundle_sha256",
    }
    for path in paths:
        resolved_path = os.path.realpath(path)
        if resolved_path in seen_paths:
            raise ValueError(f"duplicate CSV input: {path}")
        seen_paths.add(resolved_path)
        with open(path, newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if not required.issubset(reader.fieldnames or []):
                missing = sorted(required - set(reader.fieldnames or []))
                raise ValueError(f"{path} missing columns: {missing}")
            for row in reader:
                row["repeat"] = int(row["repeat"])
                if row["repeat"] not in (1, 2, 3):
                    raise ValueError(f"{path} repeat must be 1, 2, or 3")
                row["x_m"] = float(row["x_m"])
                row["y_m"] = float(row["y_m"])
                row["time_s"] = float(row["time_s"])
                row["yaw_rate_rad_s"] = float(row["yaw_rate_rad_s"])
                row["fit_rms_m"] = float(row["fit_rms_m"])
                row["condition_number"] = float(row["condition_number"])
                row["source_mask"] = int(row["source_mask"])
                if not all(math.isfinite(row[field])
                           for field in ("x_m", "y_m", "time_s", "yaw_rate_rad_s",
                                         "fit_rms_m", "condition_number")):
                    raise ValueError(f"{path} contains a non-finite motion sample")
                if row["fit_rms_m"] < 0.0 or row["condition_number"] < 1.0:
                    raise ValueError(f"{path} contains an invalid fit metric")
                if not re.fullmatch(r"[0-9a-f]{64}", row["trial_manifest_sha256"]):
                    raise ValueError(f"{path} lacks a valid trial manifest hash")
                labels = (row["profile"], row["yaw_band"], row["direction"], row["repeat"])
                previous_labels = manifest_labels.setdefault(
                    row["trial_manifest_sha256"], labels)
                if previous_labels != labels:
                    raise ValueError(f"{path} reuses a trial manifest across condition labels")
                sample_key = (row["trial_manifest_sha256"], row["time_s"])
                if sample_key in seen_samples:
                    raise ValueError(f"{path} repeats a previously imported trial sample")
                seen_samples.add(sample_key)
                row["secured_load_kg"] = float(row["secured_load_kg"])
                if not math.isfinite(row["secured_load_kg"]):
                    raise ValueError(f"{path} contains a non-finite secured load")
                for field in ("fixture_config_sha256", "hesai_config_sha256",
                              "correction_bundle_sha256",
                              "software_version_manifest_sha256",
                              "software_artifact_bundle_sha256"):
                    if not re.fullmatch(r"[0-9a-f]{64}", row[field]):
                        raise ValueError(f"{path} lacks a valid {field}")
                if not row["source_mask"] & 4:
                    raise ValueError(
                        f"{path} contains a sample without IMU acceleration validation")
                if row["profile"] not in PROFILES or row["yaw_band"] not in YAW_BANDS or \
                        row["direction"] not in DIRECTIONS:
                    raise ValueError(f"{path} has an unknown condition label")
                lower, upper = (float(item) for item in row["yaw_band"].split("-"))
                rate = row["yaw_rate_rad_s"]
                direction_matches = ((row["direction"] == "ccw" and rate > 0.0) or
                                     (row["direction"] == "cw" and rate < 0.0))
                if not direction_matches or not lower <= abs(rate) <= upper:
                    raise ValueError(f"{path} contains a sample outside its labelled yaw condition")
                row["covariance_radius_95_m"] = covariance_radius_95(row)
                rows.append(row)
    return rows


def analyse(rows, threshold, iterations, seed,
            expected_conditions=EXPECTED_CONDITIONS,
            minimum_samples_per_repeat=20,
            minimum_integrated_yaw_per_repeat_rad=4.0 * math.pi,
            maximum_integration_gap_s=0.20):
    grouped = {}
    for row in rows:
        key = (row["profile"], row["yaw_band"], row["direction"])
        grouped.setdefault(key, {}).setdefault(row["repeat"], []).append(row)

    no_load_values = {row["secured_load_kg"] for row in rows
                      if row["profile"] == "no_load"}
    loaded_values = {row["secured_load_kg"] for row in rows
                     if row["profile"] == "representative_load"}
    configuration_consistent = (
        no_load_values.issubset({0.0}) and
        len(loaded_values) <= 1 and
        all(value > 0.0 for value in loaded_values) and
        len({row["fixture_config_sha256"] for row in rows}) <= 1 and
        len({row["hesai_config_sha256"] for row in rows}) <= 1 and
        len({row["correction_bundle_sha256"] for row in rows}) <= 1
        and len({row["software_version_manifest_sha256"] for row in rows}) <= 1
        and len({row["software_artifact_bundle_sha256"] for row in rows}) <= 1
    )

    rng = random.Random(seed)
    conditions = []
    for key in sorted(grouped):
        repeats = grouped[key]
        repeat_ids_complete = set(repeats) == {1, 2, 3}
        repeat_medians = []
        samples_per_repeat = []
        manifest_hashes_by_repeat = []
        integrated_yaw_by_repeat = []
        sample_count = 0
        covariance_radii = []
        for repeat_id in sorted(repeats):
            samples = repeats[repeat_id]
            sample_count += len(samples)
            samples_per_repeat.append(len(samples))
            hashes = {sample["trial_manifest_sha256"] for sample in samples}
            manifest_hashes_by_repeat.append(hashes)
            integrated_yaw_by_repeat.append(
                integrated_yaw(samples, maximum_integration_gap_s))
            covariance_radii.extend(sample["covariance_radius_95_m"] for sample in samples)
            repeat_medians.append(coordinate_median(
                [(sample["x_m"], sample["y_m"]) for sample in samples]))
        pairwise = [distance(lhs, rhs)
                    for lhs, rhs in itertools.combinations(repeat_medians, 2)]
        maximum_pairwise = max(pairwise, default=math.inf)
        reported_radius_p95 = percentile(covariance_radii, 0.95)
        bootstrap = (bootstrap_radius(repeat_medians, iterations, rng)
                     if len(repeat_medians) >= 3 else math.inf)
        enough_samples = (repeat_ids_complete and
                          min(samples_per_repeat, default=0) >= minimum_samples_per_repeat)
        rotation_coverage_complete = (
            repeat_ids_complete and
            min(integrated_yaw_by_repeat, default=0.0) >=
            minimum_integrated_yaw_per_repeat_rad)
        manifest_traceable = (repeat_ids_complete and
                              all(len(hashes) == 1 for hashes in manifest_hashes_by_repeat) and
                              len(set().union(*manifest_hashes_by_repeat)) == 3)
        passed = (enough_samples and rotation_coverage_complete and manifest_traceable and
                  reported_radius_p95 <= threshold and
                  bootstrap <= threshold and
                  maximum_pairwise <= threshold)
        conditions.append({
            "profile": key[0],
            "yaw_band": key[1],
            "direction": key[2],
            "repeat_count": len(repeat_medians),
            "repeat_ids_complete": repeat_ids_complete,
            "minimum_samples_per_repeat": min(samples_per_repeat, default=0),
            "sample_count_gate": minimum_samples_per_repeat,
            "minimum_integrated_yaw_per_repeat_rad": min(
                integrated_yaw_by_repeat, default=0.0),
            "integrated_yaw_gate_rad": minimum_integrated_yaw_per_repeat_rad,
            "rotation_coverage_complete": rotation_coverage_complete,
            "manifest_traceable": manifest_traceable,
            "valid_sample_count": sample_count,
            "median_x_m": coordinate_median(repeat_medians)[0],
            "median_y_m": coordinate_median(repeat_medians)[1],
            "reported_covariance_radius_p95_m": finite_or_none(reported_radius_p95),
            "repeat_bootstrap_radius_95_m": finite_or_none(bootstrap),
            "maximum_pairwise_repeat_median_m": finite_or_none(maximum_pairwise),
            "result": "REPEATABILITY_PASS" if passed else "REPEATABILITY_FAIL",
        })
    present = set(grouped)
    missing = sorted(set(expected_conditions) - present)
    unexpected = sorted(present - set(expected_conditions))
    if unexpected:
        raise ValueError(f"unexpected condition labels: {unexpected}")
    overall_pass = (bool(conditions) and not missing and configuration_consistent and
                    all(item["result"] == "REPEATABILITY_PASS" for item in conditions))
    return {
        "classification": "REPEATABILITY_PASS" if overall_pass else "REPEATABILITY_FAIL",
        "absolute_accuracy": "UNKNOWN",
        "physical_rear_axle_centre": "UNKNOWN",
        "floor_z": "UNKNOWN",
        "threshold_m": threshold,
        "minimum_integrated_yaw_per_repeat_rad": minimum_integrated_yaw_per_repeat_rad,
        "expected_condition_count": len(expected_conditions),
        "present_condition_count": len(present),
        "missing_conditions": [
            {"profile": item[0], "yaw_band": item[1], "direction": item[2]}
            for item in missing
        ],
        "configuration_consistent": configuration_consistent,
        "representative_load_kg": (next(iter(loaded_values))
                                   if len(loaded_values) == 1 else None),
        "conditions": conditions,
    }


def markdown(report):
    def format_metres(value):
        return "UNKNOWN" if value is None else f"{value:.4f} m"

    lines = [
        "# EMC-270 / XT32 ICR repeatability report",
        "",
        f"Classification: **{report['classification']}**",
        "",
        "Absolute accuracy, physical rear-axle centre, and floor Z remain `UNKNOWN`.",
        "",
        (f"Condition coverage: {report['present_condition_count']}/"
         f"{report['expected_condition_count']}"),
        f"Configuration consistency: {report['configuration_consistent']}",
        "",
        "| Profile | Yaw band | Direction | Repeats | Samples | Min yaw coverage | Cov. p95 | Bootstrap 95% | Max repeat delta | Result |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in report["conditions"]:
        lines.append(
            f"| {item['profile']} | {item['yaw_band']} | {item['direction']} | "
            f"{item['repeat_count']} | {item['valid_sample_count']} | "
            f"{item['minimum_integrated_yaw_per_repeat_rad']:.3f} rad | "
            f"{format_metres(item['reported_covariance_radius_p95_m'])} | "
            f"{format_metres(item['repeat_bootstrap_radius_95_m'])} | "
            f"{format_metres(item['maximum_pairwise_repeat_median_m'])} | {item['result']} |")
    if report["missing_conditions"]:
        lines.extend(["", "Missing required conditions:", ""])
        for item in report["missing_conditions"]:
            lines.append(
                f"- {item['profile']} / {item['yaw_band']} / {item['direction']}")
    lines.extend([
        "",
        "The result is a repeatability classification only; it must not be relabelled as absolute accuracy.",
        "",
    ])
    return "\n".join(lines)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", nargs="+")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--threshold-m", type=float, default=0.010)
    parser.add_argument("--bootstrap-iterations", type=int, default=10000)
    parser.add_argument("--minimum-samples-per-repeat", type=int, default=20)
    parser.add_argument("--minimum-integrated-yaw-per-repeat-rad", type=float,
                        default=4.0 * math.pi)
    parser.add_argument("--maximum-integration-gap-s", type=float, default=0.20)
    parser.add_argument("--seed", type=int, default=270)
    return parser.parse_args()


def main():
    args = parse_args()
    if args.threshold_m <= 0.0:
        raise SystemExit("threshold-m must be positive")
    if args.bootstrap_iterations < 1:
        raise SystemExit("bootstrap-iterations must be positive")
    if args.minimum_samples_per_repeat < 1:
        raise SystemExit("minimum-samples-per-repeat must be positive")
    if args.minimum_integrated_yaw_per_repeat_rad <= 0.0:
        raise SystemExit("minimum-integrated-yaw-per-repeat-rad must be positive")
    if args.maximum_integration_gap_s <= 0.0:
        raise SystemExit("maximum-integration-gap-s must be positive")
    rows = read_rows(args.csv)
    report = analyse(rows, args.threshold_m, args.bootstrap_iterations, args.seed,
                     minimum_samples_per_repeat=args.minimum_samples_per_repeat,
                     minimum_integrated_yaw_per_repeat_rad=(
                         args.minimum_integrated_yaw_per_repeat_rad),
                     maximum_integration_gap_s=args.maximum_integration_gap_s)
    os.makedirs(args.output_dir, exist_ok=True)
    json_path = os.path.join(args.output_dir, "repeatability_report.json")
    markdown_path = os.path.join(args.output_dir, "repeatability_report.md")
    with open(json_path, "w", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    with open(markdown_path, "w", encoding="utf-8") as stream:
        stream.write(markdown(report))
    print(report["classification"])
    print(json_path)
    print(markdown_path)
    return 0 if report["classification"] == "REPEATABILITY_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
