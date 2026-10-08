# YAML移行レビュー

対象日: 2026-10-08。最新 `intent.md` を上位要求とし、既存抽出結果を入力にした。原資料・intent・抽出結果は変更していない。

## 結果の区別

| 確認対象 | 結果 | 範囲 |
|---|---|---|
| 前段の抽出忠実性 | 48項目一致という既存結果を保持 | 再抽出は行っていない。元資料ハッシュと既存抽出時ハッシュの一致を今回確認 |
| YAMLの形式・移行忠実性 | 合格、違反0件 | 5316件の比較・規則検査。設計テストのケース数ではない |
| 設計内容の妥当性 | 未判定 | 下位設計、ROS版でのIF確認、状態遷移の成立性、実車値は未検証 |
| ロボット実装・ソフト動作 | 未実施 | 移行ツールの試験と、ROS Nodeの動作試験は別 |
| 実車確認・投入判断 | 未実施・人の判断待ち | YAML移行を実車確認済みとは扱わない |

既存定義IDは **198/198件** が同じIDへ移行。加えて既存の変更記録ID `CH-01`〜`CH-04` を保持したため、既存ID対応表は **202件**。198件側の重複・対応漏れは0件。CHは旧抽出器のIDパターン対象外だったが行原文には存在しており、今回の追加抽出ではない。
モデルは629要素、出典486件。Excelモジュール38件にIDなし行の `gouda_section_executor` を `M-039` として加えた39件。図は101 vertex（枠・注記含む）、2構造要素、84接続を全て保持。図の要素数をモジュール数やExcel IF46件と同一視しない。

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

モデルの設計状態（図・出典整理用要素も含む件数）: {"未設計": 364, "案": 265}。承認済み0件。

## 矛盾・変更対応

C-001〜C-013は上位要求が明示する変更/具体化の対応。旧案の行全体を破棄・承認せず、scopeに書いた範囲だけを扱う。C-014〜C-016は未解消。

### C-001 ソフトモードの集合

状態: `resolved_by_intent`。

旧map_editをruntime modeとして採用しない。一時停止を4モードの一つとして管理。内部状態との対応は未設計。

旧側の影響ID: `LEG-05-0003`, `LEG-05-0005`, `M-001`, `M-002`, `M-005`, `M-010`, `S-05`, `D-06`, `D-07`, `ST-01`, `ST-20`, `Q-10`

原位置: Excel 使用モード定義!A3:G3; Excel 使用モード定義!A5:G5; Excel モジュール定義!A2:AD2; Excel モジュール定義!A3:AD3; Excel モジュール定義!A6:AD6; Excel モジュール定義!A11:AD11; Excel 基本仕様!A6:D6; Excel データ契約!A7:E7; Excel データ契約!A8:E8; Excel 状態遷移!A2:E2; Excel 状態遷移!A21:E21; Excel 未決事項!A11:D11

現在の採用要求: `RQ-I025`, `RQ-I064`, `RQ-I065`, `RQ-I066`。intent.md:36–36; intent.md:92–92; intent.md:93–93; intent.md:94–94

### C-002 区間属性の帰属

状態: `resolved_by_intent`。

前点から当該点へのincoming属性の旧案を、waypoint i→i+1の区間属性へ置換。初回進入の詳細は未設計。

旧側の影響ID: `S-08`, `D-03`, `M-010`, `M-037`

原位置: Excel 基本仕様!A9:D9; Excel データ契約!A4:E4; Excel モジュール定義!A11:AD11; Excel モジュール定義!A39:AD39

現在の採用要求: `RQ-I010`。intent.md:13–13

### C-003 境界速度の保証

状態: `resolved_by_intent`。

進入区間の上限を境界で適用。境界時の実速度上限以下の保証は要求しない。cmd_vel後段の独自速度制限を追加しない。旧制御器の飽和・変換特性など既存保護全体を削除する意味ではない。

旧側の影響ID: `S-13`, `D-16`, `IF-022`, `T-12`, `M-012`

原位置: Excel 基本仕様!A14:D14; Excel データ契約!A17:E17; Excel インターフェース定義!A23:P23; Excel 使用・開発検証!A13:E13; Excel モジュール定義!A14:AD14

