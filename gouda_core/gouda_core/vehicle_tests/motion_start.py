"""動き出しの試験 (DEC-409): the total delay from a stick command to the first motion, the threshold T and whether it is a circle, the time
t_lock to lock after dropping below T, and short pulses.

The lock itself cannot be seen directly, so it is probed: the delay of a following step is long from a lock and short from running. The
order keeps the distance small: turning in place first, opposite directions alternate, and a step ends as soon as motion is seen.
The delay section runs each direction twice, then the next direction of the pair twice (forward, forward, back, back: DEC-463, DEC-464), so the
vehicle comes back near where it started. The first of the two starts with the front casters left by the other direction, the second with the
casters already following this direction, and the table keeps the two apart.
"""
from __future__ import annotations

import bisect
import math
import statistics

from gouda_core.vehicle_test_core import CONTINUE, END_NEXT, END_TRIAL, Segment, Trial, dac_change_time, latest_attempt, stick


def _step(label, angle, amount, p, on_motion=END_TRIAL, on_timeout=END_TRIAL):
    f, t = stick(angle, amount)
    return Segment(label, f, t, p['max_wait_s'], True, on_motion, on_timeout, p['after_motion_s'])



def build_trials(p: dict) -> list:
    out, sec = [], p['sections']
    settle = p['settle_s']
    if 'threshold_up' in sec:
        for r in range(p['repeats']):
            for a in p['threshold_angles_deg']:
                segs = []
                levels = sorted(p['threshold_levels'])
                for lv in levels:
                    f, t = stick(a, lv)
                    hold = p['top_hold_s'] if lv == levels[-1] else p['stair_hold_s']   # the relay needs time after the largest input (DEC-414)
                    segs.append(Segment(f'{lv:g}', f, t, hold, True, END_TRIAL, END_NEXT, p['after_motion_s']))
                out.append(Trial(f'up_{a:g}_{r}', 'threshold_up', f'T 解除 {a:g}°', settle, segs, {'angle': a, 'levels': sorted(p['threshold_levels'])}))
    if 'delay' in sec:
        for amount in p['delay_amounts']:
            for r in range(p['repeats']):
                for a in p['delay_angles_deg']:
                    for same in (0, 1):
                        out.append(Trial(f'delay_{a:g}_{amount:g}_{2 * r + same}', 'delay', f'遅れ {a:g}° {amount:g}', settle, [_step('step', a, amount, p)], {'angle': a, 'amount': amount, 'same_direction': bool(same)}))
    a, amount = p['probe_angle_deg'], p['probe_amount']
    back = (a + 180) % 360
    if 'pulse' in sec:
        for i, w in enumerate(sorted(p['pulse_widths_s'])):
            for r in range(p['repeats']):
                f, t = stick(a if (i + r) % 2 == 0 else back, amount)
                segs = [Segment('pulse', f, t, w, True, CONTINUE, END_NEXT), Segment('observe', 0.0, 0.0, p['pulse_observe_s']),
                        _step('probe', a if (i + r) % 2 == 0 else back, amount, p)]
                out.append(Trial(f'pulse_{w:g}_{r}', 'pulse', f'パルス {w:g} s', settle, segs, {'width_s': w}))
    def run_then(label, value, section, tid, middle, i, r):
        f, t = stick(a if (i + r) % 2 == 0 else back, amount)
        segs = [Segment('drive', f, t, p['max_wait_s'], True, END_NEXT, END_TRIAL), Segment('hold', f, t, p['drive_hold_s']), middle(f, t),
                _step('probe', a if (i + r) % 2 == 0 else back, amount, p)]
        out.append(Trial(tid, section, f'{label} {value:g}', settle, segs, {'value': value}))
    if 't_lock' in sec:
        for i, g in enumerate(sorted(p['gaps_s'])):
            for r in range(p['repeats']):
                run_then('中立', g, 't_lock', f'gap_{g:g}_{r}', lambda f, t: Segment('gap', 0.0, 0.0, g), i, r)
    if 'threshold_down' in sec:
        for i, lv in enumerate(sorted(p['lock_levels'], reverse=True)):
            for r in range(p['repeats']):
                def middle(f, t, lv=lv):
                    s = lv / amount if amount else 0.0
                    return Segment('low', f * s, t * s, p['lock_hold_s'])
                run_then('下げ', lv, 'threshold_down', f'low_{lv:g}_{r}', middle, i, r)
    return out


def _segments(trial_events) -> dict:
    return {e['segment']: e for e in trial_events if e['event'] == 'segment_start'}, {e['segment']: e for e in trial_events if e['event'] == 'segment_end'}


