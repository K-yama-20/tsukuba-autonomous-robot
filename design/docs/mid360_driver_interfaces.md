# MID-360 のドライバの出力（原本で確かめた事実と出典）

- 作成：2026-11-07、第235便の流れ D（REV-260 の根拠。DEC-475）
- 状態：事実の表。設計の決定ではない。使うか・直すかは判断台帳の DEC-476〜479（承認待ち）
- 書いた範囲：AI が原本（上流のソース、公式の資料、ROS の定義）を直接読んで確かめたことだけ。推測は「推測」、読んでいないものは「未確認」と書く
- 実機・車載 PC での確認：**未実施**（ドライバを Gouda から動かした記録はまだない。P4 の T04-1・T04-2 で確かめる）

## 1. 読んだ原本と版

| 略号 | 原本 | 版 | 置き場所 |
|---|---|---|---|
| DRV | Livox-SDK/livox_ros_driver2 | commit 21445540f0d1（third_party/drivers.repos の固定と同じ） | lddc.cpp・livox_ros_driver2.cpp はリポジトリの `design/research/upstream_sensors/livox_ros_driver2_2144554/`。他のファイルは同じ commit の clone（.git/HEAD の値で確認）を読んだ。リポジトリには写していない |
| SDK | Livox-SDK/Livox-SDK2 | commit c0796f04c143（drivers.repos と同じ） | 同じ commit の clone を読んだ。写していない |
| PROTO | Livox LiDAR Communication Protocol -- Mid360（livox_wiki_en） | 改版 v1.4.12（commit 6b030b7、sha256 728a33c8…） | リポジトリの外の公式資料（Sensors/MID-360/official/INDEX.md） |
| UM | Livox Mid-360 User Manual（英語） | v1.2、2024.04（sha256 3f202c84…） | 同上。ページは PDF のページ番号（印刷のページ番号はかっこ内） |
| IMU-MSG | ros2/common_interfaces の sensor_msgs/msg/Imu.msg・geometry_msgs/msg/Quaternion.msg | jazzy の commit a941f14bb318（取得 2026-11-07） | GitHub から読んだ。写していない |
| REP145 | REP-145 Conventions for IMU Sensor Drivers（ros-infrastructure/rep の rep-0145.rst） | master（取得時 11ca24a4）。REP の状態は Draft（4 行） | 同上 |
| GLIM | koide3/glim_ros2・glim | v1.2.2（実車の版。DEC-062） | `design/research/upstream_sensors/glim_ros2_v1.2.2/`・`glim_v1.2.2/` |
| TUD | tu-darmstadt-ros-pkg/livox_ros_driver2（fork、branch jazzy） | commit 2a604474f3e4（2026-10-23） | GitHub から読んだ。写していない |
| GOUDA | このリポジトリの製品のコード | 作業ツリー（HEAD 9c449b5 に REV-242 の実装が未 commit で載った状態） | gouda_core/ |

## 2. 点群（IFD-59）

| 事実 | 出典 |
|---|---|
| ROS 2 の node の既定の名前は livox_driver_node。Gouda は launch の name で livox_ros_driver2 にする | DRV src/livox_ros_driver2.cpp 119 行、GOUDA mid360_config.py 35 行・gouda_nav2.launch.py 87〜88 行 |
| ROS parameter frame_id の既定は frame_default。Gouda は mid360_link を渡す | DRV src/livox_ros_driver2.cpp 136 行、GOUDA mid360_config.py 128〜130 行 |
| 点群の header.frame_id は frame_id の値 | DRV src/lddc.cpp 263 行 |
| topic は livox/lidar（multi_topic 0）。Gouda は /sensors/mid360/points に remap する（remap はこの 1 つだけ） | DRV src/lddc.cpp 659 行、GOUDA gouda_nav2.launch.py 87〜88 行 |
| publisher の深さは kMinEthPacketQueueSize（32）× 8 ＝ 256。QoS はそれ以外 rclcpp の既定 | DRV src/lddc.cpp 658〜661 行、src/comm/comm.h 49 行 |
| 時刻同期がない packet（time_type 0）の時刻は、ドライバが受け取ったときの PC の時計。PTP・GPS のときは機器の時刻 | DRV src/comm/pub_handler.cpp 265〜275 行、PROTO 117〜131 行 |
| publish_freq の既定は 10 Hz（Gouda は渡さない） | DRV src/livox_ros_driver2.cpp 134 行、GOUDA mid360_config.py 128〜130 行 |

## 3. 内蔵 IMU（ドライバの livox/imu）

