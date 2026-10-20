# 作業記録 2026-10-21 第76便: 書き込みを待たない方式、rosbag の非同期の停止と進捗、gouda.sh stop の進捗（REV-108・109、DEC-174）

## 読んだもの

- コミット `33416021655e587d0ae5f2c949d9bf81698ef44e`（作業ツリーは未 commit の変更あり）。`vehicle_bridge_node.py`、`recorder_node.py`・`recorder_core.py`、`monitor_node.py`・`monitor_core.py`・`monitor_server.py`、`web/`、`gouda.sh`、VM の pyserial 3.5 の `Serial.write`・`open`。

## 人の許可（原文は DEC-174）

書き込みは待たない方式、rosbag の停止は推奨どおり（ただし保存開始と同時にポップアップ）、gouda.sh stop は GLIM の保存状況を 1 s おきに表示。

## 変更

- `gouda_core/gouda_core/vehicle_bridge_node.py`: write_timeout 0.2 を削除。SerialTransport.write は `os.write(fd)`（pyserial が O_NONBLOCK で開く）。入りきらない分は捨て、固定の理由（serial write incomplete …）で記録。pyserial の write_timeout=0 は EAGAIN で忙しく回り続ける（3.5 のソースで確認）ため使わない。
- `gouda_core/gouda_core/recorder_core.py`: 保存中の状態（rosbag_finalizing、last_finalize）、stop_rosbag はすぐ返す、rosbag_finalized（終了コード 0 で完了、それ以外は失敗を記録）、保存中は新しい rosbag を拒否、status に rosbag_saving・rosbag_saving_output・rosbag_saving_started_at・rosbag_last_save。
- `gouda_core/gouda_core/recorder_node.py`: _bag_stop は SIGINT だけで返す（30 s・SIGTERM を廃止）、見張りのスレッドが保存の終わりを core に渡す、destroy_node は保存を上限なしで待つ。
- `gouda_core/gouda_core/monitor_core.py`（folder_bytes）、`monitor_node.py`（/api/rosbag_saving。パスは record/status から取り、クライアントからは受けない）、`web/index.html`・`style.css`・`app.js`（保存の始まりと同時にポップアップ、往復するバー、経過時間・大きさ・増え方を既存の 1 s の表示更新で取得、終わると完了・失敗と確認ボタン）。
- `gouda.sh`: stop は SIGINT の後、上限なしに待つ。PRM-77（1 s）ごとに GLIM（dump_path）と ros2 bag record（-o）の保存の大きさ・増え方を表示（$data_root の下のものだけ。照合したプロセスのコマンド行だけを読む）。usage の説明を更新。
- 試験: `gouda_core/test/test_recorder_core.py` に RosbagSaveTests 3 件、新規 `gouda_core/test/test_serial_transport.py` 2 件（pty で詰まった相手を作る。pyserial・rclpy のある VM で実行、Mac では skip）。
- REV-108（DEC-174、PRM-77 を追加、ND-01・02・04・12 の解釈）、REV-109（PRM-77 の source_refs が空でスキーマ違反だったのを intent.md:103 に）。番号は reserve_ids.py で予約。

## 原因の分類

- REV-108 の後の DR-01（スキーマ）違反: 設計（正本への追加の誤り。source_refs が空）。REV-109 で正本を直し、検査をやり直した。

## 検査・試験

- Mac `cd gouda_core && python3 -m pytest -q test/test_recorder_core.py test/test_monitor_core.py test/test_monitor_server.py test/test_logging_call_sites.py test/test_serial_transport.py`: 41 passed、2 skipped。
- VM（一時の写し ~/gouda_unit_tree。動いている Gouda と ~/gouda_ws には触れていない）`python3 -m pytest -q test`: 12 failed・195 passed。不合格 12 件は第71便の既知（期待値が古い 2、対角 1 mV、test_motion_core の trial の前提 9）。新しい試験はすべて合格。最初の写しでは macOS の `._*` ファイルが混ざり test_logging_call_sites が失敗した（写し方の問題。除いて再実行）。
- VM の実機の確認（ROS_DOMAIN_ID=77、一時のフォルダ）: 改めた recorder_node と本物の ros2 bag record。stop のサービスは 0.71 s で返り、保存は 0.16 s で終わり rosbag_last_save に記録。記録中に node へ SIGINT を送ると保存を待って 1 s で終了し、bag_02 に metadata.yaml があり result は stopped。node の終了時に rclpy の ExternalShutdownException の traceback が出る（main が KeyboardInterrupt だけを受けるため。今回の変更の前からの振る舞いと推測、未確認）。
- monitor のポップアップ: 合成の値の DEMO サーバ（scratchpad、DEMO-NOT-REAL）を内蔵ブラウザで表示。保存中（バー・経過・大きさ・増え方）と完了（所要・終了コード・確認ボタン）を目で確かめた。
- gouda.sh の表示: 関数だけを VM で読み込み、GLIM と ros2 bag record の代役のプロセスで 1 s ごとの行を確かめた。動いている Gouda の stop は実行していない（未実行）。
- `design/.venv/bin/python design/tools/run_checks.py`: 終了コード 1。設計検査 合格 12・違反 0・未判定 5（DR-15 は 10 件に減った: write_timeout 0.2 の削除）。移行の照合の違反は以前から。

## 残るリスク

- 書き込みで捨てた指令の直後に来る指令も、途中で切れた指令の後ろにつながるため firmware の CRC で捨てられる（1 回の詰まりで 2 つ失う。推測）。車体側は PRM-13 で中立。
- gouda.sh stop は終わらなければ人が PC を再起動する前提（人の決定）。
- VM の時計が Mac より約 2 日遅れている（tar の警告）。

## 次に進められる作業・止まっている作業

- 許可待ち: vehicle_bridge の事前地図作成での configure、試験の修正（既知の 12 件）、不感帯の補償。
- 承認待ち: DEC-168、DEC-172、intent.md 第12版。