def _before(run, p, t, forward, turn):
    """The vehicle in the window just before t, seen on the signals of a command (DEC-466). Turning shows in the mean yaw; driving straight has
    no mean acceleration, so it is read from the spread. None when the IMU record or the noise is missing."""
    imu, sigma = run.get('imu'), run.get('sigma')
    if not imu or not sigma: return None
    lo, hi = bisect.bisect_left(imu['t'], t - p['baseline_tail_s']), bisect.bisect_left(imu['t'], t)
    if hi - lo < 2: return None
    yaw = statistics.fmean(imu['signal_yaw'][lo:hi]); spread = statistics.pstdev(imu['signal_accel'][lo:hi])
    k = p['noise_k']
    return {'yaw': yaw, 'accel_spread': spread, 'moving': bool((turn and abs(yaw) > k * sigma['yaw']) or (forward and spread > k * sigma['accel']))}


def _rows(run, p) -> list:
    """One row per trial: what was commanded and when motion was seen, from the events of the run."""
    rows = []
    for tr in run['trials']:
        ev = latest_attempt([e for e in run['events'] if e.get('trial') == tr.id])
        starts, ends = _segments(ev)
        row = {'trial': tr.id, 'section': tr.section, 'label': tr.label, **tr.info, 'segments': []}
        for i, st in sorted(starts.items()):
            en = ends.get(i, {})
            seg = {'label': st['label'], 't': st['t'], 'forward': st.get('forward', 0.0), 'turn': st.get('turn', 0.0)}
            if st['label'] == 'probe': seg['before'] = _before(run, p, st['t'], seg['forward'], seg['turn'])
            if en.get('first') is not None: seg['first_s'] = en['first'] - st['t']
            if en.get('sustained') is not None: seg['motion_s'] = en['sustained'] - st['t']
            if en: seg['peaks'] = en.get('peaks')
            row['segments'].append(seg)
        if starts:
            row['ran'] = True
            t_to = max(e['t'] for e in ev)
            first = starts[min(starts)]
            dac = dac_change_time(run['status'], run['clock'], first['t'], t_to)
            if dac is not None: row['dac_s'] = dac - first['t']
        rows.append(row)
    return rows


def _seg(row, label):
    return next((s for s in row['segments'] if s['label'] == label), None)


def _stats(v):
    return {'n': len(v), 'mean_s': statistics.fmean(v), 'min_s': min(v), 'max_s': max(v)} if v else {'n': 0}


def _angle(seg) -> float:
    return round(math.degrees(math.atan2(seg['turn'], seg['forward']))) % 360


def _probes(rows, section) -> dict:
    """(value, direction) -> the probes that ran. A trial whose vehicle was still moving before the probe has no delay to read (DEC-466)."""
    by = {}
    for r in rows:
        s = _seg(r, 'probe') if r['section'] == section and r.get('ran') else None
        if s: by.setdefault((r['value'], _angle(s)), []).append(s)
    return by


def _still(probes) -> list:
    return [s for s in probes if s.get('before') and not s['before']['moving']]


def _delays(probes) -> dict:
    still = _still(probes); got = [s['motion_s'] for s in still if 'motion_s' in s]
    return {**_stats(got), 'no_motion': len(still) - len(got), 'moving': len(probes) - len(still)}


def _t_lock_table(rows, delay_rows, fraction) -> list:
    """Per direction. Long = fraction of the full delay: the delay table of that direction, else the longest gap of that direction with a stopped vehicle."""
    by, table = _probes(rows, 't_lock'), []
    for (gap, a), probes in sorted(by.items()):
        d = _delays(probes)
        near = [x['max_s'] for x in delay_rows if x.get('n') and x['angle'] == a]
        longest = [_delays(v) for (g, b), v in sorted(by.items(), reverse=True) if b == a and _delays(v).get('n')]
        full = statistics.fmean(near) if near else (longest[0]['mean_s'] if longest else None)
        table.append({'gap_s': gap, 'angle': a, **d, 'locked': d['mean_s'] >= fraction * full if d.get('n') and full else None})
    return table


def _t_down_table(rows) -> list:
    """Per direction. Locked = the vehicle has stopped at this level. Both results in one row leave it open."""
    table = []
    for (level, a), probes in sorted(_probes(rows, 'threshold_down').items()):
        seen = [s['before'] for s in probes if s.get('before')]
        table.append({'level': level, 'angle': a, **_delays(probes), 'yaw_before': statistics.fmean(abs(x['yaw']) for x in seen) if seen else None,
                      'locked': (not seen[0]['moving']) if seen and all(x['moving'] == seen[0]['moving'] for x in seen) else None})
    return table


