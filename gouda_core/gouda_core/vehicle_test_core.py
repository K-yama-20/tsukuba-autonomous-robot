"""Vehicle tests of the /dev tab (ND-20): the parts every test shares. No ROS dependency; gouda_vehicle_test wraps it.

A test is a module in gouda_core/vehicle_tests/ (build_trials, analyze) plus a YAML file of the same name with its conditions, listed
in vehicle_tests/__init__.py. A test only describes trials; running, stopping, recording and showing them are here and in the node,
so adding a test does not touch them. Every value (conditions, detection, waits) comes from the YAML file or the /dev tab.

A trial is neutral for settle_s, then segments of a fixed stick command. A segment can watch the IMU and end early on motion, which
keeps the distance small. The stick command (forward, turn in [-1, 1]) goes to vehicle/joystick_command (IFD-16), the point after
gouda_motion_controller, so the measurement is free of the dead-band compensation and covers bridge, firmware, DAC and vehicle.

Motion is judged from the deviation from a mean taken in the neutral just before a segment: forward acceleration and yaw rate in
base_link when the IMU's TF is known, the norms of both vectors otherwise. The first excursion may be the shock of the lock release and
not motion, so the first sample over the threshold and the first sustained excursion are kept apart and the waveform stays in the
record. Nothing here judges a pass: the results are measurements for a human to read.
"""
from __future__ import annotations

import csv
import json
import math
import re
import statistics
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml

END_NEXT, END_TRIAL, CONTINUE = 'next', 'end_trial', 'continue'
SIG_ACCEL, SIG_YAW, SIG_BOTH = 'accel', 'yaw', 'both'
END_COMPLETED, END_CANCELLED, END_MODE, END_MANUAL, END_IMU, END_STATUS, END_REFUSED, END_ERROR = (
    'completed', 'cancelled', 'mode_changed', 'manual_override', 'imu_lost', 'status_lost', 'refused', 'error')
IMU_COLUMNS = ['t', 'ax', 'ay', 'az', 'wx', 'wy', 'wz', 'signal_accel', 'signal_yaw']
STATUS_COLUMNS = ['t_rx', 'uptime_ms', 'source', 'reason', 'dac_x', 'dac_y', 'applied_x_q10000', 'applied_y_q10000', 'last_pc_seq', 'pc_age_ms']
COMMAND_COLUMNS = ['t', 'forward', 'turn', 'trial', 'segment']


def stick(angle_deg: float, amount: float) -> tuple:
    """(forward, turn) of an amount along a direction of the stick plane: 0 = forward, 90 = turn left, 180 = reverse, 270 = turn right."""
    a = math.radians(angle_deg)
    f, t = amount * math.cos(a), amount * math.sin(a)
    return (0.0 if abs(f) < 1e-9 else f, 0.0 if abs(t) < 1e-9 else t)


def signal_for(forward: float, turn: float) -> str:
    return SIG_BOTH if forward and turn else SIG_YAW if turn else SIG_ACCEL


@dataclass
class Segment:
    label: str
    forward: float
    turn: float
    duration_s: float
    detect: bool = False
    on_motion: str = CONTINUE     # what a detected motion does
    on_timeout: str = END_NEXT    # what the end of duration_s without motion does when detect is true


@dataclass
class Trial:
    id: str
    section: str
    label: str
    settle_s: float
    segments: List[Segment]
    info: dict = field(default_factory=dict)   # the conditions the analysis reads


# ---- conditions ----
def load_definition(path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding='utf-8'))


def validate_params(definition: dict, given: dict) -> tuple:
    """(values, errors). A missing key takes the default in the YAML file; a value outside its range is refused."""
    values, errors = {}, []
    sections = [s['key'] for s in definition.get('sections', [])]
    for p in definition['parameters']:
        k, kind = p['key'], p['kind']
        v = given.get(k, p.get('default'))
        try:
            if kind == 'sections':
                v = [str(x) for x in v]
                bad = [x for x in v if x not in sections]
                if bad: errors.append(f'{k}: unknown {bad}')
            elif kind == 'numbers':
                v = [float(x) for x in v]
                if not v: errors.append(f'{k}: empty')
                if any(not math.isfinite(x) or x < p['min'] or x > p['max'] for x in v): errors.append(f"{k}: outside {p['min']}..{p['max']}")
            else:
                v = float(v)
                if not math.isfinite(v) or v < p['min'] or v > p['max']: errors.append(f"{k}: {v} outside {p['min']}..{p['max']}")
                if p.get('integer'): v = int(v)
        except (TypeError, ValueError):
            errors.append(f'{k}: {v!r} is not valid')
        values[k] = v
    return values, errors