現在の採用要求: `RQ-I010`, `RQ-I020`, `RQ-I062`。intent.md:13–13; intent.md:26–26; intent.md:90–90

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

現在の採用要求: `RQ-I008`, `RQ-I009`, `RQ-I010`。intent.md:11–11; intent.md:12–12; intent.md:13–13

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

状態: `open`。

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

## 残っている問題

計25件。技術事項12件、人の判断7件、資料不足6件。未解消衝突3件は資料不足の問題に紐付き、二重加算しない。元Qは部分的に置換されたものも閉じずに残余課題を保持。

| 問題ID | 分類 | 状態 | 内容 |
|---|---|---|---|
| Q-01 | technical | open | ROS 2・Nav2の採用版 |
| Q-02 | technical | open | 自己位置推定の方式・成立条件 |
| Q-03 | source_missing | open | 既存車両通信と制御校正 |
| Q-04 | human | open | XT-32の取付と可視範囲 |
| Q-05 | human | open | 数値パラメータと時間契約 |
| Q-06 | human | open | 車体・経路・通過の幾何条件 |
| Q-07 | human | open | 指定線への追従と迂回方式 |
| Q-08 | technical | partially_superseded | P介入で通った点の扱い |
| Q-09 | source_missing | partially_superseded | Bluetooth切断時のP状態 |
| Q-10 | human | partially_superseded | mode・再起動・HMI断の運用 |
| Q-11 | technical | open | 補助構成と独自IFの採用 |
| Q-12 | human | open | waypoint半径5 mの用途 |
| Q-13 | technical | deferred | 後工程の保留 |
| H-001 | human | open | SpeedLimit発行手段の承認 |
| G-ARCH | technical | open | Node・process・状態所有・IF契約の具体化 |
| G-PARAM | technical | open | パラメータ群の分解と型・単位 |
| G-RECOVERY | technical | open | 復旧・故障応答・内部状態の設計 |
| G-TEST | technical | open | 旧試験の現要求への対応と新要求の試験 |
| G-LOG | technical | open | ログ・rosbagの責務と記録状態 |
| G-GRAPH | technical | open | 図の要素とモデルIFの対応 |
| G-ENDPOINT | technical | open | IFの総称・表記揺れ・所有者 |
| U-DRAW-001 | source_missing | open | 接続先IDなしの線 |
| U-DRAW-002 | source_missing | open | 非常停止検知線と取得不能記載 |
| U-DRAW-003 | source_missing | open | heartbeat必須性と衝突停止線 |
| U-HISTORY | source_missing | open | 変更記録と現在図の時点差 |

### 人が判断する7件

この移行の完了に回答は不要。決定済み要求の再承認は求めない。以下は影響する次段階の設計/実車値だけを対象とする。推奨は未採用の判断材料。

#### Q-04 XT-32の取付と可視範囲

検出対象・取付条件・走行面をどの実車条件で評価するか。

- 実車の対象と条件を指定する：指定された条件をそのまま評価計画へ反映
- 後工程まで未確定とする：実車での検出範囲の合否判定を保留

推奨: 実車の対象と条件を指定する

影響ID: `IF-043`, `IF-044`

出典: Excel 未決事項!A5:D5

次の作業: 選択肢と影響IDを確認し、運用方針・実車値を人が決定する。

#### Q-05 数値パラメータと時間契約

実車の周期・watchdog・timeout等の値、復旧試行回数の上限、試験条件をどう決定するか。

- 実測資料と試験条件で決める：既存値の根拠を確認し、人が採用値を決定
- 実車値の確定を保留する：型・設定経路の下位設計は進め、値依存の実車確認は未判定

推奨: 実測資料と試験条件で決める

影響ID: `IF-001`, `IF-002`, `IF-003`, `IF-004`, `IF-005`, `IF-006`, `IF-007`, `IF-008`, `IF-009`, `IF-010`, `IF-017`, `IF-019`, `IF-020`, `IF-021`, `IF-023`, `IF-024`, `IF-025`, `IF-026`, `IF-027`, `IF-033`, `IF-034`, `IF-035`, `IF-036`, `IF-037`, `IF-038`, `IF-040`, `IF-042`, `IF-043`, `IF-044`, `IF-045`, `IF-046`, `D-21`, `ST-16`, `T-02`, `RQ-I013`

