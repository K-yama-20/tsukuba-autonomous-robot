import csv
import importlib.util
import pathlib
import tempfile
import unittest


SCRIPT = pathlib.Path(__file__).parents[1] / "scripts" / "generate_repeatability_report.py"
SPEC = importlib.util.spec_from_file_location("repeatability", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RepeatabilityReportTest(unittest.TestCase):
    def _rows(self, spread, covariance):
        rows = []
        for repeat in (1, 2, 3):
            for sample in range(20):
                rows.append({
                    "profile": "no_load",
                    "yaw_band": "0.30-0.45",
                    "direction": "ccw",
                    "repeat": repeat,
                    "time_s": repeat * 100.0 + sample * 0.05,
                    "x_m": 0.30 + repeat * spread + sample * 1e-6,
                    "y_m": -0.10 - repeat * spread,
                    "cov_xx": covariance,
                    "cov_xy": 0.0,
                    "cov_yx": 0.0,
                    "cov_yy": covariance,
                    "covariance_radius_95_m": (5.991 * covariance) ** 0.5,
                    "yaw_rate_rad_s": 0.35,
                    "fit_rms_m": 0.001,
                    "condition_number": 10.0,
                    "source_mask": 5,
                    "trial_manifest_sha256": f"{repeat:064x}",
                    "secured_load_kg": 0.0,
                    "fixture_config_sha256": "a" * 64,
                    "hesai_config_sha256": "b" * 64,
                    "correction_bundle_sha256": "c" * 64,
                    "software_version_manifest_sha256": "d" * 64,
                    "software_artifact_bundle_sha256": "e" * 64,
                })
        return rows

    def test_pass_and_fail(self):
        expected = {("no_load", "0.30-0.45", "ccw")}
        passed = MODULE.analyse(
            self._rows(0.001, 1e-6), 0.010, 1000, 270,
            expected_conditions=expected,
            minimum_integrated_yaw_per_repeat_rad=0.0)
        self.assertEqual(passed["classification"], "REPEATABILITY_PASS")
        failed = MODULE.analyse(
            self._rows(0.010, 1e-6), 0.010, 1000, 270,
            expected_conditions=expected,
            minimum_integrated_yaw_per_repeat_rad=0.0)
        self.assertEqual(failed["classification"], "REPEATABILITY_FAIL")
        self.assertEqual(failed["absolute_accuracy"], "UNKNOWN")

    def test_missing_matrix_condition_fails(self):
        incomplete = MODULE.analyse(
            self._rows(0.001, 1e-6), 0.010, 1000, 270)
        self.assertEqual(incomplete["classification"], "REPEATABILITY_FAIL")
        self.assertEqual(incomplete["present_condition_count"], 1)
        self.assertEqual(len(incomplete["missing_conditions"]), 11)

    def test_reused_manifest_or_changed_configuration_fails(self):
        expected = {("no_load", "0.30-0.45", "ccw")}
        reused = self._rows(0.001, 1e-6)
        for item in reused:
            item["trial_manifest_sha256"] = "f" * 64
        reused_report = MODULE.analyse(
            reused, 0.010, 1000, 270, expected_conditions=expected,
            minimum_integrated_yaw_per_repeat_rad=0.0)
        self.assertEqual(reused_report["classification"], "REPEATABILITY_FAIL")
        self.assertFalse(reused_report["conditions"][0]["manifest_traceable"])

        changed = self._rows(0.001, 1e-6)
        changed[-1]["fixture_config_sha256"] = "9" * 64
        changed_report = MODULE.analyse(
            changed, 0.010, 1000, 270, expected_conditions=expected,
            minimum_integrated_yaw_per_repeat_rad=0.0)
        self.assertEqual(changed_report["classification"], "REPEATABILITY_FAIL")
        self.assertFalse(changed_report["configuration_consistent"])

    def test_two_rotation_coverage_is_required(self):
        expected = {("no_load", "0.30-0.45", "ccw")}
        report = MODULE.analyse(
            self._rows(0.001, 1e-6), 0.010, 1000, 270,
            expected_conditions=expected)
        self.assertEqual(report["classification"], "REPEATABILITY_FAIL")
        self.assertFalse(report["conditions"][0]["rotation_coverage_complete"])

    def test_csv_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "bad.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["profile"])
                writer.writeheader()
            with self.assertRaises(ValueError):
                MODULE.read_rows([path])


if __name__ == "__main__":
    unittest.main()
