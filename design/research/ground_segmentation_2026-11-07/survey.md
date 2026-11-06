# 走行中の地面分割の OSS の調査（G1、issue #85）

- 日付：2026-11-07。読んだコミット：9c449b5（作業木は共有で、他の流れの未コミットの変更がある。`gouda_core/gouda_core/nav2_config.py` は読む間にも行番号が動いたので、関数名で示す）
- 人の指示（原文）：「地面はRANSAC等を用いたOSSを使って検出しよう。閾値設定だけでは障害物がないのにあると誤検知してしまうかもしれません。」
- 許可：DEC-475（`design/revisions/REV-259.yaml`）の G1（調査）。G3（製品への組み込み）は含まない。G2 の結果の後の承認事項
- 状態：**提案**（AI の調査。承認済みの仕様ではない。この文書の案を参照・生成・実装に使わない。CLAUDE.md 1.7）
- 方法：GitHub の原本を `gh api`・`gh search` で、文書と Discourse を WebFetch で、apt の有無を packages.ros.org の pool の一覧で、pip の有無を PyPI の JSON で読んだ。ビルド・起動・rosbag の再生は**未実行**
- 書き方：【事実】読んだ原本と場所。【計算】事実からの計算。【推測】確かめていない考え。【未確認】調べていない、または分からなかったこと

## 1. 今の経路（リポジトリで確かめた事実）

- XT-32 の点群を上流の pointcloud_to_laserscan（node `xt32_scan`）で base_link の高さの帯で切り、LaserScan（IFD-57）にして ObstacleLayer の印と消去に使う。帯は PRM-70 −0.065 m・PRM-71 1.085 m（承認済み、`design/model.yaml` の PRM-70・71）。scan は `inf_is_valid: true`（`nav2_config.py` の `scan_parameters`・`_scan_observation`、REV-185）
- MID-360 は別の層 `mid360_layer`。印は `mid360_scan`（同じ帯）、消去は MID-360 の生の点（`sensor_frame: mid360_link`）（`nav2_config.py` の `add_mid360`、ND-21、REV-242）
- 【計算】base_link は地面から約 0.165 m（`design/intent.md:107`）なので、帯の下限は地面から約 0.10 m
- 印・消去の距離は PRM-125・126 が未決のため、Nav2 のテンプレートの 2.5 m・3.0 m（`design/research/upstream_jazzy/nav2_bringup/params/nav2_params.yaml:221-223`）
- MID-360：50° 下向き（DEC-424）、高さは 800 mm か 500 mm の候補（DEC-425）、取付の値は実測待ちで、値が入るまで経路を起動しない（DEC-457）。DEC-425 の計算：前方の地面が見え始めるのは取付点から 0.32 m（500 mm）・0.52 m（800 mm）、横は 1.23 m・1.98 m、後方の地面は見えない、光線の約 29 % が車体の箱に当たる
- XT-32：地面から 1.182 m。地面が見え始めるのは 4.0〜4.2 m、1 通 64000 点、600 rpm（`design/docs/lidar_xt32_spec.md:10,17,54`、#73）
- GLIM の map・odom の z は、開始時の IMU の重力の向きから（`gouda_core/gouda_core/localization_core.py:237`）。開始時の傾きがずれた例（4.15°）が REV-048 の未解決の項目にある（`design/model.yaml:44517` 付近）
- ドライバの点群の publisher は reliable・depth 10（`design/research/upstream_sensors/hesai_ros2_e7e112f/source_driver_ros2.hpp:131`、`livox_ros_driver2_2144554/lddc.cpp:532`）。pointcloud_to_laserscan（jazzy の枝）は SensorDataQoS で受ける（上流 `src/pointcloud_to_laserscan_node.cpp:121-123`）

## 2. 候補の比較

### 2.1 配布・保守

