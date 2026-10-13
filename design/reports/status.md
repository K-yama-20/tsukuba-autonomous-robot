# 現状の要約（status.md）

最終更新：2026-10-14（REV-043、第24便）。

**gouda_monitor に「地図」タブを新設**（intent.md 第9版 106 行目、DEC-092）。
- 原図を選び、変換設定を入力して再変換できる。変換のたびに新しい rev ができる。
- 人の回答: 高さの基準は地面（DEC-093）、今は GLIM を変えず移動して作った原図で密度を測る（DEC-096 C）、段差・坂の地図は確認用（DEC-097 A、条件付き承認。条件は確認中）。
- 変換を、点群から推定した地面からの高さで判定する方式にした（PRM-62〜64 を新設）。
- 1 つの rev として次を作る（DEC-095）。地図タブで切り替えて見られる。
  - 2D 占有格子（Nav2）
  - 3D 点群地図（PCD）
  - 表示用の傾き・段差・高さの図（走行には使わない）
- 確認: VM の試験スタック（実機の原図の写し）と DEMO。
- 暫定の推奨値は承認待ち（DEC-098）。実車の設定では既定値の欄は空で、値を入れれば再変換できる。
- これまでの原図はすべて静止して作られていた。地面の見え方（DEC-099）と点の密度・GLIM の処理周期（DEC-100）は、移動しての地図作成の実機試験（TS-34、手順 `docs/map_conversion.md` §5、解析 `map_inspect`）で測る。
- 作業記録 `reports/worklog/2026-10-14_rev039_040_map_tab.md`。

前便（第23便）: 起動経路を一つにした（`bash gouda.sh start` だけ、環境変数なし。DEC-090・DEC-091）。IMU 100 Hz、LiDAR 600 rpm を確定（REV-036〜038）。

前便（第22便）: センサーの受信表示と再接続時のドライバ作り直し（REV-034・035）。

前便（第21便）: GLIM の開始を VM で検証し、gouda.sh・mode_manager などの不具合を修正（REV-032・033）。

前便（第20便）: IMU デバイス名と XT-32 の時刻（PC 受信時刻）を確定、センサドライバの起動を実装（REV-031）。

前便（第19便）: XT-32 の IP・宛先・ポートと IMU の名前を宣言（REV-030）。

前便（第18便）: **工程5-5（車体出力）を実装し、Ubuntu の ROS 2 Jazzy 上で stub 試験合格（PC 側と firmware 中核の卓上 stub。ESP32 実機・車体なし）**。作業記録 `reports/worklog/2026-10-10_rev027_stage5-5.md`。次は DEC-076 の順序どおり、5-3 のセンサー有り試験 → 5-5 の実車試験（いずれも人のハード接続・判断が必要。着手前にセンサー・車体・ESP32 の接続状況を人に確認する）。実車向け firmware の書き込みは DEC-077（DAC 電圧の初期値）の回答待ち。

工程5-5 の内容: IFD-40 の独自型 `gouda_interfaces/msg/MotionHold` を確定、PC–ESP32 プロトコル v4 を設計（`docs/esp32_protocol_v4.md`、G-FIRMWARE）、ND-11 `gouda_motion_controller`・ND-12 `vehicle_bridge`（lifecycle node）、ND-17 新 firmware `firmware/gouda_esp32_v4`（PlatformIO、Bluepad32、MCP4922、NVS 設定）、mode_manager の `control/motion_hold` 発行、monitor の `/esp32/status` 表示。設定は generated/params から読み、未確定値は trial ファイル（stub 専用）。完了条件 (a) 手動優先 (b) 入力途絶時の中立化 (c) 一時停止中の中立出力 は、firmware 中核のホスト試験と PC 側の stub 試験で確認（実機・実車では未確認）。

前便まで: 工程5-1〜5-4 はソフト試験合格（5-3・5-4 はセンサーなし・合成データの範囲）。ゲート3は条件付き承認（DEC-064・065）。intent.md は第7版（`f69dd98b…`）。GLIM 1.2.2-0noble（DEC-062）。試験環境は Parallels の Ubuntu 24.04（`ssh -o BatchMode=yes aya@10.211.55.4`、`~/gouda_ws`。DEC-067）。firmware のビルド環境は Mac の PlatformIO（`~/.platformio/penv/bin/pio`）。

## 三つの状態（CLAUDE.md 1.4）＋報告用の三区分（DEC-057）

