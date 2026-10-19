"""ROS side of the mode manager's autonomy (ND-03, stage 5-6, REV-061): the thin Nav2 client and the activation of the
autonomy nodes. The decisions are in autonomy_core; the transitions are applied by mode_manager_node.

What it talks to (all names from the design):
- Nav2 (ND-10): lifecycle_manager_navigation/manage_nodes (STARTUP at TR-05, RESET at TR-11 / TR-12; IFD-36), the parameters
  of map_server (map, IFD-24), filter_mask_server and costmap_filter_info_server (the waypoint set's mask, IFD-41 / IFD-42) set
  before STARTUP, and navigate_through_poses (IFD-13: goal, feedback, result, cancel).
- the vehicle output ND-11 / ND-12: lifecycle configure + activate at TR-05, deactivate at TR-11 / TR-12 (IFD-36).
- localization/initial_pose (IFD-34): the human's initial pose, sent once at TR-05.
- speed_limit (IFD-14), costmap_filter_info / speed_filter_mask (IFD-42): observed only, for speed_limit_application_state.
Waiting: a service or action server that is not there makes the step fail at once (recorded). A started call is waited for
without an upper limit (no time value is invented); the human can always pause or end, which abandons the start.
"""
from __future__ import annotations

import threading
from typing import Callable, Optional

from rclpy.action import ActionClient
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from rclpy.parameter import Parameter
from rcl_interfaces.srv import SetParameters
from lifecycle_msgs.msg import Transition, State
from lifecycle_msgs.srv import ChangeState, GetState
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from nav_msgs.msg import OccupancyGrid
from nav2_msgs.action import NavigateThroughPoses
from nav2_msgs.msg import SpeedLimit, CostmapFilterInfo
from nav2_msgs.srv import ManageLifecycleNodes

from gouda_core import autonomy_core as ac
from gouda_core import nav2_config as nc

LATCHED = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL, history=HistoryPolicy.KEEP_LAST, depth=1)
VOLATILE1 = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE, history=HistoryPolicy.KEEP_LAST, depth=1)
SPEED_LIMIT_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE, history=HistoryPolicy.KEEP_LAST, depth=10)  # IFD-14
VEHICLE_NODES = ('gouda_motion_controller', 'vehicle_bridge')   # ND-11, ND-12


class StepFailed(Exception):
    pass


class Abandoned(Exception):
    pass


