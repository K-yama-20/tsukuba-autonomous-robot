"""DR-15 hardcode scan (DEC-175): numbers written in the product code of the new implementation.

Two kinds of finding, both reported as 未判定 (a human decides; nothing here is a violation by itself):
- approved value: a numeric literal equal to an approved parameter value (RQ-I076: a setting is declared once, in the model)
- timing value: a numeric literal on a line that waits, times out, sleeps or sets a period (sleep / timeout / wait / join /
  delay / period / interval / create_timer / setTimeout / setInterval / deadline / retry, and `seq A B` loops in shell),
  whether or not it equals a parameter: an undeclared time value can stop or slow Gouda without any setting showing it.
Only code is scanned: comments, docstrings and string literals are removed first, so section numbers, version strings
and prose are not reported. Languages: Python (tokenize), C/C++ and JavaScript (comments and strings removed by a small
lexer), shell (comments and quoted strings removed). Files and languages come from tools/hardcode_scan_roots.json.
A finding is accepted only through tools/hardcode_allowlist.json (file, the code text the line contains, the literal,
the reason and the decision that accepted it); an allowlist entry that no longer matches anything is itself reported,
so the list cannot silently go stale.
"""
from __future__ import annotations

import io
import json
import re
import tokenize
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
# case-sensitive on purpose: enum names such as R_WAITING_CENTER are not waits; camelCase and kConstants are covered
TIMING = re.compile(r'(sleep|[Tt]imeout|wait|join\(timeout|[Dd]elay|[Pp]eriod|[Ii]nterval|create_timer|deadline|retr(y|ies))')
NUMBER = re.compile(r'(?<![\w.\[])(\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?(?![\w.\]])')   # not an index such as it[5]
# integer approved values are looked for only in the language of their declaration (a QoS depth 50 or HTTP 200 in Python
# is not the firmware's STATUS period 50 ms or release time 200 ms)
INT_LANG = {'firmware_config': {'cpp'}, 'ros_parameter': {'python', 'shell'}, 'bt_xml': {'python'}}
TRIVIAL = {'0', '0.0', '0.'}   # zero is "no wait"; every other number on a timing line is reported


def _python_code_lines(text: str) -> dict:
    """line number -> code text with strings and comments removed (tokenize keeps NUMBER tokens exactly)."""
    out: dict = {}
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING) or tok.type == getattr(tokenize, 'FSTRING_MIDDLE', -1):
                continue
            if tok.type in (tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER):
                continue
            out.setdefault(tok.start[0], []).append(tok.string)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return {i + 1: l for i, l in enumerate(text.splitlines())}   # unparsable: scan the raw text (over-reports, never hides)
    def join(toks):   # spaces only between two word-like tokens, so that `time.sleep(0.2)` reads as written
        r = ''
        for t in toks:
            r += (' ' if r and (r[-1].isalnum() or r[-1] == '_') and (t[0].isalnum() or t[0] == '_') else '') + t
        return r
    return {k: join(v) for k, v in out.items()}


def _c_like_code_lines(text: str, template_strings: bool) -> dict:
    """C/C++/JavaScript: remove // and /* */ comments and "..." '...' (and `...` in JS) strings, keep line numbers."""
    res = []; i = 0; n = len(text); quotes = '"\'`' if template_strings else '"\''
    while i < n:
        c = text[i]
        if text.startswith('//', i):
            j = text.find('\n', i); i = n if j < 0 else j; continue
        if text.startswith('/*', i):
            j = text.find('*/', i + 2); j = n if j < 0 else j + 2
            res.append('\n' * text.count('\n', i, j)); i = j; continue
        if c in quotes:
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == '\\' else 1
            res.append('\n' * text.count('\n', i, j)); i = j + 1; continue
        res.append(c); i += 1
    return {k + 1: l for k, l in enumerate(''.join(res).split('\n'))}


def _shell_code_lines(text: str) -> dict:
    out = {}
    for k, line in enumerate(text.splitlines(), 1):
        line = re.sub(r'"(?:[^"\\]|\\.)*"|\'[^\']*\'', '""', line)
        line = re.sub(r'(^|\s)#.*$', '', line)
        out[k] = line
    return out


