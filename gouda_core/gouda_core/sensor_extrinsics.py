"""Sensor mounting from /config (IFD-26) -> poses in base_link and GLIM's T_lidar_imu. No ROS dependency.

Requirement: the human sets the sensor mounting for GLIM in gouda_monitor (/config). An unknown mounting is never asked about
and never stops design, implementation or mapping (intent.md:105, RQ-I081). Therefore every field that is still UNKNOWN is
replaced by the neutral element (translation 0, rotation none, axes = base_link axes) and the list of such fields is returned
so that the caller records it (DecisionEvent) and the monitor shows it. Nothing is guessed beyond that.

/config fields (monitor_core.CONFIG_FIELDS), per sensor s in {lidar, imu}:
  s_mount_x_m / _y_m / _z_m          origin of the sensor frame in base_link [m] (REP-103: x forward, y left, z up)
  s_mount_roll_rad / _pitch_rad / _yaw_rad   additional rotation of the mounted sensor, applied in base_link after the axis mapping
  s_axis_mapping                     where the sensor's own axes point, e.g. "+x forward, +y left, +z up"
                                     items "<sign><axis> <direction>" for x, y, z; direction is forward/back/left/right/up/down
                                     (also 前/後/左/右/上/下). A left-handed mapping is not a rotation and is reported as invalid.
Pose of the sensor in base_link: R = R_rpy * A (columns of A = sensor axes in base_link), t = (x, y, z).
GLIM: T_lidar_imu maps IMU-frame points into the LiDAR frame = inv(T_base_lidar) * T_base_imu, written as TUM [x, y, z, qx, qy, qz, qw].
"""
from __future__ import annotations

import math
import re
from typing import List, Optional, Tuple

UNKNOWN = 'UNKNOWN'
DIRECTIONS = {'forward': (1, 0, 0), 'front': (1, 0, 0), '前': (1, 0, 0), '前方': (1, 0, 0),
              'back': (-1, 0, 0), 'backward': (-1, 0, 0), '後': (-1, 0, 0), '後方': (-1, 0, 0),
              'left': (0, 1, 0), '左': (0, 1, 0), '左方': (0, 1, 0),
              'right': (0, -1, 0), '右': (0, -1, 0), '右方': (0, -1, 0),
              'up': (0, 0, 1), '上': (0, 0, 1), '上方': (0, 0, 1),
              'down': (0, 0, -1), '下': (0, 0, -1), '下方': (0, 0, -1)}
ITEM = re.compile(r'^\s*([+-]?)\s*([xyz])\s*(?:axis)?\s*[:=]?\s*(\S+)\s*$', re.I)
IDENTITY = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
Matrix = Tuple[Tuple[float, float, float], ...]


def parse_axis_mapping(text: str) -> Matrix:
    """Return the matrix whose columns are the sensor x, y, z axes in base_link. Raises ValueError for bad syntax."""
    items = [s for s in re.split(r'[,、;]', text) if s.strip()]
    cols = {}
    for it in items:
        m = ITEM.match(it)
        if not m: raise ValueError(f'axis mapping item {it.strip()!r}: expected "<sign><axis> <direction>", e.g. "+x forward"')
        sign, axis, direction = m.group(1), m.group(2).lower(), m.group(3).lower()
        if direction not in DIRECTIONS: raise ValueError(f'unknown direction {m.group(3)!r} (forward/back/left/right/up/down)')
        if axis in cols: raise ValueError(f'axis {axis} given twice')
        v = DIRECTIONS[direction]
        cols[axis] = tuple(-c for c in v) if sign == '-' else v     # "-y forward": the sensor's -y points forward, so +y points back
    if set(cols) != {'x', 'y', 'z'}: raise ValueError('axis mapping must give x, y and z')
    a = cols['x'], cols['y'], cols['z']
    if len({tuple(abs(c) for c in v) for v in a}) != 3: raise ValueError('two sensor axes point along the same base_link axis')
    return tuple(tuple(a[c][r] for c in range(3)) for r in range(3))


def determinant(m: Matrix) -> float:
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


def matmul(a: Matrix, b: Matrix) -> Matrix:
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))


def transpose(a: Matrix) -> Matrix:
    return tuple(tuple(a[j][i] for j in range(3)) for i in range(3))


