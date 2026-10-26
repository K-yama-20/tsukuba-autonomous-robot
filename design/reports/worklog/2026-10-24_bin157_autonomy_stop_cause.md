# 第157便 作業記録：自律走行が少し動いてエラーで止まった原因の調査（読むだけ）

- 日付：2026-10-24
- 読んだコミット：1d7ee4663687a69ba101121964757405ff16cc00（作業ツリーには未コミットの変更あり）
- 読んだもの：`design/reports/status.md`（第139〜156便）、作業指示（CLAUDE.md 1.1〜1.7）、VM の記録
- 人の指示（原文）：「最新の自律走行はエラーで止まってしまった。最初は少し動いた。原因を探索せよ」
- 変更：コード・設定・正本・生成物は変えていない。VM の Gouda には触れていない（読むだけ）。REV・DEC は取っていない（第157便だけ予約した）

## 1. 対象の走行

- 記録：VM `~/gouda_ws/gouda_data/records/20261024_021625`（log/events.jsonl）と `run/gouda_core.launch.log`、`run/localization/a3_20261024_024521.log`、`run/glim_odometry/run-ff780d47/glim.log`
- 走行：run-ff780d47。地図 `maps/20261024_023928_de02d093/converted/001`（02:39〜02:41 に作った地図）、waypoint セット `routes/20261024_021815_228809/007`、23 点
- 証拠（抜き出し）：`design/research/vehicle_pc/2026-10-24_autonomy_stop_run-ff780d47/`
  - `decision_timeline.txt`：DecisionEvent と mode/state の変化の一覧
  - `abort_context.txt`：2 回の中止の直前の launch log
  - `nav2_warn_error_1792777570-1792777619.txt`：走行中の Nav2 の WARN/ERROR
  - `localization_glim_warnings.txt`：EKF と GLIM の警告
  - NTRIP の認証情報・コマンドラインが含まれないことを grep で確かめた

## 2. 時系列（VM の時計、JST）

| 時刻 | 出来事 | 出典 |
|---|---|---|
| 02:45:21 | 自律走行の開始（GLIM 起動、初期位置 x -0.719, y -1.004） | decision |
| 02:46:09 | 自己位置推定 正常 → Nav2 起動 | decision |
| 02:46:13.021 | vehicle_bridge が COMMAND の送信を開始（pc_enable_request つき） | decision |
| 02:46:13.051 | motion_hold 解除。13.104 に motion controller が drive を出し、13.122 に bridge が最初の command_output（x -459, y 480、中立でない）を記録 | decision |
| 02:46:13〜33 | **ESP32 が PC の操作を受け付けていない**（pc_enabled の event がない） | decision |
| 02:46:23.067 | controller_server「Failed to make progress」（0.5 m／10 s を満たさない）→ 回復（costmap の消去、spin 1.57 rad） | launch log |
| 02:46:33.134 | spin が中止（10 s） | launch log |
| 02:46:33.638 | **ESP32 の event pc_enabled**（spin が終わって中立の指令が届いた直後） | decision |
| 02:46:38.191〜 | 経路の追従を再開、drive。ここから約 13 s 走り、waypoint を 2 つ過ぎた（残り 23 → 21、区間 1） | launch log・mode/state |
| 02:46:51.598 | **tf_help「Transform data too old when converting from map to odom」**（経路の時刻 …611.528、map→odom の最新 …611.100、差 0.43 s）→「Failed to transform end pose to global frame」→ follow_path 中止 | launch log |
| 02:46:51.642 | NavigateThroughPoses が status 6・error_code 102 で終了 → mode manager が TR-07 で一時停止（stop_reason plan_failure） | decision |
| 02:47:31〜02:48:10 | 停止中に 推定不能（ekf_covariance_large・ekf_pose_not_updated）。EKF の twist の遅れが 1.4 s → 9.2 s に増える | decision・a3 log |
| 02:48:17 | 人が自律走行を終了（pause → manual） | decision |

error_code 102 は Jazzy の FollowPath.action の TF_ERROR（VM の `/opt/ros/jazzy/share/nav2_msgs/action/FollowPath.action:14` で確認）。

## 3. 原因

### 3.1 止まった直接の原因：map→odom が古くなり、Nav2 の controller が TF エラーで中止した（確認した事実＋推測）

- 事実：controller_server が経路の終点を map から odom に変換するとき、map→odom の最新が経路の時刻より 0.43 s 古く、許容を超えて中止した（`abort_context.txt`）
- 事実：local costmap の CostmapFilter のエラー文から求めた map→odom の遅れは、走行中ふだん 0.09〜0.12 s。02:46:48〜52 に 0.19 → 0.59 s に増え、停止後は数秒まで増えた
- 事実：map→odom は gouda_global_localization が **odometry（GLIM）のメッセージの時刻** で出している（`global_localization_node.py` の docstring と 320 行）。だから map→odom の古さ＝GLIM の odometry の遅れ
- 事実：停止中の 02:47:35〜02:48:19 に EKF が「Twist delay exceeds the compensation limit」（遅れ 1.4〜9.2 s）。GLIM も 02:47:58〜02:48:07 に「large time difference between points and imu」「insufficient number of IMU data」
- 事実：Nav2 の controller の周期は走行中ずっと 9〜12 Hz（設定は 20 Hz、「Control loop missed its desired rate」）。調査時（02:52、manual で待機中）でも load average 5.5〜9.0（6 コア）、gouda_monitor が CPU 91 %、ブラウザの描画のプロセスが 46 %
- 推測：VM の CPU が足りず、走り出して点群の処理が重くなったところで GLIM の odometry が遅れ、map→odom が Nav2 の許容を超えて古くなった。local costmap の transform_tolerance は upstream の params に書かれておらず、Jazzy の既定値（0.3 s と理解しているが、ソースは未照合）が効いていると推測。0.43 s はこれを超える
- 未確認：止まった瞬間の CPU の使用率（記録がない）。gouda_monitor が走行中も 90 % 前後だったか

