import importlib.util
import pathlib
import unittest


SCRIPT = pathlib.Path(__file__).parents[1] / "scripts" / "compare_icr_csv.py"
SPEC = importlib.util.spec_from_file_location("compare_icr", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def row(x_m):
    return {
        "profile": "no_load",
        "yaw_band": "0.30-0.45",
        "direction": "ccw",
        "repeat": "1",
        "source_mask": "1",
        "trial_manifest_sha256": "MISSING_ALLOWED",
        "secured_load_kg": "UNKNOWN",
        "fixture_config_sha256": "MISSING_ALLOWED",
        "hesai_config_sha256": "MISSING_ALLOWED",
        "correction_bundle_sha256": "MISSING_ALLOWED",
        "software_version_manifest_sha256": "MISSING_ALLOWED",
        "software_artifact_bundle_sha256": "MISSING_ALLOWED",
        "time_s": "10.0",
        "x_m": str(x_m),
        "y_m": "-0.2",
        "cov_xx": "1e-6",
        "cov_xy": "0.0",
        "cov_yx": "0.0",
        "cov_yy": "1e-6",
        "yaw_rate_rad_s": "0.35",
        "fit_rms_m": "0.001",
        "condition_number": "10.0",
    }


class CompareIcrCsvTest(unittest.TestCase):
    def test_pass_and_fail(self):
        passed = MODULE.compare([row(0.3)], [row(0.3 + 1e-12)], 1e-10)
        self.assertEqual(passed["classification"], "DETERMINISTIC_PASS")
        failed = MODULE.compare([row(0.3)], [row(0.301)], 1e-10)
        self.assertEqual(failed["classification"], "DETERMINISTIC_FAIL")

    def test_row_count_mismatch_fails(self):
        report = MODULE.compare([row(0.3)], [], 1e-10)
        self.assertEqual(report["classification"], "DETERMINISTIC_FAIL")

    def test_two_empty_inputs_fail(self):
        report = MODULE.compare([], [], 1e-10)
        self.assertEqual(report["classification"], "DETERMINISTIC_FAIL")


if __name__ == "__main__":
    unittest.main()
