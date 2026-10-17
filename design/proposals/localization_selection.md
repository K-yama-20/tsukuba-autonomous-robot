# 自己位置推定の方式の選定（Q-02 / DEC-021。提案 第2版。実装は許可まで行わない）

状態: 提案（承認待ち）。2026-10-17。

- 人の指示（判断台帳に原文）:
  - DEC-109: map_creator の改良を一旦置き、自己位置推定の方式の選定に進む。
  - DEC-110: Cartographer も検討する。
  - DEC-111: LeGO-LOAM と Autoware の ndt_matching も検討する。
  - DEC-112: KISS-ICP は以前の評価試験で目標性能を出せなかったため外す。**案 A・A3・B のみを検討する。rosbag を VM に移すのは一旦しない。**
  - DEC-113（intent.md 第10版、人の編集）: 「Navigationに関しては…独自プログラムで実装しない。」の後に「OSSとして公開されており使用実績の豊富なものについては、Nav2に追加しても良い。」が加わった（RQ-I083）。
  - DEC-114: 外付けと VM を使ってよい。**案 A と A3 を重点的に検証する。** 両方の node を用意して gouda_monitor で切り替える案もある（§10）。合格基準は AI の案で承認。次の実機試験でも同じ場所を 2 回走る。
- 実装・設定の変更は、人の個別の許可（DEC-106）の後。
- 前提の未回答: DEC-105（IMU と LiDAR の傾き）、PRM-05（base_link の高さ）。
- 事実は 2026-10-17 に上流のページとソースで確かめた（§8）。推測は推測と書く。

| 案 | odom→base_link（ND-08） | map→odom（ND-07） |
|---|---|---|
| A | GLIM（odometry だけ） | lidar_localization_ros2（NDT_OMP、Nav2 用の設定） |
| A3 | GLIM（odometry だけ） | Autoware Core の autoware_ndt_scan_matcher ＋ autoware_ekf_localizer |
| B | GLIM（odometry だけ） | Nav2 AMCL（pointcloud_to_laserscan で 2D に変換） |

## 1. 地面の推定は要るか（DEC-109 の質問への答え）

地面の推定が要るのは、地図の点を「その場の地面からの高さ」で障害物と空きに分けるときだけ。

| 使い道 | 案 A・A3（3D 照合） | 案 B（2D 照合） |
|---|---|---|
| 自己位置推定 | 3D 点群地図（PCD）と照合する。**地面の推定は要らない** | 2D 地図が、走行中の 2D スキャンと同じ高さの帯で作られている必要がある。**地図全体で正確な地面の推定が要る**（DEC-107 が前提に戻る） |
| Nav2 の 2D 地図（大域の経路計画） | 走るのは地図作成で通った道。経路から数 m なら「軌跡の高さ − 1.18 m」を基準にした帯で足りる見込み。1.18 m は rosbag で測った LiDAR の地面からの高さ（FILE-EVENING-MAPS-ROSBAG） | 上の行と同じ地図を使う |
| 走行中の障害物（ND-09） | 生の点群から地面を除く処理が要る（車体座標の局所の問題で、地図の地面の推定とは別） | 同じ |

## 2. 要求（正本から）

| 要求 | 出典 |
|---|---|
| 初期位置と向きは人が「ある程度」指定する。開始ボタンの後は追加の承認なし | intent.md 体験 9（RQ-I011）、IFD-34（PoseWithCovarianceStamped） |
| PC 再起動後の再開は人の初期位置の再指定の後。保存した姿勢は使わない | DEC-009、H-007 |
| 停止の原因に「推定不能」を区別して残す。stale・未初期化を正常にしない。生存の信号で品質を代用しない | IF-010（EstimatorStatus 案、D-13）、FM-M-007 |
| map→odom は Global_localization だけ、odom→base_link は local_odometry だけが出す | M-007・M-008、ND-07・ND-08、D-17 |
| 同じ TF を複数の node から出さない。センサーの固定 TF は一つの所有者（ND-13） | intent.md 設計規約、D-17 |
| 車輪のエンコーダはない | DEC-037、M-008 V9 |
| GLIM などの交換は、その部品と launch の変更で済む | intent.md 交換性 |
| Gouda の判断を記録の再生で再現できる | intent.md デバッグ性 |
| Nav2 は改変しない。Nav2 の機能を独自プログラムで作らない。OSS として公開され使用実績の豊富なものは Nav2 に追加してよい | intent.md 設計規約（第10版 82 行、RQ-I083） |

