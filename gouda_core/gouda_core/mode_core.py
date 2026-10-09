"""Mode manager core (ND-03, stage 5-1 scope): boot transitions and the mode/state record.

Design references (design/model.yaml): SO-01 (software_mode, previous_mode_record, initial_pose_received_after_restart),
TR-01 (boot -> 手動走行 when there is no persisted record or it is 手動走行), TR-02 (PC restart -> 一時停止 when the
persisted previous mode is 自律走行/事前地図作成/一時停止; walking is never resumed without a human operation:
RQ-I025, RQ-I064, DEC-009). This module has no ROS dependency; the node wraps it.

Nothing here starts recording: the boot transition is not an auto-record trigger (RQ-I015).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

MODE_MANUAL = 'manual'        # 手動走行 (SoftwareMode.MODE_MANUAL = 1)
MODE_MAPPING = 'mapping'      # 事前地図作成 (2)
MODE_AUTONOMY = 'autonomy'    # 自律走行 (3)
MODE_PAUSE = 'pause'          # 一時停止 (4)
MODES = (MODE_MANUAL, MODE_MAPPING, MODE_AUTONOMY, MODE_PAUSE)  # exactly four (RQ-I065)
MODE_CODES = {MODE_MANUAL: 1, MODE_MAPPING: 2, MODE_AUTONOMY: 3, MODE_PAUSE: 4}

TRANSITION_BOOT_MANUAL = 'TR-01'
TRANSITION_PC_RESTART_PAUSE = 'TR-02'


@dataclass
class PreviousModeRecord:
    """SO-01 previous_mode_record (persisted). Written on every transition; read once at boot."""
    mode: str
    human_pause_or_end: bool = False   # a human pause/end preceded this record (RQ-I025)
    run_id: str = ''
    state_revision: int = 0

    @classmethod
    def load(cls, path: Path) -> Optional['PreviousModeRecord']:
        """Return the persisted record, or None when there is no readable record.

        An unreadable or malformed file is treated as "no record" (boot -> manual, TR-01) and reported by the caller;
        the content is never guessed.
        """
        try:
            raw = json.loads(Path(path).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None
        if not isinstance(raw, dict) or raw.get('mode') not in MODES:
            return None
        return cls(mode=raw['mode'], human_pause_or_end=bool(raw.get('human_pause_or_end', False)),
                   run_id=str(raw.get('run_id', '')), state_revision=int(raw.get('state_revision', 0)))

    def save(self, path: Path) -> None:
        p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + '.tmp')
        tmp.write_text(json.dumps(asdict(self), ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
        tmp.replace(p)  # atomic replace: a partially written record is never visible


@dataclass
class ModeState:
    """The fields of IFD-01 mode/state owned by the mode manager."""
    mode: str
    processing_state: str = 'idle'
    run_id: str = ''
    remaining_waypoints: int = 0
    current_section: int = -1
    stop_reason: str = ''
    speed_limit_application_state: str = 'unknown'
    previous_mode: str = ''
    human_pause_or_end_recorded: bool = False
    initial_pose_required: bool = False
    state_revision: int = 0

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class BootDecision:
    transition_id: str
    state: ModeState
    reason: str
    record_found: bool
    details: dict = field(default_factory=dict)


def decide_boot(record: Optional[PreviousModeRecord]) -> BootDecision:
    """Apply TR-01 / TR-02 to the persisted previous-mode record.

    - No record, or previous mode 手動走行 -> 手動走行 (TR-01). Recording is not started (RQ-I015).
    - Previous mode 自律走行 / 事前地図作成 / 一時停止 -> 一時停止 (TR-02). Autonomy is not re-permitted; a human initial
      pose request is required before resume (DEC-009); a human pause/end flag is kept (RQ-I025).
    The returned state_revision continues from the record so that an old value is never re-published as newer.
    """
    base_rev = record.state_revision if record else 0
    if record is None or record.mode == MODE_MANUAL:
        state = ModeState(mode=MODE_MANUAL, previous_mode=record.mode if record else '',
                          human_pause_or_end_recorded=record.human_pause_or_end if record else False,
                          state_revision=base_rev + 1)
        reason = ('persisted previous mode is manual' if record else 'no persisted previous mode record') + ' -> manual (RQ-I080)'
        return BootDecision(TRANSITION_BOOT_MANUAL, state, reason, record is not None,
                            {'previous_mode': record.mode if record else None})
    state = ModeState(mode=MODE_PAUSE, previous_mode=record.mode, human_pause_or_end_recorded=record.human_pause_or_end,
                      run_id=record.run_id, initial_pose_required=True, stop_reason='', state_revision=base_rev + 1)
    reason = (f'persisted previous mode is {record.mode} -> pause (RQ-I064); autonomy is not re-permitted; '
              'resume only by a human operation after an initial pose request (RQ-I025, DEC-009)')
    return BootDecision(TRANSITION_PC_RESTART_PAUSE, state, reason, True,
                        {'previous_mode': record.mode, 'human_pause_or_end': record.human_pause_or_end, 'run_id': record.run_id})


def record_after_boot(decision: BootDecision) -> PreviousModeRecord:
    """The record to persist after the boot transition (human pause/end flag is preserved, never cleared by a restart)."""
    s = decision.state
    return PreviousModeRecord(mode=s.mode, human_pause_or_end=s.human_pause_or_end_recorded, run_id=s.run_id, state_revision=s.state_revision)


# ---------------------------------------------------------------------------------------------------------------------
# Human mode operations (stage 5-2 scope: the service endpoints of ND-03 and their guards).
# Each event maps to the design transition(s). A request is accepted only when the current mode matches the
# transition's from-mode and the guard holds, and the transition's actions are implemented in the current build;
# otherwise it is refused with a reason (never silently). Nothing here starts a recording or sends a goal.
# ---------------------------------------------------------------------------------------------------------------------

EVENT_TRANSITIONS = {
    # event: list of (from_mode, to_mode, transition_id, stage_that_implements_it)
    'start_mapping': [(MODE_MANUAL, MODE_MAPPING, 'TR-03', '5-3 地図作成と変換')],
    'end_mapping': [(MODE_MAPPING, MODE_MANUAL, 'TR-04', '5-3 地図作成と変換')],
    'start_autonomy': [(MODE_MANUAL, MODE_AUTONOMY, 'TR-05', '5-6 自律走行の為の最小構成')],
    'pause': [(MODE_AUTONOMY, MODE_PAUSE, 'TR-06', '5-7 blocked・一時停止・復帰')],
    'resume': [(MODE_PAUSE, MODE_AUTONOMY, 'TR-10', '5-7 blocked・一時停止・復帰')],
    'end_autonomy': [(MODE_AUTONOMY, MODE_MANUAL, 'TR-11', '5-7 blocked・一時停止・復帰'),
                     (MODE_PAUSE, MODE_MANUAL, 'TR-12', '5-7 blocked・一時停止・復帰')],
}
HUMAN_EVENTS = tuple(EVENT_TRANSITIONS)


@dataclass
class RequestResult:
    accepted: bool
    transition_id: str
    reason: str
    new_state: Optional[ModeState] = None


def request_transition(event: str, state: ModeState, implemented: frozenset = frozenset()) -> RequestResult:
    """Evaluate a human mode operation against the transition table and guards.

    `implemented` names the transition ids whose actions exist in this build. A transition that is not implemented is
    refused with its stage, so that pressing a button never pretends a mode change happened (RQ-I028).
    """
    if event not in EVENT_TRANSITIONS:
        return RequestResult(False, '', f'unknown event {event!r}')
    candidates = EVENT_TRANSITIONS[event]
    match = next((c for c in candidates if c[0] == state.mode), None)
    if match is None:
        allowed = '／'.join(c[0] for c in candidates)
        return RequestResult(False, candidates[0][2], f'refused: {event} is not accepted in mode {state.mode} (accepted in {allowed})')
    from_mode, to_mode, tid, stage = match
    if tid == 'TR-10' and state.initial_pose_required:
        return RequestResult(False, tid, 'refused: resume after a PC restart requires a human initial pose request first (DEC-009)')
    if tid not in implemented:
        return RequestResult(False, tid, f'refused: {tid} ({from_mode} -> {to_mode}) is not implemented in this build; it belongs to stage {stage}')
    new = ModeState(**{**state.as_dict(), 'mode': to_mode, 'previous_mode': from_mode, 'state_revision': state.state_revision + 1})
    return RequestResult(True, tid, f'{tid}: {from_mode} -> {to_mode}', new)