- 移行が正確：合格。初回移行 baseline（`baselines/migration_v1/`、凍結）を保持したまま REV-002〜043 を適用。違反 0。原資料・抽出結果・baseline の SHA-256 は一致（`reports/input_integrity.json`。作業ツリーの `docs/architecture/*.xlsx|drawio` に未コミットの変更があるが、検査対象の抽出コピーは不変）。
- 設計検査に合格：**未判定**。設計整合性 17 ルール 違反 0・未判定 4（DR-04 5 件、DR-05 2 件: RQ-I027・RQ-I072 は問題／衝突のみで対応、DR-10 2 件: 版照合、DR-11: 未確定値 59）。検査違反 0 件は未判定の解消でも実車適合の証明でもない。
- ソフト試験合格：**工程5-1〜5-5 が合格**（5-5: TS-07・TS-13・TS-19 PC 側・TS-12・TS-30 を Ubuntu で、TS-17・18・19・29 を firmware 中核のホスト試験と Python 模擬で。FILE-VEHICLE-PC-STAGE55）。5-3・5-4 はセンサーなし、5-5 は ESP32 実機・ゲームパッド・車体なしの範囲。TS-01〜06・08〜11・14〜16・20〜22 は未実行。
- 実車検証済み／実車投入可能：**人の判断待ち**。実車試験は未実施。承認済みの実車値は PRM-07・08・13・21 の 4 件のみ。DAC 電圧（PRM-43〜46）は未確定で、実車向け firmware ビルドには入っていない（DEC-077）。DEC-050 の実機照合は未実施。

## 検査結果の件数（`design/.venv/bin/python design/tools/run_checks.py`、終了コード 0、REV-043 適用後）

| 検査 | 合格 | 違反 | 未判定 |
|---|---|---|---|
| 入力の完全性（原資料・抽出・baseline・intent の SHA-256） | 一致 | 0 | 0 |
| 形式・移行忠実性 | 全件 | 0 | 0 |
| intent 版間の同一性 | 13（12 一致、1 記録済み置換） | 0 | 0 |
| 設定の生成（generate_params → generated/params/。firmware_config.trial.yaml を追加） | 生成 | 0 | 0 |
| 設計整合性（17 ルール） | 13 | 0 | 4（DR-04 5、DR-05 2、DR-10 2、DR-11 59） |
| 検査器の試験 | 68 | 0 | 0 |
| gouda_core 単体試験（Mac・VM、f5f9be8） | 127（Mac では 1 件 skip、VM ではすべて実行） | 0 | 0 |
| firmware 中核ホスト試験（g++、仮値ヘッダ。TS-17・18・19・29 の卓上 stub） | 274 checks | 0 | 0（実機未実行） |
| firmware ビルド（esp32dev・esp32dev_trial） | 2 | 0 | 0（書き込み未実施） |
| 工程5-1〜5-5 の ROS 上の試験（Ubuntu） | 合格 | 0 | 0（センサー・ESP32・実車は未接続） |
| ソフト試験（TS-01〜34） | 12（TS-07・12・13・17・18・19・23〜28・29・30 のうち stub 範囲） | 0 | 22（未実行または一部のみ。TS-31〜33 は一部を VM で実行: 作業記録。TS-34 は実機試験で未実行） |
| 判断台帳 | 98 件（answered 52、recorded 36、pending 10: DEC-021・022・024・050・077・078・079・098・099・100） | | |

## 承認待ち・実測待ち・人の作業・提案

