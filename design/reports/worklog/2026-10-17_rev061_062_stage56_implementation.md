# 作業記録 2026-10-17 第32便: 工程 5-6 の実装（GNSS の取込み、静的 TF、Nav2、mode_manager の Nav2 の client、ND-08）と VM の試験（REV-061・REV-062）

## 読んだもの

- コミット `2ce59ea3eb892b4a430f7f38f179b13aab4c37c9` ＋ 第31便の未コミットの作業（REV-060、`proposals/stage56_navigation_localization_plan.md`）。
- 正本: ND-03・08・09・10・11・13・14・18、IFD-13〜15・18〜26・28・34・36・39・41・42、TR-05〜16、TS-01・05・15・21・31・34、PRM-01〜07・11・12・17・18・54、G-INIT-POSE-GNSS、G-DDS、DEC-009。intent.md の全行（第11版）。
- 上流: septentrio_gnss_driver 1.4.8 の config/gnss.yaml と msg（apt-get download して VM で展開）、nav2_loopback_sim 1.3.13 のソース、nav2_bringup の nav2_params.yaml（research の写しは VM の 1.3.13 と同一を diff で確認）・navigation_launch.py、BT の navigate_through_poses_w_replanning_and_recovery.xml、GLIM の config_ros.json（VM の導入済み）、rclpy の tf2_ros/static_transform_broadcaster.py（VM）。
- コード: sensor_supervisor・device_watch・sensor_config・monitor_*・web・mode_core・mode_manager_node・glim_runner・waypoints・map_database・speed_mask・motion_controller・launch・setup.sh。

## 1. 人の回答（判断台帳に原文）

- DEC-120〜124: 「DEC-120〜124 をすべて許可する」。DEC-124 は方針の許可で、推奨のとおり詳細の設計を提案として出してから実装する（`proposals/gnss_initial_pose_design.md`、承認事項 DEC-126〜129）。

## 2. 実装（人の許可 DEC-120〜123）

| 範囲 | 内容 | ファイル |
|---|---|---|
| GNSS（ND-19、DEC-123 (1)） | 上流の gnss.yaml を雛形に接続先（PRM-65）・frame・PC 時刻・TF なしを差し込む。RTK の補正は x86 機の `<data_root>/config/gnss_rtk.yaml`（人が置く、公開しない）があれば使う。supervisor が接続先（serial の by-id、tcp のネットワークの I/F）で見張って起動。monitor に受信・測位の種類・衛星数・向きを表示（地図作成開始の警告には入れない） | gnss_config.py、sensor_supervisor_node.py、gouda_sensors.launch.py、monitor_core.py・monitor_node.py・app.js、setup.sh |
| 静的 TF（ND-13、DEC-122） | /config から base_link→base_footprint・xt32_link・imu_link・gnss_link・gnss_aux1_link。UNKNOWN は中立の値で記録。/config の保存で出し直す。/config に GNSS の 2 つのアンテナの位置の欄 | sensor_extrinsics.py、static_tf_node.py、monitor_core.py |
| Nav2（ND-10、DEC-121・122） | 上流の nav2_params.yaml を雛形に RPP・NavFn・spin/backup/wait・velocity_smoother・TwistStamped・点群の障害物の層・SpeedFilter・BT（PRM-11・18）。collision_monitor なし。autostart なし。実車の値（PRM-11・17・18・66〜73）が未確定なら起動しない | nav2_config.py、gouda_nav2.launch.py、gouda_core.launch.py、setup.sh |
| mode_manager（ND-03、DEC-120） | TR-05（ハッシュの照合、Nav2 の設定、初期姿勢、ND-07 の node の有無を確かめてから自律走行へ。hold は適用中まで true）、TR-06・07・08・10（同じプロセスの中だけ）・11・12 | autonomy_core.py、autonomy_client.py、mode_core.py、mode_manager_node.py |
| ND-08（DEC-123 (2)） | TR-05 で GLIM を odometry だけで起動（odom→odom_glim→base_link）、gouda_local_odometry が TF から localization/odometry を作る。TR-11・12 で止める | glim_runner.py、odometry_core.py、local_odometry_node.py |
| ND-11 | cmd_vel を TwistStamped で受ける（PRM-12 を承認値 true に。期限切れの判定は今も受信時刻） | motion_controller_node.py、stage55_probe.py |
| monitor | waypoint タブに「自律走行の準備」（セットの選択、地図と waypoint のプレビュー、初期位置の入力と地図のクリック、開始の要求に添える） | web/index.html・app.js、monitor_node.py |
| 生成器 | bt_params の仮値のファイル（bt_params.trial.yaml）を出す（試験の基盤。実車では読まない） | design/tools/generate_params.py |

