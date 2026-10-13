# 作業記録 2026-10-09 第14便: 記録の自動開始 IF、IFD-28 の transient_local、UI 待ち時間の parameter 化、検査規則 DR-16・DR-17（REV-020）

## 読んだもの

- ローカル HEAD `afe61ce` → 本便で `f660f50` を push。人の指示（第13便の判断事項 1〜3 への回答と、工程5-3 への進行許可）。正本の IFD-08・09・28、ND-02・03・04、TR-03・04・05・10・11・12・13、PRM-16、TS-23。`tools/check_design.py`、`rules/README.md`。

## 1. 人の回答（原文で台帳へ）

| 台帳 | 内容 |
|---|---|
| DEC-071（approval） | 記録用 IF の名前（record/log/start_autodrive・start_pre_mapping）と設計条件（発行条件→検査規則、重複時、開始元の保持、走行への影響、失敗時ポップアップ、停止側の確認、対象範囲） |
| DEC-072（approval） | IFD-28 の transient_local を条件付きで承認（全 publisher を揃える、履歴欄と現在状態欄の分離、契機にしない、永続履歴ではない、保持件数は AI が宣言、QoS 互換性の検査規則） |
| DEC-073（approval） | UI の周期・待ち時間を ROS parameter として宣言（既定値 2 s／1 s／5 s はソフトウェア既定値、実測対象にしない、待ちの種類の区別、一時停止は別枠、timeout 時は失敗表示、転用しない、宣言先は中継ノード） |
| DEC-074（approval） | 細部の逐一承認は不要。新 IF と既存契約の差分を示したうえで更新し、工程5-3 へ進むことを許可 |

## 2. 新 IF と既存契約との差分（DEC-074 の要求）

| 項目 | 既存契約（REV-019 まで） | 変更後（REV-020） | 影響 ID |
|---|---|---|---|
| ログの自動開始 | IFD-08 record/log/start を ND-02 と ND-03 が呼ぶ（契機の区別なし。recorder は全要求を人の開始として扱っていた） | 入口を分離: IFD-08（人の Record）、IFD-44 record/log/start_autodrive（TR-05）、IFD-45 record/log/start_pre_mapping（TR-03）。処理と状態管理は共通（recorder_core.start_log）。契機を保持しログに残す | IFD-08、IFD-44、IFD-45、ND-03、ND-04、TR-03、TR-05 |
| 自動開始分だけの停止 | 存在せず（IFD-09 は開始元を問わず停止） | IFD-46 record/log/stop_auto を追加（手動開始には何もせず「手動開始のため停止しない」）。IFD-09 は人の Stop Record 専用 | IFD-09、IFD-46、TR-04、TR-11、TR-12 |
| 重複時 | 記録中なら「already active」（仕様未明記） | 何もせず「記録中」と応答。手動開始を自動開始へ書き換えない | ND-04、TS-23、TS-26 |
| 発行条件 | 文言のみ（RQ-I015） | 検査規則 DR-16: IFD-44／45／46 を参照できるのは人の開始／終了操作の遷移のみ。fault_recovery・resume・pc_restart・boot の遷移と ND-02 からの参照は違反 | DR-16、TR-02・10・13〜16 |
| 走行への影響 | 未明記 | ND-03 は非同期で呼び応答を待ち合わせない。失敗・無応答は DecisionEvent（record_auto_start_failed）。走行開始は止めない | ND-03、TR-03、TR-05 |
| 失敗の表示 | なし | monitor がポップアップで警告（新しいイベントのみ。保持メッセージは契機にしない） | ND-02 |
| IFD-28 QoS | reliable／volatile／50 | reliable／transient_local／50（publisher ごと最新 50 件）。publisher に ND-02（settings）を追加。全 publisher を transient_local に（DR-17） | IFD-28、ND-02・03・11・12 |
| monitor の表示 | 判断の一覧 | 「履歴」欄（時刻付き）と「現在の状態」欄（mode/state）を分離。保持メッセージは判断・記録の契機にしない。履歴の正本は保存ログ | ND-02 |
| UI の周期・待ち時間 | コード内の固定値（2 s／2 s／1 s／5 s） | PRM-27〜32（gouda_monitor の ROS parameter。承認値＝ソフトウェア既定値。一時停止は別枠）。生成ファイルから読み、未設定なら起動を拒否。timeout は失敗表示、自動再試行なし。起動時と /config 保存時に settings を DecisionEvent で記録 | PRM-27〜32、ND-02、PRM-16 |
| rosbag | 人のみ、自動開始しない | 変更なし | — |