| 候補 | ライセンス（本文で確認） | ROS 2 Jazzy | apt `ros-jazzy-*` | 最後の commit | 主な依存 |
|---|---|---|---|---|---|
| Patchwork++ ROS 2（url-kaist/patchwork-plusplus の `ros/`、package `patchworkpp`） | 根の `LICENSE` は BSD-2-Clause（2024-12-13 の 1bf9dd1 で GPL-3.0 から変更）。`ros/LICENSE` は MIT（KISS-ICP の著者）。`ros/package.xml` は `GPL-3.0`（2024-04-15 の fe276b7 のまま）。**表示が食い違う** | CI（`.github/workflows/ros.yml`）が `osrf/ros:{humble,jazzy}-desktop` で colcon build。master 3e6903a の run（2026-05-23）は jazzy・humble とも success。README の badge は Humble | なし（pool に `ros-jazzy-patchworkpp` なし、rosdistro jazzy（89956d4、2026-11-06）にも記載なし） | 3e6903a、2026-05-23（v1.4.1） | Eigen（既定 `USE_SYSTEM_EIGEN3 OFF` で gitlab から 3.4.0 を build 時に取得：`cpp/cmake/eigen.cmake`）、TBB は任意、C++20。ROS 側は rclcpp・rclcpp_components・tf2_ros ほか |
| pypatchworkpp（同じ core の pip 版） | PyPI の license 欄は空 | — | —（PyPI 1.4.1、2026-05-23。cp312 の manylinux x86_64 の wheel あり。Linux aarch64 の wheel なし） | 同上 | numpy |
| linefit ROS 2（baiyeweiguang/linefit_ground_segmentation_ros2。KBKN-Autonomous-Robotics-Lab の同名はその fork） | BSD-3-Clause（2017 Lorenz Wellhausen） | distro の記載なし。CI なし | なし | 移植の元：5b8a5ae、2026-08-19（`r_max` の型の修正、issue #2・#3）。KBKN の fork：e20e73b、2023-11-13（この修正を含まない）。上流 lorenwel：e6b9418、2022-12-21（ROS 1。ROS 2 への移植の issue #53 は open） | PCL・pcl_ros・pcl_conversions・Eigen・tf2_ros。`package.xml` に ROS 1 の `eigen_conversions`（Jazzy の rosdistro にない） |
| GSeg3D（dfki-ric/ground_segmentation、dfki-ric/ground_segmentation_ros2） | BSD-3-Clause（両方） | README：Humble・Jazzy。CI（`build.yml`）が jazzy・lyrical・rolling で build と test、master c0d60fd（2026-09-03）の run は 3 つとも success | なし（core は ROS index に出ていないと CI の注記） | ros2：c0d60fd、2026-09-03。core：e5aa4c2、2026-09-02。公開 2026-02-20 | PCL、Eigen、nanoflann、message_filters、tf2_eigen |
| Nav2 Ground Consistency Layer（dfki-ric/nav2_ground_consistency_costmap_plugin） | BSD-3-Clause | docs.nav2.org の jazzy の枝の plugin 一覧（`docs/configuration_and_development/navigation_plugins.md:49`）と tutorial（要件「ROS 2 Jazzy」、line 17）。`main` が Jazzy 向け、`rolling` の枝は rolling 向け（1bcb685）。CI なし | なし | 41cec62、2026-05-15（作成 2026-03-26） | nav2_costmap_2d、pluginlib、tf2 |
| Autoware `autoware_ground_filter`（autoware_core） | Apache-2.0（`package.xml`） | rosdistro jazzy に autoware_core 1.9.0-1 | **あり**：`ros-jazzy-autoware-ground-filter` 1.9.0（amd64・arm64、2026-09-16 の build） | 762319d、2026-09-28（1.10.0） | autoware_utils_*・autoware_vehicle_info_utils・autoware_point_types・pcl_ros ほか（どれも jazzy の rosdistro にある） |
| Autoware `autoware_ground_segmentation`（autoware_universe。ransac・ray・scan） | 未確認 | 未確認 | rosdistro jazzy に記載なし | 未確認 | 未確認（monorepo からの切り出し） |
| TRAVEL（url-kaist/TRAVEL） | GPL-3.0-or-later | CI に humble・jazzy の ROS 2 build | なし | 95dc2fb、2026-05-19 | PCL、Eigen |
| GroundGrid（dcmlr/groundgrid の `ros2-jazzy` の枝） | BSD-3-Clause | 枝の名と README が Jazzy | なし | ab0f093、2026-03-21 | grid_map 一式、velodyne_pointcloud、cv_bridge、tf_transformations |
| 部品：pcl_ros の CropBox（perception_pcl の jazzy の枝） | 未確認（本文を読んでいない） | jazzy の枝、rosdistro 2.6.5-1 | **あり**：`ros-jazzy-pcl-ros` 2.6.5 | — | — |

### 2.2 入力の前提と出力

