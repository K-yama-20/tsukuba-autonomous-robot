# 自律走行に向けた不足と完了の一覧（2026-10-21、第85便、調査のみ）

人の指示（原文）: 「自律走行するために、まだ足りないもの・もう実装が完了しているもの等を表にまとめよ。また、vehicle_bridgeは完成しているかが知りたい。gouda_motion_controllerの状況も詳しく知りたい。」

読んだコミット: `0c898dabbd5ab58cfa55c2b6e29419e60d100a77`（作業ツリーの変更は人のファイルだけ）。根拠は、正本 `design/model.yaml`（ros_node ND-01〜19、pending の判断）、`design/generated/params/*.yaml`、`docs/implementation_stages.md`、`reports/status.md`・`handover_2026-10-21.md`、`gouda_core/` のコード（下の各節にファイルと行）。試験はこの調査では実行していない。試験の結果は既存の作業記録から引用した。

用語: 「実装済み」はコードがあること。「ソフト試験」は stub・VM の試験。「実機」は ESP32・センサー・車体での試験。

## 1. 自律走行に要るものの一覧

| 区分 | 要素 | 実装 | 設定値 | 試験 | 足りないもの・止めているもの |
|---|---|---|---|---|---|
| 起動 | gouda.sh（ND-01） | 実装済み | — | 5-1 合格 | — |
| モード管理 | gouda_mode_manager（ND-03） | 自律走行の開始・一時停止・再開・終了・Nav2 の結果（TR-05〜08・10〜12）は実装済み | PRM-10＝50（第82便） | 5-6 は VM で一部（2026-10-17、loopback_sim で ND-07・08 を代用、FILE-STAGE56-VM-TEST） | 工程 5-7 の自動復帰（TR-13〜16）と TR-09 は未実装（`mode_manager_node.py:69` の IMPLEMENTED_TRANSITIONS にない）。G-RECOVERY-COUNT 未決 |
| HMI | gouda_monitor（ND-02） | 自律走行の準備（waypoint セットの選択、地図上で初期位置を置く）は実装済み（`web/app.js:314`〜） | — | 5-2 合格 | — |
| 記録 | gouda_recorder（ND-04） | 実装済み（非同期の停止、DEC-178） | — | 5-1 合格 | — |
| 地図 | GLIM（ND-06）＋ gouda_map_creator（ND-05） | 地図作成・2D 変換は実装済み | PRM-33〜38・62〜64 未確定（DEC-098 承認待ち）、PRM-37 未確定 | 実データの 2D 変換は TS-34 で不合格（床の反射、G-FLOOR-REFLECTION） | **Nav2 で使える 2D 地図がまだない**。地面推定の修正（DEC-107 承認待ち）、DEC-099・100 の実測 |
| waypoint・速度マスク | monitor の waypoint タブ | 実装済み | PRM-19・20 未確定（保存の要求で値を明示すれば作れる） | 5-4 API 合格、ブラウザ操作は未確認 | 実際の地図での waypoint の作成 |
| 大域の自己位置 | gouda_global_localization（ND-07） | **未実装** | — | — | **最大の不足**。方式が未決（DEC-115 保留、第一候補 A3＝GLIM の odometry＋Autoware の NDT・EKF）。この node がないと TR-05 が開始を拒否する（`mode_manager_node.py:185-189`） |
| 局所の自己位置 | GLIM の odometry ＋ gouda_local_odometry（ND-08） | 実装済み（TR-05 で GLIM を起動） | — | VM で一部 | 正本は lifecycle node、実装は通常の node（第61便の食い違い。台帳未登録） |
| 初期位置 | 人が monitor の地図上に置く | 実装済み | — | VM で一部 | GNSS で初期位置を出す仕組み（DEC-127・129 承認待ち、DEC-148）は未実装 |
| GNSS | septentrio_gnss_driver（ND-19）、NTRIP 中継 | 取込み・記録は実装済み | — | VM・実機で一部 | 自己位置への利用は ND-07 の後 |
| 障害物 | Nav2 costmap の設定（ND-09） | 実装済み（`nav2_config.py`） | PRM-70・71（障害物の高さ）未確定（Q-04） | — | 値の決定 |
| 経路・追従 | Nav2（ND-10）、BT、SpeedFilter、action client | 実装済み（launch、設定の生成、BT、IFD-13 の client） | **PRM-11・17・18・66〜69・72・73 未確定** | VM で一部（TS-01・05・15・21 の一部） | 値が 1 つでも未確定だと Nav2 を起動しない（`nav2_config.py` の冒頭）。TS-02・06・14・16 は未実行 |
| 静的 TF | gouda_static_tf（ND-13） | 実装済み | PRM-05＝0.165 m は記載値（実測していない） | — | IMU と LiDAR の傾き（DEC-105 実測待ち） |
| センサー | sensor_supervisor（ND-18）、XT-32（ND-14）、IMU（ND-15） | 実装済み | 承認済み | 実機で一部 | VM での点群の取りこぼし（DEC-138 承認待ち） |
| 速度指令→倒し量 | gouda_motion_controller（ND-11） | 実装済み | すべて承認済み（§3） | ソフト試験合格（TS-07・13） | 不感帯の補償（DEC-171）と後退の正規化（DEC-172）は未実装（許可待ち）。実機未試験 |
| ESP32 との通信 | vehicle_bridge（ND-12） | 実装済み | すべて承認済み（§2） | ソフト試験合格（TS-13・19 の PC 側、TS-29・30、再接続） | 実機未試験。事前地図作成での configure（DEC-169）は未実装（許可待ち） |
| 車体側 | ESP32 firmware（ND-17） | 実装済み、人が書き込み済み（人の申告） | PRM-43〜49 すべて承認済み | ホスト試験のみ | 卓上の TS-17〜19、VL-01、DEC-050 の実機照合、1 mV の非対称（handover §5 の 4） |
| 反映 | VM `~/gouda_ws`、x86 機（実車 PC） | — | — | — | 両方とも a9554a1 が入っていない（VM は 3341602 のまま、x86 機は未反映） |
| 実車投入 | — | — | — | 実車試験は未実施 | 人の判断待ち |

