# YAML移行レビュー

対象日: 2026-10-08。最新 `intent.md` を上位要求とし、既存抽出結果を入力にした。原資料・intent・抽出結果は変更していない。

## 結果の区別

| 確認対象 | 結果 | 範囲 |
|---|---|---|
| 前段の抽出忠実性 | 48項目一致という既存結果を保持 | 再抽出は行っていない。元資料ハッシュと既存抽出時ハッシュの一致を今回確認 |
| YAMLの形式・移行忠実性 | 合格、違反0件 | 5896件の比較・規則検査。設計テストのケース数ではない |
| 設計内容の妥当性 | 未判定 | 下位設計、ROS版でのIF確認、状態遷移の成立性、実車値は未検証 |
| ロボット実装・ソフト動作 | 未実施 | 移行ツールの試験と、ROS Nodeの動作試験は別 |
| 実車確認・投入判断 | 未実施・人の判断待ち | YAML移行を実車確認済みとは扱わない |

既存定義IDは **198/198件** が同じIDへ移行。加えて既存の変更記録ID `CH-01`〜`CH-04` を保持したため、既存ID対応表は **202件**。198件側の重複・対応漏れは0件。CHは旧抽出器のIDパターン対象外だったが行原文には存在しており、今回の追加抽出ではない。
モデルは800要素、出典497件。Excelモジュール38件にIDなし行の `gouda_section_executor` を `M-039` として加えた39件。図は101 vertex（枠・注記含む）、2構造要素、84接続を全て保持。図の要素数をモジュール数やExcel IF46件と同一視しない。

## 正本の読み方と状態

- `files` は原ファイル/抽出ファイル/検証結果のパスとSHA-256、`sources` は実位置と原文。`raw_fields` の原文を編集用の設計値と混ぜない。
- `entities` が下位設計の管理単位。`field_bindings` は出典の列/フィールドへ参照し、状態所有・パラメータ群・故障応答・実行配置を独立IDで関係付ける。同じ原文を各表へ再転記しない。`name` は表示ラベルであり仕様の正本値ではない。
- `original_status` は抽出時の「確定／未決」と根拠・元の区分をそのまま保持。`design_status` は下位設計の「未設計／案／承認済み」。原資料の確定・実装済みという記載から下位設計の承認や実車確認を推定しない。
- `adoption: upper_requirement` は現在の上位要求。`legacy_candidate` は移行された旧設計候補であり、自動採用ではない。`partially_superseded` はC番号のscopeで特定した部分を置換する。残りの候補を無条件に承認する意味ではない。
- 現在の採用内容は `reconciliation.adopted_requirement_refs` で上位要求を参照する。旧原文は残るが、置換された部分を現在要求と合成しない。`open` の衝突は未解消の問題IDを参照する。
- 明示なし・未設計の全てを人の判断待ちにしない。`issue.category` が `technical` ならAIの次段階作業、`human` だけが人の判断対象、`source_missing` は証拠不足。
- パラメータ群24件は、元の主要設定欄を参照した段階。個別キー・型・単位・値は未設計。`value: null` と `value_state: unresolved` を保存し、0や慣例値を入れていない。原文内の5 m等の旧値は原文として残り、採用値には昇格しない。
- 現在のruntime modeは4件。旧モード/メタ値6件も資料履歴として保持するが `runtime: false`。内部状態と新モードを混同しない。
- 実行構成39件は原文の種別・実装場所・使用モード・起動条件を保持する枠。ROS Node分割・process配置は未設計。モジュール分類も `unclassified` のままで、1モジュール=1Node=1processとはしない。
- 新IDは `migration_manifest.json` の `id_registry` に固定。新旧の出典位置が変わっても再採番しない。ビルダーは初回移行専用で正本を上書きしない。今後の設計ではモデルを編集し、移行baselineは履歴として維持する。
- `schema.json` は形式と許される未確定状態を検査。`validate_model.py` はID、参照、出典、元データ照合、明示問題を検査。初回移行の全件台帳も固定して検査するため、将来の追加設計は移行baselineの改版/差分審査と分けて扱う。
- 最新intent以外のWeb資料・公式仕様・実装コードは、この移行で再検証していない。REF行は引用記録として移行しただけで、採用版への適合を保証しない。

## 未設計の範囲

Node分割、process配置、IFの標準型選択・所有者・QoS・時刻、パラメータの個別定義、復旧時の必要状態・旧goal処理、ログ/rosbagの独立制御、故障応答の詳細、現要求に対応した試験は未設計。既存25試験は未実行。新しい通過判定、後退累計管理、境界での実速度保証、モード、保護、承認操作は追加していない。

モデルの設計状態（図・出典整理用要素も含む件数）: {"未設計": 403, "案": 393, "承認済み": 4}。承認済み0件。

## 矛盾・変更対応

C-001〜C-013は上位要求が明示する変更/具体化の対応。旧案の行全体を破棄・承認せず、scopeに書いた範囲だけを扱う（置換しない範囲は `generated/gate3_review_C001_C013.md`）。C-014〜C-016は未解消。REV-002 で C-017（非常停止検知の不採用、resolved_by_intent）、C-018（車体座標系とREP-103の衝突、open）、C-019（復旧不能時の遷移先、open）を追加。

### C-001 ソフトモードの集合

状態: `resolved_by_intent`。

旧map_editをruntime modeとして採用しない。一時停止を4モードの一つとして管理。内部状態との対応は未設計。

旧側の影響ID: `LEG-05-0003`, `LEG-05-0005`, `M-001`, `M-002`, `M-005`, `M-010`, `S-05`, `D-06`, `D-07`, `ST-01`, `ST-20`, `Q-10`

原位置: Excel 使用モード定義!A3:G3; Excel 使用モード定義!A5:G5; Excel モジュール定義!A2:AD2; Excel モジュール定義!A3:AD3; Excel モジュール定義!A6:AD6; Excel モジュール定義!A11:AD11; Excel 基本仕様!A6:D6; Excel データ契約!A7:E7; Excel データ契約!A8:E8; Excel 状態遷移!A2:E2; Excel 状態遷移!A21:E21; Excel 未決事項!A11:D11

現在の採用要求: `RQ-I025`, `RQ-I064`, `RQ-I065`, `RQ-I080`。intent.md:36–36; intent.md:92–92; intent.md:93–93; intent.md:95–95

### C-002 区間属性の帰属

状態: `resolved_by_intent`。

前点から当該点へのincoming属性の旧案を、waypoint i→i+1の区間属性へ置換。初回進入の詳細は未設計。

旧側の影響ID: `S-08`, `D-03`, `M-010`, `M-037`

原位置: Excel 基本仕様!A9:D9; Excel データ契約!A4:E4; Excel モジュール定義!A11:AD11; Excel モジュール定義!A39:AD39

現在の採用要求: `RQ-I078`。intent.md:13–13

### C-003 境界速度の保証

状態: `resolved_by_intent`。

進入区間の上限を境界で適用。境界時の実速度上限以下の保証は要求しない。cmd_vel後段の独自速度制限を追加しない。旧制御器の飽和・変換特性など既存保護全体を削除する意味ではない。

旧側の影響ID: `S-13`, `D-16`, `IF-022`, `T-12`, `M-012`

原位置: Excel 基本仕様!A14:D14; Excel データ契約!A17:E17; Excel インターフェース定義!A23:P23; Excel 使用・開発検証!A13:E13; Excel モジュール定義!A14:AD14

現在の採用要求: `RQ-I078`, `RQ-I020`, `RQ-I062`。intent.md:13–13; intent.md:26–26; intent.md:90–90

### C-004 通過判定の所有者

状態: `resolved_by_intent`。

通過・到達判定はNav2。Gouda独自の幾何判定・通過証拠による再判定を現在契約として採用しない。進捗保持やイベント順序は別途設計。

旧側の影響ID: `S-14`, `D-09`, `ST-04`, `ST-17`, `T-14`, `Q-08`, `M-037`, `M-039`

原位置: Excel 基本仕様!A15:D15; Excel データ契約!A10:E10; Excel 状態遷移!A5:E5; Excel 状態遷移!A18:E18; Excel 使用・開発検証!A15:E15; Excel 未決事項!A9:D9; Excel モジュール定義!A39:AD39; Excel モジュール定義!A12:AD12

現在の採用要求: `RQ-I011`, `RQ-I019`, `RQ-I057`。intent.md:14–14; intent.md:25–25; intent.md:82–82

### C-005 Nav2の後退と再計画

状態: `resolved_by_intent`。

無断後退・自動retryを一律に外す旧案から、Nav2 BTによる後退・再計画へ置換。BT失敗後は一時停止。Goudaで二重実行しない。

旧側の影響ID: `S-17`, `M-011`, `IF-020`, `REF-05`, `ST-09`, `ST-10`

原位置: Excel 基本仕様!A18:D18; Excel モジュール定義!A13:AD13; Excel インターフェース定義!A21:P21; Excel 参照・変更記録!A6:D6; Excel 状態遷移!A10:E10; Excel 状態遷移!A11:E11

現在の採用要求: `RQ-I012`, `RQ-I018`, `RQ-I019`。intent.md:15–15; intent.md:24–24; intent.md:25–25

### C-006 異常後の自動復帰

状態: `resolved_by_intent`。

プロセス再起動→必要状態復元→旧goal終了/破棄確認→自律復帰の場合だけ指令再許可。人の追加承認不要。PC再起動、人のpause/end後は別の復帰規則を適用。

旧側の影響ID: `D-22`, `ST-11`, `ST-12`, `M-007`, `M-037`, `T-21`, `Q-10`

原位置: Excel データ契約!A23:E23; Excel 状態遷移!A12:E12; Excel 状態遷移!A13:E13; Excel モジュール定義!A8:AD8; Excel モジュール定義!A39:AD39; Excel 使用・開発検証!A22:E22; Excel 未決事項!A11:D11

現在の採用要求: `RQ-I013`, `RQ-I014`, `RQ-I025`, `RQ-I064`, `RQ-I069`。intent.md:16–16; intent.md:17–17; intent.md:36–36; intent.md:92–92; intent.md:97–97

### C-007 最終点後の扱い

状態: `resolved_by_intent`。

最終点で自動終了せず停止して一時停止。再開時も最終waypointを目指す。人の終了操作まで自律走行を終了しない。

旧側の影響ID: `S-15`, `ST-14`, `T-24`, `M-037`

原位置: Excel 基本仕様!A16:D16; Excel 状態遷移!A15:E15; Excel 使用・開発検証!A25:E25; Excel モジュール定義!A39:AD39

現在の採用要求: `RQ-I015`, `RQ-I017`, `RQ-I067`。intent.md:19–19; intent.md:21–21; intent.md:95–95

### C-008 Bluetooth入力途絶

状態: `resolved_by_intent`。

Bluetooth断時追加処理なしという旧記載を採用要件にしない。現在採用している指令源の入力途絶時はESP32が中立。既存実装の成立は未確認のまま。

旧側の影響ID: `S-04`, `M-025`, `Q-09`, `T-18`

原位置: Excel 基本仕様!A5:D5; Excel モジュール定義!A27:AD27; Excel 未決事項!A10:D10; Excel 使用・開発検証!A19:E19

現在の採用要求: `RQ-I023`, `RQ-I024`, `RQ-I063`, `RQ-I068`。intent.md:34–34; intent.md:35–35; intent.md:91–91; intent.md:96–96

### C-009 ログとrosbagの操作と保存

状態: `resolved_by_intent`。

ログとrosbagを独立操作。ログ自動開始は人の地図作成開始/自律開始のみ。復帰/再開では自動開始しない。手動開始記録は自動停止しない。記録失敗で走行停止しない。

旧側の影響ID: `M-016`, `M-017`, `IF-038`, `IF-039`, `IF-040`, `D-24`, `T-23`, `Q-10`

原位置: Excel モジュール定義!A18:AD18; Excel モジュール定義!A19:AD19; Excel インターフェース定義!A39:P39; Excel インターフェース定義!A40:P40; Excel インターフェース定義!A41:P41; Excel データ契約!A25:E25; Excel 使用・開発検証!A24:E24; Excel 未決事項!A11:D11

現在の採用要求: `RQ-I005`, `RQ-I015`, `RQ-I016`, `RQ-I017`。intent.md:8–8; intent.md:19–19; intent.md:20–20; intent.md:21–21

### C-010 開始操作と準備

状態: `resolved_by_intent`。

初期姿勢指定後に開始を一度押し、推定しながらNav2開始。開始後の追加承認を挟まない。必要条件の内部処理は未設計。

旧側の影響ID: `S-06`, `ST-02`, `ST-03`, `M-002`, `M-007`

