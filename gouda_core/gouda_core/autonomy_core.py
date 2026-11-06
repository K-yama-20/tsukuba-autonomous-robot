"""Autonomy decisions of the mode manager (ND-03, stage 5-6, REV-061). No ROS dependency; mode_manager_node wraps it.

- resolve_mission: the human's start request (IFD-02) names a waypoint set and a converted map with their hashes. The set, its
  speed mask (IFD-41) and the map (IFD-29) are read from the databases and every hash is compared; any mismatch refuses the
  start (RQ-I078, TR-05 guard).
- goal poses: the waypoints from an offset (all at TR-05; the remaining ones at TR-10), in the map frame (IFD-13).
- section index from the feedback: s = k + (P - r) - 1 for offset k, P poses, r remaining (docs/speed_limit_publisher.md),
  for the record only (RQ-I030). Passing is judged by Nav2 (RQ-I011).
- speed_limit_application_state (DEC-047): observed from the latched mask (IFD-42), the robot position and the last speed_limit
  (IFD-14). Gouda never publishes a speed limit (RQ-I020). The hold is released only in 'applied' (DEC-056, TR-05).
- WaypointSkip (DEC-367, REV-235): when a waypoint the human marked skip_allowed stays blocked, the mode manager gives it up
  and sends the goal again from the next one. Nothing is skipped while one of PRM-137..140 is unresolved.
- nav2_failure_reason (E-4, REV-183, DEC-393): the stop reason of a failed Nav2 goal from its error code. The code table comes
  from the nav2_msgs action constants (autonomy_client.error_code_table); only the rule by action and constant name is here.
- nav2_failure_action / nav2_resend_due (DEC-437, DEC-460, REV-245): a failed Nav2 goal does not pause when
  nav2_failure_resend_wait_s (PRM-161) has a value; the goal is sent again after that wait unless something came between.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from gouda_core.map_database import MapDatabase
from gouda_core.waypoints import RouteDatabase

# speed_limit_application_state values (IFD-01, DEC-047) and their monitor labels
SL_NOT_LOADED = 'not_loaded'        # 未読込・上限なし
SL_OUTSIDE_MASK = 'outside_mask'    # マスク外・直前値保持
SL_OUTSIDE_BAND = 'outside_band'    # 帯外・無制限
SL_APPLIED = 'applied'              # 適用中
SL_UNKNOWN = 'unknown'              # 不明
SL_LABELS = {SL_NOT_LOADED: '未読込・上限なし', SL_OUTSIDE_MASK: 'マスク外・直前値保持', SL_OUTSIDE_BAND: '帯外・無制限',
             SL_APPLIED: '適用中', SL_UNKNOWN: '不明'}


@dataclass
class Mission:
    set_id: str
    set_revision: int
    set_hash: str
    map_origin_id: str
    map_revision: int
    map_hash: str
    map_yaml: str
    mask_yaml: str
    filter_base: float
    filter_multiplier: float
    waypoints: list = field(default_factory=list)      # [(x, y, yaw)]
    section_limits_mps: list = field(default_factory=list)
    map_directory: str = ''                             # the converted map revision (ND-07's map, REV-128)
    keepout_yaml: str = ''                              # the drawn areas' KeepoutFilter mask (IFD-41, REV-137)
    keepout_sha256: str = ''                            # hash of the cell values map_server publishes (DEC-224 (a))
    keepout_size: tuple = (0, 0)                        # (width, height) of that mask
    skip_allowed: list = field(default_factory=list)    # per waypoint: the human's mark (DEC-367)


FOLLOW_PATH_BLOCKED = ('PATIENCE_EXCEEDED', 'FAILED_TO_MAKE_PROGRESS', 'NO_VALID_CONTROL')


def stop_reason_for(action: str, name: str) -> Optional[str]:
    """The stop reason of one nav2_msgs error constant (action 'FollowPath' / 'ComputePathThroughPoses' / 'ComputePathToPose');
    None for NONE."""
    from gouda_core import mode_core
    if name == 'NONE':
        return None
    if name == 'TF_ERROR':
        return mode_core.STOP_REASON_NAV2_TF
    if action == 'FollowPath':
        return mode_core.STOP_REASON_BLOCKED if name in FOLLOW_PATH_BLOCKED else mode_core.STOP_REASON_CONTROLLER
    return mode_core.STOP_REASON_PLAN_FAILURE


def nav2_failure_reason(error_code: int, table: dict) -> tuple:
    """(stop reason, code name) of a failed goal. table: {code: (stop reason, 'Action.NAME')} from error_code_table."""
    from gouda_core import mode_core
    if error_code == 0:
        return mode_core.STOP_REASON_NAV2_NO_CODE, 'NONE (no error code)'
    if error_code in table:
        return table[error_code]
    return mode_core.STOP_REASON_NAV2_OTHER, f'unknown code {error_code}'


def _int(text) -> Optional[int]:
    try:
        return int(str(text))
    except ValueError:
        return None


def resolve_mission(data_root: Path, request: dict) -> tuple:
    """(Mission or None, reason). request: waypoint_set_id / _revision / _hash, map_id / map_revision / map_hash (strings)."""
    data_root = Path(data_root)
    sid, srev = request.get('waypoint_set_id', ''), _int(request.get('waypoint_set_revision', ''))
    if not sid or srev is None:
        return None, 'no waypoint set selected (waypoint_set_id / waypoint_set_revision)'
    routes = RouteDatabase(data_root / 'routes')
    ws, man = routes.load(sid, srev), routes.manifest(sid, srev)
    if ws is None or man is None:
        return None, f'waypoint set {sid}/{srev:03d} not found'
    if request.get('waypoint_set_hash') != man.get('content_hash') or ws.content_hash() != man.get('content_hash'):
        return None, f'waypoint set {sid}/{srev:03d}: content hash does not match the request (RQ-I078)'
    mid, mrev = request.get('map_id', ''), _int(request.get('map_revision', ''))
    if (mid, mrev, request.get('map_hash')) != (ws.map_origin_id, ws.map_revision, ws.map_content_hash):
        return None, f'the selected map {mid}/{mrev} does not match the map of the waypoint set {ws.map_origin_id}/{ws.map_revision} (RQ-I078)'
    maps = MapDatabase(data_root / 'maps')
    cm = maps.converted_manifest(mid, mrev)
    if cm is None or cm.get('content_hash') != ws.map_content_hash:
        return None, f'converted map {mid}/{mrev:03d} not found or its content hash differs (RQ-I078)'
    sdir = data_root / 'routes' / sid / f'{srev:03d}'
    mdir = data_root / 'maps' / mid / 'converted' / f'{mrev:03d}'
    map_yaml, mask_yaml, info = mdir / 'map.yaml', sdir / 'speed_mask.yaml', sdir / 'filter_info.yaml'
    for p in (map_yaml, mask_yaml, info):
        if not p.is_file():
            return None, f'{p} is missing'
    try:
        fi = yaml.safe_load(info.read_text(encoding='utf-8')) or {}
        params = fi.get('costmap_filter_info_server', {}).get('ros__parameters', fi)
        base, mult, kind = float(params['base']), float(params['multiplier']), int(params['type'])
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        return None, f'{info} could not be read ({type(e).__name__})'
    if kind != 2:
        return None, f'{info}: type {kind} is not the speed limit in m/s (type 2, IFD-41)'
    from gouda_core import keepout_mask
    keep = (man.get('generator') or {}).get('keepout') or {}
    kyaml = sdir / f'{keepout_mask.NAME}.yaml'
    if not keep.get('data_sha256') or not kyaml.is_file():
        return None, f'waypoint set {sid}/{srev:03d} has no keepout mask (saved before REV-137): save it again in the waypoint tab'
    return Mission(sid, srev, man['content_hash'], mid, mrev, ws.map_content_hash, str(map_yaml), str(mask_yaml), base, mult,
                   [(w.x, w.y, w.yaw) for w in ws.waypoints], list(ws.section_limits_mps), str(mdir),
                   str(kyaml), str(keep['data_sha256']), (int(keep.get('width', 0)), int(keep.get('height', 0))),
                   [bool(w.skip_allowed) for w in ws.waypoints], [w.kind == 'stop' for w in ws.waypoints]), 'mission resolved'


def check_localization_map(map_directory: str) -> Optional[str]:
    """None when the converted map has what ND-07 (trial A3) needs: the point-map tiles and the mapping trajectory (REV-128)."""
    from gouda_core import map_convert as mc
    d = Path(map_directory)
    for rel in (mc.POINTCLOUD_MAP_METADATA, mc.TRAJECTORY_FILE):
        if not (d / rel).is_file():
            return f'the map has no {rel} for the global localization (ND-07): convert it again with PRM-94 / PRM-95 resolved'
    return None


LOC_WAIT_NONE, LOC_WAIT_CLEAR, LOC_WAIT_KEEP, LOC_WAIT_RESUME = 'none', 'clear', 'keep', 'resume'


def localization_wait_action(waiting: bool, in_autonomy: bool, goal_active: bool) -> str:
    """What 正常 does to localization_wait (DEC-423): a human's pause or end clears it; a goal still ending keeps it until the next status."""
    if not waiting:
        return LOC_WAIT_NONE
    if not in_autonomy:
        return LOC_WAIT_CLEAR
    return LOC_WAIT_KEEP if goal_active else LOC_WAIT_RESUME


