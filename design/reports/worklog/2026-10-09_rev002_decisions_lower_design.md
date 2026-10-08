# 人の決定の反映（REV-002）と範囲を絞った下位設計案

作業日: 2026-10-08〜09。対象: 非常停止不採用の上位要求の反映、intent.md 新版の記録、境界要素の未確認化、ゲート3レビュー表、未提出成果物、C-006 の確認、4点の下位設計案、検査の分離。Node の実装、故障モード表・試験表を含む完成版の図表生成には進んでいない。

## 読み直したもの

- `design/reports/status.md`、直近の作業記録 `2026-10-08_model_migration.md`、CLAUDE.md（1.1〜1.9）、`design/intent.md`（現版 100 行、SHA-256 `1e087b30…`）、`design/model.yaml`・`schema.json`・`migration_manifest.json`・`migration_review.md`（初回移行 baseline、`design/baselines/migration_v1/snapshot.json` と一致）、抽出結果 `docs/extraction_20261008_01a11af4/`（excel_rows.jsonl、drawio_objects.jsonl）、`research/upstream_jazzy/`（前セッションで取得済み）。
- 実装リポジトリ `tsukuba-autonomous-robot` HEAD `a091ed39eb154b2dff7065840dc13c6478b153da`（作業ツリーに `docs/architecture/*.xlsx|drawio` の未コミット変更あり。触れていない）。
- 設計成果物は Git 管理外のため、対象版はファイルハッシュ（`reports/check_run.json`）で識別する。

## 人の回答（判断台帳 `model.yaml: decisions` に原文で記録）

- DEC-001（answered）: 「3項目とも新版に含める」→ intent.md 98〜100 行を上位要求 RQ-I070〜RQ-I072 とする。
- DEC-002（recorded）: 非常停止検知／PC側非常停止機構を存在させない（intent.md:100 と指示文の原文）。
- DEC-003（recorded）: 実車PC環境の申告「ROS2 jazzyをubuntu 24.0.5上で動かしています。aya@10.211.55.4」。認証情報は記録していない。
- DEC-004〜DEC-011（pending）: H-002〜H-008 と H-001 の質問。

## 機械確認した事実

- intent.md の差分: 旧版（`baselines/migration_v1/intent.md`、`a571d340…`）→ 新版は **98・99・100 行の 3 行追加、削除・変更なし**。指示文の「追記1文のみ」とは一致せず（AR-002 に `instruction_expected_added_lines: 1` / `observed_added_lines: 3` を記録）。DEC-001 により 3 行とも新版に含めた。検査器は「旧版コピー＋記録した追加行＝現ファイル」を毎回再構成して照合する。
- 原資料・抽出結果・baseline の SHA-256: すべて一致（`reports/input_integrity.json`）。intent.md のみ新版として記録。
- 非常停止語の検索（Excel 全シート・drawio 全要素、`generated/impact_estop.md`）: Excel 一致 10 行、drawio 6 要素。不採用は図の線 x5bDQh8FaZrcMh8EckeY-164 とラベル -165 の押下検知機能のみ（C-017）。M-028・IF-032 はハードウェア事実として参照保持。観測不可の記載 8 箇所は範囲外・保持。
- 実車PC への鍵認証は拒否（`Permission denied (publickey,password)`）。パスワード認証は AI の方針で行わず、版は未照合（V-001）。

## 自律判断した変更と理由

- モデルの変更を「変更セット `revisions/REV-002.yaml` → `tools/apply_revision.py` で適用」に統一した。理由: 初回移行 baseline を凍結したまま追加・変更を記録し（削除禁止）、検査器が baseline との差分を記録と照合できるようにするため。初回移行の全件一致検査は「baseline ⊆ 現在、追加＝記録」に置き換えたが、原文・ID・出典・図の照合はそのまま残した（条件の緩和ではなく、追加の記録義務を課した）。
- スキーマ 1.1（`tools/model_schema.py`。1.0 の上に `authority_revisions`・`revisions`・`decisions`・`ros_node`・`designed_interface`・遷移/状態の payload・`boundary` を追加）。1.0 の記録はすべて有効。
- 境界が曖昧な要素（Safety_gate 系 8 件、collision_stop_request 2 件、heartbeat 9 件）に `boundary: 未確認` を付け、検査 DR-07 で設計要素からの使用を禁止した。
- C-014／U-DRAW-002 は「上位要求により不採用（C-017）」として整理し、資料間の不一致は履歴として `open` のまま保持（U-DRAW-002 は `partially_superseded`、resolution_refs=[C-017]）。
- C-006 に `clarification` を追記（固定4段階ではなく依存順序。RQ-I069 で必要な処理だけ）。原文で解消できない「復旧不能時の遷移先」は C-019／H-006 に分離。
- C-001〜C-013 に `retained_scope`（置換しない範囲）を追記。行全体の破棄は図の 2 要素のみ（DR-12 で機械確認）。
- 生成ファイルの置き場所: `conflicts.yaml`・`intent_open_items.yaml`・`intent_index.yaml` は指示どおり `design/` 直下に置いた（CLAUDE.md 1.9 の `generated/` ではない）。先頭行に「GENERATED」を明記し、手編集しない。
- Nav2 上流の追加証拠を同じコミット（645abd95）で取得するよう `collect_official_specs.py` を改修（commit を evidence.json で固定）。
- 下位設計案の名称（ND-xx、IFD-xx、TR-xx、SO-xx、PRM-xx）は新規ID。既存IDは再採番していない。

