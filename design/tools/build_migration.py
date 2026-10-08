"""Initial migration only. Never edits inputs, or overwrites an existing model.

Run using dependencies in requirements.txt. For reproducibility --out can point
to an empty staging directory. Future design work edits model.yaml, not sources.
"""
import argparse, collections, csv, hashlib, html, json, re, uuid
from pathlib import Path
from ruamel.yaml import YAML

DESIGN = Path(__file__).resolve().parents[1]
ROOT = DESIGN.parent
EXTRACT = DESIGN/'docs/extraction_20261008_01a11af4'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def readjl(name): return [json.loads(s) for s in (EXTRACT/name).read_text().splitlines()]
def stable(prefix, key): return prefix+'-'+str(uuid.uuid5(uuid.NAMESPACE_URL,'gouda-migration-v1:'+key))
def jswrite(path,obj): path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')

def schema():
    text={'type':'string','minLength':1}; nullable={'type':['string','null']}
    ref={'type':'string','minLength':1,'description':'Global ID; existence and target kind checked by validator.'}
    refs={'type':'array','items':ref,'uniqueItems':True}
    def obj(props,required=None): return {'type':'object','properties':props,'required':list(props) if required is None else required,'additionalProperties':False}
    bind=obj({'source_ref':ref,'field':text})
    fieldbindings={'type':'object','additionalProperties':bind}
    source=obj({'id':ref,'file_ref':ref,'kind':{'enum':['excel_row','intent_lines','drawio_object']},
       'locator':obj({'sheet':text,'range':text,'row':{'type':'integer','minimum':1},'page':text,'element_id':text,'line_start':{'type':'integer','minimum':1},'line_end':{'type':'integer','minimum':1}},[]),
       'raw_fields':{'type':'object','additionalProperties':{}},
       'original_status':obj({'classification':{'enum':['確定','未決','上位要求']},'raw':{'type':'string'},'basis':{'type':'string'},'locations':{'type':'array','items':{'type':'string'}}})})
    source['allOf']=[{'if':{'properties':{'kind':{'const':k}}},'then':{'properties':{'locator':{'required':required}}}} for k,required in [('excel_row',['sheet','range','row']),('intent_lines',['line_start','line_end']),('drawio_object',['page','element_id'])]]
    module=obj({'element_class':{'enum':['module','internal_component','ros_node','process','hardware','unclassified']},'state_refs':refs,'parameter_refs':refs,'failure_refs':refs,'execution_ref':ref})
    endpoint=obj({'role':{'enum':['from','to']},'source_ref':ref,'field':text,'resolved_refs':refs,'unresolved_tokens':{'type':'array','items':text}})
    iface=obj({'purpose':{'enum':['command','data','diagnostic','configuration','unclassified']},'endpoints':{'type':'array','minItems':2,'maxItems':2,'items':endpoint},'data_owner_ref':nullable})
    diagram=obj({'object_kind':{'enum':['vertex','edge','structural']},'parent_ref':nullable,'from_ref':nullable,'to_ref':nullable,'label_refs':refs,'module_match_refs':refs,'endpoint_status':{'enum':['bound','unidentified','not_applicable']}})
    issue=obj({'category':{'enum':['technical','human','source_missing']},'state':{'enum':['open','deferred','partially_superseded']},'affected_refs':dict(refs,minItems=1),'resolution_refs':refs,'question':text,'next_action':text,'options':{'type':'array','items':obj({'label':text,'effect':text})},'recommendation':text,'recommendation_basis':text},['category','state','affected_refs','resolution_refs','question','next_action'])
    issue['allOf']=[{'if':{'properties':{'category':{'const':'human'}}},'then':{'required':['options','recommendation','recommendation_basis'],'properties':{'options':{'minItems':2}}},'else':{'not':{'anyOf':[{'required':['options']},{'required':['recommendation']}]}}}]
    rec=obj({'state':{'enum':['resolved_by_intent','open']},'affected_refs':dict(refs,minItems=1),'adopted_requirement_refs':refs,'scope':text,'rationale':text,'issue_refs':refs})
    entity=obj({'id':ref,'kind':{'enum':['requirement','module','state_owner','execution','mode','transition','interface','data_contract','parameter','failure_mode','test','issue','reference','diagram_element','diagram_connection','reconciliation']},'name':text,
       'source_refs':dict(refs,minItems=1),'design_status':{'enum':['未設計','案','承認済み']},
       'adoption':{'enum':['upper_requirement','legacy_candidate','partially_superseded','superseded','unresolved','reference_only']},
       'field_bindings':fieldbindings,'related_refs':refs,'issue_refs':refs,
       'interpretation':{'type':'string'},'approval_source_ref':ref,'sensitivity':{'type':'array','items':{'enum':['safety','operation','intent']},'uniqueItems':True},
       'module':module,'interface':iface,'diagram':diagram,'issue':issue,'reconciliation':rec,
       'mode':obj({'runtime':{'type':'boolean'},'current_name':nullable}),
       'state_owner':obj({'owner_ref':ref,'state_definition':bind}),
       'execution':obj({'module_ref':ref,'ros_node_ref':nullable,'process_ref':nullable,'placement_status':{'const':'未設計'}}),
       'parameter':obj({'owner_ref':ref,'value':{'type':['number','string','boolean','null']},'value_state':{'enum':['unresolved','source_value','approved']},'unit':nullable}),
       'failure_mode':obj({'owner_ref':ref,'response_status':{'enum':['source_candidate','未設計']}}),
       'test':obj({'execution_status':{'const':'未実行'}})},['id','kind','name','source_refs','design_status','adoption','field_bindings','related_refs','issue_refs','interpretation','sensitivity'])
    payload={'module':'module','interface':'interface','diagram_element':'diagram','diagram_connection':'diagram','issue':'issue','reconciliation':'reconciliation','mode':'mode','state_owner':'state_owner','execution':'execution','parameter':'parameter','failure_mode':'failure_mode','test':'test'}
    entity['allOf']=[{'if':{'properties':{'kind':{'const':k}}},'then':{'required':[v]}} for k,v in payload.items()]
    entity['allOf'] += [{'if':{'properties':{'parameter':{'properties':{'value_state':{'const':'unresolved'}}}},'required':['parameter']},'then':{'properties':{'parameter':{'properties':{'value':{'type':'null'}}}}}}]
    result=obj({'schema_version':{'const':'1.0'},'metadata':obj({'authority_ref':ref,'scope':text,'id_policy':text,'extraction_verification_ref':ref,'design_validity':{'const':'未判定'},'vehicle_verification':{'const':'未実施'}}),
       'files':{'type':'array','items':obj({'id':ref,'path':text,'sha256':{'type':'string','pattern':'^[0-9a-f]{64}$'},'role':{'enum':['authority','source','extraction','verification']}})},
       'sources':{'type':'array','items':source},'entities':{'type':'array','items':entity},
       'migration':obj({'baseline_definition_count':{'const':198},'id_map':{'type':'array','items':obj({'legacy_id':ref,'target_ref':ref,'source_ref':ref,'baseline':{'type':'boolean'}})},'row_dispositions':{'type':'array','items':obj({'sheet':text,'row':{'type':'integer'},'disposition':{'enum':['migrated','header','vocabulary','empty']},'target_ref':nullable})}})})
    result.update({'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'urn:gouda:design-model:1.0','title':'Gouda staged lower-design model','description':'Schema validates form only. IDs, evidence, source preservation, coverage and known issues require validate_model.py. Passing is not design approval.'})
    return result

def build(out):
    out.mkdir(parents=True,exist_ok=True)
    if any((out/n).exists() for n in ['model.yaml','schema.json','migration_manifest.json']): raise SystemExit('Refusing to overwrite existing canonical artifacts. Use an empty --out directory.')
    files=[]; sources=[]; entities=[]; mapping=[]; dispositions=[]; registry={}; byid={}; rowmap={}; sourcebyid={}
    filepaths=[('FILE-INTENT',DESIGN/'intent.md','authority'),('FILE-XLSX',DESIGN/'docs/Gouda_architecture_detail.xlsx','source'),('FILE-DRAWIO',DESIGN/'docs/SystemArchitecture.drawio','source'),('FILE-ROWS',EXTRACT/'excel_rows.jsonl','extraction'),('FILE-IDS',EXTRACT/'excel_ids.csv','extraction'),('FILE-DRAW-EXTRACT',EXTRACT/'drawio_objects.jsonl','extraction'),('FILE-EXTRACT-VERIFY',EXTRACT/'verification.json','verification')]
    for i,p,role in filepaths: files.append(dict(id=i,path=str(p.relative_to(ROOT)),sha256=sha(p),role=role))
    # Capture all read-only input artifacts, not just the seven actively referenced files.
    protected=[DESIGN/'intent.md',DESIGN/'docs/Gouda_architecture_detail.xlsx',DESIGN/'docs/SystemArchitecture.drawio']+sorted(p for p in EXTRACT.rglob('*') if p.is_file())
    manifest={'protected_files':{str(p.relative_to(ROOT)):sha(p) for p in protected},'id_registry':registry,'source_repository_head':'a091ed39eb154b2dff7065840dc13c6478b153da'}
    def addsource(s): sources.append(s); sourcebyid[s['id']]=s; return s['id']
    def entity(i,k,name,src,adoption='legacy_candidate',status='案',bindings=None):
        e=dict(id=i,kind=k,name=name or i,source_refs=list(src),design_status=status,adoption=adoption,field_bindings=bindings or {},related_refs=[],issue_refs=[],interpretation='',sensitivity=[])
        assert i not in byid,i
        byid[i]=e; entities.append(e); return e
    def binding(s,f): return {'source_ref':s,'field':f}
    def bindrow(s,row): return {re.sub(r'\d','',k):binding(s,k) for k in row['values']}
    intent=(DESIGN/'intent.md').read_text().splitlines()
    # Stable IDs allocated once, persisted in registry; future editing never renumbers.
    reqbyline={}
    headings={'達成したい体験：','設計において優先する順序:','基本契約','役割分担:','設計する順序：','避けてほしいこと：','設計規約：','個別の要求仕様：','・デバッグ性の受入条件','・交換性の受入条件'}
    for line,raw in enumerate(intent,1):
        if not raw.strip() or raw.strip().startswith('#') or raw.strip() in headings: continue
        i=f'RQ-I{len(reqbyline)+1:03}'; s=f'SRC-I{line:03}'; reqbyline[line]=i; registry[f'intent:line:{line}']=i
        addsource(dict(id=s,file_ref='FILE-INTENT',kind='intent_lines',locator={'line_start':line,'line_end':line},raw_fields={'text':raw},original_status={'classification':'上位要求','raw':'','basis':'最新intent.mdを上位要求とする今回指示','locations':[f'intent.md:{line}']}))
        e=entity(i,'requirement',f'intent.md:{line}',[s],'upper_requirement','未設計',{'statement':binding(s,'text')}); e['sensitivity']=['intent']
    def reqs(lines): return [reqbyline[n] for n in lines]
    rows=readjl('excel_rows.jsonl')
    baseline=list(csv.DictReader((EXTRACT/'excel_ids.csv').open(encoding='utf-8-sig')))
    baseline={(r['sheet'],r['cell']):r['id'] for r in baseline if r['role']=='definition'}
    kindmap={'モジュール定義':'module','インターフェース定義':'interface','命名規則':'requirement','使用モード定義':'mode','基本仕様':'requirement','データ契約':'data_contract','状態遷移':'transition','使用・開発検証':'test','未決事項':'issue','参照・変更記録':'reference'}
    sheetnums={s['name']:i+1 for i,s in enumerate(json.loads((EXTRACT/'excel_sheets.json').read_text()))}
    for r in rows:
        sn=r['sheet']; rn=r['row']; vals=r['values']; disp='migrated'
        if rn==1: disp='header'
        elif sn=='選択肢': disp='vocabulary'
        elif not any(v not in (None,'') for v in vals.values()): disp='empty'
        if disp!='migrated': dispositions.append(dict(sheet=sn,row=rn,disposition=disp,target_ref=None)); continue
        s=f'SRC-X{sheetnums[sn]:02}-{rn:04}'
        # Source range uses the complete original stored row width.
        end=r['cell_ids'][-1]
        addsource(dict(id=s,file_ref='FILE-XLSX',kind='excel_row',locator={'sheet':sn,'row':rn,'range':f'A{rn}:{end}'},raw_fields=vals.copy(),original_status={'classification':r['status'],'raw':r['status_raw'],'basis':r['status_basis'],'locations':r['status_source']}))
        aid=vals.get(f'A{rn}',''); isold=bool(re.fullmatch(r'(?:M|IF|S|D|ST|T|Q|REF|CH)-\d+',aid or ''))
        i=aid if isold else ('M-039' if sn=='モジュール定義' else f'LEG-{sheetnums[sn]:02}-{rn:04}')
        if not isold: registry[f'excel:{sn}:{rn}']=i
        k=kindmap[sn]; name=vals.get(f'B{rn}') if isold or k=='module' else vals.get(f'A{rn}')
        e=entity(i,k,name,[s],bindings=bindrow(s,r)); rowmap[i]=r
        if isold: mapping.append(dict(legacy_id=i,target_ref=i,source_ref=s,baseline=(sn,f'A{rn}') in baseline))
        dispositions.append(dict(sheet=sn,row=rn,disposition=disp,target_ref=i))
        if k=='mode': e['mode']={'runtime':False,'current_name':None}; e['adoption']='reference_only'; e['interpretation']='旧資料のモード記載。現在のruntime modeではない。'
        if k=='test': e['test']={'execution_status':'未実行'}
        if k=='module':
            e['module']={'element_class':'unclassified','state_refs':[],'parameter_refs':[],'failure_refs':[],'execution_ref':'EX-'+i}
            for col,kind,prefix,property_name in [('L','state_owner','OWN','state_refs'),('M','parameter','PAR','parameter_refs'),('P','failure_mode','FM','failure_refs')]:
                if vals.get(f'{col}{rn}') not in ('',None):
                    child=entity(prefix+'-'+i,kind,name+' / '+{'L':'保持状態','M':'パラメータ群','P':'異常時動作'}[col],[s],bindings={'source_definition':binding(s,f'{col}{rn}')})
                    registry[f'excel:{sn}:{rn}:{col}']=child['id']; e['module'][property_name].append(child['id']); e['field_bindings'].pop(col,None)
                    child['related_refs']=[i]
                    if kind=='state_owner': child[kind]={'owner_ref':i,'state_definition':binding(s,f'{col}{rn}')}
                    if kind=='parameter': child[kind]={'owner_ref':i,'value':None,'value_state':'unresolved','unit':None}; child['design_status']='未設計'; child['interpretation']='原資料のパラメータ群。個別キー・型・値への分解は次の下位設計。nullは未確定で、0ではない。'
                    if kind=='failure_mode': child[kind]={'owner_ref':i,'response_status':'source_candidate'}
            ex=entity('EX-'+i,'execution',name+' / 実行配置',[s],status='未設計',bindings={c:e['field_bindings'].pop(c) for c in ('D','E','H','T') if c in e['field_bindings']})
            ex['execution']={'module_ref':i,'ros_node_ref':None,'process_ref':None,'placement_status':'未設計'}
            ex['interpretation']='原文の種別・実装場所・使用モード・起動条件を保持。Node分割とprocess配置は未設計。'
            registry[f'execution:{i}']=ex['id']
    # Interface endpoints: only byte-exact names separated by semicolons are bound.
    names=collections.defaultdict(list)
    for e in entities:
        if e['kind']=='module': names[e['name']].append(e['id'])
    command=set(range(17,18))|set(range(19,33))
    diagnostics={10,18,34,36,37,38,45}
    for e in list(entities):
        if e['kind']!='interface': continue
        n=int(e['id'].split('-')[1]); purpose='command' if n in command else 'diagnostic' if n in diagnostics else 'configuration' if n in (9,42) else 'data'
        r=rowmap[e['id']]; endpoints=[]
        for c,role in [('B','from'),('C','to')]:
            tokens=[x.strip() for x in r['values'][f'{c}{r["row"]}'].split(';')]
            endpoints.append(dict(role=role,source_ref=e['source_refs'][0],field=f'{c}{r["row"]}',resolved_refs=[names[t][0] for t in tokens if len(names[t])==1],unresolved_tokens=[t for t in tokens if len(names[t])!=1]))
        e['interface']={'purpose':purpose,'endpoints':endpoints,'data_owner_ref':None}
        e['interpretation']='用途は原文の意味に基づく移行分類。送受信名の完全一致のみ参照化。データ所有者・総称/別名の対応は未設計。'
    # Preserve every drawio object. No heuristic endpoint completion.
    draws=readjl('drawio_objects.jsonl'); dgids={d['id']:stable('DG',d['page_id']+':'+d['id']) for d in draws}
    for d in draws:
        i=dgids[d['id']]; s='SRC-'+i; registry[f'drawio:{d["page_id"]}:{d["id"]}']=i
        raw={k:d[k] for k in ('value_raw','attributes','wrapper_attributes','geometry_xml','parent','source','target')}
        addsource(dict(id=s,file_ref='FILE-DRAWIO',kind='drawio_object',locator={'page':d['page_id'],'element_id':d['id']},raw_fields=raw,original_status={'classification':d['status'],'raw':d['status_raw'],'basis':d['status_basis'],'locations':[]}))
        e=entity(i,'diagram_connection' if d['kind']=='edge' else 'diagram_element',d['value_raw'] or d['id'],[s],'reference_only','未設計',{'label':binding(s,'value_raw')})
        label=html.unescape(re.sub('<[^>]*>','',d['value_raw'])).strip()
        e['diagram']={'object_kind':d['kind'],'parent_ref':dgids.get(d['parent']),'from_ref':dgids.get(d['source']),'to_ref':dgids.get(d['target']),'label_refs':[dgids[x] for x in d.get('label_ids',[])],'module_match_refs':names.get(label,[]),'endpoint_status':'unidentified' if d['kind']=='edge' and (d['source'] is None or d['target'] is None) else 'bound' if d['kind']=='edge' else 'not_applicable'}
        e['interpretation']='図示の記録。HTML除去後の名称完全一致は対応候補のみ。実行必須IFやNode配置の承認にはしない。'
    # Four current software modes directly trace to the authority; no fifth mode.
    for i,name in [('MODE-AUTO','自律走行'),('MODE-MAP','事前地図作成'),('MODE-PAUSE','一時停止'),('MODE-MANUAL','手動走行')]:
        e=entity(i,'mode',name,byid[reqbyline[93]]['source_refs'],'upper_requirement','未設計'); e['mode']={'runtime':True,'current_name':name}; e['related_refs']=reqs([92,93,94]); e['interpretation']='intent列挙値の移行。起動直後の手動操縦表記は同一モードの表現として保持。'; registry[i]=i
    def allsrc(ids): return list(dict.fromkeys(s for i in ids for s in byid[i]['source_refs']))
    def problem(i,name,cat,affected,question,action,options=None,recommendation=None,state='open'):
        e=entity(i,'issue',name,allsrc(affected),'unresolved','未設計')
        e['issue']=dict(category=cat,state=state,affected_refs=affected,resolution_refs=[],question=question,next_action=action)
        if cat=='human':
            e['issue'].update(options=[dict(label=a,effect=b) for a,b in options],recommendation=recommendation,recommendation_basis='上位要求を変えず、未確認の運用・実車値を推測しないための未採用案。')
        for a in affected:
            if i not in byid[a]['issue_refs']: byid[a]['issue_refs'].append(i)
        return e
    def conflict(i,name,affected,lines,scope,state='resolved_by_intent',issue=None):
        targets=reqs(lines); e=entity(i,'reconciliation',name,allsrc(affected+targets),'reference_only','未設計')
        e['reconciliation']=dict(state=state,affected_refs=affected,adopted_requirement_refs=targets,scope=scope,rationale='最新intent.mdを上位要求とする。旧原文は出典に保持し、記載の影響範囲だけを置換。' if state=='resolved_by_intent' else '資料間の衝突は上位要求だけで一意に解消できない。',issue_refs=[issue] if issue else [])
        for a in affected:
            byid[a]['related_refs'].append(i)
            if byid[a]['kind']!='issue': byid[a]['adoption']='partially_superseded' if state=='resolved_by_intent' else 'unresolved'
        return e
    conflict('C-001','ソフトモードの集合',['LEG-05-0003','LEG-05-0005','M-001','M-002','M-005','M-010','S-05','D-06','D-07','ST-01','ST-20','Q-10'],[36,92,93,94],'旧map_editをruntime modeとして採用しない。一時停止を4モードの一つとして管理。内部状態との対応は未設計。')
    conflict('C-002','区間属性の帰属',['S-08','D-03','M-010','M-037'],[13],'前点から当該点へのincoming属性の旧案を、waypoint i→i+1の区間属性へ置換。初回進入の詳細は未設計。')
    conflict('C-003','境界速度の保証',['S-13','D-16','IF-022','T-12','M-012'],[13,26,90],'進入区間の上限を境界で適用。境界時の実速度上限以下の保証は要求しない。cmd_vel後段の独自速度制限を追加しない。旧制御器の飽和・変換特性など既存保護全体を削除する意味ではない。')
    conflict('C-004','通過判定の所有者',['S-14','D-09','ST-04','ST-17','T-14','Q-08','M-037','M-039'],[14,25,82],'通過・到達判定はNav2。Gouda独自の幾何判定・通過証拠による再判定を現在契約として採用しない。進捗保持やイベント順序は別途設計。')
    conflict('C-005','Nav2の後退と再計画',['S-17','M-011','IF-020','REF-05','ST-09','ST-10'],[15,24,25],'無断後退・自動retryを一律に外す旧案から、Nav2 BTによる後退・再計画へ置換。BT失敗後は一時停止。Goudaで二重実行しない。')
    conflict('C-006','異常後の自動復帰',['D-22','ST-11','ST-12','M-007','M-037','T-21','Q-10'],[16,17,36,92,97],'プロセス再起動→必要状態復元→旧goal終了/破棄確認→自律復帰の場合だけ指令再許可。人の追加承認不要。PC再起動、人のpause/end後は別の復帰規則を適用。')
    conflict('C-007','最終点後の扱い',['S-15','ST-14','T-24','M-037'],[19,21,95],'最終点で自動終了せず停止して一時停止。再開時も最終waypointを目指す。人の終了操作まで自律走行を終了しない。')
    conflict('C-008','Bluetooth入力途絶',['S-04','M-025','Q-09','T-18'],[34,35,91,96],'Bluetooth断時追加処理なしという旧記載を採用要件にしない。現在採用している指令源の入力途絶時はESP32が中立。既存実装の成立は未確認のまま。')
    conflict('C-009','ログとrosbagの操作と保存',['M-016','M-017','IF-038','IF-039','IF-040','D-24','T-23','Q-10'],[8,19,20,21],'ログとrosbagを独立操作。ログ自動開始は人の地図作成開始/自律開始のみ。復帰/再開では自動開始しない。手動開始記録は自動停止しない。記録失敗で走行停止しない。')
    conflict('C-010','開始操作と準備',['S-06','ST-02','ST-03','M-002','M-007'],[14],'初期姿勢指定後に開始を一度押し、推定しながらNav2開始。開始後の追加承認を挟まない。必要条件の内部処理は未設計。')
    conflict('C-011','地図変換と成果物同一性',['M-005','M-006','M-009','D-01','D-02','IF-011','IF-012','IF-013','IF-015','IF-016'],[11,12,13],'地図終了時に自動変換。由来IDを共有し各成果物は独立ハッシュと版。waypointは変換後地図のID/版/ハッシュを参照し独立保存。失敗時は原図保持、不完全変換成果物破棄。')
    conflict('C-012','Navigation実行主体',['M-039','D-08','IF-019','IF-020',dgids['2TSgiu6-nVzXwyzMdGmE-24'],dgids['2TSgiu6-nVzXwyzMdGmE-25']],[14,24,25,80,82],'Gouda section executor/progress trackerを独立した二重実行/判定主体として採用しない。薄いadapterの要否や標準IFとの対応は次段階。')
    conflict('C-013','waypoint UIの配置',['M-010','M-002','M-018'],[64],'waypoint_manager GUIはgouda_monitor内。画面転送は禁止。地図作成中のRViz表示要求は保持。')
    # Legacy issue IDs retained, responsibility assigned without promoting all unspecified facts to human decisions.
    qtypes={'Q-01':'technical','Q-02':'technical','Q-03':'source_missing','Q-04':'human','Q-05':'human','Q-06':'human','Q-07':'human','Q-08':'technical','Q-09':'source_missing','Q-10':'human','Q-11':'technical','Q-12':'human','Q-13':'technical'}
    questions={
      'Q-04':('検出対象・取付条件・走行面をどの実車条件で評価するか。',[('実車の対象と条件を指定する','指定された条件をそのまま評価計画へ反映'),('後工程まで未確定とする','実車での検出範囲の合否判定を保留')],'実車の対象と条件を指定する'),
      'Q-05':('実車の周期・watchdog・timeout等の値と試験条件をどう決定するか。',[('実測資料と試験条件で決める','既存値の根拠を確認し、人が採用値を決定'),('実車値の確定を保留する','型・設定経路の下位設計は進め、値依存の実車確認は未判定')],'実測資料と試験条件で決める'),
      'Q-06':('車体形状・上限速度等の実車値と、走行対象の未知領域方針をどう指定するか。',[('実車値と運用条件を指定する','Nav2設定に反映。独自通過判定は作らない'),('対象環境・値の確定を保留する','Nav2設定値と実車合否は未判定')],'実車値と運用条件を指定する'),
      'Q-07':('旧資料の指定線方式を今回も必要とし、どの範囲の迂回を認めるか。',[('Nav2での実現案と運用差を次段階で比較する','人が追従/迂回の方針を判断するまで旧案は非採用候補'),('旧二方式の運用要求を維持すると明示する','許容範囲・追従優先度を人が追加指定する必要がある')],'Nav2での実現案と運用差を次段階で比較する'),
      'Q-10':('最新intentで決まったmode/復帰/最終点以外に、monitor断時の走行継続方針をどうするか。',[('旧案の走行継続を採用する','表示断自体は停止契機にせず再接続時に状態取得'),('monitor断を一時停止契機とする','基本契約の追加・運用変更として人の明示決定が必要')],'旧案の走行継続を採用する'),
      'Q-12':('旧5 mはNav2設定に残す要求か、迂回領域等の別要求か。',[('5 mの用途を保留してNav2設定案で再確認する','一般的な既定値で補わず、独自通過判定も追加しない'),('用途を人が明示する','Nav2で表せる設定/運用要求として設計可能か次段階で確認')],'5 mの用途を保留してNav2設定案で再確認する')}
    for q,cat in qtypes.items():
        e=byid[q]; related=[x['id'] for x in entities if x['id']!=q and x['kind'] not in ('issue','reconciliation') and any(q in str(sourcebyid[s]['raw_fields']) for s in x['source_refs'])]
        if not related: related=reqs([1])
        e['adoption']='unresolved'; e['design_status']='未設計'
        e['issue']=dict(category=cat,state='partially_superseded' if q in ('Q-08','Q-09','Q-10') else 'deferred' if q=='Q-13' else 'open',affected_refs=related,resolution_refs=[x['id'] for x in entities if x['kind']=='reconciliation' and q in x['reconciliation']['affected_refs']],question=questions[q][0] if q in questions else e['name'],next_action={'technical':'次の下位設計で、上位要求に従い技術案・標準IF・構成を具体化する。','human':'選択肢と影響IDを確認し、運用方針・実車値を人が決定する。','source_missing':'原資料・既存通信仕様・実車記録を確認する。移行時点では推定しない。'}[cat])
        if cat=='human': e['issue'].update(options=[dict(label=a,effect=b) for a,b in questions[q][1]],recommendation=questions[q][2],recommendation_basis='未採用の判断材料。最新intentの決定済み事項を再承認にはしない。')
        for a in related:
            if q not in byid[a]['issue_refs']: byid[a]['issue_refs'].append(q)
    problem('H-001','SpeedLimit発行手段の承認','human',reqs([26,27])+['IF-022','D-16','M-011'],'採用Nav2版に対応する発行手段をどれにするか。','AIが次段階で版適合を調べて比較し、人が承認する。',[('Speed Filter','この経路を単一発行元にする案。採用版・区間対応・設定負担の調査が必要'),('Route Server','この経路を単一発行元にする案。採用版・区間対応・設定負担の調査が必要'),('Gouda側発行器','Goudaが標準SpeedLimitを単一発行する案。責務と実装負担の比較が必要')],'採用版で3案を比較してから承認する。現段階で方式を選ぶ根拠は不足しており、推奨方式自体は未定。')
    # The new recovery-attempt limit has no supplied value. It belongs with
    # human operational/vehicle values, not an invented technical default.
    byid['Q-05']['issue']['affected_refs']+=reqs([16])
    byid['Q-05']['source_refs']=list(dict.fromkeys(byid['Q-05']['source_refs']+allsrc(reqs([16]))))
    byid['Q-05']['issue']['question']='実車の周期・watchdog・timeout等の値、復旧試行回数の上限、試験条件をどう決定するか。'
    byid[reqbyline[16]]['issue_refs'].append('Q-05')
    problem('G-ARCH','Node・process・状態所有・IF契約の具体化','technical',[e['id'] for e in entities if e['kind'] in ('module','execution','state_owner','interface','data_contract')],'旧候補を現在要求へ適合させる下位設計が未実施。','責務、標準IF、所有者、配置、QoS、時刻を次段階で設計。資料の確定明示なしは人の承認待ちにしない。')
    problem('G-PARAM','パラメータ群の分解と型・単位','technical',[e['id'] for e in entities if e['kind']=='parameter'],'パラメータ群は原文参照で移行し、個別型・キー・単位・設定所有者は未設計。','技術的な分解はAIが行う。実車採用値・試験条件はQ-03〜Q-06。')
    problem('G-RECOVERY','復旧・故障応答・内部状態の設計','technical',reqs([16,36,92,97])+[e['id'] for e in entities if e['kind'] in ('transition','failure_mode')],'最新の復旧順序と故障別復帰先に対応する下位設計は未実施。','必要状態だけの復元・旧goal処理を次段階で具体化。人の追加承認や新モードを追加しない。')
    problem('G-TEST','旧試験の現要求への対応と新要求の試験','technical',[e['id'] for e in entities if e['kind']=='test'],'旧試験はすべて未実行で、旧期待値を含む。','置換対応を参照して次段階で試験を設計。今回の検査器試験と区別する。')
    problem('G-LOG','ログ・rosbagの責務と記録状態','technical',reqs([8,19,20,21])+['M-016','M-017','IF-038','IF-040'],'独立した記録操作・自動開始条件・欠落追跡の具体IFと状態所有者が不足。','最新要求の範囲内で次段階に設計。復帰時の無断自動Recordを追加しない。')
    problem('G-GRAPH','図の要素とモデルIFの対応','technical',[e['id'] for e in entities if e['kind'].startswith('diagram_')],'図中の枠・注記・内部構成・接続を、承認済みNode/IFと同一視できない。','原IDを保ちながら次段階で責務境界を整理。名称一致以外の自動統合をしない。')
    problem('G-ENDPOINT','IFの総称・表記揺れ・所有者','technical',[e['id'] for e in entities if e['kind']=='interface' and any(x['unresolved_tokens'] for x in e['interface']['endpoints'])],'logger、Navigation内境界、PC構成node、safety_gouda_safety_supervisor等の具体参照が未解決。','原文を保持し次の下位設計で対応付け。誤記と推測して黙って修正しない。')
    problem('U-DRAW-001','接続先IDなしの線','source_missing',[dgids['2TSgiu6-nVzXwyzMdGmE-18']],'targetPointはあるがtarget IDがない。接続先未特定。','図の意図を示す資料で確認。source/controllerやcmd_velラベルから接続先を推測しない。')
    problem('U-DRAW-002','非常停止検知線と取得不能記載','source_missing',['M-028','IF-032','CH-02',dgids['x5bDQh8FaZrcMh8EckeY-164']],'図のESP32押下検知線とExcelの取得不能記載が衝突する。','現物回路・既存実装資料で確認するまで検知機能を採用済みにしない。')
    problem('U-DRAW-003','heartbeat必須性と衝突停止線','source_missing',['M-013','M-023','M-012','CH-02',dgids['x5bDQh8FaZrcMh8EckeY-40'],dgids['x5bDQh8FaZrcMh8EckeY-163']],'図のheartbeat_and_status/collision_stop_requestとExcelの任意/未提供記載の対応が未確認。','原資料で現状/構想を確認。図の線を必須監視や実装済み機能へ昇格しない。')
    problem('U-HISTORY','変更記録と現在図の時点差','source_missing',['CH-02','M-008','M-037',dgids['4S4QAY9o3vVNfXHAsMHo-1'],dgids['2TSgiu6-nVzXwyzMdGmE-4']],'CH-02はlocal_odometry/mission_managerが図に未記載とするが、現在図には両ラベルが存在する。','CH-02を旧時点の記録として保持。図の追加時期・変更履歴は未確認。')
    conflict('C-014','非常停止検知の資料間衝突',['M-028','IF-032',dgids['x5bDQh8FaZrcMh8EckeY-164']],[],'取得可否は資料だけで統合しない。',state='open',issue='U-DRAW-002')
    conflict('C-015','heartbeatとcollision_stopの資料間衝突',['M-013','M-023',dgids['x5bDQh8FaZrcMh8EckeY-40'],dgids['x5bDQh8FaZrcMh8EckeY-163']],[],'実行必須性・実装有無を保留。',state='open',issue='U-DRAW-003')
    conflict('C-016','変更記録の時点差',['CH-02',dgids['4S4QAY9o3vVNfXHAsMHo-1'],dgids['2TSgiu6-nVzXwyzMdGmE-4']],[],'現在図に存在するという観察と旧履歴を別に保持。',state='open',issue='U-HISTORY')
    # Link legacy Q references as actual IDs, without copying their decision text.
    for e in entities:
        raw='\n'.join(str(sourcebyid[s]['raw_fields']) for s in e['source_refs'])
        for q in sorted(set(re.findall(r'\bQ-\d{2}\b',raw))):
            if q in byid and q!=e['id'] and q not in e['related_refs']: e['related_refs'].append(q)
        if e['kind'] in ('module','interface','failure_mode','transition') and re.search('停止|中立|速度|異常|watchdog',raw): e['sensitivity']=['safety','operation']
    # Derived views never bypass the owner's replacement scope. Keep one
    # reconciliation record, and link to it instead of copying its wording.
    for e in entities:
        if e['kind'] in ('state_owner','parameter','failure_mode','execution'):
            owner=e[e['kind']].get('owner_ref',e[e['kind']].get('module_ref'))
            inherited=[ref for ref in byid[owner]['related_refs'] if byid[ref]['kind']=='reconciliation']
            e['related_refs']=list(dict.fromkeys(e['related_refs']+inherited))
            if inherited: e['adoption']=byid[owner]['adoption']
    model={'schema_version':'1.0','metadata':dict(authority_ref='FILE-INTENT',scope='スキーマ・既存資料移行・出典・矛盾整理・移行検査のみ。新規下位設計、ROS実装、完成図表は対象外。',id_policy='既存IDを保持。新IDは今回割当てたregistryを固定し、位置変更や名称変更で再採番しない。',extraction_verification_ref='FILE-EXTRACT-VERIFY',design_validity='未判定',vehicle_verification='未実施'),'files':files,'sources':sources,'entities':entities,'migration':{'baseline_definition_count':198,'id_map':mapping,'row_dispositions':dispositions}}
    manifest['baseline_ids']=sorted(r['legacy_id'] for r in mapping if r['baseline'])
    manifest['additional_legacy_ids']=sorted(r['legacy_id'] for r in mapping if not r['baseline'])
    manifest['entity_ids']=[e['id'] for e in entities]
    manifest['source_ids']=[s['id'] for s in sources]
    manifest['known_issue_ids']=[e['id'] for e in entities if e['kind']=='issue']
    manifest['intent_requirement_lines']=reqbyline
    manifest['kind_counts']=dict(collections.Counter(e['kind'] for e in entities))
    y=YAML(typ='rt'); y.allow_unicode=True; y.width=110; y.indent(mapping=2,sequence=4,offset=2)
    with (out/'model.yaml').open('w') as f: y.dump(model,f)
    jswrite(out/'schema.json',schema()); jswrite(out/'migration_manifest.json',manifest)
    print(json.dumps({'entities':len(entities),'sources':len(sources),'legacy_ids':len(mapping),'issues':manifest['known_issue_ids'],'kinds':manifest['kind_counts']},ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--out',type=Path,default=DESIGN); args=p.parse_args(); build(args.out)
