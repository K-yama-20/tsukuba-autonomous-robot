"""Recorder core (ND-04 gouda_recorder): independent log and rosbag sessions, gap ranges, status.

Design references (design/model.yaml): SO-02 (log_session, rosbag_session, gap_ranges), IFD-08..11 (Trigger services),
IFD-12 (record/status), RQ-I015 (log content, gaps, auto-start triggers, failure never stops driving), RQ-I016 (rosbag is
separate, never auto-started, same directory with separate folders), RQ-I034 (gap ranges are recorded).

No ROS dependency. The node supplies a clock (float seconds) and a rosbag process controller.

Session layout (RQ-I016):  <record_root>/<session_id>/log/events.jsonl   (JSON lines, one received input / decision each)
                           <record_root>/<session_id>/log/gaps.jsonl     (gap ranges, appended when a gap closes)
                           <record_root>/<session_id>/rosbag/            (rosbag2 output of the same session)
                           <record_root>/<session_id>/session.json       (who started what, when, and failures)
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable, Optional

TRIGGER_HUMAN = 'human'                     # Record / Rosbag record button (ND-02)
TRIGGER_AUTO_MAP_START = 'auto:map_start'    # the only two automatic triggers for the log (RQ-I015), both human-initiated
TRIGGER_AUTO_AUTONOMY_START = 'auto:autonomy_start'
AUTO_TRIGGERS = (TRIGGER_AUTO_MAP_START, TRIGGER_AUTO_AUTONOMY_START)
# Events that must never start a recording (RQ-I015): boot, fault recovery, resume button, monitor reconnect.
NEVER_AUTO_START = ('boot', 'fault_recovery', 'resume', 'monitor_reconnect', 'pc_restart')


@dataclass
class GapRange:
    start: float
    end: Optional[float] = None
    kind: str = 'stopped'   # 'stopped' (recording inactive) or 'failure' (write failure while active)
    detail: str = ''


@dataclass
class Session:
    session_id: str
    directory: Path
    log_active: bool = False
    log_started_by: str = ''            # '' | human | auto:map_start | auto:autonomy_start
    rosbag_active: bool = False
    rosbag_started_by: str = ''
    open_gap: Optional[GapRange] = None
    gaps: list = field(default_factory=list)
    failures: list = field(default_factory=list)


class RecorderCore:
    """State machine for the two independent recordings. All methods return (ok, message) and never raise to the caller
    for recording failures: a failed recording is reported, driving is not stopped (RQ-I015)."""

    def __init__(self, record_root: Path, clock: Callable[[], float] = time.time,
                 rosbag_start: Optional[Callable[[Path], None]] = None, rosbag_stop: Optional[Callable[[], None]] = None,
                 session_id_factory: Optional[Callable[[], str]] = None):
        self.record_root = Path(record_root)
        self.clock = clock
        self._rosbag_start = rosbag_start or (lambda d: None)
        self._rosbag_stop = rosbag_stop or (lambda: None)
        self._session_id_factory = session_id_factory or (lambda: time.strftime('%Y%m%d_%H%M%S', time.localtime(self.clock())))
        self.session: Optional[Session] = None
        self.last_gap: Optional[GapRange] = None
        self.status_revision = 0

    # ---- session ----
    def _ensure_session(self) -> Session:
        if self.session is None:
            sid = self._session_id_factory()
            d = self.record_root / sid
            self.session = Session(session_id=sid, directory=d)
            (d / 'log').mkdir(parents=True, exist_ok=True)
            (d / 'rosbag').mkdir(parents=True, exist_ok=True)
            self._write_session_json()
        return self.session

    def _write_session_json(self) -> None:
        s = self.session
        if s is None: return
        try:
            (s.directory / 'session.json').write_text(json.dumps({
                'session_id': s.session_id, 'log_active': s.log_active, 'log_started_by': s.log_started_by,
                'rosbag_active': s.rosbag_active, 'rosbag_started_by': s.rosbag_started_by,
                'gaps': [asdict(g) for g in s.gaps], 'failures': s.failures, 'updated': self.clock()},
                ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        except OSError as e:
            s.failures.append({'time': self.clock(), 'what': 'session.json', 'error': str(e)})

    # ---- log recording (IFD-08 / IFD-09) ----
    def start_log(self, trigger: str) -> tuple[bool, str]:
        if trigger != TRIGGER_HUMAN and trigger not in AUTO_TRIGGERS:
            return False, f'refused: {trigger!r} is not a permitted start trigger (RQ-I015)'
        s = self._ensure_session()
        if s.log_active:
            return True, f'log already active (started by {s.log_started_by}); trigger {trigger} ignored'
        s.log_active = True; s.log_started_by = trigger
        self._close_gap()
        self.status_revision += 1
        self._write_session_json()
        self._append(s.directory / 'log' / 'events.jsonl', {'t': self.clock(), 'kind': 'record_start', 'trigger': trigger})
        return True, f'log recording started ({trigger}) in {s.directory}'

    def stop_log(self, trigger: str) -> tuple[bool, str]:
        s = self.session
        if s is None or not s.log_active:
            return True, 'log recording is not active'
        # Automatic stop (map end / autonomy end) stops only an automatically started recording (RQ-I017).
        if trigger != TRIGGER_HUMAN and s.log_started_by == TRIGGER_HUMAN:
            return False, 'refused: a recording started by a human is not stopped automatically (RQ-I017)'
        self._append(s.directory / 'log' / 'events.jsonl', {'t': self.clock(), 'kind': 'record_stop', 'trigger': trigger})
        s.log_active = False; s.log_started_by = ''
        self._open_gap('stopped', f'stopped by {trigger}')
        self.status_revision += 1
        self._write_session_json()
        return True, 'log recording stopped'

    def auto_start_allowed(self, event: str) -> bool:
        """True only for the two permitted automatic triggers; boot/recovery/resume never start a recording."""
        return event in AUTO_TRIGGERS and event not in NEVER_AUTO_START

    # ---- rosbag recording (IFD-10 / IFD-11), human only ----
    def start_rosbag(self, trigger: str) -> tuple[bool, str]:
        if trigger != TRIGGER_HUMAN:
            return False, 'refused: rosbag recording is started only by a human (RQ-I016)'
        s = self._ensure_session()
        if s.rosbag_active:
            return True, 'rosbag already active'
        try:
            self._rosbag_start(s.directory / 'rosbag')
        except Exception as e:  # recording failure is reported, never propagated (RQ-I015)
            s.failures.append({'time': self.clock(), 'what': 'rosbag_start', 'error': str(e)})
            self.status_revision += 1; self._write_session_json()
            return False, f'rosbag start failed: {e}'
        s.rosbag_active = True; s.rosbag_started_by = trigger
        self.status_revision += 1; self._write_session_json()
        return True, f'rosbag recording started in {s.directory / "rosbag"}'

    def stop_rosbag(self, trigger: str) -> tuple[bool, str]:
        s = self.session
        if s is None or not s.rosbag_active:
            return True, 'rosbag recording is not active'
        try:
            self._rosbag_stop()
        except Exception as e:
            s.failures.append({'time': self.clock(), 'what': 'rosbag_stop', 'error': str(e)})
        s.rosbag_active = False; s.rosbag_started_by = ''
        self.status_revision += 1; self._write_session_json()
        return True, 'rosbag recording stopped'

    # ---- received inputs and decisions ----
    def record(self, kind: str, topic: str, received_at: float, payload: dict) -> bool:
        """Append one received message (input or decision) to the log. Only what was received is written (RQ-I015).
        Returns False (and opens a failure gap) when the write fails; the caller keeps running."""
        s = self.session
        if s is None or not s.log_active:
            return False
        return self._append(s.directory / 'log' / 'events.jsonl', {'t': received_at, 'kind': kind, 'topic': topic, 'data': payload})

    def _append(self, path: Path, obj: dict) -> bool:
        try:
            with open(path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(obj, ensure_ascii=False, default=str) + '\n')
            if self.session and self.session.open_gap and self.session.open_gap.kind == 'failure':
                self._close_gap()
            return True
        except OSError as e:
            if self.session:
                self.session.failures.append({'time': self.clock(), 'what': str(path.name), 'error': str(e)})
                self._open_gap('failure', str(e))
                self.status_revision += 1
            return False

    # ---- gaps (RQ-I034) ----
    def _open_gap(self, kind: str, detail: str) -> None:
        s = self.session
        if s is None or s.open_gap is not None: return
        s.open_gap = GapRange(start=self.clock(), kind=kind, detail=detail)

    def _close_gap(self) -> None:
        s = self.session
        if s is None or s.open_gap is None: return
        g = s.open_gap; g.end = self.clock(); s.gaps.append(g); self.last_gap = g; s.open_gap = None
        self._append(s.directory / 'log' / 'gaps.jsonl', asdict(g))

    # ---- status (IFD-12) ----
    def status(self) -> dict:
        s = self.session
        gap = s.open_gap if s and s.open_gap else self.last_gap
        return {
            'log_active': bool(s and s.log_active), 'rosbag_active': bool(s and s.rosbag_active),
            'session_dir': str(s.directory) if s else '', 'auto_started_by': (s.log_started_by if s and s.log_started_by in AUTO_TRIGGERS else ''),
            'log_started_by': s.log_started_by if s else '', 'rosbag_started_by': s.rosbag_started_by if s else '',
            'last_gap': (f"{gap.kind} {gap.start:.3f}..{'open' if gap.end is None else f'{gap.end:.3f}'} {gap.detail}" if gap else ''),
            'failures': len(s.failures) if s else 0, 'status_revision': self.status_revision,
        }
