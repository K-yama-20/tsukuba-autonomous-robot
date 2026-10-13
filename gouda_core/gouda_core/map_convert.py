"""Map conversion core (ND-05 gouda_map_creator): GLIM dump (原図) -> the maps of one converted revision.

Reader: a GLIM 1.2.2 dump holds one %06d/ directory per submap with data.txt (id, T_world_origin, frame_id ...) and the
submap point cloud saved by gtsam_points PointCloud::save_compact (points_compact.bin: float32 x,y,z per point, in the
submap frame; layout confirmed with the dumps of 2026-10-13). The reader validates sizes and refuses, with a reason, any
layout it cannot verify instead of guessing (RQ-I015: nothing is invented).

Heights are measured from the ground (DEC-093). GLIM's map frame has its origin at the sensor pose at the start, so the
ground is not at z=0 and may slope. The ground is estimated from the points themselves (docs/map_conversion.md):
  - a ground grid (cell PRM-62) keeps the lowest point of each cell;
  - the ground height is the lower envelope of those lowest points with a slope limit (PRM-63): a cell's ground is never
    above its own lowest point nor above a neighbour's ground plus the allowed rise. The lowest point of a cell that only
    sees an obstacle (a car body, a wall) therefore does not lift the ground there;
  - cells without points get the envelope only within PRM-64 of a cell with points; farther away the ground is unknown
    and points there are not classified (the XT-32 may not see the ground everywhere: the measurement DEC-099);
  - a point's ground is the bilinear interpolation of the cell centres.

Products of one conversion (all from the same points and settings; RQ-I008/RQ-I009):
  map.yaml + map.pgm     Nav2 2D occupancy grid (PRM-33 resolution; ground band PRM-34; obstacle band PRM-35..36;
                         occupied at PRM-38 obstacle points per cell). Only this map is used for driving.
  pointmap.pcd           3D point map in the map frame (all submap points, float32 x y z, binary PCD) for localisation (DEC-095).
  terrain.json, slope.png, step.png, height.png
                         views for the human (DEC-097 A: not used for driving): ground slope and step height per ground
                         cell, and the highest point above the ground per 2D cell (a top view of the 3D map).
All settings come in as a dict (declared parameters); nothing numeric is hard-coded.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

from gouda_core import png as pngmod

SUBMAP_DIR = re.compile(r'^\d{6}$')
CONVERTER_VERSION = 'gouda_map_convert 0.2 (ground-relative height bands; 3D point map; terrain views)'
SETTING_KEYS = ['map_resolution_m', 'ground_band_max_m', 'obstacle_band_min_m', 'obstacle_band_max_m', 'occupied_min_points',
                'ground_cell_m', 'ground_max_slope_deg', 'ground_fill_radius_m']
NAV2_FILES = ['map.yaml', 'map.pgm']
PRODUCT_FILES = NAV2_FILES + ['pointmap.pcd', 'terrain.json', 'slope.png', 'step.png', 'height.png']
VIEW_FILES = ['slope.png', 'step.png', 'height.png']


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
        if line.startswith('id:') and sid is None: sid = int(line.split(':', 1)[1].strip())
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


def world_points(submaps: list) -> 'np.ndarray':
    """All submap points in the map frame (N x 3, float64)."""
    world = []
    for sm in submaps:
        if sm.points.shape[0] == 0: continue
        p = sm.points.astype(np.float64)
        world.append(p @ sm.t_world_origin[:3, :3].T + sm.t_world_origin[:3, 3])
    if not world:
        raise ValueError('submaps contain no points; nothing to convert')
    return np.concatenate(world)


def _require(settings: dict, keys: Iterable[str]) -> dict:
    missing = [k for k in keys if settings.get(k) is None]
    if missing:
        raise ValueError(f'conversion settings missing: {missing} (declared parameters must be provided; no defaults)')
    return {k: float(settings[k]) for k in keys}


# ---------------------------------------------------------------- ground

_NEIGHBOURS = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy, dx) != (0, 0)]


def _shifted(a: 'np.ndarray', dy: int, dx: int, fill: float) -> 'np.ndarray':
    """b[y, x] = a[y + dy, x + dx] (fill outside)."""
    h, w = a.shape
    p = np.full((h + 2, w + 2), fill, dtype=a.dtype); p[1:-1, 1:-1] = a
    return p[1 + dy:1 + dy + h, 1 + dx:1 + dx + w]


@dataclass
class Ground:
    cell: float
    origin_x: float          # lower-left corner of cell (0, 0)
    origin_y: float
    zmin: 'np.ndarray'       # H x W lowest point per cell, NaN where the cell has no point
    height: 'np.ndarray'     # H x W ground height (slope-limited lower envelope), NaN where unknown
    filled_cells: int        # cells without points that got a ground height (within the fill radius)

    @property
    def observed(self) -> 'np.ndarray':
        return np.isfinite(self.zmin)

    def at(self, x: 'np.ndarray', y: 'np.ndarray') -> 'np.ndarray':
        """Ground height at points (bilinear over cell centres; unknown neighbours are left out; NaN if all unknown)."""
        h, w = self.height.shape
        fx = (x - self.origin_x) / self.cell - 0.5; fy = (y - self.origin_y) / self.cell - 0.5
        x0 = np.floor(fx).astype(np.int64); y0 = np.floor(fy).astype(np.int64); tx = fx - x0; ty = fy - y0
        num = np.zeros_like(fx); den = np.zeros_like(fx)
        for cx, cy, wt in ((x0, y0, (1 - tx) * (1 - ty)), (x0 + 1, y0, tx * (1 - ty)), (x0, y0 + 1, (1 - tx) * ty), (x0 + 1, y0 + 1, tx * ty)):
            inside = (cx >= 0) & (cx < w) & (cy >= 0) & (cy < h)
            v = np.full(fx.shape, np.nan); v[inside] = self.height[cy[inside], cx[inside]]
            ok = np.isfinite(v) & (wt > 0)
            num[ok] += wt[ok] * v[ok]; den[ok] += wt[ok]
        out = np.full(fx.shape, np.nan); m = den > 0; out[m] = num[m] / den[m]
        return out


def estimate_ground(pts: 'np.ndarray', cell: float, max_slope_deg: float, fill_radius: float) -> Ground:
    if cell <= 0: raise ValueError('ground_cell_m must be positive')
    if not 0 < math.radians(max_slope_deg) < math.pi / 2: raise ValueError('ground_max_slope_deg must be between 0 and 90 degrees')
    if fill_radius < 0: raise ValueError('ground_fill_radius_m must not be negative')
    minx, miny = pts[:, 0].min(), pts[:, 1].min()
    w = int(math.floor((pts[:, 0].max() - minx) / cell)) + 1; h = int(math.floor((pts[:, 1].max() - miny) / cell)) + 1
    if w * h > 20_000_000:
        raise ValueError(f'ground grid too large: {w}x{h} cells at {cell} m')
    ix = np.clip(((pts[:, 0] - minx) / cell).astype(np.int64), 0, w - 1); iy = np.clip(((pts[:, 1] - miny) / cell).astype(np.int64), 0, h - 1)
    zmin = np.full((h, w), np.inf); np.minimum.at(zmin, (iy, ix), pts[:, 2])
    observed = np.isfinite(zmin)
    # distance (8-neighbour chamfer) from the nearest observed cell, needed only up to the fill radius
    dist = np.where(observed, 0.0, np.inf)
    for _ in range(int(math.ceil(fill_radius / cell)) + 1):
        prev = dist
        for dy, dx in _NEIGHBOURS:
            dist = np.minimum(dist, _shifted(prev, dy, dx, np.inf) + cell * math.hypot(dy, dx))
        if np.array_equal(prev, dist): break
    allowed = observed | (dist <= fill_radius)
    # slope-limited lower envelope inside the allowed cells (Jacobi relaxation until nothing changes)
    rise = math.tan(math.radians(max_slope_deg)) * cell
    g = np.where(observed, zmin, np.inf)
    for _ in range(h + w + 1):
        prev = g
        for dy, dx in _NEIGHBOURS:
            cand = _shifted(prev, dy, dx, np.inf) + rise * math.hypot(dy, dx)
            g = np.where(allowed, np.minimum(g, cand), np.inf)
        if np.array_equal(prev, g): break
    g = np.where(np.isfinite(g), g, np.nan)
    return Ground(cell, float(minx), float(miny), np.where(observed, zmin, np.nan), g, int((np.isfinite(g) & ~observed).sum()))


# ---------------------------------------------------------------- 2D occupancy grid (Nav2)

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
    points_between: int        # above the ground band, below the obstacle band
    points_above: int          # above the obstacle band (branches, ceilings)
    points_no_ground: int      # where the ground is unknown (not classified)


def classify(pts: 'np.ndarray', ground: Ground, s: dict):
    """Height above the ground (NaN where unknown), ground mask, obstacle mask."""
    hag = pts[:, 2] - ground.at(pts[:, 0], pts[:, 1])
    known = np.isfinite(hag)
    gnd = known & (hag <= s['ground_band_max_m'])
    obst = known & (hag >= s['obstacle_band_min_m']) & (hag <= s['obstacle_band_max_m'])
    return hag, gnd, obst


def build_grid(pts: 'np.ndarray', hag: 'np.ndarray', gnd: 'np.ndarray', obst: 'np.ndarray', s: dict):
    """Return (grid uint8 HxW with 0 free / 100 occupied / 255 unknown, GridResult). Occupied wins over free."""
    res = s['map_resolution_m']
    if res <= 0: raise ValueError('map_resolution_m must be positive')
    sel = pts[gnd | obst]
    if sel.shape[0] == 0:
        raise ValueError('no points inside the ground/obstacle height bands')
    minx, miny = sel[:, 0].min(), sel[:, 1].min()
    width = int(math.floor((sel[:, 0].max() - minx) / res)) + 1; height = int(math.floor((sel[:, 1].max() - miny) / res)) + 1
    if width * height > 50_000_000:
        raise ValueError(f'grid too large: {width}x{height} cells at {res} m')
    inside = (pts[:, 0] >= minx) & (pts[:, 1] >= miny) & (pts[:, 0] < minx + width * res) & (pts[:, 1] < miny + height * res)
    ix = np.clip(((pts[:, 0] - minx) / res).astype(np.int64), 0, width - 1)
    iy = np.clip(((pts[:, 1] - miny) / res).astype(np.int64), 0, height - 1)
    occ_count = np.zeros((height, width), dtype=np.int32); gnd_count = np.zeros((height, width), dtype=np.int32)
    o = obst & inside; g = gnd & inside
    np.add.at(occ_count, (iy[o], ix[o]), 1); np.add.at(gnd_count, (iy[g], ix[g]), 1)
    grid = np.full((height, width), 255, dtype=np.uint8)            # unknown
    grid[gnd_count > 0] = 0                                           # free (ground seen)
    grid[occ_count >= int(s['occupied_min_points'])] = 100           # occupied
    known = np.isfinite(hag)
    result = GridResult(res, float(minx), float(miny), width, height, int((grid == 100).sum()), int((grid == 0).sum()), int((grid == 255).sum()),
                        int(pts.shape[0]), int(obst.sum()), int(gnd.sum()),
                        int((known & ~gnd & (hag < s['obstacle_band_min_m'])).sum()), int((known & (hag > s['obstacle_band_max_m'])).sum()), int((~known).sum()))
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


# ---------------------------------------------------------------- 3D point map

def write_pcd(pts: 'np.ndarray', path: Path) -> None:
    """Binary PCD (x y z float32) in the map frame. The header follows the example of the PCD file format specification
    (pointclouds.org), which writes the format version as ".7"; PCL's reader accepts it."""
    data = np.ascontiguousarray(pts, dtype='<f4')
    header = ('# .PCD v.7 - Gouda 3D point map (map frame)\nVERSION .7\nFIELDS x y z\nSIZE 4 4 4\nTYPE F F F\nCOUNT 1 1 1\n'
              f'WIDTH {data.shape[0]}\nHEIGHT 1\nVIEWPOINT 0 0 0 1 0 0 0\nPOINTS {data.shape[0]}\nDATA binary\n')
    Path(path).write_bytes(header.encode('ascii') + data.tobytes())