def analyze(run: dict, p: dict) -> dict:
    rows = _rows(run, p)
    out = {'clock': run['clock'], 'sigma': run.get('sigma'), 'axes': run.get('axes'), 'rows': rows, 'tables': []}
    # T up: the level at which motion first appeared, per direction
    by = {}
    for r in rows:
        if r['section'] == 'threshold_up' and r.get('ran'):
            lv = next((float(s['label']) for s in r['segments'] if 'motion_s' in s), None)
            first = next((float(s['label']) for s in r['segments'] if 'first_s' in s), None)
            levels = r['levels']; below = max([x for x in levels if lv is not None and x < lv], default=0.0)
            by.setdefault(r['angle'], []).append({'below': below, 'level': lv, 'first_level': first})
    t_rows = [{'angle': a, 'level': [x['level'] for x in v], 'below': [x['below'] for x in v], 'first_level': [x['first_level'] for x in v]} for a, v in by.items()]
    if t_rows: out['tables'].append({'key': 'threshold_up', 'title': 'T 解除', 'columns': ['angle', 'below', 'level', 'first_level'], 'rows': t_rows})
    # delay
    by = {}
    for r in rows:
        if r['section'] == 'delay' and r.get('ran'):
            s = _seg(r, 'step')
            by.setdefault((r['angle'], r['amount']), []).append((s.get('motion_s'), s.get('first_s'), r.get('dac_s'), r['same_direction']))
    d_rows = []
    for (a, m), v in sorted(by.items(), key=lambda x: x[0]):
        moved = [x[0] for x in v if x[0] is not None]
        firsts = [x[1] for x in v if x[1] is not None]; dacs = [x[2] for x in v if x[2] is not None]
        changed = [x[0] for x in v if x[0] is not None and not x[3]]; same = [x[0] for x in v if x[0] is not None and x[3]]
        d_rows.append({'angle': a, 'amount': m, **_stats(moved), 'no_motion': len(v) - len(moved), 'first_mean_s': statistics.fmean(firsts) if firsts else None, 'dac_mean_s': statistics.fmean(dacs) if dacs else None,
                       'changed_mean_s': statistics.fmean(changed) if changed else None, 'same_mean_s': statistics.fmean(same) if same else None})
    if d_rows: out['tables'].append({'key': 'delay', 'title': '遅れ', 'columns': ['angle', 'amount', 'n', 'mean_s', 'min_s', 'max_s', 'changed_mean_s', 'same_mean_s', 'first_mean_s', 'dac_mean_s', 'no_motion'], 'rows': d_rows})
    # the full delay from a lock: this run's delay table for the probe direction, else the longest probe of the run
    near = [x['max_s'] for x in d_rows if x.get('n') and x['angle'] in (p['probe_angle_deg'], (p['probe_angle_deg'] + 180) % 360)]
    probes = [s['motion_s'] for r in rows if r['section'] in ('t_lock', 'threshold_down') for s in r['segments'] if s['label'] == 'probe' and 'motion_s' in s]
    full = statistics.fmean(near) if near else (max(probes) if probes else None)
    out['full_delay_s'] = full
    # pulse
    by = {}
    for r in rows:
        if r['section'] == 'pulse' and r.get('ran'):
            a, b, c = _seg(r, 'pulse'), _seg(r, 'probe'), r.get('dac_s')
            by.setdefault(r['width_s'], []).append((a and 'motion_s' in a, b.get('motion_s') if b else None))
    p_rows = []
    for w, v in sorted(by.items()):
        ds = [x[1] for x in v if x[1] is not None]
        p_rows.append({'width_s': w, 'moved_in_pulse': sum(1 for x in v if x[0]), **_stats(ds), 'locked': (statistics.fmean(ds) >= p['locked_fraction'] * full) if ds and full else None})
    if p_rows: out['tables'].append({'key': 'pulse', 'title': 'パルス', 'columns': ['width_s', 'moved_in_pulse', 'n', 'mean_s', 'min_s', 'max_s', 'locked'], 'rows': p_rows})
    # t_lock, T lock
    tbl = _t_lock_table(rows, d_rows, p['locked_fraction'])
    if tbl: out['tables'].append({'key': 't_lock', 'title': 't_lock', 'columns': ['gap_s', 'angle', 'n', 'mean_s', 'min_s', 'max_s', 'no_motion', 'moving', 'locked'], 'rows': tbl})
    tbl = _t_down_table(rows)
    if tbl: out['tables'].append({'key': 'threshold_down', 'title': 'T ロック', 'columns': ['level', 'angle', 'n', 'mean_s', 'min_s', 'max_s', 'no_motion', 'moving', 'yaw_before', 'locked'], 'rows': tbl})
    return out
