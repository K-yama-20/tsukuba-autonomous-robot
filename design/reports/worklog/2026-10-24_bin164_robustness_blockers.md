# 第164便 作業記録：ロバストな自律走行を妨げる設定・構成の列挙（読むだけ、実装なし）

- 日付：2026-10-24
- 読んだコミット：1d7ee4663687a69ba101121964757405ff16cc00（作業ツリーに未コミットの変更あり）
- 人の発言（原文）：「進んでいないことの判定が厳しすぎるのと、plannerが20ms以内に返さないと落ちるってのもひどい話だ。実装はせず、プログラムを呼んで、ロバスト性の高い自律走行の妨げとなるような設定やシステム構成を列挙せよ。障害物があったのは確か（私が前を一回か二回通り過ぎたりした。すぐ止まった。）だが、経路を再計画するのがめちゃくちゃ遅い気がする」
  - 「プログラムを呼んで」は「プログラムを読んで」と解釈した
- 読んだもの：VM の実行時の `run/nav2/nav2_params.yaml`・`navigate_through_poses.xml`（写しを `design/research/vehicle_pc/2026-10-24_nav2_runtime_config/` に保存）、`mode_manager_node.py` の一時停止の扱い、第157〜163便の記録
- 変更：コード・設定・正本は変えていない
- 「上流の既定値」と書いたものは、生成した params に書かれていないので Jazzy の既定値が効いていると推測したもの（上流のソースとは未照合）

## 0. 人の指摘への答え

1. 「進んでいない判定が厳しい」：そのとおり。0.5 m を 10 s で動かないと失敗（B-2）。人が前を通って待っただけでも失敗し、回復（旋回・後退）に入る
2. 「20 ms で落ちる」：そのとおり。しかも落ちたときに回復を一度も試さない（A-1）。9999999 回の再試行の設定が効かない
3. 「再計画が遅い」：再計画そのもの（1 Hz）より、(a) 障害物を見ると 0.3 s で追従をやめる（B-1）、(b) 人が去っても障害物の印が消えない（C-1）、(c) 消すのは失敗の後の回復だけ（A-3）、が重なって、止まってから動き出すまで 10 s 以上かかっている、と考える

## A. Nav2 の BT・失敗の扱い

| ID | 設定・構成 | 今の値・場所 | 何が起きるか | 根拠 |
|---|---|---|---|---|
| A-1 | BT の外側の回復が、error_code の分かる失敗にしか効かない | BT の RecoveryNode の回復側が `WouldAControllerRecoveryHelp` / `WouldAPlannerRecoveryHelp` の Fallback から始まる（上流の BT のまま） | 受け付けの時間切れなど error_code のない失敗では回復を 1 回も試さず、goal 全体が失敗する。`number_of_retries` 9999999（PRM-18）が効かない | 第163便：「Timed out while waiting for action server to acknowledge goal request for compute_path_through_poses」の 0.04 s 後に「Goal failed」、error_code 0 |
| A-2 | BT が action server の受け付けを待つ時間 | `default_server_timeout: 20`（ms、上流の既定値） | 一時的に処理が詰まると（controller が 1.6 Hz まで落ちた時間がある）、BT の action の呼び出しが失敗する | 第163便 |
| A-3 | 障害物の印を消すのが、失敗の後の回復だけ | BT：ClearEntireCostmap は FollowPath・ComputePath の失敗の後と回復の列にだけある | 誤った・古い障害物は、失敗→回復の順を踏むまで消えない | BT |
| A-4 | 回復の中身が、人のそばでは不利 | RoundRobin：消去 → Spin 1.57 rad → Wait 5 s → BackUp 0.30 m | 人が前にいるとき、その場で 90° 回る・後ろに下がる。第163便では BackUp は Collision Ahead で中止 | BT、第160・163便 |
| A-5 | 経路の計画の失敗の回復は 1 回だけ | 内側の RecoveryNode `number_of_retries="1"`（ComputePathThroughPoses、FollowPath） | 1 回の失敗で外側の回復の列に落ちる | BT |

## B. 追従（controller）と進みの監視