NAV2_FAIL_PAUSE, NAV2_FAIL_RESEND = 'pause', 'resend'


def nav2_failure_action(resend_wait_s, in_autonomy: bool) -> str:
    """What a failed Nav2 goal does (DEC-437, DEC-460): re-send after resend_wait_s (PRM-161) in 自律走行; without a value (or
    outside 自律走行) the old TR-07 automatic pause (DEC-200)."""
    return NAV2_FAIL_RESEND if resend_wait_s is not None and in_autonomy else NAV2_FAIL_PAUSE


def nav2_resend_due(token: int, current_token: int, in_autonomy: bool, localization_waiting: bool, goal_active: bool) -> bool:
    """A re-send scheduled after a failure (DEC-460) is sent only when nothing came during the wait: a human pause / end, a new
    start and a localization wait each take a new token; the mode must still be 自律走行 and no other goal may be active."""
    return token == current_token and in_autonomy and not localization_waiting and not goal_active


class EstimatorGrace:
    """How long 推定不能 has lasted while driving (DEC-419): bad() says whether it just started and whether continue_s has passed."""
    def __init__(self, continue_s: float):
        self.continue_s = continue_s
        self.since: Optional[float] = None

    def bad(self, now: float) -> tuple:
        started = self.since is None
        if started:
            self.since = now
        return started, now - self.since >= self.continue_s

    def clear(self) -> Optional[float]:
        """Back to normal; returns when the bad period started, or None when there was none."""
        since, self.since = self.since, None
        return since


