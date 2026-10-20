# 作業記録 2026-10-17 第30便: recorder の rosbag の再開と GLIM の異常終了の検出の修正、スリープの抑止の検討、intent 第11版（REV-058・REV-059）

## 読んだもの

- コミット `6b86d92` と未コミットの第27〜29便の記録（REV-051〜057）、status.md、`proposals/sleep_inhibit_plan.md`、`proposals/localization_selection.md`。
- コード: `gouda_core/gouda_core/recorder_core.py`・`recorder_node.py`・`glim_runner.py`・`mode_manager_node.py`・`monitor_node.py`、`gouda_core/web/app.js`、試験 `test_recorder_core.py`・`test_mapping_core.py`。
- 正本: ND-02・ND-03・ND-04、SO-02、IFD-10〜12、TR-14、TS-23・TS-27、G-DUP-START、C-004・C-010・C-012。

## 1. 人の指示（DEC-117 に原文）

- Septentrio mosaic-go G5 P6（デュアルアンテナ、ネットワーク RTK）を搭載した。
- 自己位置推定の方式の選定（DEC-115）は保留。
- recorder の rosbag の再開の不具合（最優先）と、GLIM の異常終了の検出と表示を修正したい。
- 蓋を閉じたときのスリープの抑止（DEC-104）を検討せよ。
- 最新版を実機 x86 に反映済みで、二重起動の防止は正常に動いている。

「修正したい」を、修正 2 件の個別の許可（DEC-106）として扱った。

## 2. recorder の rosbag の再開（G-REC-ROSBAG-RESTART。分類: 実装）

- 原因（VM で再現）: 同じセッションで再開すると `ros2 bag record -o rosbag/bag` が「Output folder 'rosbag/bag' already exists.」で終了コード 1 になる。recorder は子プロセスの出力を捨て、終了も見ていなかった。ND-04 の「記録失敗を表示する」に反していた。
- 修正:
  - `recorder_core.py`:
    - 開始ごとに `rosbag/bag_NN`（01, 02, ...。既にあるものは飛ばす）。
    - session.json に `rosbag_outputs`（出力先、開始・停止の時刻、結果）を残す。
    - `rosbag_exited()`: 停止の要求なしの終了を失敗として記録する。記録中を解除し、session.json の failures と、ログが動いていれば `record_failure` を残す。
    - 状態に `rosbag_output`・`last_failure` を加えた。
  - `recorder_node.py`:
    - `ros2 bag record` の出力を `bag_NN.log` に残す。
    - 子プロセスの終了を待ち合わせる見張りのスレッドを付け、止める操作による終了と区別する。
    - サービスと見張りを 1 つの排他で直列にした。
    - 新しい時間の設定値は作っていない。
  - `app.js`: record/status の failures が増えたらポップアップ（最後の失敗の内容）。表に rosbag_output・last_failure を加えた。
- 既存の試験 1 件の期待値を変えた（出力先 `S1/rosbag` → `S1/rosbag/bag_01`）。修正で契約の中身が変わったためで、試験を通すための変更ではない。

## 3. GLIM の異常終了の検出と表示（G-GLIM-EXIT。分類: 実装）

- 原因: mode_manager は GLIM の子プロセスの終了を見ておらず、175310 では約 2 分間気づけなかった。設計の TR-14（事前地図作成中の個別異常からの自動復帰）は未実装だった。
- 修正（TR-14 のうち検出と表示だけ）:
  - `glim_runner.py`: `GlimRun` に `log_file`・`exited_unexpectedly_at` を加えた。`unexpected_exit_report()`（終了コード、開始からの時間、glim.log の末尾 3 行。停止の要求の後なら報告しない）と `log_tail()` を加えた。
  - `mode_manager_node.py`:
    - 地図作成の開始（TR-03）で GLIM の終了を待ち合わせる見張りのスレッドを付けた。
    - 停止の要求なしの終了は DecisionEvent `glim_exited`（TR-14）で記録する。モードは保ち、GLIM は再起動しない。
    - mapping_stopped に `glim_exited_unexpectedly_at` を残す。
  - `app.js`: `glim_exited` を新しく受け取ったらポップアップ。
    - 既存の記録の自動開始・停止の失敗のポップアップは、同じ仕組みにまとめた。
    - 文言は変えていない（一度変えかけて戻した）。

## 4. 試験

- Mac の単体試験（`cd gouda_core && python3 -m unittest discover -s test -p "test_*.py"`、作業ツリー）: 134 件 OK、1 件 skip。追加は recorder 4 件、地図作成 1 件と既存 1 件の拡張。
- VM の試験（別のワークスペース `~/gouda_fix_ws` に作業ツリーを写して build、試験スタック、ROS_DOMAIN_ID 77、センサーのドライバなし。FILE-RECORDER-GLIM-FIX-VM-TEST、スクリプト FILE-RECORDER-GLIM-FIX-VM-TEST-SCRIPT）:
  - R1: rosbag の開始・停止・開始・停止 → `bag_01`・`bag_02` の両方に mcap と metadata、失敗 0。
  - R2: 記録中の `ros2 bag record` を SIGKILL → 記録中が解除され、失敗 1、last_failure に終了コード −9 と出力の末尾。`bag_03` は failed。
  - G1: 地図作成中に glim_rosnode を SIGABRT → 数秒以内に `glim_exited`（TR-14、終了コード −6）、モードは事前地図作成のまま。地図作成終了 → mapping_stopped に先の終了の時刻、source_map_not_registered。
  - G2: 通常の開始・終了 → `glim_exited` は増えない。
