# センサーの受信表示と、デバイス再接続時のドライバ作り直し（DEC-088、REV-034）

状態: 正本（Markdown）。案（design_status 案）。人の指示 DEC-088 による。モデル: ND-02（gouda_monitor）、ND-14・ND-15（センサードライバ）、ND-18（gouda_sensor_supervisor）、SO-12、IFD-21・IFD-22・IFD-28、PRM-57〜59（確定: DEC-091）、PRM-60（LiDAR 600 rpm）、TS-31・TS-32。

## 1. 背景（2026-10-13 の VM での観測。FILE-VEHICLE-PC-GLIM-START と第21〜22便の作業記録）

- IMU は by-id の名前（PRM-54）で開いているが、名前を探すのは起動時の 1 回だけだった。USB が繋ぎ直されると名前は新しい機器を指すが、ドライバは古い機器を握ったまま読み続けた（「Cannot read data from port」が 16 万回）。
- IMU のドライバを、USB を繋ぎ直さずに再起動すると IMU が応答しない（正常終了の後でも再現）。
- LiDAR の点群が止まっても、monitor には表示されず、地図作成は「データなし」のまま成功扱いで終わった。

## 2. monitor の受信表示と地図作成開始時の警告（ND-02）

- monitor は sensors/xt32/points（IFD-21）と sensors/imu/data（IFD-22）を購読する。中身は解釈せず、到着時刻と header.stamp だけを読む（直列化されたままの受信。6 万点の点群を展開しない）。QoS は IF の定義どおり best_effort・volatile・保持 5。
- 表示（運用タブの LIDAR / LOC 欄の SENSORS 表）: 状態（NOT_RECEIVED／RECEIVED／STALE）、受信周期（直近 50 件の到着から計算）、最後の受信からの経過、header.stamp と受信時刻の差、しきい値。表示のみで停止条件にしない。
- STALE のしきい値は点群 PRM-57、IMU PRM-58（gouda_monitor の ROS parameter。いずれも 1.0 s で確定: DEC-091）。値が無い場合は STALE を判定せず、表に「しきい値未確定」と出す。
- 地図作成開始ボタンが押された時点で、どちらかのセンサーが NOT_RECEIVED（起動後に一度も受信していない）または STALE なら警告する。
  - 警告は画面のポップアップと DecisionEvent（event=mapping_start_sensor_warning、node gouda_monitor、TR-03）で残す。
  - 地図作成の開始は止めない（追加の承認操作を挟まない: RQ-I011）。開始要求はそのまま mode_manager へ送る。

## 3. デバイスの見張りとドライバの作り直し（ND-18 gouda_sensor_supervisor）

- gouda.sh（起動の方法は bash gouda.sh start の一つ。DEC-090・DEC-091）は常に gouda_sensor_supervisor を起動し、supervisor がドライバ 2 つを子プロセスとして起動する。モードの切替ではドライバを止めない。
- デバイスは名前で探す（DEC-081）。番号は「繋ぎ直されたか」の判定にだけ使う。
  - IMU: /dev/serial/by-id の名前（PRM-54）。同一性は、名前の先にある tty 名と USB のバス番号・デバイス番号（sysfs）。USB のデバイス番号は列挙のたびに増えるので、同じ ttyACM 番号が再利用されても新しい列挙と分かる。
  - XT-32: PC 側アドレス PRM-51 を持つネットワーク I/F。同一性は I/F 名と ifindex（USB-LAN が登録し直されると変わる）。
- 見張りはイベント駆動。`udevadm monitor`（tty・net の追加と削除）と `ip monitor link address` の出力をきっかけに評価する。周期の値は持たない。起動時にも 1 回評価する。
- 作り直しの規則:

| 観測 | 動作 |
|---|---|
| デバイスが現れた（初回、または消えていた後） | ドライバを起動 |
| デバイスがあり、同一性が変わった（繋ぎ直し） | そのドライバだけ止めて起動し直す |
| 同一性が同じ | 何もしない。ドライバが自分で終了しても再起動しない（IMU は繋ぎ直さずに再起動すると応答しなくなるため） |
| デバイスが消えた | そのドライバを止める（再び現れたら起動） |

