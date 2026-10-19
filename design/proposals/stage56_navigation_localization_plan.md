# 工程 5-6: Global_localization と Navigation の実装の検討（提案 第1版。実装は許可まで行わない）

状態: 提案（承認待ち）。2026-10-17。人の指示（DEC-119、原文）「次にやりたいことは、Global_localizationまたはNavigationのノードの実装。まずは検討して、結果を私に報告せよ。」

- 実装・設定の変更は人の個別の許可（DEC-106）の後。本書の承認事項は判断台帳 DEC-120〜DEC-124。DEC-115（自己位置推定の方式）は保留のまま。
- 正本で確かめた事実と、AI の推測・推奨を分けて書く。読んだ正本: `docs/implementation_stages.md` §1（5-6）、`docs/speed_filter_design.md`、`proposals/localization_selection.md`、model.yaml の ND-03・07〜10・13、IFD-02・13・14・25・26・32〜34・39・41・42、TR-05、SO-07、TS-01・02・05・06・14〜16・21、Q-02・04・06、PRM-01〜07・11・12・16〜18、G-INIT-POSE-GNSS、H-007・DEC-009。

## 1. 結論（AI の推奨）

1. **先に Navigation（ND-10 と mode_manager の Nav2 の client）を作る。** 自己位置推定の方式（DEC-115）にも GNSS の設計にも依存しない部分が大きい。VM で、Nav2 の標準の模擬（nav2_loopback_sim）に map→odom と odom→base_link を出させれば、車体を動かさずに 5-6 の試験の多く（TS-01・02・05・14・15・21）を通せる。
2. **並行して GNSS の取込み（受信と記録と表示だけ）を、次の実機試験の前に作る。** 次の実機試験（同じ場所を 2 回。DEC-114）の rosbag に GNSS が入っていないと、地図と GNSS の座標の対応も、GNSS による初期位置（intent 第11版）も評価できない。時間の制約があるのはこれだけ。
3. **Global_localization（ND-07）は DEC-115 と GNSS の初期位置の設計（G-INIT-POSE-GNSS）を決めてから。** ただし ND-08（GLIM を odometry だけで動かし、odom→base_link を出す）は案 A・A3・B に共通で、DEC-115 を待たずに作れる。

## 2. 現状（実装と環境。2026-10-17 に確かめた事実）

| 項目 | 状態 |
|---|---|
| mode_manager | TR-05（自律走行開始）は未実装で「5-6」として拒否（`IMPLEMENTED_TRANSITIONS = {TR-03, TR-04, TR-12}`）。Nav2 の action client はない |
| StartAutonomy（IFD-02） | 型は定義済み（地図・waypoint の ID／版／ハッシュと initial_pose）。monitor は request_id だけを送る |
| 静的 TF（ND-13） | 未実装。取付位置から姿勢を計算する `sensor_extrinsics.py`（GLIM の T_lidar_imu 用）はある |
| 速度マスク（IFD-41） | waypoint の保存時に生成済み（工程 5-4）。Nav2 への読み込み（IFD-42）は未実装 |
| 車体出力（ND-11・12） | 実装済み（工程 5-5、stub 試験）。実車試験は未実施、DAC 値は未確定（DEC-077） |
| x86 機の Nav2 | **setup.sh は Nav2 を入れない**（ros-jazzy-desktop・GLIM・ドライバだけ）。x86 機に Nav2 が入っているかは未確認。「実車PC の Nav2 1.3.13」の記録（2026-10-09_vehicle_pc_versions.txt）は VM（arm64）のもの |
| VM の apt | Nav2 1.3.13（amcl・bt_navigator・controller・costmap・map_server・mppi・rpp・smac・velocity_smoother・collision_monitor・bringup）、Autoware の ndt_scan_matcher・ekf_localizer・map_loader 1.9.0、robot_localization 3.8.3 は導入済み。nav2_loopback_sim 1.3.13・pointcloud_to_laserscan 2.0.2・septentrio_gnss_driver 1.4.8 は apt にあり未導入 |
| GNSS | Septentrio mosaic-go G5 P6（デュアルアンテナ、ネットワーク RTK）を搭載（DEC-117）。ドライバ・node・IF・記録は未設計。VM の `~/mosaic_test.sbf` は 0 バイト（2026-10-17 16:54 作成。中身なし） |
| VM の点群の試験 | DEC-116 で試験スタックに Fast DDS の設定を入れた（約 2 MB の点群が届くようになった。FILE-DEC116-FASTDDS） |

