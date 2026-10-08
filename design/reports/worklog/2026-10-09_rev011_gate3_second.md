# 作業記録 2026-10-09 第7便: intent.md 第6版、ゲート3 第2回の条件付き承認と未解消条件、基本契約の試験、design/ のコミット（REV-011）

## 読んだもの

- リポジトリ HEAD `a091ed39eb154b2dff7065840dc13c6478b153da`（作業開始時。design/ は未追跡）。`reports/status.md`、`reports/worklog/2026-10-09_rev010_gate3.md`、`revisions/REV-004.yaml`（AR-003・C-021 の置換の書式）、人が編集したワークスペース直下の `design/intent.md`。

## 1. 承認記録（人の回答は原文で台帳へ）

| 台帳 | 内容 |
|---|---|
| DEC-058（approval, answered） | ゲート3 第2回の条件付き承認（原文全文）。承認範囲: C-001〜C-013 の置換範囲の確認、下位設計案 122 件は暫定ベースライン（確定設計でも実車投入の承認でもない）。未解消の 4 条件を note に工程・状態付きで記録。**承認は確認完了の意味に扱わない**（生成物 `generated/gate3_package.md` §3b に明記） |
| DEC-059（question, pending, open_human） | 条件 2 の人の判断（H-013 の選択肢）。工程 5-4 の前に回答が必要 |
| DEC-060（confirmation） | design/ のコミット指示（原文） |
| DEC-052（note 追記） | 「claude.mdの修復差分に問題はなかった。」（原文） |
| DEC-055（note・resulting_refs 更新） | 「intent.mdから該当文言を削除した。」→ AR-006、RQ-I078、C-022 |

## 2. intent.md 第6版（AR-006）

- 人はワークスペース直下の `design/intent.md`（旧コピー）を編集していた。差分は 13 行の「区間境界では、進入する区間の値を適用する。」の削除のみ（diff で確認）。AI はその内容をリポジトリの `design/intent.md` へ一字も変えずに複製した（SHA `4f9f8606…`）。旧版（第5版 `81d71f07…`）は `baselines/intent_history/intent_v5_81d71f07cc72.md`、新版の保存コピーは `intent_v6_4f9f8606689b.md`。
- 機械検証: 置換 1 行（13 行）、追加・削除なし。`allow_non_append: true`、`decision_ref: DEC-055`。RQ-I010 → RQ-I078（`requirement_ref_replacements`、C-022）。C-002・C-003・C-011 の adopted_requirement_refs は後継 RQ-I078 に更新（置換後の行に同じ文が残るため）。

## 3. 未解消条件への対応（REV-011）

- 条件 1: REV-010 の列挙（IFD-14 名称、TR-05・TR-10、TS-01）を DEC-058 の note に記録。状態「更新済み・人の確認待ち」。
- 条件 2: 衝突 C-023（state open）と人の判断 H-013（案 A 位置ベース＋同値運用＋保存時警告、案 B Gouda 側発行器に戻す、案 C 重複経路の禁止。推奨 A）を登録。影響 ID: RQ-I078、IFD-14・41・42、ND-02・ND-10、TS-02・03・14、PRM-19。台帳 DEC-059。
- 条件 3: 基本契約の試験 TS-17（手動優先）、TS-18（gamepad 途絶 0.25 s）、TS-19（PC 指令途絶 1.0 s）、TS-20（一時停止）、TS-21（開始は人の操作のみ）を追加。工程と「車体出力の完了条件に含める案」は `docs/implementation_stages.md` §5。
- 条件 4: C-012 に clarification（薄い adapter は ND-03 の action client、独立モジュールなし）。IFD-31・DEC-015/032/044・C-003 は REV-010 の回答を参照。
- 修正の分類（1.6）: 設計（置換された要求を根拠に持つ衝突の後継更新。初回適用で REPLACEMENT_AUTHORITY 違反 3 件→REV-011 に後継の設定を加え、適用前のモデルから再適用して解消。検査の条件・期待値は変えていない）。

## 4. 検査・試験（`design/.venv/bin/python design/tools/run_checks.py`、終了コード 0。REV-011 適用後 model.yaml SHA `a7945cb22a3a5676fd4b…`）

| 検査 | 結果 |
|---|---|
| 入力の完全性 | PASS（原資料・抽出・baseline 一致。intent は新版 AR-006 として検証） |
| 設定の生成・intent 同一性 | PASS |
| 形式・移行忠実性 | 合格（5,881 検査、違反 0） |
| 設計整合性 15 ルール | 違反 0・未判定 4（DR-04 5、DR-05 2、DR-10 2、DR-11 38） |
| 検査器の試験 | 59 件 OK |
| ソフト試験（TS-01〜21）・ROS 動作・実車 | 未実行 |

停止・復帰の成立条件ビュー: 欠落なし。

## 5. 残るリスク

- H-013 が未回答のまま 5-4 に入ると、速度マスク生成器の重複規則（案 A 前提）を作り直す可能性がある。
- TS-17〜19 は卓上試験で、実車の配線・firmware との一致は DEC-050 の実機照合が別に必要。
- 別 clone では `.DS_Store` 2 件（保護対象）が .gitignore で除外され、入力の完全性が「不一致」になる（baseline 改版は人の判断）。
- コミットには design/.venv と .DS_Store を含めない。再現には `tools/requirements.txt` で仮想環境を作る。

## 6. 更新した生成物

`generated/gate3_package.md`（§3b 追加、§4）、`generated/review_r3.md`、`generated/stop_resume_conditions.md`、`generated/failure_modes.md`、`generated/parameters_by_stage.md`、`generated/measurement_plan.md`、`generated/pending_classification.md`、`generated/human_decisions_r2.md`、`generated/params/`、`conflicts.yaml`、`intent_open_items.yaml`、`intent_index.yaml`、`migration_review.md`、`reports/model_diff_rev-011.md`、`schema.json`。正本 Markdown: `docs/implementation_stages.md` §5。

## 7. コミット

- 指示（DEC-060）: ブランチは任意、メッセージ "Added design sheets"。ブランチ `design/gate3-baseline-2026-10-09` に `design/` 配下のみをコミット。コミット ID は末尾に追記する（コミット後に書くため、その追記自体は未コミット）。
- 対象外: `docs/architecture/*.xlsx`・`.drawio` の変更と `.bkp`（design/ 一式の指示に含まれないため触れていない）。

## 8. 次の作業

- 人の確認待ち: DEC-058 の 4 条件の対応（gate3_package §3b）。H-013 の選択（DEC-059）。implementation_stages §5 の案の採否。
- 進められる: 工程 5-1（起動と記録）。独自型 4 件の定義、G-FIRMWARE、Q-02 候補比較。
- 止まっている: 5-4（H-013 待ち）、GLIM 版固定、DEC-050。

## コミット ID（追記）

- ブランチ `design/gate3-baseline-2026-10-09`、コミット `4b7bdbeb38015299c8436c84686d963ad8422bdb`（"Added design sheets"、design/ 配下のみ）。この追記自体はコミット後に書いたため未コミット。
