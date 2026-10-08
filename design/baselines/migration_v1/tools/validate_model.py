"""Form, migration fidelity and known-issue inventory are separate checks.

This is not a ROS, simulation, safety or vehicle acceptance test.
CLI always runs full migration verification; unit tests can exercise the core
against deliberately small documents without claiming migration acceptance.
"""
import argparse, collections, csv, hashlib, json, re, sys
from pathlib import Path
from ruamel.yaml import YAML
from jsonschema import Draft202012Validator

ROOT=Path(__file__).resolve().parents[2]
DESIGN=ROOT/'design'
EXTRACT=DESIGN/'docs/extraction_20261008_01a11af4'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load_yaml(path):
    y=YAML(typ='safe'); y.allow_duplicate_keys=False
    return y.load(path.read_text())
def walk(obj,path=()):
    if isinstance(obj,dict):
        for k,v in obj.items():
            yield path+(k,),k,v
            yield from walk(v,path+(k,))
    elif isinstance(obj,list):
        for i,v in enumerate(obj): yield from walk(v,path+(i,))
def core(model,schema):
    findings=[]; performed=[]
    def fail(code,path,detail): findings.append(dict(code=code,path=str(path),detail=str(detail)))
    Draft202012Validator.check_schema(schema)
    for err in Draft202012Validator(schema).iter_errors(model): fail('SCHEMA',list(err.absolute_path),err.message)
    performed.append('JSON Schema Draft 2020-12')
    if findings: return findings,performed
    records=model['files']+model['sources']+model['entities']
    ids=[r['id'] for r in records]; counts=collections.Counter(ids)
    for i,n in counts.items():
        if n>1: fail('DUPLICATE_ID',i,n)
    byid={r['id']:r for r in records}; sourceids={s['id'] for s in model['sources']}; fileids={f['id'] for f in model['files']}
    entities={e['id']:e for e in model['entities']}
    for path,key,value in walk(model):
        # Source raw content is opaque evidence, never interpreted as model refs.
        if 'raw_fields' in path or 'original_status' in path: continue
        refs=value if key.endswith('_refs') and isinstance(value,list) else [value] if key.endswith('_ref') else []
        for target in refs:
            if target is not None and target not in byid: fail('DANGLING_REF',path,target)
        if key in ('source_ref','approval_source_ref') and value not in sourceids: fail('SOURCE_TARGET',path,value)
        if key=='source_refs':
            for target in value:
                if target not in sourceids: fail('SOURCE_TARGET',path,target)
        if key in ('file_ref','authority_ref','extraction_verification_ref') and value not in fileids: fail('FILE_TARGET',path,value)
    performed.extend(['global ID uniqueness','reference existence and evidence target types'])
    for e in model['entities']:
        if not e['source_refs']: fail('MISSING_SOURCE',e['id'],'empty source_refs')
        if e['design_status']=='承認済み' and not e.get('approval_source_ref'): fail('APPROVAL_EVIDENCE',e['id'],'No lower-design approval evidence')
        payload={'module':'module','interface':'interface','mode':'mode','state_owner':'state_owner','execution':'execution','parameter':'parameter','failure_mode':'failure_mode','test':'test','issue':'issue','reconciliation':'reconciliation','diagram_element':'diagram','diagram_connection':'diagram'}
        allowed=payload.get(e['kind'])
        for field in set(payload.values()):
            if field in e and field!=allowed: fail('KIND_PAYLOAD',e['id'],field)
        for path,key,v in walk(e):
            if isinstance(v,dict) and 'source_ref' in v and 'field' in v:
                s=byid.get(v['source_ref'],{})
                if v['field'] not in s.get('raw_fields',{}): fail('FIELD_SOURCE',e['id'],v)
                if v['source_ref'] not in e['source_refs']: fail('UNDECLARED_SOURCE',e['id'],v)
        for ref in e['issue_refs']:
            if entities.get(ref,{}).get('kind')!='issue': fail('ISSUE_TARGET',e['id'],ref)
        if e['kind']=='interface':
            if sorted(x['role'] for x in e['interface']['endpoints'])!=['from','to']: fail('ENDPOINT_ROLES',e['id'],'from/to required')
            for ep in e['interface']['endpoints']:
                for ref in ep['resolved_refs']:
                    if entities.get(ref,{}).get('kind')!='module': fail('ENDPOINT_TYPE',e['id'],ref)
                if ep['unresolved_tokens'] and not e['issue_refs']: fail('UNTRACKED_ENDPOINT',e['id'],ep['unresolved_tokens'])
        if e['kind']=='module':
            for field,kind in [('state_refs','state_owner'),('parameter_refs','parameter'),('failure_refs','failure_mode')]:
                for ref in e['module'][field]:
                    if entities.get(ref,{}).get('kind')!=kind: fail('MODULE_RELATION',e['id'],[field,ref])
            if entities.get(e['module']['execution_ref'],{}).get('kind')!='execution': fail('MODULE_RELATION',e['id'],'execution_ref')
        if e['kind'] in ('state_owner','parameter','failure_mode','execution'):
            key='module_ref' if e['kind']=='execution' else 'owner_ref'
            if entities.get(e[e['kind']][key],{}).get('kind')!='module': fail('OWNER_TYPE',e['id'],key)
            owner=entities.get(e[e['kind']][key],{})
            expected={r for r in owner.get('related_refs',[]) if entities.get(r,{}).get('kind')=='reconciliation'}
            if not expected.issubset(e['related_refs']): fail('LOST_OWNER_RECONCILIATION',e['id'],sorted(expected-set(e['related_refs'])))
        if e['kind']=='diagram_connection':
            d=e['diagram']
            if d['object_kind']!='edge': fail('CONNECTION_KIND',e['id'],'edge required')
            for key in ('from_ref','to_ref','parent_ref'):
                if d[key] is not None and entities.get(d[key],{}).get('kind') not in ('diagram_element','diagram_connection'): fail('GRAPH_REF_TYPE',e['id'],key)
            if d['from_ref'] is None or d['to_ref'] is None:
                if d['endpoint_status']!='unidentified' or not e['issue_refs']: fail('UNTRACKED_UNBOUND',e['id'],'Null endpoint must be explicit and tracked')
        if e['kind']=='parameter' and e['parameter']['value_state']=='unresolved' and not e['issue_refs']: fail('UNTRACKED_PARAMETER',e['id'],'missing issue')
        if e['kind']=='reconciliation':
            r=e['reconciliation']
            if r['state']=='resolved_by_intent':
                if not r['adopted_requirement_refs']: fail('REPLACEMENT_EVIDENCE',e['id'],'no authority')
                for ref in r['adopted_requirement_refs']:
                    if entities.get(ref,{}).get('adoption')!='upper_requirement': fail('REPLACEMENT_AUTHORITY',e['id'],ref)
            elif not r['issue_refs']: fail('UNTRACKED_CONFLICT',e['id'],'open conflict without issue')
        if e['kind']=='issue':
            for a in e['issue']['affected_refs']:
                if a not in entities: fail('AFFECTED_TARGET',e['id'],a)
    performed.extend(['field bindings and source presence','entity-kind and ownership references','explicit unknowns and issue tracking','replacement authority and open conflict tracking'])
    return findings,performed

