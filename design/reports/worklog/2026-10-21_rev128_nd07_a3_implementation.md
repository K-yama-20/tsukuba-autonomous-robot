# 第99便: ND-07 を案 A3 で試す構成の正本への取込みと実装（段 1〜4）、推定不能での一時停止（REV-128・129、DEC-207〜209）

## 読んだもの

- コミット：`4b44f75`（design/records-2026-10-21）の上の作業ツリー（REV-126・127 は未 commit で適用済み）。
- 提案 `proposals/nd07_a3_trial_design_2026-10-21.md`、`proposals/localization_selection.md`、評価の道具 `research/vehicle_pc/2026-10-17_localization_eval/`（run_eval_A3.sh、a3_init.py、twist_relay.py、make_map_pcd.py、tile_pcd.py、params）。
- 実装：`mode_manager_node.py`、`autonomy_client.py`、`autonomy_core.py`、`mode_core.py`、`map_convert.py`、`map_creator_node.py`、`local_odometry_node.py`、`odometry_core.py`、`glim_runner.py`、`vehicle_bridge_node.py`・`motion_controller_node.py`（lifecycle の作り）、`launch/gouda_core.launch.py`、試験の基盤 `test/stack.sh`・`ubuntu_stage5-6.sh`・`stage56_fixture.py`。
- VM（読み取り）：上流の launch と param ファイル（autoware_ndt_scan_matcher・ekf_localizer・map_loader 1.9.0）、pcl_ros 2.6.5 の node と parameter、ekf・ndt のライブラリの診断の項目名（strings）。

## 人の発言（原文）

「転記は私の回答で間違いない。段 1（setup.sh）と段 2〜4（ND-07）に着手して。DEC-207 は (a) で良い。」

DEC-207 の answer_verbatim に記録し、DEC-203・205 の note に、このチャットで確かめたことを足した（REV-128）。

## 記録と設計（REV-128）

- DEC-207 answered（(a)：monitor のタブを作り、gouda.sh start のときに monitor の値で BT を作る）。段 5 の実装の許可は DEC-209（pending）。
- 新しい設定値 PRM-79〜95（すべて未確定。試行の値は評価の値か上流 1.9.0 の既定値）。値の承認は DEC-208（pending）。
- IFD-53（localization/status、型 gouda_interfaces/EstimatorStatus）、試験 TS-41〜43。
- ND-07（構成、IF）、ND-03（ND-07 の有効化と推定不能での一時停止）、ND-05（20 m 格子と軌跡の写し）、TR-05・TR-07、IFD-34（transient_local）、IFD-33 の解釈。

## 実装（人の許可：DEC-203・205、このチャットでの確認）

- 段 1 `setup.sh`：ros-jazzy-autoware-map-loader・ndt-scan-matcher・ekf-localizer と ros-jazzy-pcl-ros（A3 の部品として直接使うので明示）。版は見ない（DEC-205）。
- 段 2 `map_convert.py`・`map_creator_node.py`：PRM-94 で間引いた点を PRM-95 の正方形の格子の PCD と metadata.yaml に（pointcloud_map/）。原図の traj_imu.txt を trajectory_imu.txt に写す。設定が未確定なら格子を作らない（2D 地図は作る）。地図タブからの再変換では node の parameter から補う。
- 段 3 `localization_core.py`（ROS なし）、`global_localization_node.py`（lifecycle、gouda_global_localization）、`launch/gouda_localization_a3.launch.py`（上流の部品を改変せず名前空間 localization/a3 で起動）、`gouda_interfaces/msg/EstimatorStatus.msg`、`gouda_core.launch.py`・`setup.py`・`package.xml`。
- 段 4 `mode_core.py`（stop_reason estimator_unavailable）、`autonomy_core.py`（Mission.map_directory、check_localization_map）、`autonomy_client.py`（IFD-34 を transient_local に、ND-07 の configure・activate と正常の待ち、deactivate・cleanup、EstimatorUnavailable）、`mode_manager_node.py`（IFD-53 の購読、推定不能・途絶での TR-07、TR-10 の guard、TR-03 の guard、TR-11・12 での停止、PRM-93）。
- 試験の基盤：`test/nd07_stub.py`（5-6 の試験の模擬の ND-07）、`ubuntu_stage5-6.sh`（本物の ND-07 を PID で止めて模擬に替える、T5・T6 を追加、WS を変えられるように）、`stage56_fixture.py`（地図に pointcloud_map/ と軌跡）、`ubuntu_nd07_smoke.sh`・`ubuntu_nd07_synthetic.sh`・`a3_synthetic_feed.py`（ND-07 の VM の確認）。

