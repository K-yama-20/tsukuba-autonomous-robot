"""Form, baseline fidelity and known-issue inventory are separate checks.

This is not a ROS, simulation, safety or vehicle acceptance test, and not the
design-consistency check (see check_design.py).

Fidelity is checked against the frozen initial migration
(design/baselines/migration_v1 + migration_manifest.json). Later revisions may
add entities and modify existing ones only through recorded revision entries;
nothing from the baseline may disappear or change silently. The authority
(intent.md) may only change through a recorded authority revision whose added
lines reproduce the current file from the archived previous copy exactly.
"""
import argparse, collections, csv, hashlib, json, re, sys
from pathlib import Path
from ruamel.yaml import YAML
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / 'design'
EXTRACT = DESIGN / 'docs/extraction_20261008_01a11af4'
BASELINE = DESIGN / 'baselines/migration_v1'
DESIGNED_KINDS = ('ros_node', 'designed_interface')


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def load_yaml(path):
    y = YAML(typ='safe'); y.allow_duplicate_keys = False
    return y.load(path.read_text())


def canonical(o): return json.dumps(o, ensure_ascii=False, sort_keys=True, default=str)


HEADINGS = {'達成したい体験：', '設計において優先する順序:', '基本契約', '役割分担:', '設計する順序：', '避けてほしいこと：', '設計規約：', '個別の要求仕様：', '・デバッグ性の受入条件', '・交換性の受入条件'}


def is_requirement_line(text):
    t = text.strip()
    return bool(t) and not t.startswith('#') and t not in HEADINGS


def authority_text(model, file_ref, root=ROOT):
    """Return the lines of the authority version a source refers to (archived copy for superseded versions)."""
    f = next(x for x in model['files'] if x['id'] == file_ref)
    path = root / (f['archived_copy'] if f['role'] == 'authority_superseded' else f['path'])
    return path.read_text().splitlines()


def current_line_map(model, root=ROOT, intent_path=None):
    """Map intent.md line numbers (of the given version file, default the live file) to requirement IDs by exact text match."""
    srcs = {s['id']: s for s in model['sources']}
    by_text = {}
    for e in model['entities']:
        if e['kind'] != 'requirement' or e['adoption'] == 'superseded': continue
        src = srcs[e['source_refs'][0]]
        if src['kind'] == 'intent_lines': by_text.setdefault(src['raw_fields']['text'], e['id'])
    cur = (intent_path or root / 'design/intent.md').read_text().splitlines()
    return {i: by_text[t] for i, t in enumerate(cur, 1) if t in by_text}


def walk(obj, path=()):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield path + (k,), k, v
            yield from walk(v, path + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj): yield from walk(v, path + (i,))