原位置: Excel 基本仕様!A7:D7; Excel 状態遷移!A3:E3; Excel 状態遷移!A4:E4; Excel モジュール定義!A3:AD3; Excel モジュール定義!A8:AD8

現在の採用要求: `RQ-I011`。intent.md:14–14

### C-011 地図変換と成果物同一性

状態: `resolved_by_intent`。

地図終了時に自動変換。由来IDを共有し各成果物は独立ハッシュと版。waypointは変換後地図のID/版/ハッシュを参照し独立保存。失敗時は原図保持、不完全変換成果物破棄。

旧側の影響ID: `M-005`, `M-006`, `M-009`, `D-01`, `D-02`, `IF-011`, `IF-012`, `IF-013`, `IF-015`, `IF-016`

原位置: Excel モジュール定義!A6:AD6; Excel モジュール定義!A7:AD7; Excel モジュール定義!A10:AD10; Excel データ契約!A2:E2; Excel データ契約!A3:E3; Excel インターフェース定義!A12:P12; Excel インターフェース定義!A13:P13; Excel インターフェース定義!A14:P14; Excel インターフェース定義!A16:P16; Excel インターフェース定義!A17:P17

現在の採用要求: `RQ-I008`, `RQ-I009`, `RQ-I078`。intent.md:11–11; intent.md:12–12; intent.md:13–13

### C-012 Navigation実行主体

状態: `resolved_by_intent`。

Gouda section executor/progress trackerを独立した二重実行/判定主体として採用しない。薄いadapterの要否や標準IFとの対応は次段階。

旧側の影響ID: `M-039`, `D-08`, `IF-019`, `IF-020`, `DG-09708a83-295b-5f99-b694-07f63194e199`, `DG-59fe0346-99a1-5627-9b51-df2e5a79f1b0`

原位置: Excel モジュール定義!A12:AD12; Excel データ契約!A9:E9; Excel インターフェース定義!A20:P20; Excel インターフェース定義!A21:P21; drawio page=lc-_yTM2-hEJOly5ozWo element=2TSgiu6-nVzXwyzMdGmE-24; drawio page=lc-_yTM2-hEJOly5ozWo element=2TSgiu6-nVzXwyzMdGmE-25

現在の採用要求: `RQ-I011`, `RQ-I018`, `RQ-I019`, `RQ-I055`, `RQ-I057`。intent.md:14–14; intent.md:24–24; intent.md:25–25; intent.md:80–80; intent.md:82–82

### C-013 waypoint UIの配置

状態: `resolved_by_intent`。

waypoint_manager GUIはgouda_monitor内。画面転送は禁止。地図作成中のRViz表示要求は保持。

旧側の影響ID: `M-010`, `M-002`, `M-018`

原位置: Excel モジュール定義!A11:AD11; Excel モジュール定義!A3:AD3; Excel モジュール定義!A20:AD20

現在の採用要求: `RQ-I044`。intent.md:64–64

### C-014 非常停止検知の資料間衝突

状態: `open`。

取得可否は資料だけで統合しない。

旧側の影響ID: `M-028`, `IF-032`, `DG-0cc70760-7d1f-5fd2-bf1c-42880b31214b`

原位置: Excel モジュール定義!A30:AD30; Excel インターフェース定義!A33:P33; drawio page=lc-_yTM2-hEJOly5ozWo element=x5bDQh8FaZrcMh8EckeY-164

未解消問題: `U-DRAW-002`

### C-015 heartbeatとcollision_stopの資料間衝突

状態: `resolved_by_decision`。

実行必須性・実装有無を保留。

旧側の影響ID: `M-013`, `M-023`, `DG-b4b9e22a-0538-579b-9565-5f42cc082644`, `DG-83cfa2b7-7651-54db-b436-ada322f7c78c`

原位置: Excel モジュール定義!A15:AD15; Excel モジュール定義!A25:AD25; drawio page=lc-_yTM2-hEJOly5ozWo element=x5bDQh8FaZrcMh8EckeY-40; drawio page=lc-_yTM2-hEJOly5ozWo element=x5bDQh8FaZrcMh8EckeY-163

未解消問題: `U-DRAW-003`

### C-016 変更記録の時点差

状態: `open`。

現在図に存在するという観察と旧履歴を別に保持。

旧側の影響ID: `CH-02`, `DG-a78e555c-f9ed-5012-8910-5e5a0dcbfc9e`, `DG-4cceab74-ddb6-5dfa-ac81-b682c415f71f`

原位置: Excel 参照・変更記録!A10:D10; drawio page=lc-_yTM2-hEJOly5ozWo element=4S4QAY9o3vVNfXHAsMHo-1; drawio page=lc-_yTM2-hEJOly5ozWo element=2TSgiu6-nVzXwyzMdGmE-4

未解消問題: `U-HISTORY`

### C-017 非常停止検知／PC側非常停止機構の不採用（上位要求）

状態: `resolved_by_intent`。

不採用とする範囲（原文引用）: drawio ページ lc-_yTM2-hEJOly5ozWo の線 x5bDQh8FaZrcMh8EckeY-164（source=x5bDQh8FaZrcMh8EckeY-22「Emergency_stop_button」→ target=x5bDQh8FaZrcMh8EckeY-2「esp32」）と、 その線上のラベル x5bDQh8FaZrcMh8EckeY-165「非常押しボタン押下検知」が示す、ESP32またはPC側での非常停止ボタン押下検知機能。 あわせて、PC側に非常停止機構（別名を含む）を設けること。これらは現在の実行構成に採用しない。原文・ID・出典は履歴として保持する。

旧側の影響ID: `DG-0cc70760-7d1f-5fd2-bf1c-42880b31214b`, `DG-7ffa9506-5db6-5737-8d7e-604bbb927160`, `M-028`, `IF-032`

原位置: drawio page=lc-_yTM2-hEJOly5ozWo element=x5bDQh8FaZrcMh8EckeY-164; drawio page=lc-_yTM2-hEJOly5ozWo element=x5bDQh8FaZrcMh8EckeY-165; Excel モジュール定義!A30:AD30; Excel インターフェース定義!A33:P33

現在の採用要求: `RQ-I072`。intent.md:100–100

### C-018 車体座標系（RQ-I071）とREP-103／Nav2前提の衝突

状態: `resolved_by_decision`。

RQ-I071 は「LiDARの座標系に合わせ、-y方向を車体前方、+x方向を車体右方、+z方向を上方」と定める。REP-103（RQ-I055が優先）は x前方・y左方・z上方。 Nav2 controller の cmd_vel は base_link の x 方向を前進とみなし、costmap footprint も base_link 基準。RQ-I056「Nav2本体は改変しない」と同時には満たせない。

旧側の影響ID: `IFD-15`, `IFD-18`, `IFD-19`, `IFD-20`, `ND-10`, `ND-13`, `PRM-07`

原位置: intent.md:26–26; intent.md:91–91; intent.md:80–80; intent.md:7–7; intent.md:83–83; intent.md:14–14; intent.md:98–98; intent.md:99–99; intent.md:15–15; intent.md:24–24; intent.md:25–25; intent.md:81–81; intent.md:82–82; intent.md:103–103

未解消問題: `H-005`

### C-019 復旧不能時の遷移先（RQ-I013とRQ-I064の読み）

状態: `resolved_by_decision`。

RQ-I013「復旧できない場合、または復旧の試行回数が上限に達した場合は、一時停止モードに入り理由を記録する」は復帰先を限定していない。 RQ-I064 は復帰先を「直前の状態（自律走行/事前地図作成/一時停止/手動走行）」とし、RQ-I026 は一時停止を自律走行の一時停止として定義する。 直前が手動走行・事前地図作成のとき復旧不能なら一時停止モードに入るのかは原文から一意に読めない。

旧側の影響ID: `TR-09`, `TR-13`, `TR-14`, `TR-15`, `TR-16`

原位置: intent.md:16–16; intent.md:92–92; intent.md:97–97; intent.md:36–36

未解消問題: `H-006`

### C-020 collision_stop_request と「緊急停止信号」注記の不採用（人の決定）

状態: `resolved_by_decision`。

不採用（原文引用）：drawio 線 x5bDQh8FaZrcMh8EckeY-163「collision_stop_request」（障害物認識 → gouda_motion_controller）と注記 x5bDQh8FaZrcMh8EckeY-105 「原則として障害物情報はNavigationに渡して停止・回避動作を行わせるが、緊急時はmotion_controllerに緊急停止信号をいれる。」。

旧側の影響ID: `DG-83cfa2b7-7651-54db-b436-ada322f7c78c`, `DG-195f5869-3a67-5066-a741-e90dc7d29fa8`

原位置: drawio page=lc-_yTM2-hEJOly5ozWo element=x5bDQh8FaZrcMh8EckeY-163; drawio page=lc-_yTM2-hEJOly5ozWo element=x5bDQh8FaZrcMh8EckeY-105

### C-021 車体座標系の文の置換（intent.md 第2版 99 行 → 第3版 100 行）

状態: `resolved_by_intent`。

第2版 99 行「EMC-270の車体座標系は…LiDARの座標系に合わせ、-y方向を車体前方、+x方向を車体右方、+z方向を上方とする」を、 第3版 100 行「LiDARないしはdriverが出す点群の座標系は、-y方向を車体前方、+x方向を車体右方、+z方向を上方とするものであうが、これをNav2用に変換する」で置換。

旧側の影響ID: `RQ-I071`

原位置: intent.md:99–99

現在の採用要求: `RQ-I074`。intent.md:100–100

### C-022 RQ-I010 の境界文の削除（intent.md 第5版 13 行 → 第6版 13 行）

状態: `resolved_by_intent`。

第5版 13 行の「区間境界では、進入する区間の値を適用する。」を削除した第6版 13 行で置換（DEC-055）。他の文（区間 i→i+1 の属性、waypoint_database への保存、地図の ID・版・ハッシュの参照、独立ハッシュ、別保存）は同一。

旧側の影響ID: `RQ-I010`

原位置: intent.md:13–13

現在の採用要求: `RQ-I078`。intent.md:13–13

### C-023 区間属性の上限（RQ-I078）と Speed Filter の位置ベース上限・重複時は低い方（DEC-045）の食い違い

状態: `resolved_by_decision`。

RQ-I078 は速度上限を「区間（waypoint i → i+1）の属性」＝進行順序に属する値と定める。Speed Filter（DEC-031）は costmap の mask cell（位置）で上限を決め、 同じ位置を複数の区間が通る（再訪・交差・重複）場合は区間を区別できず、重複 cell は低い方の上限を採用する（DEC-045）。 したがって、再訪・重複する区間に異なる上限を設定しても実行時には反映されない。食い違いは「区間ごとの値」を「位置ごとの値」に写像する点にある。

旧側の影響ID: `RQ-I078`, `IFD-14`, `IFD-41`, `IFD-42`, `TS-02`, `TS-03`, `TS-14`

原位置: intent.md:13–13; intent.md:13–13; intent.md:26–26; intent.md:27–27; intent.md:90–90; intent.md:81–81; intent.md:14–14; intent.md:17–17; intent.md:95–95

現在の採用要求: `RQ-I078`, `RQ-I020`。intent.md:13–13; intent.md:26–26

未解消問題: `H-013`

### C-024 SpeedLimit の文への位置ベース上限の補足（intent.md 第6版 27 行 → 第7版 27 行）

状態: `resolved_by_intent`。

第6版 27 行「SpeedLimitの発行手段（…）は、採用するNav2の版に合わせてAIが提案し、人が承認する」の文末に、位置ベースで上限を決める、再訪・交差・重複する区間は同じ上限を設定する運用、 異なる値は保存時に warning し実行時は低い方、帯の外は無制限、帯の幅は実機調整、を追記した第7版 27 行で置換（人の編集）。

旧側の影響ID: `RQ-I021`

原位置: intent.md:27–27

現在の採用要求: `RQ-I079`。intent.md:27–27

### C-025 既定モードの表記の統一（intent.md 第6版 95 行「手動操縦モード」→ 第7版 95 行「手動走行モード」）

状態: `resolved_by_intent`。

「起動直後は手動操縦モードに入る。手動操縦モードがデフォルトのモード。」を「起動直後は手動走行モードに入る。手動走行モードがデフォルトのモード。」で置換（表記のみ。意味は同一）。

旧側の影響ID: `RQ-I066`

原位置: intent.md:94–94

現在の採用要求: `RQ-I080`。intent.md:95–95

## 残っている問題

計41件。技術事項14件、人の判断20件、資料不足7件。未解消衝突3件は資料不足の問題に紐付き、二重加算しない。元Qは部分的に置換されたものも閉じずに残余課題を保持。