# ---------------------------------------------------------------- terrain views (display only, DEC-097 A)

def ground_like(ground: Ground, s: dict) -> 'np.ndarray':
    """Cells whose lowest point is ground (within the ground band of the envelope): the observed ground surface."""
    with np.errstate(invalid='ignore'):
        return ground.observed & (ground.zmin - ground.height <= s['ground_band_max_m'])


def terrain(ground: Ground, s: dict) -> dict:
    """Slope [deg] and step [m] per ground cell from the observed ground surface (NaN where not observed).

    The step is the largest height difference to a side neighbour; on a slope it includes the rise over one cell."""
    gl = ground_like(ground, s); z = np.where(gl, ground.zmin, np.nan); c = ground.cell
    zx1, zx0 = _shifted(z, 0, 1, np.nan), _shifted(z, 0, -1, np.nan); zy1, zy0 = _shifted(z, 1, 0, np.nan), _shifted(z, -1, 0, np.nan)
    def slope_1d(a1, a0):   # central difference, one-sided at the edge of the observed surface
        with np.errstate(invalid='ignore'):
            return np.where(np.isfinite(a1) & np.isfinite(a0), (a1 - a0) / (2 * c), np.where(np.isfinite(a1), (a1 - z) / c, (z - a0) / c))
    gx, gy = slope_1d(zx1, zx0), slope_1d(zy1, zy0)
    with np.errstate(invalid='ignore'):
        slope = np.degrees(np.arctan(np.hypot(np.nan_to_num(gx), np.nan_to_num(gy))))
    slope = np.where(gl & (np.isfinite(gx) | np.isfinite(gy)), slope, np.nan)
    step = np.full(z.shape, np.nan)
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):   # side neighbours: a diagonal adds the slope over a longer distance
        n = _shifted(z, dy, dx, np.nan); d = np.abs(z - n)
        step = np.where(np.isfinite(d), np.fmax(step, d), step)
    return {'slope_deg': slope, 'step_m': step, 'ground_like': gl}