要約: **ソフトウェアの骨組み（モード、Nav2 の起動と goal、速度上限、車体出力）はできている。** 実車で自律走行するのを止めているものは次の 3 つ。

1. **ND-07（大域の自己位置）が未実装**。方式の決定（DEC-115）が先。
2. **Nav2 の実車の値（PRM-11・17・18・66〜73）が未確定**。Nav2 が起動しない。
3. **Nav2 で使える 2D 地図がない**。変換の設定値（DEC-098）と床の反射（DEC-107）の判断が要る。

その次に、車体出力の実機試験（卓上の TS-17〜19、DEC-050）と、VM・x86 機への反映が要る。

## 2. vehicle_bridge（ND-12）は完成しているか

**工程 5-5 の範囲のソフトウェアとしては完成している。ESP32 実機・車体での確認がまだなので、実車で使えることは確かめていない。**

できていること（`gouda_core/gouda_core/vehicle_bridge_node.py`、`vehicle_core.py`、`esp32_protocol.py`）:

| 機能 | 内容 | 根拠 |
|---|---|---|
| lifecycle | configure でポートを開き、HELLO を送る。HELLO_REPLY の boot_token を受けたら SET_CONFIG で firmware の設定を登録する。active の間だけ COMMAND を送る | `vehicle_bridge_node.py:199-258` |
| 周期送信 | active の間、PRM-14（0.1 s）ごとに COMMAND を送る。cmd_vel が来ていなくても送り続ける。joystick_command が PRM-09（0.35 s）より古いときは中立を送り、古い非中立の値は送らない | `vehicle_core.py:96-108` |
| 軸の対応 | x＝−turn×10000、y＝forward×10000 | `vehicle_core.py:52-53` |
| 書き込み | 待たない方式。O_NONBLOCK の fd に os.write し、OS のバッファに入らない分は捨てる（DEC-174） | `vehicle_bridge_node.py:142-162` |
| 再接続 | USB が抜けたら記録してポートを閉じる。udev のイベントで同じ by-id 名を開き直し、HELLO からやり直す。lifecycle は変えない（DEC-176） | `vehicle_bridge_node.py:260-279`、`SerialTransport`（同 69-174） |
| ESP32 の再起動 | uptime が戻る、または boot イベントを受けたらセッションをやり直す | `vehicle_bridge_node.py:321-343` |
| 表示 | STATUS を /esp32/status に出す。USB の切断回数を vehicle/link_status に出す（DEC-177） | `vehicle_bridge_node.py:289-319, 345-358` |
| 設定値 | PRM-09 0.35 s、PRM-14 0.1 s、PRM-61（CP2102N の by-id）。すべて承認済み（DEC-166） | `generated/params/vehicle_bridge.yaml` |

試験: 単体試験は test_vehicle_core 22 件、再接続・by-id・送信・切断回数 14 件。gouda_core 全体は VM で 216 件合格（第82便の時点）。VM での結合試験（第76・79・80便）。ESP32 実機・車体では未実行。

残り:
- 実機で確かめること: 卓上の TS-17〜19、VL-01（ポートを開くと ESP32 がリセットされるか）、軸の符号（x の向き、Q-03）、DEC-050 の実機照合。
- 許可待ちの実装: 事前地図作成でも configure する（DEC-169。handover §5 の 1）。今は手動走行・事前地図作成では unconfigured なので、ポートを開かない。そのため次のことができない: STATUS の表示、ゲームパッドの指令の rosbag への記録、事前地図作成中の切断回数。
- 安全の前提（PC 側では保証しない）: 手動の優先（RQ-I023）と、PC の指令が途絶えたときの中立化（PRM-13 の 1.0 s）は firmware が受け持つ。bridge が中立を送っても、車体が止まることは保証しない（CLAUDE.md 1.5）。