| 候補 | 入力の前提（frame・高さ・傾き・TF） | 出力 | 主な parameter（既定） | 範囲の外・近い点 |
|---|---|---|---|---|
| Patchwork++ ROS node | **TF を使わない**。入力の frame の z を上として、区画ごとの面の法線の z 成分を `uprightness_thr` と比べ、原点を中心に同心円の区画を作る（`cpp/patchworkpp/src/patchworkpp.cpp` の `estimateGround`・`pc2czm`）。地面は z ≈ −`sensor_height`。出力は `frame_id` を `base_frame` に**書き換えるだけで点は変換しない**（`ros/src/GroundSegmentationServer.cpp:151-160`） | `/patchworkpp/ground`・`/patchworkpp/nonground`・`/patchworkpp/cloud`（絶対名、remap で変える）。reliable・transient_local・depth 10（同:119-126）。入力は SensorDataQoS | `sensor_height` 1.723、`th_dist` 0.125、`th_seeds` 0.125、`uprightness_thr` 0.707、`min_range` 2.7、`max_range` 80、`num_min_pts` 10、区画は 4 つの帯（セクタ 16/32/54/32、リング 2/4/4/4）（`patchworkpp.h:81-120`）。ROS から変えられるのは一部（`GroundSegmentationServer.cpp:29-52`）。RNR は wrapper が無効にする。`USAGE.md` の既定値の記述（`uprightness_thr` 0.5、`th_seeds` 0.5）は header と食い違う | 水平の半径が `min_range` 以下・`max_range` 超の点は**すべて非地面**（`pc2czm`、patchworkpp.cpp:604,627）。近い 4 リングより外では、上向きの区画を高さを見ずに地面にする（`estimateGround` の `!is_near_zone`、同:280-281）。`sensor_height` は近いリングの地面の高さで更新し続ける（同:360） |
| linefit ROS 2 | `gravity_aligned_frame` を与えると TF の**回転だけ**を当てる（平行移動は消す。原点はセンサーのまま）。地面は z ≈ −`sensor_height`。TF が取れないと WARN を出し、回さない点群のまま分割する（`ground_segmentation_node.cc:101-128`）。lookupTransform は待ち時間なし | `ground_output_topic`・`obstacle_output_topic`（parameter、相対名）。点は元の frame・元の座標（同:131-145）。SensorDataQoS | `sensor_height`、`max_dist_to_line`、`max_slope`、`min_slope`、`max_fit_error`、`long_threshold`、`max_long_height`、`max_start_height`、`line_search_angle`、`r_min`、`r_max`、`n_bins`、`n_segments`、`n_threads`（`launch/segmentation_params.yaml`。移植の元の既定値は `sensor_height` 0.6、入力 topic `livox/lidar/pointcloud`） | `r_min`〜`r_max` の外の点は障害物（`ground_segmentation.cc` の `insertionThread` で bin なし→ラベル 0）。線は −`sensor_height` から `max_start_height` 以内でしか始まらない（`segment.cc:30,70`） |
| GSeg3D ROS 2 | `robot_frame` へ TF（平行移動を含む）で変換する。地面の高さ＝TF の z＋`lidar_to_ground`（符号つき）。`use_imu_orientation: true` なら sensor_msgs/Imu の orientation で重力に合わせ、false なら `robot_frame` の z を上とする（`src/ground_segmentation_ros2_node.cpp:164-238`）。TF が取れない通は捨てる | `/ground_segmentation/ground_points`・`obstacle_points`・`raw_points`（絶対名、depth 10）、frame は `robot_frame`（同:55-57,289-291）。入力は IMU なしなら depth 10 の reliable、IMU ありなら SensorDataQoS（同:59-77） | `robot_frame`、`lidar_to_ground`、`cellSizeX/Y/Z`、`cellSizeZPhase2`、`slopeThresholdDegrees`、`groundInlierThreshold`、`centroidSearchRadius`、`maxGroundHeightDeviation`、ROI、`downsample`、`transform_tolerance`（`config/parameters.yaml`、SemanticKITTI 用） | ロボットの下に合成の種の点を入れる（core の README）。PCL の SACSegmentation（PROSAC）で区画ごとに面を当てる（同） |
| Ground Consistency Layer | 地面・非地面の 2 本の PointCloud2 を TF で costmap の global frame に変換する。高さは global frame の z で、区画ごとの地面の点の平均との差 | costmap の層。**master の格子に直接書く**（`src/ground_consistency_layer.cpp` の `updateCosts`） | `ground_inc` 1.0、`nonground_inc` 1.5、`ground_decay` 0.80、`nonground_decay` 0.93、`nonground_occ_thresh` 6.0、`nonground_prob_thresh` 0.75、`min_clearance` 0.1、`robot_height` 1.2、`maximum_height_filter`、`max_data_range` 50、`discretize_costs` true、`ground_neighbor_search_cells` 0、`footprint_clearing_enabled` true（同 `declareParameter`） | 地面の情報がない区画で、非地面の証拠が閾値を超えると LETHAL（同、`updateBounds` の判定） |
| Autoware ground_filter | input_frame は base_link に固定が前提（`docs/ground-filter.md` の Known limits）。前輪の中心の地面に仮想の地面の点を置く（`use_virtual_ground_point`、vehicle_info の値が要る） | 非地面の点 | `global_slope_max_angle_deg` 10、`local_slope_max_angle_deg` 13、`split_height_distance` 0.2、`non_ground_height_threshold` 0.2、`grid_size_m` 0.5 ほか（`config/ground_filter.param.yaml`） | 未確認 |

