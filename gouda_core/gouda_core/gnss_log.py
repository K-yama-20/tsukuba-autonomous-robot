"""GNSS record of a mapping run (REV-063, DEC-126). No ROS dependency; mode_manager_node feeds it.

While 事前地図作成 runs (TR-03 .. TR-04) every GNSS message (IFD-47 navsatfix, IFD-48 pvtgeodetic, IFD-49 atteuler, IFD-50
attcoveuler) is appended as one JSON line to <mapping work dir>/gnss.jsonl: the topic, the PC receive time and the whole
message as a dictionary (nothing is selected or converted, so a later alignment can use any field: the receiver time in
block_header, the RTK mode, the accuracies, the heading and its covariance). A missing receiver only gives an empty record;
mapping is never stopped for it (DEC-126). At TR-04 the file is put next to the registered source map (not inside the GLIM
dump, whose content hash keeps its meaning) and its SHA-256 and line counts are written into source_manifest.json.
"""
from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Optional

FILE_NAME = 'gnss.jsonl'


class GnssLog:
    def __init__(self):
        self._lock = threading.Lock()
        self._f = None
        self.path: Optional[Path] = None
        self.counts: dict = {}

    @property
    def active(self) -> bool:
        return self._f is not None

    def open(self, work_dir: Path) -> Path:
        with self._lock:
            self._close_locked()
            Path(work_dir).mkdir(parents=True, exist_ok=True)
            self.path = Path(work_dir) / FILE_NAME
            self._f = open(self.path, 'a', encoding='utf-8')
            self.counts = {}
            return self.path

    def write(self, topic: str, received_at: float, message: dict) -> None:
        with self._lock:
            if self._f is None:
                return
            self._f.write(json.dumps({'topic': topic, 'received_at': received_at, 'msg': message}, ensure_ascii=False, default=str) + '\n')
            self.counts[topic] = self.counts.get(topic, 0) + 1

    def note(self, text: str, at: float) -> None:
        """A line that is not a message (e.g. the driver's message types are not installed)."""
        self.write('note', at, {'text': text})

    def close(self) -> Optional[dict]:
        """Close and return {'file', 'sha256', 'counts'} (None when nothing was open)."""
        with self._lock:
            return self._close_locked()

    def _close_locked(self) -> Optional[dict]:
        if self._f is None:
            return None
        self._f.close(); self._f = None
        return summary(self.path, dict(self.counts))


def summary(path: Path, counts: dict) -> dict:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return {'file': FILE_NAME, 'sha256': h.hexdigest(), 'counts': counts}
