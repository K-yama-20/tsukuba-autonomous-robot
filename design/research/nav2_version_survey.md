# Nav2 採用版の調査メモ（2026-10-09 時点）

状態: **実車PCの版は照合済み（V-001 解消、DEC-012）**。実車PC（aya@aya-Parallels-ARM-Virtual-Machine）で人が実行した確認コマンドの出力 `research/vehicle_pc/2026-10-09_vehicle_pc_versions.txt` により、Ubuntu 24.04.5 LTS（arm64）、/opt/ros/jazzy、Nav2 パッケージ 1.3.13（navigation2・bringup・bt-navigator・controller・msgs・route）を確認。上流 jazzy ブランチ commit 645abd95 の package.xml 版 1.3.13 と一致する。パッケージ版での照合であり、インストール済みバイナリ内の IDL を直接読んだものではない。開発作業環境（この Mac）の版は根拠にしていない。

## 1. 人の申告と照合状況

| 項目 | 内容 | 根拠 | 状態 |
|---|---|---|---|
| 実車PCの OS / ROS 2 | 申告「ROS2 jazzyをubuntu 24.0.5上で動かしています」→ 実測 Ubuntu 24.04.5 LTS、/opt/ros/jazzy | DEC-003（申告原文）、DEC-012（出力原文）、FILE-VEHICLE-PC | 照合済み |
| 実車PCへの接続 | 鍵認証は拒否。人が実車PCでコマンドを実行し出力を提供 | 2026-10-09 | AI は接続していない。出力を証拠ファイルとして保存 |
| 実装リポジトリの記述 | README「Ubuntu 24.04 / ROS 2 Jazzy」、`gouda_gui/runtime.py` が `/opt/ros/jazzy/lib/rviz2` を参照、`docs/gouda_runbook.md`「Ubuntu ARM64/Jazzyの開発環境で確認した範囲。最終配布版ではない」 | `tsukuba-autonomous-robot` HEAD a091ed39 | 開発環境の記述であり実車PCの証拠ではない |
| 実装リポジトリの Nav2 依存 | `gouda_navigation/package.xml` は nav2_msgs・nav2_planner・nav2_navfn_planner・nav2_lifecycle_manager に exec_depend。版は未指定 | 同上 | 版の根拠にならない |
| Nav2 上流 | ros-navigation/navigation2 ブランチ jazzy、commit `645abd95f2be02a13ca539b29c2ddc065db34f89`、nav2_msgs / nav2_route / nav2_bt_navigator の package.xml version `1.3.13` | `research/upstream_jazzy/evidence.json`（SHA-256 付き） | 実車PC の 1.3.13 と版一致 |

照合に使ったコマンド（出力は `design/research/vehicle_pc/2026-10-09_vehicle_pc_versions.txt`）:

```bash
cat /etc/os-release; ls /opt/ros; dpkg -l | grep -E "ros-[a-z]+-(navigation2|nav2-msgs|nav2-bringup|nav2-route|nav2-controller|nav2-bt-navigator)"
```

## 2. 版依存IFの確認結果（上流 jazzy 645abd95。実車PC の 1.3.13 と版一致）