## 承認事項・実測待ち（人の判断）

`generated/human_decisions_r2.md`（影響IDの件数順）。新規: H-002 Safety_gate、H-003 collision_stop_request、H-004 heartbeat、H-005 base_link 軸定義（RQ-I071 と REP-103 の衝突。最初に決める必要）、H-006 復旧不能時の遷移先、H-007 PC再起動後の初期化、H-008 地図作成終了後のモード。更新: H-001（上流 jazzy での 3 案比較。推奨は Gouda 側の単一発行器）。既存: Q-04〜Q-07、Q-10、Q-12。実測待ち: Q-05 の全値、PRM-08〜PRM-12。

## 実行した検査・試験

コマンド（ワークスペース直下、プロジェクト内仮想環境）:

```sh
design/.venv/bin/python design/tools/apply_revision.py REV-002
design/.venv/bin/python design/tools/run_checks.py
design/.venv/bin/python design/tools/render_migration_review.py
design/.venv/bin/python design/tools/render_views.py
```

結果（対象: `design/model.yaml` ほか、ハッシュは `reports/check_run.json`）:

| 検査 | 結果 |
|---|---|
| 入力の完全性 | 合格（原資料・抽出・baseline 一致。intent は AR-002 として検証） |
| 形式・移行忠実性（validate_model.py） | 合格。5,839 比較・規則、違反 0。終了コード 0 |
| 設計整合性（check_design.py） | 違反 0、未判定 4 ルール（DR-04 人の判断待ち 8 件、DR-05 問題だけで対応 2 件、DR-10 版照合待ち 6 件、DR-11 値未確定 30 件）、合格 9。終了コード 0 |
| 検査器の試験 | 50 件合格（意図的違反の検出を含む）。終了コード 0 |
| ROS 動作・実車試験 | 未実行 |

修正の原因分類（検査を通すまでに直したもの）: 実装（変更セット YAML の記法誤り、スキーマで owner_ref を null 可にしていなかった、派生ビューへの reconciliation 参照の継承漏れ、DR-10/DR-13 の判定条件が GLIM 版依存や「流用しない」文を誤検出）。試験（試験基盤: 最小 fixture の schema_version、対応漏れ試験の対象要求）。期待値・合否基準は変えていない。

## 残るリスク

- 実車PC の ROS 2／Nav2 版が未照合（V-001）。版依存 IF（IFD-13〜15, 24, 32, 35）は案。
- RQ-I071 の軸定義と REP-103／Nav2 の衝突（C-018）が未決のまま TF・footprint・Nav2 設定に進めない。
- 一時停止・終了時の PC 側遮断は Nav2 取消＋途絶中立の単経路（H-002 の回答まで）。
- CLAUDE.md（プロジェクト直下）に行番号付きリストの貼り付け痕（先頭が「18」「19### 1.1 …」）があり、1〜16 行が欠けている可能性。人の所有ファイルのため未修正。
- 実装リポジトリ `docs/gouda_protocol_v3.md` は ESP32 プロトコルの候補資料だが、設計側では原本未照合（Q-03）。

## 更新・追加した生成物

正本・変更: `design/model.yaml`（REV-002 適用。733 要素、489 出典。追加 104、変更 74、削除 0）、`design/schema.json`（1.1）。
新規: `design/revisions/REV-002.yaml`、`design/tools/{model_schema,apply_revision,check_design,run_checks,render_views}.py`、`design/rules/test_check_design.py`、`design/generated/{gate3_review_C001_C013,impact_estop,lower_design_r2,human_decisions_r2}.md`、`design/conflicts.yaml`、`design/intent_open_items.yaml`、`design/intent_index.yaml`、`design/reports/{design_check.json,design_check.txt,input_integrity.json,check_run.json,model_diff_r2.md}`、`design/research/nav2_version_survey.md`、`design/research/upstream_jazzy/`（6 ファイル追加）、`design/proposals/undetectable_faults_r2.md`、`design/docs/git_management_plan.md`。
更新: `design/tools/{validate_model,render_migration_review,collect_official_specs}.py`、`design/rules/{test_validate_model.py,README.md,fixtures/minimal.yaml}`、`design/migration_review.md`、`design/reports/{migration_validation.json,migration_validator.txt,migration_tests.txt}`、`design/reports/status.md`。
変更していない: `design/intent.md`、原資料、抽出結果、`design/baselines/migration_v1/`、`design/migration_manifest.json`、`design/tools/build_migration.py`、実装リポジトリ。