## 自律判断した変更とその理由

- 初期の高さ：人の初期姿勢は x・y・向きだけなので、地図作成の軌跡（GLIM の traj_imu.txt、map 座標）の最も近い点の高さから /config の imu_mount_z_m を引いた値にした（未入力なら 0 として記録）。NDT は高さも探す（PRM-85）。提案 §2 の「初期化の手順」の範囲。
- map→odom の発行の時刻：EKF の姿勢の時刻で計算し（odometry を補間）、odometry を受けるたびにその時刻で /tf に出す。Nav2 が odom→base_link と同じ時刻で map→odom を引けるようにするため。
- IFD-34 を transient_local にした：ND-03 が出した後に ND-07 が configure で購読を始めても受け取れるようにするため（外から見た振る舞いは同じ）。
- 点群の間引きは、評価の球の範囲（1〜100 m）の代わりに pcl_ros の CropBox（立方体）2 つにした（独自の node を作らないため。PRM-79・80 の説明に書いた）。

## 修正（原因の分類：1.6）

- 設計の記述：PRM-95 の説明に、整数の m に限ることを REV-129 で足した（下の実装の修正に合わせた）。
- 実装：VM の確認で、autoware_pointcloud_map_loader が metadata.yaml の格子の左下の座標を整数で読み、`[0.0, 0.0]` で落ちた（`yaml-cpp: error at line 3, column 18: bad conversion`、exit code -6）。評価の道具は整数で書いていた。変換を整数で書くように直し、格子の大きさが整数の m でなければ理由を付けて拒否するようにした。同じ日に書いた単体試験の期待値（`[-20.0, -20.0]`）は、上流の形式の事実に合わせて `[-20, -20]` に直した（根拠は VM の記録）。直した後、map loader は起動した。

## 実行した検査・試験

（作業ツリーは 4b44f75 の上の未 commit の変更）
- `design/.venv/bin/python design/tools/apply_revision.py REV-128 --dry-run --check`：新しい違反 4（生成物の未生成 3、IFD-34 の QoS のコードとの食い違い 1。どちらもこの作業の中で解消）、新しい未判定 17（DR-11、PRM-79〜95 の値未確定）。本適用の後に解消を確認（下）。
- `run_checks.py`（実装の後）：設計整合性の要約行 `{"合格": 12, "違反": 0, "未判定": 5} 違反0件・未判定5件`。DR-11 は 47（30＋17）、DR-15 は 31（＋1：`global_localization_node.py` の IFD-28 の QoS の深さ 50。ほかの node の同じ行と同じ種類で、DEC-189 の許容の一覧の案の対象）。終了コード 1 の原因は入力の照合の 3 件（前と同じ）。
- Mac の単体試験 `python3 -m pytest -q gouda_core/test`：238 合格、8 skip、不合格 0（修正の前）。修正の後の test_mapping_core 19 合格。
- 規則を壊した写し（scratchpad）で、足した試験が不合格になることを確認：状態の判定（NDT の診断なしを正常にする）、補間の範囲、metadata の座標、stop_reason。
- VM（`~/gouda_rev128_ws`、gouda_interfaces と gouda_core を --symlink-install で build）：単体 246 合格、不合格 0。
- VM `ubuntu_nd07_smoke.sh`（ROS_DOMAIN_ID 78、原図 20261014_054556_fbd0a733 を読むだけ）：変換（格子 13 個）、configure で A3 の部品 6 つが起動、センサーなしでは初期化が失敗し「推定不能」（init_failed）のまま、/tf の発行者は gouda_global_localization だけ、deactivate・cleanup で A3 の部品が 0。
- VM `ubuntu_nd07_synthetic.sh`（ROS_DOMAIN_ID 79、地図の点を軌跡の上の姿勢から見た模擬の点群）：
  - 軌跡 200 行目、初期姿勢のずれ 1 m・10 度：約 10 s で「正常」。nearest_voxel_transformation_likelihood 3.08、pose_no_update_count 0、EKF の標準偏差 0.07〜0.16 m。map→odom と本当の姿勢の差は x 0.04 m、y 0.07 m、z 0.13 m。入力を止めて 3 s で「推定不能」（input_stale）。
  - 200 行目、2.8 m・30 度：「正常」。400 行目、1 m・10 度：「正常」。
  - 400 行目、5 m・90 度：探索が誤った姿勢（傾いた向き）に収束し、照合の良さ 2.03（下限 2.3 未満）で「推定不能」（ndt_score_low）。正常にはしなかった。評価（2026-10-17、実の点群、高さは基準の軌跡）の「5 m・90 度から収束」はこの模擬では再現しなかった（観測。理由は未確認）。