def check_initial_pose(frame_id: str, x: float, y: float, qz: float, qw: float) -> Optional[str]:
    """None when the initial pose (IFD-02 / IFD-34) is usable: map frame, finite, a unit planar quaternion."""
    if frame_id != 'map':
        return f'initial pose frame {frame_id!r} is not map (no initial pose given?)'
    if not all(math.isfinite(v) for v in (x, y, qz, qw)):
        return 'initial pose is not finite'
    if abs(math.hypot(qz, qw) - 1) > 1e-3:
        return 'initial pose orientation is not a unit yaw quaternion'
    return None


def goal_poses(waypoints: list, offset: int) -> list:
    """[(x, y, qz, qw)] of the waypoints from offset (map frame)."""
    return [(x, y, math.sin(yaw / 2), math.cos(yaw / 2)) for (x, y, yaw) in waypoints[offset:]]


def section_from_feedback(offset: int, poses: int, remaining: int) -> int:
    """Section being driven (for the record): s = k + (P - r) - 1, never below the offset's section."""
    return max(offset + (poses - remaining) - 1, max(offset - 1, 0))


def remaining_offset(offset: int, poses: int, remaining: int) -> int:
    """Index of the first waypoint not yet passed (kept for the resume, TR-10 / RQ-I014)."""
    return offset + max(poses - remaining, 0)