【推測】Autoware の base_link は地面の上にある前提に見える。こちらの base_link は地面から約 0.165 m なので、そのままでは前提が合わない（確かめていない）。universe の RANSAC の filter は文書に「坂を扱えない」とある（`perception/autoware_ground_segmentation/docs/ransac-ground-filter.md:27`）。

人の指示の「RANSAC等」との対応：RANSAC 系で面を当てるのは GSeg3D（PROSAC、区画ごと）と Autoware universe の ransac（単一の面）。Patchwork++ は区画ごとの PCA の面、linefit は直線の当てはめ。

## 3. 実機での使用例（読んだ原本）

- **Patchwork++**
  - Open Navigation の honeybee（open-navigation/opennav_amd_demonstrations、Apache-2.0）：Ouster の点群を `patchworkpp_node` に入れ（`base_frame` はセンサーの frame `os0_lidar`、`sensor_height` 0.495、`min_range` 0.0、`max_range` 20）、非地面を Nav2 の NonPersistentVoxelLayer の源にする（`min_obstacle_height` 0.254 を残す）（`honeybee_bringup/config/ouster.yaml`、`honeybee_nav2/config/nav2_gps_params.yaml`）
  - WHILL（電動車椅子）の Iruazu/whill_lab0_ros2（ライセンスの表示なし）：VLP-16 → Patchwork++ の C++ core を自作の wrapper で包む → pointcloud_to_laserscan → obstacle_layer。`docs/decisions/0011-ground-removal-choice.md` の記録：base_link の帯では 5° 前後の坂と路面の凸凹が lethal になった（2026-07-14 の屋外の実測）、上流の `ros/` のライセンスの表示の食い違いを理由に wrapper を自作、bag の再生で 1 通 1.6〜2.7 ms（約 2.9 万点）、core は RNR を有効にすると intensity がない点群を捨てる（エラーが出ない落とし穴）。走行での判定（同 AC4）は未確定と書かれている
  - MID-360：上流の `USAGE.md` に「四足歩行の MID-360 で `sensor_height` 0.3〜0.6 m」という目安があるだけ。傾けた MID-360 での例は見つからなかった
- **linefit**：KBKN（法政大 orange。README につくばチャレンジと IGVC）の orange2026A。`orange_ros2.rosinstall` に KBKN の fork（main）、`orange_sensor_tools/config/ground_segmentation.yaml`（`sensor_height` 1.45、`gravity_aligned_frame: livox_frame`、`r_min` 0.90）。シミュレーションの launch（orange_ros2 の `livox_to_pointcloud2_laserscan_simulation.launch.py`）は非地面 → pointcloud_to_laserscan → `/livox_scan`。**実機の launch**（orange2026A の `livox_to_pointcloud2_laserscan.launch.py`）は `/pcd_segment_obs`（`pcd_convert` の高さの帯による分割。坂の区間は waypoint の番号で閾値を切り替える）を scan にしている。本番の走行で linefit を使ったかは未確認
- **GSeg3D**：DFKI の Arter（掘削機）、BotanicGarden・Citrus-Farm の記録（Ground Consistency Layer の README）。ROS Discourse（https://discourse.openrobotics.org/t/new-release-ground-segmentation-library-ros-2-integration/52601 、2026-02-28 の返信）：屋外の MID-360 の記録で概ね良いが、高さ約 1 m の茂みを通れる地面とすることがあり、そこで出力がちらつく、という報告。作者は parameter（cell の大きさ、`maxGroundHeightDeviation`）を疑い記録を求めた（2026-03-01）。解決の記録はない。**#85 の「茂みを通れると判定」は誤検知ではなく見落とし（障害物を地面にした）の例**
- **Ground Consistency Layer**：上記の DFKI の例と、Nav2 の tutorial（Gazebo の Husky、`navigation2_tutorials` の jazzy の枝の `nav2_lidar_ground_segmentation_demo`、f3bd892、2026-05-15）。tutorial は GSeg3D と組み、局所の costmap に層を置き、global は非地面の点を ObstacleLayer に入れる（同 `config/nav2_config.yaml`）。依存は `dependencies.repos` で GSeg3D は `master`、層は `main`（commit の固定なし）
- **つくばチャレンジ**：KBKN の linefit（上記）のほかは見つからなかった（GitHub の code search で `patchworkpp_node`・`linefit` を検索。検索は網羅的でない）

## 4. 組み込みの形の案（G3 の判断の材料。提案）

### 4.1 「点群 →（変換）→ 地面分割 → 非地面の点 → 今の帯の scan → ObstacleLayer の印」でよいか