実車での振る舞い: ND-07 が無いため自律走行の開始（TR-05）は「gouda_global_localization (ND-07) is not running」で拒否される。Nav2 は未確定の値（PRM-11・17・18・66〜73）のため起動しない。GNSS のドライバは接続先（PRM-65）が未確定のため起動せず理由を記録する。

## 3. 自律判断した変更とその理由

- **TF の木の直し（設計）**: IFD-19（odom→base_link）と IFD-20（base_footprint→base_link）を同時に使うと base_link の親が二つになる（ND-13 が未実装だったので表に出ていなかった）。静的 TF を base_link→base_footprint（z=−PRM-05）にした。base_link の親は odom だけ。Nav2・GLIM は base_link を使い、振る舞いは変わらない。REV-061 の要約・ND-13・IFD-20 に記録。**人の確認を求める**（承認事項ではなく自律判断として扱ったが、TF の向きは REP-105 の慣例と違う）。
- **待ちの上限を置かない**: Nav2 の STARTUP・lifecycle・goal の受理の待ちに上限の値を作らなかった（値を発明しない）。相手のサービスがないときはすぐ失敗として記録する。人の一時停止・終了は待ちを打ち切る。
- **hold の解除の条件**: TR-05 の action どおり「適用中」を確かめるまで hold=true。帯の外から始めると動かない（TS-15 の (3) で確認）。
- **ND-08 の中継は GLIM の TF から**: GLIM の ~/odom の中身は実機で確かめていないので、TF（odom_glim→base_link）の差分から速度・角速度を作る（評価の twist_relay と同じ考え方）。
- **TR-05 の guard**: ND-07 は node の有無（gouda_global_localization）で見る。推定の有効性（EstimatorStatus）は ND-07 の実装（DEC-115 の後）で加える。
- **monitor の GNSS の品質の表示**: PVTGeodetic・AttEuler の mode の意味は SBF の定義を AI の知識で書いた（**原本未照合**。受信機のリファレンスで確かめる）。表示だけで判断には使わない。
- **試験の環境**: VM に sudo がないため、nav2_loopback_sim と依存を ROS の apt から取り出して展開し、試験の script の中だけで読んだ（システムは変えていない）。loopback_sim は ND-07・ND-08 の代わり（node 名 gouda_global_localization）。

## 4. 修正（原因の分類: CLAUDE.md 1.6）

1. SpeedFilter が mask を受け取らなかった — 実装。global_costmap の名前空間で相対名が /global_costmap/… になった。filter の topic を絶対名に（nav2_config）。試験に検査を足した。
2. /config の保存で静的 TF が古い値のまま — 実装。rclpy の StaticTransformBroadcaster は同じ子の frame を置き換えない。gouda_static_tf が /tf_static に全件を出す。
3. 既存の単体試験 test_sensor_extrinsics の数え方 — 試験（基盤）。/config の項目に GNSS を足したため「全項目＝LiDAR と IMU」の前提が崩れた。数える対象を LiDAR・IMU の項目に絞った（試験の意味は同じ）。
4. DR-15 の未判定 10 件 — 実装（書き方）。local_odometry_node.py の単位の姿勢の 1.0 と docstring の「depth 5.」。値は変えずに書き方を直した。
5. 再現しない不具合: 最初の goal が BT の受理の待ち（上流の default_server_timeout 20 ms）で失敗（G-NAV2-FIRST-GOAL）。1 回だけ。待ちの値は変えていない。一時停止に入り再開で続けられる（安全側）。

## 5. 試験（コマンド・対象・結果）

対象: コミット 2ce59ea ＋ 作業ツリー（本便の変更）。