@dataclass
class MaskGrid:
    origin_x: float
    origin_y: float
    resolution: float
    width: int
    height: int
    data: list          # row-major, OccupancyGrid values

    def cell(self, x: float, y: float) -> Optional[int]:
        i, j = math.floor((x - self.origin_x) / self.resolution), math.floor((y - self.origin_y) / self.resolution)
        if not (0 <= i < self.width and 0 <= j < self.height):
            return None
        return int(self.data[j * self.width + i])


def speed_limit_state(mask: Optional[MaskGrid], info_received: bool, robot_xy: Optional[tuple], limit_since_start: Optional[float]) -> str:
    """DEC-047 state. 'applied' needs the robot in a band cell (> 0) AND a speed_limit received since the Nav2 start with a
    positive value; a band cell without such a speed_limit is 'unknown' (the hold stays: DEC-056)."""
    if mask is None or not info_received:
        return SL_NOT_LOADED
    if robot_xy is None:
        return SL_UNKNOWN
    c = mask.cell(*robot_xy)
    if c is None:
        return SL_OUTSIDE_MASK
    if c <= 0:
        return SL_OUTSIDE_BAND
    return SL_APPLIED if (limit_since_start is not None and limit_since_start > 0) else SL_UNKNOWN


def parse_footprint(text: str) -> Optional[list]:
    """[(x, y)] of a Nav2 footprint string "[[x1, y1], [x2, y2], ...]" (PRM-69), None when it is not a polygon."""
    try:
        pts = [(float(x), float(y)) for x, y in yaml.safe_load(text)]
    except (TypeError, ValueError, yaml.YAMLError):
        return None
    return pts if len(pts) >= 3 else None


def footprint_max_cost(grid: MaskGrid, x: float, y: float, yaw: float, footprint: list) -> Optional[int]:
    """Largest costmap value in the cells under the footprint placed at (x, y, yaw); None when no cell is on the grid. A cell
    counts when its centre is inside the polygon; unknown (-1) is not a cost."""
    c, s = math.cos(yaw), math.sin(yaw)
    poly = [(x + px * c - py * s, y + px * s + py * c) for px, py in footprint]
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    r = grid.resolution
    i0, i1 = math.floor((min(xs) - grid.origin_x) / r), math.floor((max(xs) - grid.origin_x) / r)
    j0, j1 = math.floor((min(ys) - grid.origin_y) / r), math.floor((max(ys) - grid.origin_y) / r)
    best = None
    for j in range(max(j0, 0), min(j1, grid.height - 1) + 1):
        cy = grid.origin_y + (j + 0.5) * r
        for i in range(max(i0, 0), min(i1, grid.width - 1) + 1):
            cx = grid.origin_x + (i + 0.5) * r
            if _inside(poly, cx, cy):
                v = int(grid.data[j * grid.width + i])
                if v >= 0 and (best is None or v > best):
                    best = v
    return best


def _inside(poly: list, x: float, y: float) -> bool:
    inside, n = False, len(poly)
    for k in range(n):
        (ax, ay), (bx, by) = poly[k], poly[(k + 1) % n]
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
            inside = not inside
    return inside


