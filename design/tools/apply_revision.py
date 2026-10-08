"""Apply one change set (design/revisions/<REV>.yaml) to the canonical model.

Deterministic: the same change set on the same model gives the same model.
Refuses to apply a revision twice, never deletes entities, never edits inputs
(intent.md, Excel, drawio, extraction) and never rewrites the frozen baseline.

The intent.md revision is verified mechanically: the archived previous copy plus
the recorded added lines must reproduce the current file exactly. Any removed or
changed line stops the run; such a change must first be registered as a decision.
"""
import argparse, copy, datetime, difflib, hashlib, json, sys
from pathlib import Path
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / 'design'
sys.path.insert(0, str(DESIGN / 'tools'))
import model_schema  # noqa: E402
from validate_model import current_line_map, is_requirement_line  # noqa: E402

ENTITY_KEYS = ['id', 'kind', 'name', 'source_refs', 'design_status', 'adoption', 'field_bindings', 'related_refs', 'issue_refs', 'interpretation', 'sensitivity', 'requirement_refs', 'revision_ref']
PAYLOADS = ['module', 'interface', 'diagram', 'issue', 'reconciliation', 'mode', 'state_owner', 'execution', 'parameter', 'failure_mode', 'test', 'ros_node', 'designed_interface', 'transition', 'boundary', 'approval_source_ref', 'approval_decision_ref']


def sha(p: Path):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def yaml_rt():
    y = YAML(typ='rt'); y.allow_unicode = True; y.width = 110; y.indent(mapping=2, sequence=4, offset=2)
    return y


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)


def to_plain(obj):
    return json.loads(json.dumps(obj, ensure_ascii=False, default=str))


def resolve_tokens(obj, dg_by_orig):
    """Replace 'DG@<drawio element id>' tokens by the stable model IDs."""
    if isinstance(obj, str):
        if obj.startswith('DG@'):
            key = obj[3:]
            if key not in dg_by_orig:
                raise SystemExit(f'unknown drawio element in change set: {key}')
            return dg_by_orig[key]
        return obj
    if isinstance(obj, list):
        return [resolve_tokens(x, dg_by_orig) for x in obj]
    if isinstance(obj, dict):
        return {k: resolve_tokens(v, dg_by_orig) for k, v in obj.items()}
    return obj


def ordered_entity(spec):
    e = CommentedMap()
    for k in ENTITY_KEYS:
        if k in spec:
            e[k] = spec[k]
    for k in PAYLOADS:
        if k in spec:
            e[k] = spec[k]
    extra = set(spec) - set(ENTITY_KEYS) - set(PAYLOADS)
    if extra:
        raise SystemExit(f'unexpected keys in entity {spec.get("id")}: {sorted(extra)}')
    return e