# ---- detection ----
class Excursion:
    """First sample over the threshold and the first run of sustain_s over it, for one signal. feed() returns True once sustained."""

    def __init__(self, mean: float, threshold: float, sustain_s: float):
        self.mean, self.threshold, self.sustain_s = mean, threshold, sustain_s
        self.first = None; self.sustained = None; self.peak = 0.0; self._run_start = None

    def feed(self, t: float, value: float) -> bool:
        d = abs(value - self.mean)
        self.peak = max(self.peak, d)
        if d > self.threshold:
            if self.first is None: self.first = t
            if self._run_start is None: self._run_start = t
            if self.sustained is None and t - self._run_start >= self.sustain_s: self.sustained = t
        else:
            self._run_start = None
        return self.sustained is not None


class Baseline:
    """Noise (standard deviation) of each signal in the first neutral, and the recent mean used just before a segment."""

    def __init__(self, tail_s: float):
        self.tail_s = tail_s; self.tail = deque(); self.noise = {SIG_ACCEL: [], SIG_YAW: []}; self.sigma = None

    def feed(self, t: float, accel: float, yaw: float, collecting: bool):
        self.tail.append((t, accel, yaw))
        while self.tail and t - self.tail[0][0] > self.tail_s: self.tail.popleft()
        if collecting:
            self.noise[SIG_ACCEL].append(accel); self.noise[SIG_YAW].append(yaw)

    def freeze(self):
        if len(self.noise[SIG_ACCEL]) >= 2:
            self.sigma = {k: statistics.pstdev(v) for k, v in self.noise.items()}
        return self.sigma

    def means(self) -> Optional[dict]:
        if not self.tail: return None
        return {SIG_ACCEL: statistics.fmean(s[1] for s in self.tail), SIG_YAW: statistics.fmean(s[2] for s in self.tail)}


class MotionDetector:
    def __init__(self, means: dict, sigma: dict, noise_k: float, sustain_s: float, signal: str):
        keys = [SIG_ACCEL, SIG_YAW] if signal == SIG_BOTH else [signal]
        self.ex = {k: Excursion(means[k], noise_k * sigma[k], sustain_s) for k in keys}

    def feed(self, t: float, accel: float, yaw: float) -> bool:
        vals = {SIG_ACCEL: accel, SIG_YAW: yaw}
        return any([e.feed(t, vals[k]) for k, e in self.ex.items()])

    @property
    def first(self):
        return min((e.first for e in self.ex.values() if e.first is not None), default=None)

    @property
    def sustained(self):
        return min((e.sustained for e in self.ex.values() if e.sustained is not None), default=None)

    def peaks(self) -> dict:
        return {k: e.peak for k, e in self.ex.items()}


def imu_signals(ax, ay, az, wx, wy, wz, rotation) -> tuple:
    """(acceleration signal, yaw signal). rotation: base_link <- IMU 3x3 rows, or None when the TF is not known (the norms)."""
    if rotation is None:
        return math.sqrt(ax * ax + ay * ay + az * az), math.sqrt(wx * wx + wy * wy + wz * wz)
    r0, r2 = rotation[0], rotation[2]
    return r0[0] * ax + r0[1] * ay + r0[2] * az, r2[0] * wx + r2[1] * wy + r2[2] * wz