def core(model, schema):
    findings = []; performed = []
    def fail(code, path, detail): findings.append(dict(code=code, path=str(path), detail=str(detail)))
    Draft202012Validator.check_schema(schema)
    for err in Draft202012Validator(schema).iter_errors(model): fail('SCHEMA', list(err.absolute_path), err.message)
    performed.append('JSON Schema Draft 2020-12')
    if findings: return findings, performed
    ledgers = model.get('decisions', []) + model.get('revisions', []) + model.get('authority_revisions', [])
    records = model['files'] + model['sources'] + model['entities'] + ledgers
    ids = [r['id'] for r in records]; counts = collections.Counter(ids)
    for i, n in counts.items():
        if n > 1: fail('DUPLICATE_ID', i, n)
    byid = {r['id']: r for r in records}; sourceids = {s['id'] for s in model['sources']}; fileids = {f['id'] for f in model['files']}
    entities = {e['id']: e for e in model['entities']}
    decisions = {d['id']: d for d in model.get('decisions', [])}
    revisions = {r['id']: r for r in model.get('revisions', [])}
    for path, key, value in walk(model):
        # Source raw content and verbatim records are opaque evidence, never interpreted as model refs.
        if 'raw_fields' in path or 'original_status' in path or 'added_lines' in path or 'removed_lines' in path or 'changed_lines' in path: continue
        refs = value if key.endswith('_refs') and isinstance(value, list) else [value] if key.endswith('_ref') else []
        for target in refs:
            if target is not None and target not in byid: fail('DANGLING_REF', path, target)
        if key in ('source_ref', 'approval_source_ref') and value not in sourceids: fail('SOURCE_TARGET', path, value)
        if key == 'source_refs':
            for target in value:
                if target not in sourceids: fail('SOURCE_TARGET', path, target)
        if key in ('file_ref', 'authority_ref', 'extraction_verification_ref', 'previous_file_ref', 'superseded_by') and value is not None and value not in fileids: fail('FILE_TARGET', path, value)
        if key == 'decision_ref' and value is not None and value not in decisions: fail('DECISION_TARGET', path, value)
        if key == 'revision_ref' and value not in revisions: fail('REVISION_TARGET', path, value)
    performed.extend(['global ID uniqueness (files, sources, entities, ledgers)', 'reference existence and evidence target types'])
    for f in model['files']:
        if f['role'] == 'authority_superseded' and not (f.get('superseded_by') and f.get('archived_copy')): fail('SUPERSEDED_FILE', f['id'], 'needs superseded_by and archived_copy')
    if entities and byid.get(model['metadata']['authority_ref'], {}).get('role') != 'authority': fail('AUTHORITY_ROLE', 'metadata.authority_ref', 'must point at the current authority file')
    for d in decisions.values():
        if d['status'] == 'answered' and not d['answer_verbatim'].strip(): fail('DECISION_NO_VERBATIM', d['id'], 'answered without verbatim answer')
        if d['status'] == 'pending' and d['answer_verbatim'].strip(): fail('DECISION_PENDING_TEXT', d['id'], 'pending decision must not carry an answer')
    payload = {'module': 'module', 'interface': 'interface', 'mode': 'mode', 'state_owner': 'state_owner', 'execution': 'execution', 'parameter': 'parameter', 'failure_mode': 'failure_mode', 'test': 'test', 'issue': 'issue', 'reconciliation': 'reconciliation', 'diagram_element': 'diagram', 'diagram_connection': 'diagram', 'ros_node': 'ros_node', 'designed_interface': 'designed_interface', 'transition': 'transition'}
    runtime_modes = {e['id'] for e in model['entities'] if e['kind'] == 'mode' and e['mode']['runtime']}
    for e in model['entities']:
        if not e['source_refs']: fail('MISSING_SOURCE', e['id'], 'empty source_refs')
        if e['design_status'] == '承認済み' and not (e.get('approval_source_ref') or decisions.get(e.get('approval_decision_ref'), {}).get('status') == 'answered'): fail('APPROVAL_EVIDENCE', e['id'], 'No lower-design approval evidence (source or answered decision)')
        if e['adoption'] == 'approved' and e['design_status'] != '承認済み': fail('APPROVED_STATUS', e['id'], 'approved adoption requires 承認済み with evidence')
        allowed = payload.get(e['kind'])
        for field in set(payload.values()):
            if field in e and field != allowed: fail('KIND_PAYLOAD', e['id'], field)
        for path, key, v in walk(e):
            if isinstance(v, dict) and 'source_ref' in v and 'field' in v:
                s = byid.get(v['source_ref'], {})
                if v['field'] not in s.get('raw_fields', {}): fail('FIELD_SOURCE', e['id'], v)
                if v['source_ref'] not in e['source_refs']: fail('UNDECLARED_SOURCE', e['id'], v)
        for ref in e['issue_refs']:
            if entities.get(ref, {}).get('kind') != 'issue': fail('ISSUE_TARGET', e['id'], ref)
        for ref in e.get('requirement_refs', []):
            if entities.get(ref, {}).get('adoption') != 'upper_requirement': fail('REQUIREMENT_TARGET', e['id'], ref)
        if 'revision_ref' in e:
            r = revisions.get(e['revision_ref'], {})
            if e['id'] not in r.get('added_entity_ids', []) and e['id'] not in r.get('modified_entity_ids', []): fail('REVISION_MEMBERSHIP', e['id'], e['revision_ref'])
        if e['adoption'] == 'designed_proposal' and e['design_status'] != '案': fail('PROPOSAL_STATUS', e['id'], 'designed proposals stay 案 until approval evidence exists')
        if e['kind'] == 'interface':
            if sorted(x['role'] for x in e['interface']['endpoints']) != ['from', 'to']: fail('ENDPOINT_ROLES', e['id'], 'from/to required')
            for ep in e['interface']['endpoints']:
                for ref in ep['resolved_refs']:
                    if entities.get(ref, {}).get('kind') != 'module': fail('ENDPOINT_TYPE', e['id'], ref)
                if ep['unresolved_tokens'] and not e['issue_refs']: fail('UNTRACKED_ENDPOINT', e['id'], ep['unresolved_tokens'])
        if e['kind'] == 'module':
            for field, kind in [('state_refs', 'state_owner'), ('parameter_refs', 'parameter'), ('failure_refs', 'failure_mode')]:
                for ref in e['module'][field]:
                    if entities.get(ref, {}).get('kind') != kind: fail('MODULE_RELATION', e['id'], [field, ref])
            if entities.get(e['module']['execution_ref'], {}).get('kind') != 'execution': fail('MODULE_RELATION', e['id'], 'execution_ref')
        if e['kind'] in ('state_owner', 'parameter', 'failure_mode', 'execution'):
            key = 'module_ref' if e['kind'] == 'execution' else 'owner_ref'
            owner = entities.get(e[e['kind']][key], {})
            allowed_owner = ('module',) if e['kind'] == 'execution' else ('module', 'ros_node')
            if owner.get('kind') not in allowed_owner: fail('OWNER_TYPE', e['id'], key)
            expected = {r for r in owner.get('related_refs', []) if entities.get(r, {}).get('kind') == 'reconciliation'}
            if not expected.issubset(e['related_refs']): fail('LOST_OWNER_RECONCILIATION', e['id'], sorted(expected - set(e['related_refs'])))
            if e['kind'] == 'state_owner' and owner.get('kind') == 'ros_node' and e['id'] not in owner['ros_node']['owned_state_refs']: fail('OWNER_BACKLINK', e['id'], 'owner node does not list this state')
        if e['kind'] == 'diagram_connection':
            d = e['diagram']
            if d['object_kind'] != 'edge': fail('CONNECTION_KIND', e['id'], 'edge required')
            for key in ('from_ref', 'to_ref', 'parent_ref'):
                if d[key] is not None and entities.get(d[key], {}).get('kind') not in ('diagram_element', 'diagram_connection'): fail('GRAPH_REF_TYPE', e['id'], key)
            if d['from_ref'] is None or d['to_ref'] is None:
                if d['endpoint_status'] != 'unidentified' or not e['issue_refs']: fail('UNTRACKED_UNBOUND', e['id'], 'Null endpoint must be explicit and tracked')
        if e['kind'] == 'parameter' and e['parameter']['value_state'] == 'unresolved' and not e['issue_refs']: fail('UNTRACKED_PARAMETER', e['id'], 'missing issue')
        if e['kind'] == 'reconciliation':
            r = e['reconciliation']
            if r['state'] == 'resolved_by_intent':
                if not r['adopted_requirement_refs']: fail('REPLACEMENT_EVIDENCE', e['id'], 'no authority')
                for ref in r['adopted_requirement_refs']:
                    if entities.get(ref, {}).get('adoption') != 'upper_requirement': fail('REPLACEMENT_AUTHORITY', e['id'], ref)
            elif r['state'] == 'resolved_by_decision':
                if decisions.get(r.get('decision_ref'), {}).get('status') != 'answered': fail('DECISION_RESOLUTION', e['id'], 'resolved_by_decision needs an answered decision')
            elif not r['issue_refs']: fail('UNTRACKED_CONFLICT', e['id'], 'open conflict without issue')
        if e['kind'] == 'issue':
            if e['issue']['state'] == 'resolved' and not e['issue']['resolution_refs']: fail('RESOLVED_WITHOUT_EVIDENCE', e['id'], 'resolved issue needs resolution_refs')
            for a in e['issue']['affected_refs']:
                if a not in entities: fail('AFFECTED_TARGET', e['id'], a)
        if e['kind'] == 'ros_node':
            n = e['ros_node']
            for ref in n['absorbs_module_refs']:
                if entities.get(ref, {}).get('kind') != 'module': fail('NODE_ABSORBS_TYPE', e['id'], ref)
            for ref in n['active_in_mode_refs']:
                if ref not in runtime_modes: fail('NODE_MODE_TYPE', e['id'], ref)
            for field in ('publishes_refs', 'subscribes_refs', 'serves_refs', 'calls_refs'):
                for ref in n[field]:
                    if entities.get(ref, {}).get('kind') != 'designed_interface': fail('NODE_IF_TYPE', e['id'], [field, ref])
            for ref in n['owned_state_refs']:
                so = entities.get(ref, {})
                if so.get('kind') != 'state_owner' or so['state_owner']['owner_ref'] != e['id']: fail('NODE_STATE_OWNER', e['id'], ref)
        if e['kind'] == 'designed_interface':
            d = e['designed_interface']
            for ref in d['publisher_refs']:
                if entities.get(ref, {}).get('kind') != 'ros_node': fail('IF_PUBLISHER_TYPE', e['id'], ref)
            for ref in d['consumer_refs']:
                if entities.get(ref, {}).get('kind') not in ('ros_node', 'module'): fail('IF_CONSUMER_TYPE', e['id'], ref)
            for ref in d['legacy_refs']:
                if entities.get(ref, {}).get('kind') not in ('interface', 'data_contract'): fail('IF_LEGACY_TYPE', e['id'], ref)
            if d['owner_ref'] is not None:
                if entities.get(d['owner_ref'], {}).get('kind') != 'ros_node': fail('IF_OWNER_TYPE', e['id'], d['owner_ref'])
                if d['owner_ref'] not in d['publisher_refs']: fail('IF_OWNER_NOT_PUBLISHER', e['id'], d['owner_ref'])
            if d['version_dependency']['status'] != 'none' and e['design_status'] == '承認済み': fail('VERSION_UNCONFIRMED_APPROVED', e['id'], d['version_dependency']['status'])
        if e['kind'] == 'transition' and 'transition' in e:
            t = e['transition']
            for key in ('from_mode_ref', 'to_mode_ref'):
                if t[key] is not None and t[key] not in runtime_modes: fail('TRANSITION_MODE_TYPE', e['id'], [key, t[key]])
            if entities.get(t['owner_ref'], {}).get('kind') != 'ros_node': fail('TRANSITION_OWNER_TYPE', e['id'], t['owner_ref'])
        if 'boundary' in e and e['boundary']['decision_ref'] in decisions and decisions[e['boundary']['decision_ref']]['status'] != 'pending': fail('BOUNDARY_DECIDED', e['id'], 'decision answered; boundary status must be updated by a revision')
    performed.extend(['field bindings and source presence', 'entity-kind and ownership references', 'explicit unknowns and issue tracking', 'replacement authority and open conflict tracking', 'designed node/interface/transition reference types', 'decision ledger verbatim rule'])
    return findings, performed