## 3. 3 案に共通: GLIM を odometry だけで動かす（ND-08）

確かめた事実（glim_ros2・glim のソース、§8）:
- 地図作成の機能を切ると odometry だけで動く（config_ros.json の enable_local_mapping・enable_global_mapping を false）。
- TF と odometry の topic は、拡張モジュール librviz_viewer.so が出す。TF は「map_frame_id → odom_frame_id → base_frame_id」と「imu → lidar」。
  - TF を止める設定は publish_imu2lidar（imu→lidar）だけ。
  - map→odom は、global mapping が補正を更新しない限り**単位行列**のまま（TrajectoryManager の初期値）。odometry だけなら常に単位行列で、飛ばない。
  - frame の名前は設定で変えられる（map_frame_id・odom_frame_id・base_frame_id）。
- odometry の topic `~/odom`（nav_msgs/Odometry）は、子の frame が IMU で、速度は並進だけ（角速度なし）。共分散は計算された時だけ入る。購読者がいる時だけ出る。

設計の案（3 案に共通。上流は変えず、設定と小さな中継で合わせる）:
- **frame の名前の付け替え**:
  - GLIM の map_frame_id を `odom`、odom_frame_id を `odom_glim`、base_frame_id を `base_link` にする。
  - TF の木は map →（照合器）odom →（GLIM、単位行列）odom_glim →（GLIM）base_link。odom の親は一つで、重ならない。
  - Nav2 は odom を局所の座標系として使える。frame の名前は案で、実装時に決める。
- **publish_imu2lidar は false**: センサーの固定 TF は ND-13 が持つ（同じ TF を二つの node から出さない）。
- **odometry の中継（独自の小さな node）**: GLIM の `~/odom` と IMU の角速度から、IFD-25（localization/odometry、odom→base_link、m/s と rad/s）の形の nav_msgs/Odometry を作る。Nav2 の controller・velocity_smoother がこの topic を使う。
- **地図作成と走行で GLIM の設定を切り替える**: 地図作成モードは今の設定（global mapping あり）、自律走行・一時停止では odometry だけの設定。同時には動かさない（intent: 競合する推定器を同時に有効化しない）。
- IMU と LiDAR の間の回転（約 2 度。FILE-EVENING-MAPS-ROSBAG の参考値）は odometry の重力の向きに効く。/config の設定は人（RQ-I081）。
- 観察（未試験）: odometry だけでは TrajectoryManager の履歴が消されずに増える。1 frame 約 136 B × 10 Hz で 1 時間に約 5 MB と見積もる（AI の計算）。

## 4. 各案

### 案 A: lidar_localization_ros2（第一候補）

事実（v1.3.0、2026-10-09。BSD-2。§8）:
- Nav2 用の設定（enable_map_odom_tf）では map→odom を出す。odom→base_link は TF から取る（なければ map→odom を出さない）。
- 照合の予測には、速度の topic か odom の TF を使える（use_odom_tf_prediction）。Nav2 用の launch は IMU の事前積分を既定で使わない。
- 既定の設定 nav2_ndt_urban.yaml: NDT_OMP、格子 1.0 m、score のしきい値 6.0、局所の地図の切り出し 150 m。
- 品質: `/alignment_status`（DiagnosticArray）。
  - failure_category: healthy・missing_map・missing_initial_pose・weak_overlap（点が 100 未満）・bad_match・stale_prediction（受理なし 2.0 s）・overload（0.3 s 超）。
  - fitness_score、連続の棄却の数。
  - 診断だけで動作は変えない。棄却の間は map→odom を最後に受理した値で止める（odometry で走り続ける）。
  - `/reinitialization_requested` は約 30 s 受理がないと true。自動の再初期化は既定で無効。
