"""Reserve the next change-set id (REV-NNN), decision ids (DEC-NNN), work-entry number (第N便) and model ids
(PRM-NN, IFD-NN, ND-NN) for one session.

Several Claude sessions work in parallel, each in its own git worktree and branch. A number taken as "the latest
number + 1" inside one worktree is not visible to the others, so two sessions could pick the same REV / DEC / 便 /
PRM / IFD / ND number and the branches would collide at the merge.

This tool keeps one marker file per number in a place every worktree of this clone shares: the directory
`gouda-reservations/` inside the common git directory (`git rev-parse --git-common-dir`; never committed, never
checked out). A marker is created with exclusive file creation (O_CREAT | O_EXCL), so only one session gets each number.
- REV: marker REV-NNN.txt, plus design/revisions/REV-NNN.yaml in the caller's worktree holding only a comment (the
  session then writes the change set into it). apply_revision.py refuses a file that is still only a reservation.
- DEC, 便, PRM, IFD, ND: marker DEC-NNN.txt, bin-NNN.txt, PRM-NN.txt, IFD-NN.txt, ND-NN.txt.

The next number is one more than the largest one in use. "In use" is read from the shared markers and from the design
folder of every worktree of this clone (`git worktree list`): REV file names, ids in model.yaml and in every REV file,
便 numbers in reports/status.md, and the markers of the earlier scheme (design/reports/reservations/). Markers of the
earlier scheme are also copied into the shared place, so they can be removed from the working tree later.

Limits: the shared place belongs to one clone. Reserve only on the machine that holds the worktrees (not on the
vehicle PC or another clone). A number used only on a branch that is not checked out in any worktree and was never
reserved with this tool is not seen.

Outside a git repository (the unit tests) the markers go to design/reports/reservations/ of the given design folder.

Usage:
  design/.venv/bin/python design/tools/reserve_ids.py --label <session name> [--decisions N] [--bin] [--no-revision]
      [--prm N] [--ifd N] [--nd N] [--design <design folder of the caller's worktree>]
--design: for a worktree whose own copy of this tool is older (cut before the shared scheme): run the copy of an
up-to-date checkout and name the worktree's design folder; the REV file is created there.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import time
from pathlib import Path

DESIGN = Path(__file__).resolve().parents[1]
RESERVED_MARK = '# reserved by reserve_ids.py'
SHARED_NAME = 'gouda-reservations'
# model ids that can be reserved besides REV / DEC / 便: prefix -> digits of the marker name
MODEL_ID_WIDTH = {'PRM': 2, 'IFD': 2, 'ND': 2}


def _max_number(pattern: str, texts) -> int:
    rx = re.compile(pattern)
    return max([int(m) for t in texts for m in rx.findall(t)] + [0])


def _id_pattern(prefix: str) -> str:
    """PREFIX-<digits>, not preceded by a letter (so 'ND-12' does not match inside 'IND-12')."""
    return rf'(?<![A-Za-z]){prefix}-(\d+)'


def _create(path: Path, body: str) -> bool:
    """Create path exclusively; False when it already exists."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        return False
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(body)
    return True


def _take(path_for, start: int, body: str) -> int:
    """Create path_for(n) exclusively from n = start upward; returns the number taken."""
    n = start
    while not _create(path_for(n), body):
        n += 1
    return n


def _texts(paths):
    return [p.read_text(encoding='utf-8') for p in paths if p.is_file()]