def intent_diff(prev_lines, cur_lines):
    added, removed, changed = [], [], []
    sm = difflib.SequenceMatcher(a=prev_lines, b=cur_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        if tag == 'insert':
            added += [{'line': j + 1, 'text': cur_lines[j]} for j in range(j1, j2)]
        elif tag == 'delete':
            removed += [{'line': i + 1, 'text': prev_lines[i]} for i in range(i1, i2)]
        else:  # replace: a trailing-newline-only difference on the last line is an append, not a change
            if i2 - i1 == 1 and j2 - j1 >= 1 and prev_lines[i1] == cur_lines[j1]:
                added += [{'line': j + 1, 'text': cur_lines[j]} for j in range(j1 + 1, j2)]
            else:  # replaced lines: recorded as removed (old numbering) plus added (new numbering)
                removed += [{'line': i + 1, 'text': prev_lines[i]} for i in range(i1, i2)]
                added += [{'line': j + 1, 'text': cur_lines[j]} for j in range(j1, j2)]
    return added, removed, changed


def apply(rev_id, model_path=DESIGN / 'model.yaml', manifest_path=DESIGN / 'migration_manifest.json', dry_run=False):
    cs = YAML(typ='safe').load((DESIGN / 'revisions' / f'{rev_id}.yaml').read_text())
    if cs['id'] != rev_id:
        raise SystemExit('change set id mismatch')
    y = yaml_rt()
    model = y.load(model_path.read_text())
    if any(r['id'] == rev_id for r in model.get('revisions', [])):
        raise SystemExit(f'{rev_id} already applied; refusing to apply twice')
    manifest = json.loads(manifest_path.read_text())
    byid = {e['id']: e for e in model['entities']}
    sources = {s['id']: s for s in model['sources']}
    files = {f['id']: f for f in model['files']}
    before = {e['id']: canonical(to_plain(e)) for e in model['entities']}
    before_sources = set(sources); before_files = set(files)
    dg_by_orig = {sources[e['source_refs'][0]]['locator']['element_id']: e['id'] for e in model['entities'] if e['kind'] in ('diagram_element', 'diagram_connection')}
    cs = resolve_tokens(cs, dg_by_orig)
    linemap = {int(k): v for k, v in manifest['intent_requirement_lines'].items()}
    for e in model['entities']:  # requirement lines added by earlier authority revisions
        if e['kind'] == 'requirement' and sources[e['source_refs'][0]]['kind'] == 'intent_lines': linemap[sources[e['source_refs'][0]]['locator']['line_start']] = e['id']

    # ---- authority revision (intent.md) ----
    ar = cs.get('authority_revision')
    rqs = []; added = []; new_entity_ids = []; current_file = DESIGN / 'intent.md'
    if ar:
      prev_file = files[ar['previous_file_id']]
      archived = ROOT / ar['archived_previous_copy']
      current_file = ROOT / ar['current_copy'] if ar.get('current_copy') else DESIGN / 'intent.md'  # pinned copy of the version this revision recorded
      prev_sha = sha(archived); cur_sha = sha(current_file)
      if prev_sha != prev_file['sha256']:
          raise SystemExit(f'archived previous intent copy hash {prev_sha} does not match recorded {prev_file["sha256"]}')
      prev_lines = archived.read_text().splitlines(); cur_lines = current_file.read_text().splitlines()
      added, removed, changed = intent_diff(prev_lines, cur_lines)
      if (removed or changed) and not (ar.get('allow_non_append') and ar.get('decision_ref')):
          raise SystemExit(f'intent.md has removed/changed lines; register them as a decision first: removed={removed} changed={changed}')
      expected_lines = sorted(int(k) for k in ar['new_requirement_lines'])
      if sorted(a['line'] for a in added) != expected_lines:
          raise SystemExit(f'added intent lines {[a["line"] for a in added]} differ from change set {expected_lines}')
      if ar['file_id'] not in files:
          model['files'].append(CommentedMap([('id', ar['file_id']), ('path', 'design/intent.md'), ('sha256', cur_sha), ('role', 'authority')]))
          files[ar['file_id']] = model['files'][-1]
      prev_file['role'] = 'authority_superseded'
      prev_file['superseded_by'] = ar['file_id']
      prev_file['archived_copy'] = ar['archived_previous_copy']
      if prev_file['id'] != 'FILE-INTENT' and 'FILE-INTENT' in files: files['FILE-INTENT'].setdefault('archived_copy', 'design/baselines/migration_v1/intent.md')
      model['metadata']['authority_ref'] = ar['file_id']
      model['metadata']['model_revision'] = rev_id
      model['schema_version'] = '1.1'
      rqs = [ar['new_requirement_lines'][k] for k in sorted(ar['new_requirement_lines'])]
      model.setdefault('authority_revisions', CommentedSeq()).append(CommentedMap([
          ('id', ar['id']), ('file_ref', ar['file_id']), ('previous_file_ref', ar['previous_file_id']), ('sha256', cur_sha), ('previous_sha256', prev_sha),
          ('archived_previous_copy', ar['archived_previous_copy']), ('added_lines', added), ('removed_lines', removed), ('changed_lines', changed),
          ('instruction_expected_added_lines', ar.get('instruction_expected_added_lines', 0)), ('observed_added_lines', len(added)),
          ('decision_ref', ar.get('decision_ref')), ('requirement_refs', rqs), ('note', ar.get('note', ''))]))
      for line_s, rq in ([] if not ar else sorted(ar['new_requirement_lines'].items(), key=lambda kv: int(kv[0]))):
          line = int(line_s); suffix = '' if ar['file_id'] == 'FILE-INTENT-V2' else '-' + ar['file_id'].split('-')[-1]; sid = f'SRC-I{line:03}{suffix}'
          if sid in sources or rq in byid:
              raise SystemExit(f'{sid}/{rq} already exist')
          model['sources'].append(CommentedMap([('id', sid), ('file_ref', ar['file_id']), ('kind', 'intent_lines'), ('locator', {'line_start': line, 'line_end': line}),
                                                ('raw_fields', {'text': cur_lines[line - 1]}),
                                                ('original_status', {'classification': '上位要求', 'raw': '', 'basis': f'intent.md 新版 {ar["id"]}（{ar.get("decision_ref")} の回答）を上位要求とする', 'locations': [f'intent.md:{line}']})]))
          sources[sid] = model['sources'][-1]
          e = ordered_entity({'id': rq, 'kind': 'requirement', 'name': f'intent.md:{line}（{ar["file_id"]}）', 'source_refs': [sid], 'design_status': '未設計', 'adoption': 'upper_requirement',
                              'field_bindings': {'statement': {'source_ref': sid, 'field': 'text'}}, 'related_refs': [], 'issue_refs': [], 'interpretation': '', 'sensitivity': ['intent'], 'revision_ref': rev_id})
          model['entities'].append(e); byid[rq] = e; new_entity_ids.append(rq); linemap[line] = rq

    # Current-file line numbers → requirement IDs (text match across versions), after any new requirement lines were added.
    intent_version = ROOT / cs['intent_version_copy'] if cs.get('intent_version_copy') else (current_file if ar else DESIGN / 'intent.md')
    linemap = current_line_map(model, intent_path=intent_version)
    # ---- evidence files ----
    for fs in cs.get('files', []):
        if fs['id'] in files: raise SystemExit(f'file {fs["id"]} already exists')
        model['files'].append(CommentedMap([('id', fs['id']), ('path', fs['path']), ('sha256', sha(ROOT / fs['path'])), ('role', fs['role'])])); files[fs['id']] = model['files'][-1]
    # ---- decisions ----
    decisions = model.setdefault('decisions', CommentedSeq())
    known = {d['id'] for d in decisions}
    for du in cs.get('decision_updates', []):
        d = next((x for x in decisions if x['id'] == du['id']), None)
        if d is None: raise SystemExit(f'decision {du["id"]} missing')
        for k, v in du['set'].items(): d[k] = v
    for d in cs.get('decisions', []):
        if d['id'] in known:
            raise SystemExit(f'decision {d["id"]} already exists')
        decisions.append(CommentedMap([(k, d[k]) for k in ['id', 'kind', 'status', 'asked_on', 'answered_on', 'channel', 'question', 'answer_verbatim', 'affected_refs', 'resulting_refs', 'note', 'disposition'] if k in d]))

    # ---- new entities ----
    pending_source_from_affected = []
    for spec in cs.get('entities', []):
        spec = dict(spec)
        if spec['id'] in byid:
            raise SystemExit(f'entity {spec["id"]} already exists')
        lines = spec.pop('intent_lines', [])
        for ln in lines:
            if ln not in linemap:
                raise SystemExit(f'intent line {ln} is not a requirement line')
        req = [linemap[ln] for ln in lines]
        src = [byid[r]['source_refs'][0] for r in req]
        sfa = spec.pop('source_from_affected', False)
        spec.setdefault('source_refs', [])
        spec['source_refs'] = list(dict.fromkeys(spec['source_refs'] + src))
        spec.setdefault('design_status', '案'); spec.setdefault('adoption', 'designed_proposal'); spec.setdefault('field_bindings', {})
        spec.setdefault('related_refs', []); spec.setdefault('issue_refs', []); spec.setdefault('interpretation', ''); spec.setdefault('sensitivity', [])
        spec['requirement_refs'] = list(dict.fromkeys(spec.get('requirement_refs', []) + req)); spec['revision_ref'] = rev_id
        e = ordered_entity(spec); model['entities'].append(e); byid[e['id']] = e; new_entity_ids.append(e['id'])
        if sfa:
            pending_source_from_affected.append(e)
    for e in pending_source_from_affected:
        affected = (e.get('reconciliation') or e.get('issue'))['affected_refs']
        for a in affected:
            if a not in byid:
                raise SystemExit(f'{e["id"]} affects unknown {a}')
            for s in byid[a]['source_refs']:
                if s not in e['source_refs']:
                    e['source_refs'].append(s)
    # back links, as the initial builder did: issues -> issue_refs, reconciliations -> related_refs
    for e in list(byid.values()):
        if e.get('revision_ref') != rev_id or e['id'] not in new_entity_ids:
            continue
        if e['kind'] == 'issue':
            for a in e['issue']['affected_refs']:
                t = byid[a]
                if e['id'] not in t['issue_refs']:
                    t['issue_refs'].append(e['id'])
        if e['kind'] == 'reconciliation':
            for a in e['reconciliation']['affected_refs']:
                t = byid[a]
                if e['id'] not in t['related_refs']:
                    t['related_refs'].append(e['id'])

    # ---- modifications of existing entities ----
    for mod in cs.get('modifications', []):
        e = byid.get(mod['id'])
        if e is None:
            raise SystemExit(f'modification target {mod["id"]} missing')
        if mod['id'] in new_entity_ids:
            raise SystemExit(f'{mod["id"]} is new in this revision; edit its spec instead')
        for k, v in (mod.get('set') or {}).items():
            e[k] = v
        for k, vals in (mod.get('append') or {}).items():
            e.setdefault(k, CommentedSeq())
            for v in vals:
                if v not in e[k]:
                    e[k].append(v)
        for path, v in (mod.get('set_nested') or {}).items():
            cur = e; parts = path.split('.')
            for p in parts[:-1]:
                cur = cur[p]
            cur[parts[-1]] = v
        if 'interpretation_append' in mod:
            e['interpretation'] = (e['interpretation'] + ' ' if e['interpretation'] else '') + mod['interpretation_append']
        if 'boundary' in mod:
            e['boundary'] = CommentedMap([(k, mod['boundary'][k]) for k in ['status', 'decision_ref', 'note']])
        for k in mod.get('delete_fields', []):
            e.pop(k, None)
        for ln in mod.get('append_intent_lines', []):
            rq = linemap[ln]; sid = byid[rq]['source_refs'][0]
            if sid not in e['source_refs']: e['source_refs'].append(sid)
            e.setdefault('requirement_refs', CommentedSeq())
            if rq not in e['requirement_refs']: e['requirement_refs'].append(rq)

    # Derived views (state/parameter/failure/execution) inherit the owner's reconciliation
    # links, exactly as the initial builder did, so no replacement scope is lost.
    for e in model['entities']:
        if e['kind'] in ('state_owner', 'parameter', 'failure_mode', 'execution'):
            owner_id = e[e['kind']].get('owner_ref', e[e['kind']].get('module_ref'))
            owner = byid.get(owner_id, {})
            for ref in owner.get('related_refs', []):
                if byid.get(ref, {}).get('kind') == 'reconciliation' and ref not in e['related_refs']:
                    e['related_refs'].append(ref)

    # ---- global requirement reference replacement (superseded requirement -> successor) ----
    for old_rq, new_rq in (cs.get('requirement_ref_replacements') or {}).items():
        for e in model['entities']:
            if old_rq in e.get('requirement_refs', []):
                e['requirement_refs'] = [new_rq if r == old_rq else r for r in e['requirement_refs']]
                if len(set(e['requirement_refs'])) != len(e['requirement_refs']): e['requirement_refs'] = list(dict.fromkeys(e['requirement_refs']))

    # ---- revision record ----
    modified = []
    for e in model['entities']:
        if e['id'] in before and canonical(to_plain(e)) != before[e['id']]:
            modified.append(e['id']); e['revision_ref'] = rev_id
    record = CommentedMap([('id', rev_id), ('date', cs['date']), ('summary', cs['summary'].strip()), ('basis_refs', cs.get('basis_refs', [])),
                           ('added_entity_ids', new_entity_ids), ('modified_entity_ids', modified),
                           ('added_source_ids', [s for s in sources if s not in before_sources]), ('added_file_ids', [f for f in files if f not in before_files]),
                           ('removed_entity_ids', [])])
    model.setdefault('revisions', CommentedSeq()).append(record)
    summary = {'revision': rev_id, 'added_entities': len(new_entity_ids), 'modified_entities': len(modified), 'added_sources': len(record['added_source_ids']),
               'added_files': record['added_file_ids'], 'intent_added_lines': [a['line'] for a in added], 'intent_expected_by_instruction': ar.get('instruction_expected_added_lines') if ar else None}
    if dry_run:
        print(json.dumps(summary, ensure_ascii=False)); return summary
    with model_path.open('w') as f:
        y.dump(model, f)
    model_schema.write()
    print(json.dumps(summary, ensure_ascii=False))
    return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('revision'); p.add_argument('--dry-run', action='store_true'); a = p.parse_args()
    apply(a.revision, dry_run=a.dry_run)
