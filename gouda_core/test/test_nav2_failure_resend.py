"""DEC-437 / DEC-460 (REV-245): a failed Nav2 goal no longer pauses (TR-07) when nav2_failure_resend_wait_s (PRM-161) has a
value. The mode stays 自律走行 with motion_hold=true, and after the wait the goal is sent again from the first waypoint not yet
passed; a failed re-send is tried again after the same wait. Unchanged: TR-08, a cancelled goal, a failure during the
localization wait, and the old pause when PRM-161 has no value. Runs where rclpy and action_msgs are installed (the VM / the
simulation host); skipped elsewhere."""
import sys
import threading
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import mode_core as mc  # noqa: E402
try:
    from action_msgs.msg import GoalStatus
    from gouda_core.autonomy_client import StepFailed
    from gouda_core.mode_manager_node import ModeManagerNode
except ImportError:   # no ROS here (the Mac)
    ModeManagerNode = None

ABORTED, SUCCEEDED, CANCELED = 6, 4, 5   # action_msgs/GoalStatus (checked against the import below)
WAIT = 2.5   # a test value of PRM-161 (not the approved one)


class FakeAuto:
    def __init__(self):
        self._token = 1
        self.sent = []      # offsets of send_goal
        self.fail = []      # exceptions raised by the next send_goal calls

    def new_token(self):
        self._token += 1
        return self._token

    def send_goal(self, token, mission, offset, rec):
        self.sent.append(offset)
        if self.fail:
            raise self.fail.pop(0)


if ModeManagerNode is not None:
    class Manager:
        """The mode manager's state and the methods under test, without a ROS node."""
        _on_nav_result = ModeManagerNode._on_nav_result
        _schedule_resend = ModeManagerNode._schedule_resend
        _resend_fire = ModeManagerNode._resend_fire
        _resend_goal = ModeManagerNode._resend_goal
        _auto_pause = ModeManagerNode._auto_pause
        _update_fields = ModeManagerNode._update_fields
        _rec = ModeManagerNode._rec

        def __init__(self, wait):
            self._lock = threading.RLock()
            self.state = mc.ModeState(mode=mc.MODE_AUTONOMY, run_id='run-test', remaining_waypoints=3, current_section=1,
                                      speed_limit_application_state='applied')
            self.mission = types.SimpleNamespace(waypoints=[(0, 0, 0, 1)] * 5)
            self.next_offset = 2
            self.goal_active, self.drive_released, self.localization_waiting = True, True, False
            self.nav2_resend_wait = wait
            self._resend_run, self.nav2_resend_count = None, 0
            self._error_codes = {}
            self.auto = FakeAuto()
            self.events = []    # (event, transition_id, details)
            self.timers = []    # (wait, token) of _start_resend_timer
            self._logger = types.SimpleNamespace(warning=lambda *a: None, info=lambda *a: None)

        def get_logger(self):
            return self._logger

        def _publish_decision(self, event, tid, reason, details):
            self.events.append((event, tid, details))

        def _publish_state(self):
            pass

        def _set_state(self, new):
            self.state = new

        def _start_resend_timer(self, wait, token):
            self.timers.append((wait, token))

        def fire(self):
            wait, token = self.timers.pop(0)
            self._resend_fire(token)

        def names(self):
            return [e[0] for e in self.events]


