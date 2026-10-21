"""Keepout mask (IFD-41 / IFD-55, REV-137; DEC-220..223; proposals/drawn_areas_2026-10-21.md). No ROS dependency.

The human draws polygons on the waypoint tab's map: 「走行禁止」 (keepout) and 「走行可」 (allowed). They are saved with the
waypoint set (DEC-221) and turned into one mask on the speed mask's grid (the converted map's geometry):
  keepout -> 100 (Nav2's KeepoutFilter writes a lethal cost), allowed -> 0 (it turns an unknown cell into free),
  neither -> -1 (the filter leaves the cell as it is). Keepout wins over allowed where they overlap.
The keepout areas are not widened (DEC-223: base_link may come up to their edge; the human leaves room for the vehicle).
When saving, pairs of keepout areas closer than PRM-99 (DEC-227, DEC-229) are warned about (never refused, as DEC-215): the
global costmap inflates keepout areas like walls (DEC-227 plan A), so a narrow gap between two of them may not let the vehicle
through. Areas that touch or overlap close the way completely and are not warned about.
The mask is written as a map_server map in trinary mode (pixel 0 / 254 / 205) with the costmap_filter_info_server parameters
(type 0, base 0, multiplier 1: the values KeepoutFilter requires). The hash of the cell values map_server will publish is
recorded so that the autonomy start can check the mask Nav2 received (DEC-224 (a)).
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

import numpy as np
import yaml

KEEPOUT, ALLOWED = 'keepout', 'allowed'
KINDS = (KEEPOUT, ALLOWED)
OCCUPIED, FREE, UNKNOWN = 100, 0, -1
PIXEL = {OCCUPIED: 0, FREE: 254, UNKNOWN: 205}             # map_server conventions (as map_convert.write_map)
OCCUPIED_THRESH, FREE_THRESH = 0.65, 0.196                  # map_server defaults, written into the yaml
NAME = 'keepout_mask'
INFO_FILE = 'keepout_filter_info.yaml'


def validate_areas(areas: list) -> list:
    errors = []
    for i, a in enumerate(areas):
        if not isinstance(a, dict) or a.get('kind') not in KINDS:
            errors.append(f'area {i}: kind must be {KEEPOUT} or {ALLOWED}'); continue
        poly = a.get('polygon')
        if not isinstance(poly, list) or len(poly) < 3:
            errors.append(f'area {i}: a polygon needs at least 3 points'); continue
        for j, p in enumerate(poly):
            if not (isinstance(p, (list, tuple)) and len(p) == 2 and all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in p)):
                errors.append(f'area {i} point {j}: [x, y] finite numbers in the map frame')
    return errors


def normalised(areas: list) -> list:
    """The areas with plain float coordinates (the waypoint set's hash must not depend on the number spelling)."""
    return [{'kind': a['kind'], 'polygon': [[float(x), float(y)] for x, y in a['polygon']]} for a in areas]


def inside(polygon: list, xs: 'np.ndarray', ys: 'np.ndarray') -> 'np.ndarray':
    """Even-odd rule: which of the points (xs, ys) lie inside the polygon."""
    res = np.zeros(xs.shape, dtype=bool)
    n = len(polygon)
    for k in range(n):
        x1, y1 = polygon[k]; x2, y2 = polygon[(k + 1) % n]
        if y1 == y2:
            continue
        crosses = (ys >= min(y1, y2)) & (ys < max(y1, y2))
        xc = x1 + (ys - y1) * (x2 - x1) / (y2 - y1)
        res ^= crosses & (xs < xc)
    return res


def rasterize(areas: list, geom) -> 'np.ndarray':
    """int8 H x W grid (row 0 = smallest y, OccupancyGrid order) on the converted map's geometry."""
    grid = np.full((geom.height, geom.width), UNKNOWN, dtype=np.int8)
    cx = geom.origin_x + (np.arange(geom.width) * 2 + 1) * geom.resolution / 2     # cell centres
    cy = geom.origin_y + (np.arange(geom.height) * 2 + 1) * geom.resolution / 2
    xs, ys = np.meshgrid(cx, cy)
    for kind, value in ((ALLOWED, FREE), (KEEPOUT, OCCUPIED)):   # keepout last: it wins
        for a in areas:
            if a['kind'] == kind:
                grid[inside(a['polygon'], xs, ys)] = value
    return grid


def map_server_values(pixels_top_row_first: 'np.ndarray') -> 'np.ndarray':
    """The cell values map_server publishes for a trinary map (negate 0), row 0 = smallest y."""
    p = (255 - pixels_top_row_first.astype(np.float64)) / 255
    out = np.full(p.shape, UNKNOWN, dtype=np.int8)
    out[p > OCCUPIED_THRESH] = OCCUPIED
    out[p < FREE_THRESH] = FREE
    return out[::-1, :]


def data_sha256(values: 'np.ndarray') -> str:
    """Hash of the int8 cell values in OccupancyGrid order (what the autonomy start compares with the received mask)."""
    return hashlib.sha256(np.ascontiguousarray(values, dtype=np.int8).tobytes()).hexdigest()


def write(grid: 'np.ndarray', geom, out_dir: Path, mask_topic: str, filter_info_topic: str) -> tuple:
    """Write keepout_mask.pgm/.yaml and keepout_filter_info.yaml; return (files, record) with the hash of the values map_server will
    publish (computed back from the written image, so that what is checked is what Nav2 reads)."""
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    img = np.vectorize(PIXEL.get, otypes=[np.uint8])(grid)[::-1, :]   # pgm row 0 is the top (largest y)
    (out_dir / f'{NAME}.pgm').write_bytes(f'P5\n{geom.width} {geom.height}\n255\n'.encode('ascii') + img.tobytes())
    (out_dir / f'{NAME}.yaml').write_text(f'image: {NAME}.pgm\nmode: trinary\nresolution: {geom.resolution}\norigin: [{geom.origin_x}, {geom.origin_y}, 0.0]\n'
                                          f'negate: 0\noccupied_thresh: {OCCUPIED_THRESH}\nfree_thresh: {FREE_THRESH}\n', encoding='utf-8')
    info = {'costmap_filter_info_server': {'ros__parameters': {'type': 0, 'filter_info_topic': filter_info_topic, 'mask_topic': mask_topic, 'base': 0.0, 'multiplier': 1.0}}}
    (out_dir / INFO_FILE).write_text(yaml.safe_dump(info, sort_keys=False), encoding='utf-8')
    values = map_server_values(img)
    record = {'mask_yaml': f'{NAME}.yaml', 'data_sha256': data_sha256(values), 'width': int(geom.width), 'height': int(geom.height),
              'keepout_cells': int((values == OCCUPIED).sum()), 'allowed_cells': int((values == FREE).sum())}
    return {'keepout_pgm': f'{NAME}.pgm', 'keepout_yaml': f'{NAME}.yaml', 'keepout_info_yaml': INFO_FILE}, record


def waypoints_in_keepout(areas: list, points: list) -> list:
    """Indices of the points that lie inside a keepout polygon (warned about when saving, never refused: DEC-215 / §6)."""
    if not points:
        return []
    xs = np.array([p[0] for p in points], dtype=np.float64); ys = np.array([p[1] for p in points], dtype=np.float64)
    hit = np.zeros(xs.shape, dtype=bool)
    for a in areas:
        if a['kind'] == KEEPOUT:
            hit |= inside(a['polygon'], xs, ys)
    return [int(i) for i in np.nonzero(hit)[0]]


def _seg_dist(p, q, a, b) -> tuple:
    """Smallest distance between the segments p-q and a-b, with the closest points (0 and the crossing point when they cross)."""
    def cross(o, u, v):
        return (u[0] - o[0]) * (v[1] - o[1]) - (u[1] - o[1]) * (v[0] - o[0])
    d1, d2, d3, d4 = cross(a, b, p), cross(a, b, q), cross(p, q, a), cross(p, q, b)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and 0 not in (d1, d2, d3, d4):
        t = d1 / (d1 - d2)
        c = (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]))
        return 0.0, c, c

    def point_seg(x, u, v):
        dx, dy = v[0] - u[0], v[1] - u[1]
        L = dx * dx + dy * dy
        t = 0.0 if L == 0 else max(0.0, min(1.0, ((x[0] - u[0]) * dx + (x[1] - u[1]) * dy) / L))
        c = (u[0] + t * dx, u[1] + t * dy)
        return math.hypot(x[0] - c[0], x[1] - c[1]), c
    best = None
    for x, u, v, first in ((p, a, b, True), (q, a, b, True), (a, p, q, False), (b, p, q, False)):
        d, c = point_seg(x, u, v)
        if best is None or d < best[0]:
            best = (d, tuple(x), c) if first else (d, c, tuple(x))
    return best