- よい点
  - costmap の層の組み方（REV-185・REV-242、DEC-216・DEC-336・DEC-454）を変えず、印の元だけが変わる
  - 帯は残るので、分割の後の点にも PRM-70・71 がかかる（二重の網）。印になるのは「分割で非地面」かつ「帯の中」の点
  - 同じ順の例がある（WHILL、KBKN のシミュレーション、Open Navigation は帯の代わりに Nav2 の高さの範囲）
- 傾いたセンサーの扱い（候補で違う）
  - Patchwork++：前段で z が上の frame へ変換が要る。部品は pcl_ros の `filter_crop_box_node`（apt にある。`input_frame`・`output_frame` で TF 変換し、箱で車体の点を除ける。perception_pcl jazzy の `pcl_ros/src/pcl_ros/filters/filter.cpp` の `computePublish`・`use_frame_params`、`pcl_ros/CMakeLists.txt:126-128`）。変換に失敗した通は捨てる（`computePublish`）
  - linefit：`gravity_aligned_frame` で自分で回す。GSeg3D：`robot_frame` で自分で変換する
- どの frame に変換するか
  - 案 a（推奨、提案）：**base_link**。静的な TF だけで済み、新しい frame はいらない。センサーの 50° は除ける。坂の上の車体の傾きは残るが、Patchwork++ は区画ごとに面を当てて法線が `uprightness_thr`（0.707＝45°）以内なら地面にするので、数度の傾きは区画の面として扱われる見込み【推測】。原点が後輪軸になり、同心円の区画の中心がセンサーとずれる（影響は未確認）。`sensor_height` は「原点の地面からの高さ」の意味になり約 0.165 m【推測】
  - 案 b：重力に沿った frame（odom の z）。linefit は `gravity_aligned_frame: odom` で回転だけを当てられる（ただし動的な TF なので、待ち時間なしの lookupTransform が失敗すると回さずに分割する）。Patchwork++ には、センサーの位置で odom の向きの frame を出す node が要る（上流にない＝自作。同じ TF を複数から出さない：`intent.md:90`）。GLIM の開始時の傾きの誤差がそのまま入る。IMU で補う #80 は未承認
- 設定の落とし穴
  - Patchwork++ の `base_frame` は入力の frame と同じ名前にする（違うと点は動かず名前だけ変わる）
  - 出力の topic は絶対名（Patchwork++・GSeg3D）。XT-32 と MID-360 の両方に使うなら node 名と remap を分ける
  - 時刻：3 つとも入力の stamp を残すので、pointcloud_to_laserscan の TF の照合は今と同じ
  - QoS：driver（reliable）→ CropBox → Patchwork++（SensorDataQoS で受け、reliable・transient_local で出す）→ pointcloud_to_laserscan（SensorDataQoS）は、受ける側が best effort なので繋がる見込み【推測】。GSeg3D は IMU なしだと reliable で受けるので、best effort の publisher とは繋がらない（CropBox の出力の QoS は未確認）

### 4.2 消去に地面の点を使えるか

- MID-360 の層は、すでに生の点（地面の点を含む）で消している（`add_mid360` の `mid_clear`）。地面の点だけを別の消去の源に足しても、新しく消える所はない【推測】。案：消去は今のまま
- 【推測】ObstacleLayer の消去は高さを見ない 2D の光線なので、下向きの光線が低い物の上を通って遠くの地面に届くと、その物の区画を消す。50° 下向きの MID-360 で起こりやすい。今もある性質で、地面分割では変わらない（VoxelLayer の 3D の光線や Ground Consistency Layer との違い）
- XT-32 の scan は `inf_is_valid: true` で、帯に点がない方位は raytrace の範囲まで消す（`_scan_observation`、DEC-322）。分割を入れると、地面とされた点の方位は inf になって消去に回る。地面の誤検知は消えるが、**地面と誤判定された低い物の方位も消去に回る**【推測】

### 4.3 Ground Consistency Layer に置き換える場合との違い

| 観点 | 分割＋帯の scan＋ObstacleLayer | Ground Consistency Layer |
|---|---|---|
| 高さの基準 | base_link の帯（PRM-70・71） | 区画ごとの地面の点の平均からの差（global frame の z）。坂でも相対の高さ |
| 印の出し方 | 1 回の観測で印 | 証拠を積む。`nonground_occ_thresh` 6.0 は約 4 回の観測（tutorial の説明）。印が遅れる |
| 消去 | 光線 | 光線なし。地面の証拠と減衰（costmap の更新の周期ごと、点が来た周期だけ） |
| master への書き方 | 層ごとの格子を combination_method でまとめる（global は 2、DEC-216） | master の格子に直接書く。前の層の印を FREE で上書きしうるので、層の順序が効く |
| 地面が見えない所 | 帯の中の点は印 | 非地面の証拠が足りれば LETHAL |
| 置き場 | local・global | local を推奨（README・tutorial） |
| 変える範囲 | 前段の node の追加だけ | 承認済みの層の設計（DEC-216・DEC-336・DEC-454）の見直し |