- Mac の単体: `cd gouda_core && python3 -m unittest discover -s test -p "test_*.py"` → 166 件 OK・1 件 skip（新規: test_gnss_config 5、test_nav2_config 8、test_autonomy_core 9、test_local_odometry 5、test_monitor_core の GNSS 3、test_sensor_extrinsics の静的 TF 2）。
- VM の単体: 同じコマンド → 166 件 OK・1 件 skip（照合用の雛形を写した後。写す前は 16 件がファイルなしのエラー: 試験の環境）。
- VM の結合: `gouda_core/test/ubuntu_stage5-6.sh` を 3 回（FILE-STAGE56-VM-TEST）。最後の回: 開始の拒否 2 件（初期位置なし、ND-07 なし）、開始 → hold=true（適用中待ち）→ 適用中で hold=false → 最後の waypoint（3.94, 2.77）で一時停止（TR-08）、TR-12 で Nav2 RESET・ND-11/12 の無効化・GLIM の停止・記録の自動停止、TR-05 → TR-06（goal の取消）→ TR-10（残りの waypoint から）→ TR-11。
- VM の静的 TF: /config の保存で revision 1 の TF（base_link→gnss_aux1_link = (−0.5, 0, 1.1)）。
- VM の 5-5 の試験の再実行（ND-11 の型の変更）: プローブの全段が合格（cmd_vel の途絶で 0.747 s に中立など）。
- VM の前回の試験（recorder・GLIM）の再実行: 前回と同じ結果。
- 全検査 `design/.venv/bin/python design/tools/run_checks.py` → 終了コード 1。不合格は人の drawio の SHA だけ（input_integrity・migration_validator・migration_tests の 1 件）。設計整合性 17 ルール 違反 0、未判定 4（DR-04 5、DR-05 2、DR-10 2、DR-11 67: 新しい未確定の実車値 PRM-65〜73 の分が増えた）。
- 未実行: x86 機での全部（GNSS の受信機、Nav2 の導入、CPU の余裕）、記録の再生での ND-08（外付けの SSD が未接続）、TS-15 の (1)(2)、TS-21 の再起動・復帰の条件、TS-01 の値の照合、PRM-12 の実車。

## 6. 承認事項と実測待ち

- 新規 pending: DEC-125（実測・確認: GNSS の接続先と RTK の補正の受け方）、DEC-126〜129（GNSS による初期位置の詳細）。
- 実車値（tbd）: PRM-65（GNSS の接続先）、PRM-66〜73（Nav2 の速度・加速度・footprint・障害物の高さ・膨張半径）。実車で Nav2 を起動するには全部が要る。PRM-11・17・18 も未確定のまま。

## 7. 残るリスク

- TF の向きの直し（base_link→base_footprint）は人の確認が要る。
- Nav2 の設定の雛形の値（RPP の lookahead など）は上流の既定のまま。実車での調整は TS-16 などで。
- 最初の goal の失敗（G-NAV2-FIRST-GOAL）が x86 機で起きるかは未確認。
- VM の制御周期は 3 Hz 前後（controller の警告）。x86 機の余裕は未測定。
- Nav2 の RESET を goal の取消の直後に出すと bt_navigator が警告を出す（動作は正常）。
- 「PC 出力の中立化は車体の停止の保証ではない」。手動の優先・ESP32 の watchdog の実機での確認（5-5 の実車試験、DEC-050）は残る。

## 8. 生成物の変更

- `design/generated/params/`: 新規 gouda_nav2.yaml・gouda_nav2.trial.yaml・septentrio_gnss_driver.yaml・bt_params.trial.yaml。controller_server.yaml に enable_stamped_cmd_vel: true（PRM-12 承認）。その他は元の model の SHA の行だけ。
- `design/generated/*.md`・conflicts.yaml・intent_*.yaml: render_views の再生成。

## 9. 次に進められる作業と止まっている作業

- 人の作業: DEC-125 の回答（x86 機の `ls -l /dev/serial/by-id/` と `ip -4 addr`、RTK の受け方）、x86 機への反映（setup.sh で Nav2 と GNSS のドライバが入る。sudo が要る）、TF の向きの直しの確認、DEC-126〜129 の回答。
- 進められる: 承認の後の DEC-126（地図作成の間の GNSS の記録）。ND-07 は DEC-115 の回答の後。
- commit はしていない。
