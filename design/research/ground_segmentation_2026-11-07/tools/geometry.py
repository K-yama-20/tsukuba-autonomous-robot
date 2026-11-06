"""Rotations and transforms (REP-103: x forward, y left, z up; roll, pitch, yaw about x, y, z; R = Rz(yaw) Ry(pitch) Rx(roll))."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


def rx(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=np.float64)


def ry(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=np.float64)


def rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=np.float64)


def rpy(roll, pitch, yaw):
    return rz(yaw) @ ry(pitch) @ rx(roll)


def quat_to_mat(x, y, z, w):
    n = math.sqrt(x * x + y * y + z * z + w * w)
    x, y, z, w = x / n, y / n, z / n, w / n
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


@dataclass
class Transform:
    """p_parent = R p_child + t."""
    R: np.ndarray
    t: np.ndarray

    def __matmul__(self, o: 'Transform') -> 'Transform':
        return Transform(self.R @ o.R, self.R @ o.t + self.t)

    def inv(self) -> 'Transform':
        return Transform(self.R.T, -self.R.T @ self.t)


def identity() -> Transform:
    return Transform(np.eye(3), np.zeros(3))


def transform_points(T: Transform, pts: np.ndarray) -> np.ndarray:
    """In float32, like tf2_sensor_msgs doTransform (Eigen::Affine3f) on a PointCloud2 with float32 x, y, z."""
    R = T.R.astype(np.float32); t = T.t.astype(np.float32)
    return (pts.astype(np.float32) @ R.T + t).astype(np.float32)


def tf_tree(transforms) -> dict:
    """{child: (parent, Transform)} from decoded geometry_msgs/TransformStamped objects (/tf_static)."""
    out = {}
    for tr in transforms:
        q = tr.transform.rotation; p = tr.transform.translation
        out[tr.child_frame_id] = (tr.header.frame_id, Transform(quat_to_mat(q.x, q.y, q.z, q.w), np.array([p.x, p.y, p.z])))
    return out


def lookup(tree: dict, target: str, source: str) -> Transform:
    """T_target_source (points in source -> target) from a tree of {child: (parent, T_parent_child)}."""
    def chain(frame):
        c = [(frame, identity())]
        T = identity(); f = frame
        while f in tree:
            parent, Tpc = tree[f]
            T = Tpc @ T; f = parent
            c.append((f, T))
            if len(c) > 64:
                raise ValueError('loop in the tf tree')
        return c        # [(ancestor, T_ancestor_frame)]
    cs = dict(chain(source)); ct = dict(chain(target))
    for f, T_f_src in cs.items():
        if f in ct:
            return ct[f].inv() @ T_f_src
    raise KeyError(f'no common ancestor of {target} and {source} in /tf_static')
