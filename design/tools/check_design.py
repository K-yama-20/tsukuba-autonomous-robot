"""Design-consistency check of the lower-design proposal (separate from fidelity).

Every rule names its basis (an upper requirement RQ-Ixxx from intent.md, or a
design rule from the work instruction / CLAUDE.md). Results are three-valued per
rule: 合格 / 違反 / 未判定. 未判定 carries the reason and the issue that resolves
it. Passing is not design approval, ROS verification or vehicle verification.
"""
import argparse, collections, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_model import core, load_yaml, current_line_map, DESIGN  # noqa: E402

DESIGNED = ('ros_node', 'designed_interface')
ESTOP = re.compile(r'非常停止|非常押し|e-?stop|emergency|押下検知|緊急停止', re.I)
REQUIRED_EVENTS = {'start': '開始', 'pause': '一時停止', 'resume': '再開', 'end': '終了', 'goal_reached': 'ゴール到達', 'fault_recovery': '個別異常の復帰', 'pc_restart': 'PC再起動'}
HUMAN_ONLY_EVENTS = {'start', 'pause', 'resume', 'end', 'map_start', 'map_end'}
# Scope of this stage: user experience, navigation, basic contracts, individual requirements (intent.md lines).
SCOPE_LINES = list(range(6, 22)) + [24, 25, 26, 27] + list(range(34, 39)) + list(range(90, 101))
CONTRACT_LINES = {34: '手動優先', 37: '人による一時停止操作', 96: '採用中の指令源途絶時のESP32中立化', 35: 'gamepad途絶時のESP32中立', 91: 'PC指令途絶時の中立'}

RULES = [
    ('DR-01', '参照切れ・型不一致がない', '依頼5「参照切れ」、CLAUDE.md 1.8（IDと参照関係）'),
    ('DR-02', '所有者不明がない（IFのデータ所有者、状態の所有者、TFの単独所有）', 'RQ-I059（intent.md:84 IFにデータの所有者を定義）、RQ-I058（intent.md:83 同じTFを複数nodeから発行しない）'),
    ('DR-03', 'モード内の発行者競合がない（指令・データtopicとTF）', 'RQ-I004（intent.md:7 競合する推定器・TF発行者は同時に有効化しない）、RQ-I020（intent.md:26 SpeedLimitは単一の発行元）'),
    ('DR-04', '状態遷移の整合（4モード、起動既定、到達可能性、必須イベント、自律開始は人の操作のみ）', 'RQ-I065（intent.md:93）、RQ-I066（intent.md:94）、RQ-I025（intent.md:36）、RQ-I064（intent.md:92）、依頼4の7イベント'),
    ('DR-05', '要求の対応漏れがない（対象範囲の上位要求が設計要素または問題に対応付く）', '依頼5「要求の対応漏れ」、RQ-I061（intent.md:86 機械可読モデルで管理）'),
    ('DR-06', '非常停止検知・PC側非常停止機構を設計要素に含めない', 'RQ-I072（intent.md:100）'),
    ('DR-07', '未確認の境界要素を利用可能な機能として設計に使わない', '依頼2「回答があるまでは未確認とし、利用可能な機能として設計に使わない」'),
    ('DR-08', '既存契約（手動優先・人の一時停止操作・ESP32の中立化）を維持し参照している', 'RQ-I023（intent.md:34）、RQ-I026（intent.md:37）、RQ-I068（intent.md:96）、RQ-I024（intent.md:35）、RQ-I063（intent.md:91）'),
    ('DR-09', '新しいモード・保護・承認操作を追加していない', 'RQ-I065（4モードのみ）、RQ-I027（intent.md:38 保護を独断で増やさない）、RQ-I011（intent.md:14 追加の承認を挟まない）'),
    ('DR-10', '版依存IFを確定扱いしていない', 'RQ-I021（intent.md:27）、依頼4「版に依存するIFは…確認できるまで確定しない」'),
    ('DR-11', '実車値・未確定値を一般値で埋めていない', 'RQ-I060（intent.md:85）、CLAUDE.md 1.5、依頼4「実車値を一般的な値で埋めない」'),
    ('DR-12', '旧設計候補を自動採用せず、行全体の破棄・承認をしていない', '依頼3・4、CLAUDE.md 1.8（確定／設計案／提案／未解決の区別）'),
    ('DR-13', '旧値の5 mを流用していない', '依頼4「旧値の5 mを流用しない」'),
    ('DR-14', '人の判断・資料不足の問題はすべて判断台帳に項目がある', 'RQ-I073（intent.md:87 決定は全て判断台帳に記録せよ。旧Qで台帳項目がないものも記録対象）'),
    ('DR-15', '設定値は正本で一度だけ宣言され、生成物と一致し、コードにハードコードされていない', 'RQ-I076（intent.md:103 実測値はプログラムにハードコードせず、宣言的に書く）、RQ-I058（intent.md:83 設定はROS parameterで行う）'),
]


