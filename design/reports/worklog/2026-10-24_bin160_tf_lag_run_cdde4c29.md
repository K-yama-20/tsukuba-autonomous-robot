# 第160便 作業記録：run-cdde4c29 が走った後に止まった原因（読むだけ）

- 日付：2026-10-24
- 読んだコミット：1d7ee4663687a69ba101121964757405ff16cc00（作業ツリーに未コミットの変更あり）
- 人の発言（原文）：「直近のランで、車は動いたがしばらくして停止した。地図がどんどん遅れちゃったのかな」
- 変更：コード・設定・正本は変えていない。VM の Gouda には触れていない

## 1. 対象

- VM の `records/20261024_032654`。Gouda は 03:2x に人が起動し直していた（pgid 13017）。ESP32 も再起動されていた（esp_ms 35671 at 03:26:55、boot_token 0x6ea94676）。第159便の seq の棄却は出ていない（pc_frame_rejected 0 件、各走行の開始の直後に pc_enabled）
- 自律走行は 3 回：run-3aefb819（03:26:55〜03:27:49、人が終了）、run-408d2263（03:28:37〜03:29:29、人が終了）、**run-cdde4c29（03:30:01〜、止まった走行）**
- 証拠：`design/research/vehicle_pc/2026-10-24_autonomy_stop_run-cdde4c29/`（decision_timeline.txt、nav2_log_033043_033110.txt。NTRIP の情報がないことを grep で確かめた）

## 2. run-cdde4c29 の時系列（確認した事実）

| 時刻 | 出来事 |
|---|---|
| 03:30:01.148 | 車体出力を最初に有効化（DEC-391）。01.302 に pc_enabled |
| 03:30:44 | 自己位置推定 正常 |
| 03:30:48.35 | Nav2 起動・goal・motion_hold 解除（速度上限 0.9 m/s） |
| 03:30:49.87 | RPP「detected collision ahead」→「Controller patience exceeded」→ 回復（costmap 消去、spin は「Collision Ahead」で失敗、wait 5 s） |
| 03:30:55.66 | 再び collision ahead → 回復（backup） |
| 03:30:56〜03:31:07 | 走行。waypoint を 3 つ過ぎた（残り 23 → 20、区間 2） |
| 03:31:07.94 | **tf_help「Transform data too old when converting from map to odom」**（経路の時刻 …267.921、map→odom の最新 …267.534、差 0.39 s）→「Failed to transform end pose to global frame」→ 中止 |
| 03:31:07.98 | error_code 102（FollowPath の TF_ERROR）で TR-07、一時停止（stop_reason は plan_failure と記録） |
| 03:31:09.9 | 推定不能（NVTL 2.17 < 2.3）が 0.7 s。03:31:10.6 に正常へ戻る |
| 03:32:22 | 人が終了 |

## 3. 「地図がどんどん遅れた」か

- 答え：**どんどん（累積して）遅れたのではなく、走っている途中で一瞬遅れた**（確認した事実）
  - local costmap の CostmapFilter のエラー文から出した map→odom の遅れ（goal から の秒数）：0〜15 s は 0.12〜0.15 s で一定。16.3 s に 0.33 s、19.9 s に 0.24 s、21.1 s に 0.64 s、22.3 s に 0.35 s。23 s 以後（停止後）は 0.13 s に戻った
  - 止まった瞬間（19.6 s）の差は 0.39 s。Nav2 の controller の許容（local costmap の transform_tolerance。upstream の params に書かれておらず、Jazzy の既定値 0.3 s と推測、ソースは未照合）を超えた
  - EKF の「Twist delay」（GLIM の odometry が秒単位で遅れる警告）は今回は出ていない。第157便の停止の後のような数秒の遅れには育っていない
- 仕組み（第157便と同じ）：map→odom は GLIM の odometry の時刻で出しているので、GLIM の出力が一瞬遅れると map→odom が古くなる。地図そのもの（NDT の位置合わせ）は合っていた（NVTL 3.2、止まった後の短い推定不能を除く）
- 「地図」という言葉の対応：人が言う「地図が遅れる」は、ここでは「地図の座標（map）から見た車の位置の更新（map→odom）が遅れる」ことにあたる、と解釈した（推測）

## 4. 遅れの原因の候補（推測を含む）

