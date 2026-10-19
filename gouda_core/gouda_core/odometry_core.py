"""ND-08 relay core (REV-061, DEC-123): body velocity from two successive poses of base_link in odom. No ROS dependency.

GLIM (odometry only) publishes TF odom -> odom_glim -> base_link. The relay (gouda_local_odometry) turns each new
odom_glim -> base_link transform into localization/odometry (IFD-25: header odom, child base_link, pose, twist in base_link).
The velocity is the difference of the two last poses (the same way as the evaluation helper twist_relay.py,
FILE-LOCALIZATION-EVAL); it is an estimate, not a wheel measurement (there is no encoder: DEC-037).
"""
from __future__ import annotations

import math
from typing import Optional, Tuple

Pose = Tuple[float, float, float, float, float, float, float]   # x, y, z, qx, qy, qz, qw
IDENTITY: Pose = (0, 0, 0, 0, 0, 0, 1)


def quat_mul(a, b):
    ax, ay, az, aw = a; bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz)


def rotate(q, v):
    x, y, z = v
    qv = quat_mul(quat_mul(q, (x, y, z, 0.0)), (-q[0], -q[1], -q[2], q[3]))
    return qv[:3]


def compose(a: Pose, b: Pose) -> Pose:
    """a * b (parent->mid composed with mid->child)."""
    t = rotate(a[3:], b[:3])
    q = quat_mul(a[3:], b[3:])
    return (a[0] + t[0], a[1] + t[1], a[2] + t[2], *q)


def yaw(q) -> float:
    x, y, z, w = q
    return math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


def body_twist(prev: Pose, t_prev: float, cur: Pose, t_cur: float) -> Optional[Tuple[float, float, float, float]]:
    """(vx, vy, vz, wz) in the base_link frame of prev, or None when the time does not advance."""
    dt = t_cur - t_prev
    if not dt > 0:
        return None
    d = (cur[0] - prev[0], cur[1] - prev[1], cur[2] - prev[2])
    inv = (-prev[3], -prev[4], -prev[5], prev[6])
    v = rotate(inv, d)
    dyaw = math.atan2(math.sin(yaw(cur[3:]) - yaw(prev[3:])), math.cos(yaw(cur[3:]) - yaw(prev[3:])))
    return v[0] / dt, v[1] / dt, v[2] / dt, dyaw / dt