## 3. 依存の整理

| 作るもの | DEC-115（方式） | GNSS の設計 | Q-04・Q-06・PRM（実車値） | 車体 |
|---|---|---|---|---|
| N1 Nav2 の構成（launch・設定・BT）と mode_manager の client（TR-05・IFD-13・IFD-42・適用状態） | 不要 | 不要（初期姿勢は今の IF のまま。§6） | 仮値で試験（PRM-11・17・18 は上流の既定、footprint は PRM-01・02・06 の記載値） | 不要（VM の模擬） |
| N2 静的 TF（ND-13） | 不要 | アンテナの位置を足すなら関係 | 取付値は人が /config で（RQ-I081） | 不要 |
| N3 障害物の点群（ND-09）と costmap | 不要 | 不要 | Q-04（可視範囲）は実車で | rosbag の再生で可 |
| G0 GNSS の取込み（受信・記録・表示） | 不要 | 取込みの部分だけ | アンテナ位置は人が /config で | 実機試験の前に x86 機で |
| L1 ND-08（GLIM の odometry だけ＋中継） | 不要（3 案に共通） | 不要 | IMU と LiDAR の傾き（DEC-105）は精度に効く | rosbag の再生で可 |
| L2 ND-07（照合器と EstimatorStatus） | **要る** | 初期化の流れは要る | 推定不能のしきい値は承認か実測 | rosbag の再生で可 |
| L3 GNSS による初期位置と人の確認 | 要る（A3 なら Monte Carlo の探索が GNSS の誤差を吸収できる見込み） | **要る** | — | 実機試験 |

## 4. Navigation（N1〜N3）の案

### 4.1 構成（N1）

- Nav2 は改変しない（RQ-I056）。標準の bt_navigator・planner_server・controller_server・behavior_server・smoother_server・map_server（静的地図）・map_server（速度マスク用）・costmap_filter_info_server・lifecycle_manager を、**gouda_core の launch とは別の launch**（例 `gouda_nav2.launch.py`）で gouda.sh start から一緒に起動する（起動の方法は増やさない: DEC-090）。設定は `design/generated/params/` に生成する（DR-15、RQ-I076）。
- 自律走行・一時停止の間だけ active にするか、常に active で goal を持たないかは、ND-10 の placement_rationale（「一時停止中も active のまま goal を持たない」）に従う。手動走行・地図作成では、map→odom の持ち主（ND-07）がないため Nav2 を inactive にしておく案（AI の推奨。RQ-I004 の競合する推定器を同時に有効化しない、と合わせる）。
- 選ぶもの（承認事項 DEC-122）:

| 項目 | 推奨 | 代わり | 理由・振る舞いの違い |
|---|---|---|---|
| controller | Regulated Pure Pursuit（RPP） | MPPI（Jazzy の既定） | RPP は経路をなぞるだけで計算が軽く、挙動を説明しやすい。speed_limit（SpeedFilter）に対応。MPPI は障害物の回避が滑らかだが CPU を使い、自己位置推定と同じ PC で動く。後退は RPP の allow_reversing（既定 false）で無効のまま |
| planner | NavFn（Jazzy の既定） | Smac 2D | 差動二輪で十分。設定が少ない |
| BT | 上流の navigate_through_poses_w_replanning_and_recovery.xml を写して、RemovePassedGoals の radius（PRM-11）と RecoveryNode の回数（PRM-18）だけを生成時に入れる | 独自の BT | Nav2 の機能を独自に作らない（intent 82 行）。PRM-11・18 は仮値 |
| behaviors | spin・backup・wait（上流の既定） | backup を外す | intent の「後退」（RQ-I018）は Nav2 の backup。AssistedTeleop・DriveOnHeading は使わない |
| velocity_smoother | 使う（上流の既定どおり controller と ND-11 の間） | 使わない | 加速度の制限は Nav2 で行う。値は Q-06（実車値）。使うと cmd_vel の発行元は velocity_smoother になる（IFD-15 の発行元の記述を直す） |
| collision_monitor | **使わない** | 使う | 「近づいたら止める」機構は PC 側の非常停止に当たりうる（RQ-I072、DR-06）。障害物は costmap と計画で扱う |
| cmd_vel の型（PRM-12） | TwistStamped（enable_stamped_cmd_vel=true） | Twist | 期限切れの判定ができる（ND-11）。ND-11 の購読の型を合わせる実装が要る |

