"""Waypoint sets (IFD-30) and the route database, stage 5-4. No ROS dependency.

A waypoint set belongs to one converted map (origin id, revision, content hash: RQ-I078) and holds the waypoints in the
map frame plus the speed limit of each section i -> i+1 (m/s). It carries its own content hash and is saved
atomically into <data_root>/routes/<set_id>/<revision>/ together with the speed mask (IFD-41) generated from it.

Layout:
  routes/<set_id>/<revision>/waypoints.yaml      the set (YAML, IFD-30)
  routes/<set_id>/<revision>/speed_mask.pgm/.yaml raw-mode mask for the Nav2 SpeedFilter (IFD-41)
  routes/<set_id>/<revision>/filter_info.yaml     costmap_filter_info_server parameters (IFD-41)
  routes/<set_id>/<revision>/manifest.json        hashes, map reference, generator settings, warnings
  routes/index.json                               derived list
The legacy default pass radius (D-02) is not reused (DEC-016).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import yaml

SCHEMA = 1


@dataclass
class Waypoint:
    x: float
    y: float
    yaw: float = 0.0      # rad, map frame (REP-103)
    kind: str = 'pass'    # pass | stop (stop points are kept for the record; passing is judged by Nav2: RQ-I011)


@dataclass
class WaypointSet:
    map_origin_id: str
    map_revision: int
    map_content_hash: str
    waypoints: list                       # list[Waypoint]
    section_limits_mps: list              # len = len(waypoints) - 1; section i -> i+1
    set_id: str = ''
    revision: int = 0
    note: str = ''

    def validate(self) -> list:
        errors = []
        if not self.map_origin_id or not self.map_content_hash: errors.append('map reference (origin id / content hash) is required (RQ-I078)')
        if len(self.waypoints) < 2: errors.append('at least two waypoints are required')
        if len(self.section_limits_mps) != max(len(self.waypoints) - 1, 0): errors.append(f'section_limits_mps must have {max(len(self.waypoints) - 1, 0)} entries (one per section)')
        for i, v in enumerate(self.section_limits_mps):
            if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or v <= 0: errors.append(f'section {i}: speed limit must be a positive number (m/s), got {v!r}')
        for i, w in enumerate(self.waypoints):
            if not all(isinstance(getattr(w, k), (int, float)) and math.isfinite(getattr(w, k)) for k in ('x', 'y', 'yaw')): errors.append(f'waypoint {i}: x, y, yaw must be finite numbers')
            if w.kind not in ('pass', 'stop'): errors.append(f'waypoint {i}: kind must be pass or stop')
        return errors

    def to_dict(self) -> dict:
        return {'schema': SCHEMA, 'set_id': self.set_id, 'revision': self.revision, 'note': self.note,
                'map': {'origin_id': self.map_origin_id, 'revision': self.map_revision, 'content_hash': self.map_content_hash},
                'frame': 'map', 'waypoints': [{'x': float(w.x), 'y': float(w.y), 'yaw': float(w.yaw), 'kind': w.kind} for w in self.waypoints],
                'section_limits_mps': [float(v) for v in self.section_limits_mps]}   # normalised numbers: the hash does not depend on int/float spelling

    @classmethod
    def from_dict(cls, d: dict) -> 'WaypointSet':
        m = d.get('map', {})
        return cls(map_origin_id=str(m.get('origin_id', '')), map_revision=int(m.get('revision', 0)), map_content_hash=str(m.get('content_hash', '')),
                   waypoints=[Waypoint(float(w['x']), float(w['y']), float(w.get('yaw', 0.0)), str(w.get('kind', 'pass'))) for w in d.get('waypoints', [])],
                   section_limits_mps=[float(v) for v in d.get('section_limits_mps', [])], set_id=str(d.get('set_id', '')), revision=int(d.get('revision', 0)), note=str(d.get('note', '')))

    def content_hash(self) -> str:
        """Hash of the set's content (without set_id/revision/note), independent of file names."""
        d = self.to_dict(); d.pop('set_id'); d.pop('revision'); d.pop('note')
        return hashlib.sha256(json.dumps(d, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def new_set_id() -> str:
    return time.strftime('%Y%m%d_%H%M%S', time.localtime()) + '_' + uuid.uuid4().hex[:6]


class RouteDatabase:
    def __init__(self, root: Path):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True)

    def begin(self, set_id: Optional[str]) -> tuple[str, int, Path]:
        set_id = set_id or new_set_id()
        sdir = self.root / set_id
        existing = sorted(int(x.name) for x in sdir.iterdir() if x.is_dir() and x.name.isdigit()) if sdir.is_dir() else []
        revision = (existing[-1] + 1) if existing else 1
        tmp = sdir / f'.saving_{uuid.uuid4().hex[:8]}'; tmp.mkdir(parents=True)
        return set_id, revision, tmp

    def publish(self, set_id: str, revision: int, tmp: Path, ws: WaypointSet, mask_files: dict, warnings: list, generator: dict) -> tuple[bool, str, Optional[dict]]:
        """Verify waypoints.yaml and the mask files, write manifest.json and rename into place (atomic)."""
        tmp = Path(tmp)
        ws.set_id, ws.revision = set_id, revision
        (tmp / 'waypoints.yaml').write_text(yaml.safe_dump(ws.to_dict(), allow_unicode=True, sort_keys=False), encoding='utf-8')
        for f in ['waypoints.yaml'] + list(mask_files.values()):
            if not (tmp / f).is_file() or (tmp / f).stat().st_size == 0:
                shutil.rmtree(tmp, ignore_errors=True)
                return False, f'save discarded: {f} missing or empty', None
        files_hash = _dir_hash(tmp, exclude=('manifest.json',))
        manifest = {'schema': SCHEMA, 'kind': 'waypoint_set', 'set_id': set_id, 'revision': revision, 'content_hash': ws.content_hash(), 'files_content_hash': files_hash,
                    'map': {'origin_id': ws.map_origin_id, 'revision': ws.map_revision, 'content_hash': ws.map_content_hash}, 'waypoints': len(ws.waypoints),
                    'sections': len(ws.section_limits_mps), 'mask_files': mask_files, 'generator': generator, 'warnings': warnings, 'created_at': time.time()}
        (tmp / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        os.replace(tmp, self.root / set_id / f'{revision:03d}')
        self._rebuild_index()
        return True, f'waypoint set saved as {set_id}/{revision:03d} (hash {manifest["content_hash"][:12]}…; {len(warnings)} warning(s))', manifest

    def abort(self, tmp: Path, reason: str) -> str:
        shutil.rmtree(Path(tmp), ignore_errors=True); return f'save aborted: {reason}'

    def load(self, set_id: str, revision: int) -> Optional[WaypointSet]:
        p = self.root / set_id / f'{revision:03d}' / 'waypoints.yaml'
        try: return WaypointSet.from_dict(yaml.safe_load(p.read_text(encoding='utf-8')))
        except (OSError, ValueError, TypeError, KeyError): return None

    def manifest(self, set_id: str, revision: int) -> Optional[dict]:
        p = self.root / set_id / f'{revision:03d}' / 'manifest.json'
        try: return json.loads(p.read_text(encoding='utf-8'))
        except (OSError, ValueError): return None

    def _rebuild_index(self) -> dict:
        sets = []
        for d in sorted(x for x in self.root.iterdir() if x.is_dir() and not x.name.startswith('.')):
            revs = []
            for r in sorted(x for x in d.iterdir() if x.is_dir() and x.name.isdigit()):
                m = self.manifest(d.name, int(r.name))
                if m: revs.append({'revision': m['revision'], 'content_hash': m['content_hash'], 'map': m['map'], 'waypoints': m['waypoints'], 'warnings': len(m['warnings']), 'created_at': m['created_at']})
            if revs: sets.append({'set_id': d.name, 'revisions': revs})
        index = {'schema': SCHEMA, 'sets': sets, 'updated_at': time.time()}
        tmp = self.root / '.index.json.tmp'; tmp.write_text(json.dumps(index, ensure_ascii=False, indent=1) + '\n', encoding='utf-8'); os.replace(tmp, self.root / 'index.json')
        return index

    def index(self) -> dict:
        try: return json.loads((self.root / 'index.json').read_text(encoding='utf-8'))
        except (OSError, ValueError): return self._rebuild_index()


def _dir_hash(directory: Path, exclude: tuple = ()) -> str:
    h = hashlib.sha256(); d = Path(directory)
    for p in sorted(x for x in d.rglob('*') if x.is_file() and x.name not in exclude):
        rel = p.relative_to(d).as_posix().encode('utf-8'); h.update(len(rel).to_bytes(4, 'big') + rel); h.update(p.read_bytes())
    return h.hexdigest()