## 次に進められる作業と止まっている作業

進められる: V-001 の照合手順の受け取りと evidence 化、H-005 以外の TF 以外の IF の型定義の詰め（独自型 4 件の .msg/.srv/.action 案）、記録（gouda_recorder）の詳細設計、検査ルールの追加（遷移 guard の要求参照）。
止まっている: TF・footprint・Nav2 設定（H-005）、SpeedLimit 発行器の実装（DEC-011）、Safety_gate／heartbeat 系の設計（H-002/H-004）、復旧手順の最終形（H-006/H-007）、実車値（Q-05）。

---

# 追記: REV-003（H-005 の回答、実車PC版の照合）

人の回答（原文を判断台帳に記録）:

- DEC-007（answered）: 「lidarやIMUの座標方向はgouda_monitorで指定することとし、内部でNav2前提の方向に変換する方針を採用する。」→ H-005 を resolved、C-018 を resolved_by_decision。base_link/base_footprint は REP-103、センサ座標方向は gouda_monitor の /config（IFD-26、SO-03）で指定し、静的TF発行（ND-13）が回転として変換。PRM-07 を承認済み（approval_decision_ref DEC-007）。intent.md:99 の文言は人の所有のため未変更。更新するかは P-001／DEC-013 として提示。
- DEC-012（recorded）: 実車PC の確認コマンド出力の原文。Ubuntu 24.04.5 LTS、/opt/ros/jazzy、Nav2 1.3.13。`research/vehicle_pc/2026-10-09_vehicle_pc_versions.txt` を FILE-VEHICLE-PC として登録。V-001・Q-01 を resolved。IFD-13/14/15/24/32 を `confirmed_installed_version`（パッケージ版の一致。バイナリ内 IDL の直接照合はしていない）。

自律判断: スキーマ 1.1 に issue.state `resolved`、reconciliation.state `resolved_by_decision`＋`decision_ref`、adoption `approved`＋`approval_decision_ref`、version_dependency `confirmed_installed_version` を追加し、検査器に「resolved は resolution_refs 必須」「resolved_by_decision は回答済み決定が必須」「承認済みは出典または回答済み決定が必須」「実車版照合済みは実車PC証拠ファイル必須」を追加。上流 jazzy で map_server・Costmap2DPublisher・planner_server の QoS を同じコミットで確認し IFD-24/32 に反映。修正の分類: 実装（REV-003 適用時に AR-002 で追加した行 98〜100 を要求行として認識していなかった、後続リビジョンで変更した要素の照合先が baseline になっていた）、試験（DR-10 の試験対象を照合済みになった IFD-13 から IFD-35 へ変更）。期待値・合否基準は変えていない。

検査（`design/.venv/bin/python design/tools/run_checks.py`、終了コード 0）: 入力の完全性 合格、移行忠実性 5,841 項目 違反 0、設計整合性 違反 0・未判定 4 ルール（DR-04 8 件、DR-05 2 件、DR-10 1 件＝IFD-35 GLIM、DR-11 29 件）、試験 53 件合格。問題 34 件（技術 12、資料不足 7、人の判断 15。うち resolved: Q-01、V-001、H-005）。承認済み 1 件（PRM-07）。残り pending: DEC-004〜006、008〜011、013。

---

# 追記: REV-004（2026-10-09 の人の回答一括反映、intent.md 第3版）

## 読み直し・照合

- intent.md 第3版（SHA-256 `f0df295f…`）: 第2版との機械比較で 87 行挿入（判断台帳の記録義務）、99→100 行の置換（座標系の文）、102 行追加（車体出力段階の値）。指示文の言及は追記 1 件だが、3 箇所すべてを人の編集として AR-003 に記録（削除・置換を許す上位要求版の記録に拡張。比較先は保存コピーに固定）。第2版の保存コピー `baselines/intent_history/intent_v2_1e087b30ddb6.md` は AR-002 の記録から再構成し、ハッシュ一致を確認。
- 実装リポジトリ（HEAD a091ed39）の照合: `gouda_vehicle/hardware_bridge.py` は protocol v3 の STATUS を `/esp32/status`（String JSON）へ公開、STATUS 鮮度 0.25 s 不足または drive 鮮度不足で DISARM（既存の停止条件）。firmware `gouda_dualsense_usb` は `kLinkTimeoutMs=250`（BT・PC 指令）。旧 firmware `gouda_esp32` も 250 ms。どちらが実機に書き込まれているかは資料から判別できない（H-010）。gouda_protocol_v3.md は「firmware does not read or report an emergency-stop switch」と明記。

## 人の回答（判断台帳に原文で記録）