- **承認待ち・実測（第24便、REV-042）**:
  - DEC-098 地図の変換の暫定の推奨値（PRM-33 0.1 m、PRM-34 0.1 m、PRM-35 0.15 m、PRM-36 1.2 m、PRM-38 1、PRM-62 0.5 m、PRM-63 10 度、PRM-64 1.0 m。高さは地面から）。推奨: 承認。止まる作業: 実車の設定での自動変換と地図タブの既定値。
  - DEC-097 の「条件付き承認」の条件の内容（回答に記載なし。確認中）。
  - 実測 DEC-099（XT-32 で地面が映るか）、DEC-100（移動して作った原図の点の密度、GLIM の処理周期・CPU 負荷・保存時間）。実機試験 TS-34 で測る（人の協力: 移動しての地図作成）。
  - 回答済み: DEC-093（高さの基準は地面）、DEC-094（B）→ DEC-096（C: 測ってから決める）、DEC-095（3D 点群地図と段差・坂の地図も作る）、DEC-097（A、条件付き）。
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
- 地図: DEC-098 の承認後に暫定値を設定へ反映。移動しての地図作成の実機試験（TS-34）の解析と記録（DEC-099・DEC-100）。
- 点群の配送の欠落（G-DDS）の調査: GLIM が受け取る周期の測定、Fast DDS の共有メモリ転送の容量・受信バッファの比較（上流は改変しない）。
- 並行して進められる基盤作業: PRM-16 の扱いの整理（承認事項）、Nav2 の cmd_vel 型（PRM-12）の決定に備えた ND-11 の TwistStamped 対応、5-6 の設計。
- 止まっている: 実車の設定での自動変換と地図タブの既定値（DEC-098）、実車向け firmware の書き込み（DEC-077）、実車試験、DEC-050。

## 主要ファイルの場所（CLAUDE.md 1.9 の対応表。パスはリポジトリ `tsukuba-autonomous-robot/` 相対）

| 役割 | 場所 | 備考 |
|---|---|---|
| 設計意図（人が所有） | `design/intent.md` | 第9版（SHA 183f8ee1…、106 行目まで）。旧版は `baselines/migration_v1/intent.md`、`baselines/intent_history/` |
| 正本（YAML） | `design/model.yaml`、`design/schema.json`（1.1） | 変更は `revisions/REV-xxx.yaml` → `tools/apply_revision.py`。最新 REV-043。次は REV-044、DEC-101 |
| 正本（Markdown） | `design/docs/` | `map_conversion.md`（地図の変換と地図作成の実機試験の手順）、`sensor_supervision.md`、`implementation_stages.md`、`esp32_protocol_v4.md`（5-5 のプロトコルと firmware の振る舞い）、`vehicle_output_timing.md`、`speed_filter_design.md`、`regulations_2026.md`、`git_management_plan.md` |
| 判断台帳 | `model.yaml: decisions`（DEC-001〜100） | ビュー: `generated/pending_classification.md`、`conflicts.yaml`、`intent_open_items.yaml`、`generated/human_decisions_r2.md` |
| ゲート3 承認の対象 | `design/baselines/gate3_2026-10-09/` | 最終承認はコミット f208066 |
| 検査器・ルール一覧・試験 | `tools/validate_model.py`、`tools/check_design.py`、`rules/` | `rules/README.md` |
| スクリプト | `tools/` | `run_checks.py`、`render_views.py`、`generate_params.py`（trial ファイルも生成）、`apply_revision.py` |
| 生成物（手編集禁止） | `generated/`（`params/` に node 別設定と `*.trial.yaml`、`firmware_config.yaml`・`.trial.yaml`）、`conflicts.yaml`、`intent_*.yaml`、`reports/*.json` | firmware のビルド時ヘッダ `firmware/gouda_esp32_v4/include/gouda_v4/build_config.hpp` はビルド時に生成（コミットしない） |
| 提案 | `proposals/` | 承認済み仕様として使わない |
| 調査・証拠 | `research/` | `vehicle_pc/`（工程 5-1〜5-5 の試験記録）、`joystick270_firmware/`、`upstream_jazzy/` |
| 報告・作業記録 | `reports/`、`reports/worklog/` | 最新 `2026-10-14_rev039_040_map_tab.md`。引き継ぎ `reports/handover_2026-10-10.md` |
| ロボット実装（新） | `gouda_interfaces/`（SoftwareMode・DecisionEvent・MotionHold・StartAutonomy・ConvertMap）、`gouda_core/`（recorder・mode_manager・monitor（地図タブの入力検査 map_tab.py）・map_creator（変換 map_convert.py、解析 map_inspect.py）・sensor_supervisor・motion_controller・vehicle_bridge、esp32_protocol・esp32_sim、web/、test/ に Ubuntu 試験 script）、`gouda.sh`（start／stop／status のみ、環境変数なし）、試験用 `gouda_core/test/stack.sh` | 工程5-1〜5-5 |
| firmware（新） | `firmware/gouda_esp32_v4/` | `include/gouda_v4/{protocol,config,control}.hpp`、`src/main.cpp`、`tools/gen_build_config.py`、`test/host/`。旧 `firmware/gouda_esp32`・`gouda_dualsense_usb` は置き換え対象 |