出典: Excel 未決事項!A6:D6; intent.md:16–16

次の作業: 選択肢と影響IDを確認し、運用方針・実車値を人が決定する。

#### Q-06 車体・経路・通過の幾何条件

車体形状・上限速度等の実車値と、走行対象の未知領域方針をどう指定するか。

- 実車値と運用条件を指定する：Nav2設定に反映。独自通過判定は作らない
- 対象環境・値の確定を保留する：Nav2設定値と実車合否は未判定

推奨: 実車値と運用条件を指定する

影響ID: `S-14`, `D-04`

出典: Excel 未決事項!A7:D7

次の作業: 選択肢と影響IDを確認し、運用方針・実車値を人が決定する。

#### Q-07 指定線への追従と迂回方式

旧資料の指定線方式を今回も必要とし、どの範囲の迂回を認めるか。

- Nav2での実現案と運用差を次段階で比較する：人が追従/迂回の方針を判断するまで旧案は非採用候補
- 旧二方式の運用要求を維持すると明示する：許容範囲・追従優先度を人が追加指定する必要がある

推奨: Nav2での実現案と運用差を次段階で比較する

影響ID: `M-011`, `OWN-M-011`, `PAR-M-011`, `FM-M-011`, `EX-M-011`, `IF-021`, `S-10`, `ST-19`

出典: Excel 未決事項!A8:D8

次の作業: 選択肢と影響IDを確認し、運用方針・実車値を人が決定する。

#### Q-10 mode・再起動・HMI断の運用

最新intentで決まったmode/復帰/最終点以外に、monitor断時の走行継続方針をどうするか。

- 旧案の走行継続を採用する：表示断自体は停止契機にせず再接続時に状態取得
- monitor断を一時停止契機とする：基本契約の追加・運用変更として人の明示決定が必要

推奨: 旧案の走行継続を採用する

影響ID: `S-05`, `D-22`, `ST-18`, `ST-20`, `T-23`

出典: Excel 未決事項!A11:D11

次の作業: 選択肢と影響IDを確認し、運用方針・実車値を人が決定する。

#### Q-12 waypoint半径5 mの用途

旧5 mはNav2設定に残す要求か、迂回領域等の別要求か。

- 5 mの用途を保留してNav2設定案で再確認する：一般的な既定値で補わず、独自通過判定も追加しない
- 用途を人が明示する：Nav2で表せる設定/運用要求として設計可能か次段階で確認

推奨: 5 mの用途を保留してNav2設定案で再確認する

影響ID: `M-011`, `OWN-M-011`, `PAR-M-011`, `FM-M-011`, `EX-M-011`, `IF-021`, `S-10`, `S-11`, `S-12`, `D-02`, `D-05`, `D-20`, `ST-19`, `T-05`, `T-11`

出典: Excel 未決事項!A13:D13

次の作業: 選択肢と影響IDを確認し、運用方針・実車値を人が決定する。

#### H-001 SpeedLimit発行手段の承認

採用Nav2版に対応する発行手段をどれにするか。

- Speed Filter：この経路を単一発行元にする案。採用版・区間対応・設定負担の調査が必要
- Route Server：この経路を単一発行元にする案。採用版・区間対応・設定負担の調査が必要
- Gouda側発行器：Goudaが標準SpeedLimitを単一発行する案。責務と実装負担の比較が必要

推奨: 採用版で3案を比較してから承認する。現段階で方式を選ぶ根拠は不足しており、推奨方式自体は未定。

影響ID: `RQ-I020`, `RQ-I021`, `IF-022`, `D-16`, `M-011`

出典: intent.md:26–26; intent.md:27–27; Excel インターフェース定義!A23:P23; Excel データ契約!A17:E17; Excel モジュール定義!A13:AD13

次の作業: AIが次段階で版適合を調べて比較し、人が承認する。

### 資料不足と技術作業