def migration(model,manifest,root=ROOT):
    failures=[]; performed=[]
    def check(name,actual,expected):
        performed.append(name)
        if actual!=expected:
            failures.append(dict(code='MIGRATION',path=name,detail={'actual':actual,'expected':expected}))
    source={s['id']:s for s in model['sources']}; entities={e['id']:e for e in model['entities']}
    for path,expected in manifest['protected_files'].items():
        p=root/path; check('unchanged '+path,sha(p) if p.exists() else None,expected)
    for f in model['files']:
        check('model file hash '+f['id'],sha(root/f['path']) if (root/f['path']).exists() else None,f['sha256'])
        check('model vs baseline file hash '+f['id'],f['sha256'],manifest['protected_files'].get(f['path']))
    check('immutable initial entity ID inventory',sorted(entities),sorted(manifest['entity_ids']))
    check('immutable initial source ID inventory',sorted(source),sorted(manifest['source_ids']))
    check('known issue ID inventory',sorted(e['id'] for e in model['entities'] if e['kind']=='issue'),sorted(manifest['known_issue_ids']))
    for key,target in manifest['id_registry'].items(): check('allocated stable ID '+key,target in entities,True)
    # Existing extraction is the input. Do not re-extract XLSX/drawio.
    rows=[json.loads(s) for s in (EXTRACT/'excel_rows.jsonl').read_text().splitlines()]
    rowlookup={(r['sheet'],r['row']):r for r in rows}
    rawdraw=[json.loads(s) for s in (EXTRACT/'drawio_objects.jsonl').read_text().splitlines()]
    drawings={(r['page_id'],r['id']):r for r in rawdraw}
    intent=(root/'design/intent.md').read_text().splitlines()
    mappedrows=[]; mappeddraw=[]; mappedlines=[]
    for s in model['sources']:
        loc=s['locator']
        if s['kind']=='excel_row':
            key=(loc['sheet'],loc['row']); r=rowlookup.get(key)
            check('Excel source exists '+s['id'],r is not None,True)
            if r:
                mappedrows.append(key)
                check('Excel verbatim '+s['id'],s['raw_fields'],r['values'])
                check('Excel exact range '+s['id'],loc['range'],f'A{r["row"]}:{r["cell_ids"][-1]}')
                check('Excel original status '+s['id'],s['original_status'],dict(classification=r['status'],raw=r['status_raw'],basis=r['status_basis'],locations=r['status_source']))
        elif s['kind']=='drawio_object':
            key=(loc['page'],loc['element_id']); d=drawings.get(key)
            check('drawio source exists '+s['id'],d is not None,True)
            if d:
                mappeddraw.append(key)
                check('drawio verbatim '+s['id'],s['raw_fields'],{k:d[k] for k in ('value_raw','attributes','wrapper_attributes','geometry_xml','parent','source','target')})
        elif s['kind']=='intent_lines':
            start=loc['line_start']; end=loc['line_end']; mappedlines.extend(range(start,end+1))
            check('intent verbatim '+s['id'],s['raw_fields'],{'text':'\n'.join(intent[start-1:end])})
    expectedrows=[]
    dispositions={(r['sheet'],r['row']):r for r in model['migration']['row_dispositions']}
    check('row disposition inventory',sorted(dispositions),sorted(rowlookup))
    for key,r in rowlookup.items():
        wanted='header' if r['row']==1 else 'vocabulary' if r['sheet']=='選択肢' else 'migrated' if any(v not in (None,'') for v in r['values'].values()) else 'empty'
        d=dispositions.get(key,{})
        check('row disposition '+str(key),d.get('disposition'),wanted)
        if wanted=='migrated':
            expectedrows.append(key)
            e=entities.get(d.get('target_ref'),{})
            check('row target provenance '+str(key),any(source.get(x,{}).get('locator',{}).get('sheet')==key[0] and source.get(x,{}).get('locator',{}).get('row')==key[1] for x in e.get('source_refs',[])),True)
    check('meaningful Excel rows complete',sorted(mappedrows),sorted(expectedrows))
    check('drawio ID occurrences complete',sorted(mappeddraw),sorted(drawings))
    check('intent requirement lines complete',sorted(mappedlines),sorted(int(x) for x in manifest['intent_requirement_lines']))
    with (EXTRACT/'excel_ids.csv').open(encoding='utf-8-sig',newline='') as f: baseline=[r for r in csv.DictReader(f) if r['role']=='definition']
    check('original 198 definition IDs',[r['id'] for r in baseline], [r['legacy_id'] for r in model['migration']['id_map'] if r['baseline']])
    check('baseline ID count',len(baseline),198)
    extra=[]
    expected_def={r['id']:(r['sheet'],int(re.search(r'\d+$',r['cell'])[0])) for r in baseline}
    for r in rows:
        value=r['values'].get(f'A{r["row"]}')
        if isinstance(value,str) and re.fullmatch(r'CH-\d+',value): expected_def[value]=(r['sheet'],r['row']); extra.append(value)
    check('additional existing IDs',sorted(r['legacy_id'] for r in model['migration']['id_map'] if not r['baseline']),sorted(extra))
    check('all ID map keys',sorted(r['legacy_id'] for r in model['migration']['id_map']),sorted(expected_def))
    for m in model['migration']['id_map']:
        check('legacy ID unchanged '+m['legacy_id'],m['target_ref'],m['legacy_id'])
        loc=source.get(m['source_ref'],{}).get('locator',{})
        check('ID mapping source '+m['legacy_id'],(loc.get('sheet'),loc.get('row')),expected_def.get(m['legacy_id']))
        check('ID mapping target source '+m['legacy_id'],m['source_ref'] in entities.get(m['target_ref'],{}).get('source_refs',[]),True)
    # Check bound endpoints by original object IDs, never by label guesses.
    byoriginal={}
    for e in model['entities']:
        if e['kind'] in ('diagram_element','diagram_connection'):
            loc=source[e['source_refs'][0]]['locator']; byoriginal[(loc['page'],loc['element_id'])]=e
    for key,d in drawings.items():
        e=byoriginal.get(key)
        check('draw object target '+str(key),e is not None,True)
        if not e: continue
        for rawkey,modelkey in [('parent','parent_ref'),('source','from_ref'),('target','to_ref')]:
            expected=byoriginal.get((key[0],d[rawkey]),{}).get('id')
            check('drawio endpoint '+d['id']+'/'+rawkey,e['diagram'][modelkey],expected)
        check('drawio kind '+d['id'],e['diagram']['object_kind'],d['kind'])
    unbound=[e for e in model['entities'] if e['kind']=='diagram_connection' and e['diagram']['endpoint_status']=='unidentified']
    check('known unbound count',len(unbound),1)
    check('known unbound issue',all('U-DRAW-001' in e['issue_refs'] for e in unbound),True)
    check('unbound target remains null',all(e['diagram']['to_ref'] is None for e in unbound),True)
    check('current four modes',sorted(e['mode']['current_name'] for e in model['entities'] if e['kind']=='mode' and e['mode']['runtime']),sorted(['自律走行','事前地図作成','一時停止','手動走行']))
    # Prior 48 checks are explicitly extraction fidelity, not current design acceptance.
    old=json.loads((EXTRACT/'verification.json').read_text()); check('prior extraction fidelity recorded',old['passed'],True)
    srcmanifest=json.loads((EXTRACT/'source_manifest.json').read_text())
    for path,h in srcmanifest['sha256'].items(): check('source matches prior extraction '+path,sha(Path(path)),h)
    return failures,performed