class AutonomyClient:
    def __init__(self, node, on_feedback: Callable, on_result: Callable, on_speed_state: Callable):
        self.node = node
        self.on_feedback, self.on_result, self.on_speed_state = on_feedback, on_result, on_speed_state
        self.nav = ActionClient(node, NavigateThroughPoses, 'navigate_through_poses')
        self.manage = node.create_client(ManageLifecycleNodes, 'lifecycle_manager_navigation/manage_nodes')
        self.set_params = {n: node.create_client(SetParameters, f'{n}/set_parameters') for n in ('map_server', 'filter_mask_server', 'costmap_filter_info_server')}
        self.change = {n: node.create_client(ChangeState, f'{n}/change_state') for n in VEHICLE_NODES}
        self.get = {n: node.create_client(GetState, f'{n}/get_state') for n in VEHICLE_NODES}
        self.initial_pose_pub = node.create_publisher(PoseWithCovarianceStamped, 'localization/initial_pose', VOLATILE1)   # IFD-34
        node.create_subscription(SpeedLimit, nc.SPEED_LIMIT_TOPIC, self._on_speed_limit, SPEED_LIMIT_QOS)
        node.create_subscription(OccupancyGrid, nc.FILTER_MASK_TOPIC, self._on_mask, LATCHED)
        node.create_subscription(CostmapFilterInfo, nc.FILTER_INFO_TOPIC, self._on_info, LATCHED)
        self.mask: Optional[ac.MaskGrid] = None
        self.info_received = False
        self.limit_since_start: Optional[float] = None
        self.robot_xy: Optional[tuple] = None
        self.goal_handle = None
        self.goal_offset, self.goal_poses = 0, 0
        self.nav2_active = False
        self._token = 0
        self._lock = threading.Lock()

    # ---- observation (IFD-14 / IFD-42) ----
    def _on_speed_limit(self, m: SpeedLimit):
        self.limit_since_start = float(m.speed_limit)
        self._speed_state()

    def _on_mask(self, m: OccupancyGrid):
        i = m.info
        self.mask = ac.MaskGrid(i.origin.position.x, i.origin.position.y, i.resolution, i.width, i.height, list(m.data))
        self._speed_state()

    def _on_info(self, m: CostmapFilterInfo):
        self.info_received = True
        self._speed_state()

    def _speed_state(self):
        self.on_speed_state(ac.speed_limit_state(self.mask, self.info_received, self.robot_xy, self.limit_since_start),
                            {'speed_limit': self.limit_since_start, 'robot_xy': self.robot_xy})

    # ---- helpers (worker thread; the executor resolves the futures) ----
    def new_token(self) -> int:
        with self._lock:
            self._token += 1
            return self._token

    def _check(self, token):
        if token != self._token:
            raise Abandoned()

    def _call(self, client, request, what, token):
        if not client.service_is_ready():
            raise StepFailed(f'{what}: service {client.srv_name} is not available')
        fut = client.call_async(request)
        done = threading.Event(); fut.add_done_callback(lambda _: done.set())
        done.wait()   # no upper limit (no time value is invented); a pause / end abandons the start by the token
        self._check(token)
        if fut.exception() is not None:
            raise StepFailed(f'{what}: {fut.exception()}')
        return fut.result()

    def _set(self, server, params, what, token):
        req = SetParameters.Request(); req.parameters = [Parameter(k, value=v).to_parameter_msg() for k, v in params.items()]
        res = self._call(self.set_params[server], req, what, token)
        bad = [r.reason for r in res.results if not r.successful]
        if bad:
            raise StepFailed(f'{what}: {bad}')

    def _vehicle_activate(self, token) -> list:
        steps = []
        for n in VEHICLE_NODES:
            st = self._call(self.get[n], GetState.Request(), f'{n} get_state', token).current_state.id
            for target, tid in ((State.PRIMARY_STATE_INACTIVE, Transition.TRANSITION_CONFIGURE), (State.PRIMARY_STATE_ACTIVE, Transition.TRANSITION_ACTIVATE)):
                if st == State.PRIMARY_STATE_UNCONFIGURED or (st == State.PRIMARY_STATE_INACTIVE and target == State.PRIMARY_STATE_ACTIVE):
                    req = ChangeState.Request(); req.transition.id = tid
                    if not self._call(self.change[n], req, f'{n} change_state {tid}', token).success:
                        raise StepFailed(f'{n}: lifecycle transition {tid} failed (see its log)')
                    st = target; steps.append(f'{n}:{tid}')
            if st != State.PRIMARY_STATE_ACTIVE:
                raise StepFailed(f'{n} is in lifecycle state {st}, not active')
        return steps

    # ---- TR-05 / TR-10 / TR-11 / TR-12 steps ----
    def start(self, token, mission: ac.Mission, initial_pose: PoseWithCovarianceStamped, record: Callable) -> None:
        """TR-05 after the transition: parameters, Nav2 STARTUP, vehicle output, initial pose, goal. Raises StepFailed / Abandoned."""
        self._set('map_server', {'yaml_filename': mission.map_yaml}, 'map_server yaml_filename', token)
        self._set('filter_mask_server', {'yaml_filename': mission.mask_yaml}, 'filter_mask_server yaml_filename', token)
        self._set('costmap_filter_info_server', {'base': mission.filter_base, 'multiplier': mission.filter_multiplier}, 'costmap_filter_info_server base / multiplier', token)
        record('nav2_parameters_set', f'map {mission.map_yaml}, mask {mission.mask_yaml}, base {mission.filter_base}, multiplier {mission.filter_multiplier}', {})
        self.initial_pose_pub.publish(initial_pose)
        record('initial_pose_sent', 'IFD-34 localization/initial_pose sent once', {'x': initial_pose.pose.pose.position.x, 'y': initial_pose.pose.pose.position.y})
        self.limit_since_start = None; self.mask = None; self.info_received = False; self.robot_xy = None
        req = ManageLifecycleNodes.Request(); req.command = ManageLifecycleNodes.Request.STARTUP
        if not self._call(self.manage, req, 'Nav2 STARTUP', token).success:
            raise StepFailed('Nav2 STARTUP failed (a server did not configure / activate; see the Nav2 logs)')
        self.nav2_active = True
        record('nav2_started', 'Nav2 servers active (lifecycle_manager_navigation STARTUP)', {})
        steps = self._vehicle_activate(token)
        record('vehicle_output_active', f'ND-11 / ND-12 active ({", ".join(steps) or "already active"})', {'steps': steps})
        self.send_goal(token, mission, 0, record)

    def send_goal(self, token, mission: ac.Mission, offset: int, record: Callable) -> None:
        if not self.nav.server_is_ready():
            raise StepFailed('navigate_through_poses action server is not available')
        goal = NavigateThroughPoses.Goal()
        stamp = self.node.get_clock().now().to_msg()
        for (x, y, qz, qw) in ac.goal_poses(mission.waypoints, offset):
            p = PoseStamped(); p.header.frame_id = 'map'; p.header.stamp = stamp
            p.pose.position.x, p.pose.position.y = float(x), float(y); p.pose.orientation.z, p.pose.orientation.w = float(qz), float(qw)
            goal.poses.append(p)
        self.goal_offset, self.goal_poses = offset, len(goal.poses)
        fut = self.nav.send_goal_async(goal, feedback_callback=self._feedback)
        done = threading.Event(); fut.add_done_callback(lambda _: done.set()); done.wait()
        self._check(token)
        gh = fut.result()
        if not gh.accepted:
            raise StepFailed('Nav2 rejected the NavigateThroughPoses goal')
        self.goal_handle = gh
        record('nav2_goal_sent', f'NavigateThroughPoses goal accepted ({len(goal.poses)} poses from waypoint {offset})', {'offset': offset, 'poses': len(goal.poses)})
        gh.get_result_async().add_done_callback(lambda f, h=gh: self._result(h, f))

    def _feedback(self, fb):
        f = fb.feedback
        self.robot_xy = (f.current_pose.pose.position.x, f.current_pose.pose.position.y)
        self.on_feedback(self.goal_offset, self.goal_poses, int(f.number_of_poses_remaining))
        self._speed_state()

    def _result(self, handle, fut):
        if handle is not self.goal_handle:
            return   # an older goal (cancelled before) — its end is recorded by the cancel
        self.goal_handle = None
        r = fut.result()
        self.on_result(int(r.status), int(getattr(r.result, 'error_code', 0)), str(getattr(r.result, 'error_msg', '')))

    def cancel(self, record: Callable, transition_id: str) -> None:
        """Cancel the active goal (TR-06 / TR-11 / TR-12); the outcome is recorded when the server answers."""
        gh, self.goal_handle = self.goal_handle, None
        if gh is None:
            record('navigation_goal_check', 'no active Nav2 goal', {}); return
        fut = gh.cancel_goal_async()
        fut.add_done_callback(lambda f: record('nav2_goal_cancelled', f'cancel answered ({len(f.result().goals_canceling)} goal(s) cancelling)', {}))

    def stop(self, token, record: Callable) -> None:
        """TR-11 / TR-12 after the transition: deactivate ND-11 / ND-12 and reset Nav2 (it stays inactive in manual)."""
        for n in VEHICLE_NODES:
            try:
                st = self._call(self.get[n], GetState.Request(), f'{n} get_state', token).current_state.id
                if st == State.PRIMARY_STATE_ACTIVE:
                    req = ChangeState.Request(); req.transition.id = Transition.TRANSITION_DEACTIVATE
                    ok = self._call(self.change[n], req, f'{n} deactivate', token).success
                    record('vehicle_output_deactivated' if ok else 'vehicle_output_deactivate_failed', f'{n} deactivate: {ok}', {'node': n})
            except StepFailed as e:
                record('vehicle_output_deactivate_failed', str(e), {'node': n})
        if self.nav2_active:
            try:
                req = ManageLifecycleNodes.Request(); req.command = ManageLifecycleNodes.Request.RESET
                ok = self._call(self.manage, req, 'Nav2 RESET', token).success
                self.nav2_active = not ok
                record('nav2_reset' if ok else 'nav2_reset_failed', f'Nav2 RESET: {ok}', {})
            except StepFailed as e:
                record('nav2_reset_failed', str(e), {})