def designed_entities(model):
    return [e for e in model['entities'] if e['kind'] in DESIGNED or (e['kind'] == 'transition' and 'transition' in e) or (e['kind'] == 'state_owner' and 'state_items' in e['state_owner']) or (e['kind'] == 'parameter' and e.get('revision_ref'))]


def run(model, schema, manifest):
    ents = {e['id']: e for e in model['entities']}
    sources = {s['id']: s for s in model['sources']}
    results = {}
    def result(rule, violations, undetermined=None):
        undetermined = undetermined or []
        results[rule] = {'result': '違反' if violations else '未判定' if undetermined else '合格', 'violations': violations, 'undetermined': undetermined}
    nodes = {e['id']: e for e in model['entities'] if e['kind'] == 'ros_node'}
    ifs = {e['id']: e for e in model['entities'] if e['kind'] == 'designed_interface'}
    modes = {e['id']: e for e in model['entities'] if e['kind'] == 'mode' and e['mode']['runtime']}
    trans = [e for e in model['entities'] if e['kind'] == 'transition' and 'transition' in e]
    designed = designed_entities(model)
    # DR-01
    findings, _ = core(model, schema)
    result('DR-01', [f'{f["code"]} {f["path"]}: {f["detail"]}' for f in findings])
    if findings and any(f['code'] == 'SCHEMA' for f in findings):
        for r, _, _ in RULES[1:]: result(r, [], ['スキーマ違反のため未判定'])
        return results
    # DR-02 owners
    v = []
    for i, e in ifs.items():
        d = e['designed_interface']
        if d['owner_ref'] is None and not (d['purpose'] in ('diagnostic', 'configuration') and len(d['publisher_refs']) >= 2):
            v.append(f'{i}: owner_ref が null（共有診断/設定topic以外は所有者が必要）')
        if d['transport'] == 'tf' and d['owner_ref'] is None: v.append(f'{i}: TF に所有者がない')
    for i, n in nodes.items():
        for s in n['ros_node']['owned_state_refs']:
            if ents.get(s, {}).get('state_owner', {}).get('owner_ref') != i: v.append(f'{i}: owned_state {s} の owner_ref が一致しない')
    for e in model['entities']:
        if e['kind'] == 'state_owner' and 'state_items' in e['state_owner']:
            o = ents.get(e['state_owner']['owner_ref'])
            if not o or o['kind'] != 'ros_node': v.append(f'{e["id"]}: 所有者が ros_node ではない')
            elif e['id'] not in o['ros_node']['owned_state_refs']: v.append(f'{e["id"]}: 所有者 {o["id"]} が owned_state_refs に列挙していない')
    result('DR-02', v)
    # DR-03 publisher conflicts per mode
    v = []
    for i, e in ifs.items():
        d = e['designed_interface']
        if d['transport'] not in ('topic', 'tf') or d['purpose'] not in ('command', 'data'): continue
        for m in modes:
            active = [p for p in d['publisher_refs'] if p in nodes and m in nodes[p]['ros_node']['active_in_mode_refs']]
            if len(active) > 1: v.append(f'{i} ({d["name"]}): モード {m} で複数の発行者 {active}')
    tf_frames = collections.defaultdict(list)
    for i, e in ifs.items():
        if e['designed_interface']['transport'] == 'tf': tf_frames[e['designed_interface']['frame']].append(i)
    result('DR-03', v)
    # DR-04 transitions
    v = []; u = []
    if len(modes) != 4: v.append(f'runtime mode が {len(modes)} 件（4件でなければならない）')
    boots = [t for t in trans if t['transition']['event_class'] == 'boot']
    if len(boots) != 1 or boots[0]['transition']['to_mode_ref'] != 'MODE-MANUAL' or boots[0]['transition']['from_mode_ref'] is not None: v.append('起動遷移は1件で手動走行へ入らなければならない（RQ-I066）')
    reach = set(); frontier = [t['transition']['to_mode_ref'] for t in trans if t['transition']['from_mode_ref'] is None]
    while frontier:
        m = frontier.pop()
        if m in reach: continue
        reach.add(m); frontier += [t['transition']['to_mode_ref'] for t in trans if t['transition']['from_mode_ref'] == m]
    for m in modes:
        if m not in reach: v.append(f'{m} に到達する遷移がない')
        if not any(t['transition']['from_mode_ref'] == m and t['transition']['to_mode_ref'] != m for t in trans): v.append(f'{m} から出る遷移がない')
        if not any(t['transition']['event_class'] == 'fault_recovery' and t['transition']['from_mode_ref'] == m for t in trans): v.append(f'{m} の個別異常復帰（RQ-I064）がない')
    present = {t['transition']['event_class'] for t in trans}
    for ev, label in REQUIRED_EVENTS.items():
        if ev not in present: v.append(f'必須イベント {label}（{ev}）の遷移がない')
    for t in trans:
        tr = t['transition']
        if tr['to_mode_ref'] == 'MODE-AUTO' and tr['from_mode_ref'] != 'MODE-AUTO' and tr['trigger_kind'] != 'human': v.append(f'{t["id"]}: 自律走行への遷移が人の操作ではない（RQ-I025）')
        if tr['from_mode_ref'] is not None and tr['to_mode_ref'] == tr['from_mode_ref'] and tr['event_class'] != 'fault_recovery': v.append(f'{t["id"]}: 自己遷移は個別異常復帰に限る')
        owner = nodes.get(tr['owner_ref'])
        if owner:
            for m in (tr['from_mode_ref'], tr['to_mode_ref']):
                if m and m not in owner['ros_node']['active_in_mode_refs']: v.append(f'{t["id"]}: owner {owner["id"]} がモード {m} で非活性')
        pend = [h for h in t['issue_refs'] if ents.get(h, {}).get('kind') == 'issue' and ents[h]['issue']['category'] == 'human' and ents[h]['issue']['state'] in ('open', 'partially_superseded')]
        if pend: u.append(f'{t["id"]}: 遷移先/復元内容が人の判断待ち {pend}')
    result('DR-04', v, u)
    # DR-05 requirement coverage
    v1map = {int(k): val for k, val in manifest['intent_requirement_lines'].items()}
    linemap = current_line_map(model)
    cur_lines = (Path(__file__).resolve().parents[2] / 'design/intent.md').read_text().splitlines()
    spec_start = next((i for i, l in enumerate(cur_lines, 1) if l.strip() == '個別の要求仕様：'), len(cur_lines) + 1)
    new_in_scope = {rq for line, rq in linemap.items() if line > spec_start and ents[rq].get('revision_ref')}
    scope_rqs = {v1map[l] for l in SCOPE_LINES if l in v1map} | new_in_scope
    scope_rqs = {r for r in scope_rqs if ents[r]['adoption'] != 'superseded'}
    rq_line = {v: k for k, v in linemap.items()}
    covered = collections.defaultdict(set)
    for e in model['entities']:
        for rq in e.get('requirement_refs', []): covered[rq].add(e['id'])
        if e['kind'] == 'reconciliation':
            for rq in e['reconciliation']['adopted_requirement_refs']: covered[rq].add(e['id'])
        if e['kind'] == 'issue':
            for rq in e['issue']['affected_refs']:
                if rq.startswith('RQ-'): covered[rq].add(e['id'])
    v = []; u = []
    for rq in sorted(scope_rqs):
        line = rq_line.get(rq, '?')
        by = covered.get(rq, set())
        if not by: v.append(f'{rq}（intent.md:{line}）に対応する設計要素も問題もない')
        elif all(ents[x]['kind'] in ('issue', 'reconciliation') for x in by): u.append(f'{rq}（intent.md:{line}）は問題/衝突 {sorted(by)} だけで対応。設計要素は人の判断待ち')
    result('DR-05', v, u)
    # DR-06 no e-stop in designed elements
    v = []
    for e in designed:
        text = json.dumps({k: val for k, val in e.items() if k not in ('issue_refs', 'related_refs', 'source_refs', 'requirement_refs')}, ensure_ascii=False)
        for sentence in re.split(r'[。"]', text):
            if ESTOP.search(sentence) and not re.search(r'取得できない|不明|しない|行わない|存在させない', sentence): v.append(f'{e["id"]}: 非常停止/押下検知に関する語を含む …{sentence[:60]}…')
    result('DR-06', v)
    # DR-07 unconfirmed boundary not used
    boundary = {e['id'] for e in model['entities'] if 'boundary' in e}
    v = []
    for n in nodes.values():
        r = n['ros_node']
        used = set(r['absorbs_module_refs']) | set(r['publishes_refs']) | set(r['subscribes_refs']) | set(r['serves_refs']) | set(r['calls_refs']) | set(r['owned_state_refs'])
        for b in used & boundary: v.append(f'{n["id"]}: 未確認要素 {b} を使用')
    for i, e in ifs.items():
        d = e['designed_interface']
        for b in (set(d['publisher_refs']) | set(d['consumer_refs']) | {d['owner_ref']}) & boundary: v.append(f'{i}: 未確認要素 {b} を発行者/所有者/消費者にしている')
    for t in trans:
        if t['transition']['owner_ref'] in boundary: v.append(f'{t["id"]}: 未確認要素が遷移の所有者')
    for b in boundary:
        e = ents[b]
        if e['design_status'] == '承認済み' or e['adoption'] == 'designed_proposal': v.append(f'{b}: 未確認なのに採用/承認状態')
    result('DR-07', v)
    # DR-08 contracts kept
    v = []; u = []
    for line, label in CONTRACT_LINES.items():
        rq = v1map.get(line)
        e = ents.get(rq)
        if not e or e['adoption'] != 'upper_requirement': v.append(f'{label}（intent.md:{line}）の要求が上位要求として存在しない'); continue
        if not covered.get(rq) or all(ents[x]['kind'] in ('issue', 'reconciliation') for x in covered[rq]): v.append(f'{label}（{rq}）を参照する設計要素がない')
        for c in model['entities']:
            if c['kind'] == 'reconciliation' and rq in c['reconciliation']['affected_refs']: v.append(f'{label}（{rq}）が置換対象 {c["id"]} に含まれている')
    result('DR-08', v, u)
    # DR-09 no new modes/protections/approvals
    v = []
    for t in trans:
        tr = t['transition']
        if tr['trigger_kind'] == 'human' and tr['event_class'] not in HUMAN_ONLY_EVENTS: v.append(f'{t["id"]}: 人の操作を要する新しいイベント {tr["event_class"]}（追加の承認操作）')
        if tr['event_class'] in ('fault_recovery', 'pc_restart', 'goal_reached', 'nav_failure', 'recovery_failed') and tr['trigger_kind'] == 'human': v.append(f'{t["id"]}: 自動であるべき遷移が人の操作になっている')
    for e in model['entities']:
        if e['kind'] == 'mode' and e['mode']['runtime'] and e['id'] not in ('MODE-AUTO', 'MODE-MAP', 'MODE-PAUSE', 'MODE-MANUAL'): v.append(f'{e["id"]}: 新しい runtime mode')
    result('DR-09', v)
    # DR-10 version-dependent IFs
    v = []
    for i, e in ifs.items():
        d = e['designed_interface']
        st = d['version_dependency']['status']
        if st != 'none' and e['design_status'] == '承認済み': v.append(f'{i}: 版依存IFが承認済み扱い')
        if st in ('unconfirmed', 'confirmed_upstream') and not any(ents.get(x, {}).get('kind') == 'issue' and ents[x]['issue']['state'] in ('open', 'partially_superseded') for x in e['issue_refs']):
            v.append(f'{i}: 版未照合のIFが未解決の技術/資料問題を参照していない')
        if st == 'confirmed_installed_version' and not any('vehicle_pc' in ev for ev in d['version_dependency']['evidence']): v.append(f'{i}: 実車版照合済みと記すが実車PCの証拠ファイルがない')
        if (d['qos']['reliability'] == 'unconfirmed' or d['qos']['durability'] == 'unconfirmed') and d['version_dependency']['status'] != 'unconfirmed': v.append(f'{i}: QoS 未確認なのに version_dependency が unconfirmed ではない')
    pending_versions = [i for i, e in ifs.items() if e['designed_interface']['version_dependency']['status'] in ('unconfirmed', 'confirmed_upstream')]
    result('DR-10', v, [f'{i}: 版・QoSの照合待ち' for i in pending_versions])
    # DR-11 no generic values
    v = []; u = []
    for e in model['entities']:
        if e['kind'] != 'parameter': continue
        p = e['parameter']
        if p['value_state'] == 'unresolved':
            if p['value'] is not None: v.append(f'{e["id"]}: 未確定なのに値がある')
            if not e['issue_refs']: v.append(f'{e["id"]}: 未確定値に問題IDがない')
            else: u.append(f'{e["id"]}: 値未確定 {e["issue_refs"]}')
        if p['value_state'] == 'source_value':
            # The cited source text must actually contain the number (separators removed).
            digits = re.sub(r'[^0-9]', '', '%g' % p['value']) if isinstance(p['value'], (int, float)) else ''
            texts = [re.sub(r'[,\.]', '', json.dumps(sources[s]['raw_fields'], ensure_ascii=False)) for s in e['source_refs'] if s in sources]
            if isinstance(p['value'], (int, float)) and not any(digits in t or digits.lstrip('0') in t for t in texts): v.append(f'{e["id"]}: 値 {p["value"]} が出典原文に見当たらない（一般値の疑い）')
        if p['value_state'] == 'approved' and not (e.get('approval_source_ref') or e.get('approval_decision_ref')): v.append(f'{e["id"]}: 承認根拠のない approved')
    result('DR-11', v, u)
    # DR-12 no automatic adoption / whole-row disposal
    v = []
    justified = {a for c in model['entities'] if c['kind'] == 'reconciliation' and c['reconciliation']['state'] in ('resolved_by_intent', 'resolved_by_decision') for a in c['reconciliation']['affected_refs']}
    for e in model['entities']:
        if e['adoption'] == 'legacy_candidate' and e['design_status'] == '承認済み': v.append(f'{e["id"]}: 旧候補が承認済み')
        if e['adoption'] == 'superseded' and e['id'] not in justified: v.append(f'{e["id"]}: 置換根拠のない superseded')
        if e['adoption'] == 'superseded' and e['kind'] in ('module', 'interface', 'requirement', 'transition', 'test', 'data_contract') and sources[e['source_refs'][0]]['kind'] != 'intent_lines': v.append(f'{e["id"]}: 旧資料の行全体を破棄扱い')
    for n in nodes.values():
        if n['design_status'] != '案': v.append(f'{n["id"]}: Node案が案以外')
        for m in n['ros_node']['absorbs_module_refs']:
            if ents[m]['design_status'] == '承認済み': v.append(f'{n["id"]}: 吸収したモジュール {m} を承認済みにしている')
    result('DR-12', v)
    # DR-13 no reuse of 5 m
    v = []
    for e in designed:
        if e['kind'] == 'parameter' and e['parameter']['unit'] == 'm' and e['parameter']['value'] == 5.0: v.append(f'{e["id"]}: 5.0 m を採用値にしている')
        text = json.dumps(e, ensure_ascii=False)
        for sentence in re.split(r'[。"]', text):
            if re.search(r'(?<![0-9.])5(?:\.0)?\s?m(?![a-z/])', sentence) and '流用しない' not in sentence and '旧' not in sentence:
                v.append(f'{e["id"]}: 5 m の言及 …{sentence[:80]}…')
    result('DR-13', v)
    # DR-14 ledger coverage
    v = []
    decided = {r for d in model.get('decisions', []) for r in d['affected_refs'] + d['resulting_refs']}
    for e in model['entities']:
        if e['kind'] == 'issue' and e['issue']['category'] in ('human', 'source_missing') and e['id'] not in decided: v.append(f'{e["id"]}: 判断台帳に項目がない')
    result('DR-14', v)
    # DR-15 declarative settings: single declaration, generated files match, no hardcode
    v = []; u = []
    import generate_params
    keys = collections.Counter()
    for e in model['entities']:
        if e['kind'] != 'parameter' or e['adoption'] not in ('designed_proposal', 'approved'): continue
        p = e['parameter']
        if not p.get('declaration'): v.append(f'{e["id"]}: declaration（宣言先）が未定義'); continue
        if p['declaration'] in ('code_state_machine', 'model_declared'):
            continue
        for f in ('target', 'param_key', 'value_type', 'apply_timing'):
            if not p.get(f): v.append(f'{e["id"]}: {f} が未定義')
        if p.get('target') and p.get('param_key'): keys[(p['target'], p['param_key'])] += 1
    for k, n in keys.items():
        if n > 1: v.append(f'設定 {k} が {n} 回宣言されている')
    expected = generate_params.render(model); outdir = generate_params.OUT
    for name, text in expected.items():
        f = outdir / name
        if not f.exists(): v.append(f'generated/params/{name} が生成されていない'); continue
        if name != 'index.json' and f.read_text() != text: v.append(f'generated/params/{name} が正本から再生成した内容と一致しない（手編集の疑い）')
    # hardcode scan: approved numeric values must not appear as literals in Gouda source trees (none implemented yet).
    # Source trees of the NEW implementation (工程5). Configured in tools/hardcode_scan_roots.json; empty until the
    # new nodes exist. The legacy implementation is replaced (DEC-030) and is not scanned.
    cfg = Path(__file__).resolve().parent / 'hardcode_scan_roots.json'
    roots = [Path(__file__).resolve().parents[2] / r for r in json.loads(cfg.read_text())['roots']] if cfg.exists() else []
    approved = [(e['id'], e['parameter']['param_key'], e['parameter']['value']) for e in model['entities'] if e['kind'] == 'parameter' and e['parameter']['value_state'] == 'approved' and isinstance(e['parameter']['value'], (int, float))]
    for root in roots:
        if not root.exists(): continue
        for src in root.rglob('*.py'):
            try: text = src.read_text()
            except Exception: continue
            for pid, key, val in approved:
                # Literal forms of the approved value as written in Python source: the float form (1.0, 0.7) and, for a
                # float with an integral value, also "1." — but not the bare integer "1", which would flag every index.
                forms = {repr(float(val)), '%g' % val} if isinstance(val, float) and not float(val).is_integer() else {repr(float(val)), f'{int(val)}.'}
                if any(re.search(rf'(?<![\w.]){re.escape(f)}(?![\w.])', text) for f in forms) and key not in text: u.append(f'{pid}: 承認値 {val} に一致するリテラルが {src.relative_to(root.parent)} にある（param_key 不在。確認が必要）')
    result('DR-15', v, u)
    return results


