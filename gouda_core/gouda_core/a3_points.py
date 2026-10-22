"""The point pre-processing of ND-07's trial A3 (REV-148, DEC-283 plan a). No ROS dependency.

Replaces the upstream chain pcl_ros CropBox -> CropBox (negative) -> VoxelGrid of gouda_localization_a3.launch.py with the same
three steps on x, y, z only, in one process:
  keep the points inside the box +-points_far_crop_m (PRM-80), drop the points inside +-points_near_crop_m (PRM-79, the vehicle and
  very near points), and replace the points of each cube of points_voxel_leaf_m (PRM-81) by their centroid, dropping the cubes with
  fewer than points_voxel_min_points points (PRM-102: 2, as pcl_ros VoxelGrid's min_points_per_voxel did; REV-151, DEC-284).
Why: pcl's VoxelGrid on the XT-32 cloud (x, y, z, intensity FLOAT32, ring UINT16, timestamp FLOAT64 at offset 18) crashed with a
segmentation fault once the clouds arrived at 10 Hz, and corrupted the heap before (第119便); with x, y, z only it did not.
The NDT reads x, y, z only. Box limits are inclusive and cubes are indexed by floor(p / leaf), as pcl's CropBox and VoxelGrid do.
Points with a non-finite coordinate are dropped. Every number comes from the settings; nothing is hard-coded (RQ-I076).
"""
from __future__ import annotations

import numpy as np

FLOAT32 = 7   # sensor_msgs/PointField.FLOAT32 (message constant, not a setting)


def xyz_view(data, point_step: int, width_height: int, offsets: dict, big_endian: bool) -> np.ndarray:
    """(N, 3) float64 copy of x, y, z read from a PointCloud2 buffer (bytes or array; any point_step and field layout)."""
    if big_endian:
        raise ValueError('big-endian point clouds are not supported')
    dt = np.dtype({'names': ['x', 'y', 'z'], 'formats': ['<f4'] * 3, 'offsets': [offsets['x'], offsets['y'], offsets['z']],
                   'itemsize': point_step})
    rec = np.frombuffer(data, dtype=dt, count=width_height)
    return np.stack([rec['x'], rec['y'], rec['z']], axis=1).astype(np.float64)


def xyz_offsets(fields) -> dict:
    """{'x': offset, 'y': ..., 'z': ...} of FLOAT32 x, y, z fields (objects with name, offset, datatype, count); raises otherwise."""
    out = {}
    for f in fields:
        if f.name in ('x', 'y', 'z'):
            if f.datatype != FLOAT32 or f.count != 1:
                raise ValueError(f'field {f.name} is not one FLOAT32 (datatype {f.datatype}, count {f.count})')
            out[f.name] = f.offset
    missing = [n for n in ('x', 'y', 'z') if n not in out]
    if missing:
        raise ValueError(f'fields missing: {missing}')
    return out


def filter_points(p: np.ndarray, near_m: float, far_m: float, leaf_m: float, min_points: int) -> np.ndarray:
    """(M, 3) float32: crop (keep inside +-far_m, drop inside +-near_m; inclusive) and voxel centroids of leaf_m cubes that
    hold at least min_points points."""
    if not (0.0 <= near_m < far_m) or leaf_m <= 0.0 or min_points < 1:
        raise ValueError(f'invalid settings: near {near_m}, far {far_m}, leaf {leaf_m}, min points {min_points}')
    p = p[np.isfinite(p).all(axis=1)]
    a = np.abs(p)
    p = p[(a <= far_m).all(axis=1) & ~(a <= near_m).all(axis=1)]
    if len(p) == 0:
        return np.zeros((0, 3), dtype=np.float32)
    idx = np.floor(p / leaf_m).astype(np.int64)
    _, inverse, counts = np.unique(idx, axis=0, return_inverse=True, return_counts=True)
    sums = np.zeros((len(counts), 3))
    np.add.at(sums, inverse.reshape(-1), p)
    keep = counts >= min_points
    return (sums[keep] / counts[keep, None]).astype(np.float32)