- 初期姿勢: `/initialpose`（map の frame）。受けると前の map→odom を捨てる。
- 入手: ソースからの build だけ（8 コアで約 30 分と README）。ndt_omp_ros2（Jazzy の CI も humble ブランチで build）が必須。地図は PCD・PLY。
- Nav2 には 2D 地図が別に要る。

Gouda への当てはめ:
- TF・初期姿勢は正本の IF にそのまま合う。
- 「推定不能」は、failure_category・棄却の続く時間・reinitialization_requested から ND-07 の側で EstimatorStatus を作る。しきい値は承認か実測。
- 地図は GLIM の dump から PCD を作る。地図の変換の変更（pointmap.pcd を 2D の設定と独立に作る）は別の承認事項。
- 独自の部分: odometry の中継（共通）と、EstimatorStatus への変換。
- 注意: 保守者は 1 人。版を固定する（third_party/drivers.repos と同じ扱い）。

### 案 A3: Autoware Core の NDT ＋ EKF（比較）

事実（v1.10.0。Jazzy の公開あり、2026-10-15 更新。CI は humble・jazzy。Apache-2.0 と BSD。§8）:
- ndt_scan_matcher:
  - 入力は点群と EKF の姿勢（予測）。地図は pointcloud_map_loader から受ける（PCD 1 つか 20 m 格子）。
  - 出力は ndt_pose_with_covariance。
  - 品質は候補の中で最も豊富: transform_probability、nearest_voxel_transformation_likelihood、反復回数、振動、実行時間、初期値からの距離など（diagnostics）。
  - 初期姿勢を Monte Carlo で探すサービス（ndt_align_srv）がある。
  - TF を出すかの記載はない。
- ekf_localizer:
  - NDT の姿勢と速度（TwistWithCovarianceStamped）を融合し、**map→base_link を出す**。TF を止める設定はない（周期 tf_rate だけ）。
  - 速度の更新が途絶えると警告・エラーを出す。/initialpose を受ける。

Gouda への当てはめ:
- **TF が重なる**: EKF の map→base_link と GLIM の odom_glim→base_link で、base_link の親が二つになる。
  - 案: launch で EKF の /tf を別の topic に remap して無効にし、EKF の姿勢と GLIM の TF から map→odom を計算して出す中継（独自）を置く。
- **速度の中継（独自）**: GLIM の odometry から TwistWithCovarianceStamped を作る。
- 地図の読み込みに pointcloud_map_loader（Autoware の別のパッケージ）も要る。
- 独自の部分: odometry の中継（共通）、速度の中継、map→odom の中継、EstimatorStatus への変換。

### 案 B: Nav2 AMCL（基準）

事実（nav2_amcl 1.3.13。LGPL-2.1-or-later。§8）:
- 入力は sensor_msgs/LaserScan だけ。3D の点群は pointcloud_to_laserscan（Jazzy 2.0.2。target_frame の座標で min_height・max_height の帯を切る）で 2D にする。
- 運動のモデルは差動二輪と全方向。map→odom を出す（tf_broadcast）。
- 初期姿勢は /initialpose・set_initial_pose のサービス・パラメータで渡す。初期姿勢が分からない間は TF を出さない。
- 品質: amcl_pose の共分散（x・y・yaw）と粒子の重みだけ。失敗を示す専用の出力はない。
- 粒子フィルタなので、再生のたびに結果が少し変わりうる（乱数。AI の推測）。

Gouda への当てはめ:
- Nav2 の機能だけで成り立つ（intent の「Nav2 に機能を持たせ」に最も素直）。apt で入り、軽い。
- 2D 地図を走行中のスキャンと同じ帯で作る必要があり、地面の推定（DEC-107）が前提に戻る。屋外の坂では、帯が地面に当たるか、構造物を外す。
- 「推定不能」は共分散からしか作れない（弱い）。
- 独自の部分: odometry の中継（共通）と、共分散からの EstimatorStatus。

## 5. 要求との照合（机上。実測は §6）

