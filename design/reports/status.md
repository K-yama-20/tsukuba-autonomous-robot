# 現状の要約（status.md）

最終更新：2026-10-09（REV-011、第7便）。ゲート3は条件付き・範囲限定で承認（DEC-053、第2回 DEC-058。承認は確認完了の意味ではなく、未解消 4 条件は `generated/gate3_package.md` §3b）。intent.md は第6版（`4f9f8606…`、人が RQ-I010 の境界文を削除。AR-006、RQ-I078）。承認対象は REV-009 適用後の model.yaml（SHA-256 `6510bbc2…`、凍結コピー `baselines/gate3_2026-10-09/model.yaml`＝FILE-GATE3-MODEL。Git 未コミット）。CLAUDE.md は修復版に置換済み（DEC-052）。工程5 は暫定ベースライン上で、値に依存しない下位設計・実車出力を伴わないソフト実装・stub 試験まで着手可（DEC-019 更新）。

## 三つの状態（CLAUDE.md 1.4）＋報告用の三区分（DEC-057）

- 移行が正確：合格。初回移行 baseline（`baselines/migration_v1/`、凍結）を保持したまま REV-002〜011 を適用。5,881 検査・違反 0。intent.md は第6版（`4f9f8606…`）で、第5版（`81d71f07…`）は `baselines/intent_history/` に保存し AR-006 で機械検証。原資料・抽出結果・baseline の SHA-256 は一致（`reports/input_integrity.json`）。
- 設計検査に合格：**未判定**。設計整合性 15 ルール 違反 0・未判定 4（DR-04: TR-09/13〜16 の試行上限 PRM-10 値、DR-05: RQ-I027・RQ-I072 は問題／衝突のみで対応、DR-10: IFD-35・IFD-38 の版照合、DR-11: 未確定値 38）。検査違反 0 件は未判定の解消でも実車適合の証明でもない。
- ソフト試験合格：**未実施**（TS-01〜21 はすべて未実行。工程5-1 から順に実施）。
- 実車検証済み／実車投入可能：**人の判断待ち**。実車試験は未実施。承認済みの実車値は PRM-07・08・13・21 の 4 件のみ。Q-04〜Q-06 は未確定、DEC-050 の実機照合は未実施（承認済み・実測済みとして扱わない：DEC-053）。

## 検査結果の件数（`design/.venv/bin/python design/tools/run_checks.py`、終了コード 0、REV-011 適用後 model.yaml `a7945cb2…`）

| 検査 | 合格 | 違反 | 未判定 |
|---|---|---|---|
| 入力の完全性（原資料・抽出・baseline・intent の SHA-256） | 一致 | 0 | 0 |
| 形式・移行忠実性（5,881 検査） | 5,881 | 0 | 0 |
| intent 版間の同一性 | 13 | 0 | 0 |
| 設定の生成（generate_params → generated/params/） | 生成 | 0 | 0 |
| 設計整合性（15 ルール） | 11 | 0 | 4（DR-04 5、DR-05 2、DR-10 2、DR-11 38） |
| 検査器の試験 | 59 | 0 | 0 |
| ソフト試験（TS-01〜21） | 0 | 0 | 21（未実行） |
| 既知の問題（issue） | — | — | 41 件（技術 14、人の判断 20、資料不足 7）。resolved 22、open 14、deferred 3（Q-07・Q-13・G-TUNING）、partially_superseded 2。判断台帳 59 件（answered 31、recorded 23、pending 5: DEC-021・022・024・050・059） |

## 承認待ち・実測待ち・人の作業・提案

- 承認済み: ゲート3 条件付き（DEC-053、第2回 DEC-058: C-001〜C-013 の置換範囲の確認、122 件は暫定ベースライン）、CLAUDE.md 修復（DEC-052。人が差分に問題なしと確認）、RQ-I010 の境界文削除と C-003 の飽和（DEC-055。intent.md 第6版で反映済み）。維持する方針: DEC-031・045・046・047・042・037・048。H-009 は閉じた。
- 人の確認待ち（承認を確認完了と扱わない）: DEC-058 の未解消 4 条件（条件 1 更新済み、条件 2 登録済み、条件 3 案提示、条件 4 回答済み。`generated/gate3_package.md` §3b、`docs/implementation_stages.md` §5）。
- 人の選択待ち: H-013（区間属性の上限と Speed Filter の位置ベース上限・DEC-045 の食い違い。案 A〜C、推奨 A。DEC-059）。工程 5-4 の前に必要。
- 任意の提案: intent.md の「手動操縦」表記の統一（`proposals/intent_edit_requests.md` §2）。
- 実測待ち: `generated/measurement_plan.md`（承認済みの PRM-08・13 は除外済み）。実機調整項目（帯幅 PRM-19、低速帯進入の記録 PRM-22〜24）は G-TUNING（設計規則・人の判断事項にしない）。
- 実機照合待ち: DEC-050（配線・firmware・操作結果）、DEC-024（Q-09）。技術調査: DEC-021（Q-02）、DEC-022（Q-03）。GLIM 版固定は実車PC の `dpkg -l | grep glim` 出力待ち。
- 提案（承認済み仕様ではない）: `proposals/undetectable_faults_r2.md`、`proposals/intent_edit_requests.md` §2（「手動操縦」表記の統一。任意）、`docs/git_management_plan.md`。