### 4.2 mode_manager（N1。実装の範囲）

- TR-05: 選んだ地図・waypoint の ID とハッシュの一致の確認 → 速度マスクと filter info を Nav2 に読み込ませる（IFD-42。map_server の load_map と costmap_filter_info_server の設定）→ NavigateThroughPoses の goal を送る（IFD-13）→ speed_limit_application_state=適用中 を確かめてから motion_hold=false（DEC-056）→ IFD-44 で記録を自動開始。
- feedback から区間の番号を記録する（RQ-I030）。result で TR-07（失敗→一時停止）・TR-08（到達→一時停止）。
- 一時停止・終了（TR-06・TR-11・TR-12）の goal の取消。復帰（TR-13）と PC 再起動後（TR-10）は 5-7 の範囲。
- monitor: 地図と waypoint の組の選択・プレビュー（RQ-I011。5-4 のプレビューの流用）、開始の要求に ID・ハッシュ・初期姿勢を入れる。
- TR-05 の guard「ND-07・ND-08・ND-10 が活性」は、N1 では ND-07・ND-08 が無い。試験スタックでは模擬（loopback_sim）を ND-07・ND-08 の代わりとして扱う設定を試験専用に置く案。**実車の起動では、ND-07・ND-08 が無い限り TR-05 は拒否のまま**（車体が自己位置推定なしに動かないこと）。

### 4.3 試験（N1。VM、車体なし）

- nav2_loopback_sim（Nav2 の標準の模擬。cmd_vel を積分して odom→base_link と map→odom を出す）を試験スタックでだけ起動する。ND-11・ND-12 は起動しても vehicle_bridge は ESP32 の模擬（esp32_sim）につなぐ（5-5 の試験と同じ）。
- 対象: TS-01（初回区間の上限）、TS-02（残り pose が一度に複数減る）、TS-05（到達と失敗）、TS-14（重複 cell）、TS-15（適用状態）、TS-21（開始は人の操作だけ）。TS-06（復帰）は 5-7。TS-16 は実車かシミュレーションの記録。
- 地図: 実機の原図の写しから変換した 2D 地図（地図タブの成果）。
- 要るもの: VM への nav2_loopback_sim の導入（apt。sudo がないため人に依頼）。

### 4.4 N2 静的 TF（ND-13）

- `sensor_extrinsics.py` の計算をそのまま使い、base_footprint→base_link（PRM-05）と base_link→各センサーの静的 TF を出す node を作る。/config の値が UNKNOWN の項目は中立の値で出して記録する（RQ-I081 と同じ扱い。ND-13 の「未入力なら TF を出さない」の記述と食い違うため、正本の直しを承認事項 DEC-122 に含める）。
- GLIM には、今と同じく T_lidar_imu を渡す（GLIM の publish_imu2lidar は false にして、TF は ND-13 だけが出す: 提案 localization_selection §3）。

### 4.5 N3 障害物（ND-09）と costmap