| 項目 | A | A3 | B |
|---|---|---|---|
| TF の分担（map→odom と odom→base_link） | そのまま合う | EKF の TF の remap と map→odom の中継が要る | そのまま合う |
| 初期姿勢（IFD-34） | /initialpose | EKF の /initialpose（＋ Monte Carlo の探索） | /initialpose |
| 「推定不能」の材料（IF-010） | failure_category・fitness・棄却の数 | 最も豊富（複数の score、diagnostics） | 共分散だけ |
| 地図 | GLIM の PCD | GLIM の PCD（20 m 格子に分けるか 1 つ） | 地面の推定つきの 2D 地図 |
| 坂・屋外（使用環境、DEC-103） | 3D で有利（見込み） | 3D で有利（見込み） | 不利（見込み） |
| 独自の部分（共通の odometry の中継のほか） | EstimatorStatus への変換 | 中継 2 つ、EstimatorStatus への変換 | EstimatorStatus への変換 |
| 入手 | ソースの build（約 30 分） | Jazzy の公開あり（依存が多い） | apt |
| 保守 | 個人（更新は活発） | 組織（TIER IV） | Nav2 |
| ライセンス | BSD-2 | Apache-2.0・BSD | LGPL-2.1+ |
| 交換性（部品と launch で済む） | 高い | 中（中継が増える） | 高い |
| 記録の再生での再現 | 決定的（見込み） | 決定的（見込み） | 乱数の影響（見込み） |

## 6. 評価の計画（DEC-112・DEC-114）

**検証の仕組み（2026-10-17 に用意。評価用で、Gouda の製品のコードではない）**:
- 場所: VM（aarch64、4 コア、メモリ 3 GB）の別のワークスペース `~/loc_eval_ws`。Gouda のワークスペースは変えない。
- データ: rosbag は外付けを Parallels の共有（`/media/psf/Crucial_4TB`）でその場で読む。VM には写さない（DEC-112）。
- 地図: GLIM の dump の全 submap の点（loop closure の補正後）を 0.2 m の格子で間引いた PCD。
  - 175857: 234 万点
  - 173522: 111 万点
- odom→base: GLIM の dump の odometry（odom_lidar.txt。時刻は rosbag の点群と 6804 frame すべて一致）を、再生の時刻に合わせて TF として流す。
  - 走行中の GLIM の odometry と同じ推定器の出力で、何度でも同じ入力になる。
- 基準の frame: LiDAR の frame（xt32_link）。GLIM の軌跡は LiDAR の姿勢なので、取付の値を介さずに比べられる。
- 基準の軌跡: 同じ走行の traj_lidar.txt（同じ走行の地図なので楽観的）。別の走行の地図での評価は、173522 の rosbag を 175857 の地図で推定させ、収束するかで同じ場所かを確かめてから行う（上から見た重なりの比較では判定できなかった）。
- 道具（`design/research/vehicle_pc/2026-10-17_localization_eval/` に置く予定）: 地図の PCD 作り、odometry の TF の再生、初期姿勢、記録、比較、実行のスクリプト。

以下は第2版の計画（参考に残す）:

1. **机上の比較（この文書）**: 済み。
2. **外付けを Mac で読む分析**（ROS なし。分析だけで実装ではない。外付けのつなぎ直しが要る）:
   1. 案 B の成り立ち: rosbag の点群を IMU の姿勢で水平に戻し、base_link の高さの帯で 2D スキャンを作る。経路に沿って、帯の中の点が方位のどれだけを埋めるかと、坂で地面が帯に入る割合を出す。
   2. 案 A・A3 の地図の向き不向き: GLIM の地図で、経路に沿って照合が弱くなる区間（開けた所、前後方向の手がかりが少ない直線）を、点の法線の分布から出す。
   3. 173522 と 175857 が同じ場所か（別の走行の地図での評価ができるか）。
3. **実際のパッケージを rosbag で動かす評価**（ROS 2 が要る）:
   - 場所は未定。VM へ rosbag を移すのは一旦しない（DEC-112）。x86 機で人が動かすか、後で決める。
   - 組み合わせは A・A3・B。
   - 指標:
     1. GLIM の補正後の軌跡との位置・向きの誤差
     2. 初期姿勢のずれからの収束
     3. 誤差が大きい時に「不良」を出すか
     4. 4.2 s の途切れの前後
     5. CPU 負荷と遅れ
   - 合格の基準の値は人が決める。AI の案: 95 % 点 0.3 m 以内、発散なし、誤差 0.5 m 超で不良。

