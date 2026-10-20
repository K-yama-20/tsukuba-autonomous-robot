"""Recorder core (ND-04 gouda_recorder): independent log and rosbag sessions, gap ranges, status.

Design references (design/model.yaml): SO-02 (log_session, rosbag_session, gap_ranges), IFD-08..11 (Trigger services),
IFD-12 (record/status), RQ-I015 (log content, gaps, auto-start triggers, failure never stops driving), RQ-I016 (rosbag is
separate, never auto-started, same directory with separate folders), RQ-I034 (gap ranges are recorded).

No ROS dependency. The node supplies a clock (float seconds) and a rosbag process controller.

Session layout (RQ-I016):  <record_root>/<session_id>/log/events.jsonl   (JSON lines, one received input / decision each)
                           <record_root>/<session_id>/log/gaps.jsonl     (gap ranges, appended when a gap closes)
                           <record_root>/<session_id>/rosbag/bag_NN/     (one rosbag2 output per rosbag start, NN = 01, 02, ...)
                           <record_root>/<session_id>/rosbag/bag_NN.log  (output of that `ros2 bag record` process)
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
    # One entry per rosbag start: a restart in the same session writes to a new folder (G-REC-ROSBAG-RESTART: a second
    # `ros2 bag record -o <existing folder>` exits at once and the bag was silently lost on 2026-10-14).
    rosbag_outputs: list = field(default_factory=list)
    # The rosbag being saved after a stop request (DEC-174): ros2 bag record finishes writing after SIGINT; there is no time
    # limit, and the monitor shows the progress from the start of the save. None when no save is in progress.
    rosbag_finalizing: Optional[dict] = None
    last_finalize: Optional[dict] = None


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
        # Last received message per topic (kind, received_at, payload). Written as a snapshot when a log starts so that
        # the state in force at the start of a recording is traceable; it carries the original receive time (RQ-I015).
        self.last_received: dict = {}

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
                'gaps': [asdict(g) for g in s.gaps], 'failures': s.failures, 'rosbag_outputs': s.rosbag_outputs, 'updated': self.clock()},
                ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        except OSError as e:
            s.failures.append({'time': self.clock(), 'what': 'session.json', 'error': str(e)})

    # ---- log recording (IFD-08 / IFD-09) ----
    def start_log(self, trigger: str) -> tuple[bool, str]:
        if trigger != TRIGGER_HUMAN and trigger not in AUTO_TRIGGERS:
            return False, f'refused: {trigger!r} is not a permitted start trigger (RQ-I015)'
        s = self._ensure_session()
        if s.log_active:
            # Already recording: nothing is changed and the origin is kept (a human-started log is never relabelled as
            # auto-started). The answer says 記録中 so that the caller can show it (DEC-071).
            return True, f'記録中 (already active; started by {s.log_started_by}; request {trigger} ignored, origin kept)'
        s.log_active = True; s.log_started_by = trigger
        self._close_gap()
        self.status_revision += 1
        self._write_session_json()
        self._append(s.directory / 'log' / 'events.jsonl', {'t': self.clock(), 'kind': 'record_start', 'trigger': trigger})
        for topic, (kind, received_at, payload) in sorted(self.last_received.items()):
            self._append(s.directory / 'log' / 'events.jsonl', {'t': received_at, 'kind': 'snapshot', 'of': kind, 'topic': topic, 'data': payload, 'written_at': self.clock()})
        return True, f'log recording started ({trigger}) in {s.directory}'

    def stop_log(self, trigger: str) -> tuple[bool, str]:
        s = self.session
        if s is None or not s.log_active:
            return True, 'log recording is not active'
        # Automatic stop (map end / autonomy end) stops only an automatically started recording (RQ-I017). Leaving a
        # human-started log running is the intended outcome, not an error, so the answer is ok with an explanation.
        if trigger != TRIGGER_HUMAN and s.log_started_by == TRIGGER_HUMAN:
            return True, '手動開始のため停止しない (started by a human; not stopped automatically: RQ-I017)'
        self._append(s.directory / 'log' / 'events.jsonl', {'t': self.clock(), 'kind': 'record_stop', 'trigger': trigger})
        s.log_active = False; s.log_started_by = ''
        self._open_gap('stopped', f'stopped by {trigger}')
        self.status_revision += 1
        self._write_session_json()
        return True, 'log recording stopped'

    def stop_auto(self) -> tuple[bool, str]:
        """IFD-46 record/log/stop_auto: stop only an automatically started log; a human-started log is left running."""
        return self.stop_log('auto:stop')

    def auto_start_allowed(self, event: str) -> bool:
        """True only for the two permitted automatic triggers; boot/recovery/resume never start a recording."""
        return event in AUTO_TRIGGERS and event not in NEVER_AUTO_START

    # ---- rosbag recording (IFD-10 / IFD-11), human only ----
    def _next_rosbag_dir(self, s: Session) -> Path:
        """A new output folder for every rosbag start in this session (rosbag/bag_01, bag_02, ...), never an existing one."""
        n = len(s.rosbag_outputs) + 1
        while (s.directory / 'rosbag' / f'bag_{n:02d}').exists():
            n += 1
        return s.directory / 'rosbag' / f'bag_{n:02d}'

    def start_rosbag(self, trigger: str) -> tuple[bool, str]:
        if trigger != TRIGGER_HUMAN:
            return False, 'refused: rosbag recording is started only by a human (RQ-I016)'
        s = self._ensure_session()
        if s.rosbag_active:
            return True, 'rosbag already active'
        if s.rosbag_finalizing is not None:
            return False, f"refused: the previous rosbag is still being saved ({s.rosbag_finalizing['output']})"
        out = self._next_rosbag_dir(s)
        try:
            self._rosbag_start(out)
        except Exception as e:  # recording failure is reported, never propagated (RQ-I015)
            s.failures.append({'time': self.clock(), 'what': 'rosbag_start', 'error': str(e), 'output': str(out)})
            s.rosbag_outputs.append({'output': str(out), 'started_by': trigger, 'started_at': self.clock(), 'stopped_at': self.clock(), 'result': 'start_failed'})
            self.status_revision += 1; self._write_session_json()
            self._log_failure('rosbag_start', str(e), str(out))
            return False, f'rosbag start failed: {e}'
        s.rosbag_active = True; s.rosbag_started_by = trigger
        s.rosbag_outputs.append({'output': str(out), 'started_by': trigger, 'started_at': self.clock(), 'stopped_at': None, 'result': 'recording'})
        self.status_revision += 1; self._write_session_json()
        return True, f'rosbag recording started in {out}'

    def stop_rosbag(self, trigger: str) -> tuple[bool, str]:
        """Request the stop and return at once (DEC-174): the save continues in ros2 bag record and ends in rosbag_finalized."""
        s = self.session
        if s is None or not s.rosbag_active:
            return True, 'rosbag recording is not active'
        out = s.rosbag_outputs[-1]['output'] if s.rosbag_outputs else ''
        s.rosbag_active = False; s.rosbag_started_by = ''
        if s.rosbag_outputs and s.rosbag_outputs[-1]['stopped_at'] is None:
            s.rosbag_outputs[-1].update(stopped_at=self.clock(), result='saving')
        try:
            saving = self._rosbag_stop()
        except Exception as e:
            s.failures.append({'time': self.clock(), 'what': 'rosbag_stop', 'error': str(e), 'output': out})
            if s.rosbag_outputs: s.rosbag_outputs[-1].update(result='stop_failed')
            self.status_revision += 1; self._write_session_json()
            self._log_failure('rosbag_stop', str(e), out)
            return False, f'rosbag stop failed: {e}'
        if saving:
            s.rosbag_finalizing = {'output': out, 'started_at': self.clock()}
            msg = f'rosbag stop requested; saving {out}'
        else:   # the process had already ended: nothing to wait for
            if s.rosbag_outputs: s.rosbag_outputs[-1].update(result='stopped')
            msg = 'rosbag recording stopped'
        self.status_revision += 1; self._write_session_json()
        return True, msg

    def rosbag_finalized(self, returncode, detail: str = '') -> tuple[bool, str]:
        """ros2 bag record ended after a stop request: the save is complete (exit code 0) or failed (recorded and shown)."""
        s = self.session
        if s is None or s.rosbag_finalizing is None:
            return False, 'no rosbag was being saved'
        f = s.rosbag_finalizing; s.rosbag_finalizing = None
        ok = returncode == 0
        result = 'stopped' if ok else 'save_failed'
        for o in reversed(s.rosbag_outputs):
            if o['output'] == f['output']:
                o.update(result=result, saved_at=self.clock(), exit_code=returncode); break
        s.last_finalize = {'output': f['output'], 'started_at': f['started_at'], 'finished_at': self.clock(), 'ok': ok, 'exit_code': returncode}
        if not ok:
            error = f'ros2 bag record ended with exit code {returncode} while saving; {detail}'.strip().rstrip(';')
            s.failures.append({'time': self.clock(), 'what': 'rosbag_save', 'error': error, 'output': f['output']})
            self._log_failure('rosbag_save', error, f['output'])
        self.status_revision += 1; self._write_session_json()
        return ok, (f"rosbag saved: {f['output']}" if ok else f"rosbag save failed (exit code {returncode}): {f['output']}")

    def rosbag_exited(self, returncode, detail: str = '') -> tuple[bool, str]:
        """The `ros2 bag record` process ended without a stop request (start refused, disk full, crash). The rosbag is
        marked stopped and the failure is recorded and shown (RQ-I015: reported, driving is not stopped)."""
        s = self.session
        if s is None or not s.rosbag_active:
            return False, 'rosbag was not active'
        out = s.rosbag_outputs[-1]['output'] if s.rosbag_outputs else ''
        error = f'ros2 bag record exited without a stop request (exit code {returncode}); {detail}'.strip().rstrip(';')
        s.failures.append({'time': self.clock(), 'what': 'rosbag_exited', 'error': error, 'output': out})
        s.rosbag_active = False; s.rosbag_started_by = ''
        if s.rosbag_outputs and s.rosbag_outputs[-1]['stopped_at'] is None:
            s.rosbag_outputs[-1].update(stopped_at=self.clock(), result='failed', exit_code=returncode)
        self.status_revision += 1; self._write_session_json()
        self._log_failure('rosbag_exited', error, out)
        return True, f'rosbag recording failed: {error} ({out})'

    def _log_failure(self, what: str, error: str, output: str) -> None:
        """A recording failure is written to the log when the log is running (the record of the failure itself)."""
        s = self.session
        if s is not None and s.log_active:
            self._append(s.directory / 'log' / 'events.jsonl', {'t': self.clock(), 'kind': 'record_failure', 'what': what, 'error': error, 'output': output})

    # ---- received inputs and decisions ----
    def record(self, kind: str, topic: str, received_at: float, payload: dict) -> bool:
        """Append one received message (input or decision) to the log. Only what was received is written (RQ-I015).
        Returns False (and opens a failure gap) when the write fails; the caller keeps running."""
        self.last_received[topic] = (kind, received_at, payload)
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
            'rosbag_output': (s.rosbag_outputs[-1]['output'] if s and s.rosbag_outputs and s.rosbag_active else ''),
            'last_failure': (f"{s.failures[-1]['what']}: {s.failures[-1]['error']}"[:300] if s and s.failures else ''),
            'rosbag_saving': bool(s and s.rosbag_finalizing),
            'rosbag_saving_output': (s.rosbag_finalizing['output'] if s and s.rosbag_finalizing else ''),
            'rosbag_saving_started_at': (s.rosbag_finalizing['started_at'] if s and s.rosbag_finalizing else ''),
            'rosbag_last_save': (json.dumps(s.last_finalize, ensure_ascii=False) if s and s.last_finalize else ''),
        }