- VM `WS=~/gouda_rev128_ws bash gouda_core/test/ubuntu_stage5-6.sh`（ROS_DOMAIN_ID 77、模擬の ND-07 nd07_stub.py、Nav2 の loopback_simulator）：
  - T1：初期姿勢なし・ND-07 なしの開始は拒否。T2：TR-05 で ND-07 の configure・activate → 正常 → Nav2 → 最後の waypoint で一時停止（TR-08）。T3：TR-12 で ND-07 も deactivate・cleanup。T4：一時停止・再開・走行中の終了。
  - T5：走行中に模擬の ND-07 を推定不能にする → 一時停止、stop_reason estimator_unavailable、motion_hold=true。正常でない間の再開は拒否（TR-10 の guard）、正常に戻すと再開できた。
  - T6：模擬の ND-07 が状態を出さなくなる → PRM-93（試行の値 1.0 s）の後に一時停止（estimator_unavailable）。終了で ND-07 は unconfigured。
  - Nav2 の ERROR 4 行：controller_server の「Failed to make progress」1 行（T2 の途中、その後に到達）と、取消のときの bt_navigator の「Failed to get result for follow_path in node halt!」3 行。
- 修正の後の Mac の単体試験：239 合格、8 skip、不合格 0。
- REV-129（PRM-95 の説明に整数の m の制約）：`--dry-run --check` 新しい違反 0・未判定 0、本適用の後の `run_checks.py` の要約行 `{"合格": 12, "違反": 0, "未判定": 5} 違反0件・未判定5件`（DR-11 47、DR-15 31）。
- rosbag の再生での評価との比較：未実行（外付けがつながっていない）。実車：未実行。

## 承認待ち・実測待ち

- DEC-208（PRM-79〜95 の値）、DEC-209（段 5 の実装）。
- 実測：PRM-79〜95 は実走で確かめる。

## 残るリスク

- 推定不能の判定は、誤った姿勢を「正常」とみなすことを防げない（評価の 0.546 m の例）。模擬では高さが約 0.13 m ずれた。
- 推定不能の間も map→odom は出し続ける（止めるのは ND-03 の一時停止）。一時停止は PC 出力の中立化で、車体の停止の保証ではない。
- x86 機では setup.sh は未実行（DEC-205 で人が VM だけと決めた）。

## 更新した生成物

- `generated/params/gouda_global_localization.yaml`・`.trial.yaml`（新）、`gouda_map_creator.trial.yaml`（新）、`gouda_mode_manager.trial.yaml`、ほかはハッシュの行。ビュー（pending_classification、intent_index ほか）、`reports/model_diff_rev-128.md`。

## 次の作業

- 人の判断：DEC-208、DEC-209。
- 止まっている：実車（trial なし）での A3 の自律走行（DEC-208 の値）、Nav2 で使える 2D 地図（DEC-107）。
- 作業ツリーに別のセッションの提案 `proposals/swept_corridor_map_2026-10-21.md`（DEC-107 の分岐）がある。中の人の決定は台帳に未記録。扱いは人に確かめる。
- commit：未実行。