| 問題ID | 分類 | 状態 | 内容 |
|---|---|---|---|
| Q-01 | technical | resolved | ROS 2・Nav2の採用版 |
| Q-02 | technical | open | 自己位置推定の方式・成立条件 |
| Q-03 | source_missing | open | 既存車両通信と制御校正 |
| Q-04 | human | open | XT-32の取付と可視範囲 |
| Q-05 | human | open | 数値パラメータと時間契約 |
| Q-06 | human | open | 車体・経路・通過の幾何条件 |
| Q-07 | human | deferred | 指定線への追従と迂回方式 |
| Q-08 | technical | resolved | P介入で通った点の扱い |
| Q-09 | source_missing | partially_superseded | Bluetooth切断時のP状態 |
| Q-10 | human | resolved | mode・再起動・HMI断の運用 |
| Q-11 | technical | resolved | 補助構成と独自IFの採用 |
| Q-12 | human | resolved | waypoint半径5 mの用途 |
| Q-13 | technical | deferred | 後工程の保留 |
| H-001 | human | resolved | SpeedLimit発行手段の承認 |
| G-ARCH | technical | open | Node・process・状態所有・IF契約の具体化 |
| G-PARAM | technical | open | パラメータ群の分解と型・単位 |
| G-RECOVERY | technical | open | 復旧・故障応答・内部状態の設計 |
| G-TEST | technical | open | 旧試験の現要求への対応と新要求の試験 |
| G-LOG | technical | open | ログ・rosbagの責務と記録状態 |
| G-GRAPH | technical | open | 図の要素とモデルIFの対応 |
| G-ENDPOINT | technical | open | IFの総称・表記揺れ・所有者 |
| U-DRAW-001 | source_missing | resolved | 接続先IDなしの線 |
| U-DRAW-002 | source_missing | partially_superseded | 非常停止検知線と取得不能記載 |
| U-DRAW-003 | source_missing | resolved | heartbeat必須性と衝突停止線 |
| U-HISTORY | source_missing | resolved | 変更記録と現在図の時点差 |
| H-002 | human | resolved | Safety_gateの採用可否と一時停止・終了・故障時の遮断経路 |
| H-003 | human | resolved | collision_stop_request線と「緊急停止信号」注記の扱い |
| H-004 | human | resolved | heartbeatの用途（診断表示か停止条件か） |
| H-005 | human | resolved | base_linkの軸定義（RQ-I071 と REP-103／Nav2 の衝突） |
| H-006 | human | resolved | 復旧不能・試行上限時の遷移先（直前モードが手動走行・事前地図作成のとき） |
| H-007 | human | resolved | PC再起動後の一時停止モードから再開するときの自己位置初期化 |
| H-008 | human | resolved | 地図作成終了ボタン押下後に入るモード |
| V-001 | source_missing | resolved | 実車PCのROS 2／Nav2採用版の照合 |
| P-001 | human | resolved | intent.md:99 の座標系文言の更新案（人の作業） |
| H-009 | human | resolved | 車体出力段階の値の不一致（intent 700 ms / 1 s と firmware・bridge の 250 ms）と 700 ms の配分 |
| H-010 | human | resolved | 実機 ESP32 に書き込まれている firmware と通信プロトコルの版 |
| H-011 | human | resolved | 速度マスクの帯の幅と帯外の扱い（Speed Filter 採用に伴う幾何条件） |
| H-012 | human | resolved | 新 firmware の手動操作経路（Bluetooth ゲームパッド優先か、純正ジョイスティックへのリレー切替か） |
| G-FIRMWARE | technical | open | 新 ESP32 firmware と PC-ESP32 通信の設計（AI の技術作業） |
| G-TUNING | technical | deferred | 実機調整で決める項目（設計規則・人の判断事項にしない） |
| H-013 | human | resolved | 区間属性の上限と位置ベース上限（Speed Filter）の食い違いの解消方法 |

### 人が判断する7件

この移行の完了に回答は不要。決定済み要求の再承認は求めない。以下は影響する次段階の設計/実車値だけを対象とする。推奨は未採用の判断材料。

#### Q-04 XT-32の取付と可視範囲

検出対象・取付条件・走行面をどの実車条件で評価するか。

- 実車の対象と条件を指定する：指定された条件をそのまま評価計画へ反映
- 後工程まで未確定とする：実車での検出範囲の合否判定を保留

推奨: 実車の対象と条件を指定する

影響ID: `IF-043`, `IF-044`

出典: Excel 未決事項!A5:D5

次の作業: 実車値は保留（DEC-017）。評価条件の決定は障害物処理の実車評価前。

#### Q-05 数値パラメータと時間契約

実車の周期・watchdog・timeout等の値、復旧試行回数の上限、試験条件をどう決定するか。

- 実測資料と試験条件で決める：既存値の根拠を確認し、人が採用値を決定
- 実車値の確定を保留する：型・設定経路の下位設計は進め、値依存の実車確認は未判定

推奨: 実測資料と試験条件で決める

影響ID: `IF-001`, `IF-002`, `IF-003`, `IF-004`, `IF-005`, `IF-006`, `IF-007`, `IF-008`, `IF-009`, `IF-010`, `IF-017`, `IF-019`, `IF-020`, `IF-021`, `IF-023`, `IF-024`, `IF-025`, `IF-026`, `IF-027`, `IF-033`, `IF-034`, `IF-035`, `IF-036`, `IF-037`, `IF-038`, `IF-040`, `IF-042`, `IF-043`, `IF-044`, `IF-045`, `IF-046`, `D-21`, `ST-16`, `T-02`, `RQ-I013`

出典: Excel 未決事項!A6:D6; intent.md:16–16

次の作業: 実車値は保留（DEC-017）。値に依存しない設計を先に進める。パラメータ一覧は generated/parameters_by_stage.md。車体出力段階の値は intent.md:102（RQ-I075）と H-009。

#### Q-06 車体・経路・通過の幾何条件

車体形状・上限速度等の実車値と、走行対象の未知領域方針をどう指定するか。

- 実車値と運用条件を指定する：Nav2設定に反映。独自通過判定は作らない
- 対象環境・値の確定を保留する：Nav2設定値と実車合否は未判定

推奨: 実車値と運用条件を指定する

影響ID: `S-14`, `D-04`

出典: Excel 未決事項!A7:D7

次の作業: 実車値は保留（DEC-017）。Nav2 設定の値（PRM-11・PRM-17・PRM-18 等）は一覧で管理し、仮値は実車採用値と区別する。

#### Q-07 指定線への追従と迂回方式

旧資料の指定線方式を今回も必要とし、どの範囲の迂回を認めるか。

- Nav2での実現案と運用差を次段階で比較する：人が追従/迂回の方針を判断するまで旧案は非採用候補
- 旧二方式の運用要求を維持すると明示する：許容範囲・追従優先度を人が追加指定する必要がある

推奨: Nav2での実現案と運用差を次段階で比較する

影響ID: `M-011`, `OWN-M-011`, `PAR-M-011`, `FM-M-011`, `EX-M-011`, `IF-021`, `S-10`, `ST-19`

出典: Excel 未決事項!A8:D8

次の作業: 後工程（DEC-015）。まず標準 Nav2 で自律走行を成立させる。指定線追従・二方式は後工程。

#### Q-10 mode・再起動・HMI断の運用

最新intentで決まったmode/復帰/最終点以外に、monitor断時の走行継続方針をどうするか。

- 旧案の走行継続を採用する：表示断自体は停止契機にせず再接続時に状態取得
- monitor断を一時停止契機とする：基本契約の追加・運用変更として人の明示決定が必要

推奨: 旧案の走行継続を採用する

影響ID: `S-05`, `D-22`, `ST-18`, `ST-20`, `T-23`

出典: Excel 未決事項!A11:D11

次の作業: 回答済み（DEC-014）。monitor の表示断は停止契機にしない。再接続後に transient_local の mode/state・record/status を取得（ND-02、TS-10）。

#### Q-12 waypoint半径5 mの用途

旧5 mはNav2設定に残す要求か、迂回領域等の別要求か。

- 5 mの用途を保留してNav2設定案で再確認する：一般的な既定値で補わず、独自通過判定も追加しない
- 用途を人が明示する：Nav2で表せる設定/運用要求として設計可能か次段階で確認

推奨: 5 mの用途を保留してNav2設定案で再確認する

影響ID: `M-011`, `OWN-M-011`, `PAR-M-011`, `FM-M-011`, `EX-M-011`, `IF-021`, `S-10`, `S-11`, `S-12`, `D-02`, `D-05`, `D-20`, `ST-19`, `T-05`, `T-11`

出典: Excel 未決事項!A13:D13

次の作業: 回答済み（DEC-016）。旧 5 m は当面採用しない。RemovePassedGoals の radius は PRM-11（未確定）。

#### H-001 SpeedLimit発行手段の承認

DEC-031 で Speed Filter（costmap filter）が発行することになった。DEC-039 の調査で、Speed Filter は値が変わるまで再発行せず、deactivate→activate だけの復帰では同じ cell で上限が再適用されないことを確認した （cleanup→configure を伴う復帰、または bond による全体 reset では再適用される）。Nav2 を改変せず単一発行元を保つ (a)(b) の比較表（「復帰後の再適用」の行を含む）は research/speed_filter_reapply_h011.md §5。最終判断は人。

- (a) Speed Filter のまま、controller／costmap の復帰を lifecycle cleanup→configure→activate で行い現在値を再発行させる：発行元は Nav2 の SpeedFilter 1 箇所。復帰手順を Gouda 側で作り込む（TR-13）。区間上限は位置依存（帯の重なり・再訪は表現不可、H-011）。mask 未読込・マスク外では発行されない。
- (b) Speed Filter を Gouda 側の単一発行器に置き換える：発行元は gouda_mode_manager 1 箇所。controller の transition_event で再発行し transient_local で遅延購読にも届く。区間上限（進行順序）の意味に一致し帯の定義が不要。Gouda 独自コードが増える。

推奨: AI は推奨しない。単一発行元（RQ-I020）の最終判断は人（DEC-039）。

影響ID: `RQ-I020`, `RQ-I021`, `IF-022`, `D-16`, `M-011`

出典: intent.md:26–26; intent.md:27–27; Excel インターフェース定義!A23:P23; Excel データ契約!A17:E17; Excel モジュール定義!A13:AD13

次の作業: 台帳上の経緯：DEC-011（Gouda 側発行器の暫定採用）→ DEC-031（Speed Filter が発行）→ DEC-039（復帰後の再適用の再比較指示。人の最終判断待ちに戻す）→ DEC-046（復帰手順を cleanup→configure→activate の 1 つに定める）。 現在の状態は resolved（発行元：Nav2 SpeedFilter、復帰手順：TR-13）。ゲート3で承認対象。

#### H-002 Safety_gateの採用可否と一時停止・終了・故障時の遮断経路

旧資料の Safety_gate（M-014: 「PC側のmission走行要求とsystem健全性、有効な制御指令を照合し、最終PC指令を一つに限定する」、入力 IF-024 control/joystick_command・IF-025 task/motion_enable・IF-026 safety/permission、出力 IF-027）は、 一時停止・終了・故障時のPC指令遮断をPC側で一本化する要素である。現在の案では遮断を「Nav2 goal の取消（controller_server は取消時に零速度を発行）→ cmd_vel 途絶で gouda_motion_controller が中立（RQ-I063）→ 指令源途絶で ESP32 が中立（RQ-I068）」で構成している。 Safety_gate を採用するか。採用する場合、motion_enable/permission は新しい保護の追加（RQ-I027：AIは独断で増やさない）に当たるため人の判断が必要。 C-015 との関係: 図の heartbeat_and_status と collision_stop_request は Safety_gate／supervisor の入力候補として描かれており、H-003・H-004 の回答と連動する。

- 採用しない（暫定案）：Nav2取消＋cmd_vel途絶中立（RQ-I063）＋ESP32中立化（RQ-I068）の既存契約だけで遮断。PC側の遮断は単経路。
- Safety_gateを採用する：task/motion_enable・safety/permission の契約（epoch・有効期限・所有者）を設計。新しい保護の追加として基本契約の変更に相当。
- 保留：未確認のまま。車体出力（RQ-I044の順序）の実装前に決定が必要。

推奨: 採用しない（暫定案）。追加の保護はRQ-I027により提案に留め、必要性・根拠・開発への影響を添えて別途提示する。

影響ID: `M-014`, `M-013`, `IF-024`, `IF-025`, `IF-026`, `IF-027`, `IF-045`, `DG-e7a41d60-dfba-59c7-957a-1c37d0aeb6f3`, `TR-06`, `TR-11`, `TR-12`, `ND-11`, `ND-12`

