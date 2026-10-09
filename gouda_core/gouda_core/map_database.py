"""Map database (ND-05 gouda_map_creator, IFD-29): a file area plus this library; no always-on DB node (M-006).

Layout (<data_root>/maps):
  <origin_id>/                       one GLIM mapping session = one origin (由来 ID), RQ-I009
    source/                          the GLIM dump (原図, IFD-35) as written by GLIM
    source_manifest.json             origin_id, content hash of source/, GLIM version, config hash, created_at, session info
    converted/<revision>/            one converted 2D map (map.yaml + map.pgm + manifest.json), RQ-I009
  index.json                         list of origins and their converted revisions (derived; rebuilt from manifests)

Identity is by content hash, never by file name (IFD-29). Every artefact is written into a temporary directory and
renamed into place only after verification, so a partially written map is never published. A failed conversion keeps
the source and discards the incomplete artefact (RQ-I009). Re-conversion is always possible.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Optional

MANIFEST_SCHEMA = 1


def content_hash(directory: Path, exclude: tuple = ()) -> str:
    """SHA-256 over the sorted relative paths and contents of all files below directory (excluding the given names)."""
    h = hashlib.sha256(); d = Path(directory)
    for p in sorted(x for x in d.rglob('*') if x.is_file() and x.name not in exclude):
        rel = p.relative_to(d).as_posix().encode('utf-8')
        h.update(len(rel).to_bytes(4, 'big') + rel)
        with open(p, 'rb') as f:
            for chunk in iter(lambda: f.read(1 << 20), b''):
                h.update(chunk)
    return h.hexdigest()


def new_origin_id() -> str:
    return time.strftime('%Y%m%d_%H%M%S', time.localtime()) + '_' + uuid.uuid4().hex[:8]


class MapDatabase:
    def __init__(self, root: Path):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True)

    # ---- source maps (原図) ----
    def register_source(self, dump_dir: Path, origin_id: Optional[str], producer: dict, session: dict) -> tuple[bool, str, Optional[dict]]:
        """Move a complete GLIM dump into the database as <origin_id>/source and write source_manifest.json.

        producer: {'software': 'glim_ros', 'version': '1.2.2-0noble', 'config_hash': ...}. Returns (ok, message, manifest).
        The dump is published only when it is complete (graph.txt/values.bin present); otherwise it is left where it is.
        """
        dump_dir = Path(dump_dir)
        if not (dump_dir / 'graph.txt').is_file() or not (dump_dir / 'values.bin').is_file():
            return False, f'source not registered: dump {dump_dir} is incomplete (graph.txt/values.bin missing); kept in place', None
        origin_id = origin_id or new_origin_id()
        final = self.root / origin_id
        if final.exists():
            return False, f'origin {origin_id} already exists', None
        tmp = self.root / f'.tmp_{origin_id}'
        if tmp.exists(): shutil.rmtree(tmp)
        tmp.mkdir(parents=True)
        shutil.move(str(dump_dir), str(tmp / 'source'))
        src_hash = content_hash(tmp / 'source')
        submaps = sum(1 for x in (tmp / 'source').iterdir() if x.is_dir() and x.name.isdigit() and len(x.name) == 6)
        manifest = {'schema': MANIFEST_SCHEMA, 'kind': 'source', 'origin_id': origin_id, 'content_hash': src_hash, 'producer': producer,
                    'session': session, 'submaps': submaps, 'created_at': time.time(), 'frame': 'glim map frame (map_frame_id of the run)'}
        (tmp / 'source_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        os.replace(tmp, final)   # atomic publish
        self._rebuild_index()
        return True, f'source map registered as {origin_id} (hash {src_hash[:12]}…, {submaps} submap(s))', manifest

    def source_manifest(self, origin_id: str) -> Optional[dict]:
        p = self.root / origin_id / 'source_manifest.json'
        try: return json.loads(p.read_text(encoding='utf-8'))
        except (OSError, ValueError): return None

    def source_dir(self, origin_id: str) -> Path:
        return self.root / origin_id / 'source'

    # ---- converted maps ----
    def begin_conversion(self, origin_id: str) -> Path:
        """Temporary output directory for a conversion; publish with finish_conversion, drop with abort_conversion."""
        if self.source_manifest(origin_id) is None:
            raise FileNotFoundError(f'origin {origin_id} has no source manifest')
        tmp = self.root / origin_id / f'.converting_{uuid.uuid4().hex[:8]}'
        tmp.mkdir(parents=True)
        return tmp

    def finish_conversion(self, origin_id: str, tmp_dir: Path, converter: dict, settings: dict, stats: dict) -> tuple[bool, str, Optional[dict]]:
        """Verify map.yaml + map.pgm, write manifest.json, and publish as converted/<revision> (revision = next integer)."""
        tmp_dir = Path(tmp_dir)
        for f in ('map.yaml', 'map.pgm'):
            if not (tmp_dir / f).is_file() or (tmp_dir / f).stat().st_size == 0:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                return False, f'conversion discarded: {f} missing or empty (source kept)', None
        src = self.source_manifest(origin_id)
        conv_dir = self.root / origin_id / 'converted'; conv_dir.mkdir(exist_ok=True)
        existing = sorted(int(x.name) for x in conv_dir.iterdir() if x.is_dir() and x.name.isdigit())
        revision = (existing[-1] + 1) if existing else 1
        h = content_hash(tmp_dir, exclude=('manifest.json',))
        manifest = {'schema': MANIFEST_SCHEMA, 'kind': 'converted', 'origin_id': origin_id, 'revision': revision, 'content_hash': h,
                    'source_content_hash': src['content_hash'] if src else None, 'converter': converter, 'settings': settings, 'stats': stats,
                    'created_at': time.time(), 'files': ['map.yaml', 'map.pgm'], 'frame': 'map'}
        (tmp_dir / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        os.replace(tmp_dir, conv_dir / f'{revision:03d}')
        self._rebuild_index()
        return True, f'converted map published as {origin_id}/converted/{revision:03d} (hash {h[:12]}…)', manifest

    def abort_conversion(self, tmp_dir: Path, reason: str) -> str:
        shutil.rmtree(Path(tmp_dir), ignore_errors=True)
        return f'conversion aborted and incomplete output discarded: {reason}'

    def converted_manifest(self, origin_id: str, revision: int) -> Optional[dict]:
        p = self.root / origin_id / 'converted' / f'{revision:03d}' / 'manifest.json'
        try: return json.loads(p.read_text(encoding='utf-8'))
        except (OSError, ValueError): return None

    # ---- index ----
    def _rebuild_index(self) -> dict:
        origins = []
        for d in sorted(x for x in self.root.iterdir() if x.is_dir() and not x.name.startswith('.')):
            src = self.source_manifest(d.name)
            if src is None: continue
            convs = []
            cdir = d / 'converted'
            if cdir.is_dir():
                for c in sorted(x for x in cdir.iterdir() if x.is_dir() and x.name.isdigit()):
                    m = self.converted_manifest(d.name, int(c.name))
                    if m: convs.append({'revision': m['revision'], 'content_hash': m['content_hash'], 'created_at': m['created_at']})
            origins.append({'origin_id': d.name, 'source_hash': src['content_hash'], 'submaps': src.get('submaps', 0), 'created_at': src['created_at'], 'converted': convs})
        index = {'schema': MANIFEST_SCHEMA, 'origins': origins, 'updated_at': time.time()}
        tmp = self.root / '.index.json.tmp'
        tmp.write_text(json.dumps(index, ensure_ascii=False, indent=1) + '\n', encoding='utf-8'); os.replace(tmp, self.root / 'index.json')
        return index

    def index(self) -> dict:
        try: return json.loads((self.root / 'index.json').read_text(encoding='utf-8'))
        except (OSError, ValueError): return self._rebuild_index()
