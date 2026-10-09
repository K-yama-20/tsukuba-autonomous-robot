# 現状の要約（status.md）

最終更新：2026-10-09（REV-025、第16便）。**工程5-4（waypoint と速度マスク生成器）を実装し Ubuntu で API 試験合格（合成の変換後地図の範囲）**。map.yaml のしきい値は宣言しない（DEC-075）。REV-020 分は Ubuntu でソフト試験合格。**工程5-3（地図作成と変換）を実装し Ubuntu でソフト試験合格（センサーなしの範囲）**: GLIM 1.2.2 の起動・保存、原図の登録（内容ハッシュ）、変換 action（submap なしでは失敗し原図保持）、自動開始分だけの記録停止。実データでの変換は未確認。**工程5-2（gouda_monitor）を実装し Ubuntu でソフト試験合格**（`research/vehicle_pc/2026-10-09_stage5-2_ubuntu_test.txt`）。試験環境は Parallels の Ubuntu 24.04（`ssh -o BatchMode=yes aya@10.211.55.4`、`~/gouda_ws`。DEC-067）。**工程5-1 は Ubuntu の ROS 2 環境でビルド・試験済み（ソフト試験合格。実車検証ではない）**。記録は `research/vehicle_pc/2026-10-09_stage5-1_ubuntu_test.txt`。旧 scripts/gouda.sh 類は削除（DEC-068）。**ゲート3は条件付きで承認（DEC-064、文言は DEC-065 で差し替え）**。条件は DEC-053・DEC-058 のとおり（暫定ベースライン。確定設計・実車値の確定・未実施試験の合格・実車投入の承認ではない）。承認対象は push 済みコミット f208066 時点の design/。**工程5-1（起動と記録）の実装に着手（DEC-066）**: gouda_interfaces・gouda_core・gouda.sh を新設。ROS 上の確認は実車PC 待ち。intent.md は第7版（`f69dd98b…`。第6版で RQ-I010 の境界文削除、第7版で 27 行に位置ベース上限の補足と 95 行の表記統一。AR-006・AR-007）。GLIM 版は実車PC の 1.2.2-0noble で固定（DEC-062）。REV-014 以降と新実装は未コミット。承認対象は REV-009 適用後の model.yaml（SHA-256 `6510bbc2…`、凍結コピー `baselines/gate3_2026-10-09/model.yaml`＝FILE-GATE3-MODEL。Git 未コミット）。CLAUDE.md は修復版に置換済み（DEC-052）。工程5 は暫定ベースライン上で、値に依存しない下位設計・実車出力を伴わないソフト実装・stub 試験まで着手可（DEC-019 更新）。

## 三つの状態（CLAUDE.md 1.4）＋報告用の三区分（DEC-057）

- 移行が正確：合格。初回移行 baseline（`baselines/migration_v1/`、凍結）を保持したまま REV-002〜025 を適用。5,896 検査・違反 0。intent.md は第7版（`f69dd98b…`）で、第5・6版は `baselines/intent_history/` に保存し AR-006・AR-007 で機械検証。intent 同一性 13 行は 12 一致・1 置換（RQ-I066→RQ-I080、記録済み）。原資料・抽出結果・baseline の SHA-256 は一致（`reports/input_integrity.json`）。
- 設計検査に合格：**未判定**。設計整合性 17 ルール 違反 0・未判定 4（DR-04: TR-09/13〜16 の試行上限 PRM-10 値、DR-05: RQ-I027・RQ-I072 は問題／衝突のみで対応、DR-10: IFD-38 の版照合、DR-11: 未確定値 38）。検査違反 0 件は未判定の解消でも実車適合の証明でもない。
- ソフト試験合格：**工程5-1〜5-4 が合格**（TS-23〜28: gouda_core 単体 59 件 OK、Ubuntu の ROS 2 上で起動・再起動・記録・monitor・/config・地図作成の開始／終了・原図登録・変換の失敗時の後始末を確認。FILE-VEHICLE-PC-STAGE51／52／53・REV020）。5-3 はセンサーなしの範囲で、実データでの変換は未確認。画面は Mac の DEMO で確認、実機ブラウザは未確認。TS-01〜22 は未実行。
- 実車検証済み／実車投入可能：**人の判断待ち**。実車試験は未実施。承認済みの実車値は PRM-07・08・13・21 の 4 件のみ。Q-04〜Q-06 は未確定、DEC-050 の実機照合は未実施（承認済み・実測済みとして扱わない：DEC-053）。

