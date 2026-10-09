"""Map conversion core (ND-05 gouda_map_creator): GLIM dump (原図) -> Nav2 2D occupancy grid (map.yaml + map.pgm).

Reader: a GLIM 1.2.2 dump holds one %06d/ directory per submap with data.txt (id, T_world_origin, frame_id ...) and the
submap point cloud saved by gtsam_points PointCloud::save_compact (points_compact.bin: float32 x,y,z per point, in the
submap frame). The point-file layout is taken from the gtsam_points sources; it has NOT yet been confirmed with a real
dump from the vehicle (no sensor data so far). The reader therefore validates sizes and refuses, with a reason, any
layout it cannot verify instead of guessing (RQ-I015: nothing is invented).

Conversion: points are transformed with T_world_origin into the map frame, a height band relative to the ground
selects obstacle points, and a grid with the given resolution is marked occupied where the obstacle count reaches a
threshold, free where only ground points were seen, unknown elsewhere. All settings come in as a dict (declared
parameters PRM-33..36); nothing numeric is hard-coded. Output follows the Nav2 map_server format.
"""
from __future__ import annotations

import math
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

SUBMAP_DIR = re.compile(r'^\d{6}$')
CONVERTER_VERSION = 'gouda_map_convert 0.1 (height-band occupancy)'


@dataclass
class Submap:
    sid: int
    t_world_origin: 'np.ndarray'   # 4x4
    points: 'np.ndarray'           # Nx3 float32, submap frame


def _parse_matrix(lines: list, start: int) -> 'np.ndarray':
    rows = []
    for i in range(start, start + 4):
        rows.append([float(x) for x in lines[i].split()])
    return np.array(rows, dtype=np.float64)


def read_submap(dir_path: Path) -> Submap:
    d = Path(dir_path)
    text = (d / 'data.txt').read_text().splitlines()
    sid = None; t = None
    for i, line in enumerate(text):
        if line.startswith('id:'): sid = int(line.split(':', 1)[1].strip())
        if line.startswith('T_world_origin:'):
            t = _parse_matrix(text, i + 1)
    if sid is None or t is None:
        raise ValueError(f'{d.name}/data.txt: id or T_world_origin not found (layout not as expected)')
    pf = d / 'points_compact.bin'
    if not pf.is_file():
        raise ValueError(f'{d.name}: points_compact.bin not found (unverified dump layout; conversion refused)')
    raw = pf.read_bytes()
    if len(raw) % 12 != 0:
        raise ValueError(f'{d.name}/points_compact.bin: size {len(raw)} is not a multiple of 12 bytes (float32 xyz expected)')
    pts = np.frombuffer(raw, dtype=np.float32).reshape(-1, 3) if raw else np.zeros((0, 3), dtype=np.float32)
    if pts.size and not np.isfinite(pts).all():
        raise ValueError(f'{d.name}/points_compact.bin: non-finite values')
    return Submap(sid, t, pts)


def read_dump(dump_dir: Path) -> list:
    d = Path(dump_dir)
    subs = sorted(x for x in d.iterdir() if x.is_dir() and SUBMAP_DIR.match(x.name))
    if not subs:
        raise ValueError('dump has no submap directory: no sensor data was received during mapping; nothing to convert')
    return [read_submap(s) for s in subs]


@dataclass
class GridResult:
    resolution: float
    origin_x: float
    origin_y: float
    width: int
    height: int
    occupied: int
    free: int
    unknown: int
    points_total: int
    points_obstacle: int
    points_ground: int


def _require(settings: dict, keys: Iterable[str]) -> dict:
    missing = [k for k in keys if settings.get(k) is None]
    if missing:
        raise ValueError(f'conversion settings missing: {missing} (declared parameters must be provided; no defaults)')
    return {k: float(settings[k]) for k in keys}


