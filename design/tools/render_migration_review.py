"""Generate the requested review tables from the canonical model; no diagrams."""
import collections, json
from pathlib import Path
from validate_model import load_yaml, DESIGN
def esc(s): return str(s).replace('|','\\|').replace('\n','<br>')
def main():
    m=load_yaml(DESIGN/'model.yaml'); v=json.loads((DESIGN/'reports/migration_validation.json').read_text()); run=json.loads((DESIGN/'reports/migration_check_run.json').read_text())
    sources={s['id']:s for s in m['sources']}; entities={e['id']:e for e in m['entities']}
    def pos(sid):
        s=sources[sid]; l=s['locator']
        if s['kind']=='excel_row': return f"Excel {l['sheet']}!{l['range']}"
        if s['kind']=='intent_lines': return f"intent.md:{l['line_start']}–{l['line_end']}"
        return f"drawio page={l['page']} element={l['element_id']}"
    def refs(ids): return ', '.join(f'`{i}`' for i in ids)
    def srcpos(ids): return '; '.join(pos(s) for s in dict.fromkeys(s for i in ids for s in entities[i]['source_refs']))
    s=v['summary']; d=v['design_validity']; counts=d['known_issue_counts']
    lines=['# YAML移行レビュー','', '対象日: 2026-10-08。最新 `intent.md` を上位要求とし、既存抽出結果を入力にした。原資料・intent・抽出結果は変更していない。','',
      '## 結果の区別','',
      '| 確認対象 | 結果 | 範囲 |','|---|---|---|',
      '| 前段の抽出忠実性 | 48項目一致という既存結果を保持 | 再抽出は行っていない。元資料ハッシュと既存抽出時ハッシュの一致を今回確認 |',
      f"| YAMLの形式・移行忠実性 | {v['format_and_migration']['result']}、違反{len(v['format_and_migration']['violations'])}件 | {v['format_and_migration']['executed_checks']}件の比較・規則検査。設計テストのケース数ではない |",
      '| 設計内容の妥当性 | 未判定 | 下位設計、ROS版でのIF確認、状態遷移の成立性、実車値は未検証 |',
      '| ロボット実装・ソフト動作 | 未実施 | 移行ツールの試験と、ROS Nodeの動作試験は別 |',
      '| 実車確認・投入判断 | 未実施・人の判断待ち | YAML移行を実車確認済みとは扱わない |','',
      f"既存定義IDは **198/198件** が同じIDへ移行。加えて既存の変更記録ID `CH-01`〜`CH-04` を保持したため、既存ID対応表は **{s['id_map_count']}件**。198件側の重複・対応漏れは0件。CHは旧抽出器のIDパターン対象外だったが行原文には存在しており、今回の追加抽出ではない。",
      f"モデルは{s['entity_count']}要素、出典{s['source_count']}件。Excelモジュール38件にIDなし行の `gouda_section_executor` を `M-039` として加えた39件。図は101 vertex（枠・注記含む）、2構造要素、84接続を全て保持。図の要素数をモジュール数やExcel IF46件と同一視しない。",'',
      '## 正本の読み方と状態','',
      '- `files` は原ファイル/抽出ファイル/検証結果のパスとSHA-256、`sources` は実位置と原文。`raw_fields` の原文を編集用の設計値と混ぜない。',
      '- `entities` が下位設計の管理単位。`field_bindings` は出典の列/フィールドへ参照し、状態所有・パラメータ群・故障応答・実行配置を独立IDで関係付ける。同じ原文を各表へ再転記しない。`name` は表示ラベルであり仕様の正本値ではない。',
      '- `original_status` は抽出時の「確定／未決」と根拠・元の区分をそのまま保持。`design_status` は下位設計の「未設計／案／承認済み」。原資料の確定・実装済みという記載から下位設計の承認や実車確認を推定しない。',
      '- `adoption: upper_requirement` は現在の上位要求。`legacy_candidate` は移行された旧設計候補であり、自動採用ではない。`partially_superseded` はC番号のscopeで特定した部分を置換する。残りの候補を無条件に承認する意味ではない。',
      '- 現在の採用内容は `reconciliation.adopted_requirement_refs` で上位要求を参照する。旧原文は残るが、置換された部分を現在要求と合成しない。`open` の衝突は未解消の問題IDを参照する。',
      '- 明示なし・未設計の全てを人の判断待ちにしない。`issue.category` が `technical` ならAIの次段階作業、`human` だけが人の判断対象、`source_missing` は証拠不足。',
      '- パラメータ群24件は、元の主要設定欄を参照した段階。個別キー・型・単位・値は未設計。`value: null` と `value_state: unresolved` を保存し、0や慣例値を入れていない。原文内の5 m等の旧値は原文として残り、採用値には昇格しない。',
      '- 現在のruntime modeは4件。旧モード/メタ値6件も資料履歴として保持するが `runtime: false`。内部状態と新モードを混同しない。',
      '- 実行構成39件は原文の種別・実装場所・使用モード・起動条件を保持する枠。ROS Node分割・process配置は未設計。モジュール分類も `unclassified` のままで、1モジュール=1Node=1processとはしない。',
      '- 新IDは `migration_manifest.json` の `id_registry` に固定。新旧の出典位置が変わっても再採番しない。ビルダーは初回移行専用で正本を上書きしない。今後の設計ではモデルを編集し、移行baselineは履歴として維持する。',
      '- `schema.json` は形式と許される未確定状態を検査。`validate_model.py` はID、参照、出典、元データ照合、明示問題を検査。初回移行の全件台帳も固定して検査するため、将来の追加設計は移行baselineの改版/差分審査と分けて扱う。',
      '- 最新intent以外のWeb資料・公式仕様・実装コードは、この移行で再検証していない。REF行は引用記録として移行しただけで、採用版への適合を保証しない。','',
      '## 未設計の範囲','',
      'Node分割、process配置、IFの標準型選択・所有者・QoS・時刻、パラメータの個別定義、復旧時の必要状態・旧goal処理、ログ/rosbagの独立制御、故障応答の詳細、現要求に対応した試験は未設計。既存25試験は未実行。新しい通過判定、後退累計管理、境界での実速度保証、モード、保護、承認操作は追加していない。','',
      'モデルの設計状態（図・出典整理用要素も含む件数）: '+json.dumps(v['design_maturity'],ensure_ascii=False)+'。承認済み0件。','',
      '## 矛盾・変更対応','',
      'C-001〜C-013は上位要求が明示する変更/具体化の対応。旧案の行全体を破棄・承認せず、scopeに書いた範囲だけを扱う（置換しない範囲は `generated/gate3_review_C001_C013.md`）。C-014〜C-016は未解消。REV-002 で C-017（非常停止検知の不採用、resolved_by_intent）、C-018（車体座標系とREP-103の衝突、open）、C-019（復旧不能時の遷移先、open）を追加。','']
    for e in m['entities']:
        if e['kind']!='reconciliation': continue
        r=e['reconciliation']; lines += [f"### {e['id']} {e['name']}",'',f"状態: `{r['state']}`。",'',r['scope'],'', '旧側の影響ID: '+refs(r['affected_refs']), '', '原位置: '+srcpos(r['affected_refs']), '']
        if r['adopted_requirement_refs']:
            lines += ['現在の採用要求: '+refs(r['adopted_requirement_refs'])+'。'+srcpos(r['adopted_requirement_refs']),'']
        if r['issue_refs']: lines += ['未解消問題: '+refs(r['issue_refs']),'']
    lines += ['## 残っている問題','',f"計{d['known_issue_count']}件。技術事項{counts['technical']}件、人の判断{counts['human']}件、資料不足{counts['source_missing']}件。未解消衝突3件は資料不足の問題に紐付き、二重加算しない。元Qは部分的に置換されたものも閉じずに残余課題を保持。",'',
              '| 問題ID | 分類 | 状態 | 内容 |','|---|---|---|---|']
    for e in m['entities']:
        if e['kind']=='issue':
            q=e['issue']; lines.append(f"| {e['id']} | {q['category']} | {q['state']} | {esc(e['name'])} |")
    lines += ['', '### 人が判断する7件','', 'この移行の完了に回答は不要。決定済み要求の再承認は求めない。以下は影響する次段階の設計/実車値だけを対象とする。推奨は未採用の判断材料。','']
    for e in m['entities']:
        if e['kind']!='issue' or e['issue']['category']!='human': continue
        q=e['issue']; lines += [f"#### {e['id']} {e['name']}",'',q['question'],'']
        for op in q['options']: lines.append('- '+op['label']+'：'+op['effect'])
        lines += ['', '推奨: '+q['recommendation'], '', '影響ID: '+refs(q['affected_refs']), '', '出典: '+'; '.join(pos(s) for s in e['source_refs']), '', '次の作業: '+q['next_action'],'']
    lines += ['### 資料不足と技術作業','']
    for e in m['entities']:
        if e['kind']!='issue' or e['issue']['category']=='human': continue
        q=e['issue']; lines += [f"- **{e['id']}**（{q['category']}）{q['question']} 次の作業: {q['next_action']}"]
    lines += ['', '接続先未特定は `U-DRAW-001`。原ページ `lc-_yTM2-hEJOly5ozWo`、線 `2TSgiu6-nVzXwyzMdGmE-18`。`targetPoint` は残し、`to_ref: null` を維持。','',
              '## 重大な基本契約・未検証前提','',
              'これらは移行検査合格をもって成立したとは判断していない。','']
    man=json.loads((DESIGN/'migration_manifest.json').read_text()); lr=dict(man['intent_requirement_lines'])
    for e in m['entities']:
        if e['kind']=='requirement' and e.get('revision_ref') and sources[e['source_refs'][0]]['kind']=='intent_lines': lr[str(sources[e['source_refs'][0]]['locator']['line_start'])]=e['id']
    for l in [14,16,19,24,25,26,34,35,36,38,90,91,92,93,95,96,97,98,99,100]:
        i=lr[str(l)]; src=sources[entities[i]['source_refs'][0]]
        lines.append(f"- `{i}`（intent.md:{l}）：{src['raw_fields']['text']}")
    lines += ['', 'ESP32中立出力・手動優先・通信仕様・DAC値の実機成立はQ-03/Q-05/Q-09で未確認。PC側の中立出力を車体全体の停止保証に読み替えない。既存の保護はこの移行では追加・削除していない。','',
              '## 既存ID全件の移行対応表','', 'baseline198列が「対象」の198件に、原文の変更記録4件を別枠で追加。旧ID=モデルID。','',
              '| 既存ID | モデルID | 種別 | 出典 | baseline198 | 現在の扱い |','|---|---|---|---|---|---|']
    for mp in m['migration']['id_map']:
        e=entities[mp['target_ref']]; lines.append(f"| {mp['legacy_id']} | {e['id']} | {e['kind']} | {esc(pos(mp['source_ref']))} | {'対象' if mp['baseline'] else '追加CH'} | {e['adoption']} |")
    lines += ['', '### 新規固定IDの対応','',
              '- `M-039`: Excel モジュール定義!B12:O12を含む保存行（IDなしのgouda_section_executor）。現行採用はC-012/G-ARCHで整理。',
              '- `RQ-I...`: intentの要求行。命名・位置の変更で再採番しない。全対応はmanifestとsources。',
              '- `LEG-...`: 元にIDがなかった命名規則・旧モード等。元のシート/行をsourcesに保持。',
              '- `OWN-M-...` / `PAR-M-...` / `FM-M-...` / `EX-M-...`: 同じモジュールの元セルから分離した保持状態・パラメータ群・故障応答・実行配置。',
              '- `DG-...`: drawioページID+要素IDから初回割当したUUID。図形・線・構造要素の原IDはsourcesに保持。',
              '- `MODE-...` / `C-...` / `G-...` / `H-...` / `U-...`: 現モード・変更対応・技術事項・承認事項・資料不足。','',
              '## 検査器と試験の再実行','',
              '必要パッケージは `tools/requirements.txt` に固定。通常のPython環境ではそのrequirementsを仮想環境へインストールしてから、workspaceルートで次を実行する。','',
              '```sh','cd /Users/AYARyoya/Desktop/自己学習/TsukubaChallenge','python3 design/tools/run_migration_checks.py','python3 design/tools/render_migration_review.py','```','',
              '今回実行した環境と正確なコマンド、終了コード、成果物ハッシュは `reports/migration_check_run.json`。今回の一時依存パスは `/private/tmp/gouda-model-deps`。再現時には再インストールが必要な場合がある。','',
              '試験結果: `reports/migration_tests.txt`。最小YAMLと意図的違反データは `rules/fixtures/`。ID重複、参照切れ、出典欠落に加えて、出典フィールド欠落、承認根拠なし、未確定値0埋め、未接続の隠蔽、問題消失、原文改変、既存ID対応漏れを検出する試験を実施。','',
              '| 実行 | 終了コード | 記録 |','|---|---:|---|']
    for r in run['runs']: lines.append(f"| {esc(' '.join(r['command']))} | {r['exit_code']} | {r['output']} |")
    lines += ['', '## ファイル配置・作業境界','',
              'workspace直下のdesignは、ロボット実装の `tsukuba-autonomous-robot/` Gitリポジトリとは別の場所。実装リポジトリの確認時HEADは `a091ed39eb154b2dff7065840dc13c6478b153da`。既存のdocs/architecture配下の変更には触れていない。',
              'schema/model/manifestは今回新規。intent、Excel、drawio、全抽出成果物は変更前後のSHA-256一致。完成版のROS graph・IF表・故障モード表や図は生成していない。ここにある表は今回要求された移行対応・矛盾・未決事項のレビュー表。','']
    (DESIGN/'migration_review.md').write_text('\n'.join(lines))
    print('Wrote design/migration_review.md')
if __name__=='__main__': main()
