"""E-4 (REV-183, DEC-393): the stop reason of a failed Nav2 goal from its error code. The rule by action and constant name runs
everywhere; the table from the real nav2_msgs constants only where nav2_msgs is installed (the VM)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import autonomy_core as ac  # noqa: E402
from gouda_core import mode_core as mc  # noqa: E402
try:
    from gouda_core.autonomy_client import error_code_table
    from nav2_msgs.action import FollowPath, ComputePathThroughPoses, ComputePathToPose
except ImportError:   # no ROS / Nav2 here (the Mac)
    error_code_table = None


class RuleTests(unittest.TestCase):
    def test_rule_by_action_and_name(self):
        self.assertIsNone(ac.stop_reason_for('FollowPath', 'NONE'))
        self.assertEqual(ac.stop_reason_for('FollowPath', 'TF_ERROR'), mc.STOP_REASON_NAV2_TF)
        self.assertEqual(ac.stop_reason_for('ComputePathThroughPoses', 'TF_ERROR'), mc.STOP_REASON_NAV2_TF)
        for n in ('PATIENCE_EXCEEDED', 'FAILED_TO_MAKE_PROGRESS', 'NO_VALID_CONTROL'):
            self.assertEqual(ac.stop_reason_for('FollowPath', n), mc.STOP_REASON_BLOCKED, n)
        self.assertEqual(ac.stop_reason_for('FollowPath', 'INVALID_PATH'), mc.STOP_REASON_CONTROLLER)
        self.assertEqual(ac.stop_reason_for('ComputePathThroughPoses', 'NO_VALID_PATH'), mc.STOP_REASON_PLAN_FAILURE)
        self.assertEqual(ac.stop_reason_for('ComputePathToPose', 'GOAL_OCCUPIED'), mc.STOP_REASON_PLAN_FAILURE)

    def test_reason_from_code(self):
        table = {7: (mc.STOP_REASON_BLOCKED, 'FollowPath.X')}
        self.assertEqual(ac.nav2_failure_reason(0, table)[0], mc.STOP_REASON_NAV2_NO_CODE)   # run-574fe6d7: no error code
        self.assertEqual(ac.nav2_failure_reason(7, table), (mc.STOP_REASON_BLOCKED, 'FollowPath.X'))
        self.assertEqual(ac.nav2_failure_reason(9, table)[0], mc.STOP_REASON_NAV2_OTHER)


@unittest.skipIf(error_code_table is None, 'nav2_msgs not installed')
class TableTests(unittest.TestCase):
    def test_real_constants(self):
        t = error_code_table()
        self.assertEqual(t[FollowPath.Result.TF_ERROR][0], mc.STOP_REASON_NAV2_TF)                     # run-ff780d47, run-cdde4c29
        self.assertEqual(t[FollowPath.Result.FAILED_TO_MAKE_PROGRESS][0], mc.STOP_REASON_BLOCKED)
        self.assertEqual(t[FollowPath.Result.PATIENCE_EXCEEDED][0], mc.STOP_REASON_BLOCKED)
        self.assertEqual(t[ComputePathThroughPoses.Result.NO_VALID_PATH][0], mc.STOP_REASON_PLAN_FAILURE)
        self.assertEqual(t[ComputePathToPose.Result.TF_ERROR][0], mc.STOP_REASON_NAV2_TF)
        self.assertNotIn(0, t)
        self.assertEqual(t[FollowPath.Result.TF_ERROR][1], 'FollowPath.TF_ERROR')


if __name__ == '__main__':
    unittest.main()
