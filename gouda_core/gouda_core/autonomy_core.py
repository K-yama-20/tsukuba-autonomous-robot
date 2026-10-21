"""Autonomy decisions of the mode manager (ND-03, stage 5-6, REV-061). No ROS dependency; mode_manager_node wraps it.

- resolve_mission: the human's start request (IFD-02) names a waypoint set and a converted map with their hashes. The set, its
  speed mask (IFD-41) and the map (IFD-29) are read from the databases and every hash is compared; any mismatch refuses the
  start (RQ-I078, TR-05 guard).
- goal poses: the waypoints from an offset (all at TR-05; the remaining ones at TR-10), in the map frame (IFD-13).
- section index from the feedback: s = k + (P - r) - 1 for offset k, P poses, r remaining (docs/speed_limit_publisher.md),
  for the record only (RQ-I030). Passing is judged by Nav2 (RQ-I011).
- speed_limit_application_state (DEC-047): observed from the latched mask (IFD-42), the robot position and the last speed_limit
  (IFD-14). Gouda never publishes a speed limit (RQ-I020). The hold is released only in 'applied' (DEC-056, TR-05).
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
    return Mission(sid, srev, man['content_hash'], mid, mrev, ws.map_content_hash, str(map_yaml), str(mask_yaml), base, mult,
                   [(w.x, w.y, w.yaw) for w in ws.waypoints], list(ws.section_limits_mps), str(mdir)), 'mission resolved'


def check_localization_map(map_directory: str) -> Optional[str]:
    """None when the converted map has what ND-07 (trial A3) needs: the point-map tiles and the mapping trajectory (REV-128)."""
    from gouda_core import map_convert as mc
    d = Path(map_directory)
    for rel in (mc.POINTCLOUD_MAP_METADATA, mc.TRAJECTORY_FILE):
        if not (d / rel).is_file():
            return f'the map has no {rel} for the global localization (ND-07): convert it again with PRM-94 / PRM-95 resolved'
    return None


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