### 3.2 「最初に少しだけ動いた」ことの背景：開始直後の 20 秒、ESP32 が PC の指令を受け付けなかった（確認した事実＋推測）

- 事実：ESP32 は pc_enable_request のついた COMMAND の x・y が **0（中立）のときだけ** PC を有効にする（`firmware/gouda_esp32_v4/include/gouda_v4/control.hpp:183`）
- 事実：bridge の COMMAND の timer は activate で作られ、最初の送信は activate の 1 周期後。この走行では motion_hold が 13.051 に解かれ 13.104 に drive が出たため、最初の command_output の記録（13.122）は中立でない値だった。pc_enabled は 33.638（spin の終わりで中立が出た直後）
- 事実：02:20 の自律走行（3 点）では activate の 0.14 s 後に pc_enabled が出ていた。順番によって起きたり起きなかったりする（競合）
- 推測：この 20 s の間、車体は動いていない（ESP32 の調停で PC の出力が使われない）。そのため 10 s で「Failed to make progress」、spin も回らず 10 s で中止。spin の終わりの中立でようやく有効になり、02:46:38 から 13 s 走った。人が見た「最初は少し動いた」はこの 13 s と推測
- 安全の面：受け付けなかったのは ESP32 の安全側の作り（いきなり動き出さない）で、車体は止まったまま。危険な動きではない。ただし Nav2 の進みの監視と回復が無駄に 1 回使われた

### 3.3 調査中に見つけた別の問題（今回の停止の原因ではない）

1. **local costmap の keepout フィルタが毎周期失敗している**（事実）：「CostmapFilter: failed to get costmap frame (odom) transformation to mask frame (map) … extrapolation into the future」が 02:20 の走行から毎周期出ている（launch log 全体で 856 件）。map→odom が odometry の時刻で出ており、costmap の今の時刻より 0.1 s ほど古いため。推測：local costmap では keepout が効いていない（global costmap の keepout_layer は別）。安全に関わる可能性があるので確認が要る
2. **local costmap が点群の消去（raytrace）をできない時間がある**（事実）：02:46:49 から「Sensor origin … is out of map bounds … The costmap cannot raytrace」。センサ（xt32_link）の odom での z が −0.00〜−0.03 m で、voxel layer の下端 0.00 を下回った。消えない障害物が残りうる
3. **停止の理由の名前が違う**（事実）：error_code 102（controller の TF エラー）を mode manager は stop_reason plan_failure と記録した。計画の失敗ではない
4. EKF の「Twist queue size (3) is exceeding max_queue_size (2)」が走行前から出ている（02:45:42〜）

## 4. 原因の分類（1.6）

- 3.1：**物理特性／実行環境**（VM の CPU 不足）と **設定**（map→odom の古さと Nav2 の許容の関係が決まっていない）が重なったもの、と見ている。どの層で直すかは人の判断が要る。timeout（transform_tolerance）を延ばして通すことは 1.5 で禁止されているので、その案は出さない
- 3.2：**設計**（開始の手順で、ESP32 が PC を有効にしたことを確かめる前に motion_hold を解いている）
- 3.3-1：**設計**（map→odom の時刻の決め方 DEC-285 と、costmap のフィルタの時刻の使い方の不整合）
- 3.3-3：**実装**（error_code の分類）

## 5. 承認・確認の候補（まだ DEC にしていない。人の指示があれば登録する）

- A（設計、3.2）：開始の手順で、ESP32 の pc_enabled（STATUS の F_PC_ENABLED）を確かめてから motion_hold を解き goal を出す。推奨：解く前に中立を送り続け、有効になるまで待つ。代替：bridge が activate の直後に中立を数回送る。影響：開始の手順（TR-05）、ND-11・ND-12。決まらないと：同じ 20 s の空走りと回復の無駄が起きうる
- B（物理特性・実行環境、3.1）：走行中の CPU を測る（GLIM の odometry の遅れ、controller の周期、プロセスごとの CPU）。gouda_monitor の CPU 91 % の原因（待機中でも高い）とブラウザの影響を調べる。人の作業：走行中の計測を許すか
- C（設計、3.1・3.3-1）：map→odom の時刻を odometry の時刻にしている設計（DEC-285）と、Nav2 の TF の許容・costmap のフィルタの時刻の関係を見直す。安全に関わる（keepout）
- D（実装、3.3-3）：error_code の 1xx（controller）を plan_failure と記録しない
- E（設計・実測、3.3-2）：voxel layer の高さの下端と odom の z のずれ

## 6. 実行した検査・試験

- 試験・設計検査：未実行（記録の読み取りだけ）
- 実行したコマンド（すべて VM で読むだけ）：`bash gouda.sh status`、records と run の log の grep・python での集計、`top -b -n1 -w 120`（コマンド名だけ、引数は表示しない）、`nproc`、`free -m`、`uptime`

## 7. 残るリスク

- 3.1 の CPU 不足の推測は、止まった瞬間の CPU を測っていないので未確定。走行中の計測が要る
- local costmap の keepout が効いていない可能性（3.3-1）は、コードとソースの照合をしていない
- Jazzy の Costmap2DROS の transform_tolerance の既定値は未照合
- VM の Gouda は manual で動いたまま（触れていない）

## 8. 更新した生成物

- なし

## 9. 次に進められる作業／止まっている作業

- 進められる：B の計測手順の案、3.3-1 の上流ソースとの照合（読むだけ）
- 止まっている：A・C・D・E の実装（人の承認待ち、DEC-106）