## 3. gouda_motion_controller（ND-11）の状況

**基本の機能（cmd_vel を倒し量に直す、中立化の条件）は実装済みで、ソフト試験に合格している。設定値はすべて承認済み。人が方針を承認した 2 つの改良（不感帯の補償、後退の正規化）は、実装の許可を待っている。実機は未試験。**

### 3.1 今の動き（`motion_core.py`、`motion_controller_node.py`）

- 入力: cmd_vel（TwistStamped、IFD-15）と control/motion_hold（IFD-40、transient_local）。出力: vehicle/joystick_command（Joy、axes[0]＝前進、axes[1]＝旋回、[−1, 1]）。周期は PRM-41（0.05 s）で、active の間だけ出す。
- 中立を出す条件（`motion_core.py:77-90`）: hold を一度も受けていない、hold＝true、hold が PRM-42（0.5 s）より古い、cmd_vel を一度も受けていない、cmd_vel が PRM-08（0.7 s）より古い、値が有限でない。hold＝false で新しい cmd_vel があるときだけ非中立を出す。
- 正規化（`motion_core.py:91-92`）: 前進＝linear.x／PRM-39（1.111 m/s）、旋回＝angular.z／PRM-40（0.97 rad/s）。どちらも [−1, 1] で頭打ち。速度を下げるのは Nav2 の SpeedFilter だけで、この node は速度を下げない（RQ-I020）。
- lifecycle: 起動時は unconfigured。TR-05 で mode_manager が configure・activate し、TR-11・12 で deactivate する。inactive の間は何も出さない。
- 記録: 出力の理由が変わるたびに log/decision に DecisionEvent を出す。

### 3.2 設定値（`generated/params/gouda_motion_controller.yaml`、すべて承認済み）

| PRM | キー | 値 |
|---|---|---|
| PRM-08 | cmd_vel_timeout_s | 0.7 s |
| PRM-39 | max_linear_speed_mps | 1.111 m/s（4 km/h） |
| PRM-40 | max_angular_speed_radps | 0.97 rad/s |
| PRM-41 | command_publish_period_s | 0.05 s |
| PRM-42 | motion_hold_timeout_s | 0.5 s |
| PRM-78 | max_reverse_speed_mps | 0.472 m/s（ファイルにはあるが、node は宣言も使用もしていない） |

### 3.3 試験

- test_motion_core 9 件（TS-07・TS-13 の中核）。Ubuntu の ROS で 5-5 合格（status.md）。5-6 の VM の試験（2026-10-17、loopback_sim、FILE-STAGE56-VM-TEST）で ND-11 のどこまでを確かめたかは、この調査では確認していない。
- 実機（ESP32・車体）では未実行。

### 3.4 足りないもの（handover §5）

| 項目 | 内容 | 状態 |
|---|---|---|
| 不感帯の補償（DEC-171 案 A） | 倒し量 r＞0 のとき、出力＝最低倒し量＋(1−最低倒し量)×r。小さなしきい値より下は中立のまま。自律走行の指令だけにかかる | 方針は承認済み、実装は許可待ち。最低倒し量・しきい値は新しい PRM で、値は実測（前進・後退・旋回） |
| 後退の正規化（DEC-172） | 後退は PRM-78（0.472 m/s）で割る。今は前後とも 1.111 で割るので、−0.47 m/s の指令が倒し量 −0.42 になり、実際は約 0.2 m/s しか出ない（計算。実測していない） | 値は承認済み、使う実装は許可待ち。Nav2 の RPP は allow_reversing false なので、後退は主に behavior の backup で出る |
| 実機の確認 | 倒し量と実速度の対応、軸の符号 | 未実施 |

注意（推測を含む）: 不感帯の補償が入るまでは、Nav2 が出す低い速度（SpeedFilter で下げた区間、動き出し）で車椅子が動かない可能性がある。動くかどうかは実測していない。

## 4. 人の判断があれば進められる順序（案）

1. Nav2 を実車で起動できるようにする。PRM-11・17・18・66〜73 の値を決める（Q-06、Q-04）。ここで「まず Nav2 で自律走行させてみよう」（DEC-171 の人の発言）の進め方を決めると、ND-07 を待たずに試験の構成（地図なし、odom 基準の短い goal）を検討できる。ただし TR-05 は ND-07 を必須にしているので、この構成は今の契約の外になり、承認事項になる。
2. ND-07 の方式を決める（DEC-115）。そのあと実装の許可。
3. 2D 地図の設定値（DEC-098）と床の反射（DEC-107）を決める。
4. 車体出力の卓上試験（TS-17〜19、VL-01、DEC-050）。そのあと motion_controller の 2 つの改良（値は実測）。
5. VM・x86 機への反映。

どれも承認・実測・人の作業で、AI が単独で決めてよいものはない。