DEC-004（H-002 motion_hold 直接入力）、DEC-005（H-003 不採用）、DEC-006（H-004 表示・診断のみ、既存停止条件は外さない、不明表示）、DEC-008（H-006 直前モード維持）、DEC-009（H-007 初期位置の再指定）、DEC-010（H-008 手動走行へ、変換は処理状態）、DEC-011（H-001 暫定採用＋5項目）、DEC-013（P-001）、DEC-014（Q-10）、DEC-015（Q-07 後工程）、DEC-016（Q-12 旧5 m 不採用）、DEC-017（Q-04/05/06 保留とパラメータ一覧の指示）、DEC-019（工程5の進め方）、DEC-020（intent 第3版）。RQ-I073 により旧Q・資料不足の未決にも台帳項目を補った（DEC-021〜028、pending）。

## 自律判断

- 削除・置換を含む上位要求版の機械検証（旧版保存コピー＋削除行＋追加行＝新版）に拡張。要求行の対応は行番号ではなく原文一致で検査（版をまたいで行番号がずれるため）。置換された RQ-I071 は C-021（resolved_by_intent）で RQ-I074 に置換し、参照先を一括置換。
- motion_hold（IFD-40）は人の回答どおり mode_manager → motion_controller の直接入力として設計。Safety_gate・supervisor（M-013・M-014・IF-024〜027・IF-045）は不採用として記録（行は保持）。
- collision_stop_request（図の線と注記）は不採用（C-020）。heartbeat 系は「未確認」を外し表示・診断のみ（IFD-38）。
- SpeedLimit 発行器の 5 項目は `docs/speed_limit_publisher.md`・IFD-14・SO-01（goal_waypoint_offset・current_section_index）・試験 TS-01〜06 に落とした。初回区間（開始地点→W[0]）の上限の扱いは要確認として残した。
- 車体出力段階の値: intent.md:102 の 700 ms／1 s を source_value として保持し、firmware の 250 ms との不一致と 700 ms の配分を H-009 として提示（推奨は既存 firmware 維持・PC 側 timeout を controller 周期の数倍。例示値は計算値で実車採用値ではない）。
- 旧リビジョンの再適用のため、REV-002/REV-003 に比較先の intent 版（保存コピー）を追記。変更内容は変えていない。
- 修正の分類: 実装（出典 ID が版をまたいで衝突、行番号の版違い、再適用時の比較先、数値照合の桁処理）、試験（境界要素が解消したため試験側で境界を注入）。期待値・合否基準は変えていない。

## 検査（`design/.venv/bin/python design/tools/run_checks.py`、終了コード 0）

入力の完全性 合格。移行忠実性 5,855 項目 違反 0。設計整合性 14 ルール: 違反 0・未判定 4（DR-04 7 件＝H-001 正式承認・Q-05 値、DR-05 2 件、DR-10 2 件＝GLIM 版・実機 firmware 版、DR-11 33 件＝値未確定）。試験 55 件合格。問題 36 件（技術 12、資料不足 7、人の判断 17。うち resolved: Q-01, Q-10, Q-12, V-001, H-002〜H-008, P-001。deferred: Q-07, Q-13）。承認済み 1 件（PRM-07）。判断台帳 29 件（answered 14、recorded 5、pending 10）。

## 成果物

新規: `revisions/REV-004.yaml`、`generated/review_r3.md`（遷移表・IF・故障時の対応・試験の期待結果）、`generated/parameters_by_stage.md`、`docs/speed_limit_publisher.md`、`baselines/intent_history/`。更新: model.yaml（REV-004: 追加 29、変更 75、削除 0）、schema.json、検査器・試験、生成物一式、`research/nav2_version_survey.md`、status.md。変更なし: 原資料・抽出・baseline（migration_v1）、実装リポジトリ。

## 残るリスク・次の作業

- ゲート3の承認まで工程5は暫定（DEC-019）。レビュー資料は `generated/review_r3.md`。
- H-009（値の不一致）と H-010（実機 firmware）が車体出力段階の前提。H-001 の正式承認は人。
- センサ取付値（RQ-I070）・Q-05 の実車値は未確定。パラメータ一覧は `generated/parameters_by_stage.md`。

---

# 追記: REV-005（2026-10-09 第2便の回答、intent.md 第4版）

## 読み直し・照合

- intent.md 第4版（SHA `6b7ab4b1…`、103 行）: 第3版に 103 行「実測値はプログラムにハードコードせず、宣言的に書く。」が追加（チャットでの言及なし。機械比較で検出）。AR-004 として記録し RQ-I076 を付与。第3版の保存コピー `baselines/intent_history/intent_v3_f0df295f9927.md` を作成し、REV-004 の比較先を固定。
- 参照 firmware `Joystick270-Firmware`（commit 2961d372）を `research/joystick270_firmware/src` に読み取り専用で取得（57 ファイル、SHA-256 一覧）。ビルド・実行はしていない。抽出は `research/joystick270_firmware/extract.md`。
- 上流 jazzy の `speed_filter.cpp`: SpeedLimit は値が変わったときだけ発行（242-258 行）。filter info・mask は transient_local 購読。
- 実装リポジトリの GLIM: `docs/gouda_recording_glim.md` が apt `ros-jazzy-glim-ros`（CPU）を導入、確認 VM で 1.2.2-0noble（版固定なし）。