- 案 a（推奨。独自の node なし）: XT-32 の点群をそのまま Nav2 の VoxelLayer（local）・ObstacleLayer（global）に入れ、高さの帯（min・max_obstacle_height、PRM-03 の車高）で地面と頭上を除く。track_unknown_space を true にして、観測していない所を空きとみなさない（RQ-I012）。
- 案 b: ND-09（独自の node）で地面を除いた点群を作る。坂でも地面を除けるが、地面の推定（DEC-107、保留中）と同じ課題になる。
- 案 a の弱み: 坂の上りで地面が帯に入ると障害物になる（推測。実車の地図で確かめる）。屋外の使用環境（DEC-103）で問題になれば案 b に進む。
- VM で rosbag の再生から costmap を作って確かめる（DEC-116 の設定で点群が届く）。

## 5. GNSS（G0・L3）の案

### 5.1 G0 取込み（次の実機試験の前に）

- ドライバ: septentrio_gnss_driver（ROS 2、apt の Jazzy 1.4.8。BSD-3）。改変しない（DEC-075 と同じ扱い）。setup.sh の apt の一覧に加える。
- 接続: mosaic-go は USB（シリアル・イーサネットの両方を出す）。sensor_supervisor（ND-18）が LiDAR・IMU と同じくデバイスの有無を見てドライバを起動・作り直す（`docs/sensor_supervision.md` の仕組みに乗せる）。
- 出す topic（案）: 位置（NavSatFix 相当、品質の区分＝RTK fix／float／単独）、デュアルアンテナの向き（AttEuler）、速度。ネットワーク RTK の補正は受信機の内蔵の NTRIP の機能か、ドライバの機能で受ける（どちらにするか、接続先・認証の情報の置き場所は実装の時に。認証の情報は公開のリポジトリに入れない）。
- 記録: rosbag に入る（recorder は -a で全 topic）。地図作成のときも記録する（地図と GNSS の対応に使う）。
- 表示: monitor のセンサーの欄に GNSS（受信・品質・衛星数・向きの有無）を加える。表示だけで停止の条件にしない（DEC-088 と同じ）。
- 前提: 走行中に車載 PC がインターネットにつながること（ネットワーク RTK）。つながらない間は単独測位（数 m の誤差）になる。

### 5.2 L3 GNSS による初期位置（G-INIT-POSE-GNSS。設計の方針案、承認事項 DEC-124）

- 地図と GNSS の対応: 地図作成の時に GNSS（RTK fix の点だけ）と GLIM の軌跡を同時に記録し、二つの軌跡の重ね合わせ（回転・平行移動。高さは使わない）で「GNSS の座標（ENU）→ 地図の座標」を求めて、原図と一緒に保存する（地図の manifest。地図の変換の仕事）。重ね合わせの残差を記録し、大きければ使わない。
- 初期位置: 開始の準備で、GNSS の位置と向き → 地図の座標の姿勢 → 自己位置推定の初期値。A3 なら Monte Carlo の探索（ndt_align_srv）で照合して収束させる。monitor に GNSS の姿勢と照合の結果を地図に重ねて表示し、**人が収束と正しさを確認してから**開始ボタンを押す（体験 9）。
- 人の指定（体験 9 の「人が初期位置や向きを設定することも可能」）: GNSS が fix でないとき・地図の対応がないときの代わりとして残す（IFD-39 をそのまま使う）。
- PC 再起動後（DEC-009）: 「人が初期位置を再指定」を「GNSS で取り直して人が確認、または人が指定」に読み替える案。保存した最後の姿勢は使わないことは変えない。読み替えは承認事項。
- 振る舞いの違い: 今の設計は人の指定だけ。案では GNSS の値が既定になり、人は確認する。誤った GNSS（マルチパス・float）で照合が別の場所に収束する危険があるので、品質の区分と照合の結果の両方を表示し、開始の可否は人の確認とする。

## 6. Global_localization（L1・L2）