def main():
    p = argparse.ArgumentParser(); p.add_argument('--model', type=Path, default=DESIGN / 'model.yaml'); p.add_argument('--schema', type=Path, default=DESIGN / 'schema.json'); p.add_argument('--manifest', type=Path, default=DESIGN / 'migration_manifest.json'); p.add_argument('--report', type=Path, default=DESIGN / 'reports/design_check.json'); a = p.parse_args()
    model = load_yaml(a.model); schema = json.loads(a.schema.read_text()); manifest = json.loads(a.manifest.read_text())
    results = run(model, schema, manifest)
    rules = [{'id': r, 'description': d, 'basis': b, **results[r]} for r, d, b in RULES]
    counts = collections.Counter(x['result'] for x in rules)
    report = {'scope': '下位設計案（REV-002）の設計整合性。移行忠実性は migration_validation.json。合格は設計承認・ROS動作確認・実車検証を意味しない。',
              'result_counts': {'合格': counts.get('合格', 0), '違反': counts.get('違反', 0), '未判定': counts.get('未判定', 0)},
              'overall': '合格' if counts.get('違反', 0) == 0 and counts.get('未判定', 0) == 0 else f"違反{counts.get('違反', 0)}件・未判定{counts.get('未判定', 0)}件",
              'rules': rules}
    a.report.parent.mkdir(parents=True, exist_ok=True); a.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    for r in rules: print(r['id'], r['result'], f"違反{len(r['violations'])} 未判定{len(r['undetermined'])}")
    print(json.dumps(report['result_counts'], ensure_ascii=False), report['overall'])
    return 1 if counts.get('違反', 0) else 0


if __name__ == '__main__': sys.exit(main())