def polygon_distance(pa: list, pb: list) -> tuple:
    """(distance, point on pa, point on pb) between two polygons; 0 when they touch, cross or one holds the other."""
    for poly, other in ((pa, pb), (pb, pa)):
        if inside(other, np.array([poly[0][0]], dtype=np.float64), np.array([poly[0][1]], dtype=np.float64))[0]:
            return 0.0, tuple(poly[0]), tuple(poly[0])
    best = None
    for i in range(len(pa)):
        p, q = pa[i], pa[(i + 1) % len(pa)]
        for j in range(len(pb)):
            d = _seg_dist(p, q, pb[j], pb[(j + 1) % len(pb)])
            if best is None or d[0] < best[0]:
                best = d
    return best


def narrow_gaps(areas: list, threshold_m: float) -> list:
    """Pairs of keepout areas whose gap is above 0 and below threshold_m (PRM-99), with the gap and its two closest points.
    A gap whose middle lies in a third keepout area is no way through and is not reported (only the middle point is tested)."""
    keep = [(i, a['polygon']) for i, a in enumerate(areas) if a['kind'] == KEEPOUT]
    out = []
    for k, (i, pa) in enumerate(keep):
        for j, pb in keep[k + 1:]:
            d, ca, cb = polygon_distance(pa, pb)
            mid = np.array([(ca[0] + cb[0]) / 2]), np.array([(ca[1] + cb[1]) / 2])
            if 0 < d < threshold_m and not any(inside(pc, *mid)[0] for m, pc in keep if m not in (i, j)):
                out.append({'areas': [i, j], 'gap_m': round(d, 3), 'from': [round(ca[0], 3), round(ca[1], 3)], 'to': [round(cb[0], 3), round(cb[1], 3)]})
    return out