- L1（ND-08、DEC-115 を待たない）: GLIM を odometry だけの設定（enable_local_mapping・enable_global_mapping を false、frame の付け替え、publish_imu2lidar false）で、自律走行・一時停止の間だけ起動する（地図作成の GLIM とは同時に動かさない）。GLIM の ~/odom と IMU の角速度から IFD-25（localization/odometry）を作る中継の node（独自、小さい）。根拠は提案 localization_selection §3（3 案に共通）。承認事項 DEC-123。
- L2（ND-07、DEC-115 の後）: A3 なら、点群の間引き・速度の中継・map→odom の中継（EKF の TF は remap）・地図の 20 m 格子への分割（map_creator）・初期化の手順・EstimatorStatus（推定不能の区分）。各部品は方式の採用と合わせて承認事項（localization_selection §9 の 5）。
- IFD-34（localization/initial_pose）は、L3 の方針が決まるまで今の形（ND-03 が開始の要求の初期姿勢を 1 回転送）で作る。GNSS の値は monitor が開始の要求の初期姿勢の既定値として入れる形にすれば、IF を変えずに済む見込み（AI の推測）。

## 7. 進める順序の案（DEC-120）

| 順 | 作業 | 必要な許可 |
|---|---|---|
| 1 | G0 GNSS の取込み（受信・記録・表示）。次の実機試験の前に。x86 機での確認は人 | DEC-123 の (1)、DEC-121（apt） |
| 1 | N1 Nav2 の構成と mode_manager の client、VM の試験 | DEC-120・121・122 |
| 2 | N2 静的 TF、N3 costmap（rosbag の再生） | DEC-122 |
| 2 | L1 ND-08（GLIM の odometry だけ＋中継） | DEC-123 の (2) |
| 3 | 次の実機試験（同じ場所を 2 回、GNSS も記録） | 人 |
| 4 | DEC-115 の最終の判断（別の走行の地図での評価、GNSS の初期値も） → L2 ND-07 → L3 | DEC-115・124 |
| 5 | 5-6 の結合試験（rosbag の再生 → 実車の低速） | 実車の判断は人 |

期間の見積もりは書かない（根拠がない）。

## 8. 承認していただきたいこと（判断台帳）

| ID | 内容 | 推奨 |
|---|---|---|
| DEC-120 | 進める順序: Navigation（N1）と GNSS の取込み（G0）を先に、Global_localization（ND-07）は DEC-115 と GNSS の初期位置の設計の後 | 承認 |
| DEC-121 | Nav2 の導入: setup.sh の apt の一覧に Nav2（navigation2 の必要なパッケージ）を加える。VM に nav2_loopback_sim を入れる（人の apt）。試験スタックでだけ loopback_sim を起動する | 承認 |
| DEC-122 | Nav2 の構成の選択（§4.1 の表）と、ND-13・ND-09 の正本の直し（UNKNOWN の取付値は中立で出して記録、ND-09 は案 a で独自の node なし） | 承認 |
| DEC-123 | (1) GNSS の取込み（§5.1）、(2) ND-08（GLIM の odometry だけ＋中継、§6 L1）の実装 | 承認 |
| DEC-124 | GNSS による初期位置の設計の方針（§5.2）。G-INIT-POSE-GNSS の解き方 | 承認（詳細の設計を提案として出してから実装） |

決まらない場合に止まる作業: DEC-120〜122 → Navigation の実装全体。DEC-123 → 次の実機試験の rosbag に GNSS が入らない（地図と GNSS の対応・GNSS の初期位置の評価ができない）。DEC-124 → L3 と、PC 再起動後の再開の設計。

## 9. 残るリスク

- x86 機の CPU: Nav2（RPP・NavFn）と GLIM の odometry と NDT を同時に動かしたときの余裕は未測定。
- 坂での障害物の誤検出（§4.5 案 a）。
- ネットワーク RTK の通信の途絶。GNSS は初期位置にだけ使い、走行中の推定には使わない案なので、途絶しても走行は止まらない（推測）。
- 「PC 出力の中立化は車体全体の停止の保証ではない」（CLAUDE.md 1.5）。Navigation を入れても、手動の優先・ESP32 の watchdog の実機での確認（DEC-050、5-5 の実車試験）は残る。
