"""Monitor core (ND-02 gouda_monitor): state aggregation for display and the persisted sensor configuration.

No ROS dependency. The node feeds received messages in; the HTTP server reads snapshots out.

Display rules (design/docs/gouda_gui_design_rules.md §7, DEC-006, DEC-014):
- a value that was never received is shown as NOT_RECEIVED, never as OK;
- STALE (received, but older than a known threshold) is distinct from ERROR; while a freshness threshold is unresolved
  (PRM-15 / PRM-16 tbd) only the age is shown, with the verdict "threshold unresolved";
- repeated identical events keep their count and last time;
- nothing is invented to fill a field; the external display areas and the ESP32 block report UNAVAILABLE / UNKNOWN.

Sensor configuration (/config, IFD-26, RQ-I070): kept server-side in a JSON file so it survives tab changes and browser
reloads; every field is UNKNOWN until a measured value is entered; each save bumps config_revision.
"""
from __future__ import annotations

import json
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

MODE_NAMES = {0: 'UNKNOWN', 1: 'MANUAL', 2: 'MAPPING', 3: 'AUTONOMY', 4: 'PAUSE'}
MODE_LABELS_JA = {0: '不明', 1: '手動走行', 2: '事前地図作成', 3: '自律走行', 4: '一時停止'}
NOT_RECEIVED = 'NOT_RECEIVED'
UNAVAILABLE = 'UNAVAILABLE'
UNKNOWN = 'UNKNOWN'

# /config fields (RQ-I070). Mount values are metres / radians in the body frame (REP-103, PRM-07); the axis mapping of a
# sensor is the text used by the static TF publisher (ND-13, stage 5-6). All start as UNKNOWN; none has a default value.
CONFIG_FIELDS = OrderedDict([
    ('lidar_mount_x_m', 'number'), ('lidar_mount_y_m', 'number'), ('lidar_mount_z_m', 'number'),
    ('lidar_mount_roll_rad', 'number'), ('lidar_mount_pitch_rad', 'number'), ('lidar_mount_yaw_rad', 'number'),
    ('lidar_axis_mapping', 'text'),
    ('imu_mount_x_m', 'number'), ('imu_mount_y_m', 'number'), ('imu_mount_z_m', 'number'),
    ('imu_mount_roll_rad', 'number'), ('imu_mount_pitch_rad', 'number'), ('imu_mount_yaw_rad', 'number'),
    ('imu_axis_mapping', 'text'),
])


@dataclass
class Received:
    data: dict
    received_at: float


@dataclass
class EventAggregate:
    key: tuple
    first_at: float
    last_at: float
    count: int
    sample: dict


@dataclass
class Freshness:
    status: str          # NOT_RECEIVED | RECEIVED | STALE
    age_s: Optional[float]
    verdict: str         # human readable


def freshness(rec: Optional[Received], now: float, stale_after_s: Optional[float]) -> Freshness:
    if rec is None:
        return Freshness(NOT_RECEIVED, None, '未受信（OK とは表示しない）')
    age = max(0.0, now - rec.received_at)
    if stale_after_s is None:
        return Freshness('RECEIVED', age, '受信あり。鮮度のしきい値は未確定（PRM-15／PRM-16）のため STALE 判定はしない')
    if age > stale_after_s:
        return Freshness('STALE', age, f'最終受信から {age:.1f} s 経過（しきい値 {stale_after_s} s）')
    return Freshness('RECEIVED', age, f'最終受信から {age:.1f} s')