def code_lines(path: Path, lang: str) -> dict:
    text = path.read_text(encoding='utf-8', errors='replace')
    if lang == 'python': return _python_code_lines(text)
    if lang == 'cpp': return _c_like_code_lines(text, template_strings=False)
    if lang == 'js':
        if path.suffix in ('.html', '.htm'):   # only the code in <script> blocks; page text and attributes are not code
            text = re.sub(r'(?is)<script[^>]*>(.*?)</script>|[^\n]', lambda m: m.group(1) if m.group(1) is not None else '', text)
        return _c_like_code_lines(text, template_strings=True)
    if lang == 'shell': return _shell_code_lines(text)
    raise ValueError(f'unknown language {lang}')


def _approved_forms(val) -> set:
    """Literal spellings of an approved value. Floats: repr and %g (0.7), and N. for integral floats (1.0 -> '1.0', '1.').
    Integers: only values with two or more digits, so that indexes and enum codes (0, 1, 4) are not reported."""
    if isinstance(val, bool): return set()
    if isinstance(val, float):
        return {repr(val), '%g' % val} if not val.is_integer() else {repr(val), f'{int(val)}.', f'{int(val)}.0'}
    if isinstance(val, int) and abs(val) >= 10: return {('int', str(val))}
    return set()


def load_config():
    cfg = json.loads((TOOLS / 'hardcode_scan_roots.json').read_text())
    allow = json.loads((TOOLS / 'hardcode_allowlist.json').read_text()) if (TOOLS / 'hardcode_allowlist.json').exists() else {'entries': []}
    return cfg, allow['entries']


def targets(cfg) -> list:
    """(path, lang) of every scanned file. 'roots' are Python package directories (also used by DR-17); 'scan' adds others."""
    out = []
    for r in cfg.get('roots', []):
        root = REPO / r
        if root.exists(): out += [(p, 'python') for p in sorted(root.rglob('*.py'))]
    excl = {str(REPO / e) for e in cfg.get('exclude', [])}
    for s in cfg.get('scan', []):
        base = REPO / s['path']; pats = s.get('glob', ['*'])
        files = [base] if base.is_file() else [p for g in pats for p in sorted(base.rglob(g))]
        out += [(p, s['lang']) for p in files if p.is_file()]
    return [(p, l) for p, l in out if str(p) not in excl and '__pycache__' not in p.parts]


def scan(model, cfg=None, allow=None) -> tuple:
    """Returns (undetermined messages, used allowlist indexes)."""
    if cfg is None: cfg, allow = load_config()
    approved = []   # (PRM id, literal, languages or None for every language)
    for e in model['entities']:
        if e['kind'] != 'parameter' or e['parameter']['value_state'] != 'approved': continue
        for f in _approved_forms(e['parameter']['value']):
            if isinstance(f, tuple): approved.append((e['id'], f[1], INT_LANG.get(e['parameter'].get('declaration'), set())))
            else: approved.append((e['id'], f, None))
    findings = []
    for path, lang in targets(cfg):
        try: lines = code_lines(path, lang)
        except Exception as ex:
            findings.append((path, 0, '', '', f'読めない（{ex}）')); continue
        for ln, code in lines.items():
            nums = [m.group(0) for m in NUMBER.finditer(code)]
            if not nums: continue
            timing = bool(TIMING.search(code)) or (lang == 'shell' and re.search(r'\bseq\s+\d', code))
            for lit in nums:
                hits = [pid for pid, f, langs in approved if f == lit and (langs is None or lang in langs)]
                if hits: findings.append((path, ln, code.strip(), lit, f'承認値と同じ数（{"・".join(sorted(set(hits)))}）'))
                elif timing and lit not in TRIVIAL: findings.append((path, ln, code.strip(), lit, '時間の値（待ち・期限・周期）'))
    used = set(); out = []; seen = set()
    for path, ln, code, lit, why in findings:
        if (path, ln, lit) in seen: continue   # the same number twice on one line is one finding
        seen.add((path, ln, lit))
        rel = str(path.relative_to(REPO))
        idx = next((i for i, a in enumerate(allow or []) if a['file'] == rel and a['literal'] == lit and a['line_contains'] in code), None)
        if idx is not None: used.add(idx); continue
        out.append(f'{rel}:{ln}: {lit} — {why}。`{code[:120]}`')
    for i, a in enumerate(allow or []):
        if i not in used: out.append(f'許容の一覧の項目が一致しない（古い可能性）：{a["file"]} の {a["literal"]}（{a["line_contains"]}）')
    return out, used
