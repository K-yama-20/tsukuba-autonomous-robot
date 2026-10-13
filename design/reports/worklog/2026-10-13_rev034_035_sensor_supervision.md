# 作業記録 2026-10-13 第22便: センサーの受信表示と地図作成開始時の警告、デバイス再接続時のドライバ作り直し（REV-034・REV-035）

## 読んだもの

- ローカル HEAD `aa1080b`（REV-033 まで）、`reports/status.md`、`reports/worklog/2026-10-13_rev032_033_glim_start.md`、正本の ND-02・ND-14・ND-15・IFD-21・IFD-22・IFD-28、monitor の実装（monitor_core・monitor_node・web）、`gouda_core/launch/gouda_sensors.launch.py`。
- VM のカーネルログ（USB の切断・再接続）、Mac の電源ログ（pmset -g log。読み取りのみ）、launch ログ。

## 1. 人の問いと指示（原文で台帳へ）

- 問い（DEC-088 の note に原文）: by-id で探す指示との関係、LiDAR が止まる原因がソフト側にあるか、VM だから起きやすいか。
- AI の考察（チャットで回答、DEC-088 の note に要旨）:
  - IMU は by-id の名前で開いていたが、探すのは起動時の 1 回だけで、再接続後に探し直さなかった。カーネルログでは 93 分で IMU の USB が 7 回、USB-LAN が 4 回、切断・再接続していた（人の抜き差しを含む）。
  - LiDAR の停止は Mac がバッテリー駆動でスリープに入った時刻（電源ログ 18:47:48 にスリープ防止の解除）と一致し、21:08:51 の完全な復帰まで VM が止まっていた。ソフトが LiDAR を止めた形跡はない（ドライバは受信のみで待機・回転数を送らない設定。22:17 に同じドライバが自動で受信を再開）。
  - VM 固有の要因（スリープ、USB の受け渡し、NTP 無効で時計が飛ぶ、パケット欠落）を観測。構成の選択肢を提示（専用 PC の Ubuntu を推奨。人の判断待ちで回答なし）。
- DEC-088（指示）: monitor に受信状況と地図作成開始時の警告、デバイス名を見張り再接続時だけそのドライバを作り直す。各種文書に記録。

## 2. 実装と自律判断

- monitor（ND-02）: 点群と IMU を直列化されたまま購読し（6 万点の点群を展開しない）、到着時刻と header.stamp だけで状態・周期・経過・時刻差を表示。地図作成開始ボタンの時点で未受信または途絶なら、応答に警告文を付けて画面のポップアップに出し、DecisionEvent（mapping_start_sensor_warning）で記録。開始は止めない（RQ-I011）。
- gouda_sensor_supervisor（ND-18、新規）: ドライバを子プロセスとして起動。IMU は by-id の名前の先の USB 列挙（tty 名＋バス・デバイス番号）、XT-32 は PC 側アドレスを持つ I/F（名前＋ifindex）を同一性とし、同一性が変わったときだけそのドライバを作り直す。同一性が同じなら、ドライバが自分で終了しても再起動しない。見張りは udevadm monitor と ip monitor のイベントで、周期の値を持たない。前回と同じ IMU の列挙を開き直すときは警告を記録。
- ドライバを launch の Node から子プロセスに変えた理由: launch は 1 つのノードだけを条件付きで作り直せないため。
- 新しい値（STALE しきい値 PRM-57・58、停止待ち PRM-59）は未確定で宣言し、仮値は根拠付き。未確定の間、monitor は未受信だけを警告し、supervisor は上限なしで停止を待つ（DEC-089 で承認を問う）。
- 誤りと修正（原因の分類）:
  - 変更セットで入れ子のキーに append を使い、スキーマ違反になった（実装＝変更セットの書き方。既知の落とし穴）。正本を戻して set_nested で全リストを与えて再適用。
  - device_watch.py のコメント中の「1.0」が DR-15 の走査で承認値と一致（実装＝表記）。コメントを変更。

## 3. 実行した検査・試験

| 検査・試験 | コマンド・対象 | 結果 |
|---|---|---|
| 全検査 | `design/.venv/bin/python design/tools/run_checks.py`（REV-035 適用後） | 終了コード 0。違反 0・未判定 4 |
| gouda_core 単体（Mac） | `python3 -m unittest discover -s test` | 112 件 OK（1 件は rclpy が要るため Mac では skip） |
| gouda_core 単体（VM） | 同（9e420b3） | OK（skip なし） |
| VM 主セッション（実センサー、仮値ファイル） | `GOUDA_SENSORS=1 GOUDA_TRIAL_PARAMS=1 bash gouda.sh start` | supervisor が XT-32 の I/F（enx6c6e0754b24a #6）と IMU の列挙（ttyACM0 usb 2-27）を名前から求めて両ドライバを起動。monitor が両方 RECEIVED と表示 |
| VM 別スタック（ROS_DOMAIN_ID=77、センサーなし） | 地図作成開始・終了を API で | 警告文が応答に付き、DecisionEvent を記録し、地図作成は開始された |
| 点群の配送 | ドライバの frame 数と ros2 topic hz | ドライバ 10 秒で 100 フレーム、購読側 1.7〜2.2 Hz（monitor 約 3 Hz）。IMU は約 100 Hz |

記録: `research/vehicle_pc/2026-10-13_sensor_supervision_vm_test.txt`（FILE-VEHICLE-PC-SENSOR-SUPERVISION）。

未実行: 実機の抜き差しによる作り直し（IMU・USB-LAN。人の協力が要る）、ドライバが自分で終了した場合の実機での確認。主セッションは IMU を再起動させないため止めていない（画面の題名の修正は次の起動から反映）。

## 4. 承認待ち

- DEC-089【承認】PRM-57 点群 1.0 s、PRM-58 IMU 1.0 s、PRM-59 5.0 s（ソフトウェア設定値）。
- 前便から: DEC-084（PTC ポート）、DEC-085（IMU 周期）。構成の選択（専用 PC）は人の判断。

## 5. 残るリスク

- 点群の配送の欠落（G-DDS）。GLIM が受け取る周期は未測定。GLIM にも及ぶなら地図の品質に直結する。
- gouda.sh の停止・起動は IMU の再起動にあたる（同じ列挙を開き直すと応答しない場合がある）。supervisor は警告を記録し、抜き差しで作り直す。
- 時計の飛びの検知は採用されていない（DEC-088 の対象外）。

## 6. 次に進められる作業と止まっている作業

- 進められる: GLIM が受け取る点群の周期の測定（G-DDS）。IMU と USB-LAN の抜き差しによる作り直しの実機確認（人の協力）。
- 止まっている: なし。