- 未実行:
  - monitor のポップアップの見た目（VM の monitor は VM の中からしか開けない。API に出る値は確認した）
  - x86 機での確認（反映は人）
  - GLIM が止まらずに固まる場合の検出（今回の範囲外）
- 全検査 `run_checks.py`（作業ツリー、REV-059 の後）: 終了コード 1。原因は人が編集中の `design/docs/SystemArchitecture.drawio` だけ（移行の検査 3 件、migration_tests 1 件、input_integrity 1 件）。design_check は違反 0、DR-15（値の直書き）は合格、intent_identity は合格。

## 5. スリープの抑止の検討（DEC-104。提案のみ）

`proposals/sleep_inhibit_plan.md` を第2版にした。推奨は前と同じ案 A（gouda.sh が動作中だけ sleep・idle・handle-lid-switch の抑止を取る）。足したことは次のとおり。
- 電池で 15 分以上キーボードに触れずに走ると、GNOME の自動サスペンドが起こりうる（自律走行では普通に起こる）。sleep の block で止まる見込み。x86 機で確かめる。
- 抑止は画面の前のセッションでしか取れない。運用として、Gouda は x86 機の画面の端末から起動する。
- x86 機での確かめ方を書いた: journal の蓋の開閉とリンク断、電源の設定、実装の後の試験 5 件。

## 6. intent.md 第11版（DEC-118。REV-059）

- 機械比較で検出した。人が 16:29 にリポジトリ側の intent.md の 14 行（体験 9）を編集していた。「初期位置と向きを人間がある程度指定し」が「GNSSにより初期位置と向きが取得されて地図にoverlayしてgouda_monitorに表示される。位置の収束や正しさを人間が確認する」に変わった。
- 記録（AI は intent.md を編集していない）:
  - 写し `baselines/intent_history/intent_v11_a7a03a313c6d.md`
  - AR-011、FILE-INTENT-V11
  - RQ-I011 → RQ-I084（RQ-I011 を参照していた 21 項目の参照を置換）、照合 C-027
  - C-004・C-012 の根拠を RQ-I084 に付け替えた（変わらない部分を根拠にしているため）
  - C-010 の根拠を RQ-I084 に付け替え、「人が地図上で初期位置を指定」が第11版と食い違うと注記した
  - 影響を問題 G-INIT-POSE-GNSS（未解決）に一覧した（IFD-34、IFD-02、ND-07、TR-05、H-007・DEC-009、IFD-39 ほか）
- 設計そのものは変えていない（自己位置推定の方式の選定 DEC-115 の再開時に一緒に設計する）。
- 修正の記録（分類: 実装＝変更セットの誤り）:
  - 1 回目は問題の影響先に DEC-009 を書いて適用が止まった（正本は変わっていない）。
  - 2 回目は category に schema にない `design`、3 回目は `human` で、必須の選択肢がなく schema 違反になった。
  - `technical` に直し、model.yaml・schema.json・generated を 6b86d92 に戻して REV-051〜059 を順に適用し直した。

## 7. 自律判断した変更

- rosbag の出力先の名前（`bag_NN`）、子プロセスの出力の置き場（`bag_NN.log`）、ポップアップの文言、GLIM の終了の報告の文言と項目。いずれも ND-04・TR-14 の範囲で、後から戻せる。
- VM の `~/gouda_fix_ws` を試験用に作った（VM の `~/gouda_ws` は変えていない）。

## 8. 承認事項・実測待ち

- 新しい承認事項はない。修正 2 件は DEC-117 で許可。
- 前からのもの: DEC-104（スリープの抑止。計画 第2版）、DEC-115（保留）、DEC-116、ほか。
- 人に依頼: x86 機への反映（ブランチの commit・push の後）、sleep_inhibit_plan.md §5 の 1・2 の確認。

## 9. 残るリスク

- x86 機では未確認。
- rosbag の出力先が `rosbag/bag` から `rosbag/bag_NN` に変わる。古いセッションの解析の手順は読み替えが要る。
- GLIM が終了せずに固まる・処理が止まる場合は検出しない。
- `ros2 bag record` が起動に成功してから書き込みに失敗する場合（ディスクの満杯で終了しない場合など）は検出できない。

## 10. 次に進められる作業と止まっている作業

- 進められる: commit と push（人の指示の後）、x86 機での確認の手順書。
- 止まっている:
  - スリープの抑止の実装（DEC-104）
  - 自己位置推定の方式と初期位置の GNSS の設計（DEC-115 保留、G-INIT-POSE-GNSS）
  - 全検査の終了コード 0（drawio の扱い待ち）