def _git(design: Path, *args: str):
    try:
        r = subprocess.run(['git', '-C', str(design), *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def shared_dir(design: Path = DESIGN) -> Path:
    """The marker directory shared by every worktree of the clone that holds `design`."""
    out = _git(design, 'rev-parse', '--git-common-dir')
    if not out or not out.strip():
        return design / 'reports' / 'reservations'
    common = Path(out.strip())
    if not common.is_absolute():
        common = (design / common).resolve()
    return common / SHARED_NAME


def worktree_designs(design: Path = DESIGN) -> list:
    """The design folder of every worktree of the clone (the caller's first); only `design` outside git."""
    designs = [design]
    top = _git(design, 'rev-parse', '--show-toplevel')
    listing = _git(design, 'worktree', 'list', '--porcelain')
    if not top or not listing:
        return designs
    try:
        rel = design.resolve().relative_to(Path(top.strip()).resolve())
    except ValueError:
        return designs
    for line in listing.splitlines():
        if line.startswith('worktree '):
            d = Path(line[len('worktree '):]) / rel
            if d.is_dir() and d.resolve() != design.resolve():
                designs.append(d)
    return designs


def _import_legacy_markers(designs, shared: Path) -> None:
    """Copy the markers of the earlier scheme (design/reports/reservations/ of each worktree) into the shared place."""
    for d in designs:
        legacy = d / 'reports' / 'reservations'
        if not legacy.is_dir() or legacy.resolve() == shared.resolve():
            continue
        for p in legacy.glob('*.txt'):
            if not (shared / p.name).exists():
                _create(shared / p.name, p.read_text(encoding='utf-8'))


def reserve(label: str, decisions: int = 0, bin_number: bool = False, design: Path = DESIGN, revision: bool = True,
            model_ids: dict | None = None, shared: Path | None = None, designs: list | None = None) -> dict:
    """model_ids: {'PRM': n, 'IFD': n, 'ND': n} (how many of each). The result has a key per requested prefix.
    shared / designs: the marker directory and the design folders to read (default: from git, see the module text)."""
    model_ids = {k: v for k, v in (model_ids or {}).items() if v}
    unknown = sorted(set(model_ids) - set(MODEL_ID_WIDTH))
    if unknown:
        raise ValueError(f'cannot reserve {unknown}; known: {sorted(MODEL_ID_WIDTH)}')
    shared = Path(shared) if shared else shared_dir(design)
    designs = [Path(d) for d in designs] if designs else worktree_designs(design)
    shared.mkdir(parents=True, exist_ok=True)
    _import_legacy_markers(designs, shared)
    stamp = time.strftime('%Y-%m-%dT%H:%M:%S')
    body = f'{RESERVED_MARK}: {label} {stamp}\n'
    markers = [p.name for p in shared.glob('*.txt')]
    rev_files = [p for d in designs for p in sorted((d / 'revisions').glob('REV-*.yaml'))]
    out = {'revision': None, 'decisions': [], 'bin': None}
    if revision:
        rev_dir = design / 'revisions'
        n = max(_max_number(r'REV-(\d+)\.yaml', [p.name for p in rev_files]), _max_number(r'^REV-(\d+)\.txt$', markers)) + 1
        while True:
            n = _take(lambda k: shared / f'REV-{k:03d}.txt', n, body)
            if _create(rev_dir / f'REV-{n:03d}.yaml', body):
                break
            n += 1  # the file exists in this worktree without a marker (written before the shared scheme)
        out['revision'] = f'REV-{n:03d}'
    if decisions or model_ids:
        id_texts = _texts([d / 'model.yaml' for d in designs] + rev_files)
        wanted = ([('DEC', 3, decisions)] if decisions else []) + [(k, MODEL_ID_WIDTH[k], v) for k, v in model_ids.items()]
        for prefix, width, count in wanted:
            n = max(_max_number(_id_pattern(prefix), id_texts), _max_number(rf'^{prefix}-(\d+)\.txt$', markers)) + 1
            got = []
            for _ in range(count):
                n = _take(lambda k: shared / f'{prefix}-{k:0{width}d}.txt', n, body)
                got.append(f'{prefix}-{n:0{width}d}')
                n += 1
            out['decisions' if prefix == 'DEC' else prefix.lower()] = got
    if bin_number:
        in_status = _max_number(r'第(\d+)便', _texts([d / 'reports' / 'status.md' for d in designs]))
        n = max(in_status, _max_number(r'^bin-(\d+)\.txt$', markers)) + 1
        n = _take(lambda k: shared / f'bin-{k:03d}.txt', n, body)
        out['bin'] = f'第{n}便'
    return out


def is_reservation_only(text: str) -> bool:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return bool(lines) and all(ln.startswith('#') for ln in lines) and any(ln.startswith(RESERVED_MARK) for ln in lines)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='Reserve REV / DEC / 便 / PRM / IFD / ND numbers for one session (markers shared by all worktrees)')
    ap.add_argument('--label', required=True, help='who reserves (e.g. the session name)')
    ap.add_argument('--decisions', type=int, default=0, help='how many DEC ids to reserve')
    ap.add_argument('--bin', action='store_true', help='also reserve the next 第N便 number for reports/status.md')
    ap.add_argument('--no-revision', action='store_true', help='do not reserve a REV (only the other numbers)')
    ap.add_argument('--prm', type=int, default=0, help='how many PRM ids to reserve')
    ap.add_argument('--ifd', type=int, default=0, help='how many IFD ids to reserve')
    ap.add_argument('--nd', type=int, default=0, help='how many ND ids to reserve')
    ap.add_argument('--design', type=Path, default=DESIGN,
                    help="design folder of the caller's worktree (default: the one this script is in)")
    a = ap.parse_args(argv)
    design = a.design.resolve()
    if not (design / 'model.yaml').is_file() or not (design / 'revisions').is_dir():
        ap.error(f'{design} is not a design folder (model.yaml and revisions/ expected)')
    ids = {'PRM': a.prm, 'IFD': a.ifd, 'ND': a.nd}
    r = reserve(a.label, a.decisions, a.bin, design=design, revision=not a.no_revision, model_ids=ids)
    parts = [r['revision'] or '', ' '.join(r['decisions']), r['bin'] or '']
    parts += [' '.join(r[k.lower()]) for k in ids if r.get(k.lower())]
    print(*parts)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
