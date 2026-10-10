# 現状の要約（status.md）

最終更新：2026-10-10（REV-028、第18便）。**工程5-5（車体出力）を実装し、Ubuntu の ROS 2 Jazzy 上で stub 試験合格（PC 側と firmware 中核の卓上 stub。ESP32 実機・車体なし）**。作業記録 `reports/worklog/2026-10-10_rev027_stage5-5.md`。次は DEC-076 の順序どおり、5-3 のセンサー有り試験 → 5-5 の実車試験（いずれも人のハード接続・判断が必要。着手前にセンサー・車体・ESP32 の接続状況を人に確認する）。実車向け firmware の書き込みは DEC-077（DAC 電圧の初期値）の回答待ち。

工程5-5 の内容: IFD-40 の独自型 `gouda_interfaces/msg/MotionHold` を確定、PC–ESP32 プロトコル v4 を設計（`docs/esp32_protocol_v4.md`、G-FIRMWARE）、ND-11 `gouda_motion_controller`・ND-12 `vehicle_bridge`（lifecycle node）、ND-17 新 firmware `firmware/gouda_esp32_v4`（PlatformIO、Bluepad32、MCP4922、NVS 設定）、mode_manager の `control/motion_hold` 発行、monitor の `/esp32/status` 表示。設定は generated/params から読み、未確定値は trial ファイル（stub 専用）。完了条件 (a) 手動優先 (b) 入力途絶時の中立化 (c) 一時停止中の中立出力 は、firmware 中核のホスト試験と PC 側の stub 試験で確認（実機・実車では未確認）。

前便まで: 工程5-1〜5-4 はソフト試験合格（5-3・5-4 はセンサーなし・合成データの範囲）。ゲート3は条件付き承認（DEC-064・065）。intent.md は第7版（`f69dd98b…`）。GLIM 1.2.2-0noble（DEC-062）。試験環境は Parallels の Ubuntu 24.04（`ssh -o BatchMode=yes aya@10.211.55.4`、`~/gouda_ws`。DEC-067）。firmware のビルド環境は Mac の PlatformIO（`~/.platformio/penv/bin/pio`）。

## 三つの状態（CLAUDE.md 1.4）＋報告用の三区分（DEC-057）

- 移行が正確：合格。初回移行 baseline（`baselines/migration_v1/`、凍結）を保持したまま REV-002〜028 を適用。違反 0。原資料・抽出結果・baseline の SHA-256 は一致（`reports/input_integrity.json`。作業ツリーの `docs/architecture/*.xlsx|drawio` に未コミットの変更があるが、検査対象の抽出コピーは不変）。
- 設計検査に合格：**未判定**。設計整合性 17 ルール 違反 0・未判定 4（DR-04: PRM-10 の値、DR-05: RQ-I027・RQ-I072 は問題／衝突のみで対応、DR-10: IFD-38 の版照合、DR-11: 未確定値 57。REV-027 で 11 件増）。検査違反 0 件は未判定の解消でも実車適合の証明でもない。
- ソフト試験合格：**工程5-1〜5-5 が合格**（5-5: TS-07・TS-13・TS-19 PC 側・TS-12・TS-30 を Ubuntu で、TS-17・18・19・29 を firmware 中核のホスト試験と Python 模擬で。FILE-VEHICLE-PC-STAGE55）。5-3・5-4 はセンサーなし、5-5 は ESP32 実機・ゲームパッド・車体なしの範囲。TS-01〜06・08〜11・14〜16・20〜22 は未実行。
- 実車検証済み／実車投入可能：**人の判断待ち**。実車試験は未実施。承認済みの実車値は PRM-07・08・13・21 の 4 件のみ。DAC 電圧（PRM-43〜46）は未確定で、実車向け firmware ビルドには入っていない（DEC-077）。DEC-050 の実機照合は未実施。

## 検査結果の件数（`design/.venv/bin/python design/tools/run_checks.py`、終了コード 0、REV-028 適用後）

| 検査 | 合格 | 違反 | 未判定 |
|---|---|---|---|
| 入力の完全性（原資料・抽出・baseline・intent の SHA-256） | 一致 | 0 | 0 |
| 形式・移行忠実性 | 全件 | 0 | 0 |
| intent 版間の同一性 | 13（12 一致、1 記録済み置換） | 0 | 0 |
| 設定の生成（generate_params → generated/params/。firmware_config.trial.yaml を追加） | 生成 | 0 | 0 |
| 設計整合性（17 ルール） | 13 | 0 | 4（DR-04 5、DR-05 2、DR-10 1、DR-11 57） |
| 検査器の試験 | 68 | 0 | 0 |
| gouda_core 単体試験（Mac・Ubuntu） | 89（5-5 で 33 件追加） | 0 | 0 |
| firmware 中核ホスト試験（g++、仮値ヘッダ。TS-17・18・19・29 の卓上 stub） | 274 checks | 0 | 0（実機未実行） |
| firmware ビルド（esp32dev・esp32dev_trial） | 2 | 0 | 0（書き込み未実施） |
| 工程5-1〜5-5 の ROS 上の試験（Ubuntu） | 合格 | 0 | 0（センサー・ESP32・実車は未接続） |
| ソフト試験（TS-01〜30） | 12（TS-07・12・13・17・18・19・23〜28・29・30 のうち stub 範囲） | 0 | 18（未実行） |
| 判断台帳 | 77 件（answered 38、recorded 32、pending 7: DEC-021・022・024・050・077・078・079）。model.yaml SHA `b512ec9a…` | | |

## 承認待ち・実測待ち・人の作業・提案