案：今回は置き換えない。G2 の後に別の案として比べる（提案）。人の地図の地面の方針（DEC-108、`design/model.yaml:61485`）の「局所地面からの相対高さで判定」は、この層の考え方に近い。

### 4.4 XT-32 にも使うか

- 【計算】平らな所では XT-32 の地面は 4.0〜4.2 m から。今の印の距離は 2.5 m（PRM-125 未決のためテンプレートの値）なので、XT-32 の地面の点は印の範囲に入らない。2.5 m 以内に地面が入るのは、車体が約 9° 前に傾いた時（atan(1.182/2.5)＝25.3°、一番下のビーム 15.98° との差）。2 m 先から 10 % の上り坂でも、ビームが地面に当たるのは約 3.6 m
- 【推測】XT-32 に分割を入れる効果は、PRM-125 を 4 m より大きくする時に出る。案：MID-360 に先に入れ、XT-32 は PRM-125 の決定と合わせて G2 で比べる
- XT-32 は 1 通 64000 点で、MID-360 より負荷が大きい

### 4.5 必要な parameter と実測

| 項目 | 候補 | 決め方 | 実測 |
|---|---|---|---|
| MID-360 の取付（x・y・z・roll・pitch・yaw）→ TF | 全部 | DEC-457 | 要（実測待ち） |
| `sensor_height`・`lidar_to_ground` | Patchwork++（案 a なら約 0.165 m の意味）、linefit（取付の高さ。誤差は `max_start_height` 以内が要る）、GSeg3D（TF の z と符号つき） | 取付の値から計算 | 要（取付） |
| `min_range`・`r_min` | Patchwork++、linefit | 一番近い地面の点の半径と、車体の点の範囲を rosbag（T04・T08）で測る | 要 |
| 地面の厚み（`th_dist`・`max_dist_to_line`・`groundInlierThreshold`） | 全部 | 平らな所の地面の点の面からの散らばりと、低い物の見落としの釣り合い（G2） | 要（記録から） |
| 坂の上限（`uprightness_thr`・`max_slope`・`slopeThresholdDegrees`） | 全部 | コースの最大の勾配 | 要（未測定） |
| 検出したい一番低い物の高さ | — | #32、PRM-70。人が決める | 判断 |
| 車体の箱（CropBox） | Patchwork++ の前段 | 全長 800×全幅 600×全高 1250 mm（`intent.md:107`）と取付具 | 一部（取付具は未確認） |
| `max_range` | Patchwork++ | PRM-126 と合わせる（WHILL の考え方） | 設計 |
| CPU・遅れ | 全部 | ワークステーションと車載 PC で測る | 要 |
| （層を使うなら）`robot_height`・`min_clearance`・減衰 | Ground Consistency Layer | 全高（`intent.md:107`）、減衰は更新周波数に依存 | 一部 |

未決の値はすべて `tbd`。推測や一般の値で埋めない（CLAUDE.md 1.5）。

## 5. 推奨とその理由（提案）

- **G2 で比べる組**（MID-360 を先に）：(0) 帯だけ（今）、(1) Patchwork++＋帯、(2) GSeg3D＋帯、(3) linefit＋帯（手間が小さければ）。Patchwork++ は pip の pypatchworkpp（同じ core、cp312 x86_64 の wheel）で、ビルドなしに解析スクリプトから回せる。ただし ROS の wrapper の設定（RNR 無効など）を合わせる
- **G3 の第一候補**（今の材料で）：Patchwork++ の上流の ROS node（commit 3e6903a に固定、変更なし）＋前段に pcl_ros の CropBox（base_link へ変換、車体の点を除く）＋今の帯の scan＋今の ObstacleLayer
  - 保守と Jazzy：2026-05 に v1.4.1、CI で jazzy の build が success
  - 実績：利用が多い（1131 stars）。Nav2 での例（Open Navigation）、電動車椅子での同じ形の例（WHILL）
  - 閾値を走りながら更新する（`sensor_height`・高さ・平らさ）ので、取付の値の誤差に linefit より強い見込み【推測】
  - costmap の層の設計（DEC-216・DEC-336・DEC-454）を変えない
  - 弱み：TF を使わないので前段の node が要る、`ros/` のライセンスの表示の食い違い（人の判断）、近い点は非地面、遠い上向きの区画は高さを見ずに地面、Eigen を build 時に取得する