@dataclass
class SkipSettings:
    stall_s: Optional[float]          # PRM-137 (T3)
    cost_threshold: Optional[float]   # PRM-138 (C)
    occupied_s: Optional[float]       # PRM-139 (T_occ)
    progress_m: Optional[float]       # PRM-140

    def missing(self) -> list:
        """The unresolved settings: while any is missing nothing is skipped."""
        return [f'{k} ({prm})' for k, prm in (('stall_s', 'PRM-137'), ('cost_threshold', 'PRM-138'), ('occupied_s', 'PRM-139'), ('progress_m', 'PRM-140'))
                if getattr(self, k) is None or not math.isfinite(getattr(self, k)) or getattr(self, k) <= 0]


class WaypointSkip:
    """DEC-367 / DEC-483: give up the current target waypoint when all of these hold, then the caller sends the goal from the next one.
    - the human marked it skip_allowed (never a stop point or the last waypoint: checked when the set is saved);
    - ND-07 is 正常;
    - the distance to the waypoint has not shrunk by progress_m (PRM-140) below its smallest value for stall_s (PRM-137), and Nav2
      counted a recovery in that time (counted over goals: a re-sent goal starts its number_of_recoveries at 0, DEC-460);
    - the largest cost under the footprint placed on the waypoint has been >= cost_threshold (PRM-138) for occupied_s (PRM-139);
    - the previous target was reached, not skipped (at most one skip in a row).
    update() returns None, or the reason (a dict for the record) when the waypoint is to be skipped."""

    def __init__(self, settings: SkipSettings):
        self.s = settings
        self.last_skipped: Optional[int] = None   # index skipped last; cleared when a later target is reached
        self._raw, self._base = 0, 0              # number_of_recoveries as received, and the sum of earlier goals' counts
        self.reset()

    def reset(self) -> None:
        self.target: Optional[int] = None
        self.anchor: Optional[tuple] = None        # (closest distance, its time, recoveries then) of the stall clock
        self.occupied_since: Optional[float] = None

    def _recoveries(self, raw: int) -> int:
        if raw < self._raw:   # a new goal: its count starts again
            self._base += self._raw
        self._raw = raw
        return self._base + raw

    def update(self, now: float, target: int, skip_allowed: list, robot_xy: tuple, recoveries: int, estimator_normal: bool,
               waypoint_cost: Optional[int], waypoint_xy: Optional[tuple] = None) -> Optional[dict]:
        total = self._recoveries(recoveries)
        if self.s.missing() or waypoint_xy is None:
            return None
        if target != self.target:   # a new target: reached (or skipped) the previous one
            if self.target is not None and self.last_skipped is not None and target > self.last_skipped + 1:
                self.last_skipped = None
            self.reset(); self.target = target
        d = math.hypot(robot_xy[0] - waypoint_xy[0], robot_xy[1] - waypoint_xy[1])
        if self.anchor is None or d <= self.anchor[0] - self.s.progress_m:
            self.anchor = (d, now, total)
        if waypoint_cost is not None and waypoint_cost >= self.s.cost_threshold:
            if self.occupied_since is None:
                self.occupied_since = now
        else:
            self.occupied_since = None
        if not (0 <= target < len(skip_allowed) - 1) or not skip_allowed[target] or not estimator_normal:
            return None
        if self.last_skipped is not None and target == self.last_skipped + 1:
            return None   # the point right after a skipped one is not skipped (one in a row)
        stalled_s = now - self.anchor[1]
        occupied_s = 0.0 if self.occupied_since is None else now - self.occupied_since
        if stalled_s < self.s.stall_s or total <= self.anchor[2] or occupied_s < self.s.occupied_s:
            return None
        self.last_skipped = target
        why = {'waypoint': target, 'distance_m': round(d, 2), 'closest_m': round(self.anchor[0], 2), 'stalled_s': round(stalled_s, 2),
               'recoveries': total - self.anchor[2], 'waypoint_cost': waypoint_cost, 'occupied_s': round(occupied_s, 2)}
        self.reset()
        return why