_GREEN, _YELLOW, _RED, _OVER, _NONE, _GROUND = (0, 170, 0), (230, 200, 0), (220, 0, 0), (200, 0, 200), (205, 205, 205), (60, 90, 60)


def colour_scale(v: 'np.ndarray', vmax: float) -> 'np.ndarray':
    """H x W x 3 uint8: green (0) -> yellow -> red (vmax), magenta above vmax, grey where NaN."""
    out = np.empty(v.shape + (3,), dtype=np.uint8); out[:] = _NONE
    ok = np.isfinite(v); t = np.zeros(v.shape)
    if vmax > 0: t[ok] = np.clip(v[ok] / vmax, 0, 1)
    lo = ok & (t <= 0.5); hi = ok & (t > 0.5)
    for ch in range(3):
        a = np.array([_GREEN[ch], _YELLOW[ch], _RED[ch]], dtype=np.float64)
        out[..., ch][lo] = np.round(a[0] + (a[1] - a[0]) * (t[lo] * 2)).astype(np.uint8)
        out[..., ch][hi] = np.round(a[1] + (a[2] - a[1]) * (t[hi] * 2 - 1)).astype(np.uint8)
    over = ok & (v > vmax); out[over] = _OVER
    return out


def write_rgb_png(rgb: 'np.ndarray', path: Path) -> None:
    img = rgb[::-1, :, :]                                               # row 0 = top (largest y), as the PGM
    Path(path).write_bytes(pngmod.encode_rgb(img.shape[1], img.shape[0], img.tobytes()))