## 原本未照合

- 実車PC の Nav2 はパッケージ版（1.3.13）で照合。バイナリ内の IDL は直接読んでいない。
- 実装リポジトリの ESP32 プロトコル文書（Q-03）。CLAUDE.md の先頭 1〜17 行の欠落は推測のまま（原本なし）。
- 前回分: 公式ページからリンクされた PDF、未読の図版。

## 次の作業

- 工程5-1（起動と記録）の実装を機能単位で開始（`docs/implementation_stages.md` §1。全 Node の一括実装はしない）。新パッケージは `tools/hardcode_scan_roots.json` に登録。基本契約の試験 TS-17〜21 の工程は同 §5。
- 並行: 独自型 4 件の定義、G-FIRMWARE の設計、Q-02 の候補比較、mask 生成器（幅・刻みを引数）。
- 止まっている: 工程 5-4（H-013／DEC-059 待ち）、GLIM 版固定、DEC-050。design/ は `design/gate3-baseline-2026-10-09` ブランチにコミット済み（DEC-060）。

## 主要ファイルの場所（CLAUDE.md 1.9 の対応表。パスはリポジトリ `tsukuba-autonomous-robot/` 相対）

| 役割 | 場所 | 備考 |
|---|---|---|
| 設計意図（人が所有） | `design/intent.md` | 第6版 103 行。旧版は `baselines/migration_v1/intent.md`（第1版）、`baselines/intent_history/`（第2〜6版の保存コピー） |
| 正本（YAML） | `design/model.yaml`、`design/schema.json`（1.1） | 変更は `revisions/REV-xxx.yaml` → `tools/apply_revision.py`。最新 REV-011 |
| 正本（Markdown） | `design/docs/` | `implementation_stages.md`（工程・完了条件）、`vehicle_output_timing.md`、`speed_filter_design.md`、`regulations_2026.md`、`git_management_plan.md` |
| 判断台帳 | `model.yaml: decisions`（原文。DEC-001〜060） | ビュー: `generated/pending_classification.md`、`conflicts.yaml`、`intent_open_items.yaml`、`generated/human_decisions_r2.md` |
| ゲート3 承認の対象 | `design/baselines/gate3_2026-10-09/`（凍結コピー＋README） | FILE-GATE3-MODEL として SHA-256 を検査 |
| 検査器・ルール一覧・試験 | `tools/validate_model.py`、`tools/check_design.py`、`rules/` | ルール一覧と根拠は `rules/README.md` |
| スクリプト | `tools/` | `run_checks.py` が全検査を実行し `reports/check_run.json` に記録。`render_views.py`・`generate_params.py`・`render_migration_review.py` で生成物を再生成 |
| 生成物（手編集禁止） | `generated/`（`gate3_package.md`、`review_r3.md`、`stop_resume_conditions.md`、`failure_modes.md`、`parameters_by_stage.md`、`measurement_plan.md`、`params/` ほか）、`conflicts.yaml`、`intent_open_items.yaml`、`intent_index.yaml`、`migration_review.md`、`reports/model_diff_rev-011.md` | |
| 提案 | `proposals/` | 承認済み仕様として使わない。`CLAUDE.md.repaired`／`.diff`（適用済み）、`intent_edit_requests.md`、`undetectable_faults_r2.md` |
| 調査・証拠 | `research/` | `claude_md/CLAUDE.md.original_2c90ed21`（修復前の原本）、`claude_md_inspection.md`、`vehicle_pc/`、`upstream_jazzy/`、`joystick270_firmware/`、`timing_values_h009.md`、`speed_filter_reapply_h011.md`、`nav2_version_survey.md` |
| 報告・作業記録 | `reports/`、`reports/worklog/` | 最新: `2026-10-09_rev011_gate3_second.md`。引き継ぎ: `reports/handover_2026-10-09.md`（追記あり） |
| baseline | `baselines/migration_v1/`（凍結、`snapshot.json`）、`baselines/intent_history/`、`baselines/gate3_2026-10-09/` | |
| 元資料 | `docs/Gouda_architecture_detail.xlsx`、`docs/SystemArchitecture.drawio`、`docs/extraction_20261008_01a11af4/` | 読み取り専用 |
| ロボット実装 | リポジトリ直下の各パッケージ | 実装コードは未変更。工程5-1 から新規パッケージを作る |