# ---- sequencing ----
class Sequencer:
    """Decides the stick command at time t. The node feeds it IMU signals and asks command(t) every period; a test in software does the same."""

    def __init__(self, trials: List[Trial], params: dict, on_event):
        self.trials, self.params, self.on_event = trials, params, on_event
        self.baseline_s = params['baseline_s']; self.baseline = Baseline(params['baseline_tail_s'])
        self.ti = -1; self.si = -1; self.t_seg = None; self.t0 = None; self.detector = None; self.done = False; self.forward = self.turn = 0.0
        self.collecting = True

    def feed_imu(self, t: float, accel: float, yaw: float):
        self.baseline.feed(t, accel, yaw, self.collecting)
        if self.detector is not None and t >= self.t_seg:   # a sample can arrive after the segment began although it was taken before it
            self.detector.feed(t, accel, yaw)

    def _next_trial(self, t: float):
        self.detector = None; self.forward = self.turn = 0.0
        if self.ti >= 0: self.on_event({'t': t, 'event': 'trial_end', 'trial': self.trials[self.ti].id})
        self.ti += 1; self.si = -1
        if self.ti >= len(self.trials):
            self.done = True; self.on_event({'t': t, 'event': 'finished'}); return
        tr = self.trials[self.ti]
        self.t_seg = t
        self.on_event({'t': t, 'event': 'trial_start', 'trial': tr.id})

    def _next_segment(self, t: float):
        self._close_segment(t)
        tr = self.trials[self.ti]
        self.si += 1
        if self.si >= len(tr.segments):
            self._next_trial(t); return
        s = tr.segments[self.si]
        self.forward, self.turn, self.t_seg = s.forward, s.turn, t
        self.detector = None
        if s.detect:
            means, sigma = self.baseline.means(), self.baseline.sigma
            if means is not None and sigma is not None:
                self.detector = MotionDetector(means, sigma, self.params['noise_k'], self.params['sustain_s'], signal_for(s.forward, s.turn))
        self.on_event({'t': t, 'event': 'segment_start', 'trial': tr.id, 'segment': self.si, 'label': s.label, 'forward': s.forward, 'turn': s.turn})

    def _close_segment(self, t: float):
        if self.detector is not None:
            d = self.detector
            self.on_event({'t': t, 'event': 'segment_end', 'trial': self.trials[self.ti].id, 'segment': self.si, 'first': d.first, 'sustained': d.sustained, 'peaks': d.peaks()})
            self.detector = None

    def command(self, t: float) -> tuple:
        if self.t0 is None:
            self.t0 = t
            if self.collecting: self.on_event({'t': t, 'event': 'baseline_start'})
        if self.collecting:
            if t - self.t0 < self.baseline_s: return 0.0, 0.0
            self.collecting = False
            self.on_event({'t': t, 'event': 'baseline_end', 'sigma': self.baseline.freeze()})
        if self.done: return 0.0, 0.0
        if self.ti < 0: self._next_trial(t)
        if self.done: return 0.0, 0.0
        tr = self.trials[self.ti]
        if self.si < 0:   # settling
            if t - self.t_seg >= tr.settle_s: self._next_segment(t)
            return self.forward, self.turn
        s = tr.segments[self.si]
        moved = self.detector is not None and self.detector.sustained is not None
        if moved and s.on_motion != CONTINUE:
            self._leave(t, s.on_motion)
        elif t - self.t_seg >= s.duration_s:
            self._leave(t, s.on_timeout if s.detect and not moved else END_NEXT)
        return self.forward, self.turn

    def _leave(self, t: float, how: str):
        if how == END_TRIAL:
            self._close_segment(t); self._next_trial(t)
        else:
            self._next_segment(t)

    def progress(self) -> tuple:
        cur = self.trials[self.ti].label if 0 <= self.ti < len(self.trials) else ('静止の記録' if self.collecting else '')
        return cur, (max(self.ti, 0) / len(self.trials) if self.trials else 1.0)

    def abort(self, t: float):
        if not self.done:
            if 0 <= self.ti < len(self.trials):
                self._close_segment(t); self.on_event({'t': t, 'event': 'trial_end', 'trial': self.trials[self.ti].id})
            self.done = True; self.forward = self.turn = 0.0


