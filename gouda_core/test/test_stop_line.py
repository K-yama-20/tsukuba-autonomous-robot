"""一時停止線 (DEC-482, REV-263): a waypoint of kind stop ends every goal, reaching it holds the robot inside 自律走行
(rule_stop_hold, stop_reason rule_stop) and the human's 再開 sends the goal from the waypoint after it.

The pure part (autonomy_core / mode_core / waypoints) runs everywhere. The node part (ModeManagerNode methods on a stub, the
pattern of test_nav2_failure_resend.py) runs where rclpy and action_msgs are installed; it is skipped on the Mac."""
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import autonomy_core as ac  # noqa: E402
from gouda_core import mode_core as mc  # noqa: E402
from gouda_core import waypoints as wpmod  # noqa: E402
try:
    from gouda_core.autonomy_client import StepFailed  # noqa: F401
    from gouda_core.mode_manager_node import ModeManagerNode
except ImportError:   # no ROS here (the Mac)
    ModeManagerNode = None

ABORTED, SUCCEEDED, CANCELED = 6, 4, 5   # action_msgs/GoalStatus (checked in test_nav2_failure_resend.py)
RADIUS = 0.7   # a test radius (the generated PRM-11 is read by the node, not this)
WAYPOINTS = [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (4.0, 0.0, 0.0), (6.0, 0.0, 0.0), (8.0, 0.0, 0.0)]


class PureTests(unittest.TestCase):
    def test_section_end_without_stop_points_is_the_last_waypoint(self):
        self.assertEqual(ac.section_end([], 0, 5), 4)
        self.assertEqual(ac.section_end([False] * 5, 2, 5), 4)

    def test_section_end_is_the_first_stop_at_or_after_the_offset(self):
        stops = [False, False, True, False, False]
        self.assertEqual([ac.section_end(stops, k, 5) for k in range(5)], [2, 2, 2, 4, 4])

    def test_two_stop_points_in_a_row(self):
        stops = [False, True, True, False, False]
        self.assertEqual([ac.section_end(stops, k, 5) for k in range(5)], [1, 1, 2, 4, 4])
        self.assertEqual([ac.held_stop_point(stops, k, 5) for k in range(5)], [1, 1, 2, None, None])

    def test_last_waypoint_stop_is_the_goal_tr08(self):
        stops = [False, False, False, False, True]
        self.assertEqual(ac.section_end(stops, 0, 5), 4)
        self.assertIsNone(ac.held_stop_point(stops, 0, 5), 'TR-08 at the last waypoint is unchanged')

    def test_goal_poses_up_to_the_end(self):
        self.assertEqual(len(ac.goal_poses(WAYPOINTS, 0)), 5, 'without end: all remaining (unchanged)')
        p = ac.goal_poses(WAYPOINTS, 1, 2)
        self.assertEqual([q[0] for q in p], [2.0, 4.0])

    def test_a_skip_cannot_jump_over_a_stop_point(self):
        # DEC-367: a skip of target k sends the goal from k + 1; that goal still ends at the stop point
        stops = [False, False, False, True, False]
        skip_allowed = [False, True, False, False, False]
        target = 1
        self.assertTrue(skip_allowed[target])
        self.assertEqual(ac.section_end(stops, target + 1, 5), 3)

    def test_stop_point_near(self):
        self.assertTrue(ac.stop_point_near(2, WAYPOINTS, (3.5, 0.2), RADIUS))
        self.assertFalse(ac.stop_point_near(2, WAYPOINTS, (3.0, 0.0), RADIUS))
        self.assertFalse(ac.stop_point_near(None, WAYPOINTS, (4.0, 0.0), RADIUS))
        self.assertFalse(ac.stop_point_near(2, WAYPOINTS, None, RADIUS))
        self.assertFalse(ac.stop_point_near(2, WAYPOINTS, (4.0, 0.0), None), 'no radius: only Nav2 success counts')

    def test_rule_stop_hold_state(self):
        s = mc.ModeState(mode=mc.MODE_AUTONOMY, run_id='r', remaining_waypoints=5, current_section=0, state_revision=7)
        h = mc.rule_stop_hold(s, 2, 5)
        self.assertEqual((h.mode, h.processing_state, h.stop_reason, h.current_section, h.remaining_waypoints, h.state_revision),
                         (mc.MODE_AUTONOMY, mc.PROCESSING_RULE_STOP_HOLD, mc.STOP_REASON_RULE_STOP, 2, 2, 8))
        self.assertIsNone(mc.rule_stop_hold(mc.ModeState(mode=mc.MODE_PAUSE), 2, 5))

    def test_rule_stop_resume_only_while_held(self):
        held = mc.rule_stop_hold(mc.ModeState(mode=mc.MODE_AUTONOMY), 1, 5)
        r = mc.rule_stop_resume(held)
        self.assertTrue(r.accepted)
        self.assertEqual((r.new_state.mode, r.new_state.processing_state, r.new_state.stop_reason), (mc.MODE_AUTONOMY, 'idle', ''))
        self.assertFalse(mc.rule_stop_resume(mc.ModeState(mode=mc.MODE_AUTONOMY)).accepted)
        # resume while not held is evaluated as before (refused in 自律走行)
        self.assertFalse(mc.request_transition('resume', mc.ModeState(mode=mc.MODE_AUTONOMY), frozenset({'TR-10'})).accepted)

    def test_mission_carries_kind_stop(self):
        ws = wpmod.WaypointSet('o', 1, 'h', [wpmod.Waypoint(0, 0), wpmod.Waypoint(1, 0, 0.0, 'stop'), wpmod.Waypoint(2, 0)], [1.0, 1.0])
        self.assertEqual(ws.validate(), [])
        d = ws.to_dict()
        self.assertEqual([w['kind'] for w in d['waypoints']], ['pass', 'stop', 'pass'])
        back = wpmod.WaypointSet.from_dict(d)
        self.assertEqual([w.kind == 'stop' for w in back.waypoints], [False, True, False])
        bad = wpmod.WaypointSet('o', 1, 'h', [wpmod.Waypoint(0, 0), wpmod.Waypoint(1, 0, 0.0, 'stop', True), wpmod.Waypoint(2, 0)], [1.0, 1.0])
        self.assertTrue(any('stop point cannot be skipped' in e for e in bad.validate()))