## 人の回答（判断台帳に原文で記録）

DEC-030（H-010: firmware 書き直し、参照リポジトリ）、DEC-031（H-001: Speed Filter が発行）、DEC-032（実車値: AI が測定計画と採用根拠、人が実測協力と採用判断。原文は途中で終わっている）、DEC-033（GLIM 版: AI が技術選定可）、DEC-034（firmware 版: H-010 に一本化）、DEC-035（H-009 の対応表の指示）、DEC-036（intent 第4版）。

## 自律判断

- H-001 を Speed Filter 発行に変更。IFD-14 の発行元を ND-10（costmap SpeedFilter）、速度マスクのファイル契約 IFD-41（waypoint 保存時に ND-02 が生成）、Nav2 標準 server による配信 IFD-42、PRM-19（帯の半幅）・PRM-20（速度刻み）を追加。帯の幅と帯外の扱いは H-011 として人へ。DEC-011 の 5 項目は Speed Filter 方式で再評価し、「controller のみ再起動した場合は値が変わるまで再適用されない」という Nav2 の挙動を制約として記録（TS-06）。`docs/speed_limit_publisher.md` は履歴、現行は `docs/speed_filter_design.md`。
- H-010 は書き直しで解消。新 firmware を ND-17（lifecycle=firmware）・SO-11・IFD-43 として追加し、設計タスクを G-FIRMWARE に一本化（DEC-034）。参照 firmware の手動経路（純正ジョイスティックへのリレー切替、Bluetooth なし）と基本契約（RQ-I023・RQ-I024）の差は H-012 として提示し、AI は推奨を出さない（基本契約の変更可否は人）。
- H-009 の対応表 `research/timing_values_h009.md`（値ごとの入力・判定部品・期限切れ動作・コード位置、要求値維持時の変更箇所、250 ms 採用時の要求変更）。firmware を書き直すため現 firmware の 250 ms は参考値に位置づけた。
- GLIM 版: apt `ros-jazzy-glim-ros`（CPU 版）を AI が選定（DEC-033）。版は実車PC の `dpkg -l | grep glim` の出力で固定する（未取得のため IFD-35 は unconfirmed のまま）。
- 実測計画 `generated/measurement_plan.md` をパラメータの measurement 欄から生成（DEC-032）。
- RQ-I076（宣言的に書く）は IFD-26・ND-11・ND-12・ND-13・ND-17 の要求参照に追加。
- 修正の分類: 実装（試験名の変更を payload に置いていた、新規要素への modification、検査 DR-06 の除外語「行わない」）。期待値・合否基準は変えていない。

## 検査（`design/.venv/bin/python design/tools/run_checks.py`、終了コード 0）

入力の完全性 合格（intent は第2〜4版の連鎖を保存コピーから検証）。移行忠実性 5,862 項目 違反 0。設計整合性 14 ルール: 違反 0・未判定 4（DR-04 5 件＝Q-05、DR-05 2 件、DR-10 2 件＝GLIM 版・新 firmware、DR-11 未確定値）。試験 55 件合格。問題 39 件（技術 13、資料不足 7、人の判断 19）。判断台帳 35 件（answered 19、recorded 7、pending 9）。承認済み 1 件（PRM-07）。

## 残るリスク・次の作業

- H-012（新 firmware の手動経路）が基本契約に関わるため最優先。H-009（時間値）、H-011（マスクの幅）。DEC-032 の文の続きの確認。GLIM 版固定のための dpkg 出力。
- Speed Filter 方式では controller 単独再起動後の上限再適用が Nav2 の挙動に依存する（TS-06 で記録。Nav2 は改変しない）。
- ゲート3の承認まで工程5は暫定（DEC-019）。レビュー資料 `generated/review_r3.md` は REV-005 を反映。

---

# 追記: REV-006・REV-007（2026-10-09 第3便、intent.md 第5版）

## 読み直し・照合