- デバイスを別のプロセスが使っているときは、ドライバを起動しない（G-DUP-START、人の許可 DEC-103）。
  - IMU はシリアルポートを開いているプロセス、XT-32 は受信の UDP ポート（PRM-52）を持つプロセスを /proc から調べる。
  - 使われていれば DecisionEvent（device_in_use。相手の pid とコマンド）を記録し、次のデバイス・アドレスのイベントで調べ直す。
  - 2026-10-14 に Gouda が 2 つ動き、同じ IMU と LiDAR を 2 つずつのドライバが読んで地図が壊れたため。
- gouda.sh は、自分の pid ファイルにない gouda_core の起動（試験スタック trial:=true は除く）が動いていれば起動を拒み、止め方を表示する（status・stop でも表示する）。
- ドライバの停止は SIGINT → SIGTERM → SIGKILL。各段で待つ時間は PRM-59（5.0 s で確定: DEC-091）。値が無い場合は上限なしで待つ（値を補わない）。
- 前回のセッションで開いた IMU の列挙（同一性）を <data_root>/run/sensor_devices.json に残す。同じ列挙を開き直すときは「IMU が応答しない可能性がある（USB を抜き差しすると直る）」を DecisionEvent（device_reopened_without_reconnect）で記録する。gouda.sh を止めて起動し直すと、このケースになる。
- 記録する DecisionEvent（node gouda_sensor_supervisor）: settings、driver_not_started（設定不足・未導入）、device_present／device_absent、device_reconnected、driver_started／driver_restarted／driver_stopped、driver_exited、device_reopened_without_reconnect、driver_stop_escalated、watch_failed。monitor の履歴欄に出る。
- 上流のドライバ（HesaiLidar_ROS_2.0、ADI_IMU_TR_Driver_ROS2）は改変しない（DEC-075 と同じ方針）。

## 4. 試験

| 試験 | 内容 | 実装 |
|---|---|---|
| TS-31 | 受信表示（周期・経過・時刻差）、しきい値の有無による STALE 判定、地図作成開始時の警告（未受信は常に、STALE はしきい値がある場合） | `gouda_core/test/test_sensor_supervision.py`（ReceptionAndWarningTests、HeaderStampTests）、VM で monitor の API |
| TS-32 | 名前による同一性（by-id → USB 列挙、PC アドレス → I/F）、作り直しの規則（同一性が同じなら再起動しない）、別のプロセスが使っているデバイス | 同（DeviceIdentityTests、RestartRuleTests、DeviceInUseTests）、VM で supervisor の起動と記録。実機の抜き差しは人の協力が要る |

## 5. 残る制約

- gouda.sh を止めて起動し直すと、IMU は同じ列挙のまま開き直すことになり、応答しない場合がある。その場合は IMU の USB を抜き差しする（supervisor が新しい列挙を検知してドライバを作り直す）。
- ドライバが自分で終了した場合、同じデバイスのままでは再起動しない。履歴に driver_exited が出たら、デバイスの抜き差しで作り直す。

## 6. センサーの確定値（DEC-091、REV-037）

| 項目 | 値 | 備考 |
|---|---|---|
| XT-32 の回転数（PRM-60） | 600 rpm（10 Hz） | ドライバの設定 speed で起動時に LiDAR へ設定する（PTC）。LiDAR は 1200 rpm（20 Hz）にも設定でき、いずれ 1200 rpm にする可能性がある |
| IMU の発行周期（PRM-56） | 100 Hz | ADIS16607-2 は約 1000 Hz まで出せる |
| PTC ポート（PRM-53） | 9347 | |
| 点群・IMU の STALE しきい値（PRM-57・58） | 1.0 s | 回転数・周期を変えたら見直す |
| ドライバ停止の待ち（PRM-59） | 5.0 s | |