出典: intent.md:37–37; intent.md:38–38; intent.md:26–26; intent.md:91–91; intent.md:96–96; intent.md:34–34; Excel モジュール定義!A16:AD16; Excel モジュール定義!A15:AD15; Excel インターフェース定義!A25:P25; Excel インターフェース定義!A26:P26; Excel インターフェース定義!A27:P27; Excel インターフェース定義!A28:P28; Excel インターフェース定義!A46:P46; drawio page=lc-_yTM2-hEJOly5ozWo element=x5bDQh8FaZrcMh8EckeY-28; intent.md:36–36; intent.md:19–19; intent.md:41–41; intent.md:21–21; intent.md:64–64; intent.md:49–49; intent.md:35–35

次の作業: 回答済み（DEC-004）。mode_manager → motion_controller の motion_hold（IFD-40）を直接入力。Safety_gate・supervisor の permission 経路は採用しない。

#### H-003 collision_stop_request線と「緊急停止信号」注記の扱い

drawio の線 x5bDQh8FaZrcMh8EckeY-163「collision_stop_request」（障害物認識 → gouda_motion_controller）と注記 x5bDQh8FaZrcMh8EckeY-105 「原則として障害物情報はNavigationに渡して停止・回避動作を行わせるが、緊急時はmotion_controllerに緊急停止信号をいれる。」は、PC側で停止を執行する機構に読める。 Excel 側は M-012 J14「将来collision_stop_requestを追加」、V14「今回collision_stop_requestの送信元は未実装で、欠落を異常扱いしない」、M-023 V25「今回collision_stop_requestは未提供」。 RQ-I072（PC側で非常停止機構は存在させない）および RQ-I012（障害物停止・回避はNav2）との関係で、どう扱うか。

- 不採用：障害物による停止・回避は Nav2 costmap/BT のみ（RQ-I012・RQ-I057）。線と注記は履歴保持。RQ-I072 と整合。
- 将来候補として履歴保持のみ：実行構成には入れず、名称も変えない。RQ-I072 の「別名で再導入しない」に抵触しないことを人が確認。
- 採用：PC側の停止執行機構を設けることになり RQ-I072 との整合を人が判断する必要がある。

推奨: 不採用

影響ID: `M-012`, `M-023`, `DG-83cfa2b7-7651-54db-b436-ada322f7c78c`, `DG-195f5869-3a67-5066-a741-e90dc7d29fa8`, `ND-09`, `ND-11`

出典: intent.md:100–100; intent.md:15–15; intent.md:24–24; intent.md:82–82; Excel モジュール定義!A14:AD14; Excel モジュール定義!A25:AD25; drawio page=lc-_yTM2-hEJOly5ozWo element=x5bDQh8FaZrcMh8EckeY-163; drawio page=lc-_yTM2-hEJOly5ozWo element=x5bDQh8FaZrcMh8EckeY-105; intent.md:10–10; intent.md:26–26; intent.md:91–91; intent.md:64–64; intent.md:49–49

次の作業: 回答済み（DEC-005「不採用」）。障害物は Nav2 costmap のみ。

#### H-004 heartbeatの用途（診断表示か停止条件か）

drawio の heartbeat 線（x5bDQh8FaZrcMh8EckeY-40「heartbeat_and_status」esp32 → vehicle_bridge、x5bDQh8FaZrcMh8EckeY-146 motion_controller → safety_supervisor、 x5bDQh8FaZrcMh8EckeY-137 crosswalk_controller → safety_supervisor）と Excel 側の記載（M-013 V15「図のESP32 heartbeat依存は今回必須から除外」、M-006 O7・M-017 O19 は非責務、IF-036 P37「ESP32返信有無は監視条件にしない」）が対応していない。 heartbeat を (a) monitor の表示・診断（RQ-I033「monitorで現在のモードと各nodeの状態がわかる」）のみに使うか、(b) 走行停止条件に使うか。(b) は新しい保護の追加に相当する。 実装リポジトリ docs/gouda_protocol_v3.md には ESP32→PC の STATUS フレームの記述があるが、設計側では原本未照合。

- 表示・診断のみ：lifecycle と /diagnostics を monitor 表示に使い、停止条件にしない。既存契約（RQ-I068 ESP32中立化）は変えない。
- 停止条件に採用：受信途絶を停止契機にする新しい保護。誤値・固着・古い値は検出できない（CLAUDE.md 1.5）。基本契約の追加として人の明示決定が必要。
- 保留：未確認のまま。supervisor の採否（H-002）と同時に決める。

推奨: 表示・診断のみ

影響ID: `M-013`, `M-006`, `M-017`, `IF-036`, `DG-b4b9e22a-0538-579b-9565-5f42cc082644`, `DG-3ee7468b-d5af-5904-b60d-1a2493f80e6c`, `DG-df3b798a-0da6-5af9-b2a8-6d065e756d2f`, `ND-02`, `ND-12`

出典: intent.md:45–45; intent.md:41–41; intent.md:38–38; intent.md:96–96; Excel モジュール定義!A15:AD15; Excel モジュール定義!A7:AD7; Excel モジュール定義!A19:AD19; Excel インターフェース定義!A37:P37; drawio page=lc-_yTM2-hEJOly5ozWo element=x5bDQh8FaZrcMh8EckeY-40; drawio page=lc-_yTM2-hEJOly5ozWo element=x5bDQh8FaZrcMh8EckeY-146; drawio page=lc-_yTM2-hEJOly5ozWo element=x5bDQh8FaZrcMh8EckeY-137; intent.md:8–8; intent.md:9–9; intent.md:13–13; intent.md:14–14; intent.md:17–17; intent.md:64–64; intent.md:98–98; intent.md:34–34; intent.md:35–35; intent.md:91–91; intent.md:49–49

次の作業: 回答済み（DEC-006）。取得できると確認した項目だけを表示・診断に使う（IFD-38）。停止条件にしない。既存実装の停止条件（firmware 250 ms、bridge DISARM）は維持。取得できない状態は「不明」表示。 実機 firmware の版の確認は H-010。

#### H-005 base_linkの軸定義（RQ-I071 と REP-103／Nav2 の衝突）

RQ-I071（intent.md:99）は EMC-270 の車体座標系を「-y方向を車体前方、+x方向を車体右方、+z方向を上方」とし、base_footprint/base_link をこの系に置く。 REP-103（RQ-I055 で優先）は x前方・y左方・z上方。Nav2 の controller は cmd_vel の linear.x を base_link 前方として扇生成し、costmap の footprint も base_link 基準で評価する。 RQ-I056（Nav2本体は改変しない）と RQ-I071 の軸定義は同時に満たせない。base_link の軸をどちらに従わせるか。

- base_linkはREP-103、LiDAR系はセンサframeの回転で表す：base_link/base_footprint を x前方・y左方で定義し、RQ-I071 の「LiDARに合わせた -y 前方」は xt32_link への静的TF（z軸回り回転）で表現。Nav2 無改変。RQ-I071 の文言は「センサ系の取り方」として読み替える必要があり人の確認が要る。
- RQ-I071どおり -y 前方の base_link を採用：Nav2 controller・costmap がそのまま動作しない。Nav2 改変（RQ-I056 違反）または cmd_vel/TF の Gouda 側変換（RQ-I020・RQ-I057 と衝突）が必要。
- 保留：TF・Nav2 設定・footprint の設計が止まる。

推奨: base_linkはREP-103、LiDAR系はセンサframeの回転で表す

影響ID: `RQ-I071`, `IFD-15`, `IFD-18`, `IFD-19`, `IFD-20`, `IFD-21`, `IFD-23`, `ND-10`, `ND-13`, `PRM-01`, `PRM-02`, `PRM-03`, `PRM-04`, `PRM-05`, `PRM-06`, `PRM-07`

出典: intent.md:99–99; intent.md:80–80; intent.md:81–81; intent.md:82–82; intent.md:78–78

次の作業: 回答済み（DEC-007）。base_link は REP-103。LiDAR・IMU の座標方向は gouda_monitor の /config（IFD-26）で指定し、静的TF発行（ND-13）が Nav2 前提へ変換する。 intent.md:99 の文言更新は P-001。

#### H-006 復旧不能・試行上限時の遷移先（直前モードが手動走行・事前地図作成のとき）

RQ-I013 は復旧不能・試行上限時に「一時停止モードに入り理由を記録する」とする。RQ-I064 は復帰先を直前の状態（4モードのいずれか）とする。 直前が手動走行または事前地図作成で、PC側の node 異常の復旧に失敗した場合も一時停止モード（RQ-I026では自律走行の一時停止）に入るか、直前モードを維持して理由を記録するか。

- 直前が自律走行・一時停止のときだけ一時停止へ。手動走行・事前地図作成では直前モードを維持し理由を記録：一時停止モードを自律走行の一時停止（RQ-I026）に限定する読み。手動走行中の PC 故障は monitor 表示と記録のみ。
- 常に一時停止モードへ（RQ-I013 の文言どおり）：手動走行中でも PC 側の表示上は一時停止になる。再開ボタンの意味（自律走行再開）と手動走行の関係を別途定義する必要がある。

推奨: 直前が自律走行・一時停止のときだけ一時停止へ。手動走行・事前地図作成では直前モードを維持し理由を記録

影響ID: `RQ-I013`, `RQ-I064`, `TR-09`, `TR-13`, `TR-14`, `TR-15`, `TR-16`

出典: intent.md:16–16; intent.md:92–92; intent.md:37–37; intent.md:97–97

次の作業: 回答済み（DEC-008）。自律走行・一時停止からは一時停止へ（TR-09・TR-15）、手動走行・事前地図作成では直前モードを維持し理由を記録（TR-14・TR-16）。

#### H-007 PC再起動後の一時停止モードから再開するときの自己位置初期化

RQ-I064 により PC 再起動後は一時停止モードへ復帰する。RQ-I014 は再開時に「再開する地点の再設定は必須ではない」とするが、PC 再起動後は自己位置推定器の状態が失われている。 再開時の初期化を、(a) 永続化した最終推定姿勢（SO-01）で自動初期化、(b) 人が初期位置を再指定してから再開、のどちらにするか。 (a) は PC 停止中に車体が動かされた場合に誤った初期位置で走行開始する可能性がある。

- 人が初期位置を再指定してから再開（RQ-I014 を同一プロセス内の一時停止に限る読み）：PC 再起動後の再開に人の操作が1回増える。誤初期化のリスクを下げる。
- 永続化した最終推定姿勢で自動初期化：操作は増えないが、停止中の車体移動を検出できない。推定成立の確認を再開の guard にする必要がある。

推奨: 人が初期位置を再指定してから再開（RQ-I014 を同一プロセス内の一時停止に限る読み）

影響ID: `RQ-I064`, `RQ-I014`, `TR-02`, `TR-10`, `SO-01`, `ND-07`

出典: intent.md:92–92; intent.md:17–17; intent.md:97–97; intent.md:14–14

次の作業: 回答済み（DEC-009）。PC 再起動後の再開は人の初期位置要求（IFD-39）の受理後に限る。保存した最終推定姿勢は初期化に使わない。

#### H-008 地図作成終了ボタン押下後に入るモード

RQ-I008 は地図作成終了ボタンで地図作成が終了すると定めるが、終了後に入るモードを明記していない。4モード（RQ-I065）のうち、どれに入るか。

- 手動走行モード（既定モード）：RQ-I066 の既定モードへ戻る。変換（RQ-I009）は手動走行中にバックグラウンドで完了する。
- 一時停止モード：一時停止を自律走行の一時停止（RQ-I026）と定義しているため意味の再定義が必要。

推奨: 手動走行モード（既定モード）

影響ID: `RQ-I008`, `TR-04`

出典: intent.md:11–11; intent.md:94–94; intent.md:93–93

次の作業: 回答済み（DEC-010）。地図作成終了後は手動走行。地図変換は processing_state（SO-01／SO-04）として続け、変換専用モードは追加しない。

#### P-001 intent.md:99 の座標系文言の更新案（人の作業）

DEC-007 により base_link は Nav2 前提（REP-103：x前方・y左方・z上方）とし、LiDAR・IMU の座標方向は gouda_monitor の /config で指定して内部で変換する。 intent.md:99 は「-y方向を車体前方、+x方向を車体右方、+z方向を上方」と記したまま。文言を更新するか、現文を残して判断台帳で補足するか。

- intent.md:99 を人が更新する：車体座標系を REP-103 とし、センサ座標方向は /config 指定・内部変換と明記。次の authority revision で機械検証。
- 現文を残し判断台帳（DEC-007）で補足する：正本と上位要求の文言が一致しない状態が続く。C-018 は resolved_by_decision のまま。