- **第二候補**：GSeg3D。TF と IMU の重力を自分で扱い、RANSAC 系（PROSAC）で面を当てる（指示の「RANSAC等」に字義どおり合う）。ライセンスは一貫し、CI は jazzy で success。弱み：公開から約 9 か月、MID-360 で約 1 m の茂みを地面にした報告（見落とし）、既定値は KITTI 用、区画は 1 m 角
  - Patchwork++ の `ros/package.xml` の GPL-3.0 を人が有効とみなす場合は、GSeg3D を第一にする。WHILL のように core だけを使う自作の wrapper は、上流を変えずに使う方針（DEC-075）と CLAUDE.md 1.11 に照らして承認事項
- **今回は採らない**
  - Ground Consistency Layer：4.3 のとおり、承認済みの層の設計の見直しになる
  - Autoware ground_filter：apt はあるが、base_link が地面にある前提と vehicle_info が要り、Autoware の他の物を使っていない
  - TRAVEL（GPL-3.0-or-later）、Patchwork2（url-kaist/Patchwork2、AGPL-3.0。ROS 2 は未確認）
  - GroundGrid の ROS 2 版：frame の名前（`odom`・`base_link`・`velodyne`）を固定で使い（`src/GroundGridNode.cpp:223-330`）、データセット向け
  - PCL の RANSAC で自作：単一の面は坂に弱い（Autoware の文書、WHILL の ADR の代替 D）。CLAUDE.md 1.11

## 6. 考慮が漏れやすい点（CLAUDE.md 1.12）

1. **低い物の見落とし**（いちばん重い）
   - 分割の厚み（Patchwork++ `th_dist` 0.125 m、GSeg3D `groundInlierThreshold` 0.2 m（KITTI 用）、Autoware `non_ground_height_threshold` 0.2 m）より低い物は地面にされうる。今の帯の下限は地面から約 0.10 m。見落としは「分割」と「帯」のどちらでも起きる
   - Patchwork++ は近い 4 リングより外で、上向きの区画を高さを見ずに地面にする。【計算】区画の境は `min_range`・`max_range` で決まる（`patchworkpp.h:129-140`）。例：0.3 m・20 m なら、4 リングの外は約 4.0 m から
   - XT-32 は地面と誤判定された点の方位が inf になり、消去に回る（4.2）
   - 縁石・コーン・#32 の低い物を G2 で数える。人は地図の地面の推定で「障害物を地面と誤判定する率」を最優先にした（DEC-108）。走行中にも同じにするかは人が決める
   - 下りの段差・側溝（負の障害物）は、帯でも分割でも検出しない。今もある穴
2. **坂・段差**：上限を超える坂は障害物になる。縁石の上の歩道（多層の地面）を MID-360 で確かめた例はない
3. **車体の傾き**：案 a では坂の上で base_link が重力に沿わない。分割で地面を除けば帯の下限の影響は小さくなるが、帯の上限（1.085 m）付近の判定は今と同じ
4. **CPU と遅れ**：MID-360 の 1 通の点数は原本で未確認、XT-32 は 64000 点。Patchwork++ は KITTI の HDL-64E で単一の thread で約 110 Hz（上流のコメント、`patchworkpp.cpp:217-225`）、WHILL の VLP-16 で 1 通 1.6〜2.7 ms。車載 PC では未測定。node が 1〜2 本増え、点群のコピーも増える。遅れは印の遅れになる
5. **取付の値の誤差**：linefit は `sensor_height` の誤差が `max_start_height` を超えると線が始まらず、ほぼ全部が障害物になる（`segment.cc:30,70`）。Patchwork++ は高さを更新するが、pitch の誤差は面の傾きとして残る。【計算】高さ 0.8 m の MID-360 で pitch の誤差 2.3° なら、2.5 m 先の地面は 0.10 m ずれ、今の帯の下限を超える
6. **近距離の死角と範囲の外**：`min_range`・`r_min` 以下の点は非地面になる。大きくすると近い地面が障害物になる。MID-360 の近い地面は取付点から 0.32〜0.52 m（DEC-425）。車体に当たる点（光線の約 29 %）は分割の前に除く方がよい【推測】
7. **TF の失敗**：linefit は回さない点群で分割を続ける（WARN だけ）。GSeg3D と CropBox はその通を捨てる。捨てた通が続くと印が古くなる
8. **状態を持つ**：Patchwork++ は過去の通の高さ・平らさを溜めて閾値を変える（`max_elevation_storage` 1000）。再起動で振る舞いが変わる。G2 では同じ rosbag を同じ順で流し、node を毎回新しく起動する
9. **ログの量**：linefit の core は毎通 stdout に処理時間を出す（`ground_segmentation.cc` の `segment`）。Patchwork++ の `verbose`
10. **点の密度**：MID-360 の非反復の走査で区画の点の数が変わる（GSeg3D の作者のコメント）。Patchwork++ は点が `num_min_pts` 未満の区画を非地面にする（ROS の launch の例は 0）
11. **反射・雨・濡れた路面**：DEC-108 の場面の一覧にある。G2 の記録に含まれるかは未確認
12. **ライセンス**：Patchwork++ の `ros/` の表示の食い違い。どう扱うかは人が判断する
13. **検査違反 0 件は安全の証明ではない**（CLAUDE.md 1.4）。分割は誤検知を減らす一方で見落としを増やしうる。ND-21 は safety の印。入れるかは人が判断する（G3）