def height_view(pts, hag, obst, gnd, result: GridResult, s: dict) -> 'np.ndarray':
    """Highest point above the ground per 2D cell, up to the obstacle band's upper limit (top view of the 3D map)."""
    res = result.resolution; w, h = result.width, result.height
    known = np.isfinite(hag) & (hag <= s['obstacle_band_max_m'])
    ix = ((pts[:, 0] - result.origin_x) / res).astype(np.int64); iy = ((pts[:, 1] - result.origin_y) / res).astype(np.int64)
    inside = known & (ix >= 0) & (ix < w) & (iy >= 0) & (iy < h)
    top = np.full((h, w), -np.inf); np.maximum.at(top, (iy[inside], ix[inside]), hag[inside])
    rgb = colour_scale(np.where(np.isfinite(top), top, np.nan), s['obstacle_band_max_m'])
    flat = np.isfinite(top) & (top <= s['ground_band_max_m']); rgb[flat] = _GROUND   # only ground seen
    return rgb


def write_views(out_dir: Path, ground: Ground, ter: dict, pts, hag, obst, gnd, result: GridResult, s: dict) -> dict:
    write_rgb_png(colour_scale(ter['slope_deg'], s['ground_max_slope_deg']), out_dir / 'slope.png')
    write_rgb_png(colour_scale(ter['step_m'], s['obstacle_band_min_m']), out_dir / 'step.png')
    write_rgb_png(height_view(pts, hag, obst, gnd, result, s), out_dir / 'height.png')
    sl, st = ter['slope_deg'], ter['step_m']
    info = {
        'use': 'display only (DEC-097 A). Not used for driving.',
        'ground_grid': {'cell_m': ground.cell, 'origin_x': ground.origin_x, 'origin_y': ground.origin_y, 'width': int(ground.height.shape[1]), 'height': int(ground.height.shape[0])},
        'views': {
            'slope.png': {'what': 'ground slope per ground cell', 'unit': 'deg', 'scale_max': s['ground_max_slope_deg'], 'scale_from': 'ground_max_slope_deg (PRM-63)'},
            'step.png': {'what': 'largest height difference to a side-neighbouring ground cell (on a slope it includes the rise over one cell)', 'unit': 'm', 'scale_max': s['obstacle_band_min_m'], 'scale_from': 'obstacle_band_min_m (PRM-35)'},
            'height.png': {'what': 'highest point above the ground per 2D cell (top view of the 3D point map)', 'unit': 'm', 'scale_max': s['obstacle_band_max_m'],
                           'scale_from': 'obstacle_band_max_m (PRM-36)', 'grid': '2D map (map.yaml)'}},
        'colours': 'green 0 -> yellow -> red at scale_max; magenta above scale_max; grey no data; dark green (height.png) only ground',
        'stats': {'ground_cells_observed': int(ground.observed.sum()), 'ground_cells_ground_like': int(ter['ground_like'].sum()), 'ground_cells_filled': ground.filled_cells,
                  'slope_max_deg': float(np.nanmax(sl)) if np.isfinite(sl).any() else None, 'step_max_m': float(np.nanmax(st)) if np.isfinite(st).any() else None}}
    (out_dir / 'terrain.json').write_text(json.dumps(info, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return info['stats']


# ---------------------------------------------------------------- conversion

def convert(dump_dir: Path, out_dir: Path, settings: dict) -> dict:
    """Full conversion; raises ValueError with a reason when the input cannot be converted (caller discards output)."""
    if np is None:
        raise RuntimeError('numpy is required for map conversion')
    s = _require(settings, SETTING_KEYS)
    submaps = read_dump(dump_dir)
    pts = world_points(submaps)
    ground = estimate_ground(pts, s['ground_cell_m'], s['ground_max_slope_deg'], s['ground_fill_radius_m'])
    hag, gnd, obst = classify(pts, ground, s)
    grid, result = build_grid(pts, hag, gnd, obst, s)
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    write_map(grid, result, out_dir)
    write_pcd(pts, out_dir / 'pointmap.pcd')
    ter_stats = write_views(out_dir, ground, terrain(ground, s), pts, hag, obst, gnd, result, s)
    return {'converter': CONVERTER_VERSION, 'submaps': len(submaps), **result.__dict__, 'terrain': ter_stats, 'files': list(PRODUCT_FILES)}