class FakeAuto:
    def __init__(self):
        self._token = 1
        self.sent = []
        self.cancelled = 0
        self.goal_handle = None
        self.robot_xy = None
        self.nav2_active = True
        self.estimator = (1, '', '', 0.0)

    def new_token(self):
        self._token += 1
        return self._token

    def send_goal(self, token, mission, offset, rec):
        end = ac.section_end(mission.stop_points, offset, len(mission.waypoints))
        self.sent.append((offset, end))

    def cancel(self, rec, tid):
        self.goal_handle = None
        self.cancelled += 1


if ModeManagerNode is not None:
    class Manager:
        _on_nav_result = ModeManagerNode._on_nav_result
        _on_nav_feedback = ModeManagerNode._on_nav_feedback
        _rule_stop_hold = ModeManagerNode._rule_stop_hold
        _request = ModeManagerNode._request
        _set_state = ModeManagerNode._set_state
        _tr10_resume = ModeManagerNode._tr10_resume
        _tr06_pause = ModeManagerNode._tr06_pause
        _perform = ModeManagerNode._perform
        _run_steps = ModeManagerNode._run_steps
        _schedule_resend = ModeManagerNode._schedule_resend
        _resend_fire = ModeManagerNode._resend_fire
        _resend_goal = ModeManagerNode._resend_goal
        _auto_pause = ModeManagerNode._auto_pause
        _update_fields = ModeManagerNode._update_fields
        _estimator_bad = ModeManagerNode._estimator_bad
        _rec = ModeManagerNode._rec

        def __init__(self, stops, resend_wait=None):
            self._lock = threading.RLock()
            self.record_path = Path(tempfile.mkdtemp()) / 'previous_mode_record.json'
            self.state = mc.ModeState(mode=mc.MODE_AUTONOMY, run_id='run-test', remaining_waypoints=5, current_section=0,
                                      speed_limit_application_state='applied')
            self.mission = types.SimpleNamespace(waypoints=list(WAYPOINTS), stop_points=list(stops), skip_allowed=[False] * 5)
            self.next_offset = 0
            self.goal_active, self.drive_released, self.localization_waiting, self.skipping = True, True, False, False
            self.stop_radius = RADIUS
            self.rule_stop_index = None
            self.nav2_resend_wait = resend_wait
            self._resend_run, self.nav2_resend_count = None, 0
            self._error_codes = {}
            self._pending_start = None
            self.auto = FakeAuto()
            self.auto.localization_running = True
            self.estimator_grace = ac.EstimatorGrace(0)
            self.events = []
            self.timers = []
            self.threads = []
            self._logger = types.SimpleNamespace(warning=lambda *a: None, info=lambda *a: None)

        def get_logger(self):
            return self._logger

        def _publish_decision(self, event, tid, reason, details):
            self.events.append((event, tid, details))

        def _publish_state(self):
            pass

        def _skip_check(self):
            pass

        def _estimator_not_normal(self):
            return ''

        def _now(self):
            return 0.0

        def _localization_wait_start(self, reason, details):
            self.events.append(('localization_wait', 'TR-07', details))

        def _start_resend_timer(self, wait, token):
            self.timers.append((wait, token))

        def names(self):
            return [e[0] for e in self.events]

        def feedback(self, xy, offset, poses, remaining):
            self.auto.robot_xy = xy
            self._on_nav_feedback(offset, poses, remaining)

        def resume(self):
            """The 再開 button: _request runs the after-transition job in a thread; wait for it."""
            r = self._request('resume', {})
            for t in threading.enumerate():
                if t.name.endswith('_after'):
                    t.join(5)
            return r