| ID | 設定 | 今の値 | 何が起きるか | 根拠 |
|---|---|---|---|---|
| B-1 | controller の失敗の許容 | `failure_tolerance: 0.3`（s、上流の雛形） | RPP が「collision ahead」を出すと 0.3 s で FollowPath を中止。1 Hz の再計画で避ける経路が来る前に失敗する | 第160・163便：「Controller patience exceeded」が collision ahead の 0.2 s 後 |
| B-2 | 進みの監視 | SimpleProgressChecker 0.5 m／10 s（上流の雛形） | 人を待つ・ゆっくり避けるだけで失敗。回復に入る | 第157・163便：「Failed to make progress」 |
| B-3 | RPP は障害物を避けない | FollowPath は RegulatedPurePursuit。衝突の検査（上流の既定値：経路の先 1 s ぶん）で止まるだけ | 避けるのは global の再計画（1 Hz）の仕事になり、その前に B-1 で落ちる | 設定 |
| B-4 | RPP の多くの値が上流の既定値（未承認） | lookahead・衝突の検査の時間・コストによる減速など | 実車に合っているか分からない | DEC-371 が承認待ち |
| B-5 | controller の周期 | 設定 20 Hz、実際は平均 10 Hz、最低 1.6 Hz | 追従が粗い。時間切れの元 | 第157・160・163便 |

## C. 障害物の検出と消去（costmap）

| ID | 設定 | 今の値 | 何が起きるか | 根拠 |
|---|---|---|---|---|
| C-1 | 高さの帯を costmap の座標の z で当てている | `min/max_obstacle_height` −0.065／1.085 m を odom・map の z で適用。odom・map の原点は IMU の高さ（base_link の 0.935 m 上） | 地面から約 1.0〜2.2 m の物だけを見ている。低い物（コーン・縁石）は見えない恐れ。**消す側も同じ帯の点しか使わないので、ひらけた場所では人が去った後ろにその高さの点がなく、人の印が消えない**（上流の作りの理解、ソース未照合） | DEC-336（承認待ち）、第160便 §9 |
| C-2 | local costmap が狭い | rolling 3 m × 3 m（前に 1.5 m） | 1.25 m/s で約 1.2 s 先しか見えない。急に止まる | 設定 |
| C-3 | 障害物として印を付ける距離 | `obstacle_max_range` 2.5 m・`raytrace_max_range` 3.0 m（上流の既定値） | 遠くの物を早く避けられない | DEC-337（承認待ち） |
| C-4 | 1 点でも印が付く | voxel layer `mark_threshold: 0` | 雑音の 1 点でも障害物になる | 設定 |
| C-5 | local の keepout フィルタが毎周期 TF で失敗 | KeepoutFilter（local）と、odometry の時刻で出す map→odom | local では立入禁止が効いていない可能性 | 第157便 3.3-1 |
| C-6 | global costmap の更新 | `update_frequency: 1.0` | 障害物の変化が経路に入るまで最大 1 s | 設定 |
| C-7 | voxel layer の高さの範囲 | `origin_z: 0.0`、0〜1.085 m（odom の z） | センサの z が 0 を少し下回ると raytrace できない（第157便で発生。第163便では出ていない） | 第157便 |

## D. 再計画（global planner）

| ID | 設定 | 今の値 | 何が起きるか | 根拠 |
|---|---|---|---|---|
| D-1 | 再計画の頻度 | RateController 1 Hz（PRM-103、暫定） | 新しい障害物を避ける経路まで最大 1 s ＋ global costmap の更新（C-6） | 設定 |
| D-2 | 残りの全 waypoint を毎回まとめて計画 | ComputePathThroughPoses（25 点）、NavFn（`use_astar: false`）、地図全体 | 1 回の計画が重い（時間は未測定） | 設定 |
| D-3 | 未知の所を通れる | NavFn `allow_unknown: true`、`track_unknown_space: true` | 見えていない所を通る経路を出しうる | 設定 |
| D-4 | 膨らませ | inflation 1.0 m、cost_scaling 3.0（PRM-72 ほか） | 狭い所で経路が出にくい・壁から離れすぎる | 設定 |

## E. Gouda の状態遷移