def migration(model, manifest, root=ROOT):
    failures = []; performed = []
    def check(name, actual, expected):
        performed.append(name)
        if actual != expected:
            failures.append(dict(code='MIGRATION', path=name, detail={'actual': actual, 'expected': expected}))
    source = {s['id']: s for s in model['sources']}; entities = {e['id']: e for e in model['entities']}; files = {f['id']: f for f in model['files']}
    revisions = model.get('revisions', []); authority_revs = model.get('authority_revisions', [])
    # Frozen baseline directory is intact.
    snapshot = json.loads((BASELINE / 'snapshot.json').read_text())
    for rel, h in snapshot.items():
        p = BASELINE / Path(rel).relative_to('design'); check('baseline snapshot intact ' + rel, sha(p) if p.exists() else None, h)
    # Input files: unchanged, except the authority through a verified authority revision.
    for path, expected in manifest['protected_files'].items():
        p = root / path; actual = sha(p) if p.exists() else None
        if actual == expected or path != 'design/intent.md':
            check('unchanged ' + path, actual, expected); continue
        ar = next((a for a in authority_revs if a['previous_sha256'] == expected), None)
        check('intent change registered as authority revision', ar is not None, True)
        if ar is None: continue
        # Follow the chain of authority revisions from the baseline to the current file.
        chain = [ar]
        while chain[-1]['sha256'] != actual:
            nxt = next((a for a in authority_revs if a['previous_sha256'] == chain[-1]['sha256']), None)
            if nxt is None: break
            chain.append(nxt)
        check('intent revision chain reaches current file', chain[-1]['sha256'], actual)
        for a in chain:
            archived = root / a['archived_previous_copy']
            check('intent previous copy archived ' + a['id'], sha(archived) if archived.exists() else None, a['previous_sha256'])
            rebuilt = archived.read_text().splitlines()
            removed = {r['line'] for r in a['removed_lines']} | {c['line'] for c in a['changed_lines']}
            for r in a['removed_lines'] + a['changed_lines']:
                check(f"intent removed line text recorded {a['id']}:{r['line']}", rebuilt[r['line'] - 1] if 0 < r['line'] <= len(rebuilt) else None, r['text'])
            rebuilt = [l for i, l in enumerate(rebuilt, 1) if i not in removed]
            for x in sorted(a['added_lines'], key=lambda x: x['line']): rebuilt.insert(x['line'] - 1, x['text'])
            target = root / 'design/intent.md' if a is chain[-1] else root / chain[chain.index(a) + 1]['archived_previous_copy']
            check('intent reproduced from archived copy plus recorded lines ' + a['id'], rebuilt, target.read_text().splitlines())
            check('intent observed added line count recorded ' + a['id'], a['observed_added_lines'], len(a['added_lines']))
            check('intent instruction expectation compared ' + a['id'], a['instruction_expected_added_lines'] == a['observed_added_lines'] or bool(a['decision_ref']), True)
            if a['removed_lines'] or a['changed_lines']:
                check('intent non-append edit recorded with decision ' + a['id'], bool(a['decision_ref']), True)
            for x in a['added_lines']:
                if not is_requirement_line(x['text']): continue
                rq = next((e for e in model['entities'] if e['kind'] == 'requirement' and source[e['source_refs'][0]]['kind'] == 'intent_lines' and source[e['source_refs'][0]]['raw_fields']['text'] == x['text']), None)
                check(f"intent added line {a['id']}:{x['line']} has requirement entity", rq is not None and rq['id'] in a['requirement_refs'], True)
    base_model = load_yaml(BASELINE / 'model.yaml'); base_file_ids = {f['id']: f['sha256'] for f in base_model['files']}
    for f in model['files']:
        if f['role'] == 'authority_superseded':
            check('model file hash (archived) ' + f['id'], sha(root / f['archived_copy']), f['sha256'])
        else:
            check('model file hash ' + f['id'], sha(root / f['path']) if (root / f['path']).exists() else None, f['sha256'])
        if f['id'] in base_file_ids:
            check('model vs baseline file hash ' + f['id'], f['sha256'], base_file_ids[f['id']])
        elif not any(f['id'] in r['added_file_ids'] for r in revisions):
            check('new file recorded in a revision ' + f['id'], False, True)
    # Inventories: baseline is a subset; every addition is recorded exactly once.
    base_entities = set(manifest['entity_ids']); base_sources = set(manifest['source_ids'])
    check('immutable initial entity ID inventory', sorted(base_entities - set(entities)), [])
    check('immutable initial source ID inventory', sorted(base_sources - set(source)), [])
    added_e = [i for r in revisions for i in r['added_entity_ids']]; added_s = [i for r in revisions for i in r['added_source_ids']]
    check('revision-added entity IDs unique', len(added_e), len(set(added_e)))
    check('revision-added entities are not baseline IDs', sorted(set(added_e) & base_entities), [])
    check('revision-added entity inventory', sorted(set(entities) - base_entities), sorted(set(added_e)))
    check('revision-added source inventory', sorted(set(source) - base_sources), sorted(set(added_s)))
    check('known issue ID inventory', sorted(set(manifest['known_issue_ids']) - {e['id'] for e in model['entities'] if e['kind'] == 'issue'}), [])
    check('no deletions recorded', [r['removed_entity_ids'] for r in revisions], [[] for _ in revisions])
    for key, target in manifest['id_registry'].items(): check('allocated stable ID ' + key, target in entities, True)
    # Baseline content: identical unless the change is recorded as a modification.
    modified = {i for r in revisions for i in r['modified_entity_ids']}
    changed = []
    for be in base_model['entities']:
        cur = entities.get(be['id'])
        if cur is None: continue
        if canonical(be) != canonical(cur): changed.append(be['id'])
    check('baseline entities changed only via recorded modifications', sorted(set(changed) - modified), [])
    check('recorded modifications actually differ from baseline', sorted((modified & base_entities) - set(changed)), [])
    check('recorded modifications of later-added entities exist', sorted((modified - base_entities) - set(added_e)), [])
    for bs in base_model['sources']: check('baseline source unchanged ' + bs['id'], canonical(source.get(bs['id'])), canonical(bs))
    check('baseline migration section unchanged', canonical(model['migration']), canonical(base_model['migration']))
    # Existing extraction is the input. Do not re-extract XLSX/drawio.
    rows = [json.loads(s) for s in (EXTRACT / 'excel_rows.jsonl').read_text().splitlines()]
    rowlookup = {(r['sheet'], r['row']): r for r in rows}
    rawdraw = [json.loads(s) for s in (EXTRACT / 'drawio_objects.jsonl').read_text().splitlines()]
    drawings = {(r['page_id'], r['id']): r for r in rawdraw}
    intent = (root / 'design/intent.md').read_text().splitlines()
    mappedrows = []; mappeddraw = []; mappedlines = []
    for s in model['sources']:
        loc = s['locator']
        if s['kind'] == 'excel_row':
            key = (loc['sheet'], loc['row']); r = rowlookup.get(key)
            check('Excel source exists ' + s['id'], r is not None, True)
            if r:
                mappedrows.append(key)
                check('Excel verbatim ' + s['id'], s['raw_fields'], r['values'])
                check('Excel exact range ' + s['id'], loc['range'], f'A{r["row"]}:{r["cell_ids"][-1]}')
                check('Excel original status ' + s['id'], s['original_status'], dict(classification=r['status'], raw=r['status_raw'], basis=r['status_basis'], locations=r['status_source']))
        elif s['kind'] == 'drawio_object':
            key = (loc['page'], loc['element_id']); d = drawings.get(key)
            check('drawio source exists ' + s['id'], d is not None, True)
            if d:
                mappeddraw.append(key)
                check('drawio verbatim ' + s['id'], s['raw_fields'], {k: d[k] for k in ('value_raw', 'attributes', 'wrapper_attributes', 'geometry_xml', 'parent', 'source', 'target')})
        elif s['kind'] == 'intent_lines':
            start = loc['line_start']; end = loc['line_end']; mappedlines.extend(range(start, end + 1))
            version_lines = authority_text(model, s['file_ref'], root)
            check('intent verbatim (its version) ' + s['id'], s['raw_fields'], {'text': '\n'.join(version_lines[start - 1:end])})
    expectedrows = []
    dispositions = {(r['sheet'], r['row']): r for r in model['migration']['row_dispositions']}
    check('row disposition inventory', sorted(dispositions), sorted(rowlookup))
    for key, r in rowlookup.items():
        wanted = 'header' if r['row'] == 1 else 'vocabulary' if r['sheet'] == '選択肢' else 'migrated' if any(v not in (None, '') for v in r['values'].values()) else 'empty'
        d = dispositions.get(key, {})
        check('row disposition ' + str(key), d.get('disposition'), wanted)
        if wanted == 'migrated':
            expectedrows.append(key)
            e = entities.get(d.get('target_ref'), {})
            check('row target provenance ' + str(key), any(source.get(x, {}).get('locator', {}).get('sheet') == key[0] and source.get(x, {}).get('locator', {}).get('row') == key[1] for x in e.get('source_refs', [])), True)
    check('meaningful Excel rows complete', sorted(mappedrows), sorted(expectedrows))
    check('drawio ID occurrences complete', sorted(mappeddraw), sorted(drawings))
    # Every requirement line of the current intent.md is a recorded requirement; every live requirement text is still in the file.
    live_texts = {source[e['source_refs'][0]]['raw_fields']['text'] for e in model['entities'] if e['kind'] == 'requirement' and e['adoption'] != 'superseded' and source[e['source_refs'][0]]['kind'] == 'intent_lines'}
    check('intent requirement lines complete', [l for l in intent if is_requirement_line(l) and l not in live_texts], [])
    check('live intent requirements still present in current file', sorted(t for t in live_texts if t not in intent), [])
    for e in model['entities']:
        if e['kind'] == 'requirement' and e['adoption'] == 'superseded':
            check('superseded requirement justified ' + e['id'], any(c['kind'] == 'reconciliation' and c['reconciliation']['state'] == 'resolved_by_intent' and e['id'] in c['reconciliation']['affected_refs'] for c in model['entities']), True)
    with (EXTRACT / 'excel_ids.csv').open(encoding='utf-8-sig', newline='') as f: baseline = [r for r in csv.DictReader(f) if r['role'] == 'definition']
    check('original 198 definition IDs', [r['id'] for r in baseline], [r['legacy_id'] for r in model['migration']['id_map'] if r['baseline']])
    check('baseline ID count', len(baseline), 198)
    extra = []
    expected_def = {r['id']: (r['sheet'], int(re.search(r'\d+$', r['cell'])[0])) for r in baseline}
    for r in rows:
        value = r['values'].get(f'A{r["row"]}')
        if isinstance(value, str) and re.fullmatch(r'CH-\d+', value): expected_def[value] = (r['sheet'], r['row']); extra.append(value)
    check('additional existing IDs', sorted(r['legacy_id'] for r in model['migration']['id_map'] if not r['baseline']), sorted(extra))
    check('all ID map keys', sorted(r['legacy_id'] for r in model['migration']['id_map']), sorted(expected_def))
    for m in model['migration']['id_map']:
        check('legacy ID unchanged ' + m['legacy_id'], m['target_ref'], m['legacy_id'])
        loc = source.get(m['source_ref'], {}).get('locator', {})
        check('ID mapping source ' + m['legacy_id'], (loc.get('sheet'), loc.get('row')), expected_def.get(m['legacy_id']))
        check('ID mapping target source ' + m['legacy_id'], m['source_ref'] in entities.get(m['target_ref'], {}).get('source_refs', []), True)
    # Check bound endpoints by original object IDs, never by label guesses.
    byoriginal = {}
    for e in model['entities']:
        if e['kind'] in ('diagram_element', 'diagram_connection'):
            loc = source[e['source_refs'][0]]['locator']; byoriginal[(loc['page'], loc['element_id'])] = e
    for key, d in drawings.items():
        e = byoriginal.get(key)
        check('draw object target ' + str(key), e is not None, True)
        if not e: continue
        for rawkey, modelkey in [('parent', 'parent_ref'), ('source', 'from_ref'), ('target', 'to_ref')]:
            expected = byoriginal.get((key[0], d[rawkey]), {}).get('id')
            check('drawio endpoint ' + d['id'] + '/' + rawkey, e['diagram'][modelkey], expected)
        check('drawio kind ' + d['id'], e['diagram']['object_kind'], d['kind'])
    unbound = [e for e in model['entities'] if e['kind'] == 'diagram_connection' and e['diagram']['endpoint_status'] == 'unidentified']
    check('known unbound count', len(unbound), 1)
    check('known unbound issue', all('U-DRAW-001' in e['issue_refs'] for e in unbound), True)
    check('unbound target remains null', all(e['diagram']['to_ref'] is None for e in unbound), True)
    check('current four modes', sorted(e['mode']['current_name'] for e in model['entities'] if e['kind'] == 'mode' and e['mode']['runtime']), sorted(['自律走行', '事前地図作成', '一時停止', '手動走行']))
    # Prior 48 checks are explicitly extraction fidelity, not current design acceptance.
    old = json.loads((EXTRACT / 'verification.json').read_text()); check('prior extraction fidelity recorded', old['passed'], True)
    srcmanifest = json.loads((EXTRACT / 'source_manifest.json').read_text())
    for path, h in srcmanifest['sha256'].items():
        # The extraction recorded absolute workspace paths; resolve them relative to this checkout first (portable), else as recorded.
        rel = path.split('/design/', 1)[1] if '/design/' in path else None
        p = root / 'design' / rel if rel and (root / 'design' / rel).exists() else Path(path)
        check('source matches prior extraction ' + path, sha(p) if p.exists() else None, h)
    return failures, performed