@unittest.skipIf(ModeManagerNode is None, 'rclpy / action_msgs not installed')
class NodeTests(unittest.TestCase):
    def held(self, m, index):
        self.assertEqual(m.state.mode, mc.MODE_AUTONOMY, 'a stop point is not 待機')
        self.assertEqual((m.state.processing_state, m.state.stop_reason), (mc.PROCESSING_RULE_STOP_HOLD, mc.STOP_REASON_RULE_STOP))
        self.assertFalse(m.drive_released, 'motion_hold=true')
        self.assertFalse(m.goal_active)
        self.assertEqual((m.rule_stop_index, m.next_offset), (index, index + 1))

    def test_success_at_the_stop_point_holds_and_resume_goes_on_from_the_next(self):
        m = Manager([False, False, True, False, False])
        m._on_nav_result(SUCCEEDED, 0, '')
        self.held(m, 2)
        self.assertEqual(m.names(), ['rule_stop_hold'])
        r = m.resume()
        self.assertTrue(r.accepted, r.reason)
        self.assertEqual(m.auto.sent, [(3, 4)], 'from the waypoint after the stop point, never the stop point itself')
        self.assertEqual((m.state.mode, m.state.processing_state, m.state.stop_reason), (mc.MODE_AUTONOMY, 'idle', ''))
        self.assertIsNone(m.rule_stop_index)
        self.assertEqual(m.state.speed_limit_application_state, 'unknown', 'the hold is released only at 適用中 (DEC-056)')

    def test_entering_the_radius_holds_at_once_and_cancels_the_goal(self):
        m = Manager([False, False, True, False, False])
        m.auto.goal_handle = object()
        m.feedback((1.0, 0.0), 0, 3, 2)   # past waypoint 0, far from the stop point
        self.assertEqual(m.state.processing_state, 'idle')
        m.feedback((3.4, 0.0), 0, 3, 1)   # 0.6 m from waypoint 2
        self.held(m, 2)
        for t in threading.enumerate():
            if t.name == 'rule_stop_cancel':
                t.join(5)
        self.assertEqual(m.auto.cancelled, 1)
        m.feedback((3.5, 0.0), 0, 3, 1)   # a late feedback of the cancelled goal changes nothing
        self.assertEqual(m.next_offset, 3)
        m._on_nav_result(SUCCEEDED, 0, '')   # a late result changes nothing
        self.held(m, 2)

    def test_no_restart_by_itself(self):
        m = Manager([False, False, True, False, False], resend_wait=2.0)
        m._on_nav_result(SUCCEEDED, 0, '')
        m._on_nav_result(ABORTED, 0, 'late')   # neither a pause nor a re-send
        self.assertEqual(m.timers, [])
        self.assertNotIn('automatic_pause', m.names())
        m._estimator_bad('ND-07 bad', {})   # no localization wait (it would drive on by itself)
        self.assertNotIn('localization_wait', m.names())
        self.held(m, 2)
        self.assertEqual(m.auto.sent, [])

    def test_resend_before_the_stop_point_goes_only_up_to_it(self):
        m = Manager([False, False, True, False, False], resend_wait=2.0)
        m.next_offset = 1
        m._on_nav_result(ABORTED, 0, '')
        wait, token = m.timers.pop(0)
        m._resend_fire(token)
        self.assertEqual(m.auto.sent, [(1, 2)], 'PRM-161 re-send never past the stop point')

    def test_resume_when_not_held_is_unchanged(self):
        m = Manager([False, False, True, False, False])
        r = m.resume()
        self.assertFalse(r.accepted)
        self.assertEqual(m.auto.sent, [])

    def test_last_waypoint_stop_is_tr08(self):
        m = Manager([False, False, False, False, True])
        m.next_offset = 3
        m._on_nav_result(SUCCEEDED, 0, '')
        self.assertEqual((m.state.mode, m.state.stop_reason), (mc.MODE_PAUSE, mc.STOP_REASON_GOAL_REACHED))

    def test_two_stop_points_in_a_row(self):
        m = Manager([False, True, True, False, False])
        m._on_nav_result(SUCCEEDED, 0, '')
        self.held(m, 1)
        m.resume()
        self.assertEqual(m.auto.sent, [(2, 2)])
        m.goal_active = True
        m._on_nav_result(SUCCEEDED, 0, '')
        self.held(m, 2)
        m.resume()
        self.assertEqual(m.auto.sent, [(2, 2), (3, 4)])

    def test_human_pause_while_held_then_resume_goes_on_after_the_stop(self):
        m = Manager([False, False, True, False, False])
        m._on_nav_result(SUCCEEDED, 0, '')
        m._request('pause', {})
        self.assertEqual((m.state.mode, m.state.processing_state, m.state.stop_reason), (mc.MODE_PAUSE, 'idle', 'human'))
        self.assertIsNone(m.rule_stop_index)
        m.resume()   # TR-10 from 待機
        self.assertEqual(m.state.mode, mc.MODE_AUTONOMY)
        self.assertEqual(m.auto.sent, [(3, 4)])


if __name__ == '__main__':
    unittest.main()
