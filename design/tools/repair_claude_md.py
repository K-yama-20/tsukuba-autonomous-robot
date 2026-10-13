"""Propose a repair of the workspace CLAUDE.md whose body carries pasted line numbers.

Read-only on the original. Writes:
  design/proposals/CLAUDE.md.repaired   proposed body (line-number prefixes removed; nothing added)
  design/proposals/CLAUDE.md.diff        unified diff original -> proposal
  design/reports/claude_md_inspection.json  evidence (hashes, numbering analysis, unknowns)

Rule: a line is treated as "<pasted number><body>" only when the leading integer continues the
consecutive numbering observed across the file (18, 19, ... 202). The number is removed and the
body kept verbatim. Lines that do not fit the sequence are kept unchanged. No text is invented for
numbers that are absent (1-17); their absence is recorded as unconfirmed.
"""
import difflib, hashlib, json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'CLAUDE.md'
OUT = ROOT / 'design/proposals'


def main():
    text = SRC.read_text(encoding='utf-8')
    lines = text.split('\n')
    numbered = []
    for i, l in enumerate(lines, 1):
        m = re.match(r'^(\d+)(.*)$', l)
        numbered.append((i, int(m.group(1)) if m else None, m.group(2) if m else l))
    nums = [n for _, n, _ in numbered if n is not None]
    consecutive = all(b == a + 1 for a, b in zip(nums, nums[1:]))
    first, last = (nums[0], nums[-1]) if nums else (None, None)
    repaired = []; stripped = 0; kept = []
    expected = first
    for i, n, body in numbered:
        if n is not None and n == expected:
            repaired.append(body); stripped += 1; expected += 1
        else:
            repaired.append(lines[i - 1]); kept.append(i)
    proposal = '\n'.join(repaired)
    OUT.mkdir(exist_ok=True)
    (OUT / 'CLAUDE.md.repaired').write_text(proposal, encoding='utf-8')
    diff = '\n'.join(difflib.unified_diff(lines, repaired, fromfile='CLAUDE.md (current)', tofile='design/proposals/CLAUDE.md.repaired', lineterm='')) + '\n'
    (OUT / 'CLAUDE.md.diff').write_text(diff, encoding='utf-8')
    report = dict(source=str(SRC.relative_to(ROOT)), source_sha256=hashlib.sha256(text.encode()).hexdigest(), source_lines=len(lines), trailing_newline=text.endswith('\n'),
                  numbered_lines=len(nums), numbering_first=first, numbering_last=last, numbering_consecutive=consecutive, stripped_prefixes=stripped,
                  lines_kept_unchanged=kept, proposal_sha256=hashlib.sha256(proposal.encode()).hexdigest(), proposal_lines=len(repaired),
                  unconfirmed=[f'numbers 1..{first - 1} are absent: whether lines existed before the first heading is unknown; no text is proposed for them' if first else 'no numbering found'],
                  sources_checked=['tsukuba-autonomous-robot git history (no CLAUDE.md ever tracked)', 'workspace .bkp files (drawio only)', 'mi3 editor DocumentData (preferences only, no content)', '~/.claude/CLAUDE.md (different file: global instructions)', 'Spotlight copies in other projects (unrelated)'])
    (ROOT / 'design/reports/claude_md_inspection.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'sources_checked'}, ensure_ascii=False))


if __name__ == '__main__': main()