def inspect(model, schema, manifest):
    failures, performed = core(model, schema)
    if not failures:
        f, p = migration(model, manifest); failures += f; performed += p
    issues = [{'id': e['id'], **e['issue']} for e in model['entities'] if e['kind'] == 'issue']
    conflicts = [{'id': e['id'], **e['reconciliation']} for e in model['entities'] if e['kind'] == 'reconciliation']
    decisions = model.get('decisions', [])
    return dict(format_and_migration={'result': '違反' if failures else '合格', 'executed_checks': len(performed), 'violations': failures, 'check_names': performed},
                design_validity={'result': '未判定', 'reason': '移行検査は設計妥当性検証ではない。設計整合性は check_design.py の三値結果を参照。未設計・未確定・資料衝突を保持。', 'known_issue_count': len(issues), 'known_issue_counts': dict(collections.Counter(i['category'] for i in issues)), 'known_issues': issues, 'open_conflicts': [c['id'] for c in conflicts if c['state'] == 'open'], 'resolved_by_intent': [c['id'] for c in conflicts if c['state'] == 'resolved_by_intent']},
                design_maturity=dict(collections.Counter(e['design_status'] for e in model['entities'])),
                revisions=[{k: (len(v) if isinstance(v, list) else v) for k, v in r.items() if k != 'summary'} for r in model.get('revisions', [])],
                authority_revisions=[{k: v for k, v in a.items() if k not in ('added_lines', 'removed_lines', 'changed_lines')} | {'added_line_numbers': [x['line'] for x in a['added_lines']]} for a in model.get('authority_revisions', [])],
                decisions={'count': len(decisions), 'by_status': dict(collections.Counter(d['status'] for d in decisions)), 'pending': [d['id'] for d in decisions if d['status'] == 'pending']},
                vehicle_verification={'result': '未実施', 'deployment_decision': '人の判断待ち'},
                summary={'entity_count': len(model['entities']), 'source_count': len(model['sources']), 'id_map_count': len(model['migration']['id_map']), 'legacy_198_count': sum(m['baseline'] for m in model['migration']['id_map']), 'unbound_edges': sum(e['kind'] == 'diagram_connection' and e['diagram']['endpoint_status'] == 'unidentified' for e in model['entities']), 'boundary_unconfirmed': [e['id'] for e in model['entities'] if 'boundary' in e]})


def main():
    p = argparse.ArgumentParser(); p.add_argument('--model', type=Path, default=DESIGN / 'model.yaml'); p.add_argument('--schema', type=Path, default=DESIGN / 'schema.json'); p.add_argument('--manifest', type=Path, default=DESIGN / 'migration_manifest.json'); p.add_argument('--report', type=Path, default=DESIGN / 'reports/migration_validation.json'); a = p.parse_args()
    try: result = inspect(load_yaml(a.model), json.loads(a.schema.read_text()), json.loads(a.manifest.read_text()))
    except Exception as exc:
        result = {'format_and_migration': {'result': '違反', 'violations': [{'code': 'LOAD_OR_VALIDATOR_ERROR', 'detail': repr(exc)}]}, 'design_validity': {'result': '未判定'}, 'vehicle_verification': {'result': '未実施'}}
    a.report.parent.mkdir(parents=True, exist_ok=True); a.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('design_validity', 'format_and_migration')}, ensure_ascii=False))
    print(json.dumps({k: v for k, v in result['format_and_migration'].items() if k != 'check_names'}, ensure_ascii=False)[:4000])
    return 0 if result['format_and_migration']['result'] == '合格' else 1


if __name__ == '__main__': sys.exit(main())