@unittest.skipIf(ModeManagerNode is None, 'rclpy / action_msgs not installed')
class Nav2FailureResendTests(unittest.TestCase):
    def test_status_constants(self):
        self.assertEqual((GoalStatus.STATUS_ABORTED, GoalStatus.STATUS_SUCCEEDED, GoalStatus.STATUS_CANCELED), (ABORTED, SUCCEEDED, CANCELED))

    def test_failure_stays_in_autonomy_and_resends_from_next_offset_after_the_wait(self):
        m = Manager(WAIT)
        m._on_nav_result(ABORTED, 0, 'aborted')
        self.assertEqual(m.state.mode, mc.MODE_AUTONOMY, 'DEC-437: no pause')
        self.assertFalse(m.drive_released, 'motion_hold=true during the wait')
        self.assertFalse(m.goal_active)
        self.assertNotIn('automatic_pause', m.names())
        self.assertEqual(m.names(), ['nav2_goal_resend_scheduled'])
        d = m.events[0][2]
        self.assertEqual((d['resend_count'], d['wait_s'], d['failure_reason'], d['error_code']), (1, WAIT, mc.STOP_REASON_NAV2_NO_CODE, 0))
        self.assertEqual(len(m.timers), 1)
        self.assertEqual(m.timers[0][0], WAIT)
        self.assertEqual(m.auto.sent, [], 'nothing is sent before the wait')
        m.fire()
        self.assertEqual(m.auto.sent, [2], 'the goal from next_offset')
        self.assertTrue(m.goal_active)
        self.assertEqual(m.state.speed_limit_application_state, 'unknown', 'the hold is released again only at 適用中 (DEC-056)')
        self.assertEqual(m.names()[-1], 'nav2_goal_resend')
        # a second failure counts on (no limit)
        m._on_nav_result(ABORTED, 0, '')
        self.assertEqual(m.events[-1][2]['resend_count'], 2)
        m.fire()
        self.assertEqual(m.auto.sent, [2, 2])
        self.assertEqual(m.state.mode, mc.MODE_AUTONOMY)

    def test_offset_is_clamped_to_the_last_waypoint(self):
        m = Manager(WAIT); m.next_offset = 9
        m._on_nav_result(ABORTED, 0, ''); m.fire()
        self.assertEqual(m.auto.sent, [4])

    def test_a_failed_resend_is_tried_again_after_the_same_wait(self):
        m = Manager(WAIT)
        m.auto.fail = [StepFailed('Nav2 rejected the NavigateThroughPoses goal')]
        m._on_nav_result(ABORTED, 0, '')
        m.fire()
        self.assertEqual(m.state.mode, mc.MODE_AUTONOMY, 'a rejected re-send does not pause either')
        self.assertFalse(m.goal_active)
        self.assertEqual(len(m.timers), 1)
        self.assertEqual(m.timers[0][0], WAIT)
        self.assertEqual(m.events[-1][0], 'nav2_goal_resend_scheduled')
        self.assertEqual(m.events[-1][2]['resend_count'], 2)
        m.fire()
        self.assertEqual(m.auto.sent, [2, 2])
        self.assertTrue(m.goal_active)

    def test_success_still_pauses_with_tr08(self):
        m = Manager(WAIT)
        m._on_nav_result(SUCCEEDED, 0, '')
        self.assertEqual((m.state.mode, m.state.stop_reason), (mc.MODE_PAUSE, mc.STOP_REASON_GOAL_REACHED))
        self.assertEqual(m.names(), ['goal_reached'])
        self.assertEqual(m.timers, [])

    def test_cancelled_goal_is_unchanged(self):
        m = Manager(WAIT)
        m._on_nav_result(CANCELED, 0, '')
        self.assertEqual(m.state.mode, mc.MODE_AUTONOMY)
        self.assertEqual(m.names(), ['nav2_goal_ended'])
        self.assertEqual(m.timers, [])

    def test_failure_during_localization_wait_is_unchanged(self):
        m = Manager(WAIT); m.localization_waiting = True
        m._on_nav_result(ABORTED, 0, '')
        self.assertEqual(m.state.mode, mc.MODE_AUTONOMY)
        self.assertEqual(m.names(), ['nav2_goal_ended'])
        self.assertEqual(m.events[0][1], 'TR-07')
        self.assertEqual(m.timers, [])

    def test_human_pause_during_the_wait_drops_the_resend(self):
        m = Manager(WAIT)
        m._on_nav_result(ABORTED, 0, '')
        m.auto.new_token()   # TR-06 takes a new token
        m.state = mc.ModeState(**{**m.state.as_dict(), 'mode': mc.MODE_PAUSE})
        m.fire()
        self.assertEqual(m.auto.sent, [])
        self.assertEqual(m.names()[-1], 'nav2_goal_resend_dropped')
        self.assertEqual(m.state.mode, mc.MODE_PAUSE)

    def test_pause_and_resume_during_the_wait_drop_the_old_resend(self):
        m = Manager(WAIT)
        m._on_nav_result(ABORTED, 0, '')
        m.auto.new_token(); m.auto.new_token()   # TR-06 then TR-10 (its own goal): the mode is 自律走行 again
        m.fire()
        self.assertEqual(m.auto.sent, [])
        self.assertEqual(m.names()[-1], 'nav2_goal_resend_dropped')

    def test_localization_wait_during_the_wait_drops_the_resend(self):
        m = Manager(WAIT)
        m._on_nav_result(ABORTED, 0, '')
        m.auto.new_token(); m.localization_waiting = True   # _localization_wait_start
        m.fire()
        self.assertEqual(m.auto.sent, [])
        self.assertEqual(m.names()[-1], 'nav2_goal_resend_dropped')

    def test_parameter_without_a_value_keeps_the_tr07_pause(self):
        m = Manager(None)
        m._on_nav_result(ABORTED, 0, 'aborted')
        self.assertEqual((m.state.mode, m.state.stop_reason), (mc.MODE_PAUSE, mc.STOP_REASON_NAV2_NO_CODE))
        self.assertEqual(m.names(), ['automatic_pause'])
        self.assertFalse(m.drive_released)
        self.assertEqual(m.timers, [])

    def test_failure_outside_autonomy_changes_nothing(self):
        m = Manager(WAIT)
        m.state = mc.ModeState(**{**m.state.as_dict(), 'mode': mc.MODE_PAUSE})
        m._on_nav_result(ABORTED, 0, '')
        self.assertEqual(m.names(), ['nav2_result_ignored'])
        self.assertEqual(m.timers, [])


if __name__ == '__main__':
    unittest.main()