- intent.md 第5版（SHA `81d71f07…`、104 行）: 第4版に 104 行「リレーによる切り替え機能は使わない。esp32が電源に接続されている限り、常にdacが電圧を出す。」が追加（DEC-037 と同文）。第4版の保存コピーを AR-004 の記録から再構成（ハッシュ一致）し `baselines/intent_history/intent_v4_6b7ab4b145fb.md` に保存。AR-005 として記録、RQ-I077。
- Speed Filter の復帰後の再適用を、採用版（実車PC 1.3.13＝上流 645abd95）のソースと nav2_bringup の既定で調査: フィルタの載る costmap は param `filters` で選ぶ（local costmap は controller_server 内、global は planner_server 内）。costmap の cleanup→configure でフィルタは再生成され `speed_limit_prev_` が初期化されるが、deactivate→activate では保持される（`costmap_filter.cpp:97-110`、`speed_filter.cpp:53, 262-271`、`costmap_2d_ros.cpp:367-377`）。lifecycle_manager は bond 切断で全 node を hard reset し respawn 後に全体を startup する（`lifecycle_manager.cpp:44-46, 481-545`）。SpeedLimit の QoS は発行・購読とも QoS(10) volatile。docs.nav2.org のページ取得は API 422 で失敗（ソースのみを根拠にした）。
- AR-004 の同一性確認: `tools/check_intent_identity.py` で RQ-I023〜027・RQ-I062〜069 の行を第3版と現版で比較。13 件すべて行テキストの SHA-256 一致、行番号も一致。差分は 103・104 行の追加のみ（`reports/intent_identity.md`）。

## 人の回答（判断台帳に原文で記録）

DEC-037（H-012: リレー不使用、DAC 常時出力、参照 firmware は実機で動作確認済み）、DEC-038（H-011 の指示: 根拠提示、区間上限と領域上限の区別、定義方法の整理、6 km/h 超可）、DEC-039（復帰後の再適用の調査・(a)(b) 比較・TS-06 合格条件）、DEC-040（DEC-032 の入力ミス削除）、DEC-041（AR-004 の完了条件）、DEC-043（intent 第5版）。pending: DEC-042（手動経路は Bluetooth ゲームパッド→ESP32→DAC で確定かの確認）。

## 自律判断

- H-011: 前回の推奨「帯外に最低速度を敷く」は運用方針の追加のため取り下げ、定義方法（帯幅・重複・帯外・マスク外・未読込・cell 0 の意味）だけを `research/speed_filter_reapply_h011.md` §3 に整理。マスク外・未読込時は「無制限になる」のではなく「発行されない」（直前値または上限なし）ことを `speed_filter.cpp:181-200` で確認し、開始条件に mask 配信の確認を入れた。
- H-001 を人の最終判断待ち（partially_superseded）に戻し、(a) cleanup→configure を伴う復帰手順、(b) Gouda 側単一発行器、の比較表に「復帰後の再適用」の行を加えた（同 §5）。TR-13 に (a) の復帰手順、TS-06 に合格条件「同じ cell に留まったまま再起動しても現在の上限が controller へ再適用されること」と、deactivate→activate のみでは不合格になる予測を記載。
- RQ-I076（宣言的に書く）の実現: parameter に declaration（ros_parameter／bt_xml／launch_argument／config_yaml／firmware_config／model_declared／code_state_machine）・target・param_key・value_type・apply_timing を追加し PRM-01〜20 に設定。`tools/generate_params.py` が正本から `generated/params/`（node 別 ROS parameter ファイル、firmware 設定、BT 置換値、index.json）を生成。未確定値はコメントの tbd 一覧にし値を入れない。検査 DR-15（宣言の重複、宣言先・型・適用時期の欠落、生成物と正本の不一致、承認値のリテラル混入の走査）と試験 3 件を追加。宣言（モデル→生成）と実行（TR/SO）の区別は review_r3.md §4b。
- ND-17 をリレー不使用・DAC 常時出力に更新。手動経路の読み（Bluetooth ゲームパッド）は推測のため DEC-042 で確認を求める。
- 修正の分類: 実装（DR-15 の対象を設計パラメータに限定、再適用時の比較先の固定）。期待値・合否基準は変えていない。

## 検査（`design/.venv/bin/python design/tools/run_checks.py`、終了コード 0）

入力の完全性 合格。パラメータ生成 合格。intent 同一性 合格（13 件一致）。移行忠実性 5,869 項目 違反 0。設計整合性 15 ルール: 違反 0・未判定 4（DR-04 7、DR-05 2、DR-10 2、DR-11 未確定値）。試験 58 件合格。問題 39 件。判断台帳 42 件（answered 20、recorded 12、pending 10）。承認済み 1 件。

## 残るリスク・次の作業

- H-001 の最終判断（(a)/(b)）→ H-011 の承認。H-009 の値。DEC-042 の確認。H-012 の「実機で動作確認済み」は人の申告で資料未照合。
- GLIM 版固定のための dpkg 出力。ゲート3の承認まで工程5は暫定。

---

# 追記: REV-008（2026-10-09 第4便）

## 人の回答（判断台帳に原文で記録）

DEC-044（AR-004 受理。DR-15 の検出項目と試験の対応、正当な設定の非検出を示せば十分）、DEC-045（再訪・重複ルートは同じ値、重複時は低い上限、境界の揺らぎは実機調整で新しい人の判断事項にしない）、DEC-046（復帰手順を 1 つに定め、TS-06 は同じ cell での deactivate→activate と cleanup→configure の 2 経路、合格条件は controller が実際に保持する上限の一致）、DEC-047（マスク外・未読込で何も発行されない状態を区別して記録）、DEC-048（ESP32 watchdog は最後の有効指令から 1 s、cmd_vel 途絶 700 ms、Bluetooth 途絶 250 ms は別の既存動作で撤去しない）、DEC-049（優先順位）。