# ---- ESP32 clock ----
def fit_clock(uptime_ms: list, t_rx: list) -> Optional[dict]:
    """PC time of an ESP32 millis value. A STATUS is only ever late on the way to the PC, so the line is fitted by least squares for the
    slope and then lowered to the earliest arrivals. Returns t_pc = a + b * ms and how far the arrivals lie above the line."""
    n = len(uptime_ms)
    if n < 2 or n != len(t_rx): return None
    mx, my = statistics.fmean(uptime_ms), statistics.fmean(t_rx)
    sxx = sum((x - mx) ** 2 for x in uptime_ms)
    if sxx == 0: return None
    b = sum((x - mx) * (y - my) for x, y in zip(uptime_ms, t_rx)) / sxx
    res = [y - b * x for x, y in zip(uptime_ms, t_rx)]
    a = min(res)
    late = sorted(r - a for r in res)
    return {'a': a, 'b': b, 'samples': n, 'drift_ppm': (b * 1000 - 1) * 1e6, 'late_p50_s': late[n // 2], 'late_p95_s': late[int(n * 0.95)], 'late_max_s': late[-1]}


# ---- storage ----
RUN_ID = re.compile(r'^[A-Za-z0-9_-]+$')


class RunWriter:
    def __init__(self, root: Path, test_id: str, params: dict, meta: dict, stamp: Optional[str] = None):
        self.run_id = f"{test_id}_{stamp or time.strftime('%Y%m%d_%H%M%S')}"
        self.dir = Path(root) / self.run_id
        self.dir.mkdir(parents=True, exist_ok=False)
        (self.dir / 'meta.json').write_text(json.dumps(dict(meta, test_id=test_id, run_id=self.run_id, params=params), ensure_ascii=False, indent=1), encoding='utf-8')
        self._files = []
        self.imu = self._csv('imu.csv', IMU_COLUMNS); self.status = self._csv('status.csv', STATUS_COLUMNS); self.command = self._csv('command.csv', COMMAND_COLUMNS)
        self._events = open(self.dir / 'events.jsonl', 'w', encoding='utf-8'); self._files.append(self._events)

    def _csv(self, name, cols):
        f = open(self.dir / name, 'w', encoding='utf-8', newline=''); self._files.append(f)
        w = csv.writer(f); w.writerow(cols)
        return w

    def event(self, e: dict):
        self._events.write(json.dumps(e, ensure_ascii=False) + '\n')

    def close(self):
        for f in self._files: f.close()

    def write_result(self, result: dict):
        p = self.dir / 'result.json'
        p.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')


def read_csv(path: Path) -> dict:
    """Columns as lists; numbers become floats, the rest stays text."""
    with open(path, encoding='utf-8', newline='') as f:
        rows = list(csv.reader(f))
    if not rows: return {}
    out = {c: [] for c in rows[0]}
    for r in rows[1:]:
        for c, v in zip(rows[0], r):
            try: out[c].append(float(v))
            except ValueError: out[c].append(v)
    return out


def read_events(path: Path) -> list:
    return [json.loads(x) for x in Path(path).read_text(encoding='utf-8').splitlines() if x.strip()]


class RunStore:
    """What the /dev tab reads. It only reads files; the runner is the only writer."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def _dir(self, run_id: str) -> Path:
        if not RUN_ID.match(run_id or ''): raise ValueError(f'bad run id {run_id!r}')
        return self.root / run_id

    def list_runs(self) -> list:
        out = []
        if not self.root.is_dir(): return out
        for d in sorted(self.root.iterdir(), reverse=True):
            if not (d / 'meta.json').is_file(): continue
            res = None
            try: res = json.loads((d / 'result.json').read_text(encoding='utf-8'))
            except (OSError, ValueError): pass
            out.append({'run_id': d.name, 'end_reason': res.get('end_reason') if res else None})
        return out

    def result(self, run_id: str) -> dict:
        d = self._dir(run_id)
        return {'meta': json.loads((d / 'meta.json').read_text(encoding='utf-8')), 'result': json.loads((d / 'result.json').read_text(encoding='utf-8'))}

    def wave(self, run_id: str, trial_id: str, max_points: int) -> dict:
        """One trial's window, thinned by keeping each bucket's extreme so that a short shock stays visible."""
        d = self._dir(run_id)
        ev = [e for e in read_events(d / 'events.jsonl') if e.get('trial') == trial_id]
        if not ev: raise ValueError(f'no trial {trial_id!r} in {run_id}')
        t0, t1 = ev[0]['t'], ev[-1]['t']
        first_seg = next((e['t'] for e in ev if e['event'] == 'segment_start'), t0)
        out = {'t_ref': first_seg, 'events': ev}
        imu = read_csv(d / 'imu.csv'); st = read_csv(d / 'status.csv'); cmd = read_csv(d / 'command.csv')
        def window(tab, tkey, keys, thin):
            idx = [i for i, t in enumerate(tab.get(tkey, [])) if t0 <= t <= t1]
            if thin and max_points > 0 and len(idx) > max_points:
                n = max(1, len(idx) // max(1, max_points // 2)); kept = []
                for i in range(0, len(idx), n):
                    b = idx[i:i + n]; kept += sorted({max(b, key=lambda j: tab[keys[0]][j]), min(b, key=lambda j: tab[keys[0]][j])})
                idx = kept
            return {'t': [tab[tkey][i] - first_seg for i in idx], **{k: [tab[k][i] for i in idx] for k in keys}}
        out['imu_accel'] = window(imu, 't', ['signal_accel'], True); out['imu_yaw'] = window(imu, 't', ['signal_yaw'], True)
        out['status'] = window(st, 't_rx', ['dac_x', 'dac_y'], False); out['command'] = window(cmd, 't', ['forward', 'turn'], False)
        return out


def dac_change_time(status: dict, clock: Optional[dict], t_from: float, t_to: float) -> Optional[float]:
    """PC time of the first STATUS after t_from whose DAC code differs from the one before it (50 ms resolution of STATUS)."""
    prev = None
    for i, t in enumerate(status.get('t_rx', [])):
        if t > t_to: break
        cur = (status['dac_x'][i], status['dac_y'][i])
        if t >= t_from and prev is not None and cur != prev:
            return clock['a'] + clock['b'] * status['uptime_ms'][i] if clock else t
        prev = cur
    return None
