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

from gouda_core import sensor_extrinsics

MODE_NAMES = {0: 'UNKNOWN', 1: 'MANUAL', 2: 'MAPPING', 3: 'AUTONOMY', 4: 'PAUSE'}
MODE_LABELS_JA = {0: '不明', 1: '手動走行', 2: '事前地図作成', 3: '自律走行', 4: '一時停止'}
NOT_RECEIVED = 'NOT_RECEIVED'
UNAVAILABLE = 'UNAVAILABLE'
UNKNOWN = 'UNKNOWN'

# /config fields (RQ-I070). Mount values are metres / radians in the body frame (REP-103, PRM-07); the axis mapping of a
# sensor ('axes') is the text parsed by sensor_extrinsics (e.g. "+x forward, +y left, +z up"), used for GLIM's T_lidar_imu (TR-03)
# and by the static TF publisher (ND-13, stage 5-6). All start as UNKNOWN; none has a default value. The human sets them
# (intent.md:105); an UNKNOWN value is never asked about and never blocks anything.
CONFIG_FIELDS = OrderedDict([
    ('lidar_mount_x_m', 'number'), ('lidar_mount_y_m', 'number'), ('lidar_mount_z_m', 'number'),
    ('lidar_mount_roll_rad', 'number'), ('lidar_mount_pitch_rad', 'number'), ('lidar_mount_yaw_rad', 'number'),
    ('lidar_axis_mapping', 'axes'),
    ('imu_mount_x_m', 'number'), ('imu_mount_y_m', 'number'), ('imu_mount_z_m', 'number'),
    ('imu_mount_roll_rad', 'number'), ('imu_mount_pitch_rad', 'number'), ('imu_mount_yaw_rad', 'number'),
    ('imu_axis_mapping', 'axes'),
    # GNSS antenna phase centres in base_link (REV-061, ND-13 -> gnss_link / gnss_aux1_link; ND-19 reads them from TF)
    ('gnss_main_mount_x_m', 'number'), ('gnss_main_mount_y_m', 'number'), ('gnss_main_mount_z_m', 'number'),
    ('gnss_aux1_mount_x_m', 'number'), ('gnss_aux1_mount_y_m', 'number'), ('gnss_aux1_mount_z_m', 'number'),
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


class SensorReception:
    """Reception of one sensor topic as seen by the monitor (IFD-21 points, IFD-22 IMU; DEC-088). Display and the mapping-start
    warning only: never a stop condition (DEC-006 style). The monitor counts arrivals; it does not interpret the data."""

    def __init__(self, label: str, topic: str, history: int = 50):
        from collections import deque
        self.label, self.topic = label, topic
        self.arrivals = deque(maxlen=history)      # receive times; the rate is computed over these
        self.count = 0
        self.last_stamp: Optional[float] = None    # header.stamp of the last message (s), when it could be read
        self.last_at: Optional[float] = None

    def on_message(self, received_at: float, stamp: Optional[float] = None):
        self.arrivals.append(received_at); self.count += 1; self.last_at = received_at
        if stamp is not None: self.last_stamp = stamp

    def status(self, now: float, stale_after_s: Optional[float]) -> dict:
        f = freshness(Received({}, self.last_at) if self.last_at is not None else None, now, stale_after_s)
        a = list(self.arrivals)
        rate = (len(a) - 1) / (a[-1] - a[0]) if len(a) >= 2 and a[-1] > a[0] else None
        return {'label': self.label, 'topic': self.topic, 'status': f.status, 'age_s': f.age_s, 'verdict': f.verdict, 'rate_hz': rate,
                'count': self.count, 'stamp_minus_receive_s': (self.last_stamp - self.last_at) if self.last_stamp is not None and self.last_at is not None else None,
                'stale_after_s': stale_after_s}


# GNSS quality (IFD-48 PVTGeodetic.mode, IFD-49 AttEuler.mode; REV-061). Meaning of the codes from the Septentrio SBF
# reference (mosaic): 原本未照合 — written from the AI's knowledge of the SBF definition, to be checked against the receiver's
# reference guide. The monitor only displays them; nothing is decided from them.
PVT_MODE_JA = {0: '測位なし', 1: '単独測位', 2: 'DGNSS', 3: '固定位置', 4: 'RTK fix', 5: 'RTK float', 6: 'SBAS', 7: '移動基準 RTK fix',
               8: '移動基準 RTK float', 10: 'PPP'}
ATT_MODE_JA = {0: '向きなし', 1: '向きあり（float）', 2: '向きあり（fix）', 3: '向き・ロールあり（float）', 4: '向き・ロールあり（fix）'}
SBF_DO_NOT_USE_FLOAT = -2e10      # SBF "Do-Not-Use" value of float fields (same reference, 原本未照合)


def gnss_quality_text(mode: int, nr_sv: int, h_accuracy_cm: Optional[int]) -> str:
    kind = PVT_MODE_JA.get(mode & 0x0F, f'不明（{mode & 0x0F}）')
    acc = '' if h_accuracy_cm is None or h_accuracy_cm == 0xFFFF else f'、水平精度 {h_accuracy_cm / 100:.2f} m'
    return f'{kind}、衛星 {nr_sv}{acc}'


def gnss_attitude_text(mode: int, heading_deg: float) -> str:
    kind = ATT_MODE_JA.get(mode, f'不明（{mode}）')
    if mode == 0 or heading_deg <= SBF_DO_NOT_USE_FLOAT / 2:
        return kind
    return f'{kind}、heading {heading_deg:.1f} 度'


MAPPING_START_SENSORS = ('points', 'imu')   # the mapping-start warning (DEC-088) is about GLIM's inputs only


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
        self.sensors = {'points': SensorReception('XT-32 点群', 'sensors/xt32/points'), 'imu': SensorReception('IMU', 'sensors/imu/data'),
                        'gnss': SensorReception('GNSS 位置', 'sensors/gnss/navsatfix')}  # IFD-21 / IFD-22 / IFD-47
        self.stale_after_sensor_s: dict = {'points': None, 'imu': None, 'gnss': None}   # PRM-57 / PRM-58; GNSS has no threshold (no STALE)
        self.gnss_detail: dict = {}                        # 'quality' (IFD-48), 'attitude' (IFD-49), or 'note' when the driver's types are absent
        self.settings: dict = {}                           # effective UI parameters (PRM-27..32) for display

    # ---- inputs ----
    def on_mode(self, data: dict, received_at: Optional[float] = None):
        self.mode = Received(data, received_at if received_at is not None else self.clock()); self.connection_revision += 1

    def on_record(self, data: dict, received_at: Optional[float] = None):
        self.record = Received(data, received_at if received_at is not None else self.clock()); self.connection_revision += 1

    def on_esp32(self, data: dict, received_at: Optional[float] = None):
        self.esp32 = Received(data, received_at if received_at is not None else self.clock()); self.connection_revision += 1

    def on_sensor(self, key: str, received_at: Optional[float] = None, stamp: Optional[float] = None):
        self.sensors[key].on_message(received_at if received_at is not None else self.clock(), stamp)

    def on_gnss_detail(self, key: str, text: str):
        self.gnss_detail[key] = text

    def sensors_snapshot(self, now: Optional[float] = None) -> dict:
        now = self.clock() if now is None else now
        out = {k: s.status(now, self.stale_after_sensor_s.get(k)) for k, s in self.sensors.items()}
        out['gnss']['detail'] = '、'.join(self.gnss_detail[k] for k in ('quality', 'attitude', 'note') if self.gnss_detail.get(k))
        return out

    def mapping_start_warning(self, now: Optional[float] = None) -> Optional[str]:
        """Text of the warning shown when 地図作成開始 is pressed while a sensor has no data (DEC-088); None when both are
        receiving. The start itself is not refused (no additional approval step: RQ-I011)."""
        problems = []
        for k, st in self.sensors_snapshot(now).items():
            if k not in MAPPING_START_SENSORS:
                continue
            if st['status'] == 'NOT_RECEIVED':
                problems.append(f"{st['label']}（{st['topic']}）を受信していない")
            elif st['status'] == 'STALE':
                problems.append(f"{st['label']}（{st['topic']}）が {st['age_s']:.1f} s 届いていない（しきい値 {st['stale_after_s']} s）")
        if not problems:
            return None
        return '地図作成の開始時にセンサーのデータがない: ' + '、'.join(problems) + '。GLIM は動くが地図はできない。センサーの接続を確認する'

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
            'sensors': self.sensors_snapshot(now),
            'external_displays': {
                'navigation': {'status': UNAVAILABLE, 'note': '外部可視化（RViz2 等）の埋込方式は未確定。描画はこの画面で再実装しない（デザインルール §6）'},
                'lidar_localization': {'status': UNAVAILABLE, 'note': '外部可視化（RViz2 等）の埋込方式は未確定。センサーの受信状況はこの欄の上の表'},
            },
            'events': [{'node': a.key[0], 'event': a.key[1], 'transition_id': a.key[2], 'reason': a.key[3], 'count': a.count,
                        'first_at': a.first_at, 'last_at': a.last_at, 'details': a.sample.get('details', '')} for a in reversed(self.events.values())],
            'commands': list(reversed(self.command_log)),
            'settings': self.settings,
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
        if kind == 'axes': return isinstance(value, str) and sensor_extrinsics.validate_axis_mapping(value) is None
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
            if CONFIG_FIELDS[k] == 'axes' and v != UNKNOWN and sensor_extrinsics.validate_axis_mapping(v):
                return False, f'{k}: {sensor_extrinsics.validate_axis_mapping(v)}'
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
        notes = [f'{k} is left-handed (not a rotation; base_link axes are used for it)' for k, v in parsed.items()
                 if CONFIG_FIELDS[k] == 'axes' and v != UNKNOWN and sensor_extrinsics.determinant(sensor_extrinsics.parse_axis_mapping(v)) < 0]
        return True, f'config revision {self.config_revision} saved ({len(parsed)} field(s))' + ('. WARNING: ' + '; '.join(notes) if notes else '')

    def snapshot(self) -> dict:
        return {'values': dict(self.values), 'kinds': dict(CONFIG_FIELDS), 'config_revision': self.config_revision, 'updated_at': self.updated_at,
                'path': str(self.path), 'unknown_count': sum(1 for v in self.values.values() if v == UNKNOWN)}