## 反映

- H-001 解消: Speed Filter（DEC-031）＋復帰手順 cleanup→configure→activate（TR-13）。H-011 解消: 重複 cell は低い方の上限、帯幅 PRM-19 は tbd、帯外は Nav2 の挙動。H-009 解消: PRM-13=1.0 s、PRM-08=0.7 s を承認値（DEC-048）、PRM-21=0.25 s（Bluetooth 報告の途絶。既存動作を新 firmware でも維持）を追加。承認済み 4 件（PRM-07・08・13・21）。
- マスク外・未読込の記録: ND-03 が mask・filter info の latched 配信、speed_limit の最終受信値・時刻、位置が mask 範囲内かを観測し speed_limit_application_state を IFD-01・DecisionEvent に記録、monitor 表示（SO-01、TS-15）。発行はしないので単一発行元を維持。
- TS-06: 2 経路と「再走行前に controller が実際に保持している上限」の一致（controller は上限を公開しないため直線 stub 経路の cmd_vel 最大値で観測）。TS-16: 低速帯進入試験（揺れ幅・継続時間・減速距離の許容値 PRM-22〜24 は実測で決め、人の判断事項にしない）。
- 優先 1 の整理: docs/vehicle_output_timing.md（手動優先と途絶時中立化の入力・判定部品・期限・動作）。
- DR-15 の検出項目と試験の対応表を rules/README.md に追加。正当な設定の非検出試験（別 target の同じキー、実モデル違反 0）を追加。ハードコード走査の対象は tools/hardcode_scan_roots.json（新実装ができたら追加。旧実装は置き換え対象のため対象外。空のため現状 0 件）。
- 修正の分類: 実装（新規要素の approval_decision_ref を適用器が受け付けていなかった、firmware 設定キーの単位表記 ms と秒値の不一致 → キーを `_s` に統一、ハードコード走査の対象を旧実装から外した）。期待値・合否基準は変えていない。

## 検査（`design/.venv/bin/python design/tools/run_checks.py`、終了コード 0。baseline から REV-002〜008 を再適用して確認）

入力の完全性・パラメータ生成・intent 同一性 合格。移行忠実性 5,869 項目 違反 0。設計整合性 15 ルール 違反 0・未判定 4（DR-04 5、DR-05 2、DR-10 2、DR-11 未確定値 38）。試験 59 件合格。問題 39 件（人の判断 open: Q-04・Q-05・Q-06 のみ）。判断台帳 48 件（answered 25、recorded 13、pending 10）。

## 残る作業

- DEC-042（手動経路の読みの確認）、GLIM 版固定の dpkg 出力、ゲート3の承認。
- 優先 2〜4 の設計・試験は案として整備済み。実装（工程5）はゲート3の承認後。

---

# 追記: REV-009（2026-10-09 第5便: CLAUDE.md 検査、判断台帳の分類、ゲート3 資料）

## CLAUDE.md の検査（読み取り専用。原本は変更していない）

- 照合先: 実装リポジトリの Git 履歴（CLAUDE.md は未追跡）、ワークスペースの .bkp（drawio のみ）、mi エディタの DocumentData（設定のみ）、`~/.claude/CLAUDE.md`（別ファイル）、Spotlight の他コピー（無関係）。原本・旧版は見つからず。
- 構造: 1 行目の見出しのみ番号なし。2〜186 行は `<整数><本文>` で整数は 18〜202 と途切れなく連続。空行は番号のみの行。貼り付け時の行番号混入と判断。
- 「先頭 1〜17 行の欠落」は推測のまま（本文を補っていない）。
- 修復差分: `tools/repair_claude_md.py`（連続番号の先頭整数を除くだけ。本文は不変、追加なし）→ `proposals/CLAUDE.md.repaired`（SHA `4e071b7e…`）、`proposals/CLAUDE.md.diff`、根拠 `reports/claude_md_inspection.json`・`research/claude_md_inspection.md`。sed による独立確認で一致。承認は DEC-052（pending）。承認まで CLAUDE.md の指示に依存する新規作業は止める。本便は台帳整理・既存資料の照合のみ。

## 判断台帳の分類（DEC-051）

decisions に `disposition` を追加。既存決定で解消（閉じる）: DEC-023（Q-08、根拠 C-004/RQ-I011）、DEC-026（Q-13、S-02/DEC-015）、DEC-027（U-DRAW-001、図は参照のみ）、DEC-028（U-HISTORY、履歴）、DEC-029（H-009、DEC-048）。ゲート3 で一括承認: DEC-025（Q-11）。本当に未決の人の判断: DEC-052（CLAUDE.md 修復差分の承認）。技術調査・実測待ち（承認待ちから外す）: DEC-021（Q-02）、DEC-022（Q-03）。実機照合待ち: DEC-024（Q-09）、DEC-050。DEC-042 は設計前提（answered、「これは確定である」）と実機照合（DEC-050、pending）に分割。H-001 の台帳上の経緯（DEC-011→031→039→046、現在 resolved）を記録。一覧は `generated/pending_classification.md`。

