"""地図 tab of gouda_monitor (intent.md:106, RQ-I082): conversion settings, re-conversion, results. No ROS dependency.

The conversion parameters of gouda_map_creator (PRM-33..36, PRM-38) are tuning items: the human edits them in the 地図 tab and
re-converts a source map (原図) as often as wanted. Every conversion is a new revision in the map database with its own
settings, statistics and content hash (RQ-I008); the source is never changed (RQ-I009). The defaults shown in the tab are the
values gouda_map_creator was started with (its ROS parameters, from the generated parameter file); nothing numeric is here.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Optional

# key, design id, label, unit, integer?  (names and units only; values come from gouda_map_creator's parameters)
CONVERSION_SETTINGS = [
    {'key': 'map_resolution_m', 'prm': 'PRM-33', 'label': '変換後地図の解像度（1 セルの大きさ）', 'unit': 'm', 'integer': False},
    {'key': 'ground_band_max_m', 'prm': 'PRM-34', 'label': '地面とみなす高さの上限', 'unit': 'm', 'integer': False},
    {'key': 'obstacle_band_min_m', 'prm': 'PRM-35', 'label': '障害物とみなす高さの下限', 'unit': 'm', 'integer': False},
    {'key': 'obstacle_band_max_m', 'prm': 'PRM-36', 'label': '障害物とみなす高さの上限', 'unit': 'm', 'integer': False},
    {'key': 'occupied_min_points', 'prm': 'PRM-38', 'label': 'セルを占有とみなす障害物点数の下限', 'unit': '点', 'integer': True},
]
KEYS = [s['key'] for s in CONVERSION_SETTINGS]


def validate_settings(raw: dict) -> tuple:
    """(settings, errors). Every key must be a finite number; the resolution and the point count must be positive and the
    height bands ordered (ground upper < obstacle lower < obstacle upper). Unknown keys are refused."""
    errors, out = [], {}
    unknown = sorted(set(raw) - set(KEYS))
    if unknown:
        errors.append(f'unknown settings {unknown}')
    for s in CONVERSION_SETTINGS:
        v = raw.get(s['key'])
        try:
            v = float(v)
        except (TypeError, ValueError):
            errors.append(f"{s['label']}（{s['key']}）が数値ではない: {v!r}"); continue
        if not math.isfinite(v):
            errors.append(f"{s['label']}（{s['key']}）が有限の数値ではない"); continue
        if s['integer'] and v != int(v):
            errors.append(f"{s['label']}（{s['key']}）は整数"); continue
        out[s['key']] = v
    if not errors:
        if out['map_resolution_m'] <= 0: errors.append('解像度は正の値')
        if out['occupied_min_points'] < 1: errors.append('占有とみなす点数は 1 以上')
        if not out['ground_band_max_m'] < out['obstacle_band_min_m'] < out['obstacle_band_max_m']:
            errors.append('高さの帯は「地面の上限 < 障害物の下限 < 障害物の上限」の順')
    return (out if not errors else None), errors


@dataclass
class ConversionTracker:
    """The conversion requested from the 地図 tab (one at a time from the monitor)."""
    state: str = 'idle'                 # idle | running | done | failed
    origin_id: str = ''
    settings: dict = field(default_factory=dict)
    requested_at: Optional[float] = None
    finished_at: Optional[float] = None
    message: str = ''
    revision: Optional[int] = None
    stage: str = ''
    progress: Optional[float] = None

    def start(self, origin_id: str, settings: dict, now: Optional[float] = None) -> tuple:
        if self.state == 'running':
            return False, f'a conversion of {self.origin_id} is still running'
        self.state, self.origin_id, self.settings = 'running', origin_id, dict(settings)
        self.requested_at, self.finished_at, self.message, self.revision, self.stage, self.progress = (now or time.time()), None, '', None, 'requested', None
        return True, 'conversion requested'

    def feedback(self, stage: str, progress: float):
        self.stage, self.progress = stage, progress

    def finish(self, ok: bool, message: str, revision: Optional[int] = None, now: Optional[float] = None):
        self.state = 'done' if ok else 'failed'; self.message = message; self.revision = revision if ok else None
        self.finished_at = now or time.time(); self.stage = 'finished'

    def snapshot(self) -> dict:
        return dict(self.__dict__)
