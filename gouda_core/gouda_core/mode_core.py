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
    if to_mode in (MODE_MAPPING, MODE_AUTONOMY):
        new = ModeState(**{**new.as_dict(), 'stop_reason': ''})   # a new activity starts: the previous stop reason no longer applies
    if event == 'pause':
        # TR-06: a human pause. Persisted so that no restart resumes driving without a human operation (RQ-I025).
        new = ModeState(**{**new.as_dict(), 'human_pause_or_end_recorded': True, 'stop_reason': 'human'})
    if event in ('start_autonomy', 'resume'):
        # TR-05 / TR-10: the human start / resume operation itself; the earlier human pause/end no longer holds (TR-10 action).
        new = ModeState(**{**new.as_dict(), 'human_pause_or_end_recorded': False, 'stop_reason': ''})
    if event == 'end_autonomy':
        # TR-11 / TR-12: a human end. The flag is persisted so that no restart resumes driving (RQ-I025); the mission ends and
        # the initial-pose requirement of a resumed pause no longer applies in manual.
        new = ModeState(**{**new.as_dict(), 'human_pause_or_end_recorded': True, 'initial_pose_required': False, 'run_id': '', 'stop_reason': 'human'})
    return RequestResult(True, tid, f'{tid}: {from_mode} -> {to_mode}', new)


# ---------------------------------------------------------------------------------------------------------------------
# Automatic transitions from the Nav2 result (stage 5-6): TR-07 (BT failure) and TR-08 (last waypoint reached). Both go to
# 一時停止 without a human flag (RQ-I017, RQ-I012); resuming needs the human resume (TR-10, RQ-I025). TR-07 also covers 推定不能
# (REV-128, DEC-200) with its own stop reason, so that it is told apart from the plan failure (RQ-I029).
# ---------------------------------------------------------------------------------------------------------------------
STOP_REASON_PLAN_FAILURE = 'plan_failure'       # 計画の失敗 (ComputePath* error codes since REV-183; Nav2 BT failed after its own recovery: RQ-I012)
STOP_REASON_NODE_FAILURE = 'node_failure'       # node の異常 (the autonomy start failed: Nav2 / vehicle output / goal)
STOP_REASON_GOAL_REACHED = 'goal_reached'       # 最終 waypoint 到達 (TR-08)
STOP_REASON_ESTIMATOR = 'estimator_unavailable'   # 推定不能 (ND-07 state IFD-53 not 正常, or no state: DEC-200, REV-128)
# E-4 (REV-183, DEC-393): a Nav2 goal failure is told apart by its error code (autonomy_core.nav2_failure_reason)
STOP_REASON_BLOCKED = 'blocked'                   # FollowPath: patience exceeded / no progress / no valid control (an obstacle)
STOP_REASON_CONTROLLER = 'controller_failure'     # FollowPath: other codes (unknown, invalid controller / path, timed out)
STOP_REASON_NAV2_TF = 'nav2_tf_error'             # FollowPath / ComputePath*: TF_ERROR (a transform too old or missing)
STOP_REASON_NAV2_NO_CODE = 'nav2_no_error_code'   # no error code (e.g. an action server that did not acknowledge in time)
STOP_REASON_NAV2_OTHER = 'nav2_unclassified'      # a code that is in none of the tables above


def automatic_pause(state: ModeState, transition_id: str, stop_reason: str, remaining_waypoints: int) -> Optional[ModeState]:
    """The 一時停止 state after TR-07 / TR-08, or None when the mode is not 自律走行 (then nothing happens)."""
    if state.mode != MODE_AUTONOMY or transition_id not in ('TR-07', 'TR-08'):
        return None
    return ModeState(**{**state.as_dict(), 'mode': MODE_PAUSE, 'previous_mode': MODE_AUTONOMY, 'stop_reason': stop_reason,
                        'remaining_waypoints': remaining_waypoints, 'state_revision': state.state_revision + 1})


# ---------------------------------------------------------------------------------------------------------------------
# 一時停止線 (DEC-482, REV-263): a stage inside 自律走行 (intent.md:101), not 待機. Reaching a waypoint of kind stop holds the
# robot (motion_hold=true, no goal) with processing_state rule_stop_hold and stop_reason rule_stop; nothing restarts by itself.
# The human's resume (the same 再開 button / mode/resume as TR-10, DEC-345) sends the goal from the waypoint after it.
# ---------------------------------------------------------------------------------------------------------------------
STOP_REASON_RULE_STOP = 'rule_stop'               # 停止線で停止中 (waiting for the human's resume)
PROCESSING_RULE_STOP_HOLD = 'rule_stop_hold'


def rule_stop_hold(state: ModeState, stop_index: int, total: int) -> Optional[ModeState]:
    """The state held at stop point stop_index, or None when the mode is not 自律走行 (then nothing happens)."""
    if state.mode != MODE_AUTONOMY:
        return None
    return ModeState(**{**state.as_dict(), 'processing_state': PROCESSING_RULE_STOP_HOLD, 'stop_reason': STOP_REASON_RULE_STOP,
                        'current_section': stop_index, 'remaining_waypoints': total - stop_index - 1, 'state_revision': state.state_revision + 1})


def rule_stop_resume(state: ModeState) -> RequestResult:
    """The human's resume while held at a stop point: accepted only in 自律走行 with rule_stop_hold (the caller checks the goal,
    Nav2 and ND-07 as TR-10 does). Elsewhere the resume is evaluated by request_transition as before."""
    if state.mode != MODE_AUTONOMY or state.processing_state != PROCESSING_RULE_STOP_HOLD:
        return RequestResult(False, '', 'refused: not held at a stop point')
    new = ModeState(**{**state.as_dict(), 'processing_state': 'idle', 'stop_reason': '', 'state_revision': state.state_revision + 1})
    return RequestResult(True, '', 'rule stop: resumed by the human (DEC-482)', new)