class MonitorCore:
    def __init__(self, clock: Callable[[], float] = time.time, max_events: int = 200):
        self.clock = clock
        self.mode: Optional[Received] = None
        self.record: Optional[Received] = None
        self.esp32: Optional[Received] = None          # IFD-38: nothing until stage 5-5
        self.nodes: list = []                            # names seen on the graph (ND-02 reads them periodically)
        self.nodes_at: Optional[float] = None
        self.events: "OrderedDict[tuple, EventAggregate]" = OrderedDict()
        self.max_events = max_events
        self.command_log: list = []                      # last results of human commands (for the log pane)
        self.connection_revision = 0                     # bumps on every change; SSE clients use it
        self.stale_after_mode_s: Optional[float] = None  # PRM-16 (tbd)
        self.stale_after_esp32_s: Optional[float] = None # PRM-15 (tbd)

    # ---- inputs ----
    def on_mode(self, data: dict, received_at: Optional[float] = None):
        self.mode = Received(data, received_at if received_at is not None else self.clock()); self.connection_revision += 1

    def on_record(self, data: dict, received_at: Optional[float] = None):
        self.record = Received(data, received_at if received_at is not None else self.clock()); self.connection_revision += 1

    def on_esp32(self, data: dict, received_at: Optional[float] = None):
        self.esp32 = Received(data, received_at if received_at is not None else self.clock()); self.connection_revision += 1

    def on_nodes(self, names: list):
        self.nodes = sorted(names); self.nodes_at = self.clock(); self.connection_revision += 1

    def on_decision(self, data: dict, received_at: Optional[float] = None):
        """Aggregate identical events (node, event, transition_id, reason): count and last time are never lost."""
        t = received_at if received_at is not None else self.clock()
        key = (data.get('node', ''), data.get('event', ''), data.get('transition_id', ''), data.get('reason', ''))
        agg = self.events.get(key)
        if agg is None:
            agg = EventAggregate(key, t, t, 0, data)
            self.events[key] = agg
            while len(self.events) > self.max_events:
                self.events.popitem(last=False)
        agg.count += 1; agg.last_at = t; agg.sample = data
        self.events.move_to_end(key)
        self.connection_revision += 1

    def on_command_result(self, name: str, ok: bool, message: str):
        self.command_log.append({'t': self.clock(), 'command': name, 'ok': ok, 'message': message})
        self.command_log = self.command_log[-50:]
        self.connection_revision += 1

    # ---- snapshot for display ----
    def snapshot(self, now: Optional[float] = None) -> dict:
        now = self.clock() if now is None else now
        fm = freshness(self.mode, now, self.stale_after_mode_s)
        fr = freshness(self.record, now, None)
        fe = freshness(self.esp32, now, self.stale_after_esp32_s)
        mode_code = int(self.mode.data.get('mode', 0)) if self.mode else 0
        return {
            'now': now, 'revision': self.connection_revision,
            'mode': {
                'freshness': fm.__dict__, 'code': mode_code, 'name': MODE_NAMES.get(mode_code, 'UNKNOWN'), 'label': MODE_LABELS_JA.get(mode_code, '不明'),
                'fields': self.mode.data if self.mode else {},
            },
            'record': {'freshness': fr.__dict__, 'fields': self.record.data if self.record else {}},
            'esp32': {'freshness': fe.__dict__, 'fields': self.esp32.data if self.esp32 else {},
                      'note': 'ESP32 STATUS は工程5-5（車体出力）で受信する。取得できる項目は新 firmware の STATUS 定義に従い、取得できない項目は常に不明（DEC-006）' if not self.esp32 else ''},
            'nodes': {'names': self.nodes, 'at': self.nodes_at, 'age_s': (now - self.nodes_at) if self.nodes_at else None},
            'external_displays': {
                'navigation': {'status': UNAVAILABLE, 'note': '外部可視化（RViz2 等）の埋込方式は未確定。描画はこの画面で再実装しない（デザインルール §6）'},
                'lidar_localization': {'status': UNAVAILABLE, 'note': '外部可視化（RViz2 等）の埋込方式は未確定。センサーは未接続'},
            },
            'events': [{'node': a.key[0], 'event': a.key[1], 'transition_id': a.key[2], 'reason': a.key[3], 'count': a.count,
                        'first_at': a.first_at, 'last_at': a.last_at, 'details': a.sample.get('details', '')} for a in reversed(self.events.values())],
            'commands': list(reversed(self.command_log)),
        }


class SensorConfig:
    """/config (IFD-26): persisted JSON, fields UNKNOWN until a measured value is entered (RQ-I070)."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.values = OrderedDict((k, UNKNOWN) for k in CONFIG_FIELDS)
        self.config_revision = 0
        self.updated_at: Optional[float] = None
        self.load()

    def load(self) -> bool:
        try:
            raw = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return False
        if not isinstance(raw, dict): return False
        vals = raw.get('values', {})
        for k in CONFIG_FIELDS:
            v = vals.get(k, UNKNOWN)
            self.values[k] = v if self._valid(k, v) else UNKNOWN
        self.config_revision = int(raw.get('config_revision', 0)); self.updated_at = raw.get('updated_at')
        return True

    def _valid(self, key: str, value) -> bool:
        kind = CONFIG_FIELDS[key]
        if value == UNKNOWN: return True
        if kind == 'number': return isinstance(value, (int, float)) and not isinstance(value, bool)
        return isinstance(value, str) and value != ''

    def update(self, changes: dict, now: float) -> tuple[bool, str]:
        """Apply validated changes and persist atomically. Unknown keys or invalid values are refused as a whole."""
        parsed = {}
        for k, v in changes.items():
            if k not in CONFIG_FIELDS: return False, f'unknown config field {k!r}'
            if CONFIG_FIELDS[k] == 'number' and isinstance(v, str) and v.strip() not in ('', UNKNOWN):
                try: v = float(v)
                except ValueError: return False, f'{k}: not a number ({v!r})'
            if isinstance(v, str) and v.strip() in ('', UNKNOWN): v = UNKNOWN
            if not self._valid(k, v): return False, f'{k}: invalid value {v!r}'
            parsed[k] = v
        if not parsed: return True, 'no change'
        self.values.update(parsed); self.config_revision += 1; self.updated_at = now
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + '.tmp')
            tmp.write_text(json.dumps({'values': self.values, 'config_revision': self.config_revision, 'updated_at': now}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
            tmp.replace(self.path)
        except OSError as e:
            return False, f'saved in memory but writing {self.path} failed: {e}'
        return True, f'config revision {self.config_revision} saved ({len(parsed)} field(s))'

    def snapshot(self) -> dict:
        return {'values': dict(self.values), 'kinds': dict(CONFIG_FIELDS), 'config_revision': self.config_revision, 'updated_at': self.updated_at,
                'path': str(self.path), 'unknown_count': sum(1 for v in self.values.values() if v == UNKNOWN)}
