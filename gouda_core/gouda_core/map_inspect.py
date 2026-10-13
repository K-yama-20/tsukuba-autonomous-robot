"""Measurement analysis of one source map (原図) for the moving mapping field test (TS-34; DEC-099, DEC-100).

    python3 -m gouda_core.map_inspect <maps>/<origin_id>/source --cell <m> --radii <m> [<m> ...]

Reports, from the GLIM dump only (no ROS):
  - GLIM's processed frame rate: traj_lidar.txt has one line per frame GLIM's odometry processed (the XT-32 sends 10 Hz;
    fewer lines mean frames were lost on the way or skipped; G-DDS), the longest gap, the duration;
  - the path: length (the sum of the steps between frames, so it includes the jitter of a sensor standing still) and the
    largest distance from the start (a map made standing still has almost none: use this to tell whether it moved);
  - submaps, points, and the point density (points per square metre) within each radius of the path;
  - ground visibility (DEC-099): for each radius (measured on the grid, accurate to about one cell), the share of the cells of a horizontal grid (--cell) within that radius
    of the path that hold at least one point, and the share that hold a point within --band of the lowest point of the
    cell's 3x3 neighbourhood. The XT-32 does not see the ground close around itself (its lowest beam points down at a
    limited angle), so cells near the path are seen only from farther away while moving.
The radii, the cell and the band are given by the person running the test (no defaults are assumed).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

from gouda_core import map_convert as mc


def read_trajectory(source: Path) -> 'np.ndarray':
    """N x 4 (stamp, x, y, z) from traj_lidar.txt (stamp x y z qx qy qz qw per line)."""
    f = Path(source) / 'traj_lidar.txt'
    if not f.is_file():
        raise ValueError(f'{f} not found')
    rows = [line.split() for line in f.read_text().splitlines() if line.strip()]
    return np.array([[float(r[0]), float(r[1]), float(r[2]), float(r[3])] for r in rows], dtype=np.float64).reshape(-1, 4)


def frame_rate(traj: 'np.ndarray') -> dict:
    if traj.shape[0] < 2:
        return {'frames': int(traj.shape[0]), 'duration_s': None, 'rate_hz': None, 'max_gap_s': None}
    t = traj[:, 0]; d = float(t[-1] - t[0])
    return {'frames': int(traj.shape[0]), 'duration_s': d, 'rate_hz': (traj.shape[0] - 1) / d if d > 0 else None, 'max_gap_s': float(np.diff(t).max())}


def path_stats(traj: 'np.ndarray') -> dict:
    xy = traj[:, 1:3]
    if xy.shape[0] == 0:
        return {'length_m': 0.0, 'max_distance_from_start_m': 0.0}
    return {'length_m': float(np.hypot(*np.diff(xy, axis=0).T).sum()) if xy.shape[0] > 1 else 0.0,
            'max_distance_from_start_m': float(np.hypot(*(xy - xy[0]).T).max())}


def path_distance_grid(xy: 'np.ndarray', minx: float, miny: float, w: int, h: int, cell: float, max_r: float) -> 'np.ndarray':
    """Distance [m] from each grid cell to the path (8-neighbour chamfer over the grid; inf beyond max_r).

    The path is drawn into the grid with samples every half cell along each segment; distances are therefore accurate to
    about one cell."""
    on_path = np.zeros((h, w), dtype=bool)
    for (x0, y0), (x1, y1) in zip(xy[:-1], xy[1:]) if xy.shape[0] > 1 else [((xy[0, 0], xy[0, 1]), (xy[0, 0], xy[0, 1]))]:
        n = max(int(math.ceil(math.hypot(x1 - x0, y1 - y0) / (cell / 2))), 1)
        t = np.linspace(0, 1, n + 1)
        ix = np.clip(((x0 + (x1 - x0) * t - minx) / cell).astype(np.int64), 0, w - 1); iy = np.clip(((y0 + (y1 - y0) * t - miny) / cell).astype(np.int64), 0, h - 1)
        on_path[iy, ix] = True
    dist = np.where(on_path, 0.0, np.inf)
    for _ in range(int(math.ceil(max_r / cell)) + 1):
        prev = dist
        for dy, dx in mc._NEIGHBOURS:
            dist = np.minimum(dist, mc._shifted(prev, dy, dx, np.inf) + cell * math.hypot(dy, dx))
        if np.array_equal(prev, dist): break
    return dist


def inspect(source: Path, cell: float, radii: list, band: float) -> dict:
    if cell <= 0 or band < 0 or not radii or any(r <= 0 for r in radii):
        raise ValueError('cell and radii must be positive and band not negative')
    traj = read_trajectory(source)
    report = {'source': str(source), 'glim_frames': frame_rate(traj), 'path': path_stats(traj), 'cell_m': cell, 'band_m': band}
    try:
        submaps = mc.read_dump(source); pts = mc.world_points(submaps)
    except ValueError as e:
        report['points'] = {'error': str(e)}; return report
    report['submaps'] = len(submaps); report['points_total'] = int(pts.shape[0])
    xy = traj[:, 1:3]
    # cells of a horizontal grid around the whole map
    minx, miny = min(pts[:, 0].min(), xy[:, 0].min()), min(pts[:, 1].min(), xy[:, 1].min())
    w = int(math.floor((max(pts[:, 0].max(), xy[:, 0].max()) - minx) / cell)) + 1; h = int(math.floor((max(pts[:, 1].max(), xy[:, 1].max()) - miny) / cell)) + 1
    ix = np.clip(((pts[:, 0] - minx) / cell).astype(np.int64), 0, w - 1); iy = np.clip(((pts[:, 1] - miny) / cell).astype(np.int64), 0, h - 1)
    zmin = np.full((h, w), np.inf); np.minimum.at(zmin, (iy, ix), pts[:, 2])
    low = np.full((h, w), np.inf)   # lowest point of the 3x3 neighbourhood
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            low = np.minimum(low, mc._shifted(zmin, dy, dx, np.inf))
    near_low = np.zeros((h, w), dtype=bool)
    ok = np.isfinite(low[iy, ix]) & (pts[:, 2] - low[iy, ix] <= band)
    near_low[iy[ok], ix[ok]] = True
    d_cell = path_distance_grid(xy, minx, miny, w, h, cell, max(radii))
    d_pt = d_cell[iy, ix]
    rows = []
    for r in sorted(radii):
        cells = d_cell <= r; area = cells.sum() * cell * cell
        rows.append({'radius_m': r, 'cells': int(cells.sum()), 'cells_with_points': int((cells & np.isfinite(zmin)).sum()),
                     'cells_with_low_points': int((cells & near_low).sum()),
                     'share_with_points': float((cells & np.isfinite(zmin)).sum() / cells.sum()) if cells.sum() else None,
                     'share_with_low_points': float((cells & near_low).sum() / cells.sum()) if cells.sum() else None,
                     'points': int((d_pt <= r).sum()), 'points_per_m2': float((d_pt <= r).sum() / area) if area else None})
    report['near_path'] = rows
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('source', type=Path, help='<maps>/<origin_id>/source (a GLIM dump)')
    ap.add_argument('--cell', type=float, required=True, help='horizontal grid cell [m]')
    ap.add_argument('--radii', type=float, nargs='+', required=True, help='distances from the path [m]')
    ap.add_argument('--band', type=float, required=True, help='a point within this height of the lowest point of its 3x3 neighbourhood counts as low [m]')
    a = ap.parse_args(argv)
    json.dump(inspect(a.source, a.cell, a.radii, a.band), sys.stdout, ensure_ascii=False, indent=1); sys.stdout.write('\n')


if __name__ == '__main__':
    main()