| IF | 確認したこと | 根拠ファイル |
|---|---|---|
| IFD-13 NavigateThroughPoses | goal: `geometry_msgs/PoseStamped[] poses`, `string behavior_tree`。result: `uint16 error_code`, `string error_msg`（NONE=0）。feedback: `current_pose`, `navigation_time`, `estimated_time_remaining`, `number_of_recoveries`, `distance_remaining`, `number_of_poses_remaining` | `nav2_msgs/action/NavigateThroughPoses.action` |
| 通過判定 | 既定 BT `navigate_through_poses_w_replanning_and_recovery.xml` は `RemovePassedGoals radius="0.7"`。`remove_passed_goals_action.cpp` は現在位置と先頭 goal の距離が radius 以下なら goal を除く。通過判定は Nav2 側（RQ-I011 と整合）。旧資料の 5 m はここに流用しない（PRM-11 未確定） | 同 BT xml、`nav2_behavior_tree/plugins/action/remove_passed_goals_action.cpp` |
| 既定 BT の recovery | `RecoveryNode number_of_retries="6"`、ClearCostmap・Spin・Wait・BackUp を RoundRobin。後退・再計画は Nav2 BT（RQ-I018）。失敗 result で Gouda は一時停止へ（TR-07） | 同 BT xml |
| IFD-14 SpeedLimit | `nav2_msgs/msg/SpeedLimit`: `bool percentage`, `float64 speed_limit`（0.0 = 無制限）。controller_server は param `speed_limit_topic`（既定 `speed_limit`）を `rclcpp::QoS(10)` で購読し `setSpeedLimit(speed_limit, percentage)` | `nav2_msgs/msg/SpeedLimit.msg`、`nav2_controller/src/controller_server.cpp` 63,255-257,836-840 行 |
| Speed Filter | `CostmapFilterInfo.type` 1=% / 2=m/s、mask の OccupancyGrid 値を `base + data*multiplier` で速度へ。SpeedLimit を `speed_limit_topic` に QoS(10) で発行 | `nav2_msgs/msg/CostmapFilterInfo.msg`、`nav2_costmap_2d/plugins/costmap_filters/speed_filter.cpp` |
| Route Server | jazzy に `nav2_route` 1.3.13 が存在。`AdjustSpeedLimit` route operation は edge metadata `speed_tag`（既定 `speed_limit`）から `percentage=true` の SpeedLimit を発行 | `nav2_route/package.xml`、`nav2_route/src/plugins/route_operations/adjust_speed_limit.cpp` 32-65 行 |
| IFD-15 cmd_vel | controller_server は `TwistPublisher(node, "cmd_vel", 1)`。param `enable_stamped_cmd_vel` で `Twist` / `TwistStamped` を切替（既定値は実車PC版で確認）。取消時は `publishZeroVelocity()` | `nav2_util/include/nav2_util/twist_publisher.hpp`、`controller_server.cpp` 227, 512-516, 779 行 |
| REP-103 | x 前方・y 左方・z 上方。RQ-I071（-y 前方・+x 右方）との衝突は DEC-007 で解消: base_link は REP-103、LiDAR・IMU の座標方向は gouda_monitor の /config で指定し静的TFで変換（C-018 resolved_by_decision） | `research/upstream_jazzy/rep-0103.rst` |
| IFD-24 map | map_server は OccupancyGrid を `QoS(KeepLast(1)).transient_local().reliable()` で発行 | `nav2_map_server/src/map_server/map_server.cpp` 115-118 行 |
| IFD-32 plan / costmap | planner_server は `plan` を QoS(1)、Costmap2DPublisher は `KeepLast(1).transient_local().reliable()` | `nav2_planner/src/planner_server.cpp` 150 行、`nav2_costmap_2d/src/costmap_2d_publisher.cpp` 70-82 行 |

## 3. H-001（SpeedLimit 発行方式）の比較

要件: 区間（waypoint i → i+1）の速度上限を、Nav2 標準の SpeedLimit 経路で、単一の発行元から適用する（RQ-I010・RQ-I020）。境界では進入区間の値を適用し、境界時点の実速度保証は不要（RQ-I062）。通過判定は Nav2（RQ-I011）。Nav2 本体は改変しない（RQ-I056）。

| 案 | 区間境界の検出 | 値の指定 | 構成変更 | 評価 |
|---|---|---|---|---|
| A. Gouda 側発行器（gouda_mode_manager） | NavigateThroughPoses feedback の `number_of_poses_remaining` の減少（Nav2 の RemovePassedGoals による判定） | `percentage=false`、m/s | なし（action client に発行を追加） | **推奨**。要件に直接対応。独自の通過判定を持たない。feedback 周期ぶんの遅れは RQ-I062 の範囲 |
| B. Route Server（nav2_route） | route graph の edge 進入 | `percentage=true`（最大速度比）。m/s 指定不可 | waypoint 列→graph 変換、BT を route 系へ変更 | 区間=edge で意味は合う。構成変更が大きく、%指定が RQ-I010 の「速度上限（m/s）」と合わない。実車PC版での提供状況は V-001 |
| C. Speed Filter | 車体位置が mask の cell に入ったとき | type=2 で m/s | waypoint セットごとに mask 生成、filter info 配信 | 折れ線区間を平面領域に塗る幾何定義が未決（Q-06/Q-12）。境界の意味が「進入する区間の値」と一致しにくい。推奨しない |

推奨は A。承認は人（DEC-011）。実車PC版は照合済み（nav2_route 1.3.13 もインストール済みのため B も技術的には可能）。

## 4. 版照合後も確定していないもの

- `enable_stamped_cmd_vel` の採用値（PRM-12。案は true）
- Nav2 の BT 既定値（RemovePassedGoals radius 0.7、recovery 回数 6）を採用値にすること（PRM-11 は Q-12/Q-06 の後）
- GLIM の版と出力形式（IFD-35、Q-02）
- インストール済みバイナリ内 IDL の直接照合（必要なら `ros2 interface show nav2_msgs/action/NavigateThroughPoses` の出力を追加証拠にする）
