"""動き出しの試験 (DEC-409): the total delay from a stick command to the first motion, the threshold T and whether it is a circle, the time
t_lock to lock after dropping below T, and short pulses.

The lock itself cannot be seen directly, so it is probed: the delay of a following step is long from a lock and short from running. The
order keeps the distance small: turning in place first, opposite directions alternate, and a step ends as soon as motion is seen.
"""
from __future__ import annotations

import statistics

from gouda_core.vehicle_test_core import CONTINUE, END_NEXT, END_TRIAL, Segment, Trial, dac_change_time, stick


def _step(label, angle, amount, p, on_motion=END_TRIAL, on_timeout=END_TRIAL):
    f, t = stick(angle, amount)
    return Segment(label, f, t, p['max_wait_s'], True, on_motion, on_timeout)



def build_trials(p: dict) -> list:
    out, sec = [], p['sections']
    settle = p['settle_s']
    if 'threshold_up' in sec:
        for r in range(p['repeats']):
            for a in p['threshold_angles_deg']:
                segs = []
                for lv in sorted(p['threshold_levels']):
                    f, t = stick(a, lv)
                    segs.append(Segment(f'{lv:g}', f, t, p['stair_hold_s'], True, END_TRIAL, END_NEXT))
                out.append(Trial(f'up_{a:g}_{r}', 'threshold_up', f'T 解除 {a:g}°', settle, segs, {'angle': a, 'levels': sorted(p['threshold_levels'])}))
    if 'delay' in sec:
        for amount in p['delay_amounts']:
            for r in range(p['repeats']):
                for a in p['delay_angles_deg']:
                    out.append(Trial(f'delay_{a:g}_{amount:g}_{r}', 'delay', f'遅れ {a:g}° {amount:g}', settle, [_step('step', a, amount, p)], {'angle': a, 'amount': amount}))
    a, amount = p['probe_angle_deg'], p['probe_amount']
    back = (a + 180) % 360
    if 'pulse' in sec:
        for i, w in enumerate(sorted(p['pulse_widths_s'])):
            for r in range(p['repeats']):
                f, t = stick(a if (i + r) % 2 == 0 else back, amount)
                segs = [Segment('pulse', f, t, w, True, CONTINUE, END_NEXT), Segment('observe', 0.0, 0.0, p['pulse_observe_s']),
                        Segment('probe', f, t, p['max_wait_s'], True, END_TRIAL, END_TRIAL)]
                out.append(Trial(f'pulse_{w:g}_{r}', 'pulse', f'パルス {w:g} s', settle, segs, {'width_s': w}))
    def run_then(label, value, section, tid, middle, i, r):
        f, t = stick(a if (i + r) % 2 == 0 else back, amount)
        segs = [Segment('drive', f, t, p['max_wait_s'], True, END_NEXT, END_TRIAL), Segment('hold', f, t, p['drive_hold_s']), middle(f, t),
                Segment('probe', f, t, p['max_wait_s'], True, END_TRIAL, END_TRIAL)]
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


def _rows(run) -> list:
    """One row per trial: what was commanded and when motion was seen, from the events of the run."""
    rows = []
    for tr in run['trials']:
        ev = [e for e in run['events'] if e.get('trial') == tr.id]
        starts, ends = _segments(ev)
        row = {'trial': tr.id, 'section': tr.section, 'label': tr.label, **tr.info, 'segments': []}
        for i, st in sorted(starts.items()):
            en = ends.get(i, {})
            seg = {'label': st['label'], 't': st['t']}
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


def _probe_summary(rows, section, full, fraction, key_name):
    """value -> probe delays, and the two values between which the probe's delay turns long (locked). Long = fraction of the full delay."""
    by, table = {}, []
    for r in rows:
        if r['section'] == section and r.get('ran'):
            s = _seg(r, 'probe')
            by.setdefault(r['value'], []).append(s['motion_s'] if s and 'motion_s' in s else None)
    for v in sorted(by):
        got = [x for x in by[v] if x is not None]
        table.append({key_name: v, **_stats(got), 'no_motion': len(by[v]) - len(got), 'locked': (statistics.fmean(got) >= fraction * full) if got and full else None})
    return table


def analyze(run: dict, p: dict) -> dict:
    rows = _rows(run)
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
            by.setdefault((r['angle'], r['amount']), []).append((s.get('motion_s'), s.get('first_s'), r.get('dac_s')))
    d_rows = []
    for (a, m), v in sorted(by.items(), key=lambda x: x[0]):
        moved = [x[0] for x in v if x[0] is not None]
        firsts = [x[1] for x in v if x[1] is not None]; dacs = [x[2] for x in v if x[2] is not None]
        d_rows.append({'angle': a, 'amount': m, **_stats(moved), 'no_motion': len(v) - len(moved), 'first_mean_s': statistics.fmean(firsts) if firsts else None, 'dac_mean_s': statistics.fmean(dacs) if dacs else None})
    if d_rows: out['tables'].append({'key': 'delay', 'title': '遅れ', 'columns': ['angle', 'amount', 'n', 'mean_s', 'min_s', 'max_s', 'first_mean_s', 'dac_mean_s', 'no_motion'], 'rows': d_rows})
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
    tbl = _probe_summary(rows, 't_lock', full, p['locked_fraction'], 'gap_s')
    if tbl: out['tables'].append({'key': 't_lock', 'title': 't_lock', 'columns': ['gap_s', 'n', 'mean_s', 'min_s', 'max_s', 'no_motion', 'locked'], 'rows': tbl})
    tbl = _probe_summary(rows, 'threshold_down', full, p['locked_fraction'], 'level')
    if tbl: out['tables'].append({'key': 'threshold_down', 'title': 'T ロック', 'columns': ['level', 'n', 'mean_s', 'min_s', 'max_s', 'no_motion', 'locked'], 'rows': tbl})
    return out