推奨: intent.md:99 を人が更新する

影響ID: `RQ-I071`

出典: intent.md:99–99; intent.md:80–80; intent.md:2–2

次の作業: 解消（REV-004）。人が intent.md:99 を置換した（第3版 100 行、AR-003、C-021）。原文（第2版）「EMC-270の車体座標系は…LiDARの座標系に合わせ、-y方向を車体前方…」、 現文（第3版）「LiDARないしはdriverが出す点群の座標系は、-y方向を車体前方…とするものであうが、これをNav2用に変換する」。AI の評価: 標準座標系（REP-103）の base_link と /config によるセンサ座標方向の変換で実装は足りる。

#### H-009 車体出力段階の値の不一致（intent 700 ms / 1 s と firmware・bridge の 250 ms）と 700 ms の配分

intent.md:102 は「PC指令のtimeout=700ms、ESP32のwatchdog=1s周期」とし、不適切なら適切な値を考えて報告せよとする。 実装リポジトリの firmware gouda_dualsense_usb は kLinkTimeoutMs=250 ms（PC 指令・BT 報告の双方。docs/gouda_protocol_v3.md「A PC COMMAND age of 250 ms or more clears autonomous enable」）、 PC bridge（gouda_vehicle/hardware_bridge.py）は STATUS 鮮度 0.25 s 不足で DISARM。旧 firmware gouda_esp32 も kReportTimeoutMs=250 ms。 また「PC指令のtimeout 700 ms」が cmd_vel→motion_controller の途絶判定（PRM-08）か、joystick→bridge の期限（PRM-09）か、両方の合計かは文面から一意でない。 AI の評価: (1) ESP32 側の 1 s は既存 firmware の 250 ms より長く、firmware を変更しない限り実効値は 250 ms。既存の停止条件は AI の判断で外さない（DEC-006）。 (2) bridge は cmd_vel の有無に関係なく一定周期（PRM-14、firmware の 250 ms に対し十分短い値。firmware の status 送信は 50 ms 周期）で最新値または中立を送る必要がある。 (3) PC 側 700 ms は Nav2 controller の制御周期（上流既定 20 Hz=50 ms、PRM-17）の 14 周期分で、cmd_vel 停止後も最大 0.7 s 最後の速度が続く。 途絶判定としては 3 周期程度（150 ms）でも成立し、停止までの惰走を短くできる。ただし一時停止の正規の停止経路は Nav2 取消＋motion_hold（IFD-40）であり、timeout は異常時の保険。

- intent の値（PC 700 ms、ESP32 1 s）を採用し firmware/bridge を人が変更する：既存 firmware の 250 ms を 1 s へ変更する作業と実機確認が必要。PC 側は 700 ms で惰走最大 0.7 s。
- ESP32 は既存 250 ms を維持し、PC 側 timeout を controller 周期の数倍（例 150 ms。周期は PRM-17 の決定後）にする：firmware 無変更。bridge の送信周期（PRM-14）を 250 ms に対し十分短く設計する必要がある。intent.md:102 の値の更新は人の作業。
- 保留：PRM-08・PRM-13 は未確定のまま。車体出力段階（RQ-I044 の順序）の実装前に決定が必要。

推奨: ESP32 は既存 250 ms を維持し、PC 側 timeout を controller 周期の数倍（例 150 ms。周期は PRM-17 の決定後）にする

影響ID: `RQ-I075`, `PRM-08`, `PRM-09`, `PRM-13`, `PRM-14`, `ND-11`, `ND-12`, `IFD-17`

出典: intent.md:102–102; intent.md:91–91; intent.md:96–96; intent.md:35–35

次の作業: 閉じた（DEC-053）。値の割当: cmd_vel 途絶=PRM-08 0.7 s（motion_controller）、ESP32 期限切れ=PRM-13 1.0 s（最後の有効 PC 指令受信から）、Bluetooth 途絶=PRM-21 0.25 s（別枠の既存動作）。 意味の整理は docs/vehicle_output_timing.md。PRM-09・PRM-14 は未確定のまま（Q-05・G-FIRMWARE）。

#### H-010 実機 ESP32 に書き込まれている firmware と通信プロトコルの版

実装リポジトリには firmware/gouda_dualsense_usb（protocol v3、64 byte フレーム、ARM/DISARM、STATUS）と firmware/gouda_esp32（旧版、legacy_control）の 2 系統があり、 README はいずれも「実機への書き込み・実接続は未実施」とする。実機の ESP32 に書き込まれている版はどれか。gouda_protocol_v3.md との照合（DEC-006）はこの版が確定してから成立する。

- gouda_dualsense_usb（protocol v3）が書き込まれている：IFD-17 は v3 フレーム、IFD-38 の STATUS 項目が取得可能。watchdog は 250 ms（H-009）。
- gouda_esp32（旧版）が書き込まれている：STATUS 相当の取得可否を旧版コードで再照合。ARM/DISARM の有無も確認が必要。
- 未書き込み・不明：実機確認（T-18 相当）まで IFD-17・IFD-38 は案。

推奨: gouda_dualsense_usb（protocol v3）が書き込まれている

影響ID: `Q-03`, `Q-09`, `IFD-17`, `IFD-38`, `ND-12`, `M-025`

出典: intent.md:34–34; intent.md:35–35; intent.md:96–96

次の作業: 回答済み（DEC-030「初めから書き直せ」）。実機の既存 firmware 版の確認は不要になった。新 firmware の設計は G-FIRMWARE に一本化（DEC-034）。参照抽出は research/joystick270_firmware/extract.md。

#### H-011 速度マスクの帯の幅と帯外の扱い（Speed Filter 採用に伴う幾何条件）

Speed Filter（DEC-031）は mask の cell 値（位置）で上限を決めるため、区間（進行順序）の属性である RQ-I010 の上限とは別物である。再訪・交差・重複では区間ごとの値を表現できない。 帯幅（PRM-19）・重複部分の規則・帯外（cell=0 は無制限）・マスク外（発行なし＝直前値が残る）・未読込時（発行なし＝上限なし）の定義方法は research/speed_filter_reapply_h011.md §3。値は Q-06・Q-07・Q-12 が未決のため tbd。 承認は、復帰後の再適用を含む (a)(b) の再比較（同 §5、H-001）を見てから人が行う。

- 重複は進行方向で後の区間を優先、帯外は無制限（Nav2 の挙動のまま）：要求どおりの区間上限は帯が重ならない範囲でのみ成立。帯外は controller の最大速度。
- 重複は低い方の上限を優先、帯外は無制限：安全側だが重複区間では要求値より低い上限になる。
- 重複を禁止し、生成時にエラーとして人が waypoint を直す：要求どおりの値を保てるが、往復・交差する経路を作れない。
- Speed Filter をやめ Gouda 側発行器（案 (b)）に戻す：区間上限の意味に一致し帯の定義が不要。H-001 の再判断（RQ-I021 の承認）が必要。

推奨: 推奨なし。前回の推奨（帯外に最低速度を敷く）は運用方針の追加のため取り下げた。定義方法のみ提示し、値は tbd。

影響ID: `IFD-14`, `IFD-41`, `IFD-42`, `PRM-19`, `PRM-20`, `ND-02`, `ND-10`

出典: intent.md:13–13; intent.md:26–26; intent.md:90–90

次の作業: 回答済み（DEC-045）。重複 cell は低い方の上限、再訪・重複ルートには同じ値を設定。帯幅 PRM-19 は tbd（Q-06・Q-07・Q-12）、帯外は Nav2 の挙動（無制限）。境界の揺らぎは TS-16 で実機調整し、新しい人の判断事項にしない。

#### H-012 新 firmware の手動操作経路（Bluetooth ゲームパッド優先か、純正ジョイスティックへのリレー切替か）

基本契約は「bluetooth接続の手動操作がESP32で優先される」「bluetooth gamepadからの指令が途絶えたらESP32が中立を出す」（RQ-I023・RQ-I024）。 参照 Joystick270-Firmware は Bluetooth を持たず、手動操作は純正ジョイスティックへリレーで戻す方式（DISARM・指令途絶・電源断で純正側）。新 firmware をどの手動経路で設計するか。

- Bluetooth ゲームパッド優先を維持（基本契約どおり）。リレー・純正ジョイスティックは使わない：現 firmware の方式を新 firmware で再実装。ESP32 に Bluetooth（Bluepad32 等）が必要。参照 firmware のリレー・ADC 監視・中央探索は採用しない部分が出る。
- 参照設計のリレー＋純正ジョイスティックに切り替える（基本契約の文言変更）：intent.md:34-35 の変更が必要（人の編集）。手動操作は純正ジョイスティック。ESP32 故障・電源断で自動的に純正側へ戻る。
- 両立（Bluetooth 優先＋リレーで純正へも戻れる）：回路（Joystick270 基板のリレー）と Bluetooth の両方を新 firmware が扱う。優先順位の定義が必要。

推奨: 保留せず人が決める。AI は推奨を出さない（基本契約の変更可否は人の判断）。

影響ID: `ND-17`, `IFD-17`, `IFD-43`, `SO-11`, `M-025`, `M-026`, `M-027`, `Q-09`

出典: intent.md:34–34; intent.md:35–35; intent.md:96–96

次の作業: 回答済み（DEC-037）。リレー不使用、DAC 常時出力。手動経路の読み（Bluetooth ゲームパッド→ESP32→DAC）の確認は DEC-042。新 firmware の設計は G-FIRMWARE。

#### H-013 区間属性の上限と位置ベース上限（Speed Filter）の食い違いの解消方法

RQ-I078（区間 i→i+1 の属性としての上限）を、Speed Filter の位置ベース上限（DEC-031）と重複時は低い方（DEC-045）でどう実現するか。 再訪・交差・重複する区間に異なる上限を設定した場合、実行時の上限は位置で決まり、区間順序には従わない。

- 案 A（推奨）位置ベースを採用し、再訪・重複する区間には同じ上限を設定する運用。waypoint_manager は重複 cell で値が異なる区間を保存時に警告し、mask は低い方を採用する：現在の設計（DEC-031・DEC-045・IFD-41・TS-14）を維持。RQ-I078 の「区間の属性」は編集時の属性として成立し、実行時は位置に写像される。intent.md に「実行時は位置で適用し、重複区間は同じ値」を人が補足する。影響は ND-02（警告）、IFD-41 の生成規則のみ
- 案 B 区間順序に従う発行器を Gouda 側に置く（DEC-011 の方式に戻す）：区間ごとの値を厳密に実現できるが DEC-031 を覆す。Nav2 feedback に基づく区間判定・再開・復帰後の再適用の設計（H-001 で比較済み）を再度負う。影響は IFD-14 の発行元、ND-03、TS-01〜TS-06、TR-10・TR-13
- 案 C 再訪・重複する経路を waypoint 編集で禁止する（保存時に拒否）：食い違いは生じないが、同じ道を往復する経路（RQ-I001 の開始地点へ戻るルート）が作れない可能性がある。影響は ND-02・IFD-30 の検証規則

推奨: 案 A（推奨）位置ベースを採用し、再訪・重複する区間には同じ上限を設定する運用。waypoint_manager は重複 cell で値が異なる区間を保存時に警告し、mask は低い方を採用する

影響ID: `RQ-I078`, `C-023`, `IFD-14`, `IFD-41`, `IFD-42`, `ND-02`, `ND-10`, `TS-02`, `TS-03`, `TS-14`, `PRM-19`

出典: intent.md:13–13; intent.md:26–26

次の作業: 回答済み（DEC-059、案 A）。位置ベースを維持し、再訪・重複する区間には同じ上限を設定する運用。保存時に waypoint_manager が警告（ND-02、TS-22）。RQ-I078 への補足は人の編集（任意）。

### 資料不足と技術作業