## 6.1 検証の結果（2026-10-17、VM。FILE-LOCALIZATION-EVAL。同じ走行の地図なので楽観的）

| 項目 | 案 A（lidar_localization_ros2） | 案 A3（Autoware Core の NDT＋EKF） |
|---|---|---|
| 走行全体（686 s、4.2 s の LiDAR の途切れを含む）の位置の誤差 | 中央値 0.060 m、95 % 点 0.124 m、最大 0.286 m | 中央値 0.068 m、95 % 点 0.209 m、最大 0.546 m |
| 誤差 0.5 m 超で「不良」を出したか（走行全体） | 0.5 m 超はなし | 0.5 m 超の 1 回（0.546 m）を「正常」とした |
| 初期姿勢のずれ 1 m・10 度（止まった状態から） | 1.0 s で収束 | すぐ収束 |
| 同 2.8 m・30 度 | 1.7 s で収束 | 探索なし: 姿勢を出さない。探索あり: すぐ収束 |
| 同 5 m・90 度 | **収束しない。誤差 6.8〜9.7 m の姿勢を 60 秒出し、524 回中 510 回を「正常」とした** | 探索あり: すぐ収束（中央値 0.066 m） |
| 走行中に 2.8 m・30 度ずれた初期化 | 11.2 s で収束。その間、誤差 0.5 m 超の 92 回中 86 回を「正常」とした | （評価の道具の不備で未確認） |
| 1 scan の処理（中央値 / 95 % 点） | 55 / 84 ms | 33 / 55 ms |
| CPU / メモリ（VM） | 141 % / 1.37 GB | NDT 57 % / 205 MB（周囲の地図だけを読み込む） |
| 等倍の再生 | 毎秒 8.3 回（一部取りこぼし） | 毎秒 9.9 回 |

合格基準（DEC-114）との照合:
- 95 % 点 0.3 m 以内: どちらも合格（同じ走行の地図）。
- 発散なし: A は 5 m・90 度のずれから収束しなかった。A3 は合格。
- 誤差 0.5 m 超で不良を出す: A は初期化の失敗の間ほとんど出さなかった。A3 は走行全体で 1 回見逃した。
- 厳密にはどちらも全項目の合格ではない。

試していないこと: A の大域の初期化（quickstart の機能で、Nav2 用の launch では無効）、A3 の調整（NDT の格子 1.0 m では score のしきい値の調整が要る）、別の走行の地図での評価（今のデータでは重なる走行がない）、x86 機での処理の余裕。

## 7. 推奨（2026-10-17、検証の後）

**第一候補を案 A3 に変えることを推奨する。最終の決定は、次の実機試験（同じ場所を 2 回）のデータで別の走行の地図での評価をしてから。**

理由:
- 精度は両方とも基準を満たし、A がやや良い（95 % 点 0.124 m 対 0.209 m）。
- 決め手は「推定を誤ったときの振る舞い」。
  - A は、初期姿勢が大きくずれると、誤った姿勢を「正常」として出し続けた。
  - A3 は、ずれていると姿勢を出さず（棄却）、Monte Carlo の初期姿勢の探索で 5 m・90 度のずれからも戻れた。
  - intent の「推定不能」を区別する要求（IF-010）と、人が初期位置を「ある程度」指定する運用（体験 9）に、A3 の方が合う。
- 処理も軽い（周囲の地図だけを読み込み、1 scan の処理が短い）。

A3 で残る課題（実装の前に決める）:
1. 誤差 0.5 m を超えた跳ねを 1 回見逃した。対策の案は (a) NDT の設定の調整、(b) EKF の診断（マハラノビス距離、共分散）を「推定不能」の判定に加える。
2. 組み込みに要る部品（いずれも独自の小さな node か設定）:
   - 点群の間引き（評価では C++ の小さな node）
   - 速度の中継（GLIM の odometry から）
   - map→odom の中継（EKF の TF は別の topic へ remap）
   - 地図の 20 m 格子への分割（地図の変換の仕事）
   - 初期化の手順（初期姿勢 → Monte Carlo の探索 → EKF・NDT の有効化）