## ゲート3 資料

`generated/gate3_package.md`: 承認対象（designed_proposal 全件と answered 決定）、承認で着手する作業（下位設計の継続と工程5-1 以降の実装。実車試験への移行は別判断）、未確定と止まる作業、上位要求からの変更・例外（AI による変更なし。RQ-I071 は人の編集で置換）、C-001〜C-013 の置換範囲が intent 該当文に収まるかの確認（全件「収まる」。C-006 の復旧不能時の遷移先は intent から一意でなく DEC-008 で人が決めた補足、C-012 の薄い adapter は置換ではなく設計案）。

## 検査（`design/.venv/bin/python design/tools/run_checks.py`、終了コード 0）

入力の完全性・パラメータ生成・intent 同一性 合格。移行忠実性 違反 0。設計整合性 15 ルール 違反 0・未判定 4。試験 59 件合格。判断台帳 51 件（answered 26、recorded 19、pending 6: DEC-021・022・024・025・050・052）。
修正の分類: 実装（decisions の disposition を必須にしていたスキーマ生成の誤り）。

---

# 追記: リポジトリへの格納（2026-10-09）

- 設計一式をワークスペース直下 `design/` から実装リポジトリ `tsukuba-autonomous-robot/design/` に複製（`.venv`・`__pycache__`・参照 firmware の `.git` を除く）。以後はリポジトリ内を正本とする。ワークスペース側は読み取り専用の旧コピー。Git コミットは未実施（人の指示待ち）。
- 検査器の修正: 抽出時の `source_manifest.json` が絶対パス（ワークスペース）を記録しているため、`validate_model.py` がこのチェックアウト内の `design/` 相対で先に解決するようにした（移植性。条件は変えていない）。
- 既知の事項: 初回移行の protected_files に macOS の `.DS_Store` 2 件（抽出ディレクトリ内）が含まれている。リポジトリの `.gitignore` は `.DS_Store` を除外するため、別の clone では「unchanged …/.DS_Store」が違反として出る。baseline の manifest は凍結しているため、除外には人の判断（新しい baseline 版の作成）が必要。今回は同じファイルを複製して検査を通した。
- リポジトリ内で `design/.venv/bin/python design/tools/run_checks.py` を実行し、終了コード 0 を確認。
- 引き継ぎ: `design/reports/handover_2026-10-09.md`。

---

# 追記: 引き継ぎ後の読み直しと再検査（2026-10-09 第6便）

## 読んだもの

- リポジトリ HEAD: `a091ed39eb154b2dff7065840dc13c6478b153da`（2026-10-06）。`design/` は未追跡（265 ファイル、`.venv` は除外済み）。
- `reports/handover_2026-10-09.md`、`reports/status.md`、本 worklog（REV-002〜009・格納の追記）、`generated/pending_classification.md`、`reports/design_check.txt`。
- `design/intent.md`: SHA `81d71f07…`（第5版、変更なし）。

## 検査（`design/.venv/bin/python design/tools/run_checks.py`、終了コード 0。対象: 上記 HEAD ＋ 未追跡の design/）

入力の完全性・パラメータ生成・intent 同一性・移行忠実性・設計整合性・試験 すべて PASS。設計整合性 15 ルール: 合格 11・違反 0・未判定 4（DR-04 5、DR-05 2、DR-10 2、DR-11 38）。ROS 動作・実車試験は未実行。

## 確認した事実（変更なし）

- ワークスペース直下 `CLAUDE.md` は未修復（SHA `2c90ed21…`、2 行目以降に行番号が残る）。修復版 `proposals/CLAUDE.md.repaired` は SHA `4e071b7e…`。DEC-052 は pending のまま。
- 抽出ディレクトリ内の `.DS_Store` 2 件はこのチェックアウトに存在し、検査は通る。`.git/info/exclude` が `.DS_Store` を除外するため、別 clone では違反になる点は変わらず（baseline 改版は人の判断）。
- `research/vehicle_pc/` に GLIM の dpkg 出力はまだない。

## 自律判断

- なし（正本・生成物・提案は変更していない）。

## 止まっている作業と次の作業

- 人の入力待ち: DEC-052（CLAUDE.md 修復差分の承認）、ゲート3の承認（`generated/gate3_package.md`）、実車PC の `dpkg -l | grep glim` 出力、design/ の Git コミット可否。
- 回答に依存しない候補: Q-02 推定方式の候補比較、G-FIRMWARE の設計、独自型 4 件の定義、速度マスク生成器の詳細。DEC-052 の承認まで CLAUDE.md の指示に依存する新規作業は止めるため、本便では着手していない。