- **Q-01**（technical）ROS 2・Nav2の採用版 次の作業: REV-003: 採用版は実車PCの実測で ROS 2 Jazzy / Nav2 1.3.13 と確定（DEC-012）。NavigateThroughPoses・SpeedLimit・cmd_vel の IDL と既定値は上流 jazzy 645abd95 で確認（IFD-13〜15）。
- **Q-02**（technical）自己位置推定の方式・成立条件 次の作業: 次の下位設計で、上位要求に従い技術案・標準IF・構成を具体化する。
- **Q-03**（source_missing）既存車両通信と制御校正 次の作業: firmware を書き直す（DEC-030）ため既存プロトコルの照合は不要。DAC 端点（方向別 mV）・中立・遅延は実車で計測して人が設定する（参照 firmware は人が端点を登録し中央範囲を車輪速度で探索する方式）。計測計画は generated/measurement_plan.md。
- **Q-08**（technical）P介入で通った点の扱い 次の作業: 解消（REV-009）。通過・到達判定は Nav2（C-004、RQ-I011）。P 介入中も Nav2 の判定に従い、Gouda は独自に計上しない。
- **Q-09**（source_missing）Bluetooth切断時のP状態 次の作業: 新 firmware の手動経路（H-012）が決まってから、Bluetooth 切断時の挙動を設計・確認する。
- **Q-11**（technical）補助構成と独自IFの採用 次の作業: 暫定ベースラインとして採用（DEC-053）。独自型 4 件（IFD-01・02・28・37・40）の .msg/.srv/.action 定義は下位設計の継続で行う。個別の最終承認は含まれない。
- **Q-13**（technical）後工程の保留 次の作業: 次の下位設計で、上位要求に従い技術案・標準IF・構成を具体化する。
- **G-ARCH**（technical）旧候補を現在要求へ適合させる下位設計が未実施。 次の作業: 責務、標準IF、所有者、配置、QoS、時刻を次段階で設計。資料の確定明示なしは人の承認待ちにしない。
- **G-PARAM**（technical）パラメータ群は原文参照で移行し、個別型・キー・単位・設定所有者は未設計。 次の作業: 技術的な分解はAIが行う。実車採用値・試験条件はQ-03〜Q-06。
- **G-RECOVERY**（technical）最新の復旧順序と故障別復帰先に対応する下位設計は未実施。 次の作業: 必要状態だけの復元・旧goal処理を次段階で具体化。人の追加承認や新モードを追加しない。
- **G-TEST**（technical）旧試験はすべて未実行で、旧期待値を含む。 次の作業: 置換対応を参照して次段階で試験を設計。今回の検査器試験と区別する。
- **G-LOG**（technical）独立した記録操作・自動開始条件・欠落追跡の具体IFと状態所有者が不足。 次の作業: 最新要求の範囲内で次段階に設計。復帰時の無断自動Recordを追加しない。
- **G-GRAPH**（technical）図中の枠・注記・内部構成・接続を、承認済みNode/IFと同一視できない。 次の作業: 原IDを保ちながら次段階で責務境界を整理。名称一致以外の自動統合をしない。
- **G-ENDPOINT**（technical）logger、Navigation内境界、PC構成node、safety_gouda_safety_supervisor等の具体参照が未解決。 次の作業: 原文を保持し次の下位設計で対応付け。誤記と推測して黙って修正しない。
- **U-DRAW-001**（source_missing）targetPointはあるがtarget IDがない。接続先未特定。 次の作業: 閉じる（REV-009）。図は参照のみで下位設計は依存しない。接続先は推測せず原文（targetPoint）を保持。
- **U-DRAW-002**（source_missing）図のESP32押下検知線とExcelの取得不能記載が衝突する。 次の作業: REV-002: 機能は RQ-I072 により不採用（C-017）のため、現物回路・既存実装での確認は設計上不要。資料間の不一致は履歴として保持し、解決済みとは記録しない。
- **U-DRAW-003**（source_missing）図のheartbeat_and_status/collision_stop_requestとExcelの任意/未提供記載の対応が未確認。 次の作業: 解消（REV-004）。heartbeat は表示・診断のみ（DEC-006）、collision_stop_request は不採用（DEC-005）。資料間の不一致は履歴として保持。
- **U-HISTORY**（source_missing）CH-02はlocal_odometry/mission_managerが図に未記載とするが、現在図には両ラベルが存在する。 次の作業: 閉じる（REV-009）。変更記録と図は履歴・参照であり下位設計は依存しない。
- **V-001**（source_missing）人の申告は「ROS2 jazzy / ubuntu 24.0.5」（DEC-003）。実車PC（aya@10.211.55.4）への鍵認証は拒否され、AIはパスワード認証を行わないため、 実車PC上の /opt/ros/<distro> と nav2 パッケージ版は未照合。上流 jazzy ブランチ（navigation2 commit 645abd95…、nav2_msgs 1.3.13）の仕様を暫定の照合先にしている。 次の作業: 解消（REV-003）。実車PC: Ubuntu 24.04.5 LTS、/opt/ros/jazzy、Nav2 1.3.13（DEC-012、research/vehicle_pc/2026-10-09_vehicle_pc_versions.txt）。 上流 jazzy 645abd95 の package 版 1.3.13 と一致。バイナリ内 IDL の直接照合は行っていない。
- **G-FIRMWARE**（technical）参照抽出（research/joystick270_firmware/extract.md §8）を入力に、新 firmware のプロトコル・設定・watchdog・ARM 手順・STATUS/EVENT・PC bridge の対応を設計する。firmware の版の管理はここに一本化（DEC-034）。 次の作業: H-012（手動経路）と H-009（時間値）の回答後に、経路に依存しない部分から設計する。実装は工程5（ゲート3承認後）。
- **G-TUNING**（technical）境界付近の揺らぎ（帯幅 PRM-19、境界セル、減速タイミング）は詳細設計しない（DEC-055）。帯幅は mask 生成器の入力として実機調整で決め、 揺れ幅・継続時間・減速距離（PRM-22〜24）は TS-16 の記録項目で合否判定に使わない。これらは設計規則にも人の判断事項にもしない（DEC-045・DEC-049）。 次の作業: 実車試験の段階で TS-16 の記録を材料に調整する。値は正本に書かず、調整記録を research/vehicle_pc/ 以下に残す。設計検査では「値未確定（実機調整）」として扱う。

接続先未特定は `U-DRAW-001`。原ページ `lc-_yTM2-hEJOly5ozWo`、線 `2TSgiu6-nVzXwyzMdGmE-18`。`targetPoint` は残し、`to_ref: null` を維持。

## 重大な基本契約・未検証前提

これらは移行検査合格をもって成立したとは判断していない。

- `RQ-I011`（intent.md:14）：9. ここから自律走行開始の準備をする。waypoint_managerでwaypointのファイルと地図の組を選択する。地図とwaypointは重ねた状態でプレビューが表示される。次に初期位置と向きを人間がある程度指定し、自律走行開始ボタンを一回押すと、自己位置推定しながら、nav2によってナビゲーションが開始される。自律走行開始ボタンを押した後は、追加の承認を挟まない。waypointの通過や到達の判定はNav2が行う。
- `RQ-I013`（intent.md:16）：・異常終了後は、自動復帰し、その依存関係は[プロセス再起動 → mission状態の復元 → 当該missionに属する旧Nav2 goalの終了または破棄の確認→ 自律走行指令の再許可]の順である。復旧に人の追加承認は求めない。各段階の成否をログに記録する。復旧できない場合、または復旧の試行回数が上限に達した場合は、一時停止モードに入り理由を記録する。
- `RQ-I015`（intent.md:19）：・人間が明示的に自律走行終了ボタンを押さない限り、自律走行を終了してはならない。また、万が一navigationが異常終了した場合や、一時停止ボタンを押した場合でも、ログ取りは継続する。ログは、PCが受信した入力、判断と理由・状態遷移・各段の指令・通信結果・設定状況（地図作成前後と自律走行開始前後、設定変更後に記録）を記録し、データの欠落があった場合はその範囲も記録する。受信していない値は推測で記録しない。ログ取りはRecordボタンを押せばいつでも開始でき、Stop Recordボタンを押せばいつでも終了できる。また、地図作成開始時と自律走行開始時にRecordボタンが押されていない場合は、自動でRecordを開始し、人間が地図作成終了ボタンや自律走行終了ボタンを押したときに停止される。Recordの自動開始の契機は、人が押した地図作成開始ボタンと自律走行開始ボタンのみとする。異常終了後の復帰や再開ボタンでは開始しないが、ログ取得を再開できるようにする。ログ取得に失敗しても走行は止めない。
- `RQ-I018`（intent.md:24）：後退と再計画はNav2のBTが管理し、Goudaの責務ではない。
- `RQ-I019`（intent.md:25）：Navigationの実行主体はNav2とし、Gouda側で二重に実行しない。
- `RQ-I020`（intent.md:26）：速度上限は、Nav2標準のSpeedLimit経路を単一の発行元から適用する。cmd_velの後段で独自に速度を抑える処理は加えない。
- `RQ-I023`（intent.md:34）：・bluetooth接続の手動操作がESP32で優先される
- `RQ-I024`（intent.md:35）：・bluetooth gamepadからの指令が途絶えたらESP32が中立を出す。
- `RQ-I025`（intent.md:36）：自律走行の開始は人の開始操作でのみ行う。再開（異常終了後の復帰）は自動で行ってよい。人が一時停止ボタン/自律走行終了ボタンを押した後は、プロセスが再起動しても、人の操作なしに走行を再開せず、一時停止状態/手動走行に自動で戻るところまで進める。
- `RQ-I027`（intent.md:38）：・ 双方向の歯止め：AIは基本契約を独断で増やさず、優先順位を理由に既存の保護を削らない。追加の保護は、必要性・根拠・開発への影響を添えた提案として出す。
- `RQ-I062`（intent.md:90）：・境界到達時点で、実速度が進入区間の上限以下であることは保証しなくて良い。
- `RQ-I063`（intent.md:91）：・自律走行中にPCからの指令が途絶えた場合も、中立位置に戻す。
- `RQ-I064`（intent.md:92）：・node異常、推定不能、通信途絶、からの自動復帰後は直前の状態（自律走行/事前地図作成/一時停止/手動走行）に復帰する。PC再起動後は、直前が自律走行/事前地図作成/一時停止モードなら一時停止モードへ復帰し、手動走行モードなら手動走行モードに復帰する。
- `RQ-I065`（intent.md:93）：・ソフトのモードは自律走行/事前地図作成/一時停止/手動走行の4モードしかない。完全停止モードは存在しない。
- `RQ-I080`（intent.md:95）：・起動直後は手動走行モードに入る。手動走行モードがデフォルトのモード。
- `RQ-I068`（intent.md:96）：・esp32は、現在採用している指令源からの入力が途絶えたら中立を出す。
- `RQ-I069`（intent.md:97）：・故障の種類と復帰先のモードに応じて、必要な状態だけを復元する。旧goalと新goalが競合しない方法で自動復帰し、各処理の成否を記録する。自律走行指令の再許可は、自律走行へ復帰する場合に限る。
- `RQ-I070`（intent.md:98）：・センサー類のTFは未決とし、gouda_monitorの/configで設定できるものとする。タブ遷移で設定が消えないように。
- `RQ-I071`（intent.md:99）：・車体は全長 1,010 mm × 全幅 598 mm × 全高 950 mmの直方体の中にあるとする。EMC-270の車体座標系は、左右後輪の駆動軸中央の地面投影点を原点とする。LiDARの座標系に合わせ、-y方向を車体前方、+x方向を車体右方、+z方向を上方とする。`base_footprint` は原点 `(0, 0, 0)`、`base_link` は後輪軸中心高さに置く。後輪径は330 mmなので、`base_link` の高さは約 `z = 0.165 m` とする。ホイールベースは415 mmであり、前キャスタ基準位置は後輪軸から約 `y = -0.415 m` 前方にある。LiDARやIMUなど各センサの取付位置は、この車体座標系に対する静的TFとして後から実測値を設定する。
- `RQ-I074`（intent.md:100）：・車体は全長 1,010 mm × 全幅 598 mm × 全高 950 mmの直方体の中にあるとする。EMC-270の車体座標系は、左右後輪の駆動軸中央の地面投影点を原点とする。LiDARないしはdriverが出す点群の座標系は、-y方向を車体前方、+x方向を車体右方、+z方向を上方とするものであうが、これをNav2用に変換する。`base_footprint` は原点 `(0, 0, 0)`、`base_link` は後輪軸中心高さに置く。後輪径は330 mmなので、`base_link` の高さは約 `z = 0.165 m` とする。ホイールベースは415 mmであり、前キャスタ基準位置は後輪軸から約 `y = -0.415 m` 前方にある。LiDARやIMUなど各センサの取付位置は、この車体座標系に対する静的TFとして後から実測値を設定する。

ESP32中立出力・手動優先・通信仕様・DAC値の実機成立はQ-03/Q-05/Q-09で未確認。PC側の中立出力を車体全体の停止保証に読み替えない。既存の保護はこの移行では追加・削除していない。

## 既存ID全件の移行対応表

baseline198列が「対象」の198件に、原文の変更記録4件を別枠で追加。旧ID=モデルID。