- CPU 不足：controller の周期は 7.8〜10 Hz（平均 10.2 Hz、設定 20 Hz）。load average は 03:33 に 1 分 6.7・5 分 8.3（6 コア）
- **gouda_monitor の主の thread が CPU 100 %**（`top -H` で 1 thread が 99.9 %、待機中の 03:33 でも）。ブラウザ（Isolated Web Co 27 %、firefox 9 %）も使っている。monitor は IMU（sensors/imu/data）・GNSS・decision・esp32/status などを Python で購読している。どの購読が重いかは未調査（`ros2 topic hz /sensors/imu/data` は約 100 Hz と出たが、測る側も Python なので低く出ている可能性がある）
- 走り出しの collision ahead：開始の直後に前に障害物（人の可能性）があり、回復が 2 回走った。停止の原因ではない

## 5. 承認・確認の候補（まだ DEC にしていない。第157便の B・C の続き）

- B'（調査、承認不要の範囲）：gouda_monitor が CPU 100 % になる原因を調べる（どの callback か。読むだけ・計測だけ）
- C（設計）：map→odom を GLIM の odometry の時刻で出す設計（DEC-285）と、Nav2 の TF の許容の関係を見直す。たとえば map→odom を一定の周期で今の時刻で出し直す（AMCL などと同じ考え方）。安全に関わる（keepout のフィルタの失敗も同じ原因）
- transform_tolerance を延ばす案は、1.5 の「timeout の延長で通す」にあたるおそれがあるので、推奨しない（人が判断する場合は承認事項）
- 第159便の F（bridge の seq）・G・H は未回答のまま

## 6. 実行した検査・試験

- 試験・設計検査：未実行（記録の読み取りだけ）
- コマンド（VM で読むだけ）：events.jsonl と launch log の集計（python）、a3・glim の log の grep、`top -b -n1`、`top -b -n1 -H -p <gouda_monitor>`、`ros2 topic hz /sensors/imu/data`（12 s）

## 7. 残るリスク

- C を直すか CPU を減らすまで、走るたびに数十秒で同じ停止が起きうる
- 停止の理由が plan_failure と記録される（第157便の D）

## 8. 次に進められる作業／止まっている作業

- 進められる：B'（monitor の CPU の原因の調査、読むだけ）
- 止まっている：C・D・F・G・H の実装（人の承認待ち）

## 9. 追記：走り出しで避けた障害物は何 m 先か（人の質問）

- 人の発言（原文）：「障害物は何メートル先のものを避けましたか？ロボットの周り数メートルの範囲は何もないひらけた場所でした」
- **距離は記録から分からない**（事実）：この session は rosbag を取っていない（`records/20261024_032654/rosbag` は空）。Nav2 の log の「RegulatedPurePursuitController detected collision ahead!」は距離を出さない。local costmap の中身も残っていない
- 分かる範囲（上流の既定値。ソースは未照合）：生成した nav2_params.yaml に RPP の衝突の設定と obstacle_max_range は書かれていないので、Jazzy の既定値が効いていると推測。障害物として costmap に入るのはセンサから 2.5 m 以内（obstacle_max_range、DEC-337 で既定値のまま）。RPP の衝突の検査は経路の先の 1.0 s ぶん（max_allowed_time_to_collision_up_to_carrot）まで
- 同じ「collision ahead」は run-408d2263 の 03:29:26〜27 にも出ていた（その 2 s 後に人が終了）。2 回とも走り出しの直後
- **ひらけた場所で障害物が出る理由の有力な候補**（事実＋推測）：
  - 障害物の高さの帯（PRM-70 −0.065 m・PRM-71 1.085 m）は正本では base_link 基準だが、Nav2 は costmap の座標（local は odom、global は map）の z で当てている（実行時の nav2_params.yaml で確認。既知の不一致、DEC-336 が承認待ち）
  - odom・map の z の原点は GLIM の起点（IMU の高さ）にある。根拠：初期位置の高さが map で −0.84〜−0.93 m（03:26〜03:30 の initial_pose_received・aligned）、第157便の「Sensor origin」の z が −0.03〜0.00 m。IMU は base_link の 0.935 m 上（sensor_config.json）、base_link は地面の 0.165 m 上（PRM-05、記載値）
  - そのため、実際に障害物として扱われているのは **地面から約 1.0〜2.2 m の高さ** の物（推測の換算：帯 −0.065〜1.085 m ＋ 地面から odom の原点まで約 1.10 m）。地面から 1 m より低い物は見えていない
  - ひらけた場所でこの高さに入るのは、そばに立っている人（随行・チームの人の胴や頭、2.5 m 以内）、木の枝、車体の上の方の部品などが考えられる。どれかは記録がないので分からない
- 安全の面：低い障害物（コーン・縁石・座っている人など）が local・global の costmap に入らない可能性が高い。DEC-336 の判断が急ぐ
- 次に同じことを調べるには：自律走行のときに rosbag（points、tf、local_costmap）を取ってもらう（人の操作）