- **承認待ち（第18便、REV-027 で登録）**:
  - DEC-077 新 firmware の DAC 電圧の初期登録値（旧 firmware 記載の要求値 2500／230／4700／4700 mV を Q-03 実測までの初期値として承認するか）。推奨: 承認。止まる作業: 実車向け firmware の書き込み。
  - DEC-078 基本契約 5 件の stub 試験を 5-5 の完了条件に含める案（`docs/implementation_stages.md` §5）。推奨: 含める。
  - DEC-079 手動仲裁の既存値の維持（deadzone 8 %、中立安定 200 ms）。推奨: 維持。
  - 人の確認対象: プロトコル v4 で旧 v3 と異なる振る舞い（`docs/esp32_protocol_v4.md` §7。BT 途絶で PC 指令源を無効化しない等）。
- 前便からの回答待ち: intent 同一性チェッカーが記録済み置換を合格扱いにする変更の可否、122 件の design_status の扱い（推奨: 変えない）、旧 scripts の統合、rosbag の対象 topic（後工程）。
- 実測待ち: `generated/measurement_plan.md`（PRM-09・14・15・16・39〜49 を含む。承認済みの PRM-08・13 は除外済み）。PRM-16 は 5-6 の前に決める必要あり（motion_hold の期限切れ判定 PRM-42 が周期発行を前提とするため）。
- 実機照合待ち: DEC-050（配線・firmware・操作結果）、DEC-024（Q-09）。技術調査: DEC-021（Q-02）、DEC-022（Q-03）。
- 提案（承認済み仕様ではない）: `proposals/undetectable_faults_r2.md`、`proposals/intent_edit_requests.md` §2、`docs/git_management_plan.md`。

## 原本未照合

- 実車PC の Nav2 はパッケージ版（1.3.13）で照合。バイナリ内の IDL は直接読んでいない。
- 実機 ESP32 の配線・現在の firmware（DEC-050 未実施）。CLAUDE.md の先頭 1〜17 行の欠落は推測のまま。
- 前回分: 公式ページからリンクされた PDF、未読の図版。

## 次の作業

- DEC-076 の順序: (1) 工程5-3 の流れをセンサー有りで試験（実データで原図→変換。TS-27 の未確認項目）。センサー接続状況を人に確認してから。(2) 工程5-5 の実車試験（人の判断・協力。先に DEC-077・079 の回答→`esp32dev` ビルドに DAC 値→書き込み→卓上で TS-17〜19 の実機確認→DEC-050 の実機照合）。
- 並行して進められる基盤作業: PRM-16 の扱いの整理（承認事項）、Nav2 の cmd_vel 型（PRM-12）の決定に備えた ND-11 の TwistStamped 対応、5-6 の設計。
- 止まっている: 実車向け firmware の書き込み（DEC-077）、実車試験、DEC-050。

## 主要ファイルの場所（CLAUDE.md 1.9 の対応表。パスはリポジトリ `tsukuba-autonomous-robot/` 相対）

| 役割 | 場所 | 備考 |
|---|---|---|
| 設計意図（人が所有） | `design/intent.md` | 第7版 103 行。旧版は `baselines/migration_v1/intent.md`、`baselines/intent_history/` |
| 正本（YAML） | `design/model.yaml`、`design/schema.json`（1.1） | 変更は `revisions/REV-xxx.yaml` → `tools/apply_revision.py`。最新 REV-028。次は REV-029、DEC-080 |
| 正本（Markdown） | `design/docs/` | `implementation_stages.md`、`esp32_protocol_v4.md`（5-5 のプロトコルと firmware の振る舞い）、`vehicle_output_timing.md`、`speed_filter_design.md`、`regulations_2026.md`、`git_management_plan.md` |
| 判断台帳 | `model.yaml: decisions`（DEC-001〜079） | ビュー: `generated/pending_classification.md`、`conflicts.yaml`、`intent_open_items.yaml`、`generated/human_decisions_r2.md` |
| ゲート3 承認の対象 | `design/baselines/gate3_2026-10-09/` | 最終承認はコミット f208066 |
| 検査器・ルール一覧・試験 | `tools/validate_model.py`、`tools/check_design.py`、`rules/` | `rules/README.md` |
| スクリプト | `tools/` | `run_checks.py`、`render_views.py`、`generate_params.py`（trial ファイルも生成）、`apply_revision.py` |
| 生成物（手編集禁止） | `generated/`（`params/` に node 別設定と `*.trial.yaml`、`firmware_config.yaml`・`.trial.yaml`）、`conflicts.yaml`、`intent_*.yaml`、`reports/*.json` | firmware のビルド時ヘッダ `firmware/gouda_esp32_v4/include/gouda_v4/build_config.hpp` はビルド時に生成（コミットしない） |
| 提案 | `proposals/` | 承認済み仕様として使わない |
| 調査・証拠 | `research/` | `vehicle_pc/`（工程 5-1〜5-5 の試験記録）、`joystick270_firmware/`、`upstream_jazzy/` |
| 報告・作業記録 | `reports/`、`reports/worklog/` | 最新 `2026-10-10_rev027_stage5-5.md`。引き継ぎ `reports/handover_2026-10-10.md` |
| ロボット実装（新） | `gouda_interfaces/`（SoftwareMode・DecisionEvent・MotionHold・StartAutonomy・ConvertMap）、`gouda_core/`（recorder・mode_manager・monitor・map_creator・motion_controller・vehicle_bridge、esp32_protocol・esp32_sim、web/、test/ に Ubuntu 試験 script）、`gouda.sh`（GOUDA_SERIAL_PORT） | 工程5-1〜5-5 |
| firmware（新） | `firmware/gouda_esp32_v4/` | `include/gouda_v4/{protocol,config,control}.hpp`、`src/main.cpp`、`tools/gen_build_config.py`、`test/host/`。旧 `firmware/gouda_esp32`・`gouda_dualsense_usb` は置き換え対象 |