| 事実 | 出典 |
|---|---|
| MID-360 は電源を入れると IMU を 200 Hz で送り始める。送信は PC から有効・無効にできる。既定は有効 | UM PDF 17（15）ページ「IMU Data」、PDF 15（13）ページ |
| 機器の設定 imu_data_en（key 0x001C）で送信を切り替える。周期・測定範囲の設定は imu_sensor_cfg（0x002B） | PROTO 373・377 行、SDK include/livox_lidar_def.h 99 行 |
| ドライバは MID-360 との接続の通知のたびに IMU の送信を有効にする（タイムアウトなら繰り返す）。止める ROS parameter はない | DRV src/call_back/livox_lidar_callback.cpp 111 行・293〜319 行、src/livox_ros_driver2.cpp 131〜139 行 |
| Gouda は雛形の imu_data_ip（と cmd_data_ip・push_msg_ip・point_data_ip）に PC のアドレスを入れる。よって IMU は PC に届く | GOUDA mid360_config.py 43 行・108〜112 行 |
| ドライバは購読者の有無に関係なく sensor_msgs/Imu を topic livox/imu に出す。深さは 32 × 8 ＝ 256 | DRV src/lddc.cpp 140〜160 行・498〜524 行・683〜688 行 |
| Gouda の launch は livox/imu を remap しない。namespace の指定もないので /livox/imu になる（推測：実行の記録では未確認） | GOUDA gouda_nav2.launch.py 87〜88 行、gouda_core.launch.py 49〜51 行 |
| Gouda の node で /livox/imu を購読するものはない。rosbag は `ros2 bag record -a` なので記録には入る | GOUDA recorder_node.py 102 行。購読は製品のコードを grep して確認 |
| UDP の IMU の値の単位：ジャイロ rad/s、加速度 g | PROTO 160〜165 行、DRV src/comm/lidar_imu_data_queue.h 36〜43 行（注釈） |
| ドライバは単位を変えない（3 か所とも値をそのまま写す） | DRV src/comm/pub_handler.cpp 119〜124 行、src/comm/lidar_imu_data_queue.cpp 35〜41 行、src/lddc.cpp 490〜495 行 |
| IMU の header.frame_id は文字列 livox_frame に固定。parameter frame_id は IMU には効かない | DRV src/lddc.cpp 481 行（点群は 263 行で parameter の値） |
| orientation と 3 つの共分散は設定しない | DRV src/lddc.cpp 480〜496 行 |
| IMU の時刻は点群と同じ扱い（同期なしは PC の時計） | DRV src/comm/pub_handler.cpp 117〜118 行・265〜275 行 |
| IMU の軸の向きは点群の座標と同じ。IMU の位置は点群の座標で x＝11.0 mm、y＝23.29 mm、z＝−44.12 mm | UM PDF 17（15）ページ |
| IMU の型式は ICM40609 | UM PDF 22（20）ページ |

### ROS の約束との違い

| 約束 | 出典 | MID-360 のドライバ |
|---|---|---|
| 加速度は m/s²（g ではない）、角速度は rad/s | IMU-MSG Imu.msg 3 行、REP145 67・73 行 | 加速度が g のまま（違反）。角速度は一致 |
| 共分散が全部 0 は「共分散が不明」の意味。推定がない要素は共分散の要素 0 を −1 にする | IMU-MSG Imu.msg 7〜13 行、REP145 110 行 | 共分散を設定しない（全部 0 のまま。推測：既定値の初期化による）。orientation に推定がない印（−1）がない |
| orientation の既定値は w＝1（回転なし） | IMU-MSG Quaternion.msg 3〜6 行 | 設定しないので、既定値の回転なしが「不明の共分散つきの値」として出る（推測。記録で未確認） |
| frame_id はセンサの frame。データは 1 つの frame で出す | REP145 41・54 行 | IMU は livox_frame、点群は mid360_link（別の名前） |
| ドライバは機器の値をそのまま出し、加工は下流に任せる | REP145 56 行 | 写すだけで加工しない（この点は一致） |

## 4. frame と TF

| 事実 | 出典 |
|---|---|
| Gouda の静的 TF（ND-13）が出す MID-360 の frame は base_link → mid360_link だけ（取り付けの値がそろうときだけ） | GOUDA static_tf_node.py 70〜78 行、mid360_config.py 82〜88 行 |
| livox_frame を TF に出すものは Gouda にない（製品のコードを grep して 0 件。上流の launch の例は frame_id に livox_frame を使う） | `design/research/upstream_sensors/livox_ros_driver2_2144554/msg_MID360_launch.py` 13 行 |
| 上流の設定ファイルの外部パラメータは 0 のまま（Gouda が 0 以外を拒む）。機器はこの値を保存するだけで使わない | GOUDA mid360_config.py 113〜115 行、UM PDF 15（13）ページ |