## 3. 実装

- `recorder_core.py`: 重複開始は「記録中」で何もしない、`stop_auto()`（手動開始は no-op で ok 応答）。`recorder_node.py`: サービス `record/log/start_autodrive`・`start_pre_mapping`・`stop_auto` を追加（処理は共通）、log/decision の購読を transient_local に。
- `mode_manager_node.py`: log/decision の publisher を transient_local（50）に。`request_auto_record(kind, transition_id)`（非同期、失敗・無応答を DecisionEvent に記録）。TR-03／TR-05／TR-04／TR-11／TR-12 の実装時に呼ぶ。復帰・再開・再起動では呼ばない。
- `monitor_node.py`: PRM-27〜32 を宣言し生成ファイルから読む（未設定なら起動拒否）、一時停止ボタンは別枠の待ち、timeout は失敗表示・自動再試行なし、settings を DecisionEvent（transient_local）で記録、log/decision の購読を transient_local に。`monitor_server.py`: keep-alive の既定値を削除（node から渡す）。`web/`: 「判断の履歴」欄、ポップアップ、UI パラメータ表。
- 検査器: DR-16（自動開始 IF の呼び元・参照遷移）、DR-17（transient_local の保持件数宣言と、走査対象コードの publisher QoS）。`rules/README.md`・試験 5 件追加。DR-15 の走査からライセンス識別子（Apache-2.0）を除外（false positive の修正）。
- 修正の分類（1.6）: 設計（IF の追加・QoS・parameter の宣言は人の指示による設計変更。REV-020）。実装（DR-17 が初回に mode_manager の volatile publisher を違反として検出 → transient_local に修正。monitor_server の既定値 2.0 を削除）。検査器（Apache-2.0 の誤検出）。試験（recorder の stop_auto の応答を「no-op は ok」に変更。停止しないという結果は不変）。

## 4. 検査（`design/.venv/bin/python design/tools/run_checks.py`、終了コード 0。REV-020 適用後 model.yaml SHA `bc4721f6b87fee55…`）

入力の完全性・設定の生成・intent 同一性 PASS。移行忠実性 違反 0。設計整合性 17 ルール 違反 0・未判定 4（DR-04 5、DR-05 2、DR-10 1、DR-11 40）。DR-16 合格、DR-17 合格（走査対象 gouda_core の log/decision publisher 3 か所が transient_local）。検査器の試験 68 件 OK。gouda_core 単体試験 41 件 OK（ローカル）。

## 5. Ubuntu 上の試験

**未実行**。コミット `f660f50` を push した直後から VM（10.211.55.4）が ping 不達・SSH タイムアウトになった（VM の休止と推測）。VM 復帰後に次を実行する: colcon build gouda_core、単体試験、gouda.sh start、/api/state の settings と履歴（transient_local により起動後の購読でも TR-01・settings が見えること）、`record/log/start_pre_mapping`→record/status の auto_started_by、重複要求「記録中」、`stop_auto`、手動開始後の `stop_auto` no-op、events.jsonl の trigger、/config 保存→settings イベント、再起動後の履歴、停止。

## 6. 残るリスク・判断事項

1. VM 不達のため ROS 上の確認が未実施（コードは push 済み）。
2. ポップアップはブラウザ側の表示で、API 試験では「イベントが出る」ことまでしか確認できない。実機ブラウザでの確認は未実施。
3. DR-17 の実装走査は `create_publisher(型, 'topic', QOS名)` の形だけを解決する（それ以外は未判定として報告）。
4. 本便の REV-020・記録は `f660f50` にコードと共にコミット済み。本 worklog と status は未コミット。

## 7. 次の作業

- VM 復帰後に §5 の試験を実行し記録を `research/vehicle_pc/` に保存。
- 工程5-3（地図作成と変換）に着手（DEC-074 の許可）: TR-03／TR-04 の動作（GLIM 起動・停止、TF 排他 RQ-I004、IFD-45／IFD-46 の呼出し）、IFD-35〜37、SO-04、変換 Action。