3. 依存が多い（Autoware の apt のパッケージ）。版を固定する。

案 A を残す場合の条件: 大域の初期化を有効にして、5 m・90 度のずれからの回復を確かめる。

monitor での切り替え（§10）: 今は作らない。比べるのはオフラインで足りる（同じ rosbag を両方に通せる）。別の走行の地図での評価で、両方に違う苦手な場面が見つかったときに改めて判断する。

## 8. 出典（2026-10-17 に読んだページ）

- GLIM:
  - [koide3/glim](https://github.com/koide3/glim)、[docs](https://koide3.github.io/glim/)、[config_ros.json](https://github.com/koide3/glim/blob/master/config/config_ros.json)
  - [trajectory_manager.hpp](https://github.com/koide3/glim/blob/master/include/glim/util/trajectory_manager.hpp)・[.cpp](https://github.com/koide3/glim/blob/master/src/glim/util/trajectory_manager.cpp)
  - [koide3/glim_ros2](https://github.com/koide3/glim_ros2)（glim_ros.cpp、rviz_viewer.cpp・.hpp、package.xml、CI）
- 案 A: [rsasaki0109/lidar_localization_ros2](https://github.com/rsasaki0109/lidar_localization_ros2)（README、docs の frame_contract・troubleshooting・pose_covariance・v1_status・quickstart・local_build、param/nav2_ndt_urban.yaml、launch の nav2_navigation・nav2_lidar_localization、package.xml、CHANGELOG、tags）、[ndt_omp_ros2](https://github.com/rsasaki0109/ndt_omp_ros2)
- 案 A3:
  - [autoware_core の localization](https://github.com/autowarefoundation/autoware_core/tree/main/localization)
  - autoware_ndt_scan_matcher の [README](https://github.com/autowarefoundation/autoware_core/blob/main/localization/autoware_ndt_scan_matcher/README.md)・[package.xml](https://github.com/autowarefoundation/autoware_core/blob/main/localization/autoware_ndt_scan_matcher/package.xml)
  - autoware_ekf_localizer の [README](https://github.com/autowarefoundation/autoware_core/blob/main/localization/autoware_ekf_localizer/README.md)・[schema](https://github.com/autowarefoundation/autoware_core/tree/main/localization/autoware_ekf_localizer/schema)
  - ROS Index の [autoware_ndt_scan_matcher](https://index.ros.org/p/autoware_ndt_scan_matcher/)・[autoware_ekf_localizer](https://index.ros.org/p/autoware_ekf_localizer/)、[Humble から Jazzy への移行の予定](https://docs.autoware.org/main/home/roadmap/timelines/humble-jazzy/)
- 案 B: [nav2_amcl（jazzy）](https://github.com/ros-navigation/navigation2/tree/jazzy/nav2_amcl)（README、package.xml、amcl_node.hpp・.cpp、plugins.xml）、[pointcloud_to_laserscan](https://index.ros.org/p/pointcloud_to_laserscan/)、手元の `design/research/upstream_jazzy/nav2_bringup/params/nav2_params.yaml`。docs.nav2.org の設定のページは 404。
- 検討から外したもの（付録）: [Cartographer](https://github.com/cartographer-project/cartographer)・[ros2/cartographer_ros](https://github.com/ros2/cartographer_ros)・[文書](https://google-cartographer-ros.readthedocs.io/en/latest/)、[LeGO-LOAM](https://github.com/RobustFieldAutonomyLab/LeGO-LOAM)・[LeGO-LOAM-SR](https://github.com/eperdices/LeGO-LOAM-SR)、[Autoware.AI core_perception](https://github.com/Autoware-AI/core_perception)、[hdl_localization](https://github.com/koide3/hdl_localization)、[FAST_LIO](https://github.com/hku-mars/FAST_LIO)、[KISS-ICP](https://github.com/PRBonn/kiss-icp)、[emcl2_ros2](https://github.com/ryuichiueda/emcl2_ros2)

## 9. 承認していただきたいこと（個別。2026-10-17 の検証の後）

1. 第一候補を案 A3 に変えてよいか（最終の決定は別の走行の地図での評価の後）。
2. 案 A3 で残る課題 1（0.5 m 超の跳ねの見逃し）の対策の進め方（設定の調整か、EKF の診断を「推定不能」の判定に加えるか）。
3. 次の実機試験の段取り: 同じ場所を 2 回（1 回目は地図作成と rosbag、2 回目は rosbag だけ）。2 回とも、出発の前に止まった状態を 10 秒以上作る（初期化の試験に使う）。
4. VM の Gouda の試験の環境に、Fast DDS の共有メモリの設定（評価で使った fastdds_eval.xml と同じもの）を入れるか（G-DDS の対策。設定の変更なので承認事項）。
5. 実装の段階で要る独自の小さな node（§7 の 2）を、方式の採用と合わせて承認事項にする。今は予告だけ。

これまでの回答: 進め方（A と A3 を重点）・評価の場所（VM）・合格基準・同じ場所を 2 回は DEC-114。「Nav2 に機能を持たせ」の読みは intent 第10版（DEC-113）。

## 10. 両方の node を用意して gouda_monitor で切り替える案（DEC-114 で人が示した案）

案: A と A3 の両方を入れておき、人が monitor で使う方を選ぶ。

利点:
- 同じ日・同じ地図で、実車の上で比べられる。
- 一方が苦手な場所が見つかったとき、コードを変えずにもう一方に替えられる（本番の保険）。

注意点・手間:
1. **TF の持ち主は常に一つ**（intent・D-17）。
   - 切り替えは手動走行・一時停止の間だけにし、自律走行の最中は替えない。
   - 使わない方は止めておく。A は lifecycle の node。Autoware の node は起動・停止のサービス（trigger_node）を持つ。中継の node は Gouda の側で止められる。
   - 二つが同時に map→odom を出さないことを試験で確かめる。
2. **組み込みと調整が二重になる**: A3 は中継 2 つと EKF の TF の付け替えが要る。両方とも合格の試験（TS）を通す必要がある。
3. **intent の「使う予定のない汎用化はしない」**: 両方を実際に使う理由がある場合に限って正当になる。
4. **起動の方法は増やさない（DEC-090）**: 選択は gouda.sh の引数ではなく、monitor の設定（/config と同じく残る設定）にする。
5. **記録**: どちらで走ったかを DecisionEvent と manifest に残す（デバッグ性）。

比べるだけなら、切り替えは要らない:
- 同じ rosbag を両方に通すオフラインの比較（§6）の方が、入力が同じで公平。
- 実車の上での切り替えは、主に「本番の保険」として意味がある。

AI の推奨（オフラインの検証の結果で決める）:
- 両方が合格し差が小さい → 一方を本採用にし、もう一方はオフラインの比較の道具として残す（簡単さを優先）。
- それぞれ違う場面で失敗する → 切り替えを作る。条件は上の 1・4・5。
- 実装は人の個別の許可（DEC-106）の後。

## 付録: 検討から外した候補と理由

| 候補 | 理由 |
|---|---|
| KISS-ICP | 人の判断（DEC-112）: 以前の評価試験で目標性能を出せなかった |
| Cartographer | DEC-112 の検討の範囲外。自身の地図（.pbstream）でしか自己位置推定できず地図作成も置き換えになる、上流の保守終了、品質の出力なし、点の時刻の形式が合わない（REV-052） |
| LeGO-LOAM | ROS 1 だけ（最後の更新 2020 年）。保存地図での自己位置推定なし。ROS 2 への移植は Dashing で IMU なし（REV-053） |
| Autoware.AI の ndt_matching | ROS 1 だけで、Autoware.AI は終了（2023-03 に archive）。後継を案 A3 とした（REV-053） |
| hdl_localization | ROS 1 だけ |
| FAST_LIO | DEC-112 の検討の範囲外（ROS 2 版の Jazzy は未確認） |
| emcl2_ros2 | DEC-112 の検討の範囲外（2D。Jazzy は未確認） |