| ID | 構成 | 今の作り | 何が起きるか | 根拠 |
|---|---|---|---|---|
| E-1 | Nav2 の goal の失敗で必ず一時停止 | `_on_nav_result`：成功・取消以外はすべて TR-07 で一時停止 | 再開には人の操作が要る。規則では人の操作は走行失敗（DEC-345）。Gouda から goal を出し直さない | mode_manager_node.py:502〜、DEC-340・342（承認待ち） |
| E-2 | 推定不能 1 回で一時停止 | `_on_estimator_status`：正常でない状態を 1 回受けたら TR-07 | 0.1〜0.7 s の短い推定不能（NVTL 2.17、EKF の σ 0.70〜0.79 m）でも止まる | 第160便 03:31:09、第163便 04:25:36、DEC-342・365（承認待ち） |
| E-3 | 推定不能の門の値 | PRM-92 0.7 m（暫定）、PRM-90 NVTL 2.3、PRM-93 1.0 s | 止まっている間にも σ が 0.7 m を行き来する | 第163便 |
| E-4 | 停止の理由の名前 | error_code に関係なく `plan_failure` | 原因の切り分けを誤らせる | 第157便 D |

## F. 自己位置と TF

| ID | 構成 | 今の作り | 何が起きるか | 根拠 |
|---|---|---|---|---|
| F-1 | map→odom の時刻 | GLIM の odometry の時刻で出す（DEC-285） | GLIM が一瞬遅れると Nav2 の TF の許容を超える（TF_ERROR 102） | 第157・160便（第163便では出ていない） |
| F-2 | オドメトリの源が GLIM だけ | 車輪のエンコーダなし、IMU は GLIM の中だけ | LiDAR の途切れ・処理の遅れがそのまま位置の遅れになる | 第142便 |

## G. 計算機・ソフトの構成

| ID | 構成 | 今の作り | 何が起きるか | 根拠 |
|---|---|---|---|---|
| G-1 | VM（6 コア）にすべてを載せている | Parallels の Ubuntu。GLIM・NDT・EKF・Nav2・monitor・ブラウザ・ドライバ | 一時的な詰まり（A-2・B-5・F-1）の元 | 第157〜163便 |
| G-2 | rclpy の MultiThreadedExecutor | mode_manager（3）・global_localization（3）・map_creator（2）。monitor は第162便で単一に変更 | 1 通ごとの手間が大きい（monitor で 4 倍） | 第161便 |
| G-3 | 走行中の記録が足りない | rosbag は自動で取らない（意図どおり）。costmap・cmd_vel・CPU の記録がない | 止まった原因（何を障害物と見たか）が分からない | 第160・163便 |

## H. 車体との通信

| ID | 構成 | 今の作り | 何が起きるか | 根拠 |
|---|---|---|---|---|
| H-1 | bridge の seq が Gouda の再起動で 1 から | ESP32 は同じ起動の間、最後の seq を覚える | Gouda だけ再起動すると、指令がすべて棄却される | 第159便の F（承認待ち） |
| H-2 | 走り出しの条件に ESP32 の受け付けを見ていない | motion_hold の解除は速度上限と keepout の確認だけ | 受け付けられていないのに Nav2 が走ったつもりになり、進みの監視が失敗する | 第159便の G（承認待ち） |

## 優先の案（推測を含む。どれも承認事項）

1. E-1・A-1・A-2：失敗で止まらない作り（Nav2 の失敗の後に Gouda が goal を出し直す、BT の回復を error_code に関係なく試す、時間切れを詰まりに強くする）。完走に直接効く
2. C-1（DEC-336）：誤った障害物と消えない印。安全（低い物）にも効く
3. B-1・B-2・A-4：人を待てる進みの監視と、人のそばで旋回・後退しない回復
4. E-2・E-3：短い推定不能で止まらない（DEC-342・365）
5. G-3：走行のたびに costmap・cmd_vel・CPU を記録する（原因を確かめるため）

- timeout を延ばすだけで通す案（A-2・F-1）は 1.5 の禁止にあたるおそれがあるので、単独では推奨しない。詰まりの原因（G-1・G-2）と、時間切れの後に回復する作り（A-1・E-1）を先に考える

## 実行した検査・試験

- 試験・設計検査：未実行（読むだけ）
- コマンド（VM で読むだけ）：`run/nav2/` の 4 ファイルの cat、launch log の集計（python）、scp で写しを保存