| 既存ID | モデルID | 種別 | 出典 | baseline198 | 現在の扱い |
|---|---|---|---|---|---|
| M-001 | M-001 | module | Excel モジュール定義!A2:AD2 | 対象 | partially_superseded |
| M-002 | M-002 | module | Excel モジュール定義!A3:AD3 | 対象 | partially_superseded |
| M-003 | M-003 | module | Excel モジュール定義!A4:AD4 | 対象 | legacy_candidate |
| M-004 | M-004 | module | Excel モジュール定義!A5:AD5 | 対象 | legacy_candidate |
| M-005 | M-005 | module | Excel モジュール定義!A6:AD6 | 対象 | partially_superseded |
| M-006 | M-006 | module | Excel モジュール定義!A7:AD7 | 対象 | partially_superseded |
| M-007 | M-007 | module | Excel モジュール定義!A8:AD8 | 対象 | partially_superseded |
| M-008 | M-008 | module | Excel モジュール定義!A9:AD9 | 対象 | legacy_candidate |
| M-009 | M-009 | module | Excel モジュール定義!A10:AD10 | 対象 | partially_superseded |
| M-010 | M-010 | module | Excel モジュール定義!A11:AD11 | 対象 | partially_superseded |
| M-011 | M-011 | module | Excel モジュール定義!A13:AD13 | 対象 | partially_superseded |
| M-012 | M-012 | module | Excel モジュール定義!A14:AD14 | 対象 | partially_superseded |
| M-013 | M-013 | module | Excel モジュール定義!A15:AD15 | 対象 | unresolved |
| M-014 | M-014 | module | Excel モジュール定義!A16:AD16 | 対象 | legacy_candidate |
| M-015 | M-015 | module | Excel モジュール定義!A17:AD17 | 対象 | legacy_candidate |
| M-016 | M-016 | module | Excel モジュール定義!A18:AD18 | 対象 | partially_superseded |
| M-017 | M-017 | module | Excel モジュール定義!A19:AD19 | 対象 | partially_superseded |
| M-018 | M-018 | module | Excel モジュール定義!A20:AD20 | 対象 | partially_superseded |
| M-019 | M-019 | module | Excel モジュール定義!A21:AD21 | 対象 | legacy_candidate |
| M-020 | M-020 | module | Excel モジュール定義!A22:AD22 | 対象 | legacy_candidate |
| M-021 | M-021 | module | Excel モジュール定義!A23:AD23 | 対象 | legacy_candidate |
| M-022 | M-022 | module | Excel モジュール定義!A24:AD24 | 対象 | legacy_candidate |
| M-023 | M-023 | module | Excel モジュール定義!A25:AD25 | 対象 | unresolved |
| M-024 | M-024 | module | Excel モジュール定義!A26:AD26 | 対象 | legacy_candidate |
| M-025 | M-025 | module | Excel モジュール定義!A27:AD27 | 対象 | partially_superseded |
| M-026 | M-026 | module | Excel モジュール定義!A28:AD28 | 対象 | legacy_candidate |
| M-027 | M-027 | module | Excel モジュール定義!A29:AD29 | 対象 | legacy_candidate |
| M-028 | M-028 | module | Excel モジュール定義!A30:AD30 | 対象 | reference_only |
| M-029 | M-029 | module | Excel モジュール定義!A31:AD31 | 対象 | legacy_candidate |
| M-030 | M-030 | module | Excel モジュール定義!A32:AD32 | 対象 | legacy_candidate |
| M-031 | M-031 | module | Excel モジュール定義!A33:AD33 | 対象 | legacy_candidate |
| M-032 | M-032 | module | Excel モジュール定義!A34:AD34 | 対象 | legacy_candidate |
| M-033 | M-033 | module | Excel モジュール定義!A35:AD35 | 対象 | legacy_candidate |
| M-034 | M-034 | module | Excel モジュール定義!A36:AD36 | 対象 | legacy_candidate |
| M-035 | M-035 | module | Excel モジュール定義!A37:AD37 | 対象 | legacy_candidate |
| M-036 | M-036 | module | Excel モジュール定義!A38:AD38 | 対象 | legacy_candidate |
| M-037 | M-037 | module | Excel モジュール定義!A39:AD39 | 対象 | partially_superseded |
| M-038 | M-038 | module | Excel モジュール定義!A40:AD40 | 対象 | legacy_candidate |
| IF-001 | IF-001 | interface | Excel インターフェース定義!A2:P2 | 対象 | legacy_candidate |
| IF-002 | IF-002 | interface | Excel インターフェース定義!A3:P3 | 対象 | legacy_candidate |
| IF-003 | IF-003 | interface | Excel インターフェース定義!A4:P4 | 対象 | legacy_candidate |
| IF-004 | IF-004 | interface | Excel インターフェース定義!A5:P5 | 対象 | legacy_candidate |
| IF-005 | IF-005 | interface | Excel インターフェース定義!A6:P6 | 対象 | legacy_candidate |
| IF-006 | IF-006 | interface | Excel インターフェース定義!A7:P7 | 対象 | legacy_candidate |
| IF-007 | IF-007 | interface | Excel インターフェース定義!A8:P8 | 対象 | legacy_candidate |
| IF-008 | IF-008 | interface | Excel インターフェース定義!A9:P9 | 対象 | legacy_candidate |
| IF-009 | IF-009 | interface | Excel インターフェース定義!A10:P10 | 対象 | legacy_candidate |
| IF-010 | IF-010 | interface | Excel インターフェース定義!A11:P11 | 対象 | legacy_candidate |
| IF-011 | IF-011 | interface | Excel インターフェース定義!A12:P12 | 対象 | partially_superseded |
| IF-012 | IF-012 | interface | Excel インターフェース定義!A13:P13 | 対象 | partially_superseded |
| IF-013 | IF-013 | interface | Excel インターフェース定義!A14:P14 | 対象 | partially_superseded |
| IF-014 | IF-014 | interface | Excel インターフェース定義!A15:P15 | 対象 | legacy_candidate |
| IF-015 | IF-015 | interface | Excel インターフェース定義!A16:P16 | 対象 | partially_superseded |
| IF-016 | IF-016 | interface | Excel インターフェース定義!A17:P17 | 対象 | partially_superseded |
| IF-017 | IF-017 | interface | Excel インターフェース定義!A18:P18 | 対象 | legacy_candidate |
| IF-018 | IF-018 | interface | Excel インターフェース定義!A19:P19 | 対象 | legacy_candidate |
| IF-019 | IF-019 | interface | Excel インターフェース定義!A20:P20 | 対象 | partially_superseded |
| IF-020 | IF-020 | interface | Excel インターフェース定義!A21:P21 | 対象 | partially_superseded |
| IF-021 | IF-021 | interface | Excel インターフェース定義!A22:P22 | 対象 | legacy_candidate |
| IF-022 | IF-022 | interface | Excel インターフェース定義!A23:P23 | 対象 | partially_superseded |
| IF-023 | IF-023 | interface | Excel インターフェース定義!A24:P24 | 対象 | legacy_candidate |
| IF-024 | IF-024 | interface | Excel インターフェース定義!A25:P25 | 対象 | legacy_candidate |
| IF-025 | IF-025 | interface | Excel インターフェース定義!A26:P26 | 対象 | legacy_candidate |
| IF-026 | IF-026 | interface | Excel インターフェース定義!A27:P27 | 対象 | legacy_candidate |
| IF-027 | IF-027 | interface | Excel インターフェース定義!A28:P28 | 対象 | legacy_candidate |
| IF-028 | IF-028 | interface | Excel インターフェース定義!A29:P29 | 対象 | legacy_candidate |
| IF-029 | IF-029 | interface | Excel インターフェース定義!A30:P30 | 対象 | legacy_candidate |
| IF-030 | IF-030 | interface | Excel インターフェース定義!A31:P31 | 対象 | legacy_candidate |
| IF-031 | IF-031 | interface | Excel インターフェース定義!A32:P32 | 対象 | legacy_candidate |
| IF-032 | IF-032 | interface | Excel インターフェース定義!A33:P33 | 対象 | reference_only |
| IF-033 | IF-033 | interface | Excel インターフェース定義!A34:P34 | 対象 | legacy_candidate |
| IF-034 | IF-034 | interface | Excel インターフェース定義!A35:P35 | 対象 | legacy_candidate |
| IF-035 | IF-035 | interface | Excel インターフェース定義!A36:P36 | 対象 | legacy_candidate |
| IF-036 | IF-036 | interface | Excel インターフェース定義!A37:P37 | 対象 | legacy_candidate |
| IF-037 | IF-037 | interface | Excel インターフェース定義!A38:P38 | 対象 | legacy_candidate |
| IF-038 | IF-038 | interface | Excel インターフェース定義!A39:P39 | 対象 | partially_superseded |
| IF-039 | IF-039 | interface | Excel インターフェース定義!A40:P40 | 対象 | partially_superseded |
| IF-040 | IF-040 | interface | Excel インターフェース定義!A41:P41 | 対象 | partially_superseded |
| IF-041 | IF-041 | interface | Excel インターフェース定義!A42:P42 | 対象 | legacy_candidate |
| IF-042 | IF-042 | interface | Excel インターフェース定義!A43:P43 | 対象 | legacy_candidate |
| IF-043 | IF-043 | interface | Excel インターフェース定義!A44:P44 | 対象 | legacy_candidate |
| IF-044 | IF-044 | interface | Excel インターフェース定義!A45:P45 | 対象 | legacy_candidate |
| IF-045 | IF-045 | interface | Excel インターフェース定義!A46:P46 | 対象 | legacy_candidate |
| IF-046 | IF-046 | interface | Excel インターフェース定義!A47:P47 | 対象 | legacy_candidate |
| S-01 | S-01 | requirement | Excel 基本仕様!A2:D2 | 対象 | legacy_candidate |
| S-02 | S-02 | requirement | Excel 基本仕様!A3:D3 | 対象 | legacy_candidate |
| S-03 | S-03 | requirement | Excel 基本仕様!A4:D4 | 対象 | legacy_candidate |
| S-04 | S-04 | requirement | Excel 基本仕様!A5:D5 | 対象 | partially_superseded |
| S-05 | S-05 | requirement | Excel 基本仕様!A6:D6 | 対象 | partially_superseded |
| S-06 | S-06 | requirement | Excel 基本仕様!A7:D7 | 対象 | partially_superseded |
| S-07 | S-07 | requirement | Excel 基本仕様!A8:D8 | 対象 | legacy_candidate |
| S-08 | S-08 | requirement | Excel 基本仕様!A9:D9 | 対象 | partially_superseded |
| S-09 | S-09 | requirement | Excel 基本仕様!A10:D10 | 対象 | legacy_candidate |
| S-10 | S-10 | requirement | Excel 基本仕様!A11:D11 | 対象 | legacy_candidate |
| S-11 | S-11 | requirement | Excel 基本仕様!A12:D12 | 対象 | legacy_candidate |
| S-12 | S-12 | requirement | Excel 基本仕様!A13:D13 | 対象 | legacy_candidate |
| S-13 | S-13 | requirement | Excel 基本仕様!A14:D14 | 対象 | partially_superseded |
| S-14 | S-14 | requirement | Excel 基本仕様!A15:D15 | 対象 | partially_superseded |
| S-15 | S-15 | requirement | Excel 基本仕様!A16:D16 | 対象 | partially_superseded |
| S-16 | S-16 | requirement | Excel 基本仕様!A17:D17 | 対象 | legacy_candidate |
| S-17 | S-17 | requirement | Excel 基本仕様!A18:D18 | 対象 | partially_superseded |
| S-18 | S-18 | requirement | Excel 基本仕様!A19:D19 | 対象 | legacy_candidate |
| S-19 | S-19 | requirement | Excel 基本仕様!A20:D20 | 対象 | legacy_candidate |
| S-20 | S-20 | requirement | Excel 基本仕様!A21:D21 | 対象 | legacy_candidate |
| S-21 | S-21 | requirement | Excel 基本仕様!A22:D22 | 対象 | legacy_candidate |
| S-22 | S-22 | requirement | Excel 基本仕様!A23:D23 | 対象 | legacy_candidate |
| S-23 | S-23 | requirement | Excel 基本仕様!A24:D24 | 対象 | legacy_candidate |
| S-24 | S-24 | requirement | Excel 基本仕様!A25:D25 | 対象 | legacy_candidate |
| D-01 | D-01 | data_contract | Excel データ契約!A2:E2 | 対象 | partially_superseded |
| D-02 | D-02 | data_contract | Excel データ契約!A3:E3 | 対象 | partially_superseded |
| D-03 | D-03 | data_contract | Excel データ契約!A4:E4 | 対象 | partially_superseded |
| D-04 | D-04 | data_contract | Excel データ契約!A5:E5 | 対象 | legacy_candidate |
| D-05 | D-05 | data_contract | Excel データ契約!A6:E6 | 対象 | legacy_candidate |
| D-06 | D-06 | data_contract | Excel データ契約!A7:E7 | 対象 | partially_superseded |
| D-07 | D-07 | data_contract | Excel データ契約!A8:E8 | 対象 | partially_superseded |
| D-08 | D-08 | data_contract | Excel データ契約!A9:E9 | 対象 | partially_superseded |
| D-09 | D-09 | data_contract | Excel データ契約!A10:E10 | 対象 | partially_superseded |
| D-10 | D-10 | data_contract | Excel データ契約!A11:E11 | 対象 | legacy_candidate |
| D-11 | D-11 | data_contract | Excel データ契約!A12:E12 | 対象 | legacy_candidate |
| D-12 | D-12 | data_contract | Excel データ契約!A13:E13 | 対象 | legacy_candidate |
| D-13 | D-13 | data_contract | Excel データ契約!A14:E14 | 対象 | legacy_candidate |
| D-14 | D-14 | data_contract | Excel データ契約!A15:E15 | 対象 | legacy_candidate |
| D-15 | D-15 | data_contract | Excel データ契約!A16:E16 | 対象 | legacy_candidate |
| D-16 | D-16 | data_contract | Excel データ契約!A17:E17 | 対象 | partially_superseded |
| D-17 | D-17 | data_contract | Excel データ契約!A18:E18 | 対象 | legacy_candidate |
| D-18 | D-18 | data_contract | Excel データ契約!A19:E19 | 対象 | legacy_candidate |
| D-19 | D-19 | data_contract | Excel データ契約!A20:E20 | 対象 | legacy_candidate |
| D-20 | D-20 | data_contract | Excel データ契約!A21:E21 | 対象 | legacy_candidate |
| D-21 | D-21 | data_contract | Excel データ契約!A22:E22 | 対象 | legacy_candidate |
| D-22 | D-22 | data_contract | Excel データ契約!A23:E23 | 対象 | partially_superseded |
| D-23 | D-23 | data_contract | Excel データ契約!A24:E24 | 対象 | legacy_candidate |
| D-24 | D-24 | data_contract | Excel データ契約!A25:E25 | 対象 | partially_superseded |
| ST-01 | ST-01 | transition | Excel 状態遷移!A2:E2 | 対象 | partially_superseded |
| ST-02 | ST-02 | transition | Excel 状態遷移!A3:E3 | 対象 | partially_superseded |
| ST-03 | ST-03 | transition | Excel 状態遷移!A4:E4 | 対象 | partially_superseded |
| ST-04 | ST-04 | transition | Excel 状態遷移!A5:E5 | 対象 | partially_superseded |
| ST-05 | ST-05 | transition | Excel 状態遷移!A6:E6 | 対象 | legacy_candidate |
| ST-06 | ST-06 | transition | Excel 状態遷移!A7:E7 | 対象 | legacy_candidate |
| ST-07 | ST-07 | transition | Excel 状態遷移!A8:E8 | 対象 | legacy_candidate |
| ST-08 | ST-08 | transition | Excel 状態遷移!A9:E9 | 対象 | legacy_candidate |
| ST-09 | ST-09 | transition | Excel 状態遷移!A10:E10 | 対象 | partially_superseded |
| ST-10 | ST-10 | transition | Excel 状態遷移!A11:E11 | 対象 | partially_superseded |
| ST-11 | ST-11 | transition | Excel 状態遷移!A12:E12 | 対象 | partially_superseded |
| ST-12 | ST-12 | transition | Excel 状態遷移!A13:E13 | 対象 | partially_superseded |
| ST-13 | ST-13 | transition | Excel 状態遷移!A14:E14 | 対象 | legacy_candidate |
| ST-14 | ST-14 | transition | Excel 状態遷移!A15:E15 | 対象 | partially_superseded |
| ST-15 | ST-15 | transition | Excel 状態遷移!A16:E16 | 対象 | legacy_candidate |
| ST-16 | ST-16 | transition | Excel 状態遷移!A17:E17 | 対象 | legacy_candidate |
| ST-17 | ST-17 | transition | Excel 状態遷移!A18:E18 | 対象 | partially_superseded |
| ST-18 | ST-18 | transition | Excel 状態遷移!A19:E19 | 対象 | legacy_candidate |
| ST-19 | ST-19 | transition | Excel 状態遷移!A20:E20 | 対象 | legacy_candidate |
| ST-20 | ST-20 | transition | Excel 状態遷移!A21:E21 | 対象 | partially_superseded |
| T-01 | T-01 | test | Excel 使用・開発検証!A2:E2 | 対象 | legacy_candidate |
| T-02 | T-02 | test | Excel 使用・開発検証!A3:E3 | 対象 | legacy_candidate |
| T-03 | T-03 | test | Excel 使用・開発検証!A4:E4 | 対象 | legacy_candidate |
| T-04 | T-04 | test | Excel 使用・開発検証!A5:E5 | 対象 | legacy_candidate |
| T-05 | T-05 | test | Excel 使用・開発検証!A6:E6 | 対象 | legacy_candidate |
| T-06 | T-06 | test | Excel 使用・開発検証!A7:E7 | 対象 | legacy_candidate |
| T-07 | T-07 | test | Excel 使用・開発検証!A8:E8 | 対象 | legacy_candidate |
| T-08 | T-08 | test | Excel 使用・開発検証!A9:E9 | 対象 | legacy_candidate |
| T-09 | T-09 | test | Excel 使用・開発検証!A10:E10 | 対象 | legacy_candidate |
| T-10 | T-10 | test | Excel 使用・開発検証!A11:E11 | 対象 | legacy_candidate |
| T-11 | T-11 | test | Excel 使用・開発検証!A12:E12 | 対象 | legacy_candidate |
| T-12 | T-12 | test | Excel 使用・開発検証!A13:E13 | 対象 | partially_superseded |
| T-13 | T-13 | test | Excel 使用・開発検証!A14:E14 | 対象 | legacy_candidate |
| T-14 | T-14 | test | Excel 使用・開発検証!A15:E15 | 対象 | partially_superseded |
| T-15 | T-15 | test | Excel 使用・開発検証!A16:E16 | 対象 | legacy_candidate |
| T-16 | T-16 | test | Excel 使用・開発検証!A17:E17 | 対象 | legacy_candidate |
| T-17 | T-17 | test | Excel 使用・開発検証!A18:E18 | 対象 | legacy_candidate |
| T-18 | T-18 | test | Excel 使用・開発検証!A19:E19 | 対象 | partially_superseded |
| T-19 | T-19 | test | Excel 使用・開発検証!A20:E20 | 対象 | legacy_candidate |
| T-20 | T-20 | test | Excel 使用・開発検証!A21:E21 | 対象 | legacy_candidate |
| T-21 | T-21 | test | Excel 使用・開発検証!A22:E22 | 対象 | partially_superseded |
| T-22 | T-22 | test | Excel 使用・開発検証!A23:E23 | 対象 | legacy_candidate |
| T-23 | T-23 | test | Excel 使用・開発検証!A24:E24 | 対象 | partially_superseded |
| T-24 | T-24 | test | Excel 使用・開発検証!A25:E25 | 対象 | partially_superseded |
| T-25 | T-25 | test | Excel 使用・開発検証!A26:E26 | 対象 | legacy_candidate |
| Q-01 | Q-01 | issue | Excel 未決事項!A2:D2 | 対象 | unresolved |
| Q-02 | Q-02 | issue | Excel 未決事項!A3:D3 | 対象 | unresolved |
| Q-03 | Q-03 | issue | Excel 未決事項!A4:D4 | 対象 | unresolved |
| Q-04 | Q-04 | issue | Excel 未決事項!A5:D5 | 対象 | unresolved |
| Q-05 | Q-05 | issue | Excel 未決事項!A6:D6 | 対象 | unresolved |
| Q-06 | Q-06 | issue | Excel 未決事項!A7:D7 | 対象 | unresolved |
| Q-07 | Q-07 | issue | Excel 未決事項!A8:D8 | 対象 | unresolved |
| Q-08 | Q-08 | issue | Excel 未決事項!A9:D9 | 対象 | unresolved |
| Q-09 | Q-09 | issue | Excel 未決事項!A10:D10 | 対象 | unresolved |
| Q-10 | Q-10 | issue | Excel 未決事項!A11:D11 | 対象 | unresolved |
| Q-11 | Q-11 | issue | Excel 未決事項!A12:D12 | 対象 | unresolved |
| Q-12 | Q-12 | issue | Excel 未決事項!A13:D13 | 対象 | unresolved |
| Q-13 | Q-13 | issue | Excel 未決事項!A14:D14 | 対象 | unresolved |
| REF-01 | REF-01 | reference | Excel 参照・変更記録!A2:D2 | 対象 | legacy_candidate |
| REF-02 | REF-02 | reference | Excel 参照・変更記録!A3:D3 | 対象 | legacy_candidate |
| REF-03 | REF-03 | reference | Excel 参照・変更記録!A4:D4 | 対象 | legacy_candidate |
| REF-04 | REF-04 | reference | Excel 参照・変更記録!A5:D5 | 対象 | legacy_candidate |
| REF-05 | REF-05 | reference | Excel 参照・変更記録!A6:D6 | 対象 | partially_superseded |
| REF-06 | REF-06 | reference | Excel 参照・変更記録!A7:D7 | 対象 | legacy_candidate |
| REF-07 | REF-07 | reference | Excel 参照・変更記録!A8:D8 | 対象 | legacy_candidate |
| CH-01 | CH-01 | reference | Excel 参照・変更記録!A9:D9 | 追加CH | legacy_candidate |
| CH-02 | CH-02 | reference | Excel 参照・変更記録!A10:D10 | 追加CH | unresolved |
| CH-03 | CH-03 | reference | Excel 参照・変更記録!A11:D11 | 追加CH | legacy_candidate |
| CH-04 | CH-04 | reference | Excel 参照・変更記録!A12:D12 | 追加CH | legacy_candidate |
| REF-08 | REF-08 | reference | Excel 参照・変更記録!A13:D13 | 対象 | legacy_candidate |