- **Q-01**（technical）ROS 2・Nav2の採用版 次の作業: 次の下位設計で、上位要求に従い技術案・標準IF・構成を具体化する。
- **Q-02**（technical）自己位置推定の方式・成立条件 次の作業: 次の下位設計で、上位要求に従い技術案・標準IF・構成を具体化する。
- **Q-03**（source_missing）既存車両通信と制御校正 次の作業: 原資料・既存通信仕様・実車記録を確認する。移行時点では推定しない。
- **Q-08**（technical）P介入で通った点の扱い 次の作業: 次の下位設計で、上位要求に従い技術案・標準IF・構成を具体化する。
- **Q-09**（source_missing）Bluetooth切断時のP状態 次の作業: 原資料・既存通信仕様・実車記録を確認する。移行時点では推定しない。
- **Q-11**（technical）補助構成と独自IFの採用 次の作業: 次の下位設計で、上位要求に従い技術案・標準IF・構成を具体化する。
- **Q-13**（technical）後工程の保留 次の作業: 次の下位設計で、上位要求に従い技術案・標準IF・構成を具体化する。
- **G-ARCH**（technical）旧候補を現在要求へ適合させる下位設計が未実施。 次の作業: 責務、標準IF、所有者、配置、QoS、時刻を次段階で設計。資料の確定明示なしは人の承認待ちにしない。
- **G-PARAM**（technical）パラメータ群は原文参照で移行し、個別型・キー・単位・設定所有者は未設計。 次の作業: 技術的な分解はAIが行う。実車採用値・試験条件はQ-03〜Q-06。
- **G-RECOVERY**（technical）最新の復旧順序と故障別復帰先に対応する下位設計は未実施。 次の作業: 必要状態だけの復元・旧goal処理を次段階で具体化。人の追加承認や新モードを追加しない。
- **G-TEST**（technical）旧試験はすべて未実行で、旧期待値を含む。 次の作業: 置換対応を参照して次段階で試験を設計。今回の検査器試験と区別する。
- **G-LOG**（technical）独立した記録操作・自動開始条件・欠落追跡の具体IFと状態所有者が不足。 次の作業: 最新要求の範囲内で次段階に設計。復帰時の無断自動Recordを追加しない。
- **G-GRAPH**（technical）図中の枠・注記・内部構成・接続を、承認済みNode/IFと同一視できない。 次の作業: 原IDを保ちながら次段階で責務境界を整理。名称一致以外の自動統合をしない。
- **G-ENDPOINT**（technical）logger、Navigation内境界、PC構成node、safety_gouda_safety_supervisor等の具体参照が未解決。 次の作業: 原文を保持し次の下位設計で対応付け。誤記と推測して黙って修正しない。
- **U-DRAW-001**（source_missing）targetPointはあるがtarget IDがない。接続先未特定。 次の作業: 図の意図を示す資料で確認。source/controllerやcmd_velラベルから接続先を推測しない。
- **U-DRAW-002**（source_missing）図のESP32押下検知線とExcelの取得不能記載が衝突する。 次の作業: 現物回路・既存実装資料で確認するまで検知機能を採用済みにしない。
- **U-DRAW-003**（source_missing）図のheartbeat_and_status/collision_stop_requestとExcelの任意/未提供記載の対応が未確認。 次の作業: 原資料で現状/構想を確認。図の線を必須監視や実装済み機能へ昇格しない。
- **U-HISTORY**（source_missing）CH-02はlocal_odometry/mission_managerが図に未記載とするが、現在図には両ラベルが存在する。 次の作業: CH-02を旧時点の記録として保持。図の追加時期・変更履歴は未確認。

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
- `RQ-I067`（intent.md:95）：・最終waypoint到達後の一時停止で再開ボタンを押した場合も、最終waypointを目指して走る。
- `RQ-I068`（intent.md:96）：・esp32は、現在採用している指令源からの入力が途絶えたら中立を出す。
- `RQ-I069`（intent.md:97）：・故障の種類と復帰先のモードに応じて、必要な状態だけを復元する。旧goalと新goalが競合しない方法で自動復帰し、各処理の成否を記録する。自律走行指令の再許可は、自律走行へ復帰する場合に限る。

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
| M-028 | M-028 | module | Excel モジュール定義!A30:AD30 | 対象 | unresolved |
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
| IF-032 | IF-032 | interface | Excel インターフェース定義!A33:P33 | 対象 | unresolved |
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