## 検査結果の件数（`design/.venv/bin/python design/tools/run_checks.py`、終了コード 0、REV-025 適用後 model.yaml（本便末尾の worklog 参照）。承認対象は REV-013 時点 `af7f5bc2…`）

| 検査 | 合格 | 違反 | 未判定 |
|---|---|---|---|
| 入力の完全性（原資料・抽出・baseline・intent の SHA-256） | 一致 | 0 | 0 |
| 形式・移行忠実性（5,896 検査） | 5,896 | 0 | 0 |
| intent 版間の同一性 | 13（12 一致、1 記録済み置換） | 0 | 0 |
| 設定の生成（generate_params → generated/params/） | 生成 | 0 | 0 |
| 設計整合性（17 ルール） | 13 | 0 | 4（DR-04 5、DR-05 2、DR-10 1、DR-11 46） |
| 検査器の試験 | 68 | 0 | 0 |
| gouda_core 単体試験（TS-23〜28 の単体部分） | 59 | 0 | 0 |
| 工程5-1〜5-4 の ROS 上の試験（Ubuntu） | 合格 | 0 | 0（センサー・実車は未接続。実データでの変換、実機ブラウザ表示と waypoint タブの操作は未確認） |
| ソフト試験（TS-01〜28） | 6（TS-23〜28） | 0 | 22（未実行） |
| 既知の問題（issue） | — | — | 41 件（技術 14、人の判断 20、資料不足 7）。resolved 23、open 13、deferred 3（Q-07・Q-13・G-TUNING）、partially_superseded 2。判断台帳 73 件（answered 38、recorded 31、pending 4: DEC-021・022・024・050） |

## 承認待ち・実測待ち・人の作業・提案

- 承認済み: ゲート3 条件付き（DEC-053、第2回 DEC-058: C-001〜C-013 の置換範囲の確認、122 件は暫定ベースライン）、CLAUDE.md 修復（DEC-052。人が差分に問題なしと確認）、RQ-I010 の境界文削除と C-003 の飽和（DEC-055。intent.md 第6版で反映済み）。維持する方針: DEC-031・045・046・047・042・037・048。H-009 は閉じた。
- 承認済み: ゲート3は条件付き（DEC-064・DEC-065。条件は DEC-053・DEC-058）。DEC-058 の 4 条件の対応は人が確認（DEC-061）。H-013 は案 A（DEC-059）で解消し intent.md 第7版に補足（RQ-I079）。
- 人の回答待ち: 「車体出力の完了条件に基本契約 5 件の stub 試験を含める案」（`docs/implementation_stages.md` §5）の採否。intent 同一性チェッカーが記録済み置換を合格扱いにする変更の可否（第8便 worklog 判断事項 1）。122 件の design_status を承認済みに変えるか（推奨: 変えない）。旧 scripts/gouda.sh と新 gouda.sh の統合・撤去（承認事項）。自動開始契機を載せる記録 IF の追加案。rosbag の対象 topic・保存形式の parameter 宣言（後の工程）。REV-014 以降と新実装のコミット指示。
- GLIM: 版は 1.2.2-0noble で固定（DEC-062、`research/vehicle_pc/2026-10-09_glim_version.txt`）。人は LTS 版の使用も可としたため、変更時は証拠を取り直す。
- 実測待ち: `generated/measurement_plan.md`（承認済みの PRM-08・13 は除外済み）。実機調整項目（帯幅 PRM-19、低速帯進入の記録 PRM-22〜24）は G-TUNING（設計規則・人の判断事項にしない）。
- 実機照合待ち: DEC-050（配線・firmware・操作結果）、DEC-024（Q-09）。技術調査: DEC-021（Q-02）、DEC-022（Q-03）。
- 提案（承認済み仕様ではない）: `proposals/undetectable_faults_r2.md`、`proposals/intent_edit_requests.md` §2（「手動操縦」表記の統一。任意）、`docs/git_management_plan.md`。

## 原本未照合

- 実車PC の Nav2 はパッケージ版（1.3.13）で照合。バイナリ内の IDL は直接読んでいない。
- 実装リポジトリの ESP32 プロトコル文書（Q-03）。CLAUDE.md の先頭 1〜17 行の欠落は推測のまま（原本なし）。
- 前回分: 公式ページからリンクされた PDF、未読の図版。

## 次の作業