### 新規固定IDの対応

- `M-039`: Excel モジュール定義!B12:O12を含む保存行（IDなしのgouda_section_executor）。現行採用はC-012/G-ARCHで整理。
- `RQ-I...`: intentの要求行。命名・位置の変更で再採番しない。全対応はmanifestとsources。
- `LEG-...`: 元にIDがなかった命名規則・旧モード等。元のシート/行をsourcesに保持。
- `OWN-M-...` / `PAR-M-...` / `FM-M-...` / `EX-M-...`: 同じモジュールの元セルから分離した保持状態・パラメータ群・故障応答・実行配置。
- `DG-...`: drawioページID+要素IDから初回割当したUUID。図形・線・構造要素の原IDはsourcesに保持。
- `MODE-...` / `C-...` / `G-...` / `H-...` / `U-...`: 現モード・変更対応・技術事項・承認事項・資料不足。

## 検査器と試験の再実行

必要パッケージは `tools/requirements.txt` に固定。通常のPython環境ではそのrequirementsを仮想環境へインストールしてから、workspaceルートで次を実行する。

```sh
cd /Users/AYARyoya/Desktop/自己学習/TsukubaChallenge
python3 design/tools/run_migration_checks.py
python3 design/tools/render_migration_review.py
```

今回実行した環境と正確なコマンド、終了コード、成果物ハッシュは `reports/migration_check_run.json`。今回の一時依存パスは `/private/tmp/gouda-model-deps`。再現時には再インストールが必要な場合がある。

試験結果: `reports/migration_tests.txt`。最小YAMLと意図的違反データは `rules/fixtures/`。ID重複、参照切れ、出典欠落に加えて、出典フィールド欠落、承認根拠なし、未確定値0埋め、未接続の隠蔽、問題消失、原文改変、既存ID対応漏れを検出する試験を実施。

| 実行 | 終了コード | 記録 |
|---|---:|---|
| /Users/AYARyoya/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 design/tools/validate_model.py | 0 | design/reports/migration_validator.txt |
| /Users/AYARyoya/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover -s design/rules -p test_*.py -v | 0 | design/reports/migration_tests.txt |

## ファイル配置・作業境界

workspace直下のdesignは、ロボット実装の `tsukuba-autonomous-robot/` Gitリポジトリとは別の場所。実装リポジトリの確認時HEADは `a091ed39eb154b2dff7065840dc13c6478b153da`。既存のdocs/architecture配下の変更には触れていない。
schema/model/manifestは今回新規。intent、Excel、drawio、全抽出成果物は変更前後のSHA-256一致。完成版のROS graph・IF表・故障モード表や図は生成していない。ここにある表は今回要求された移行対応・矛盾・未決事項のレビュー表。