## 5. 診断・状態（作動状態・温度・診断コード）

| 事実 | 出典 |
|---|---|
| MID-360 は電源を入れると、機器の情報・設定・今の状態を、設定した送り先へ周期的に送る | UM PDF 14（12）ページ「Information Push」 |
| 状態の項目：cur_work_state（0x8006）、core_temp（0x8007、単位 0.01 ℃）、lidar_diag_status（0x800E、モジュールごとに正常・警告・異常・safety_err の段階）、hms_code（0x8011、診断コード） | PROTO 384・385・391・393 行、UM PDF 15（13）ページ「Current Status」 |
| 高温では警告を出し、さらに高いと自動で止まる | UM PDF 23 ページの注 7 |
| Gouda は push_msg_ip に PC のアドレスを入れるので、状態の通知も PC に届く | GOUDA mid360_config.py 43 行 |
| SDK2 は状態の通知を SetLivoxLidarInfoCallback で登録した callback にだけ渡す | SDK sdk_core/command_handler/general_command_handler.cpp 589〜597 行、include/livox_lidar_api.h 98〜103 行 |
| ドライバはこの callback を登録しない。登録するのは接続の通知（SetLivoxLidarInfoChangeCallback。機器ごとに 1 回）と点群・IMU の callback だけ | DRV src/lds_lidar.cpp 182・187・188 行、SDK general_command_handler.cpp 582〜585 行 |
| ドライバの publisher は点群と IMU だけ（診断の topic はない） | DRV src/lddc.cpp 527〜554 行 |
| ドライバは SDK のコンソールのログを止める | DRV src/lds_lidar.cpp 131 行 |
| 以上から、状態・温度・診断コードは ROS にも Gouda の記録にも出ない。点群が途絶えたことは、topic が来ないことでしか分からない（DEC-456） | 上の行からの帰結 |

## 6. 先行事例（下流・fork）

| 候補 | 内容 | 出典 | ROS 2 Jazzy | ライセンス | 保守 | 実機での使用 |
|---|---|---|---|---|---|---|
| GLIM の acc_scale | 加速度に掛ける係数。設定の注釈は「Livox は 9.80665」。0 のときは最初に受けた値のノルムで単位を推定する（7〜12 は m/s²、0.8〜1.2 は g、それ以外は m/s² とみなして警告） | GLIM config_ros_v1.2.2.json 13・55 行、glim_ros.cpp 85・228〜243 行 | 実車に 1.2.2 が入っている（DEC-062） | この便では未確認 | この便では未確認 | この車両では XT-32＋ADIS16607-2 で使用。Livox の IMU では未使用 |
| TU Darmstadt の fork | IMU の frame_id（imu_frame_id）と単位の切り替え（imu_as_gforce。false で 9.80665 を掛ける）を持つ。診断（publish_diagnostics、既定 false）は時刻同期の種類と packet の途絶だけで、温度・診断コードは出さない | TUD src/lddc.cpp 566〜588 行、src/livox_ros_driver2.cpp 141・149・153・208〜257 行、src/parse_cfg_file/parse_livox_lidar_cfg.cpp 100〜116 行 | branch jazzy | 上流と同じ Livox の文面（MIT の部分を含む） | 最後の commit 2026-10-23 | 未確認。SDK も同じ組の fork が要る（README）。設定ファイルと ROS parameter のどちらの imu_frame_id が効くかは未照合 |
| Ericsii の fork など | IMU を m/s² で出す fork があるという調査の記録 | design/research/vehicle_pc/2026-11-06_mid360_connection/ledger.yaml の R-M-01〜03（AI は未照合） | 未確認 | 未確認 | 未確認 | 未確認 |
| 上流の issue | 単位が g（issue 157）、frame_id を変えられない（issue 217）などの報告 | 同じ台帳の R-L-04（AI は未照合） | — | — | — | — |

既製の「g を m/s² に直して共分散の印を付け直す」だけの ROS 2 の node は、この便では探していない（**未調査**）。

## 7. 確かめていないこと

- 実機で /livox/imu が出ているか、周期、frame_id、静止時の加速度のノルム（約 1 なら g）、orientation の実際の値（P4 の T04-1・T04-2・T04-6 で確かめる）
- 雛形の imu_data_ip を空にしたときに IMU の送信が止まるか
- 機器の設定で imu_data_en を 0 にしても、ドライバの接続の後に有効に戻るか（ソースからの推測では戻る）
- SDK を別のプロセスで初期化して状態の通知を読めるか（ドライバと送り先のポートを取り合う恐れがある。推測）
- IMU の位置の公式の値と、手元の機体の一致（実測の予定はない）
- 手元の機体が Mid-360 か Mid-360S か（T00-1）