- 工程5-1〜5-4 はソフト試験合格。次は 5-5（車体出力: gouda_motion_controller・vehicle_bridge・新 firmware。完了条件に手動優先・入力途絶時の中立化・一時停止中の中立出力）。センサー接続後に実データで原図→変換を確認。全 Node の一括実装はしない。`gouda_core` は `tools/hardcode_scan_roots.json` に登録済み（DR-15 合格）。基本契約の試験 TS-17〜21 の工程は同 §5。5-4 の速度マスク生成器は案 A 前提で着手可。
- 並行: 独自型 4 件の定義、G-FIRMWARE の設計、Q-02 の候補比較、mask 生成器（幅・刻みを引数）。
- 止まっている: DEC-050（実機照合）。design/ は `design/gate3-baseline-2026-10-09` ブランチにコミット済み（DEC-060。コミット 4b7bdbeb → 4a83d9f（セッション外）→ f208066 "Before gate 3 approved"、push 済み。第12便で 2eb94c2・0f02397 を push。REV-018 と第12便の記録は未コミット）。

## 主要ファイルの場所（CLAUDE.md 1.9 の対応表。パスはリポジトリ `tsukuba-autonomous-robot/` 相対）

| 役割 | 場所 | 備考 |
|---|---|---|
| 設計意図（人が所有） | `design/intent.md` | 第7版 103 行。旧版は `baselines/migration_v1/intent.md`（第1版）、`baselines/intent_history/`（第2〜7版の保存コピー） |
| 正本（YAML） | `design/model.yaml`、`design/schema.json`（1.1） | 変更は `revisions/REV-xxx.yaml` → `tools/apply_revision.py`。最新 REV-025 |
| 正本（Markdown） | `design/docs/` | `implementation_stages.md`（工程・完了条件）、`vehicle_output_timing.md`、`speed_filter_design.md`、`regulations_2026.md`、`git_management_plan.md` |
| 判断台帳 | `model.yaml: decisions`（原文。DEC-001〜075） | ビュー: `generated/pending_classification.md`、`conflicts.yaml`、`intent_open_items.yaml`、`generated/human_decisions_r2.md` |
| ゲート3 承認の対象 | `design/baselines/gate3_2026-10-09/`（条件付き承認時の凍結コピー＋README。最終承認はコミット f208066） | FILE-GATE3-MODEL として SHA-256 を検査 |
| 検査器・ルール一覧・試験 | `tools/validate_model.py`、`tools/check_design.py`、`rules/` | ルール一覧と根拠は `rules/README.md` |
| スクリプト | `tools/` | `run_checks.py` が全検査を実行し `reports/check_run.json` に記録。`render_views.py`・`generate_params.py`・`render_migration_review.py` で生成物を再生成 |
| 生成物（手編集禁止） | `generated/`（`gate3_package.md`、`review_r3.md`、`stop_resume_conditions.md`、`failure_modes.md`、`parameters_by_stage.md`、`measurement_plan.md`、`params/` ほか）、`conflicts.yaml`、`intent_open_items.yaml`、`intent_index.yaml`、`migration_review.md`、`reports/model_diff_rev-013.md` | |
| 提案 | `proposals/` | 承認済み仕様として使わない。`CLAUDE.md.repaired`／`.diff`（適用済み）、`intent_edit_requests.md`、`undetectable_faults_r2.md` |
| 調査・証拠 | `research/` | `claude_md/CLAUDE.md.original_2c90ed21`（修復前の原本）、`claude_md_inspection.md`、`vehicle_pc/`、`upstream_jazzy/`、`joystick270_firmware/`、`timing_values_h009.md`、`speed_filter_reapply_h011.md`、`nav2_version_survey.md` |
| 報告・作業記録 | `reports/`、`reports/worklog/` | 最新: `2026-10-09_rev024_025_stage5-4.md`。引き継ぎ: `reports/handover_2026-10-09.md`（追記あり） |
| baseline | `baselines/migration_v1/`（凍結、`snapshot.json`）、`baselines/intent_history/`、`baselines/gate3_2026-10-09/` | |
| 元資料 | `docs/Gouda_architecture_detail.xlsx`、`docs/SystemArchitecture.drawio`、`docs/extraction_20261008_01a11af4/` | 読み取り専用 |
| ロボット実装（新） | `gouda_interfaces/`（SoftwareMode・DecisionEvent・StartAutonomy）、`gouda_core/`（recorder・mode_manager・monitor・map_creator、glim_runner・map_database・map_convert・waypoints・speed_mask、web/）、`gouda.sh` | 工程5-1〜5-4。旧 scripts/gouda.sh・gouda_gui.sh・smoke.sh は削除（DEC-068）。gouda_gui 等の旧実装は置き換え対象 |
