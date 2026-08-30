import importlib.util
import pathlib
import sys
import tempfile
import types
import unittest


if importlib.util.find_spec("yaml") is None:
    sys.modules["yaml"] = types.ModuleType("yaml")

SCRIPT = pathlib.Path(__file__).parents[1] / "scripts" / "record_trial.py"
SPEC = importlib.util.spec_from_file_location("record_trial", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RecordValidationTest(unittest.TestCase):
    def _fixture(self):
        return {
            "frames": {
                "xt32_to_native": {
                    "translation_m": [0.0, 0.0, 0.0],
                    "rotation_rpy_rad": [0.0, 0.0, 1.5708],
                },
                "xt32_to_imu": {
                    "translation_m": [0.001, -0.001, -0.05],
                    "rotation_rpy_rad": [0.0, 0.0, 0.0],
                },
            },
            "inspection": {
                "horizontal_origin_tolerance_m": 0.002,
                "axis_angle_tolerance_rad": 0.003491,
            },
        }

    def _hesai(self, correction, firetime):
        return {
            "lidar": [{
                "driver": {
                    "source_type": 1,
                    "use_timestamp_type": 0,
                    "transform_flag": False,
                    "distance_correction_flag": True,
                    "frame_frequency": 20.0,
                    "lidar_udp_type": {
                        "device_ip_address": "192.0.2.10",
                        "host_ip_address": "192.0.2.20",
                        "correction_file_path": correction,
                        "firetimes_path": firetime,
                    },
                },
                "ros": {
                    "ros_frame_id": "hesai_lidar_native",
                    "ros_send_point_cloud_topic": "/lidar_points",
                    "send_point_cloud_ros": True,
                },
            }],
        }

    def test_valid_configs_and_rejected_precision_regressions(self):
        with tempfile.TemporaryDirectory() as directory:
            correction = pathlib.Path(directory) / "correction.csv"
            firetime = pathlib.Path(directory) / "firetime.csv"
            correction.touch()
            firetime.touch()
            MODULE.validate_fixture_config(self._fixture())
            MODULE.validate_hesai_config(
                self._hesai(str(correction), str(firetime)))

            bad_fixture = self._fixture()
            bad_fixture["frames"]["xt32_to_native"]["translation_m"][0] = 0.001
            with self.assertRaises(ValueError):
                MODULE.validate_fixture_config(bad_fixture)

            bad_hesai = self._hesai(str(correction), str(firetime))
            bad_hesai["lidar"][0]["driver"]["use_timestamp_type"] = 1
            with self.assertRaises(ValueError):
                MODULE.validate_hesai_config(bad_hesai)


if __name__ == "__main__":
    unittest.main()