def build_grid(submaps: list, settings: dict):
    """Return (grid uint8 array HxW with 0 free / 100 occupied / 255 unknown in map_server PGM terms, GridResult).

    settings: map_resolution_m, ground_band_max_m (points below this height are ground), obstacle_band_min_m,
    obstacle_band_max_m (points within are obstacles), occupied_min_points (cell occupied at/above this count).
    Heights are relative to the map frame's z (GLIM's world frame; the ground offset is the base_link height, PRM-05).
    """
    s = _require(settings, ['map_resolution_m', 'ground_band_max_m', 'obstacle_band_min_m', 'obstacle_band_max_m', 'occupied_min_points'])
    res = s['map_resolution_m']
    if res <= 0: raise ValueError('map_resolution_m must be positive')
    world = []
    for sm in submaps:
        if sm.points.shape[0] == 0: continue
        p = sm.points.astype(np.float64)
        w = p @ sm.t_world_origin[:3, :3].T + sm.t_world_origin[:3, 3]
        world.append(w)
    if not world:
        raise ValueError('submaps contain no points; nothing to convert')
    pts = np.concatenate(world)
    ground = pts[:, 2] <= s['ground_band_max_m']
    obst = (pts[:, 2] >= s['obstacle_band_min_m']) & (pts[:, 2] <= s['obstacle_band_max_m'])
    sel = pts[ground | obst]
    if sel.shape[0] == 0:
        raise ValueError('no points inside the ground/obstacle height bands')
    minx, miny = sel[:, 0].min(), sel[:, 1].min()
    maxx, maxy = sel[:, 0].max(), sel[:, 1].max()
    width = int(math.floor((maxx - minx) / res)) + 1; height = int(math.floor((maxy - miny) / res)) + 1
    if width * height > 50_000_000:
        raise ValueError(f'grid too large: {width}x{height} cells at {res} m')
    ix = np.clip(((pts[:, 0] - minx) / res).astype(np.int64), 0, width - 1)
    iy = np.clip(((pts[:, 1] - miny) / res).astype(np.int64), 0, height - 1)
    occ_count = np.zeros((height, width), dtype=np.int32); gnd_count = np.zeros((height, width), dtype=np.int32)
    np.add.at(occ_count, (iy[obst], ix[obst]), 1); np.add.at(gnd_count, (iy[ground], ix[ground]), 1)
    grid = np.full((height, width), 255, dtype=np.uint8)            # unknown
    grid[gnd_count > 0] = 0                                           # free (ground seen)
    grid[occ_count >= int(s['occupied_min_points'])] = 100           # occupied
    result = GridResult(res, float(minx), float(miny), width, height, int((grid == 100).sum()), int((grid == 0).sum()), int((grid == 255).sum()),
                        int(pts.shape[0]), int(obst.sum()), int(ground.sum()))
    return grid, result


def write_map(grid, result: GridResult, out_dir: Path, name: str = 'map') -> None:
    """Write Nav2 map_server files: <name>.pgm (P5, row 0 = top = max y) and <name>.yaml (trinary mode)."""
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    img = np.empty_like(grid)
    img[grid == 0] = 254; img[grid == 100] = 0; img[grid == 255] = 205   # map_server conventions: free white, occupied black, unknown grey
    img = img[::-1, :]                                                  # pgm row 0 is the top (largest y)
    header = f'P5\n{result.width} {result.height}\n255\n'.encode('ascii')
    (out_dir / f'{name}.pgm').write_bytes(header + img.tobytes())
    (out_dir / f'{name}.yaml').write_text(
        f'image: {name}.pgm\nmode: trinary\nresolution: {result.resolution}\norigin: [{result.origin_x}, {result.origin_y}, 0.0]\n'
        f'negate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.196\n', encoding='utf-8')


def convert(dump_dir: Path, out_dir: Path, settings: dict) -> dict:
    """Full conversion; raises ValueError with a reason when the input cannot be converted (caller discards output)."""
    if np is None:
        raise RuntimeError('numpy is required for map conversion')
    submaps = read_dump(dump_dir)
    grid, result = build_grid(submaps, settings)
    write_map(grid, result, out_dir)
    return {'converter': CONVERTER_VERSION, 'submaps': len(submaps), **result.__dict__}
