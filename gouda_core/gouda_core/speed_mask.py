"""Speed mask generator (IFD-41) for the Nav2 SpeedFilter, stage 5-4. No ROS dependency.

For each section i -> i+1 of a waypoint set, the band of half-width PRM-19 around the segment is painted with the
section's limit v[i] quantised to cell value round(v / step) (step = PRM-20 = CostmapFilterInfo multiplier, base 0),
clipped to 1..100. Where bands overlap the lower limit is kept (DEC-045); if the overlapping sections carry different
limits a warning names the sections, the cell count and the adopted lower value (DEC-059 case A, TS-22).
REV-285 (DEC-506, replacing DEC-045's / DEC-055's "outside every band = 0 = unlimited"): no cell is 0. Outside every band,
within the ramp length L_ramp (PRM-165) beyond the nearest band, the value falls linearly with the distance from that band's
limit to the outside speed V_slow (PRM-164); farther out, and everywhere without a band, it is V_slow. The ramp follows the
NEAREST band (on a tie the lower limit), so the value has no step at a band's edge; bands themselves keep the DEC-045 rule.

The mask shares the converted map's frame, origin and resolution (IFD-41). It is written as a raw-mode map_server
map (pixel value = cell value) plus the costmap_filter_info_server parameters. Nav2 itself is not modified.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import yaml

MASK_MAX = 100   # CostmapFilterInfo mask cells are int8 1..100 (0 = unlimited: no longer written, REV-285)


@dataclass
class MapGeometry:
    resolution: float
    origin_x: float
    origin_y: float
    width: int
    height: int

    @classmethod
    def from_map_yaml(cls, map_yaml: Path) -> 'MapGeometry':
        d = yaml.safe_load(Path(map_yaml).read_text(encoding='utf-8'))
        pgm = Path(map_yaml).parent / d['image']
        with open(pgm, 'rb') as f:
            magic = f.readline().strip(); dims = f.readline().strip()
            while dims.startswith(b'#'): dims = f.readline().strip()
            w, h = [int(x) for x in dims.split()]
        if magic != b'P5': raise ValueError(f'{pgm}: not a binary PGM (P5)')
        return cls(float(d['resolution']), float(d['origin'][0]), float(d['origin'][1]), w, h)


@dataclass
class MaskResult:
    grid: np.ndarray            # HxW uint8, row 0 = min y (map order); 1..100 = limit / step (REV-285: never 0)
    step_mps: float
    half_width_m: float
    warnings: list = field(default_factory=list)
    painted_cells: int = 0      # band cells
    outside_mps: Optional[float] = None   # V_slow (PRM-164)
    ramp_m: Optional[float] = None        # L_ramp (PRM-165)
    ramp_cells: int = 0                   # cells on a ramp (outside every band, within L_ramp)
    overlap_cells: int = 0
    sections_clipped: list = field(default_factory=list)   # sections whose quantised value hit 1 or 100


def quantise(v_mps: float, step_mps: float) -> int:
    if step_mps <= 0: raise ValueError('step_mps (PRM-20) must be positive')
    return int(min(MASK_MAX, max(1, round(v_mps / step_mps))))


def generate(waypoints: list, section_limits_mps: list, geom: MapGeometry, half_width_m: float, step_mps: float,
             outside_mps: float, ramp_m: float) -> MaskResult:
    """waypoints: list of (x, y) in the map frame. outside_mps: V_slow (PRM-164), ramp_m: L_ramp (PRM-165), REV-285.
    Returns the mask grid and warnings (never raises for overlaps)."""
    if half_width_m <= 0: raise ValueError('half_width_m (PRM-19) must be positive')
    if not (outside_mps > 0): raise ValueError('outside_mps (PRM-164) must be positive: the mask has no unlimited cell (REV-285)')
    if not (ramp_m >= 0): raise ValueError('ramp_m (PRM-165) must not be negative')
    if len(waypoints) < 2 or len(section_limits_mps) != len(waypoints) - 1: raise ValueError('need N waypoints and N-1 section limits')
    H, W = geom.height, geom.width
    # cell centres
    xs = geom.origin_x + (np.arange(W) + 0.5) * geom.resolution
    ys = geom.origin_y + (np.arange(H) + 0.5) * geom.resolution
    gx, gy = np.meshgrid(xs, ys)                       # HxW
    value = np.zeros((H, W), dtype=np.int16)            # adopted band value (0 = no band here)
    owner = np.full((H, W), -1, dtype=np.int32)         # section that set the adopted value
    near_d = np.full((H, W), np.inf)                    # distance to the nearest band's centre line (ramp, REV-285)
    near_v = np.zeros((H, W))                           # that section's limit (m/s)
    conflicts = {}                                     # (sec_a, sec_b) -> cells with different values
    clipped = []
    for i in range(len(waypoints) - 1):
        (x0, y0), (x1, y1) = waypoints[i], waypoints[i + 1]
        q = quantise(section_limits_mps[i], step_mps)
        if q in (1, MASK_MAX) and abs(section_limits_mps[i] / step_mps - q) > 0.5: clipped.append(i)
        dx, dy = x1 - x0, y1 - y0; L2 = dx * dx + dy * dy
        if L2 == 0:
            d = np.hypot(gx - x0, gy - y0)
        else:
            t = np.clip(((gx - x0) * dx + (gy - y0) * dy) / L2, 0, 1)
            d = np.hypot(gx - (x0 + t * dx), gy - (y0 + t * dy))
        lim = float(section_limits_mps[i])
        closer = (d < near_d) | ((d == near_d) & (lim < near_v))
        near_d = np.where(closer, d, near_d); near_v = np.where(closer, lim, near_v)
        inside = d <= half_width_m
        prev = value[inside]; prev_owner = owner[inside]
        diff = (prev > 0) & (prev != q)
        if diff.any():
            for other in np.unique(prev_owner[diff]):
                key = (int(min(other, i)), int(max(other, i)))
                conflicts[key] = conflicts.get(key, 0) + int((prev_owner[diff] == other).sum())
        new = np.where((prev == 0) | (q < prev), q, prev)
        owner_new = np.where((prev == 0) | (q < prev), i, prev_owner)
        value[inside] = new; owner[inside] = owner_new
    band = value > 0
    beyond = near_d - half_width_m                      # > 0 outside every band
    on_ramp = (~band) & (beyond <= ramp_m) if ramp_m > 0 else np.zeros((H, W), dtype=bool)
    frac = np.clip(beyond / ramp_m, 0, 1) if ramp_m > 0 else np.ones((H, W))
    ramp_v = near_v + (outside_mps - near_v) * frac
    ramp_q = np.clip(np.rint(ramp_v / step_mps), 1, MASK_MAX).astype(np.int16)
    grid = np.where(band, value, np.where(on_ramp, ramp_q, quantise(outside_mps, step_mps)))
    warnings = []
    for (a, b), n in sorted(conflicts.items()):
        va, vb = section_limits_mps[a], section_limits_mps[b]
        warnings.append({'sections': [a, b], 'cells': n, 'limits_mps': [va, vb], 'adopted_mps': min(va, vb),
                         'message': f'区間 {a}（{va} m/s）と区間 {b}（{vb} m/s）が {n} cell で重なる。重複 cell は低い方 {min(va, vb)} m/s が適用される（DEC-045）。再訪・重複する区間には同じ上限を設定する運用（DEC-059 案 A）'})
    overlap_cells = sum(conflicts.values())
    return MaskResult(grid=grid.astype(np.uint8), step_mps=step_mps, half_width_m=half_width_m, warnings=warnings,
                      painted_cells=int(band.sum()), overlap_cells=overlap_cells, sections_clipped=clipped,
                      outside_mps=float(outside_mps), ramp_m=float(ramp_m), ramp_cells=int(on_ramp.sum()))


def clamp_limits(section_limits_mps: list, v_auto_mps: float) -> tuple:
    """REV-285 (DEC-505, the start's migration step): (limits with every value above V_auto (PRM-131) set to V_auto,
    [(section, old, new)] of the changed ones)."""
    out, changed = [], []
    for i, v in enumerate(section_limits_mps):
        if v > v_auto_mps:
            out.append(float(v_auto_mps)); changed.append((i, float(v), float(v_auto_mps)))
        else:
            out.append(float(v))
    return out, changed


def limits_above(section_limits_mps: list, v_auto_mps: float) -> list:
    """REV-285 (DEC-505): the sections whose limit is above V_auto (a waypoint set with one is not saved)."""
    return [i for i, v in enumerate(section_limits_mps) if v > v_auto_mps]


def write_mask(result: MaskResult, geom: MapGeometry, out_dir: Path, mask_topic: str, filter_info_topic: str, name: str = 'speed_mask') -> dict:
    """Write speed_mask.pgm/.yaml (map_server raw mode: pixel = cell value) and filter_info.yaml (costmap_filter_info_server)."""
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    img = result.grid[::-1, :]   # pgm row 0 is the top (largest y)
    header = f'P5\n{geom.width} {geom.height}\n255\n'.encode('ascii')
    (out_dir / f'{name}.pgm').write_bytes(header + img.astype(np.uint8).tobytes())
    (out_dir / f'{name}.yaml').write_text(f'image: {name}.pgm\nmode: raw\nresolution: {geom.resolution}\norigin: [{geom.origin_x}, {geom.origin_y}, 0.0]\nnegate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.196\n', encoding='utf-8')
    info = {'costmap_filter_info_server': {'ros__parameters': {'type': 2, 'filter_info_topic': filter_info_topic, 'mask_topic': mask_topic, 'base': 0.0, 'multiplier': float(result.step_mps)}}}
    (out_dir / 'filter_info.yaml').write_text(yaml.safe_dump(info, sort_keys=False), encoding='utf-8')
    return {'mask_pgm': f'{name}.pgm', 'mask_yaml': f'{name}.yaml', 'filter_info_yaml': 'filter_info.yaml'}