## 7. 次の段階でワークステーションでビルドして確かめること（この流れでは未実行）

1. Patchwork++（3e6903a）：Jazzy で `colcon build --packages-select patchworkpp`。`-DUSE_SYSTEM_EIGEN3=ON` で網からの取得なしに通るか。C++20 の警告。`cpp/`・`python/` の `COLCON_IGNORE` で `ros/` だけが build されるか
2. pcl_ros の `filter_crop_box_node`（apt 2.6.5）：MID-360 の rosbag（T04・T08）の `/tf_static` で base_link への変換と車体の箱の除去ができるか、出力の QoS、遅れ
3. Patchwork++ に base_link の点群を入れ、`sensor_height`・`min_range`・`max_range` を変えて、地面・非地面の数、1 通の時間、更新される `sensor_height` を見る（案 a と案 b の比較を含む）
4. QoS の組み合わせ（driver → CropBox → patchworkpp → pointcloud_to_laserscan → costmap）が全部繋がるか（`ros2 topic info -v`）
5. GSeg3D：rosdep（nanoflann）と build、`robot_frame: base_link` で動くか。IMU の option は orientation が要る。今の IMU の経路が orientation を出すかは、`design/docs/imu_adis16607_spec.md` とドライバで確かめる（CLAUDE.md 1.13。未確認）
6. linefit（baiyeweiguang 5b8a5ae）：rosdep が `eigen_conversions` で止まるか、build が通るか、静的な TF で TF の失敗が出ないか
7. 決定性：同じ rosbag を 2 回流して出力が同じか（G2 の前提）
8. ドライバの点の形：XT-32 の返りのない点の表し方（NaN か 0 か）、MID-360 の点の型で x・y・z が読めるか
9. CPU と遅れ：1 通の処理時間、点群の stamp から scan の publish までの遅れ（XT-32 の 64000 点も）
10. G3 の前：gouda_sim で「帯だけ」と「分割＋帯」の costmap の印を比べる（コードと launch の変更は人の yes が要る。DEC-106）
11. Ground Consistency Layer を試すなら：`main` を Nav2 1.3.13 で build し、層の順序で XT-32 の印を上書きしないか

## 8. #85 の下書きとの差分（原本で埋めた・直した所）

- Patchwork++：ライセンスは根が BSD-2-Clause（本文で確認）だが、`ros/LICENSE` は MIT、`ros/package.xml` は GPL-3.0。Jazzy は CI で build が success（未確認→確認）
- linefit：「orange2022 で使用」は確かめていない。確かめたのは orange_ros2・orange2025・orange2026A の rosinstall と launch。orange2026A の実機の scan は高さの帯の分割から作られている。KBKN の fork は `r_max` の型の修正を含まない
- GSeg3D：ライセンス BSD-3-Clause、CI は jazzy で success（未確認→確認）。MID-360 の報告は見落とし（茂みを地面にした）の例
- Ground Consistency Layer：組む地面分割は GSeg3D（tutorial）、層のソースは dfki-ric/nav2_ground_consistency_costmap_plugin の `main`、ライセンス BSD-3-Clause。master の格子に直接書く
- Autoware：core の `autoware_ground_filter` は Jazzy の apt にある（1.9.0）。universe の RANSAC の filter が坂を扱えないことは文書で確認

## 9. 未確認の一覧

- MID-360 のデータシート（1 通の点数、距離の雑音）：原本未照合
- 傾けた MID-360 で Patchwork++・GSeg3D・linefit を使った公開の例
- つくばチャレンジの他のチームの採用（KBKN の linefit のほかは見つからない。検索は網羅的でない）
- KBKN の本番の走行での linefit の使用
- Ground Consistency Layer の Nav2 1.3.13 での build（CI なし）
- Autoware universe の `autoware_ground_segmentation` のライセンスの本文と依存の詳細
- pcl_ros の LICENSE の本文
- 車載 PC の CPU の余裕
- ObstacleLayer の光線の消去が終点の区画を含むか
- 案 a（base_link）で Patchwork++ の同心円の中心がセンサーとずれる影響