def rpy_matrix(roll: float, pitch: float, yaw: float) -> Matrix:
    """R = Rz(yaw) Ry(pitch) Rx(roll) (REP-103 fixed-axis roll, pitch, yaw)."""
    cr, sr, cp, sp, cy, sy = math.cos(roll), math.sin(roll), math.cos(pitch), math.sin(pitch), math.cos(yaw), math.sin(yaw)
    return ((cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr),
            (sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr),
            (-sp, cp * sr, cp * cr))


def quaternion(r: Matrix) -> Tuple[float, float, float, float]:
    """(qx, qy, qz, qw) of a rotation matrix, qw >= 0."""
    t = r[0][0] + r[1][1] + r[2][2]
    if t > 0:
        s = math.sqrt(t + 1) * 2
        q = ((r[2][1] - r[1][2]) / s, (r[0][2] - r[2][0]) / s, (r[1][0] - r[0][1]) / s, s / 4)
    elif r[0][0] > r[1][1] and r[0][0] > r[2][2]:
        s = math.sqrt(1 + r[0][0] - r[1][1] - r[2][2]) * 2
        q = (s / 4, (r[0][1] + r[1][0]) / s, (r[0][2] + r[2][0]) / s, (r[2][1] - r[1][2]) / s)
    elif r[1][1] > r[2][2]:
        s = math.sqrt(1 + r[1][1] - r[0][0] - r[2][2]) * 2
        q = ((r[0][1] + r[1][0]) / s, s / 4, (r[1][2] + r[2][1]) / s, (r[0][2] - r[2][0]) / s)
    else:
        s = math.sqrt(1 + r[2][2] - r[0][0] - r[1][1]) * 2
        q = ((r[0][2] + r[2][0]) / s, (r[1][2] + r[2][1]) / s, s / 4, (r[1][0] - r[0][1]) / s)
    n = math.sqrt(sum(c * c for c in q)); q = tuple(c / n for c in q)
    return q if q[3] >= 0 else tuple(-c for c in q)


def sensor_pose(values: dict, sensor: str) -> Tuple[Matrix, Tuple[float, float, float], List[str], List[str]]:
    """(R, t, defaulted fields, problems) of one sensor in base_link. Unknown fields -> neutral element, listed in defaulted."""
    defaulted, problems = [], []
    def num(key):
        v = values.get(key, UNKNOWN)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v): return float(v)
        defaulted.append(key); return 0
    t = (num(f'{sensor}_mount_x_m'), num(f'{sensor}_mount_y_m'), num(f'{sensor}_mount_z_m'))
    rpy = rpy_matrix(num(f'{sensor}_mount_roll_rad'), num(f'{sensor}_mount_pitch_rad'), num(f'{sensor}_mount_yaw_rad'))
    key = f'{sensor}_axis_mapping'; text = values.get(key, UNKNOWN)
    a = IDENTITY
    if not isinstance(text, str) or text == UNKNOWN:
        defaulted.append(key)
    else:
        try:
            a = parse_axis_mapping(text)
            if determinant(a) < 0:
                problems.append(f'{key} {text!r} is left-handed (not a rotation); base_link axes used instead'); a = IDENTITY; defaulted.append(key)
        except ValueError as e:
            problems.append(f'{key} {text!r}: {e}; base_link axes used instead'); a = IDENTITY; defaulted.append(key)
    return matmul(rpy, a), t, defaulted, problems


def t_lidar_imu(values: dict) -> dict:
    """GLIM T_lidar_imu from /config values. Never raises for missing values (intent.md:105)."""
    rl, tl, dl, pl = sensor_pose(values, 'lidar')
    ri, ti, di, pi_ = sensor_pose(values, 'imu')
    rlt = transpose(rl)
    r = matmul(rlt, ri)
    d = tuple(ti[k] - tl[k] for k in range(3))
    t = tuple(sum(rlt[i][k] * d[k] for k in range(3)) for i in range(3))
    q = quaternion(r)
    return {'T_lidar_imu': [round(v, 9) for v in (*t, *q)], 'defaulted_fields': dl + di, 'problems': pl + pi_,
            'complete': not (dl or di)}


def validate_axis_mapping(text: str) -> Optional[str]:
    """None when the text parses; otherwise the reason (used by the monitor when saving /config)."""
    try:
        parse_axis_mapping(text); return None
    except ValueError as e:
        return str(e)
