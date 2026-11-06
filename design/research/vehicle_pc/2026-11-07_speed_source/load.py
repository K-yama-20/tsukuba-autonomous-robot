"""Loaders for the 2026-11-07 odometry comparison (A: pose difference, B: GLIM v_world_imu).

Frames: GLIM T_lidar_imu has identity rotation (config_sensors.json), so IMU and LiDAR axes coincide.
Vehicle forward = LiDAR -y (analyze_turn.py, intent.md); checked again in analyze_cmp.py.
"""
import csv, os
import numpy as np


def quat_to_R(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def yaw_of_R(R):
    return np.arctan2(R[1, 0], R[0, 0])


def load_tum(path):
    a = np.loadtxt(path)
    t = a[:, 0]; p = a[:, 1:4]; R = np.array([quat_to_R(q) for q in a[:, 4:8]])
    return t, p, R


def load_dump(path):
    """data.txt of one submap -> list of frames (stamp, T_odom_lidar, T_world_lidar, v_world_imu), de-duplicated by stamp."""
    lines = open(path).read().splitlines()
    frames = []; i = 0
    while i < len(lines):
        l = lines[i].strip()
        if l.startswith('frame_') and not l.startswith('frame_id'):
            f = {}
            j = i + 1
            while j < len(lines) and not (lines[j].strip().startswith('frame_') and not lines[j].strip().startswith('frame_id')):
                s = lines[j].strip()
                if s.startswith('stamp:'): f['stamp'] = float(s.split()[1])
                elif s.startswith('T_odom_lidar:') or s.startswith('T_world_lidar:'):
                    k = s[:-1]; f[k] = np.array([[float(v) for v in lines[j + r].split()] for r in range(1, 5)]); j += 4
                elif s.startswith('v_world_imu:'): f['v'] = np.array([float(v) for v in s.split()[1:4]])
                j += 1
            frames.append(f); i = j
        else:
            i += 1
    seen = {}; dup = 0
    for f in frames:
        if f['stamp'] in seen: dup += 1
        seen[f['stamp']] = f
    out = [seen[k] for k in sorted(seen)]
    return out, len(frames), dup


def load_imu(path):
    r = list(csv.DictReader(open(path)))
    return {k: np.array([float(x[k]) for x in r]) for k in ('t', 'ax', 'ay', 'az', 'gx', 'gy', 'gz', 'rx_t')}


def load_esp(path):
    r = list(csv.DictReader(open(path)))
    return (np.array([float(x['t']) for x in r]), np.array([int(x['applied_x_q10000'] or 0) / 1e4 for x in r]),
            np.array([int(x['applied_y_q10000'] or 0) / 1e4 for x in r]))
