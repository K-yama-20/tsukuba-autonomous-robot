"""Reserve the next change-set id (REV-NNN), decision ids (DEC-NNN) and work-entry number (第N便) for one session.

Several Claude sessions write to the same working tree. Each one used to take "the latest number + 1" by itself, so two
sessions could pick the same REV file name (one overwriting the other) or the same 便 number in reports/status.md.
This tool takes the numbers with exclusive file creation (O_CREAT | O_EXCL), so only one session can get each number:
- REV: creates design/revisions/REV-NNN.yaml holding only a comment (the session then writes the change set into it).
  apply_revision.py refuses a file that is still only a reservation.
- DEC and 便: creates a marker file in design/reports/reservations/ (DEC-NNN.txt, bin-NNN.txt).
The next number is one more than the largest one in use: REV files, DEC ids in model.yaml and in every REV file, 便 numbers
in reports/status.md, and the markers. Usage:
  design/.venv/bin/python design/tools/reserve_ids.py --label <session name> [--decisions N] [--bin] [--no-revision]
"""
from __future__ import annotations

import argparse
import os
import re
import time
from pathlib import Path

DESIGN = Path(__file__).resolve().parents[1]
RESERVED_MARK = '# reserved by reserve_ids.py'


def _max_number(pattern: str, texts) -> int:
    rx = re.compile(pattern)
    return max([int(m) for t in texts for m in rx.findall(t)] + [0])


def _take(path_for, start: int, body: str) -> int:
    """Create path_for(n) exclusively from n = start upward; returns the number taken."""
    n = start
    while True:
        p = path_for(n)
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            n += 1
            continue
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(body)
        return n


def _texts(paths):
    return [p.read_text(encoding='utf-8') for p in paths if p.is_file()]


def reserve(label: str, decisions: int = 0, bin_number: bool = False, design: Path = DESIGN, revision: bool = True) -> dict:
    revisions = design / 'revisions'
    reservations = design / 'reports' / 'reservations'
    stamp = time.strftime('%Y-%m-%dT%H:%M:%S')
    body = f'{RESERVED_MARK}: {label} {stamp}\n'
    rev_files = sorted(revisions.glob('REV-*.yaml'))
    out = {'revision': None, 'decisions': [], 'bin': None}
    if revision:
        rev_next = _max_number(r'REV-(\d+)\.yaml', [p.name for p in rev_files]) + 1
        rev = _take(lambda n: revisions / f'REV-{n:03d}.yaml', rev_next, body)
        out['revision'] = f'REV-{rev:03d}'
    if decisions:
        dec_texts = _texts([design / 'model.yaml'] + rev_files) + [p.name for p in reservations.glob('DEC-*.txt')]
        n = _max_number(r'DEC-(\d+)', dec_texts) + 1
        for _ in range(decisions):
            n = _take(lambda k: reservations / f'DEC-{k:03d}.txt', n, body)
            out['decisions'].append(f'DEC-{n:03d}')
            n += 1
    if bin_number:
        in_status = _max_number(r'第(\d+)便', _texts([design / 'reports' / 'status.md']))
        in_markers = _max_number(r'bin-(\d+)\.txt', [p.name for p in reservations.glob('bin-*.txt')])
        n = max(in_status, in_markers) + 1
        n = _take(lambda k: reservations / f'bin-{k:03d}.txt', n, body)
        out['bin'] = f'第{n}便'
    return out


def is_reservation_only(text: str) -> bool:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return bool(lines) and all(ln.startswith('#') for ln in lines) and any(ln.startswith(RESERVED_MARK) for ln in lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Reserve REV / DEC / 便 numbers for one session (exclusive file creation)')
    ap.add_argument('--label', required=True, help='who reserves (e.g. the session name)')
    ap.add_argument('--decisions', type=int, default=0, help='how many DEC ids to reserve')
    ap.add_argument('--bin', action='store_true', help='also reserve the next 第N便 number for reports/status.md')
    ap.add_argument('--no-revision', action='store_true', help='do not reserve a REV (only DEC ids and/or 便)')
    a = ap.parse_args(argv)
    r = reserve(a.label, a.decisions, a.bin, revision=not a.no_revision)
    print(r['revision'] or '', ' '.join(r['decisions']), r['bin'] or '')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