def inspect(model,schema,manifest):
    failures,performed=core(model,schema)
    if not failures:
        f,p=migration(model,manifest); failures+=f; performed+=p
    issues=[{'id':e['id'],**e['issue']} for e in model['entities'] if e['kind']=='issue']
    conflicts=[{'id':e['id'],**e['reconciliation']} for e in model['entities'] if e['kind']=='reconciliation']
    return dict(format_and_migration={'result':'違反' if failures else '合格','executed_checks':len(performed),'violations':failures,'check_names':performed},
                design_validity={'result':'未判定','reason':'移行検査は設計妥当性検証ではない。未設計・未確定・資料衝突を保持。','known_issue_count':len(issues),'known_issue_counts':dict(collections.Counter(i['category'] for i in issues)),'known_issues':issues,'open_conflicts':[c['id'] for c in conflicts if c['state']=='open'],'resolved_by_intent':[c['id'] for c in conflicts if c['state']=='resolved_by_intent']},
                design_maturity=dict(collections.Counter(e['design_status'] for e in model['entities'])),
                vehicle_verification={'result':'未実施','deployment_decision':'人の判断待ち'},
                summary={'entity_count':len(model['entities']),'source_count':len(model['sources']),'id_map_count':len(model['migration']['id_map']),'legacy_198_count':sum(m['baseline'] for m in model['migration']['id_map']),'unbound_edges':sum(e['kind']=='diagram_connection' and e['diagram']['endpoint_status']=='unidentified' for e in model['entities'])})

def main():
    p=argparse.ArgumentParser(); p.add_argument('--model',type=Path,default=DESIGN/'model.yaml'); p.add_argument('--schema',type=Path,default=DESIGN/'schema.json'); p.add_argument('--manifest',type=Path,default=DESIGN/'migration_manifest.json'); p.add_argument('--report',type=Path,default=DESIGN/'reports/migration_validation.json'); a=p.parse_args()
    try: result=inspect(load_yaml(a.model),json.loads(a.schema.read_text()),json.loads(a.manifest.read_text()))
    except Exception as exc:
        result={'format_and_migration':{'result':'違反','violations':[{'code':'LOAD_OR_VALIDATOR_ERROR','detail':str(exc)}]},'design_validity':{'result':'未判定'},'vehicle_verification':{'result':'未実施'}}
    a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='design_validity' and k!='format_and_migration'},ensure_ascii=False))
    print(json.dumps({k:v for k,v in result['format_and_migration'].items() if k!='check_names'},ensure_ascii=False))
    return 0 if result['format_and_migration']['result']=='合格' else 1
if __name__=='__main__': sys.exit(main())
