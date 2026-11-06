"""TR-05 start order (DEC-391): the vehicle output ND-11 / ND-12 is activated first, before ND-08, ND-07 and Nav2, with
motion_hold still true, so that neutral COMMANDs reach the ESP32 while the rest starts (the firmware enables the PC source only
on a neutral COMMAND; run-ff780d47). Runs where rclpy and nav2_msgs are installed (the VM); skipped elsewhere."""
import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    from gouda_core.autonomy_client import AutonomyClient, StepFailed
    from gouda_core.mode_manager_node import ModeManagerNode
    from gouda_core import autonomy_core as ac
except ImportError:   # no ROS / Nav2 here (the Mac)
    AutonomyClient = None


@unittest.skipIf(AutonomyClient is None, 'rclpy / nav2_msgs not installed')
class StartOrderTests(unittest.TestCase):
    def manager(self, calls, fail_vehicle=False):
        def activate(token, rec):
            calls.append('vehicle_output')
            if fail_vehicle:
                raise StepFailed('vehicle_bridge: lifecycle transition 3 failed (see its log)')
        auto = types.SimpleNamespace(new_token=lambda: 1, _token=1, activate_vehicle_output=activate,
                                     start=lambda token, mission, pose, rec: calls.append('localization_nav2_goal'))
        m = types.SimpleNamespace(_pending_start=(types.SimpleNamespace(waypoints=[1, 2, 3], set_id='s', set_revision=7, skip_allowed=[False] * 3), 'pose'),
                                  auto=auto, request_auto_record=lambda kind, tid: calls.append('auto_record'),
                                  _start_odometry=lambda rec, run_id: calls.append('odometry'),
                                  skip_settings=ac.SkipSettings(None, None, None, None))   # DEC-367: unresolved, nothing is skipped
        m._run_steps = lambda token, tid, steps: steps(lambda *a: None)
        return m

    def test_vehicle_output_is_activated_before_odometry_localization_and_nav2(self):
        calls = []
        m = self.manager(calls)
        ok, _ = ModeManagerNode._tr05_start_autonomy(m)
        self.assertTrue(ok)
        self.assertFalse(m.drive_released)            # the hold stays true: only neutral is sent while the rest starts
        m._after_transition()
        self.assertEqual(calls, ['auto_record', 'vehicle_output', 'odometry', 'localization_nav2_goal'])

    def test_a_failed_vehicle_output_stops_the_start_before_odometry(self):
        calls = []
        m = self.manager(calls, fail_vehicle=True)
        ModeManagerNode._tr05_start_autonomy(m)
        with self.assertRaises(StepFailed):
            m._after_transition()
        self.assertEqual(calls, ['auto_record', 'vehicle_output'])

    def test_start_no_longer_activates_the_vehicle_output(self):
        calls = []
        c = types.SimpleNamespace(localize=lambda *a: calls.append('localize'), _set=lambda *a: None,
                                  _vehicle_activate=lambda token: calls.append('vehicle_output') or [],
                                  manage=None, send_goal=lambda *a: calls.append('goal'))
        c._call = lambda *a: types.SimpleNamespace(success=True)
        mission = types.SimpleNamespace(map_yaml='m', mask_yaml='k', filter_base=0.0, filter_multiplier=1.0, keepout_yaml='o',
                                        keepout_sha256='h', keepout_size=(1, 1))
        AutonomyClient.start(c, 1, mission, 'pose', lambda *a: None)
        self.assertEqual(calls, ['localize', 'goal'])


if __name__ == '__main__':
    unittest.main()
