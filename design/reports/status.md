# 現状の要約（status.md）

最終更新：2026-11-02（第178便。REV-190、第177便。REV-189、第176便。REV-186〜188、第169〜171・174・175便。REV-185・第167〜168便は 2026-11-01。REV-184・第166便は 2026-10-26。REV-176〜183・第152〜165便は 2026-10-24）。

**第270便: MID-360 の 2 本のブランチを統合ブランチに merge（REV-295、DEC-528）**（作業記録 `reports/worklog/2026-11-07_bin270_integrate_mid360_a1_status.md`）。
- 人の回答「merge して」。chat/mid360-a1-2026-11-07（第235便の A1・第264便）と chat/mid360-status-2026-11-07（第252便）を fast-forward で入れた（9acdc7f → 4e6bbb6）。共有の作業ツリーの同じ中身の写しは退避してから片付けた。
- REV-288・REV-278 の当て直しで model.yaml が一致。生成物は変わらず。単体試験 498 件 OK（skip 35）、設計検査 違反0件・未判定5件（FAIL は前からの drawio・.DS_Store だけ）。push・Dell の setup.sh・車載 PC への反映は未実行。

**第252便: MID-360 の状態・温度・診断コードを log と rosbag に記録（REV-278、DEC-494 の A）**（作業記録 `reports/worklog/2026-11-07_bin252_mid360_status_record.md`、ブランチ `chat/mid360-status-2026-11-07`）。
- 人の回答「A で進める」。setup.sh が livox_ros_driver2 の写しにだけ patch（`third_party/patches/livox_ros_driver2/`）を当て、状態の通知を `/diagnostics`（name mid360、許可した 14 項目、シリアル番号・アドレスなし）に出す。gouda_recorder がそれを log に書く。走行の判断には使わない（DEC-456）。
- 単体試験 Mac 498 件 OK（skip 35）、patch の試験 148 checks 失敗 0、設計検査 違反0件・未判定5件。センサーをつないだ確認・Dell での setup.sh は未実行。統合ブランチへの merge は統合の担当。

**第264便: 第235便の A1（ドライバを colcon で作る）を第252便より先にコミット（REV-288、DEC-515）**（作業記録 `reports/worklog/2026-11-07_bin264_mid360_a1_commit.md`、ブランチ chat/mid360-a1-2026-11-07）。
- 人の回答「A1 を先にする」。setup.sh・README.md・third_party/drivers.repos の A1 だけの差分を 9acdc7f の上に作った。setup.sh の sha256 は A1 がワークステーションで試した版と一致。第252便は、この上に差分を作り直す。
- bash -n OK、tests/test_update_sh.py 9 件 OK、設計検査 違反0件・未判定5件。Dell での setup.sh（人、A2）は統合の後。push はしない。

**第255便: 共有の作業ツリーの未コミットの変更を便ごとにコミット（REV-281、DEC-499）**（作業記録 `reports/worklog/2026-11-07_bin255_shared_tree_commits.md`）。
- 人の指示（DEC-499）で、9c449b5 の上に 2702b0b〜99a5be6 の 36 件（第184〜254便。第220便は dev-tab 系統 69631f8 を第二の親にした merge）。model.yaml・生成物・検査の報告・status.md は最後の 99a5be6 に 1 つ。push はしていない。
- 残した：第252便（recorder、patch、setup.sh・README.md・drivers.repos は第235便の分と重なる）、第257便（reserve_ids.py の新版など）、第218便（gpu_sim、REV-244）、予約だけの REV-192・278・282、人の drawio の控え。
- 99a5be6 で単体試験 489 件 OK（skip 35）、設計検査 違反0件・未判定5件（FAIL は前からの drawio・.DS_Store だけ）。車載 PC には接続していない。

**第251便: 植え込みの手前・途中から、いろいろな向きで始めても抜けられるかの模擬（試験のみ、issue #102）**（作業記録 `reports/worklog/2026-11-07_bin251_planting_start_poses.md`）。
- 48 姿勢（P2・P1・PM・PM2、内側へ 0.7 m のずらし 2 か所 × 8 向き）を 1 倍速で回した：合格 38、不合格 8、未判定 1、未実行 1。外側の壁向き・逆向き・角を曲がった後は全部合格。
- 不合格はどれも内側向きか内側へずらした位置：A 角で曲がりきれず外側の壁へ（MPPI の Optimizer fail、cmd_v 0.675＝0.27×1.25/0.5 で平ら、計算）、B 始めの旋回で前の角が植え込みを掃く（植え込みは 2 m より近いと XT-32 に映らない、計算）。
- 試験専用のファイルだけ（新規 2 件、drive_sim_course.py に差し込み口 4 行）。製品・正本・生成物は変えていない。原本未照合。コミットはまだ。

**第257便: 番号の予約を全 worktree で共有にする、worktree 運用の案（DEC-499）**（作業記録 `reports/worklog/2026-11-07_bin257_shared_reservations_worktree_proposal.md`）。
- 基盤：`tools/reserve_ids.py` の印を git の common dir（`.git/gouda-reservations/`、全 worktree で共有）に移し、PRM・IFD・ND も予約できるようにした（`--prm --ifd --nd --design`）。単体試験 15 件 OK。設計の単体試験の全体は 98 件のうち失敗 1 件（drawio などの hash、道具とは別）。`run_checks.py` は未実行（未判定）。
- 提案：`proposals/worktree_operation_2026-11-07.md`（CLAUDE.md の変更案、チャットの作業・統合・車載 PC への反映の手順）。人の回答「推奨どおりで」（DEC-501、REV-283 適用済み。設計検査 違反0件・未判定5件、FAIL は前からの drawio・.DS_Store だけ）。CLAUDE.md に 1.14 節などを入れ、`.gitattributes` に status.md の union merge、`update.sh` に `<ブランチ> <コミット>` の引数を足した（試験 9 件 OK、Mac の一時のリポジトリ。車載 PC では未実行）。push・車載 PC の退避と checkout・統合の道具は未実行。コミット：`c37020e`（道具・提案）、`e42c79b`（REV-283・update.sh・.gitattributes）。

**第250便: MID-360 なしで起動・走行できるかの確認（試験のみ、#95・#96）**（作業記録 `reports/worklog/2026-11-07_bin250_no_mid360_startup_check.md`）。
- ワークステーションの模擬（今の作業ツリー）で、ドライバなし（A）、ドライバあり・設定なし（B）、設定あり・機器なし（C）、壊れた mid360.json（D1）の 4 本ともゴールに着いた。MID-360 による Traceback・ノードの終了はなし。D2〜D5 は判定の関数だけで、例外なし。
- C ではドライバが `Init lds lidar fail!` のまま動き続け、層は入ったまま走れた。停止のときドライバは SIGKILL まで止まらない（約 15 秒、#96）。モニタでは層の有無が見えず、launch のログの `MID-360 layer ...` の一行だけ（#95）。
- 製品・正本・生成物・試験は変えていない。車載 PC・実機は未実行。コミットはまだ。

**第248便: MPPI の速度と旋回の値を下げる（REV-276、DEC-490）**（作業記録 `reports/worklog/2026-11-07_bin248_dec490_speed_turn_values.md`）。
- 人の回答「案どおり変えて」。PRM-131 vx_max 0.8→0.5 m/s、PRM-132 wz_max 1.0→0.5、PRM-67 1.0→0.5 rad/s、PRM-73 2.0→0.5 rad/s²。旋回の PI 0 は人が /config で入れる。
- 設計検査 違反0件・未判定5件、単体試験 Mac 462 件 OK（skip 35）。試験の期待値 1 件を DEC-490 に合わせた。車載 PC への反映・実車・コミットはまだ。
- 静止コーンの模擬（32 本、`research/vehicle_pc/2026-11-07_static_cone_sim/`）：新しい値で経路の上・横のコーンは 15/15 回避（間隔 0.40 m 以上）。前の値は経路の真上で接触。waypoint の真上のコーンはどの条件でも接触（vx_min で止まれない、#98）。

**第247便: DEC-476〜479 への回答の記録と、DEC-479 の記録の方法（REV-274、DEC-494、#93）**（作業記録 `reports/worklog/2026-11-07_bin247_dec476_479_answers.md`）。
- 人の回答「水書で問題ない。但し、DEC-479はlogまたはrosbagに記録」（「水書」は「推奨」と読んだ。推測）。DEC-476〜478 は推奨のまま（MID-360 の内蔵 IMU は出したまま走行中は使わない。単位と frame は使うときに決める）。DEC-479 は状態・温度・診断コードを記録する。
- 上流のドライバは状態の通知を ROS に出さない。別のプロセスの SDK は点群・IMU の送り先を奪う恐れがある。記録の方法を DEC-494 で問うた（推奨：ドライバの写しに patch → /diagnostics → rosbag と gouda_recorder の log）。
- 設計検査 違反0件・未判定5件（FAIL は前からの drawio・.DS_Store だけ）。コード・設定は変えていない。コミットはまだ。

**第238便: 確認走行区間の手書きの図を模擬のコースにして、ルールどおりゴールまで行けるかを試す**（作業記録 `reports/worklog/2026-11-07_bin238_confirmation_course_sim.md`、issue #94）。
- 人の指示「…これをモデル化し、本当にゴールまでルール通りたどり着けるか、workstationでシミュレーションせよ。二倍速で試験。」。400 m のコース（幅・寸法の多くは仮定。規則は原本未照合）を試験専用の `drive_sim_course.py`・`.sh` で作った。ワークステーションと車載 PC（x86、模擬だけ）で計 37 本（free 4、全コース 9、コーン区間 22、一時停止線を含む 2）。
- 結果：全本ゴールに着き、自動の待機・3 分の滞留はなし。ただし高さ 0.7 m の緑のコーンには全本（全コース 7/7、コーン区間 22/22、停止線つき 2/2）が当たった（375 m・392 m）。印の距離 5 m・区間の制限 0.8・MPPI の下限 0.01 でも消えず、高さ 1.3 m（XT-32 から消えない）のときだけ 0。一時停止線は 03:13 の版では素通り、第239便の仕組みを入れた今の版では止まって再開できた（前端が線を 0.09〜0.10 m 越えた。停止点は線の上）。
- 製品・正本・生成物・設定は変えていない。コミットはまだ。

**第235便: MID-360 の接続試験に向けた並列の実装（REV-259・REV-260 適用、DEC-474〜479・492）**（作業記録 `reports/worklog/2026-11-07_bin235_mid360_parallel_abdeg.md`）。
- 人の回答（DEC-474・475）で 6 つの流れを並列に実装した。
  - A1：setup.sh でドライバを build.sh でなく colcon で作る（固定の commit の写しを作る。checkout は変えない）。
  - B：T04・T05-4・T07・T08-3 の rosbag の解析（`research/vehicle_pc/2026-11-06_mid360_connection/tools/`）。
  - E：P4 でドライバだけを動かす道具（同じ場所の `tools/p4_driver/`）。
  - D：REV-260（ND-20 のモジュールの誤りなどの整合の修正と、内蔵 IMU・frame・診断の DEC-476〜479、pending）。人の回答「適用してよい」（DEC-492）で適用した。
  - G1・G2：地面分割の OSS の調査と比較（`research/ground_segmentation_2026-11-07/`、#85）。
  - 最初の試みは人の「再度最初からやり直せ」で破棄した。
- 試験と検査：
  - 単体試験：B は Mac で 62 件 OK（skip 1）、E は 19 件 OK、G2 はワークステーションで 18 件 OK。A1 はワークステーションで setup.sh の節の写しを 9 回試した。
  - 設計検査：REV-260 の適用の後も違反0件・未判定5件。
  - Dell での setup.sh（人、A2）、ROS 上での起動、実機は未実行。
- 人の判断待ち：
  - DEC-476〜479（内蔵 IMU を使うか、単位の変換、IMU の frame、診断）
  - G3（地面分割を製品に入れるか）
  - 台帳の T08-5（提案）
  - 計画 88 行の「ros2 launch のみ」
  - #87（最適化なしのビルド）・#88（上流 pointcloud_to_laserscan の配列の外への書き込み）
  - G2 が Dell の `~/gouda_ws` の下の rosbag を読んで写したこと
- その他：REV-242 のコードは未コミット。コミットはまだ。

**第246便: 停止距離の解析の準備（REV-275、DEC-495）**（作業記録 `reports/worklog/2026-11-07_bin246_stop_distance_analysis_prep.md`、スクリプト `research/vehicle_pc/2026-11-07_stop_distance/`）。
- 人の指示：停止距離は人が様々な速度で rosbag を取り、AI が読む。計測の手順は作らない。抜き出し（extract.py）と解析（stop_distance.py）を用意した（基盤。製品のコード・値は変えていない）。
- 読むには「止める合図」と「位置」が記録に要る：自律走行なら motion_hold と localization/odometry、手動なら事前地図作成モードで ESP32 の状態と GLIM の軌跡。手動走行モードだけの記録では出せない。
- 解析の単体試験 10 件 OK（合成の軌跡）。extract.py は実際の rosbag で未実行。設計検査 違反0件・未判定5件。実測待ち：DEC-346・377・378。コミットはまだ。

**第244便: DEC-488 の回答の記録（REV-271）**（作業記録 `reports/worklog/2026-11-07_bin244_dec488_answered.md`）。
- 人の回答「それでよい」：停止点は式どおり線・道路端の手前に人が置く（案 A、コード変更なし）。停止距離は未実測で、置く位置の数値は tbd（DEC-346・377）。DEC-489・DEC-343 は未回答。
- 設計検査 違反0件・未判定5件。run_checks の中で design consistency が 1 回だけ終了コード 1（単独のやり直しは 0、未解決）。コミットはまだ。

**第243便: 一時停止線の実装と規則 TK-22〜25 の照らし合わせ（REV-269、DEC-488・489）**（作業記録 `reports/worklog/2026-11-07_bin243_stop_line_rules_check.md`）。
- 第239便の実装を読んで確かめた。コード・設定は変えていない。訂正：停止線・道路端の条文（TK-22〜29）は `docs/regulations_2026.md` に原本照合済で入っている。
- 承認待ち：DEC-488（停止点を置く位置。中央は停止線の手前 0.10 m＋停止距離、道路端の手前 0.60 m＋停止距離。線の上に置くと奥側の余裕が小さい）、DEC-489（TK-25 の早めの減速。今は減速しない）。実測待ち：停止距離（DEC-346・377）。
- 単体試験 Mac 473 件 OK（skip 35）、設計検査 違反0件・未判定5件。模擬・車載 PC・実車はこの便では未実行。実車投入可能：人の判断待ち。コミットはまだ。

**第249便: MID-360 の層に残る印のたまり方の模擬、段階 2（REV-277、DEC-496、issue #97）**（作業記録 `reports/worklog/2026-11-07_bin249_blind_marks_sim_stage2.md`、証拠 `research/vehicle_pc/2026-11-07_blind_marks_sim/`）。
- 人の回答「進めて」。模擬の機械で 24 本（低い静止物・すれ違い・内側で止まる × XT-32 だけ・MID-360 の層あり × 2 回）。全部ゴール、回復動作 0 回。
- 低い静止物：XT-32 だけは 4/4 接触（印が付かない、または付いて消える）。**MID-360 の層ありでも 3/4 接触**（印は約 2 m から付いていたが、避け始めなかった。原因は未分類）。動く相手の印は最後の位置の 1 かたまりで、走行の終わりには 0。
- 「内側で止まる」の場面はねらった危険を作れていない（作り直しが要る）。その場旋回・後退は 1 回も出ていない。各条件 2 本。
- 設計検査 違反0件・未判定5件（migration の FAIL は前からの drawio・.DS_Store だけ）。未承認：#97 の案 A（避け始めない原因の調査）・B（場面の作り直し）・C（段階 3）。車載 PC・実車は未実行。実車投入可能：人の判断待ち。コミットはまだ。

**第245便: MID-360 の層に残る印のたまり方を測る模擬の道具（REV-272、DEC-493、issue #89・#90）**（作業記録 `reports/worklog/2026-11-07_bin245_blind_marks_sim_tools.md`）。
- 人の質問「死角に入った印を消さないと costmap がいっぱいになる恐れ。センサーかアルゴリズムか」への調査は #89、模擬の計画は #90。人の回答「実装して」で段階 1（試験専用の道具）だけを足した：途中で止まる物、小型ロボット大の物の場面 8 つ、残った印の数の記録、丸ごと消去の回数。製品のコード・値は変えていない。寸法と速度は仮の値。
- 単体試験 Mac 489 件 OK（skip 35、新 16 件）。設計検査 違反0件・未判定5件（migration の FAIL は前からの drawio・.DS_Store だけ）。記録の部分の ROS 上での動作・模擬の実行・車載 PC・実車は未実行。コミットはまだ。
- 人に確認中：相手の小型ロボットの寸法と速度、後退とその場旋回が出る場面。未承認：模擬の実行（段階 2・3）、#89 の案 B〜E。実車投入可能：人の判断待ち。

**第239便: 一時停止線の仕組み（REV-263、DEC-482）**（作業記録 `reports/worklog/2026-11-07_bin239_stop_line.md`）。
- 人の指示「一時停止線の仕組みをopusで実装せよ。…」。途中の waypoint で止まる実装はなかった（kind stop のデータ、TR-08、自律走行の中の段階の作りを使った）。goal を次の kind stop までで区切り、Nav2 の成功か PRM-11 の半径に入ったら自律走行のまま rule_stop_hold（stop_reason rule_stop、hold）。今の「再開」で停止点の次から。waypoint タブで印を付けられる。新しい値はない。
- 単体試験 Mac 456 件 OK（skip 35）、模擬の機械 456 件・失敗 1（前からの test_patch_copy_only_on_a_copy）。設計検査 違反0件・未判定5件。drive_sim 1 本：停止点の 0.36 m 手前で 25 s 静止（hold true）、再開で最後まで（0.03 m）。規則の原文は原本未照合。車載 PC・実車は未実行。コミットはまだ。
- 追記（REV-268、DEC-487）：止め方は「自律走行モードの中で止める」のまま（人の回答「このままでよい」）。設計検査 違反0件・未判定5件。車載 PC・実車は未実行。

**第254便: 停止点で向きを揃える動きと、停止点の置き方についての人の回答の記録（REV-280、DEC-497・498、TRB-015）**（作業記録 `reports/worklog/2026-11-07_bin254_stop_align_answers.md`、issue #99・#100）。
- 人の回答：停止点での回転は一方向でやり直さない。回転でぶつかるときだけ待ち、去ったら続ける。時間の上限 20 秒（TRB-015 に登録）。停止点は地図の目印に合わせて人が置く。目印は先に車体の位置、後で RTK（RTK の試験は人がこの後行う）。
- 実装はまだ（承認待ち）。未決：揃える向きの既定、回さない最小の角度、DEC-343・489。設計検査 違反0件・未判定5件。コード・設定は変えていない。コミットはまだ。

**第253便: 飛ばす処理の模擬（壁・通路・角・偽の点、REV-279）**（作業記録 `reports/worklog/2026-11-07_bin253_skip_sim_walls_ghosts.md`）。
- 誤って飛ばしてはいけない場面（壁・通路・人）では、偽の点 100 個でも飛ばしは 0。角の茂みは 2/2 が飛ばさずにゴール。偽の点 100 個では、飛ばす・飛ばさないに関わらず時間切れが出た（偽の点の対策は別）。
- 試験専用の drive_sim だけを変えた。コミットはまだ。

**第240便: waypoint を飛ばす処理（DEC-367・446・483、REV-235・238・264・267、PRM-137〜140、IFD-58、第211便を含む）**（作業記録 `reports/worklog/2026-11-07_bin211_waypoint_skip_impl.md`・`2026-11-07_bin240_skip_stall_by_distance.md`）。
- 人が目印（skip_allowed）を付けた waypoint だけを飛ばす。条件は次のとおり。
  - waypoint までの距離が縮まらない時間（PRM-137・140）
  - その間の recovery（出し直しをまたいで通算）
  - waypoint に置いた footprint の cost（PRM-138）が持続している（PRM-139）
  - ND-07 が正常、続けて 1 点まで
- monitor の waypoint タブで印を付ける。値は tbd で、実車では働かない。
- 模擬（仮値）：印なしの基準は 2/2 が時間切れ、印あり（仮値 25）は 2/2 がゴール、人の立ち止まりでの誤った飛ばしは 0/2。単体試験は全件 OK、設計検査は違反 0・未判定 5。実車・コミットはまだ。

**第237便: 蛇行と回避の失敗への対処の質問、速度の目標の緩和（REV-262、DEC-481）**（作業記録 `reports/worklog/2026-11-07_bin237_speed_relax_question.md`）。
- 人の発言「当初の目標1m/secを緩和して、ゆっくり動くのでも問題ないです」を記録。案：旋回の PI を止める、MPPI の vx_max・wz_max を下げる、MPPI の加速度（PRM-68・73）を実測に合わせる。模擬で確かめてから承認に回す。値は変えていない。
- 模擬の 2 回目（43 本、`research/vehicle_pc/2026-11-07_ffpi_sim_r2/`）：旋回の PI を止めると直線の蛇行は 0。遅れて出るコーンの間隔は、今の旋回の模型で 0.05〜0.16 m、az・wz 0.5 で 0.51〜0.53 m（vx 0.4・0.5、接触 0）。区間の速度の制限が vx_max より大きいと MPPI が速度・下限・旋回を引き上げる（#92）。承認待ち DEC-490（vx_max 0.5・wz 0.5・PRM-67/73 0.5）。DEC-491 は回答済み（区間の制限は人が運用で決める、頭打ちの処理は入れない、REV-273）。

**第220便: dev-tab-vehicle-test 系統の統合（REV-246、DEC-461）**（作業記録 `reports/worklog/2026-11-07_bin220_integrate_devtab_line.md`）。
- 人の回答「両系統を先に統合」。0e260f3 で分かれていた系統（待機の表記・PRM-45 4500 mV・/dev タブ・車体試験の記録）を入れた。コードは 3-way で衝突 0。
- 番号の付け直し：REV-206〜217→REV-247〜258、DEC-417〜428→DEC-462〜473、第194〜207便→第221〜234便、ND-20→ND-30、IFD-58→IFD-71。
- 設計検査 違反0件・未判定5件（migration の FAIL は前からの drawio・.DS_Store だけ）。単体試験 Mac 406 件 OK（skip 27）、Linux 431 件 OK・1 件は試験の環境による。車載 PC への反映・コミットはまだ。

**第216便: ND-11 に GLIM の速度のフィードフォワード＋PI の層（REV-241、DEC-450〜453、PRM-150〜160、IFD-70）**（作業記録 `reports/worklog/2026-11-07_bin216_nd11_speed_feedback.md`）。
- 人の指示（DEC-450）で実装。/config「自律走行の出力」で有効にしたときだけ働く（既定は無効）。実測（DEC-445）の倒し量→速度のフィードフォワード＋localization/odometry との差の PI。GLIM の速度が古ければフィードフォワードだけで走る。記録は log/motion_feedback。
- 単体試験 16 件と結合の確認 5 項目は合格。模擬（36 本、`research/vehicle_pc/2026-11-07_ffpi_sim/`）：MPPI open_loop true で発進 1.3→0.7 s・0.40→0.60 m/s、open_loop false でも発進、旋回の PI は蛇行、遅れて出るコーンは層ありで全部接触。実車の最初の値の案：前後 P 0.3・I 0.5・上限 0.15、旋回 P・I 0、有効時間 0.5 s。
- 承認待ち DEC-451・453、実測待ち DEC-452。改善の案は #83・#84。実車・コミットはまだ。

**第219便: Nav2 の失敗で待機に入らず goal を出し直す（REV-245、DEC-460、PRM-161）**（作業記録 `reports/worklog/2026-11-07_bin219_nav2_failure_resend.md`）。
- 人の回答「Nav2 の失敗で待機に入らず goal を出し直す変更を実装してよい。…」（DEC-437 の最小の形）。失敗で TR-07 に入らず、自律走行のまま（hold）PRM-161 の 2.0 s（AI の推奨値、実測なし）の後に next_offset から出し直す。上限なし、出し直しの失敗も再試行。PRM-161 に値がなければ今までどおり待機。DEC-438 は閉じていない。
- 単体試験 Mac 400 件 OK（skip 27）、模擬の機械で新しい 12 件 OK。設計検査 違反0件・未判定5件。drive_sim は goal が失敗で終わらず未判定。実車・車載 PC は未実行。残るリスク：塞がれた道で出し直しを続けて止まり続ける（3 分で失格）。コミットはまだ。
- 追記（人の指示「workstationで実験を行う。」）：模擬の機械の drive_sim で、試験用の /config の値（回復の回数 外 1・計画 0・追従 0、車両の値ではない）で goal を失敗させた。新は待機に入らず 2.0 s 後に送り直し（2 回）、旧は TR-07 で待機（blocked）、free は goal_reached。塞がれた waypoint の周りを回り続けて進まない（76 s）。ubuntu_stage5-6.sh・車載 PC・実車は未実行。

**第217便: MID-360 を別の costmap の層として入れる最小構成（REV-242、DEC-454〜457、PRM-142）**（作業記録 `reports/worklog/2026-11-07_bin217_mid360_min_impl.md`）。
- 人の回答「実装はopus5.5に実装させよ。君は監督役。」。livox_ros_driver2 と mid360_scan を Nav2 と一緒に起動し、local・global に mid360_layer（模擬の S2）。車載 PC の `<data_root>/config/mid360.json`（アドレスと取り付け）と PRM-142 とドライバがそろうときだけ。そろわなければ今と同じ（XT-32 だけ）。
- 単体試験 Mac 385 件 OK（skip 15）、設計検査 違反0件・未判定5件。未回答：DEC-455（帯）、DEC-456（つながらないとき）、DEC-457（取り付けの実測）。ROS 上の起動・車載 PC・実車は未実行。コミットはまだ。

**第241便: ゴールの到達判定の向きの許容を /config の値に（REV-265、DEC-484、PRM-163）**（作業記録 `reports/worklog/2026-11-07_bin241_goal_yaw_tolerance.md`）。
- 人の回答「入れて」。6.3 rad（向きを問わない。これまでは雛形の 0.25 rad）。下限つきの MPPI がゴールで止まれない問題（第236便の訂正）への対処。一時停止線で止まる処理は製品にない（未実装）。
- 単体試験 Mac 438 件 OK、設計検査 違反0件・未判定5件。模擬（DEC-445 の車体モデル、製品の設定の経路）：10 本すべてゴールで止まり接触 0（5 場面、各 1〜2 本）。車載 PC に反映済み（人の指示）。実車は未実行。コミットはまだ。

**第236便: MPPI の前進速度の下限 vx_min を /config の値に（REV-261、DEC-480、PRM-162）**（作業記録 `reports/worklog/2026-11-07_bin236_mppi_vx_min.md`）。
- 人の回答「入れて」。0.27 m/s（発進する倒し量 0.21×1.25 m/s の切り上げ）。これまでは 0 固定。停止用のロジックは足していない。
- 単体試験 Mac 434 件 OK、設計検査 違反0件・未判定5件。模擬：下限のみは 0/4。**訂正：下限＋open_loop は「ゴール 4/4」ではなく、ゴールで止まったのは 6 本中 2 本。4 本はゴールを通り過ぎて走り続けた**（作業記録の訂正）。車載 PC に反映済み（人の指示）で、扱いは人の判断待ち。実車は未実行。コミットはまだ。

**第215便: MPPI の open_loop を /config で切り替える（REV-240、DEC-449、PRM-141）**（作業記録 `reports/worklog/2026-11-07_bin215_mppi_open_loop.md`）。
- 人の回答「着手して」。PRM-141 `mppi_open_loop`（既定 true。既定の値は AI の読みで、人は明示していない）を足し、/config「Nav2」タブで false に戻せる。発進できない件（#61）への対処。
- 単体試験 Mac 360 件 OK（skip 15）、設計検査 違反0件・未判定5件（既存の不合格はそのまま）。模擬（実の Nav2、DEC-445 の車体）6 本：既定は 4 本とも発進して完走・接触 0、false は 2 本とも発進できず。横ずれ 0.56〜0.65 m、コーンとの最小間隔 0.05 m。
- 車載 PC への反映・画面の確認・実車は未実行（人の指示待ち）。実車投入可能：人の判断待ち。コミットはまだ。
- 追記（REV-243、DEC-459、人の回答「作業はopes5.5にやらせよ。車載PCに反映して良い」）：車載 PC に反映し gouda_core を作り直した（成功、車載 PC 上の test_nav2_config 23 件 OK）。Gouda は起動していない。画面の確認・実車は未実行。

**第212便: DEC-445 を確定（REV-236）**（作業記録 `reports/worklog/2026-11-07_bin212_dec445_confirmed.md`）。人の回答「このまま確定」で、第210便の最低速度・曲がりの不感帯の値を実測値にした。模擬への反映は人の指示待ち。設計検査 違反0件・未判定5件。コミットはまだ。

**第214便: DEC-445 の実測値での open_loop・下限の模擬の比較（REV-239、DEC-448）**（作業記録 `reports/worklog/2026-11-07_bin214_m4x_sim.md`、証拠 `research/vehicle_pc/2026-11-07_m4x_sim/`）。
- workstation と Dell に分担した。4 倍速は 1 倍速と合わず、2 倍速で 90 本を回した。
- 結果：open_loop なしは下限があっても 29 本すべて発進できない。open_loop ありの 4 方式は 58/60 がゴールし、下限ありは止まっていた時間が短い。遅れて出るコーンは全方式で接触した。
- 実装は #66・#61 の許可待ち。
- 検査：設計検査 違反0件・未判定5件。別のセッションによる証拠のファイルの書き換え（02:27、hash の不一致 13 件）と ledger のスキーマ違反を見つけた（このセッションでは戻していない）。コミットはまだ。

**第213便: TR-IMU16607 の設定のソースでの確認（REV-237、DEC-447）**（作業記録 `reports/worklog/2026-11-07_bin213_imu_board_settings.md`、記録 `docs/imu_adis16607_spec.md` の節「TR-IMU16607 基板の設定と出力」）。
- 基板ファーム 1ffaad4 とドライバ 742b7ba のソースから：重力補正のフラグは出力に使われていない（加速度は重力を含む）。16bit／32bit はドライバが感度を読んで換算するのでどちらでも動く。画面の設定のままでよい。
- 指摘：#82 の案 1（重力補正をオンにすると壊れる恐れ）はこのソースでは当たらない。人の画面と #82 の起動ログの設定が食い違う（未解決）。設計検査 違反0件・未判定5件。コード・設定は変えていない。コミットはまだ。

**第210便: 最低速度・曲がりの不感帯の実測（REV-234、DEC-444・445、#82）**（作業記録 `reports/worklog/2026-11-07_bin210_min_speed.md`、証拠 `research/vehicle_pc/2026-11-07_min_speed/`）。
- 人の手動の rosbag 2 本と GLIM の軌跡から：最低速度 前進 約 0.09 m/s・後退 約 0.075 m/s、前進中の旋回の入力 0.184 以下では曲がらず 0.195 で 0.06〜0.09 rad/s。IMU の積分は傾きで使えない。実測の候補（DEC-445）。
- IMU のフィルタの案は #82。設計検査 違反0件・未判定5件。コード・設定は変えていない。コミットはまだ。

**第209便: waypoint を飛ばす方式（REV-231、DEC-367 answered）**（作業記録 `reports/worklog/2026-11-07_bin209_skip_method.md`）。
- 人の回答「目印の点だけ」：skip_allowed の点だけを、costmap の cost と持続時間で判定して飛ばす。k10h0 は採らない。
- 未回答：DEC-344 (2)（確認走行区間の外だけか）、値（tbd）、実装の着手。コミットはまだ。

**第208便: waypoint を飛ばす工夫の採用の指示（REV-229、DEC-441）**（作業記録 `reports/worklog/2026-11-07_bin208_waypoint_skip_adoption.md`）。
- 人の指示「飛ばす､という工夫を取り入れよう」を記録した。前の指示（第200便）は比較の指示で、DEC-310・344・367 は pending のまま。
- 方式・条件と、実装の着手は人の判断待ち。設計検査は違反 0・未判定 5。コミットはまだ。

**第207便: DEC-316 を閉じた（REV-226）**（作業記録 `reports/worklog/2026-11-06_bin207_dec316_closed.md`）。
- 人の回答「前提、全部閉じる」：(1)(3)(4) は intent.md 第17版の記載（100・37・43 行）どおり、基本契約（38〜42 行）は今も前提。(2) は DEC-437。
- 残る：100 行の「直前が自律走行なら自律走行に戻る」は未実装（DEC-309）、TR-13 は未実装、100 行の「事前事前地図作成」の語の重なり（人が直す）。設計検査は違反 0・未判定 5。コミットはまだ。

**第206便: Nav2 の失敗で待機に入らない決定と、回復の構成の未決事項（REV-225、DEC-437・438）**（作業記録 `reports/worklog/2026-11-06_bin206_nav2_failure_no_standby.md`）。
- 人の回答（DEC-437、原文）：Nav2 が失敗しても待機に入らない。失敗から回復できる構成は後で考える（未決事項 DEC-438、候補は DEC-366・DEC-310・第200便）。DEC-200 の Nav2 の部分を置き換える。DEC-316 は第207便で閉じた。
- 実装はまだ。今の実装は Nav2 の失敗で待機に入る。待機に入らない変更だけを入れると自律走行モードのまま止まり続けるので、DEC-438 と組にして入れるのがよい。
- 設計検査は違反 0・未判定 5。コミットはまだ。

**第205便: gouda.sh の systemd 化と電源投入での自動起動の案（REV-223、DEC-434・435、提案）**（作業記録 `reports/worklog/2026-11-06_bin205_systemd_autostart.md`、案 `proposals/systemd_autostart_plan_2026-11-06.md`）。
- 人の回答「電源投入で自動起動」を DEC-434 に記録。その後、人が方針を転換（DEC-435 の回答、REV-224）：systemd 化はせず、PC の起動時に端末を開いて最初のディレクトリを tsukuba-autonomous-robot にするだけ。
- 2026-11-07（REV-227・228）：端末の自動起動もやめる（DEC-436）。望みは「端末を開くたびの cd と source を不要にする」と確定（DEC-439）。setup.sh で ~/.bashrc に足す実装は承認され（DEC-440、REV-230）、setup.sh・README を変更。一時的な HOME での試験は合格、x86 への反映と実機の端末での確認は未実行。コミットはまだ。

**第204便: MID-360 の接続試験・動作確認の計画と記録台帳（提案）**（作業記録 `reports/worklog/2026-11-06_bin204_mid360_connection_test_plan.md`、計画 `proposals/mid360_connection_test_plan_2026-11-06.md`、台帳 `research/vehicle_pc/2026-11-06_mid360_connection/ledger.yaml`、公式資料はリポジトリの外 `Sensors/MID-360/official/`）。
- 試験 32 項目：合格 1（T03-1 Livox Viewer 2 での点群の受信、人の報告。REV-222、DEC-433）・不合格 0・未判定 31。ドライバは公式を commit 固定・時刻はまず同期なし（REV-232、DEC-442）。setup.sh・drivers.repos に Livox-SDK2 c0796f0・livox_ros_driver2 2144554 を足した（REV-233、DEC-443。別の作業場所 ~/gouda_ws_livox、SDK は /usr/local）。Dell の一時の場所で sudo なしの試しのビルドは成功。人が Dell で `bash setup.sh` を実行したが、変更が Dell に届いておらず（Dell は dev-tab-vehicle-test、ローカルの変更 48 件）、MID-360 のドライバは未導入。変更はコミット 9c449b5 で branch design/mppi-sim-2026-11-03 に push 済み（main には未反映）。電圧は 12 V（DEC-433）。参考 61 件（公式・記事・fork）。Q1 は回答済み：Dell の x86 機（車載 PC）で行う（REV-220、DEC-431）。Q2 も回答済み：XT-32 と同時には PoE なしのスイッチで 1 つの口にまとめる（REV-221、DEC-432）。判断待ち Q5・Q6（合否基準、発熱の条件）。内蔵 IMU で取り付けの角度を求め点群の歪みを直す案を #80 に登録（ICM-40609-D のデータシートはリポジトリの外。参考 70 件）。設計検査 違反0件・未判定5件。コード・設定は変えていない。コミットはまだ。

**第200便: waypoint を諦める処理と LiDAR の欠け・偽の点のシミュレーション比較**（作業記録 `reports/worklog/2026-11-06_bin200_waypoint_skip_sim.md`、結果 `research/vehicle_pc/2026-11-06_waypoint_skip_sim/README.md`、K-yama-20/tsukuba-autonomous-robot#69・#70・#71）。
- シミュレーションのみ（走行中の旋回不感帯はなしの仮定）。第一候補 k10h0（半径 1.0 m に 5 点以上で飛ばす）は 30〜31/48 到達、base は 20〜23/48。偽の点は base でも到達を大きく下げる。対策候補 DenoiseLayer の比較は実行中。コード・設定は変えていない（実装は承認待ち）。

**第202便: MID-360 搭載版のシミュレーション案 段階 1（試験専用）**（作業記録 `reports/worklog/2026-11-06_bin202_mid360_sim_stage1.md`、#78）。
- 模擬に MID-360 の点群と仕様書の XT-32 の値を足した。単体試験 Mac OK、設計検査 違反0件・未判定5件。costmap にはまだ入れていない。コミットはまだ。

**第203便: MID-360 搭載版のシミュレーション 段階 2（試験専用）**（作業記録 `reports/worklog/2026-11-06_bin203_mid360_sim_stage2.md`、#79）。
- 119 本：接触は XT-32 だけ 18 → MID-360 の別の層 6。別の層が同じ層より良い。塞がれた waypoint で止まる（#38）。設計検査 違反0件・未判定5件。コミットはまだ。

**第199便: XT-32 の見える範囲の台帳と TRB-001 の訂正（REV-215・216、DEC-426・427）**（作業記録 `reports/worklog/2026-11-06_bin199_xt32_visible_range.md`、台帳 `docs/lidar_xt32_spec.md`）。
- 2026-10-14 の rosbag 2 本の点群から実測：ビーム +15.05°〜−15.98°（1.00° 間隔）、水平 360°、固定の死角なし、地面からの高さ 1.182 m、地面が見え始めるのは 4.0〜4.2 m 先。
- TRB-001・K-6 は高さ 1.015 m で計算しており、見えない範囲を狭く見積もっていた。人の回答「直して」で TRB-001 を実測の値に直した（K-6 は過去の提案なのでそのまま。K-yama-20/tsukuba-autonomous-robot#73）。データシートは原本未照合。コード・設定は変えていない。設計検査 違反0件・未判定5件（既存の移行の不一致の FAIL はそのまま）。

**第198便: 推定不能が 30 秒を超えたら止まって自動で回復を待つ（REV-212、DEC-423）**（作業記録 `reports/worklog/2026-11-04_bin198_localization_wait.md`）。
- T1〜T6 合格（VM、模擬）、設計検査 違反0件・未判定5件。実車は未実行。コミットはまだ。

**第197便: お助けの案の登録（REV-211、DEC-422、承認待ち）**（作業記録 `reports/worklog/2026-11-04_bin197_assist_proposal.md`）。コード・設定は変えていない。

**第196便: 推定不能でも 30 秒は走り続ける（REV-210、DEC-421、PRM-136）**（作業記録 `reports/worklog/2026-11-04_bin196_estimator_continue.md`）。
- T1〜T6 合格（VM、模擬）、設計検査 違反0件・未判定5件。LiDAR の途切れを IMU で進む部分は未実装。実車は未実行。コミットはまだ。

**第195便: IMU の仕様の記録と規則（REV-207、DEC-418）**（作業記録 `reports/worklog/2026-11-03_bin195_imu_spec.md`、仕様 `docs/imu_adis16607_spec.md`）。
- 設計検査 違反0件・未判定5件。コード・設定は変えていない。

**第194便: AI と人間の役割分担（REV-206、DEC-417）**（作業記録 `reports/worklog/2026-11-03_bin194_role_split.md`）。
- CLAUDE.md に 1.12 を足した。設計検査 違反0件・未判定5件。intent.md の 62〜63 行との統合は人の編集。コード・設定は変えていない。

**第186便: 車速 0 からの動き出しの無駄時間（REV-198・199、DEC-409・410）**（作業記録 `reports/worklog/2026-11-03_bin186_startup_dead_time.md`）。
- 人の指摘を記録。今の設計・シミュレータは考慮していない。実測待ち。コード・設定は変えていない。

**第184便: intent.md 第17版の記録（REV-195〜197、AR-017、DEC-408）**（作業記録 `reports/worklog/2026-11-03_bin184_intent_v17.md`）。
- intent_identity は合格。残る移行の不一致は SystemArchitecture.drawio と .DS_Store 2 つ。PRM-03 を 1.25 m に。コミットはまだ。
**統合：dev-tab-vehicle-test 系統の記録（第187〜193便・第221〜234便。第220便で統合、REV-246、DEC-461）**。以下はその系統の status.md の項目を写したもの。番号は付け直した（ND-20→ND-30、IFD-58→IFD-71、DEC-417〜428→DEC-462〜473、REV-206〜217→REV-247〜258、第194〜207便→第221〜234便）。

**第234便: 実車の測定結果と分析の文書（REV-256、DEC-471）**（作業記録 `reports/worklog/2026-11-04_bin234_vehicle_measurements_doc.md`）。
- 文書 `research/vehicle_pc/2026-11-03_vehicle_measurements/vehicle_measurements_2026-11-03.md`。測定値は候補で、DEC-378、DEC-462 は未回答。コードと設定は変えていない。
- 生データ 4 件も同じフォルダの `runs/` に入れた（REV-257、DEC-472、一覧 `RAW_DATA.md`）。残りの試験 4 件と rosbag は x86 にだけある。台帳と記録は push した。`gouda_core` などのコードの変更（REV-202〜 の実装を含む）は未コミット。
- REV-255 で消し残した VM のユーザー名と PC 名を置き換えた（REV-258、DEC-473）。git の履歴と main には残る。

**第233便の追記（496 回の模擬）**：下限 0.10＋open_loop はゴール 97/111・接触 2、open_loop は 93/96・接触 18、下限だけは 23/101 と 0/102。起動失敗 86 回中 84 回は ros2 daemon が不調なドメイン 105 の枠に集中。早回しは負荷なしでも 2 倍まで（controller_server の WallRate が原因とみている。推測）。全て模擬で、本番と実車は変えていない。実車投入可能：人の判断待ち。

**第233便の追記（REV-255、DEC-470）**：今のファイルから VM の接続先を置き換えた。履歴には残る。コミットと main への反映は人の指示待ち。

**第233便: 発進の対策の模擬の比較（issue #61）**（作業記録 `reports/worklog/2026-11-03_bin233_start_sim_compare.md`）。
- MPPI は実速度 0 だと指令の上限が 0.12 m/s（計算）で、不感帯を越えない。5 条件 × 2 場面 × 各 3 回の結果：open_loop は 6 回ともゴール（遅れて出るコーンで 1/3 接触）。Critic は回復の spin まで動かない。補償ありは 1.09 m/s まで出た。実車は未実行で、コードと設定は変えていない。

**第232便: 実車で MPPI の発進を確かめる準備の確認（REV-253、DEC-468）**（作業記録 `reports/worklog/2026-11-03_bin232_real_mppi_start_prep.md`）。
- 実車の走行 run-f890dddb（rosbag 解析済み）：MPPI、補償なしで 40 s 発進せず（平均 0.033 m/s、倒し量 0.04 以下、不感帯 0.20）。模擬と近い値。回復の spin（1 rad/s、約 92・104 度）と backup は実際に動いた。コードと設定は変えていない。

**第231便: 実車の補償の設定と Nav2 の発進の指令の確認（読むだけ＋模擬 1 回）**（作業記録 `reports/worklog/2026-11-03_bin231_comp_start_check.md`、案 issue #61）。
- x86 の補償は 6 項目すべて未設定。MPPI は x86 の記録では実車の走行なし（VM は未確認）。10-24 の実走（RPP、補償なし）は発進していて、RPP の模擬も発進する。MPPI の模擬だけが発進しない。RPP はカーブの小さい旋回で止まる。実車の MPPI は未確認。コードと設定は変えていない。

**第230便: 走行の模擬の車体に実測の値を入れる（REV-252、DEC-467）**（作業記録 `reports/worklog/2026-11-03_bin230_sim_plant_measured.md`）。
- 補償なしでは Nav2 の発進の指令が不感帯より小さく、模擬の 3 場面とも進まない。試しの補償では動くが最大横ずれ 4.4〜5.9 m。模擬の結果で、実車は未確認。単体試験 370 件 OK。本番のコードと設定は未変更。コミットはまだ。

**第229便: 入力を長くした t_lock と模擬の車体の値の対応（x86、実車、読むだけ）**（作業記録 `reports/worklog/2026-11-03_bin229_long_input_t_lock.md`）。
- 旋回は中立 2 s 以上で遅れが約 0.30〜0.41 s にそろう。止まった後に約 4.4 Hz の揺れが約 3 s 残る。模擬へは旋回の値と不感帯が入れられる見込みで、速度は未測定。模擬は未変更。

**第228便: t_lock と T ロックの解析を方向別に（REV-251、DEC-466）**（作業記録 `reports/worklog/2026-11-03_bin228_lock_analysis.md`）。
- 入力の直前に動いていた試行は遅れとして読まない。実車の 2 件で再計算し、T ロックは第227便と一致、t_lock は未確定。単体試験 361 件 OK。x86 の本番の作業領域には未反映。コミットはまだ。

**第227便: T 解除と T ロックの結果（x86、実車、読むだけ）**（作業記録 `reports/worklog/2026-11-03_bin227_t_up_down_results.md`）。
- 旋回の止まる段は左 0.26〜0.30、右 0.15〜0.18 で T 解除と同じ。止まる直前でも約 0.31〜0.35 rad/s。前進 0.18〜0.22、後退 0.18〜0.22。手動介入後のやり直しは実車で 4 回動いた。値は人の確認待ち。自動の `locked` は実態と合わない。

**第226便: t_lock の結果（x86、実車、読むだけ）**（作業記録 `reports/worklog/2026-11-03_bin226_t_lock_results.md`）。
- その場の旋回は中立から約 2 s で落ち着く。t_lock は未確定（表の 3〜4 s は根拠が弱い）。中立 1.5 s 以下の判定は基準の窓の影響で遅れとして使えない。前進・後退は未測定。

**第225便: 遅れとパルスの結果（x86、実車、読むだけ）**（作業記録 `reports/worklog/2026-11-03_bin225_delay_pulse_results.md`）。
- DAC コードの最大 3902 で 4500 mV の設定の到達を確認。その場の旋回は幅 0.5 s 未満のパルスではほぼ動かない。後退 0.4 の遅れは 0.85〜0.88 s。値は人の確認待ち。遅れの試験の順序の説明の誤りを訂正した。

**第224便: ゲームパッドの介入で試験を終わらせない（REV-250、DEC-465）**（作業記録 `reports/worklog/2026-11-03_bin224_manual_override_retry.md`）。
- 中立で待ち、PC が source に戻ったらその試行をやり直す。離すと試験の入力が自動で再開する。単体試験 358 件 OK。模擬・実車は未実行、x86 は未反映。コミットはまだ。

**第223便: 遅れの試験を元の位置に戻る組の順序に（REV-249、DEC-464）**（作業記録 `reports/worklog/2026-11-03_bin223_delay_return_order.md`）。
- 前進 2 回→後退 2 回、右 2 回→左 2 回。第222便の順序を置き換えた。単体試験 352 件 OK、設計検査 違反 0・未判定 5。x86 は未反映、実車は未実行。コミットはまだ。

**第222便: 遅れの試験の順序を同じ方向の繰り返しに（REV-248、DEC-463）**（作業記録 `reports/worklog/2026-11-03_bin222_delay_order.md`）。
- 各方向の 1 回目と 2 回目以降を表で分ける。単体試験 353 件 OK。x86 は測定中のため未反映、実車は未実行。コミットはまだ。

**第221便: DAC 出力電圧の実測項目と手順（REV-247、DEC-462）**（作業記録 `reports/worklog/2026-11-03_bin221_dac_voltage_measurement.md`）。
- 設定 4500 mV の実際の出力は USB 5V に比例するので、x86 接続で測る。手順は `research/vehicle_pc/2026-11-03_dac_voltage_measurement_procedure.md`。実測待ち（未実施）。設計検査 違反 0・未判定 5。コミットはまだ。

**第193便: DAC 最大電圧 PRM-45 を 4500 mV に（REV-205、DEC-416）**（作業記録 `reports/worklog/2026-11-03_bin193_dac_max_4500.md`）。
- 前進・右旋回の倒し量と電圧の傾きが約 10 % 小さくなる（計算）。x86 には未反映、実機は未確認。コミットはまだ。

**第192便: 動き出しの試験の結果（x86、実車、読むだけ）**（作業記録 `reports/worklog/2026-11-03_bin192_vehicle_test_results.md`）。
- T：前進・後退 約 0.22、左 0.30、右 0.18。遅れは前進 0.25〜0.8 s、後退 0.4 で約 0.9〜1.4 s。案 F と手動の優先は実車で動いた。値は人の確認待ち。

**第191便: vehicle_bridge の seq を firmware に合わせる（REV-204、DEC-415、TRB-014）**（作業記録 `reports/worklog/2026-11-03_bin191_bridge_seq_follow.md`）。
- 単体試験 350 件 OK、x86 の模擬の全項目 PASS（棄却 0 件）。設計検査 違反 0・未判定 5。実機の ESP32 は未実行。コミットはまだ。

**第190便: 車体試験の再試行、入力の継続、初期値、TRB-014（REV-203、DEC-414）**（作業記録 `reports/worklog/2026-11-03_bin190_vehicle_test_retry_inputs.md`）。
- 2 回目以降の試験は bridge の seq が戻って棄却されることを確認（TRB-014、未修正）。単体試験 OK、実車は未実行。コミットはまだ。

**第188便: ボタンの表記を「待機」に（REV-201、DEC-413）**（作業記録 `reports/worklog/2026-11-03_bin188_button_taiki.md`）。動作は不変。画面の目視・実車は未実行、x86 は未反映。

**第187便: /dev タブと車体試験、動き出しの試験（REV-200、DEC-411・412）**（作業記録 `reports/worklog/2026-11-03_bin187_dev_tab_vehicle_test.md`、手順 `docs/vehicle_tests.md`）。
- x86 の模擬（esp32_sim、合成 IMU）で全項目 PASS、設計検査 違反 0・未判定 5（intent 由来の FAIL はそのまま）。実車は未実行。承認待ち DEC-412（手動走行で IFD-16 へ出す経路）。

**第185便: main に入れる準備（確認だけ）**（作業記録 `reports/worklog/2026-11-03_bin185_main_merge_prep.md`）。
- 単体試験 Mac・VM 328 件 OK、T1〜T6 合格（VM、模擬）、設計検査 違反 0・未判定 5（intent 由来の FAIL はそのまま）。実車は未実行。コミットはまだ。

**第183便: x86 の PC で 30 パターン・各 4 回の回避の試験**（作業記録 `reports/worklog/2026-11-02_bin183_x86_30_patterns.md`、結果 K-yama-20/tsukuba-autonomous-robot#32）。
- 有効 104 本：ゴール 96、接触 19、最高 0.67 m/s。高さ 0.5 m 以下と正面から来る人は全回接触。車体は合成で実車は未実行。コード・設定は変えていない。

**第179便: 走行シミュレータと採点、MPPI・RPP の比較（REV-194、DEC-407）**（作業記録 `reports/worklog/2026-11-02_bin179_drive_sim.md`、証拠 `research/vehicle_pc/2026-11-02_drive_sim/`）。
- `gouda_core/test/drive_sim*`：実際の Nav2 に合成の点群と車体モデルをつなぐ試験専用の道具。製品のコード・設定は変えていない。
- VM で各 1 回の 16 本：MPPI＋印 5 m・消去 6 m が接触 0／3、最小の間隔 0.56 m、約 0.41 m/s。RPP は 2.5 m・5 m とも接触 3／3。値の採用は人の判断。実車・x86 の PC は未実行。コミットはまだ。

**第182便: PRM-135 を /config で変えられるように（REV-193、DEC-406）、影響を TRB-013 に登録**（作業記録 `reports/worklog/2026-11-02_bin182_map_odom_offset_config.md`）。
- 値は 0.5 s（人が承認）。単体試験 Mac OK、設計検査 違反 0・未判定 5（intent 由来の FAIL はそのまま）。画面の確認・VM・実車は未実行。コミットはまだ。

**第180便: map→odom を少し先の時刻で出す（REV-191、DEC-403、PRM-135 暫定 0.5 s）**（作業記録 `reports/worklog/2026-11-02_bin180_map_odom_future_stamp.md`）。
- 実機は未確認。コミットはまだ。

**第178便: 経路追従のみの試験の案を GitHub Issue に登録**（作業記録 `reports/worklog/2026-11-02_bin178_following_test_issue.md`）。
- K-yama-20/tsukuba-autonomous-robot#23。案 A・B と実装の承認は未回答。コード・設定は変えていない。

**第177便: MPPI を既定にし、経路の平滑化を足す（REV-190、DEC-400〜402）**（作業記録 `reports/worklog/2026-11-02_bin177_mppi_smooth_impl.md`）。
- MPPI：0.8 m/s・1.0 rad/s、local costmap 8 m・10 Hz（PRM-124・130〜133）。RPP は /config（PRM-130 false）で戻せる。BT に SmoothPath（PRM-134）。setup.sh に nav2-mppi-controller。
- 単体試験 Mac 309 件 OK（skip 15）、設計検査 違反 0・未判定 5（intent 由来の FAIL はそのまま）。Nav2 での起動・模擬の試験・CPU の測定・実車は未実行（VM に ssh がつながらない）。コミットはまだ。

**第176便: MPPI・平滑化の回答の記録と、waypoint の渡し方・衝突監視の検討（REV-189、DEC-400・401）**（作業記録 `reports/worklog/2026-11-02_bin176_mppi_smooth_answers_waypoint_cm.md`）。
- 人の回答「MPPI: 使用」「パスの平滑化：行う」を記録。実装の着手は確認待ち。案：区間ごとの NavigateThroughPoses（DEC-366）、collision_monitor は approach のみ・途絶で止めない（DEC-372、intent との関係は人の判断）。
- 設計検査 違反0件・未判定5件（intent 由来の FAIL はそのまま）。コード・設定は変えていない。

**第175便: gouda_monitor の配色を案 A に（REV-188、DEC-399）**（作業記録 `reports/worklog/2026-11-02_bin175_monitor_palette_a.md`、色の表 `docs/gouda_monitor_palette.md`）。
- 人の回答「A案でいこう。」。明るい灰の背景、赤・黄・緑の札と印、地図の上の印の色を `gouda_core/web` に反映。単体試験 Mac 305 件 OK（skip 15）、設計検査 違反 0・未判定 5（intent 由来とみられる既存の失敗はそのまま）、デモ画面で 6 タブを目視。人の指示で VM の gouda_ws の web に色だけ反映（Gouda は動いておらず止めていない。次の start から有効）。実機での見え方は未確認。コミットはまだ。

**第174便: 検査ルール案 2 件を承認事項に登録（REV-187、DEC-397・398、承認待ち）**（作業記録 `reports/worklog/2026-11-02_bin174_check_rule_candidates.md`）。
- 人の回答「登録する」。DEC-397：既定から外すときは失う機能を書く。DEC-398：未解決の Q に関わる選択はその Q を挙げる。設計検査 違反 0・未判定 5（intent 由来の FAIL はそのまま）。検査器は未実装。コミットはまだ。

**第173便: gouda_monitor の配色の調査（調べるだけ）**（作業記録 `reports/worklog/2026-11-02_bin173_monitor_colour_research.md`、報告はリポジトリの外の `reports/HMI配色のJIS規格と推奨色.md`）。
- JIS は色の意味と色以外の併用までで、画面の hex 値は読んだ範囲にない（JIS は全て原本未照合）。現行の活性文字は暗所の WCAG 比で 4.5:1 以上。原因の候補は小さな淡色の文字、青緑への集中、白い地図の上の線と文字、周囲光（実機では未確認）。配色の案は未承認で、明背景か暗背景かは人の決定と照度の実測の待ち。コード・設定は変えていない。

**第172便: local の keepout フィルタの TF 失敗の判断材料（読むだけ）**（作業記録 `reports/worklog/2026-11-02_bin172_keepout_tf_materials.md`）。
- ソースと log の読み：失敗しているのは override（DEC-222）の判定で、マスク自体は書かれている可能性が高い。0.1 s の待ちが controller の詰まりと時刻で一致。実機は未確認、コード・設定は変えていない。

**第171便: MPPI の試験の提案（提案だけ、実装なし）**（作業記録 `reports/worklog/2026-11-02_bin171_mppi_trial_proposal.md`、提案 `proposals/mppi_trial_2026-11-02.md`）。
- 既定は RPP のまま /config で切り替え、0.5→0.8 m/s、local 8 m で段階的に試す案。前提に local の keepout の確認（第157便の TF の失敗、未解決）。承認の候補 B1〜B6 は未登録。コード・設定は変えていない。

**第170便: 再計画が間に合わない問題の先行事例（読むだけ）**（作業記録 `reports/worklog/2026-11-02_bin170_replan_precedents.md`）。
- KUAMS（完走）は再計画 0.333 Hz・global 1 Hz・印 2.5 m で gouda と同じか遅い。回避は MPPI（local 10 Hz、8 m）に任せ、0.8 m/s と collision_monitor を組にしている。上流の既定も同じ組。RPP は動く障害物を考慮しないと上流に明記。
- 完走 7 チームのうち設定を確かめられたのは KUAMS だけ。承認の候補：DEC-122 の見直し（MPPI の試験）。コード・設定は変えていない。

**第169便: A案の scan の range_max を有限にする（REV-186、DEC-396）**（作業記録 `reports/worklog/2026-11-02_bin169_scan_range_max.md`）。
- 人の回答「修正を実装」。range_max を obstacle_max_range・raytrace_max_range の大きい方の 2 倍に（既定の範囲で 6.0 m、/config に追従）。
- 単体試験 Mac 305 件 OK（skip 15）、設計検査 違反 0・未判定 5（intent 由来の FAIL はそのまま）。VM の試験・実の costmap の消去の確認・実車は未実行（VM に ssh がつながらない）。コミットはまだ。

**第168便: main の現状と、回避機動が遅い原因の調査（読むだけ）**（作業記録 `reports/worklog/2026-11-01_bin168_main_status_avoidance_latency.md`）。
- main 8ee7162：単体試験 Mac 305 件 OK（skip 15）、設計検査 違反 0・未判定 5（intent 由来の FAIL はそのまま）。A案の実車は未実行。VM は ssh がつながらない。x86 の PC は AI から接続方法が不明。
- A案の設定は `range_max` が既定値（inf）で、点のない方位が costmap の消去に使われない疑い（上流のソースと計算で確認、実機は未実行、承認の候補）。
- 記録の訂正：controller の「平均 10 Hz」は遅れた回だけの値（0.2 s ごとに約 0.1 s の詰まり）で、「1.6 Hz」は planner_server の行。計画は 50 ms 以内がほとんど。見えてから RPP が止めるまでの猶予 1.08 s に対し、避ける経路まで最悪 2.15 s（計算）。一番長い遅れは回復（約 50 s）。コード・設定は変えていない。

**第167便: A案（障害物の高さの帯を base_link で切る、pointcloud_to_laserscan）の試験の準備（REV-185、DEC-395、DEC-336 回答）**（作業記録 `reports/worklog/2026-11-01_bin167_plan_a_scan_band.md`、ブランチ test/plan-a-scan-band-2026-11-01）。
- 上流の pointcloud_to_laserscan で XT-32 の点群を base_link の帯（PRM-70・71）で切って LaserScan（IFD-57）にし、local（ObstacleLayer に）・global の costmap の観測源にした。Nav2 側の帯は無効、点のない方位は消去に使う。
- Mac・VM の単体試験 OK、帯の確かめ（合成の点群で箱だけが出る）、模擬の結合試験 T1〜T6 合格。設計検査 違反 0・未判定 5。実車は未実行。追記：人の指示で PR #22 として main に merge（8ee7162、作者 ryoya-1）。#21 も同時に main に入った。VM（aarch64）にはパッケージ未導入。人は x86 の PC に pointcloud_to_laserscan を入れた（AI はその PC につなぐ方法を知らない）。

**第166便: monitor のモードの表示「一時停止」を「待機」に（REV-184、DEC-394）と、変更の push**（作業記録 `reports/worklog/2026-10-26_bin166_monitor_label_taiki.md`）。
- 人の指示で、画面の表示名だけを「待機」に（正本の MODE-PAUSE・IFD-01・ボタンの文字は変えていない）。第156〜166便の変更をコミットして push（§5）。VM の Gouda には第165・166便は未反映（待機中の run-83d10ac0 の扱いが人の判断待ち）。

**第165便: A-1・E-4 の実装と、/config で変えられる Nav2 の値（REV-183、DEC-393、PRM-105〜129）**（作業記録 `reports/worklog/2026-10-24_bin165_a1_e4_nav2_tunables.md`、提案 `proposals/failure_handling_E1-E3_2026-10-24.md`）。
- 人の回答「A1, E4: 採用／E1,2,3; 検討／A2,4,5,B3,4,C2,3,4,6D1,4: /configで設定できるようにする。推奨値も考えて」。A-1：BT の外側の回復を error_code のない失敗でも試す。E-4：一時停止の理由を error_code で分ける（blocked・nav2_tf_error ほか）。25 の値を /config「Nav2」タブで変えられるようにした（PRM は未確定。値がない間は Nav2 1.3.13 の値のまま）。推奨値は PRM の interpretation と作業記録の表（承認待ち）。E-1〜3 は提案。
- 単体試験 Mac 305 件・VM 全件 OK、模擬の結合試験（stage5-6）は今の値・推奨値とも T1〜T6 合格。設計検査 違反 0・未判定 5（DR-11 の未確定の項目 +25）。VM の Gouda には未反映。コミットはまだ。

**第164便: ロバストな自律走行を妨げる設定・構成の列挙（読むだけ）**（作業記録 `reports/worklog/2026-10-24_bin164_robustness_blockers.md`、証拠 `research/vehicle_pc/2026-10-24_nav2_runtime_config/`）。
- 8 群 32 項目。主なもの：BT の回復が error_code のない失敗（受け付けの 20 ms の時間切れ）で 1 回も試されない（A-1・A-2）、controller が障害物を見て 0.3 s で中止（B-1）、進みの監視 0.5 m／10 s（B-2）、高さの帯の不一致で人の印が消えない恐れ（C-1、DEC-336）、Nav2 の失敗・1 回の推定不能で必ず一時停止（E-1・E-2）。
- 優先の案を挙げた（すべて承認事項）。コード・設定は変えていない。

**第163便: run-574fe6d7 がしばらく走って止まった原因（読むだけ）**（作業記録 `reports/worklog/2026-10-24_bin163_run_574fe6d7_stop.md`、証拠 `research/vehicle_pc/2026-10-24_autonomy_stop_run-574fe6d7/`）。
- 12 s 走って waypoint を 2 つ過ぎた後、RPP が「collision ahead」を出し続けて前進が 0 になり、回復（spin・wait・backup は Collision Ahead で中止）の後、63 s で planner が 20 ms 以内に受け付けを返さず BT が失敗（error_code 0）。
- map→odom の遅れは最大 0.18 s で、TF エラーは出ていない（第162便の後）。障害物が何かは rosbag がなく不明。候補は高さの帯の不一致（DEC-336、承認待ち）。次の走行で rosbag を取ってほしい。

**第162便: gouda_monitor の CPU を減らす（REV-182、DEC-392、PRM-104）**（作業記録 `reports/worklog/2026-10-24_bin162_monitor_m1_m2.md`）。
- 人の指示「M1,M2の推奨案を採用。また、monitorの更新周期を5Hzくらいに下げてみることも検討」で、monitor の executor を単一の thread にし（M1）、SSE で画面へ送る snapshot を最大 5 Hz に間引いた（M2、PRM-104 `ui_sse_max_rate_hz` 5.0、間の変化は最新にまとめて送る）。
- 単体試験 Mac 297 件 OK（skip 14）・VM 297 件 OK、設計検査 違反 0・未判定 5（intent 由来の既存の失敗はそのまま）。monitor を単体で起動して stub のサービスの答えが 22〜30 ms で返ることを確認。人の指示で VM の Gouda に反映（manual を確認、04:1x 再起動）：gouda_monitor 99.4 % → 2.8 %、SSE 16.6 → 5.0 回/s。IMU の差し直しの後（IMU あり、ESP32 の STATUS なし、manual）で 8.7 %。地図作成は始まっておらず、ESP32 の STATUS がある条件は未計測。ESP32・IMU の USB の差し直しが要る（人）。コミットはまだ。

**第161便: gouda_monitor の CPU 100 % の原因（調査だけ）**（作業記録 `reports/worklog/2026-10-24_bin161_monitor_cpu.md`、証拠 `research/vehicle_pc/2026-10-24_monitor_cpu/`）。
- (1) ESP32 の STATUS（PRM-49 50 ms＝20 Hz）を受けるたびに、画面の全体（約 63 KB、地図と routes の index をファイルから読む）を SSE で送っている：24 回/s・1.5 MB/s。ブラウザも 27〜100 % を使う。(2) rclpy の MultiThreadedExecutor が重い：同じ購読の probe で multi 65〜69 %、single 5〜16 %。
- 案 M1（single に）・M2（SSE の回数を抑える）は承認待ち。コード・設定は変えていない。

**第160便: run-cdde4c29 が走った後に止まった原因（読むだけ）**（作業記録 `reports/worklog/2026-10-24_bin160_tf_lag_run_cdde4c29.md`、証拠 `research/vehicle_pc/2026-10-24_autonomy_stop_run-cdde4c29/`）。
- 約 12 s 走って waypoint を 3 つ過ぎた後、第157便と同じ TF エラー（error_code 102、map→odom が 0.39 s 古い）で一時停止。遅れは累積ではなく一時的（ふだん 0.13 s、16〜22 s に 0.24〜0.64 s、その後 0.13 s に戻る）。
- CPU：controller は平均 10 Hz（設定 20 Hz）、gouda_monitor の主の thread が待機中でも 100 %。原因は未調査（B'）。今回は ESP32 の再起動で seq の棄却はなかった。
- 候補 C（map→odom の時刻の決め方）などは人の判断待ち。コード・設定は変えていない。
- 追記：走り出しの「collision ahead」の距離は rosbag がなく不明（2.5 m 以内、経路の先 1 s ぶん以内）。高さの帯が odom・map の z（原点は IMU の高さ）で当たり、実際は地面から約 1.0〜2.2 m の物を障害物にしている可能性が高い（DEC-336、承認待ち）。低い障害物が見えていない恐れ。

**第159便: 再び車両が動かなかった原因（ESP32 が PC の指令をすべて棄却）と DAC の勾配の確認（読むだけ）**（作業記録 `reports/worklog/2026-10-24_bin159_esp32_seq_rejection.md`、証拠 `research/vehicle_pc/2026-10-24_esp32_seq_rejection/`）。
- 03:10・03:17・03:19 の自律走行で、ESP32 が COMMAND を 1210 回「seq が新しくない」で棄却し、PC の出力は一度も使われなかった（DAC は中立のまま）。VM・Gouda だけが再起動し、bridge の seq が 1 から数え直された一方、ESP32（02:35 から起動したまま）は last_pc_seq 1643 を覚えていた。分類は実装（＋プロトコルの文書の不足）。
- 電圧を急に上げてはいない（今回は出力なし）。勾配は Nav2 の velocity_smoother（PRM-68 1.2 m/s²、PRM-73 2.0 rad/s²。前進 ≒2130 mV/s、旋回 ≒4580 mV/s 相当）だけで、ESP32 と motion controller にはない。「勾配をつけろ」の指示は記録に見つからなかった。
- 候補 F（bridge が ESP32 の last_pc_seq から続ける）・G（pc_enabled を走り出しの条件に）・H（DAC の勾配の決め方）は人の判断待ち。回避は ESP32 の USB の差し直し（人の作業、未確認）。コード・設定は変えていない。

**第158便: 自律走行開始で中立を先に送る（REV-181、DEC-391）**（作業記録 `reports/worklog/2026-10-24_bin158_early_neutral_dec391.md`）。
- 人の指示「Aを実行せよ。自律走行開始を押したら、中立信号をまず送る。その間にNav2とが立ち上がったりする」で、TR-05 の最初に ND-11・ND-12 を活性化するようにした（motion_hold は true のままなので中立が ESP32 に届き、その間に GLIM・ND-07・Nav2 が起動する）。autonomy_client・mode_manager_node と新しい試験 test_tr05_start_order（3 件）。
- 単体試験 Mac 296 件 OK（skip 14）、VM 296 件 OK。設計検査 違反 0・未判定 5（intent 由来の既存の失敗はそのまま）。結合試験・実車は未実行。人の指示で VM の Gouda に反映し起動した（停止中・manual を確認、03:06、Traceback なし、manual）。XT-32・GNSS は absent（人の接続待ち）。コミットはまだ。

**引き継ぎ: `reports/handover_2026-10-21_2.md`**（次のチャットの最初に貼るプロンプトは §0。人の判断待ちの一覧は §5。前回の引き継ぎは `handover_2026-10-21.md`。`handover_2026-10-17.md` §5「Global_localization または Navigation のノードの実装の検討」は未着手）。

**第157便: 自律走行 run-ff780d47 が少し動いて止まった原因の調査（読むだけ）**（作業記録 `reports/worklog/2026-10-24_bin157_autonomy_stop_cause.md`、証拠 `research/vehicle_pc/2026-10-24_autonomy_stop_run-ff780d47/`）。
- 止まった直接の原因：Nav2 の controller が map→odom の古さ（0.43 s）で TF エラー（error_code 102）を出して中止、TR-07 で一時停止。map→odom は GLIM の odometry の時刻で出るので、GLIM の遅れがそのまま効く。controller は走行中ずっと 10 Hz（設定 20 Hz）、待機中でも gouda_monitor が CPU 91 %。VM の CPU 不足による GLIM の遅れと推測（止まった瞬間の CPU は未測定）。
- 開始直後の 20 s、ESP32 が PC を有効にしなかった（最初の COMMAND が中立でなかった。中立のときだけ有効になる）。進みの監視と spin の回復が無駄に 1 回走り、有効になってから 13 s 走った。
- 別の問題：local costmap の keepout フィルタが毎周期 TF で失敗（keepout が効いていない可能性、安全に関わる）、voxel layer が raytrace できない時間、102 を plan_failure と記録。
- 承認・確認の候補 A〜E は DEC にしていない（人の指示待ち）。コード・設定は変えていない。試験・設計検査は未実行。

**第156便: 探索の範囲の試験と S3 の段・上限の案（REV-180）**（作業記録 `reports/worklog/2026-10-24_bin156_search_range_matrix.md`、証拠 `research/vehicle_pc/2026-10-24_search_range_matrix/`）。
- VM の模擬の試験（ROS_DOMAIN_ID 91）：ずれ 1〜4 m × 探索の広がり σ 0.5〜2.0 m の 16 通りすべて正しい位置に合った（誤差 0.07 m）。σ 0.5 m でも 4 m から合う（第148便では 5 m は誤り）。σ 2.0 m は合った直後に短い推定不能が 4 回中 3 回。
- 案（人の判断待ち）：S2 σ 0.5 → S3-1 σ 1.0 → S3-2 σ 1.5（上限）、1 段 90 s。上限の確定には 5 m 以上・他の向き・実の点群の試験が要る。コード・設定は変えていない。

**第154便: 開始の初期位置の順 DEC-385 の承認の記録（REV-178）**（作業記録 `reports/worklog/2026-10-24_bin154_dec385_approval.md`）。
- 人の回答「DEC-385を承認する。」：S1 GNSS → S2 登録した開始姿勢 → S3 範囲を段階的に広げる → S4 人。DEC-356（段階的な探索）も answered。DEC-133 の条件 (2) は準備の段階では自動で次の段に進む形に置き換わる。
- 段の値・上限は tbd（DEC-360）。S1 は DEC-384・388 の後。実装はまだ。設計検査 違反 0・未判定 5（intent 由来の既存の失敗はそのまま）。

**第155便: PRM-92（EKF の位置の標準偏差の上限）を暫定 0.7 m に（REV-179、DEC-358）**（作業記録 `reports/worklog/2026-10-24_bin155_prm92_dec358.md`）。
- 人の指示「DEC-358を承認するから、実装せよ。」で 0.5 → 0.7 m。生成物 gouda_global_localization.yaml に反映、コードは変えていない。localization の単体試験 17 件合格。
- VM にはこの 1 ファイルだけを写した（Gouda は停止中、次の起動から効く）。DEC-385（別のチャットで実装中）のコードには触れていない。設計検査 違反 0、intent 由来の既存の失敗はそのまま。コミットはまだ。

**第153便: 障害物の高さの帯の上端 PRM-71 を地上 1.25 m に（REV-177、DEC-324）**（作業記録 `reports/worklog/2026-10-24_bin153_prm71_dec324.md`）。
- 人の指示「DEC-324は1250mmに変更せよ。」で PRM-71 を 1.185 → 1.085 m（base_link 基準、地面から 1.25 m、余裕なし）。生成物 gouda_nav2.yaml に反映、Nav2 の設定の単体試験 14 件合格。人の指示で VM に写した（Gouda は停止中・最後のモードは manual だったので起動していない。次の起動で読み込む、未確認）。
- PRM-03（全高）は intent.md の記録（AR-017）のときに、PRM-36（地図の上限 1.35 m）は変えていない。設計検査 違反 0・未判定 5（intent 由来の既存の失敗はそのまま）。コミットはまだ。

**第152便: 自己位置推定の判断 1〜3 の回答の記録、DEC-291 の保留、判断 4 の作り直し（REV-176、DEC-382〜390）**（作業記録 `reports/worklog/2026-10-24_bin152_localization_answers_gnss_states.md`、提案 `proposals/localization_start_gnss_states_2026-10-24.md`）。
- 人の回答（DEC-382）：判断 1〜3 は推奨案を許可 → DEC-365・350・342・306（故障の種類で分ける、待機に入らない）、DEC-286・358（PRM-92 暫定 0.7 m）・352、DEC-351・353（再初期化は予算の中の探索）を answered。DEC-291 は保留。
- 判断 4 は人の指示で作り直し：GNSS の状態 G1〜G5（良い・悪い・出ない・揺らぐ・地図と対応なし）でも動く作り。承認待ち DEC-383〜388、確認待ち DEC-389（intent.md 11 行の Nav2 の文と DEC-359）、実測 DEC-390。
- PRM-92 の値の変更（許可済み）は未反映。D・T などの暫定値は未定。intent.md は人が改善した（SHA-256 857661bd…）が未記録（AR-017。誤字・未完の文があり、編集の終わりの確認待ち）。設計検査 違反 0・未判定 5、intent 由来の既存の失敗あり（intent_identity も）。コミットはまだ。

**第151便: KUAMS の調査の証拠の登録と、トラブルシューティング台帳への TRB-006〜012 の登録（REV-175）**（作業記録 `reports/worklog/2026-10-23_bin151_kuams_evidence_troubleshooting.md`、証拠 `research/kuams_tc2025_2026-10-23/`）。
- 人の指示「判断台帳等への登録を進めよ」で行った。
- **証拠の登録**：FILE-KUAMS-TC2025-* の 6 件
  - 本走行の結果の CSV。個人名の 2 列を除いた（notes.txt に明記）
  - 読んだ KUAMS の commit の一覧
  - 比較・まとめ・文献の写し
- **トラブルシューティング台帳**
  - TRB-006：塞がれた waypoint の後の U ターン
  - **TRB-007（発生）**：回復が効かない種類の失敗で、PRM-18 に関係なく中止され待機に入る。第104便の VM で 1 回起き、未解決
  - TRB-008：waypoint の向きがすべて 0 で、最後の点でその場で回る
  - TRB-009：RPP の検査と local costmap が既定値のままで、急に現れた物の前で止まり切れない
  - TRB-010：途切れの間の EKF の外挿で、戻ったときに map→odom に段差が入る
  - TRB-011：幅の広い物で計画が失敗し続け、滞留する
  - TRB-012：速い旋回で、deskew していない点群が NDT を乱す
- 新しい DEC はない。コード・設定は変えていない。設計検査は違反 0・未判定 5（既存の intent.md 由来の失敗はそのまま）。コミットはまだ。

**第150便: KUAMS（関西大、TC2025 で完走）の工夫を取り入れるかの検討の登録（REV-174、DEC-365〜381）**（作業記録 `reports/worklog/2026-10-23_bin150_kuams_adoption_review.md`、提案 `proposals/kuams_adoption_review_2026-10-23.md`）。
- 6 つのトピックをエージェントで検討し、人の指示で承認・確認・実測と記録の訂正を登録した。コード・設定は変えていない。
- **承認待ち**
  - DEC-365：推定不能を故障の種類で分ける（DEC-342 c の具体化）
  - DEC-366：stop で区切った区間ごとの goal と、その区間だけの自動の出し直し（DEC-307）
  - DEC-367：opt-in で waypoint を飛ばす（DEC-344 (2) の再確認を含む）
  - DEC-370：待機列の段階 queue_follow
  - DEC-371：大域の上限は変えず区間の速度上限で遅くする。RPP と local costmap の値を PRM にする
  - DEC-373：軌跡から waypoint の候補を作る道具
- **確認待ち**
  - DEC-368：TK-70 は本走行に適用されるか
  - DEC-369：待機列の扱い
  - DEC-372：collision_monitor は intent の範囲に入るか
  - DEC-380：実装の抜け（Mission が kind を落とす、waypoint の向きが 0）
- **実測待ち**：DEC-374〜379
- **記録の訂正**：DEC-381。DEC-343・345 の「規則の原文を読んでいない」を置き換える
- 設計検査は違反 0・未判定 5（既存の移行の違反 2 件・test_real_model の不合格・input_integrity の FAIL はそのまま）。コミットはまだ。

**第149便: monitor の /config で入力欄と保存ボタンに届かない不具合の修正（REV-173、DEC-364）**（作業記録 `reports/worklog/2026-10-23_bin149_config_tab_scroll.md`）。
- 原因：サブタブのパネルが overflow hidden で、高さ 100% のままサブタブの行の下に置かれてはみ出し、display block が縦並びを上書きしていた（実装の誤り）。
- 人の指示で、/config タブの中を縦に並べ、表示中のサブタブのパネルを中でスクロールできるようにした（style.css のみ、3 つのサブタブ）。デモの monitor で 3 つとも確認（ホイールも）、monitor の単体試験 27 件 OK。人の指示で VM に写して `gouda.sh start`（止まっていたため）、VM の画面で 3 つとも確認（センサ取付は入力欄 20、ホイールで保存ボタンまで届く）。Gouda は MANUAL で起動したまま。第146便とあわせて web の 2 ファイルだけを PR #19（fix/monitor-panel-scroll-2026-10-23、8aa1d9d）に出した。記録（REV-171・173 ほか）は未コミット。
- 設計検査 違反 0・未判定 5（既存の移行の違反 2 件・検査器の試験の不合格 1 件はそのまま）。

**第148便: 初期位置の探索の切り分けの試験（DEC-360 (1)）**（作業記録 `reports/worklog/2026-10-23_bin148_initial_search_offsets.md`、記録 `research/vehicle_pc/2026-10-23_initial_search_offsets/`）。
- VM の模擬の試験（ROS_DOMAIN_ID 89、動いている Gouda には触れず）：0 m・90°、0 m・180°、1 m・90°、3 m・0° は正しく合った（誤差 0.07 m）。**5 m・0° は 5.86 m 離れた誤った位置に合い、NVTL 2.67 で「正常」**と判定した。向きのずれは原因ではなく、位置のずれが原因。
- 3 m・0° では、合った後に推定不能と正常を数回行き来した（原因は未調査）。トラブルシューティング台帳に TRB-005 を足した。コード・設定は変えていない。

**第146便: monitor の waypoint タブで waypoint セットの選択欄に届かない不具合の修正（REV-171、DEC-363）**（作業記録 `reports/worklog/2026-10-23_bin146_waypoint_tab_scroll.md`）。
- 原因：画面とパネルが overflow hidden で、右パネルの表が長くなると「AUTO 自律走行の準備」がパネルの外に押し出されていた（実装の誤り）。
- 人の回答「Bで」：AUTO の欄を右パネルの一番上に移し、waypoint タブの両パネルを中でスクロールできるようにした（web の index.html・style.css）。デモの monitor で確認、monitor の単体試験 27 件 OK。人の指示で VM の Gouda に反映し（MANUAL・idle を確かめてから。2 ファイルの上書きだけで再起動なし）、VM の monitor の画面で確認した。コミットはまだ。
- 設計検査 違反 0・未判定 5（既存の移行の違反 2 件・検査器の試験の不合格 1 件はそのまま）。

**第147便: NTRIP の中継を TLS で包む実装（REV-172、DEC-361 回答：stunnel4）**（作業記録 `reports/worklog/2026-10-23_bin147_ntrip_tls_relay.md`）。
- 人の指示「認証系を直して」と選択「stunnel4 で包む」で実装。str2str は 127.0.0.1 の stunnel4 にだけつなぎ、stunnel4 が caster へ TLS（証明書とホスト名を確認）。stunnel4 がなければ中継を起動しない（平文の道なし）。TLS の出来事は ntrip_tls_state で記録。setup.sh に stunnel4・ca-certificates。
- 試験：Mac 293 件・VM 293 件 OK。実の stunnel4＋str2str で caster から 30 秒に RTCM3 181 frame を受けた（出力はファイル。受信機は外れていた）。
- VM の Gouda に反映（手動モードを確認して再起動）。1 回目の反映で、起動しない中継が見張りの thread を落とす回帰（既知の host_ip の不具合に落ちる）を起こし、直して再反映。今は Traceback なし、中継は「stunnel4 is not installed」で止まっている。
- 追記（23:48〜）：stunnel4 を入れ、受信機を VM につないだ後、中継は自動で起動し TLS connected・input connected になった。受信機は衛星を受けておらず（PVT mode 0・error 1）、RTK は未確認。DEC-362 は回答待ち。コミットはまだ。

**第145便: NTRIP が使えない原因（REV-170、DEC-361・362）**（作業記録 `reports/worklog/2026-10-23_bin145_ntrip_tls_cause.md`、証拠 `research/vehicle_pc/2026-10-23_ntrip_tls_probe/`）。
- 原因：caster の port は TLS 専用。平文の要求は 0.13 s でリセット。TLS では認証・mountpoint とも受け付けられた（v1 ICY 200 OK、v2 HTTP 200）。apt の str2str（RTKLIB 2.4.3 b34）には TLS がなく、今の中継ではつながらない。
- 承認待ち DEC-361（TLS 対応：推奨 stunnel4 で包む）。確認 DEC-362（str2str と AI の診断が認証を平文で送っていた。パスワードの変更の検討）。
- 未確認：TLS で GGA を送った後の RTCM の受信（20:06 に受信機の USB が VM から外れ、ドライバが落ちたため未実行）。

**第144便: GNSS の 2 アンテナと NTRIP の状態の確認（読むだけ）**（作業記録 `reports/worklog/2026-10-23_bin144_gnss_dual_ntrip_check.md`）。
- 2 アンテナ：ドライバの設定は multi_antenna true で、受信機も向きを計算しようとしているが、AttEuler は mode 0・error 1（Main-Aux1 の測定が足りない。Reference Guide で確認）。向きは出ていない。
- NTRIP：中継（str2str）は動いているが「input waiting」のまま。補正が届かず、単独測位（衛星 16、水平精度 8.2 m）。RTK は効いていない。
- 受信機・設定には触れていない。原因（副アンテナの配線・設置、caster への接続）は未確認。

**第143便: 初期位置の推定・開始の速さ・確認用の表示（REV-169、DEC-355〜360）**（作業記録 `reports/worklog/2026-10-23_bin143_initial_localization_questions.md`）。
- 人の発言を記録（DEC-355）。以前の失敗は「5 m・90 度」で、探索は向きを一周試すため、主因は位置のずれ 5 m（探索の広がりは標準偏差 0.5 m）と推測。
- 承認待ち：DEC-356（探索の範囲を 1 m から段階的に広げる）、DEC-357（確認用の表示に VM の rviz2 を使う。新しいプログラムなし）、DEC-358（PRM-92 を暫定 0.7 m）、DEC-359（準備の段階で推定と Nav2 の起動を済ませる＋DEC-287 の推奨案）。試験・実測 DEC-360。
- コード・設定は変えていない。設計検査 違反 0・未判定 5。

**第142便: 推定不能の間の補い方の調べと提案（REV-168、DEC-350〜354）**（作業記録 `reports/worklog/2026-10-23_bin142_localization_gap_bridging.md`、提案 `proposals/localization_gap_bridging_2026-10-23.md`、証拠 `research/vehicle_pc/2026-10-23_glim_odom_drift/`）。
- 推奨：新しいフィルタ（IMU の予測・因子グラフ）は今は足さない（エンコーダ・GNSS がなく、使える情報が増えない）。原因で分ける：LiDAR の途切れ（GLIM も止まる、2.7〜4.2 s）は止まって待つ。照合の質の低下は map→odom を固定して GLIM で進み、距離 D・時間 T を超えたら止まって待つ → 止まったまま再初期化。戻すときは NDT と GLIM の一致を連続 N 回確かめてから寄せる。値はすべて rosbag の再生に故障を入れて測る（DEC-354）。
- 記録から：GLIM の odometry のずれの下限は 50 m あたり p95 0.06〜1.18 %（基準は真値でない）。止まっている間はずれない。人混み・段差・走行中の推定の失敗の記録はない。
- 上流のソースで確かめた：NDT は収束しないと姿勢を出さない。EKF の棄却は 2 乗でない距離と 49.5 を比べるので実質ない（PRM-91 の説明は実態と違う）。
- 承認待ち DEC-350〜353、実測 DEC-354（外付けの接続と新しい記録は人の作業）。第143便の DEC-356（探索の範囲）・DEC-358（PRM-92 暫定 0.7 m）と関係する（再初期化 DEC-353、ずれの目安に EKF の共分散を使わない DEC-352）。
- 実装なし。設計検査 違反 0・未判定 5。移行の違反 2 件・検査器の試験の不合格 1 件は intent.md の未記録の編集による（既存）。コミットはまだ。

**第141便: 規則の操作の範囲、経路の引き直しの頻度 PRM-103 の実装、障害物の扱いと段差（REV-167、DEC-347〜349）**（作業記録 `reports/worklog/2026-10-23_bin141_replan_rate_and_rules.md`）。
- 人の回答（DEC-345）：異常のときにチームメンバーがボタンを押すと走行失敗。再開ボタンは停止線で止まった後か信号が青になった後だけ。停止線での再開に PC のボタンは使ってよい。
- 人の指示で、Nav2 の経路の引き直しの頻度を PRM-103＝1 Hz（暫定、上流は 0.333 Hz）にし、monitor の /config「Nav2」タブで変えられるようにした（nav2_config・monitor・web、試験つき）。Mac 287 件・VM 287 件の単体試験は合格。VM の Gouda に反映済み（手動モードを確かめてから再起動。生成された BT の hz 1.0、Nav2 タブの表示、不正な値の拒否を確認）。VM にセンサーはつながっていない。
- 記録：障害物を遠くから認識して近づくにつれて更新する人の案（DEC-348）、段差での GLIM・NDT の確認（DEC-349、実測待ち、TRB-004）。
- 設計検査 違反 0・未判定 5。コミットはまだ。

**第140便: 状態遷移の再設計の提案（REV-166、DEC-342〜346）**（作業記録 `reports/worklog/2026-10-23_bin140_state_transition_redesign.md`、提案 `proposals/state_transition_redesign_2026-10-23.md`）。
- モードは 4 つのまま。自動で待機に入るのは最後の waypoint だけ。推定不能・Nav2 の失敗・滞留・部品の復帰・停止線の待ちは、自律走行モードの中の処理の段階で表す（TR-07・TR-09 をなくす）。DEC-305〜314 と DEC-340・DEC-332 をまとめた。
- 横断歩道：既存の waypoint の kind: stop を使い、区切りごとに goal を出す。止まったら人の「横断を始める」操作で次へ（DEC-343）。
- 承認・確認・実測待ち：DEC-342（推定不能は「少し進んでから待つ」案）、DEC-343、DEC-344（場所ごとの inflation、waypoint を飛ばす段の制限）、DEC-345（待機ボタンは規則上許されるか）、DEC-346（実測）。実装なし。

**第139便: 規則の読みの訂正と、推定不能での自動の待機についての人の発言の記録（REV-165、DEC-339〜341）**（作業記録 `reports/worklog/2026-10-23_bin139_rule_corrections.md`）。
- 人が規則を確認：3 分以上の滞留が失敗なのは確認走行区間（ほかは記載なし）。確認走行中の緑のコーンへの接触は失敗。歩行者にぶつかると失敗。制限時間 100 分、スタートは 1 分以内にスタートライン・2 分以内に 20 m。狭い所は迂回すればよい（DEC-339）。
- 人の発言：推定不能で即待機に入るのは良くない。自動の待機は削除してよい気がするが、状態遷移の再設計が要る（DEC-340）。
- 確認待ち：DEC-341（コーン・歩行者のため、DEC-321 の local の 2 次元化と DEC-322 を見直すか）。トラブルシューティング台帳に接触が失敗になることを書き足した。
- intent.md が人に編集された（15:08、全高 1250 mm、monitor の表示の行の追加）。未記録（AR-017 は編集の終わりの確認待ち）。このため移行の違反 2 件。設計検査は違反 0・未判定 5。

**第138便: costmap 第2版・第134便の問いへの人の回答の記録と、トラブルシューティング台帳の作成（REV-164、DEC-319〜338）**（作業記録 `reports/worklog/2026-10-23_bin138_answers_troubleshooting.md`）。
- 人の回答 A1〜A9・B1〜B5 と、第130便でチャットにしか残っていなかった回答（A〜E）を原文で記録した。
- 決まったこと：帯の段は rosbag で比べる（人が rosbag を用意するまで待つ）、local は 2 次元の ObstacleLayer（一旦採用）、点のない方位を消去に使う、点群の途絶を Nav2 で検出しない（保護の削減）、costmap の凍結は 12/1（暫定）、**モード名「一時停止」を「待機」に変える**、**横断歩道の状態遷移を最優先で作る**（waypoint の属性で止まり、人が再開）、走行・実験は VM で行う（人が指示するまで）、LAN はハードウェアを改良済み、Nebula は後回し。
- 人の申告：コーンの課題（目の前に置かれたコーンの回避、ランダムに置かれた区間の通過）があり、XT-32 だけでは無理。第2版の「本番前は XT-32 だけ」は取り下げ、MID-360 を入れる第3版を作る。車両の最大高さは実測でおよそ 1.25 m。
- トラブルシューティング台帳 `design/troubleshooting/ledger.yaml` を作り、TRB-001（2 次元の local で低い物に衝突）・TRB-002（点のない方位の消去で反射の弱い物に衝突）・TRB-003（途絶を検出せず古い costmap で走る）を登録した。
- 確認・承認待ち：DEC-324（帯の上端）、DEC-331（名称変更の範囲）、DEC-336（base_link の帯）、DEC-337（距離の PRM 化）、DEC-338（案 A〜E の扱い）。
- 検査：設計検査 違反 0・未判定 5。移行の違反は既存の 6 件。検査器の試験 88 件のうち既存の 1 件（test_real_model）だけ不合格。新しい台帳の試験 5 件は合格。実装なし。コミットはまだ。

**第137便: intent.md 第16版の記録（REV-163、AR-016、DEC-318）**（作業記録 `reports/worklog/2026-10-23_bin137_intent_v16.md`）。
- 人の編集（1 行目の目的の文：「自動的にgoudaが一時停止モードに入って自律走行が出来なくなったり」）を記録した。新しい要求は RQ-I095。RQ-I089 を superseded にした（C-031）。
- 検査：設計検査は違反 0・未判定 5。intent の照合は合格。移行の違反は既存の 6 件。検査器の試験は既存の 1 件だけが不合格。コミットはまだ。

**第135便: 検査器の試験の見本の差し替え（REV-162、DEC-317）**（作業記録 `reports/worklog/2026-10-22_bin135_test_fixture.md`）。
- 人の許可（原文）で、`test_superseded_requirement_needs_intent_justification` の見本を RQ-I001 から RQ-I002 に替えた。合否の基準は変えていない。この試験は合格し、規則を壊した写しで検出されることも確かめた。
- 検査の途中（23:45）に、人が intent.md の 1 行目をもう一度編集した（SHA-256 23170969…）。まだ AR-016 に記録していない（人が編集を終えたかの確認待ち）。このため、intent の照合と移行の検査は違反、検査器の試験は 2 件不合格。設計検査は違反 0・未判定 5。コミットはまだ。

**第133便: intent.md 第15版の記録（REV-161、AR-015、DEC-315・316）**（作業記録 `reports/worklog/2026-10-22_bin133_intent_v15.md`）。
- 人の編集を記録した。目的に本番の失格の条件、必達は 2.2 km の完走、16 行に Nav2 の失敗で「一時停止モードに入らずとも良い」、33 行に優先順位「0. 本番で完走できる」、39 行に保護削減は報告し台帳に記録、94 行に PC 再起動の後は自律走行に戻る。
- 新しい要求は RQ-I089〜094。旧要求 5 件を superseded にした（C-030）。
- 確認待ち DEC-316：事前地図作成からの PC 再起動の復帰先、一時停止しない場合の振る舞い、優先順位の 0、39 行と DEC-106 の関係。回答までは DEC-106 に従い、実装しない。
- 検査：設計検査は違反 0・未判定 5。移行の違反は HEAD と同じ既存の 6 件。検査器の試験で、新しく 1 件が不合格（RQ-I001 を見本に使う試験の前提が崩れた。直すのは許可の後）。コミットはまだ。

**第132便: 本番で自動で一時停止しない方針の承認事項（REV-160、DEC-304〜314）**（作業記録 `reports/worklog/2026-10-22_bin132_competition_no_auto_pause.md`、提案 `proposals/competition_no_auto_pause_2026-10-22.md`、intent.md の編集依頼 `proposals/intent_edit_request_competition_2026-10-22.md`）。
- 人の発言（DEC-304、原文）：本番では、一時停止モードに入ること、3 分の滞留が失格になる。衝突は失格ではない。必達は 2.2 km の完走。大会の規則の原文は未照合。
- 確定済みの DEC-200 と intent.md の 15・93・38 行と衝突するため、次を pending で登録した。
  - DEC-305：方針と intent.md の修正案
  - DEC-306：推定不能
  - DEC-307：Nav2 の失敗
  - DEC-308：ドライバの作り直し
  - DEC-309：PC 再起動の後の自動復帰
  - DEC-310：滞留の段階
  - DEC-311：motion_hold
  - DEC-312：ESP32 の再許可
  - DEC-313：回避の設定
  - DEC-314：実測
- 作業中に、人が intent.md の 15 行を編集した（「一時停止モードに入らずとも良い」）。第133便で、編集を終えた版を AR-015 として記録した。
- 設計検査：違反 0・未判定 5。実装はしていない。コミットもまだ。

**第131便: RxTools での検査の手順（REV-159、DEC-303）**（作業記録 `reports/worklog/2026-10-22_bin131_rxtools_checklist.md`、手順 `research/rxtools_inspection_checklist_2026-10-22.md`）。
- 人の指示: RxTools（Windows の VM）でまず検査する。測位を繰り返し試さない。受信機は屋内。
- 手順: 受信機を Windows の VM に渡し、検査の間は Ubuntu で Gouda を起動しない。設定の全体（Current・Boot・RxDefault）、アンテナの給電と過電流、前段ごとの AGC、スペクトル、追尾を止めうる設定を、変えずに読む。受信機には触れていない。コミットはまだ。

**第136便: costmap の入力の直しの提案 第2版（完走優先）**（作業記録 `reports/worklog/2026-10-22_bin136_costmap_proposal_v2.md`、提案 `proposals/costmap_inputs_completion_v2_2026-10-22.md`。第1版を置き換え）。
- 本番前は XT-32 だけ。高さの帯を base_link で当てる（pcl_ros PassThrough と pointcloud_to_laserscan を rosbag で比べて選ぶ）、local を ObstacleLayer に、距離 2.5・3.0 m を PRM で明示、expected_update_rate は 0 のまま（保護の削減として記録）。STVL・MID-360・Nebula・PTP・地面の推定は本番の後。
- 承認事項 V2-1〜V2-6・人の判断 1〜9 は台帳に未登録。実装・計測なし。

**第134便: 点群・costmap・時刻・計算資源の、完走優先での再検討（4 つのエージェント）**（作業記録 `reports/worklog/2026-10-22_bin134_costmap_review_completion.md`）。
- 690 件の時刻差の警告は LiDAR の LAN のリンク断（2.7〜3.5 s の途切れ）と合う。本番では推定不能 → 一時停止になる。Nebula・PTP は本番の後へ。
- 第130便の提案は完走優先では P-1・P-3・P-6・P-8 の向きが逆（提案の冒頭に注）。残すのは base_link の帯（P-4）と距離の明示（P-7）。
- costmap の待ちの打ち切り（CONTROLLER_TIMED_OUT）は BT の回復の対象外（Nav2 1.3.13 で確認）。
- 規則: 停止線・道路端での停止（EV-22）は未設計、スタートの後の操作は失格（EV-19）。計算資源の数値は VM のもので、G15 では未計測。台帳には未登録。

**第130便: 点群の送受信の無駄の調べと、costmap の入力の作り直しの提案**（作業記録 `reports/worklog/2026-10-22_bin130_costmap_inputs_proposal.md`、提案 `proposals/costmap_inputs_stvl_mid360_2026-10-22.md`）。
- 生の XT-32 点群を自律走行中に 4 プロセスが購読。costmap は全点を変換してから大半を捨てる。高さの帯は base_link 基準の定義なのに odom・map の z で当たっている（標高で低い物が見えなくなる）。点群の途絶を Nav2 が検出しない。
- 提案（段階 1）: pcl_ros で base_link の帯・距離を切り、local costmap は STVL、global は ObstacleLayer のまま。MID-360 は livox_ros_driver2。承認事項 P-1〜P-9・実測 M-1〜M-11 は**台帳に未登録**（仮の番号）。人の回答 A・C・D・E（チャット）も未登録。
- 実装・計測なし（VM に接続できず）。コミットはまだ。

**第129便: GNSS が衛星を追尾しない件の調べ（REV-158、DEC-299〜302）**（作業記録 `reports/worklog/2026-10-22_bin129_gnss_no_tracking.md`、記録 `research/gnss_no_tracking_investigation_2026-10-22.md`）。
- 受信機は屋外でも衛星の信号を 1 つも受けていない。2026-10-19 朝は屋内で衛星 13〜17 を捕まえていたが、AI が勧めた DualAnt と reset の後から捕まえなくなった。Gouda のコードが原因の証拠はない。
- AI の誤り: 2026-10-20 の観測 0 を「屋内だから」とした（確かめていない仮定）。
- 承認待ち: DEC-299（T1 読むだけで AGC・アンテナの状態）、DEC-300（T2 Nominal に戻す）、DEC-301（caster の確かめ）、DEC-302（monitor・中継の改善）。人の確認: 10-19 の後にアンテナ・ケーブルを替えたか。コミットはまだ。

**第128便: GNSS まわりの現状と改善点の提案（REV-157、DEC-294〜298）**（作業記録 `reports/worklog/2026-10-22_bin128_gnss_improvements.md`、提案 `proposals/gnss_improvements_2026-10-22.md`）。
- 2026-10-22 の実の地図作成 3 回の GNSS はすべて解なし・方位なし。今の地図はどれも GNSS と対応づけられない。屋外の方位の確認と RTK（中継）は未確認（VM に str2str と gnss_rtk.yaml はある）。
- 提案: 屋外で方位と RTK を 1 回で確かめる、RTK fix を確かめてから地図作成。小さな実装の承認待ち: DEC-294（地図作成の GNSS の警告と manifest の質の要約）、DEC-295（副アンテナの見張り）、DEC-296（ntp_server false）、DEC-297（受信機の状態の記録）、DEC-298（NTRIP v1・TLS なしの受け入れ）。
- 検査: 設計検査 違反 0・未判定 5、移行の違反は既存の 6 件。コード・設定は変えていない。コミットはまだ。

**第127便: 人混み・他のロボットの中での自己位置推定の対策の提案（REV-156、DEC-290〜293）**（作業記録 `reports/worklog/2026-10-22_bin127_crowd_localization.md`、提案 `proposals/crowd_robust_localization_2026-10-22.md`）。
- 車輪のエンコーダがないため、GNSS が切れると位置を保てるのは LiDAR だけ。「GNSS＋IMU が主、LiDAR は補助」は危ないと判断。
- 推奨：NDT の入力を人の頭より高い点に絞る（DEC-291）→ 人混みの記録で評価（DEC-293、実測）→ RTK fix の GNSS と NDT を品質で重み付けして融合（DEC-290）。エンコーダは評価の後に判断（DEC-292）。
- 検査：design_check 違反 0・未判定 5、run_checks の違反は既存の 6 件。コード・設定は変えていない。コミットはまだ。

**第126便: DEC-289 の実装（REV-155、地図作成の終わりの姿勢）**（作業記録 `reports/worklog/2026-10-22_bin126_dec289_end_pose.md`）。
- 人の指示（原文）で案 a。waypoint タブに、地図作成の終わりの車体の姿勢（黄の矢印）と「地図作成の終わりの姿勢を初期位置にする」ボタン。
- 試験
  - Mac の単体試験は合格。
  - 実際の地図作成の終わりの姿勢 (−0.371, −0.216, −97.6°) は、ND-07 の推定 (−0.36, −0.20, −97°) と 0.02 m で合う。
  - demo の monitor で、矢印とボタンを確かめた。
- VM（人が起動した後）：単体試験 285 件合格。Gouda を起動し、実機の monitor で矢印・ボタン・プレビューを確かめた（自律走行は送っていない、mode は手動）。
- VM の再起動の後、センサーは 3 つとも未受信（USB の接続を人が確かめる）。コミットはまだ。

**第125便: 「止まったまま作った地図」での自己位置推定の失敗の根本の調べ（REV-154、DEC-288・289）**（作業記録 `reports/worklog/2026-10-22_bin125_root_cause.md`、記録 `research/vehicle_pc/2026-10-22_mapping_motion/`）。
- 地図作成の間、GLIM は ESP32 の手動の優先（manual_override）の間だけ動いた（7.54 m・514 度）。止まっている間はずれていない。車体は実際に動いたと推論する。
- 自己位置推定は正しかった：地図作成の終わりの姿勢と、人の開始の推定 (−0.36, −0.20, −97°) が合う。人が置いた初期姿勢（円の中央）が 1.4 m 違った。
- 開始が止まった理由は、Nav2 が残った件（DEC-287）と EKF のしきい値（DEC-286）。第121・123便の「初期化がばらつく」は、車体が動いていたことを考えていなかった（訂正）。
- 確認待ち：DEC-288（地図作成の間にゲームパッドを操作したか。していないなら安全の問題）。提案：DEC-289（地図作成の終わりの姿勢を waypoint タブに表示し、初期姿勢の候補にする）。
- VM：一時停止のまま、Nav2 が残り、IMU が USB から外れている。

**第124便: 人が本当の位置で開始した試行の調べ（REV-153、DEC-287）**（作業記録 `reports/worklog/2026-10-22_bin124_nav2_left_active.md`、記録 `research/vehicle_pc/2026-10-22_nav2_restart/`）。
- 人が新しい地図・waypoint・本当の位置で開始した。ND-07 は 29.6 秒で正常になったが、Nav2 の STARTUP が失敗した（map_server が動いたまま）。今も一時停止。
- 原因：第123便の開始が STARTUP の最中に捨てられ、Nav2 が動いたまま残った（終了で RESET されない競合、実装の誤り）。
- 承認待ち：DEC-287（推奨 a：STARTUP の前に記録して、終了で必ず RESET）、DEC-286。
- 推定の位置 (−0.36, −0.20)、向き −97° は、人の設定 (−1.32, −1.43, −90°) と約 1.5 m 違う（どちらが正しいか人の確認待ち）。

**第123便: 実車（VM）での 4 回目の自律走行開始（REV-152、DEC-286）**（作業記録 `reports/worklog/2026-10-22_bin123_autonomy_run4.md`、記録 `research/vehicle_pc/2026-10-22_autonomy_run4/`）。
- 人の指示（原文）で、一時停止を終了してから、Claude が自律走行開始を送った。
- 初期化は 17 秒、18 秒で正常になり、Nav2 の設定と keepout のマスクの確認まで初めて進んだ（DEC-285 の効果）。
- 25 秒に EKF の標準偏差 0.51 m が PRM-92（0.5 m、実測でない）を超えて推定不能になり、TR-07 で一時停止した。goal は送られず、速度の指令は 0 通。
- 推定の位置 (−1.5, 0.08)・向き −67° は、置いた位置から約 2.1 m・47° 離れている（これまでの結果とも違う）。Claude は再開せず終了した。
- 人の確認待ち：本当の位置・向き。承認・実測待ち：DEC-286（推奨 a：EKF の標準偏差を実車で測って値を決める）。

**第122便: DEC-285・284 の実装と VM の試験（REV-151、PRM-102）**（作業記録 `reports/worklog/2026-10-22_bin122_dec284_285_impl.md`、記録 `research/vehicle_pc/2026-10-22_mapodom_fix/`）。
- 人の回答（原文）で、両方とも案 a を採用した。
  - ND-07 は EKF の姿勢をためて、odometry ごとに map→odom を計算する。初回の計算までは初期化中。
  - 前処理は、点が 2（PRM-102）より少ない立方体を捨てる。
- 試験
  - Mac・VM の単体試験は合格。前の作りでは、同じ遅れの場面で map→odom が 0 回だったことも確かめた。
  - VM の模擬の試験（odometry の遅れ 0.15 秒）：観察用の 120 秒の写しで、約 40 秒で合い、50 秒までに正常、推定不能は 0。
  - 30 秒の W3 は、探索が遅く不合格のまま。
- Claude の誤り：人の試行が一時停止中のときに、確かめずに gouda.sh stop を送った。起動し直した後は、その run の一時停止（初期姿勢が要る）に戻っている。
- 未確認：実車での自律走行開始（人の確認待ち）。コミットはまだ。

**第121便: 実車（VM）での 3 回目の自律走行開始（REV-150、DEC-285）**（作業記録 `reports/worklog/2026-10-22_bin121_autonomy_run3.md`、記録 `research/vehicle_pc/2026-10-22_autonomy_run3/`）。
- 人の指示（原文）で、Claude が自律走行開始を送った。
- 入力はすべて届き（点群・NDT・GLIM 10 Hz、EKF 50 Hz）、初期化は 19 秒。前処理は落ちなかった。
- その直後に推定不能（no_map_odom）になり、TR-07 で一時停止した。Nav2 は起動せず、速度の指令は 0 通。
- 原因：EKF の姿勢はいつも odometry より 0.13〜0.25 秒新しく、map→odom の計算が保留のまま行われない（実装の誤り）。
- 承認待ち：DEC-285（推奨 a：EKF の姿勢をためて odometry の時刻で計算し、初回の計算までは初期化中にする）、DEC-284。
- 安全に関わる観察：同じ置き方で、初期化の結果が 3.4 m ほどばらつく。走る前に、人が推定位置と本当の位置を見比べる必要がある。

**第120便: DEC-283 の実装と VM の試験（REV-148・149、gouda_a3_points、DEC-284）**（作業記録 `reports/worklog/2026-10-22_bin120_dec283_impl.md`、記録 `research/vehicle_pc/2026-10-22_a3_points/`）。
- 人の回答（原文）で案 a。A3 の前処理を Gouda の一つのノード gouda_a3_points にした（x・y・z だけを扱う）。
- 試験
  - 実の XT-32 の点群で 10 Hz、落ちない、CPU は 1 コアの 52 %。単体試験は合格。
  - VM の模擬の試験：W3 は 30 秒で探索が終わらず不合格（2 回）。120 秒見ると約 55 秒で正しく合い、正常のまま（推定不能 0）。
  - 探索が遅くなった原因は未確認（点の数ではない見込み）。
- 承認待ち：DEC-284（点が一つの立方体を捨てて前と同じにする、推奨 a）。
- 実車での開始はまだ（人の確認待ち）。コミットはまだ。

**第119便: 実車（VM）での 2 回目の自律走行開始（REV-147、DEC-283）**（作業記録 `reports/worklog/2026-10-22_bin119_autonomy_run2.md`、記録 `research/vehicle_pc/2026-10-22_autonomy_run2/`）。
- 人の指示（原文）で、Claude が自律走行開始を送った。
- 良くなった点
  - 推定不能・一時停止は出なかった。
  - 点群は前処理の 2 段目まで 10 Hz、GLIM の odometry も 10 Hz。
  - 初期化は約 25 秒。
- A3 の VoxelGrid（pcl_ros）が落ち（exit −11）、NDT の入力が来ないので初期化中のまま進まなかった。Nav2 は起動せず、速度の指令は 0 通。Claude が終了させた。
- 実の点群の UINT16・FLOAT64 の field で、VoxelGrid がメモリを壊す疑い（x・y・z だけなら落ちない）。
- 承認待ち：DEC-283（推奨 a：前処理を Gouda の一つのノードにして x・y・z だけを扱う）。
- 初期化の結果は、初期姿勢から 2.3 m 離れている（正しいかは未確認）。

**第118便: DEC-281・282・138 の実装と VM の試験（REV-146、PRM-101、IFD-56）**（作業記録 `reports/worklog/2026-10-22_bin118_dec281_282_impl.md`）。
- 人の回答（原文）で採用：DEC-282 は案 a、DEC-281 は案 a と b、DEC-138。
  - gouda.sh の profile に共有メモリの区画（PRM-101、64 MB）を入れた。
  - monitor は点群を購読せず、ドライバの点群ごとの通知（IFD-56）で受信を見る。
  - ND-07 は、初期化の後、入力が一度ずつ届くまで初期化中（awaiting_inputs）にする。
- 試験
  - Mac の単体試験 272 件、VM の単体試験は合格。
  - VM の模擬の試験：初期化の後、初期化中を経て正常になり、推定不能は 0 件。monitor の points は 10 Hz で RECEIVED。
  - 設計検査は違反 0・未判定 5（run_checks の違反は既存の 6 件）。
- 未確認：実車での自律走行開始（車体が走るので人の確認待ち）。コミットはまだ。VM の作業ツリーは変わっている。

**第117便: 実車（VM）での自律走行開始の試行（REV-145、DEC-281・282）**（作業記録 `reports/worklog/2026-10-22_bin117_autonomy_run.md`、記録 `research/vehicle_pc/2026-10-22_autonomy_run/`）。
- 人の指示（原文）で、Claude が自律走行開始を送った（c2b8d65、人の直前の試行と同じ地図・waypoint・位置）。
- 点群を待ち、約 50 秒で初期化した。その直後に推定不能（input_stale）になり、TR-07 で一時停止した。Nav2 は起動せず、速度の指令は 0 通。
- 原因は二つ。
  - 初期化の直後は入力がまだ届いておらず、必ず一度推定不能を出す。開始の手順はそれで失敗する（DEC-282）。
  - 点群が A3 の前処理と GLIM をほとんど通らない（NDT の入力 0.4 Hz、GLIM 2.8 Hz。DEC-281、DEC-138）。
- 承認待ち：DEC-282（推奨 a）、DEC-281（推奨 a＋b）、DEC-138。コードと設定は変えていない。

**第116便: DEC-279・280 の実装と VM の試験（REV-144、PRM-100）**（作業記録 `reports/worklog/2026-10-22_bin116_dec279_280_impl.md`）。
- 人の回答（原文）で、両方とも案 a を採用した。
  - gouda.sh start は PRM-100（4194304 バイト）から Fast DDS の profile を書き、全プロセスに渡す。共有メモリの区画は既定のまま（DEC-138 は pending）。
  - ND-07 は、NDT が点群を保持するまで待ってから ndt_align_srv を呼ぶ。待つ間は初期化中で、捨てた理由を出す。
- 試験
  - Mac・VM の単体試験は 271 件合格。
  - VM の `ubuntu_nd07_wait_points.sh`：点群なし・捨てられる点群の間は初期化中、保持すると 25 秒で正常。
  - 設計検査は違反 0・未判定 5。run_checks の違反 6 件は、原本 drawio・`.DS_Store` によるもので第115便と同じ。
- 実の点群での確認は未判定。XT-32 に届かない（USB-LAN の speed 0、ARP 失敗。人が接続を確かめる）。
- 別の不具合（未修正）：gouda.sh stop で sensor supervisor が落ち、hesai_ros_driver が残って stop が終わらない。
- VM の `~/gouda_ws` は作業ツリーが変わっている（update.sh は止まる）。コミットはまだ。

**第115便: 自律走行開始で ND-07 が推定不能（init_failed）になる件（REV-143、DEC-279・280）**（作業記録 `reports/worklog/2026-10-22_bin115_ndt_init_failed.md`）。
- NDT が点群を一つも受け取らないまま ndt_align_srv を呼んでいた（No InputSource）。原因は二つ。
  - ND-07 が、A3 の起動から 1.5〜3 秒で点群を待たずに呼ぶ。
  - XT-32 の 1.66 MB の点群は、BEST_EFFORT では既定の受信バッファでほとんど届かない。pcl_ros の CropBox は 18 秒で 3 通しか出さなかった。受信バッファを 4 MB にすると、10 秒で 75 通届いた。
- 対応は承認待ち：DEC-279（Fast DDS の profile で受信バッファを大きくする）、DEC-280（NDT が点群を受け取るまで待つ）。コードと設定は変えていない。実車での自律走行は、これが決まるまで止まる。

**第114便: VM のセンサーの状態**（作業記録 `reports/worklog/2026-10-22_bin114_sensor_status.md`）。
- XT-32 は待機（standby 1）で点群が来ていなかったが、確認の途中で運転に戻り、10 Hz で届いている（切り替えたのは Claude ではない）。IMU は受信あり。GNSS は衛星 0 で測位なし。NTRIP の補正は 0 バイトで、ネットワーク RTK は使えていない。人がアンテナを外に出した後も、2 分半のあいだ衛星の信号 0（アンテナの信号が届いていない可能性）。接続を直した後（10-22 00:5x）、LiDAR は 10 Hz、IMU は受信あり、GNSS はなお信号 0。

**第113便: VM のセンサーの接続の確認と Parallels の設定の点検**（作業記録 `reports/worklog/2026-10-21_bin113_sensors_parallels.md`）。
- IMU は受信あり。GNSS はドライバ起動・測位なし。ESP32 は手動走行では開かない。XT-32 は、VM の起動のときに USB-LAN の結び付きが失敗していて未受信（付け直しは人の作業）。Claude のアプリが Mac の眠りを止めているので、閉じると 1 分で眠る見込み（DEC-104）。Parallels の設定の案は人の判断待ち。

**第112便: monitor の「発進準備」タブを実装済みの手順に合わせた**（作業記録 `reports/worklog/2026-10-21_bin112_prep_tab.md`）。
- 文面だけのタブが「未実装」のまま古かった。waypoint タブでの選択と初期位置、自律走行ボタン、その後の自動の起動の順に書き直した。未実装は GNSS による初期位置（DEC-124）だけ。Mac 258 合格。VM には未反映。

**第111便: main への取り込み（PR #14・#15）と VM の update**（作業記録 `reports/worklog/2026-10-21_bin111_main_merge_vm_update.md`）。
- 第103〜110便を PR #15 にし、人が merge した（main a86a7d0）。VM の `~/gouda_ws` は update.sh でコードが a86a7d0 になったが、setup.sh が rtklib の導入で sudo のパスワードを求めて止まり、組み立てはまだ（人が setup.sh を実行する）。

**第110便: PRM-99 を実車でも仮に 1.0 m に（REV-142、DEC-278）**（作業記録 `reports/worklog/2026-10-21_rev142_prm99_interim.md`）。
- 人の決定（原文）で、DEC-229 が決まるまで実車でも PRM-99＝1.0 m を使う。gouda_monitor.yaml に反映した。設計検査は違反 0・未判定 5（DR-11 30）。Mac 258 合格。VM（人が再開した後）で、承認値だけで隙間 0.8 m の保存の警告が出ることを確認した。

**第109便: DEC-227 案 A の Nav2 の設定と、禁止の範囲どうしの隙間の警告（REV-140・141、PRM-99）**（作業記録 `reports/worklog/2026-10-21_rev140_141_dec227_plan_a.md`）。
- 人の確認（原文）で着手。global costmap に keepout_layer（StaticLayer、inflation の前）を足し、禁止の範囲を壁と同じに膨らませる。保存のとき、禁止の範囲どうしの狭い隙間を警告し地図に示す（しきい値 PRM-99 は未確定、試験用の仮の値 1.0 m。実車では「確かめていない」と出る）。
- 試験：Mac 258 合格（10 skip）、VM 268 合格、不合格 0。VM の 5-6（全段）で、禁止の範囲を迂回して最後まで着いた（collision ahead 0 回）。まっすぐの隙間：0.7 m は手前で止まり、0.8 m はぎりぎりで着き、0.9 m 以上は問題なく通れた。曲がる場合は未測定（DEC-229）。設計検査は違反 0・未判定 5。

**第108便: DEC-227 への人の回答（転記）と DEC-229 の記録（REV-139）**（作業記録 `reports/worklog/2026-10-21_rev139_dec227_transcribed.md`）。
- 分岐セッションからの転記：案 A を採用（global で禁止の範囲を壁と同じに膨らませる）。禁止の範囲どうしの隙間の条件は、受入の条件と保存のときの警告で扱う。警告のしきい値は実測 DEC-229（仮 1.0 m、tbd）。実装は人の確認の後。設計検査は違反 0・未判定 5。

**第107便: 人が描く範囲の実装（REV-137）と、禁止の範囲の縁で RPP が止まる件（REV-138、DEC-227）**（作業記録 `reports/worklog/2026-10-21_rev137_138_drawn_areas.md`）。
- 人の確認（原文）で着手。waypoint セットの範囲（走行禁止・走行可）、keepout のマスク（広げない）、keepout の server と global・local の KeepoutFilter（override_lethal_cost true）、開始のときのマスクの確認（(a)）を実装した。
- 試験：Mac 256 合格（8 skip）、VM 264＋2 合格、不合格 0。VM の 5-6 で、マスクを確かめてから motion_hold が解け、車体は禁止の範囲に入らなかった。ただし経路が禁止の範囲の縁に沿い、車体がはみ出すので RPP が止まり、最後まで着かなかった（範囲なしでは着く）。filter は inflation の後にかかることを確認。対応の案は DEC-227（pending、推奨は案 A：global で禁止の範囲を壁と同じに膨らませる）。コードと設定は変えていない。
- 別の不具合：試験の基盤で sensor_supervisor が host_ip の AttributeError で落ちる（未修正、人の許可待ち）。設計検査は違反 0・未判定 5。

**第106便: DEC-220〜224 への人の回答（転記）と DEC-226 の記録（REV-136）**（作業記録 `reports/worklog/2026-10-21_rev136_dec220_224_transcribed.md`）。
- 分岐セッションからのメッセージで届いた回答を転記として記録：人が描く範囲の実装を始める、waypoint セットと一緒に保存、KeepoutFilter を global・local に置き override_lethal_cost は true、広げる幅は作らない、開始のときは (a) だけ確かめる。(b) は DEC-226（pending）。実装は人の確認の後。

**第105便: DEC-225（B＝5.1 m）と、作り直した地図の ~/gouda_ws への取り込み（REV-135）**（作業記録 `reports/worklog/2026-10-21_rev135_dec225_map_into_gouda_ws.md`）。
- 人の回答（原文）：B（PRM-97）＝5.1 m（DR-13 は変えない）。VM のメモリは 12 GB（人の申告、確認）。作り直した原図を承認値だけで変換し直し（rev 2、帯は 1 区間）、VM の `~/gouda_ws/gouda_data/maps/` に原図と rev 2 を入れた（ハッシュ一致）。175847 は人の指示で作り直さない。VM の再起動で `~/gouda_ws` の Gouda は止まっている。`~/gouda_ws` のコードは古い（3341602）。設計検査は違反 0・未判定 5。

**第104便: 帯の地図を走行用に、Nav2 の設定、外付けの rosbag からの地図の作り直し（REV-134、DEC-225）**（作業記録 `reports/worklog/2026-10-21_rev134_plan_c_driving_nav2.md`、記録 `research/vehicle_pc/2026-10-21_rosbag_rebuild/`）。
- 人の確認（原文）で着手。走行用の map.yaml を帯の地図に（今の分類の地図は表示用、帯が作れない原図は変換を失敗に）、地図タブに帯と点群の重ね図、帯の外の waypoint は警告つきで保存、global の obstacle_layer の combination_method 2、inflate_around_unknown（PRM-98、false、Nav2 タブで上書き）、PRM-72＝1.0 m、PRM-96＝1.0 m。PRM-97（B＝5 m）は検査ルール DR-13（旧値 5 m の流用の禁止）に機械的に当たるので値を入れず、DEC-225 で承認を求める。
- 試験：Mac 248、VM 256 合格、不合格 0。VM の Nav2 タブと 5-6 の結合試験（帯の地図）。5-6 の 1 回目に一度だけ Nav2 の goal の受け付けの時間切れで TR-07（再現せず、未解決）。外付けの rosbag 20261014_173522 から原図（/config の写しつき）と変換を作り直した。20261014_175847 は VM のメモリ不足で GLIM が止められ、作れなかった。今の分類の地図は帯の中の 51000／57931 格子を占有にしていた。設計検査は違反 0・未判定 5。

**第103便: DEC-211〜215 への人の回答（転記）と DEC-216〜224 の記録（REV-133）**（作業記録 `reports/worklog/2026-10-21_rev133_dec211_215_transcribed.md`）。
- 分岐セッション「Side chat」からのメッセージで届いた人の回答を転記として記録：帯の地図を走行に使い人が描く範囲を重ねる（DEC-211）、写しのない原図は帯を作らず外付けの rosbag から作り直す（DEC-212）、A 1.0 m・B 5 m（DEC-213）、allow_unknown は true（DEC-214 不採用）、帯の外の waypoint は警告だけ（DEC-215）、combination_method 2（DEC-216）、inflate_around_unknown false を Nav2 タブで（DEC-217）、PRM-72 を 1 m（DEC-218）。確認・承認待ちは DEC-219〜224。値の変更・実装・作り直しは人の確認の後。status.md の後半の古い記述を直した。

**第102便: DEC-208・209 の回答と monitor の「Nav2」タブ（REV-132）**（作業記録 `reports/worklog/2026-10-21_rev132_dec208_209_nav2_tab.md`）。
- 人の回答（原文）：DEC-208 は全て既定値（PRM-79〜95 を推奨の値で承認。ND-07 は実車でも設定値がそろった）、DEC-209 は承認。monitor の /config に「Nav2」タブ（recovery の回数、1〜PRM-18）を足し、次の gouda.sh start で BT に入れる（IFD-54）。
- 試験：Mac 246 合格、VM 254 合格、不合格 0。VM の試験スタックで、保存した 3 が起動し直した後の BT に入ることを確認。設計検査は違反 0・未判定 5（DR-11 32）。

**第101便: 案 C（通った帯の 2D 地図）の実装（REV-131、DEC-210）**（作業記録 `reports/worklog/2026-10-21_rev131_plan_c_corridor.md`、分析 `research/vehicle_pc/2026-10-21_swept_corridor/`）。
- 人の確認（原文）で着手。変換に帯の 2D 地図（map_swept_corridor、swept_corridor.json）を追加の成果物として足した（走行用の map.yaml は替えない：DEC-211 待ち）。PRM-96・97 は未確定（DEC-213）。/config の写しがない原図では作らない（DEC-212 待ち）。
- 試験：Mac 243 合格、VM 251 合格、不合格 0。VM の原図 2 つで分析（今の分類の地図は帯の中に占有 570・955 格子）。VM の Nav2 で帯の地図の上を最後の waypoint まで走った。軌跡は約 5 Hz で、1 m を超える間隔の多くは時間のあきだけ：試行の値 B＝1.0 m ではふつうの所も切れる（DEC-213 の材料）。設計検査は違反 0・未判定 5（DR-11 49）。

**第100便: DEC-107 への人の回答（転記）と案 C の実装の指示の記録（REV-130、DEC-210〜215）**（作業記録 `reports/worklog/2026-10-21_rev130_dec107_plan_c_transcribed.md`、提案 `proposals/swept_corridor_map_2026-10-21.md`）。
- 分岐セッション「Side chat」からのメッセージで届いた人の回答を転記として記録：DEC-107 は案 A を DEC-105 の後に再検討し、まず案 C（通った帯だけを空きにする 2D 地図）を試す。実装の指示は DEC-210（このチャットで人に確かめてから着手）。提案 §9 の 2〜6 は DEC-211〜215（pending）。設計検査は違反 0・未判定 5。

**第99便: ND-07 を案 A3 で試す構成の正本への取込みと実装（段 1〜4）、推定不能での一時停止（REV-128・129、DEC-207〜209）**（作業記録 `reports/worklog/2026-10-21_rev128_nd07_a3_implementation.md`）。
- 人の確認（原文）で DEC-203・205 に着手、DEC-207 は (a)。setup.sh に Autoware の 3 つと pcl_ros。地図の変換で 20 m 格子（pointcloud_map/）と軌跡の写し。ND-07（gouda_global_localization、lifecycle、上流の部品は子の launch）と IFD-53（EstimatorStatus）。mode_manager は ND-07 が正常になってから Nav2 を起動し、推定不能か状態の途絶で TR-07（estimator_unavailable）。新しい設定値 PRM-79〜95 は未確定（値は DEC-208）、段 5 は DEC-209。
- 試験：Mac 239 合格・不合格 0、VM 246 合格・不合格 0。VM で ND-07 が A3 の部品を起動・停止し、模擬の点群で正常になり（1 m・10 度、2.8 m・30 度）、5 m・90 度では推定不能になった。5-6 の結合試験（模擬の ND-07）で推定不能と途絶の一時停止を確認。地図の読み込みが格子の座標を整数で読む誤りを見つけて直した（REV-129）。rosbag の再生と実車は未実行。設計検査は違反 0・未判定 5（DR-11 47、DR-15 31）。

**第98便: DEC-203〜206 への人の回答（転記）の記録（REV-127、DEC-207）**（作業記録 `reports/worklog/2026-10-21_rev127_dec203_206_transcribed.md`）。
- 分岐セッションからのセッション間のメッセージで届いた人の回答を転記として記録：DEC-203 許可、DEC-204 は Nav2 の設定と BT を gouda.sh start で一度だけ作るまま、DEC-205 は版の確認なしで setup.sh に Autoware の 3 つ・試験は VM だけ、DEC-206 は解釈 3 つを確定。DEC-204 の意味（monitor のタブを作るか）は DEC-207（pending）。実装は人がこのチャットで確かめてから。設計検査は違反 0・未判定 5（変わらず）。

**第97便: 分岐セッションの E 項目の回答（転記）の記録と、ND-07（案 A3）の設計の案（REV-126、DEC-200〜206、DEC-115）**（作業記録 `reports/worklog/2026-10-21_rev126_e_items_transcribed.md`、提案 `proposals/nd07_a3_trial_design_2026-10-21.md`）。
- 人の回答（転記）：推定不能か Nav2 の失敗で一時停止し原因を区別（DEC-200）、PRM-18 は 9999999 のまま monitor で変えて次の走行から反映（DEC-201）、setup.sh に A3 のパッケージ（DEC-202）、ND-07 は案 A3 を試す（DEC-115 answered、DEC-021 は pending のまま）。
- 設計の案と実装の許可は DEC-203〜205、解釈の確認は DEC-206（pending）。事実：Nav2 の設定と BT は gouda.sh start のときだけ作る（goal の behavior_tree で走行ごとに渡す案）。setup.sh は Nav2 をすでに入れている。設計検査は違反 0・未判定 5（変わらず）。

**第96便: 引き継ぎからの再開と、main の上での検査**（作業記録 `reports/worklog/2026-10-21_bin096_resume_check.md`）。
- main（416a6d6）の写しで全検査を実行：設計検査は違反 0・未判定 5（変わらず）。入力の完全性は .DS_Store 2 つが「無い」で違反（git では無視されているのに baseline に含まれる。手元以外ではいつも違反になる）。扱いは承認事項として提示。
- 人の指示で、手元を main（416a6d6）から作ったブランチ design/records-2026-10-21 に切り替え、第94〜96便の記録を commit した（push は未実行）。

**第95便: 次のチャットへの引き継ぎ**（`reports/handover_2026-10-21_2.md`）。
- 第85〜94便の状態、守ること、人の判断待ちをまとめた。main は 416a6d6（作業ブランチは merge 済み）。手元は design/field-mapping-2026-10-14 のまま、第94・95便の記録は未 commit。

**第94便: main への取り込み（PR #11・#10）**（作業記録 `reports/worklog/2026-10-21_bin094_main_merge.md`）。
- 人が GitHub の画面から PR #11（作業ブランチ、REV-060〜125）と PR #10（README の更新手順）を main に merge した（main は 416a6d6）。main と作業ブランチの差は README.md だけ。PR #6（歩行者用信号、main と衝突）は人の判断待ち。

**第93便: 試験 test_nav2_config の修正（REV-125、DEC-199）**（作業記録 `reports/worklog/2026-10-21_rev125_test_nav2_config_fix.md`）。
- 人の許可で、test_vehicle_files_alone_do_not_build を、生成物の写しから PRM-66 を消して「組まない」を確かめる形に直し、本物の生成物で「組める」を確かめる試験を足した。合否の基準は変えていない。Mac 223 合格・不合格 0。規則を壊した写しでは不合格になることを確認。設計検査は違反 0・未判定 5。

**第92便: Nav2 の後退の速度の上限を PRM-78 に（REV-124、DEC-198 案 A）**（作業記録 `reports/worklog/2026-10-21_rev124_dec198_reverse_limit.md`）。
- 人の許可で、nav2_config が velocity_smoother の後退の上限（min_velocity の x）に PRM-78（0.472 m/s）を使うようにした。PRM-78 は gouda_motion_controller の生成物から読み、未確定なら Nav2 を組まない値に加えた。実車の値だけで組んだ設定は min_velocity [−0.472, 0, −1.0]。試験 2 件を追加（合格）。Mac 221 合格・1 不合格（既知の test_nav2_config、許可待ち）。設計検査は違反 0・未判定 5。

**第91便: intent.md 第14版、PRM-01〜03、後退の上限の検討（REV-123、DEC-195〜198）**（作業記録 `reports/worklog/2026-10-21_rev123_intent_v14_reverse_study.md`、報告 `reports/reverse_limit_study_2026-10-21.md`）。
- intent.md 第14版（100 行：車体は全長 800 mm × 全幅 600 mm × 全高 1200 mm、108 行：電動車椅子に人は乗らない）を記録した（AR-014、RQ-I087・RQ-I088、C-029）。途中の版の「全高 120 mm」は、人に確かめて 1200 mm の誤りと分かった。PRM-01 0.80 m、PRM-02 0.60 m、PRM-03 1.2 m。DEC-195 は解消。
- 後退の倒し量と速度の関係（人の説明、DEC-197）と、Nav2 の後退の上限の案 A・B（・C）の検討を報告した。今の設定（RPP は後退しない、BackUp は 0.15 m/s）では、A と B で動きは同じ。推奨は A（予防）。判断は DEC-198（pending）。設計検査は違反 0・未判定 5。

**第90便: 分岐セッションの D10・D11 の回答（転記）の反映：Nav2 の実車の値、PRM-39、地図の変換の値（REV-122、DEC-192〜195、DEC-098）**（作業記録 `reports/worklog/2026-10-21_rev122_d10_d11_transcribed.md`）。
- Nav2 の実車の値 PRM-11・17・18・66〜73 を承認値にした（footprint は足置きを外した車体、前 0.55・後 0.24・幅 0.60 m。前進 1.25 m/s。障害物は地面から 0.10〜1.35 m。recovery 9999999 回）。Nav2 の設定は実車の値だけで組めるようになった（nav2_config.missing が空）。PRM-39 は 1.25 m/s（DEC-166 の 1.111 を DEC-193 で置き換え）。地図の変換の値 PRM-33〜36・38・62〜64 を承認（DEC-098。PRM-36 は 1.35 m）。
- PRM-01・02（intent.md:100 の写し）は変えていない。intent.md の改訂案（車体の寸法、人は乗らない）は DEC-195（pending）。試験 test_nav2_config の 1 件が不合格（「本物の生成物では Nav2 を組まない」前提が崩れた。試験の基盤の問題。修正は許可待ち）。設計検査は違反 0・未判定 5（DR-11 は 49 → 30）。

**第89便: VL-02 の試験の追加（REV-121、DEC-191）**（作業記録 `reports/worklog/2026-10-21_rev121_vl02_test.md`）。
- 人の許可で、承認値で斜めに倒し切ったときの x と y の振れ幅の差が 1 mV 以内であることを確かめる試験を、Python の模型（test_vehicle_core.py）と firmware のホスト試験（test_core.cpp）に追加した。firmware と模型の処理は変えていない（DEC-186 の保留のまま）。Mac 221 合格、ホスト試験 OK 282。差を 2 mV にした写しでは両方が不合格になることを確認。設計検査は違反 0・未判定 5。

**第88便: 分岐セッションの B4〜B6 の回答（転記）の反映（REV-120、DEC-186〜190）**（作業記録 `reports/worklog/2026-10-21_rev120_b4_b5_b6_transcribed.md`）。
- B4: 斜めに倒し切ったときの 1 mV の非対称は直さずに保留し、`docs/deferred_verification.md` の VL-02 にした。B5: `--dry-run --check` の単体試験 `design/rules/test_apply_revision.py`（4 件、合格）を追加した。B6: DR-15 の 30 件を分類し（時間の値 9、偶然の一致 18、PRM の写し 1、8 項目にない値 1、走査器の誤検出 1）、許容の一覧の案（28 件）を `proposals/dr15_allowlist_proposal_2026-10-21.md` に書いた。一覧の本体には書いていない（承認待ち DEC-189）。gouda.sh の PRM-77 の写しは DEC-190 で質問。
- 第87便の「入力の照合の不一致 2 件」は誤りで、正しくは 3 件（drawio と .DS_Store 2 つ。第87便の時点でも同じ）。下の表を直した。設計検査は違反 0・未判定 5。

**第87便: 分岐セッションの A1〜A3 の回答（転記）の反映（REV-119、DEC-182〜185）**（作業記録 `reports/worklog/2026-10-21_rev119_a1_a2_a3_transcribed.md`）。
- A1: ND-08 の lifecycle・process_group・作り方を実装に合わせた（案 1）。A2: ND-10 に起動する server の名前を補い、詳細設計書の変更案（`proposals/spreadsheet_change_requests_2026-10-21.md`、M-039 の GNSS は M-040 にする案）を作った。Hokuyo を使うかは DEC-184（pending）。A3: この文書の後半（三つの状態・検査結果の件数・承認待ち・場所）を今の状態に書き直した。設計検査は違反 0・未判定 5。コードは変えていない。

**第86便: 後退の正規化、不感帯の補償と /config のタブ、事前地図作成での vehicle_bridge の configure（REV-118、DEC-180・181）**（作業記録 `reports/worklog/2026-10-21_rev118_dec180_181_motion_bridge.md`）。
- 人の許可で実装した。motion_controller は後退を PRM-78 で割る。不感帯の補償（前進・後退・旋回の最低倒し量としきい値）は、monitor の /config の新しいタブ「自律走行の出力」で入れ、保存したらすぐ使う（IFD-52）。未設定の向きは補償しない。事前地図作成の開始で vehicle_bridge を configure する（COMMAND は送らず、終了後も接続したまま）。
- 試験: Mac 220 合格、VM 228 合格。VM の結合（地図作成で configure、STATUS あり・COMMAND 0 件、補償の保存から出力まで 8 項目 PASS）も合格。設計検査は違反 0・未判定 5。実機は未試験、VL-01（ポートを開くと ESP32 がリセットされるか）は未検証。commit はしていない。

**第85便: 自律走行に向けた不足と完了の一覧（調査のみ）**（作業記録 `reports/worklog/2026-10-21_bin085_autonomy_readiness.md`、報告 `reports/autonomy_readiness_2026-10-21.md`）。
- 実車での自律走行を止めているもの: ND-07 未実装（DEC-115）、Nav2 の実車の値（PRM-11・17・18・66〜73）未確定、Nav2 で使える 2D 地図がない（DEC-098・107）。vehicle_bridge・motion_controller は工程 5-5 のソフトウェアとして実装済みで、設定値はすべて承認済み。実機は未試験。改良（DEC-169・171・172）は許可待ち。変更なし。

**第84便: 次のチャットへの引き継ぎ**（`reports/handover_2026-10-21.md`）。
- 第60〜83便の状態、守ること、人の判断待ち（実装の許可 6 件、決定待ち）、人の作業（ESP32 の書き込みなど）をまとめた。人の指示で a9554a1 に commit し origin に push（main は未 merge、人の drawio・xlsx・*.bkp は含めない）。人の申告（2026-10-21）: ESP32 に firmware を書き込み済み。

**第83便: 変更セットの試し適用（--dry-run --check）**（作業記録 `reports/worklog/2026-10-21_bin083_trial_check.md`）。
- 記録の誤りが増えた（第70〜82便で 6 件）ため、`apply_revision.py REV-xxx --dry-run --check` を追加。正本を書かずに検査し、新しい違反だけを示す（あれば終了コード 1）。過去の誤り 2 種を再現して検出を確認。以後は試し適用の後に本適用する。

**第82便: intent.md 第13版、DEC-168 の解消、PRM-10、PRM-78（REV-116・117、DEC-179）**（作業記録 `reports/worklog/2026-10-21_rev116_117_intent_v13_prm78.md`）。
- intent.md 第13版（16 行：自動復帰は上限なく 50 回ごとに理由を記録）を記録、RQ-I086。DEC-168 解消、PRM-10＝理由を記録する区切り 50。影響は G-RECOVERY-COUNT（工程 5-7）。DEC-172: PRM-78 最大後退速度 0.472 m/s（1.7 km/h）、motion_controller での使用は許可待ち。設計検査 違反 0・未判定 5。移行の照合の intent.md の違反は解消。

**第81便: 12 件の試験の修正、intent.md 第12版（REV-114・115、DEC-178）**（作業記録 `reports/worklog/2026-10-21_rev114_115_intent_v12_tests.md`）。
- 試験の修正で gouda_core 単体は Mac 208 合格・VM 216 合格（不合格 0）。intent.md 第12版（107 行、RQ-I085）を記録。rosbag のポップアップは今のまま。**その後 intent.md 16 行が人に編集された（未記録、第13版）**: 「復旧回数が50回を超える度に、理由を記録する。」。意味を確認中（DEC-168）。設計検査 違反 0・未判定 5。

**第80便: ESP32 の USB の切断回数の表示と記録（REV-112・113、DEC-177）**（作業記録 `reports/worklog/2026-10-21_rev112_113_usb_link_counts.md`）。
- 人の承認で実装。vehicle_bridge が事前地図作成・自律走行のセッションの中だけ数え（一時停止・再開で継続）、vehicle/link_status（IFD-51）に出す。monitor は上部と ESP32 の欄に常に表示（ポップアップなし）。切断の記録の理由の文を固定。VM で結合確認。事前地図作成で数えるには DEC-169 の configure の実装が要る（許可待ち）。設計検査 違反 0・未判定 5。

**第79便: vehicle_bridge の USB 再接続（REV-111、DEC-176）**（作業記録 `reports/worklog/2026-10-21_rev111_usb_replug_reconnect.md`）。
- 切断を記録してポートを閉じ、udev のイベントで同じ by-id の名前を開き直して HELLO から再開。lifecycle は変えず、自律走行は切断で一時停止しない（人の決定）。firmware は変えていない（手動は USB に依らない）。VM の単体 5 件合格、実機は未確認。設計検査 違反 0・未判定 5。

**第78便: 「後で検証する項目」の文書（VL-01）**（作業記録 `reports/worklog/2026-10-21_bin078_deferred_verification.md`）。
- 人の指示（転送）で新規 `docs/deferred_verification.md` を作り、VL-01（PC がシリアルを開くと ESP32 がリセットされるか。今のコードは DTR・RTS を設定しない、旧 bridge は False にしていた）を追加。未検証。

**第77便: DR-15 の走査の改訂（REV-110、DEC-175）、uptime_ms の確認、USB の差し直しの改善案**（作業記録 `reports/worklog/2026-10-21_rev110_dr15_scan_usb_uptime.md`）。
- DR-15 はコードだけ（文章を除く）を Python・web・firmware・シェルで走査し、時間の値も未判定にする（`tools/hardcode_scan.py`、許容の一覧 `tools/hardcode_allowlist.json` は空）。DR-15 未判定 19 件。uptime_ms は STATUS を作った時刻と確認（コードの読みのみ）。USB の差し直しの再接続は案のみ（許可待ち）。設計検査 違反 0・未判定 5。

**第76便: 書き込みを待たない方式、rosbag の非同期の停止と進捗、gouda.sh stop の進捗（REV-108・109、DEC-174）**（作業記録 `reports/worklog/2026-10-21_rev108_109_nonblocking_rosbag_stop.md`）。
- 人の許可で実装。vehicle_bridge は os.write で待たない。rosbag の停止はすぐ返し、保存の始まりと同時に monitor のポップアップで進捗、上限なし。gouda.sh stop は上限なし、PRM-77（1 s）ごとに GLIM・rosbag の保存の大きさを表示。VM で実機の rosbag と単体（既知の 12 件以外合格）、ポップアップは DEMO で確認。設計検査 違反 0・未判定 5。commit はしていない。

**第75便: DEC-173（時間の値の扱い）（REV-107）**（作業記録 `reports/worklog/2026-10-21_rev107_dec173_time_values.md`）。
- 通知の集約と STATUS の送信時刻はすでに実装済み（第73便の報告の誤りを訂正）。gouda.sh stop の上限の撤去、rosbag の停止の強制終了の廃止と進捗の表示は人の決定、実装は許可待ち。設計検査 違反 0・未判定 5。

**第74便: 転送された人の発言の記録（REV-106、DEC-170〜172）**（作業記録 `reports/worklog/2026-10-21_rev106_relay_speed_deadband.md`）。
- DEC-170: 最高速度の規則（SR-06・07）は車椅子側の速度上限で守る（人の確定、安全の前提）。DEC-171: 不感帯の補償 案 A を方針として承認（実装は許可待ち）、後退 1.7 km/h の申告。**承認待ち（新規）DEC-172**: 後退の正規化。設計検査 違反 0・未判定 5。

**第73便: DR-15 の未判定 11 件の調査（調査のみ）**（作業記録 `reports/worklog/2026-10-21_bin073_dr15_literal_audit.md`、報告 `reports/dr15_literal_audit_2026-10-21.md`）。
- 11 件はどれも PRM の写しではない（7 件は偶然・誤検出）。設定にない時間の値: vehicle_bridge のシリアル（0.2・0.05・0.5 s）、recorder の 30 s、gouda.sh の 30・10 s（PRM-37 と食い違いの可能性）など。宣言するか許容するかは人の判断待ち。変更なし。

**第72便: PRM-49 を 50 ms に（REV-105、DEC-169）、検査件数の訂正**（作業記録 `reports/worklog/2026-10-21_rev105_prm49_50ms.md`）。
- PRM-49＝50 ms。firmware 再ビルド成功、ホスト試験 OK 278。vehicle_bridge を事前地図作成モードでも起動する件は、起動の段階を人に確認中。設計検査 違反 0・**未判定 5**（DR-15 11 件が REV-103 から。第70・71便の「未判定 4」は誤り）。commit はしていない。

**第71便: A9・A10 の実施、DEC-078・163 の回答、DEC-168（REV-104）**（作業記録 `reports/worklog/2026-10-21_rev104_a9_a10_dec078_163_prm10.md`）。
- 人の許可で test_vehicle_core.py の trial ファイルの前提を直し（12→3 件の不合格）、ホスト試験に PC 途絶後の手動の試験を追加（OK 260）。DEC-078・163 answered、RQ-I020 に補足。**承認待ち（新規）DEC-168**: PRM-10 無制限が intent.md:16 と食い違う。gouda_core 単体 12 件不合格（期待値が古い 2、対角 1 mV、test_motion_core の trial 前提 9）は許可待ち。commit はしていない。

**第70便: DEC-166、車体出力の実車の設定値（REV-103）**（作業記録 `reports/worklog/2026-10-21_rev103_dec166_vehicle_values.md`）。
- 人の回答（原文は台帳）: PRM-14 0.1、09 0.35、41 0.05、16 0.2、42 0.5、15 1.5 s、61 CP2102N の by-id、39 1.111 m/s、40 0.97 rad/s。motion_controller・vehicle_bridge の設定がそろった。A9・A10・方針11 は内容の確認中。人が intent.md に 107 行目を追記（第12版の記録が必要）。設計検査 違反 0・未判定 4。commit はしていない。

**第69便: DEC-164 の回答、firmware のコメントの修正（REV-102）**（作業記録 `reports/worklog/2026-10-21_rev102_dec164_comment.md`）。
- 人の許可。main.cpp の「gain 1x」→「gain 2x (GA=0)」（動作は不変）。`pio run -e esp32dev` 成功、ホスト試験 OK 256、設計検査 違反 0・未判定 4。commit はしていない。

**第68便: DEC-161・DEC-162 の回答（REV-100・101）**（作業記録 `reports/worklog/2026-10-20_rev100_101_dec161_162_answers.md`）。
- 人の回答（原文は台帳）: DEC-162 は電源を切る順番（車体→基板）の運用で扱い、プルダウンは付けない。DEC-161 は不要。REV-100 の ND-17 の追記が DR-06 に当たり REV-101 で書き直した。全検査: 設計検査 違反 0・未判定 4。commit はしていない。

**第67便: DEC-160 の回答、実車向け firmware のビルド（REV-099）**（作業記録 `reports/worklog/2026-10-20_rev099_dec160_firmware_build.md`）。
- 人の回答（原文は台帳）: 最大 4720・最低 280・フルスケール 4720 mV。設定の検査に合格。`pio run -e esp32dev` 成功（has_config=true）、ホスト試験 OK 256。書き込みは人。test_vehicle_core.py は trial ファイルがなく 12 件不合格（許可待ち）。DEC-161・162・164 は未決。commit はしていない。

**第66便: 案 B1 の段 4、setup.sh に rtklib、apt の str2str の確認（REV-098）**（作業記録 `reports/worklog/2026-10-20_rev098_b1_step4_rtklib.md`、記録 `research/upstream_sensors/rtklib_2.4.3b34_str2str_review_2026-10-20.md`）。
- 人の許可（DEC-165）。setup.sh の apt に rtklib。apt の str2str は raw・エコー無効、URL のデコードなし、状態の形は同じ、NTRIP v1・TLS なし（認証は暗号化されずに流れる）。Point One が v1 を受け付けるかは原本未照合。
- 単体（Mac）: GNSS・NTRIP は合格。`test_vehicle_core.py` の 12 件が失敗（別のセッションの REV-095〜097 の後。DEC-160 の矛盾を含む。そのセッションが対応）。commit はしていない。人の作業: VM で `bash setup.sh`。

**第65便: ESP32 の DAC 出力と基板の配線の実測の記録（REV-097）**（作業記録 `reports/worklog/2026-10-20_rev097_esp32_dac_wiring.md`）。
- 分岐セッションの引き継ぎを記録（人の発言・実測は転記）。DAC は 2 倍の倍率で、フルスケールは USB 5V の実電圧（無負荷 4.72 V）。4800 mV は今の給電では出せない。**承認・実測待ち（新規）DEC-161〜164**（フルスケールの実測、R7 除去で EMC の入力が浮く件（安全）、RQ-I020 の補足、コメントの修正）。全検査: 設計検査 違反 0・未判定 4。commit はしていない。

**第64便: DAC の最小・最大の変更と STATUS 周期（REV-096）**（作業記録 `reports/worklog/2026-10-20_rev096_dac_range_status_period.md`）。
- 人の指示（DEC-159、原文は台帳）: 中立 2500・最大 4800・最小 200 mV、STATUS 500 ms。PRM-44・45・49 を更新・承認。最大 4800 がフルスケール 4700 を超え firmware の設定検査が不合格（DAC に書かない）。**承認待ち（新規）DEC-160**: フルスケールの値。全検査: 設計検査 違反 0・未判定 4。commit はしていない。

**第63便: DEC-077・DEC-079 の回答（REV-095）**（作業記録 `reports/worklog/2026-10-20_rev095_dec077_079_answers.md`）。
- 人の回答（原文は台帳）。PRM-43〜46＝2500／230／4700／4700 mV（旧 firmware の値、測定値ではない。Q-03 の確認は残る）、PRM-47＝半径 8 %、PRM-48＝200 ms を承認。人の申告: EMC-270 の基準電圧は未接続、ESP32 から出して GND で返す。firmware_config.yaml に入った。PRM-49（STATUS 周期）が未確定のため実車向けビルドはまだ has_config=false。PRM-46 の「x,y軸の合計値」の意味を人に確認中。
- 全検査: 設計検査 違反 0・未判定 4。移行の照合の違反は drawio（以前から）と extraction 内の .DS_Store（Finder、10-19）。commit はしていない。

**第62便: コードレビューの指摘 8 件の修正（REV-094）**（作業記録 `reports/worklog/2026-10-20_rev094_review_fixes.md`）。
- 人の許可（DEC-158）。中継の状態の追跡を起動ごとに新しく、標準エラーは例外があっても読み続ける、数値の値に引用符の案内、URL の伏せ字を最後の @ まで、秘密のファイルは 1 回だけ読む、中継を Driver の項目で扱う（key の分岐を削除）、supervisor の中継の試験（偽の str2str、VM で実行）。
- 単体: Mac 199 件合格・3 件 skip、VM 202 件合格。全検査: 設計検査 違反 0・未判定 4。commit はしていない。次: 段 4 の許可待ち。

**第61便: 自律走行に要る node と詳細設計書の照合（調査のみ）**（作業記録 `reports/worklog/2026-10-20_bin061_autonomy_node_inventory.md`）。
- 自律走行の node は正本 ND と launch で 20 余り。ND-07 は未実装（TR-05 で開始を拒否）。スプレッドシートは module 単位で node の一覧なし、不採用の Safety_gate 等が自律走行の行に残る、ND-18・ND-13・ND-19 の行なし、M-039 が二つの意味（section_executor と GNSS）で衝突。正本も ND-10 の内部 node 名の一部、Hokuyo の扱い、ND-08 の lifecycle の食い違いあり。登録は人の了承待ち。正本・コードは変えていない。検査は未実行。

**第60便: 案 B1 の段 3、中継の起動の実装（REV-093）**（作業記録 `reports/worklog/2026-10-20_rev093_b1_step3_relay.md`）。
- 人の許可（DEC-157）。supervisor が str2str を PRM-76 で見張って起動する。起動用の command（秘密）はメモリだけ、記録は伏せ字の command と状態の変化だけ。終了しても作り直さない。新しい `gouda_core/gouda_core/ntrip_relay.py`。
- 単体: Mac 194 件合格・1 件 skip、VM 195 件合格。全検査: 設計検査 違反 0・未判定 4。ROS 上の動きは未確認（段 4・6）。commit はしていない。次: 段 4 の許可待ち。

**第59便: DEC-156 の回答（REV-092）**（作業記録 `reports/worklog/2026-10-20_rev091_b1_step3_design.md` の追記）。
- 人の回答「DEC-156 を承認する。」。段 3 の設計（提案 §9、終了の扱いは案 A）が決まった。次: 段 3 の実装の許可待ち。commit はしていない。

**第58便: 案 B1 の段 3 の設計の案（REV-091）**（作業記録 `reports/worklog/2026-10-20_rev091_b1_step3_design.md`）。
- 中継（str2str）を supervisor の子プロセスにし PRM-76 で見張る。起動の時の記録が全 command をそのまま書くことを確かめ、記録用と起動用の command を分ける案に。標準エラーからは状態だけを取り、終了しても同じ同一性では作り直さない（提案 §9）。
- 承認待ち（新規）DEC-156。実装はしていない。全検査: 設計検査 違反 0・未判定 4。commit はしていない。

**第57便: Google スプレッドシートの gnss_localization_submodule の行の記入**（作業記録 `reports/worklog/2026-10-20_bin057_sheet_gnss_row.md`）。
- 人の指示「spreadsheetを更新せよ」で、内蔵ブラウザから「モジュール定義」41 行目（M-039）を記入し、CSV の書き出しで確かめた。内容は草案（独立の供給元、受信機の中で測位、NTRIP は str2str で中継、未承認の点は備考）。リポジトリの xlsx の写しは変えていない。提案の文書は第1版のまま（第2版は未作成）。検査は未実行。

**第56便: 案 B1 の段 2、gnss_config の実装（REV-090）**（作業記録 `reports/worklog/2026-10-20_rev090_b1_step2_gnss_config.md`）。
- 人の許可（DEC-155）。gnss_rtk.yaml は ntrip の節だけを読み、誤り・広い権限・旧い書式では使わない。ドライバには NTRIP の値を渡さず、有効なときだけ serial_1.port = USB2（PRM-75）。ドライバは補正なしでも起動する。
- 単体: Mac・VM とも 188 件合格・1 件 skip。全検査: 設計検査 違反 0・未判定 4。commit はしていない。VM の Gouda には入っていない。次: 段 3 の許可待ち。

**第55便: DEC-154 の回答と PRM-75・76（REV-089）**（作業記録 `reports/worklog/2026-10-20_rev089_dec154_prm75_76.md`）。
- 人の回答「DEC-154 を承認する。」。PRM-75（補正の入力の接続先 USB2）、PRM-76（中継の接続先 if02 の by-id）を承認値で足した。生成物の septentrio_gnss_driver.yaml に入った（gnss_config はまだ読まない）。
- 全検査: 設計検査 違反 0・未判定 4。単体 184 件合格。commit はしていない。次: 段 2 の実装の許可待ち。

**第54便: 案 B1 の段 2 の設計の案（REV-088）**（作業記録 `reports/worklog/2026-10-20_rev088_b1_step2_design.md`）。
- gnss_rtk.yaml は ntrip の節（5 項目）だけ、中継だけが読む。誤りのときは中継だけ止め、ドライバは補正なしで起動。新しい PRM 2 つ（受信機の接続先の名前 USB2、中継の接続先 if02 の by-id）。他は雛形のまま（提案 §8）。
- 承認待ち（新規）DEC-154。実装はしていない。全検査: 設計検査 違反 0・未判定 4。commit はしていない。

**第53便: 案 B1 の段 1、記録の伏せ字（REV-087）**（作業記録 `reports/worklog/2026-10-20_rev087_b1_step1_redaction.md`）。
- 人の許可（DEC-153）。sensor supervisor が他のプロセスの command line を記録する前に、ntrip の URL 全体と URL の user:password を伏せ字にする（device_watch.redact_command・command_lines）。
- 単体の試験 5 件を追加。Mac・VM（一時の写し）とも 184 件合格・1 件 skip。全検査: 設計検査 違反 0・未判定 4。commit はしていない。VM の Gouda には入っていない。
- 次: 段 2 の許可待ち。

**第52便: DEC-151 の回答と実装の段（REV-086）**（作業記録 `reports/worklog/2026-10-20_rev086_dec151_steps.md`）。
- 人の回答: 「DEC-151 を承認する。実装の各段はそれぞれ許可を求めること。」
- 実装を 6 段に分けた（提案 `proposals/ntrip_gga_proposal.md` §7）。段 1（記録の伏せ字）の許可待ち。実装はしていない。commit はしていない。

**第51便: DEC-139 の回答（案 B1）と秘密の扱い（REV-085）**（作業記録 `reports/worklog/2026-10-20_rev085_dec139_b1_secrets.md`）。
- 人の回答: 「B1を採用する。NRTKのパスワード、ユーザー名等はリモート、git, ログ、rosbag, 記録文書にも載せてはならない。」
- 漏れうる経路をソースで確かめた（中継の引数、supervisor の cmdline の記録、str2str の状態の出力、ドライバの params）。対策の案を提案 `proposals/ntrip_gga_proposal.md` 第3版 §5 に。
- 承認待ち（新規）: DEC-151（B1 の実装の案）、DEC-152（秘密を書かない検査ルールの案）。実装はしていない。全検査: 設計検査 違反 0・未判定 4。commit はしていない。

**第50便: DEC-139 に案 B3 を追加（REV-084）**（作業記録 `reports/worklog/2026-10-20_rev084_dec139_option_b3.md`）。
- 人の指示で、提案 `proposals/ntrip_gga_proposal.md` を第2版に（案 B3: Gouda の専用 node が NTRIP と USB2 を中継。B1 との比較、共通の注意）。DEC-139 の note に追記。
- 推奨は変えない: まず B1（str2str か mrtk relay）で RTK fix を確かめ、必要なら後で B3。実装はしていない（DEC-106）。
- 全検査: 設計検査 違反 0・未判定 4。commit はしていない。

**第49便: DualAnt の後のドライバの屋内の検査（REV-083）**（作業記録 `reports/worklog/2026-10-20_rev083_gnss_driver_indoor_check.md`、記録 `research/vehicle_pc/2026-10-20_gnss_driver_indoor_check_dualant.txt`）。
- 受信機を VM につなぎ直した後、ドライバが by-id の USB1 で起動し設定を終えた（拒否は既知の sntp だけ）。方位のオフセット 90 度（/config revision 18）。PVT・方位・観測 10 Hz。
- 屋内のため観測 0、測位・方位とも mode 0（期待どおり）。干渉・なりすましなし。受信機のポートには触れていない。
- 次: 屋外で副アンテナと方位の確認。全検査: 設計検査 違反 0・未判定 4。commit はしていない。Gouda は VM で動いている。

**第48便: 複数のセッションの番号の重なりの解消と、登録済みの証拠のファイルの修正（REV-081・082）**（作業記録 `reports/worklog/2026-10-20_rev081_082_shared_numbering.md`）。
- 人の指示「この問題を解決せよ」（DEC-150）。status.md の便を時系列に並べ直した（第45便 P6 の調査、第46便 運用の条件、第47便 ガイドとアンテナ間隔）。
- **REV・DEC・便の番号は `design/tools/reserve_ids.py` で予約してから使う**（排他的なファイルの作成。apply_revision は予約だけの REV を拒否する。試験 5 件合格）。別のセッションにも知らせた。
- AI の誤りを直した: REV-075 で登録した証拠のファイル 2 つに後から追記して SHA-256 が合わなくなっていた。元に戻し、追記を FILE-MOSAIC-MRTK-QUERY-FOLLOWUP に分けた（REV-082）。
- 全検査: 設計検査 違反 0・未判定 4。移行の検査の違反は人の drawio と .DS_Store だけ。commit はしていない。

**第47便: mosaic-go の使い方のまとめと開発のセッションへの共有、アンテナ間隔の確認（REV-080）**（作業記録 `reports/worklog/2026-10-19_p6_dual_antenna_survey.md` の追記、記録 `research/mosaic_go_g5_p6_usage_guide_2026-10-20.md`）。
- 位置・速度・方位は受信機の中で計算され、RTKLIB は NTRIP の中継（str2str）だけ、という整理を開発のセッションに送った（情報の共有）。
- 人が /config に GNSS のアンテナ位置を入れた（main (0.45, 0.17, 0.77)、aux1 (0.45, -0.17, 0.77) m、左右 0.34 m）。人の確認 DEC-149: 0.34 m が正しく、DEC-130 の 0.6 m は古い値。
- 全検査（REV-080 適用後）: 終了コード 1。設計検査 違反 0・未判定 4。不合格は人の drawio と .DS_Store の不一致だけ（以前と同じ）。commit はしていない。受信機には触れていない。

**第46便: 本番と実験の運用の条件の記録**（作業記録 `reports/worklog/2026-10-20_rev079_operation_condition.md`）。
- 分岐したセッションで人が発言した条件を原文で記録（DEC-147）: 本番はスタート位置に並んだらすぐ発進。fix を待つ時間は取れるが、八の字旋回などはできない。実験は手間をかけてよい。今の設計（較正は実験、本番は静止の初期化）と食い違わない。
- 承認待ち（新規）DEC-148: intent.md:14 への追記の案（`proposals/intent_edit_requests.md` §3）。
- 全検査: 設計検査 違反 0・未判定 4。commit はしていない。Gouda は VM で止めたまま。

**第45便: mosaic-G5 P6 のデュアルアンテナの方法の調査**（作業記録 `reports/worklog/2026-10-19_p6_dual_antenna_survey.md`、記録 `research/gnss_mosaic_g5_p6_dual_antenna_survey_2026-10-19.md`）。
- 公式のサポート記事と Hardware Manual v2.0.0（2026-05）: P6 は方位に対応するが出荷時は無効、DualAnt → Boot 保存 → reset で有効。第43〜44便の手順と同じ。ROS ドライバ・ArduPilot・PX4 は sfm を送らない。
- 条件: 前置増幅 15〜35 dB（AGC 30〜50 dB）、2 本の差 5 dB 以内、ANT_2 を空けない。屋外の確かめ方は記録 §5。受信機・VM には触れていない。検査は未実行。
- 2026-10-20 追記: 人が渡した Reference Guide v1.1.1 で照合（記録 §7）。Nominal は「普通は SingleAnt、方位が主目的の製品では DualAnt」→ P6 では単一アンテナ。原本未照合は解消。firmware の更新は不要。

**第44便: DualAnt の Boot 保存と受信機の reset**（作業記録 `reports/worklog/2026-10-19_rev075_mosaic_dual_antenna_query.md` の追記）。
- 人の許可（DEC-146）で Gouda を止め、USB2 から eccf, Current, Boot と exeResetReceiver, Hard, none を送った。reset で USB が切れ返答は記録できず。by-id は作り直された（if02 は ttyACM2 に）。
- reset の後: gfm **DualAnt**、gga MultiAntenna, Fixed。Boot 保存と reset は効いた。
- **Gouda は VM で止めたまま**。次: Gouda を起動し、屋外で副アンテナの観測と方位を確かめる。全検査: 設計検査 違反 0・未判定 4。commit はしていない。

**第43便: sfm, DualAnt を Current にだけ送った**（作業記録 `reports/worklog/2026-10-19_rev075_mosaic_dual_antenna_query.md` の追記）。
- 人の許可（DEC-145）で USB2 から送った。gfm Nominal → sfm, DualAnt 受理（$R:）→ gfm DualAnt。Boot 保存・再起動はしていない。効くのは次の reset から（マニュアル 1.0.1）。
- **注意**: ドライバ（configure_rx true）は起動のたびに eccf, Current, Boot を送るので、Gouda の再起動や USB の抜き差しでドライバが起動し直すと DualAnt が Boot に保存される。Gouda は VM で動いたまま。
- 次（人の判断）: Gouda を止めて Boot 保存と受信機の reset、屋外で副アンテナの観測と方位を確かめる。全検査: 設計検査 違反 0・未判定 4。commit はしていない。

**第42便: gnss_localization_submodule の責務と非責務（提案）**（作業記録 `reports/worklog/2026-10-19_gnss_submodule_responsibility.md`、提案 `proposals/gnss_localization_submodule_responsibility.md`）。
- drawio の新しい箱（中に MRTKLIB、入力は mosaic-go だけ、出力の線なし）とシートの空の行に対し、責務・非責務・シートの行の案を作った。承認待ち Q-A〜Q-F（位置の計算は受信機かMRTKLIBか、Global_localization の下位か、出力の座標、enu→map の発行元、方位なしの初期化、シートへの書き込み）。正本は変えていない。検査は未実行。

**第42便: DEC-144 の承認と frontend mode の値の照会**（作業記録 `reports/worklog/2026-10-19_rev075_mosaic_dual_antenna_query.md` の追記）。
- 人が DEC-144 を承認（先に値の一覧を照会して報告）。`help, setFrontendMode` は引数名 fmMode だけで値の一覧を返さず、`help, fmMode` はエラー。firmware 1.1.x の資料も見つからない。DualAnt が 1.1.1 の値かは未確認のため、設定には進まず報告した（REV-076）。
- 全検査: 設計検査 違反 0・未判定 4。移行の検査は第41便と同じ（人の drawio・.DS_Store）。commit はしていない。Gouda は VM で動いたまま。

**第41便: 副アンテナの確認（マニュアルと MRTKLIB での照会）**（作業記録 `reports/worklog/2026-10-19_rev075_mosaic_dual_antenna_query.md`、記録 `research/gnss_mosaic_g5_dual_antenna_2026-10-19.md`・`research/vehicle_pc/2026-10-19_mosaic_mrtk_query.txt`）。
- 人の確認: アンテナを入れ替えても main 側だけ受信（アンテナ・ケーブルは正常）。
- 人の許可（DEC-143）で MRTKLIB の mrtk relay から USB2 に照会だけ: 能力 Main+Aux1、許可は 2 本のアンテナと方位、方位の計算 MultiAntenna, Fixed、**frontend mode は Nominal**（マニュアル 1.0.1 の値 SingleAnt・DualAnt にない。意味は原本未照合）。型・許可は原因ではない。
- マニュアル（Hardware Manual §4.2.3.2）: 2 本で動かすには setFrontendMode DualAnt を Boot に保存して再起動する。承認待ち（新規）**DEC-144**（値の一覧の照会 → DualAnt・Boot 保存・再起動 → 屋外で確認）。
- 全検査: 設計検査 違反 0・未判定 4。移行の検査は人の drawio と macOS の .DS_Store 2 件（AI は触っていない）。commit はしていない。Gouda は VM で動いたまま。

**第40便: GNSS のドライバの最初の起動（VM）**（作業記録 `reports/worklog/2026-10-19_rev073_gnss_first_start.md`、記録 `research/vehicle_pc/2026-10-19_gnss_first_start.txt`）。
- ブランチを commit（3341602）・push、人が VM を更新。gouda.sh start でドライバが USB1（by-id）で起動し設定を終えた。受信機は `sntp, on` を拒否（ファームウェア 1.1.1）。
- 起動の後の gso: Stream1（状態、500 ms）・Stream3（PVT・方位など、100 ms）が USB1、ほかは off。USB2 の NMEA は止まった。
- 屋内で単独測位（衛星 13〜17、水平精度 約 11 m）。屋外でも単独測位（衛星 16〜21、約 6.4 m）。**方位は出ない**: 観測は主アンテナだけで、副アンテナの観測が一つもない（G-GNSS-NO-HEADING、REV-074）。Gouda は VM で動いたまま。

**第39便: 最初の起動の前の受信機の記録**（作業記録 `reports/worklog/2026-10-19_rev072_mosaic_before_first_start.md`、記録 `research/vehicle_pc/2026-10-19_mosaic_before_first_start.txt`）。
- 人の許可（DEC-142）で USB2 から照会。gso: Stream1〜3 は off、Stream4〜10・Res1〜4 は空（10/17 の Stream4 は残っていない）。getDataInOut: 全接続先が入力 auto・出力 SBF+NMEA。USB2 の NMEA では単独測位。
- 最初の CR で受信機の入力に残っていた GGA の断片が無効なコマンドになった（以前に NMEA が送り返されていた。設定は変わっていない）。
- 生の記録は位置を含むので VM にだけ置いた。commit はしていない。

**第38便: DEC-140 の回答（configure_rx true）、起動の前後の記録の道具、DEC-139 と GGA の提案**（作業記録 `reports/worklog/2026-10-19_rev070_071_dec140_query_tool_ntrip.md`）。
- PRM-74 を承認値 true に。**このブランチで Gouda を起動するとドライバが起動し、受信機の全出力を止めて Boot に保存する**（VM の ~/gouda_ws は main なので、まだ起動しない）。
- 記録の道具 `gouda_core/gouda_core/septentrio_query.py`（照会だけ、by-id、raw・エコー無効を確かめてから）。単体 180 件（Mac・VM）合格。実行は人の許可の後。
- 提案 `proposals/ntrip_gga_proposal.md`: DEC-139 の推奨を案 B1 に（ドライバが USB2 を補正の入力・GGA の出力に、RTKLIB の str2str が中継。GGA は受信機が 1 秒ごと）。
- 全検査は終了コード 1（人の drawio だけ）。commit はしていない。

**第37便: 人の指示 DEC-141（PRM-65 の承認、by-id の名前だけ、DEC-140 の材料）**（作業記録 `reports/worklog/2026-10-19_rev069_by_id_prm65_dec140_material.md`）。
- PRM-65 を承認値（serial:/dev/serial/by-id/usb-Septentrio_Septentrio_USB_Device_0100012541-if00、USB1）に。configure_rx を PRM-74（未確定、DEC-140）にし、決まるまでドライバを起動しない。
- 実装: IMU・GNSS とも /dev/serial/by-id/ の名前だけを受け付け、それ以外はドライバを起動せず理由を記録。単体 177 件（Mac・VM）合格、同時接続で番号が入れ替わっても取り違えないことを確認。
- DEC-140 の材料: `proposals/mosaic_receiver_setup_configure_rx_false.md`（USB1 の 2 つの SBF のストリーム、sga・sto、人の手順、Boot には保存しない）。ドライバは起動しておらず、受信機のポートには触っていない。
- 全検査は終了コード 1（人の drawio だけ）。commit はしていない。

**第36便: 上流 GNSS ドライバのソースの確認（人の手順 1）**（作業記録 `reports/worklog/2026-10-19_rev068_septentrio_source_review.md`、記録 `research/upstream_sensors/septentrio_gnss_driver_1.4.8/source_review_2026-10-19.md`）。
- シリアルは raw・エコー無効で開く。configure_rx true は起動のたびに受信機の全出力を止め、最後に Boot に保存する（人の資料 §5・§6 と合わない）。主アンテナの位置は補正しない（方位のオフセットだけ）。
- 承認待ち（新規）: DEC-140（configure_rx を使うか。推奨は使わない）。人の手順 2（PRM-65 を if00）は承認待ち。ドライバはまだ起動していない。
- 全検査は終了コード 1（人の drawio だけ）。commit はしていない。

**第35便: DEC-125・135・136 の回答、GNSS の較正の検証の道具、mosaic-go の VM への接続**（作業記録 `reports/worklog/2026-10-19_rev067_gnss_calibration_tool_mosaic.md`）。
- 人の回答: DEC-136 承知、DEC-135 一旦承認（人の実験走行の実データで検証、だめなら不採用）、DEC-125 しばらく VM で実機試験・mosaic-go は USB・補正は NTRIP（Point One TrueRTK）。
- 実装: 較正の検証の道具 `gouda_core/gouda_core/gnss_calibration.py`（地図への組み込みはしない）、地図作成の時の /config の写しを原図の横に。単体（Mac 173 件・VM 全件）と VM の記録の試験は合格。
- mosaic-go は VM で if00（USB1）・if02（USB2、NMEA）のシリアルとして見え、USB イーサネットはない。PRM-65 の候補は if00。DEC-139 の案 A は今の接続ではできず、推奨の見直しが要る。
- **注意**: AI がポートを raw・エコー無効にせずに読んだため、NMEA が受信機へ送り返された可能性がある（人の資料 §2）。
- 承認待ち（新規）: DEC-138（VM の起動にも Fast DDS の設定）、DEC-139（NTRIP の受け方）。VM の ~/gouda_ws は main のまま。
- 全検査は終了コード 1（人の drawio だけ）。commit はしていない。

**第34便: GNSS の承認事項の回答の記録と、ソフトウェアでの較正の再検討**（作業記録 `reports/worklog/2026-10-18_rev065_gnss_answers_calibration.md`）。
- 人の回答: DEC-131 承認、DEC-132 は調査結果を添えてソフトウェアの較正の再検討、DEC-133 条件付き承認（条件は DEC-137 の回答で記録: REV-066、分岐したセッション。人の操作で初期化を始める、失敗は止めて表示、未収束でも警告だけ、人の指定を残す、静止の判定と値は実機検証の後、対応のある地図だけ、PC 再起動後も同じ、方式によらない契約）、DEC-128 は許可の取消（不採用）、DEC-134 保留（過剰な安全策の可能性）。
- 再検討（合成のデータ。`research/vehicle_pc/2026-10-18_gnss_calib_feasibility/`）: 較正の走行ならレバーアーム 1〜2 mm・取付 Yaw 0.02 度・遅延 5 ms の誤差で同時に推定できる。ant_z は平地で決まらない。直線だけでは遅延を誤り、標準偏差でも見抜けない。方位の定義の取り違えは残差で分かる。
- 提案 `proposals/gnss_initial_pose_design.md` 第3版 §11。承認待ち DEC-135（ソフトウェアの較正、DEC-127・132 の置き換え）、DEC-136（次の実機試験に較正の動き）。実装はしていない。
- 全検査は終了コード 1（人の drawio だけ）。commit はしていない。

**第33便: DEC-126 の実装（地図作成の間の GNSS の記録）と、人が貼った GNSS の仕様との照合**（作業記録 `reports/worklog/2026-10-18_rev063_gnss_mapping_record.md`）。
- 人の回答: 「DEC-126は許可。」同じメッセージに GNSS 活用の実装仕様の文書（扱いの指示なし。DEC-130、写し `research/gnss_reference_spec_2026-10-18.md`）。
- 実装: 地図作成の間、GNSS（IFD-47〜50。方位の共分散を IFD-50 として追加）を gnss.jsonl に全項目のまま記録し、原図の横に置いて source_manifest.json に SHA-256 と行数を書く。Mac・VM の単体 168 件 OK。VM の試験スタックで地図作成の開始・終了の記録と原図への登録が合格（REV-064、FILE-GNSS-MAPPING-RECORD-VM-TEST）。受信機での実機の記録は未実行。
- 提案 `proposals/gnss_initial_pose_design.md` を第2版に（仕様との照合 §9、上流 README の確認 §10）。新しい承認待ち DEC-131〜134。DEC-128 は取り下げを推奨（代わり DEC-133）。
- 全検査は終了コード 1（人の drawio だけ）。commit はしていない。

**第32便: 工程 5-6 の実装（人の許可 DEC-120〜124）と VM の試験**（作業記録 `reports/worklog/2026-10-17_rev061_062_stage56_implementation.md`、記録 `research/vehicle_pc/2026-10-17_stage56_vm_test.txt`）。
- 人の回答: 「DEC-120〜124 をすべて許可する」。
- 実装: GNSS の取込み（ND-19、supervisor が起動、monitor に表示）、静的 TF（ND-13、/config に GNSS のアンテナ）、Nav2（RPP・NavFn・velocity_smoother・SpeedFilter、collision_monitor なし、自律走行の間だけ active）、mode_manager の TR-05・06・07・08・10・11・12、ND-08（GLIM の odometry だけ＋中継）、ND-11 の TwistStamped、monitor の「自律走行の準備」、setup.sh に Nav2 と GNSS のドライバ。
- 実車では: ND-07 がないため自律走行の開始は拒否。Nav2 は未確定の値（PRM-11・17・18・66〜73）のため起動しない。GNSS は接続先（PRM-65）が未確定のため起動しない（DEC-125）。
- VM の試験（loopback_sim が ND-07・08 の代わり、ESP32 は模擬）: 開始の拒否 2 件、開始 → 適用中で hold の解除 → 最後の waypoint で一時停止（TR-08）、終了・一時停止・再開・走行中の終了。不具合 2 件を直した（SpeedFilter の topic の名前空間、静的 TF の置き換え）。再現しない不具合 1 件（最初の goal の失敗: G-NAV2-FIRST-GOAL）。単体 166 件 OK（Mac・VM）、5-5 と前回の試験の再実行も合格。
- 自律判断で TF の木を直した（base_link→base_footprint。odom→base_link と合わせて base_link の親を一つに）。人の確認を求める。
- 提案: GNSS による初期位置の詳細（`proposals/gnss_initial_pose_design.md`）。承認待ち DEC-126〜129。実測・確認待ち DEC-125。
- 全検査は終了コード 1（原因は人の drawio だけ。設計整合性は違反 0、DR-11 の未判定は 67 件に）。commit はしていない。

**第31便: DEC-116 の実装（試験スタックの Fast DDS の設定）と、工程 5-6 の Global_localization・Navigation の検討（提案）**（作業記録 `reports/worklog/2026-10-17_rev060_stage56_study_dec116.md`、提案 `proposals/stage56_navigation_localization_plan.md`）。
- 人の回答（DEC-116）: 許可。`gouda_core/test/stack.sh` だけに `gouda_core/test/fastdds_test_stack.xml` を入れた（gouda.sh・x86 機は変えていない）。VM で前回の試験が同じ結果、約 2 MB の点群の配送が 70・86/200 → 178・182/200（FILE-DEC116-FASTDDS）。
- 人の指示（DEC-119）: Global_localization または Navigation のノードの実装を検討して報告。実装なし（DEC-106）。
- 推奨: Navigation（Nav2 の構成と mode_manager の client、TR-05）を先に作り、VM で nav2_loopback_sim を使って車体なしで試験。GNSS の取込み（受信・記録・表示）は次の実機試験の前に。ND-08（GLIM の odometry だけ）は方式に依存しない。ND-07 は DEC-115 と GNSS の初期位置の設計の後。
- 分かったこと: setup.sh は Nav2 を入れない（x86 機の Nav2 の有無は未確認。「実車PC の Nav2 1.3.13」の記録は VM のもの）。ND-13（静的 TF）は未実装。septentrio_gnss_driver は apt に Jazzy 1.4.8。
- 承認待ち（新規）: DEC-120（順序）、DEC-121（Nav2 の導入）、DEC-122（Nav2 の構成の選択、ND-09・ND-13 の直し）、DEC-123（GNSS の取込み、ND-08）、DEC-124（GNSS による初期位置の方針）。
- 全検査は終了コード 1（原因は人の drawio だけ。設計整合性は違反 0）。commit はしていない。

**第30便: recorder の rosbag の再開と GLIM の異常終了の検出を修正（実装。人の許可 DEC-117）、スリープの抑止の計画 第2版、intent 第11版**（作業記録 `reports/worklog/2026-10-17_rev058_059_recorder_glim_fix.md`）。
- 人の連絡（DEC-117）: Septentrio mosaic-go G5 P6（デュアルアンテナ、ネットワーク RTK）を搭載。DEC-115 は保留。最新版を x86 に反映し、二重起動の防止は正常。
- recorder（G-REC-ROSBAG-RESTART）: 開始ごとに `rosbag/bag_NN` に書く。子プロセスの予期しない終了を失敗として record/status・session.json・ログに残し、monitor がポップアップで示す。
- GLIM（G-GLIM-EXIT）: 地図作成中の GLIM の予期しない終了を DecisionEvent glim_exited（TR-14 の検出と表示だけ）で記録し、monitor がポップアップで示す。モードは保ち、再起動しない。
- 試験: Mac の単体 134 件 OK・1 件 skip。VM の試験スタックで rosbag の再開・強制終了、GLIM の強制終了・通常終了が合格（FILE-RECORDER-GLIM-FIX-VM-TEST）。x86 機は未確認（反映は人）。
- スリープの抑止（DEC-104）: 計画を第2版にした（電池での自動サスペンド、抑止の効く範囲、x86 機での確かめ方）。推奨は案 A のまま。
- intent 第11版（DEC-118、人の編集）: 体験 9 の初期位置は GNSS で取得し人が確認する。人が指定する前提の設計への影響を G-INIT-POSE-GNSS（未解決）に一覧した。設計は変えていない。
- 全検査は終了コード 1（原因は人が編集中の drawio だけ。設計整合性は違反 0）。commit はしていない。

**第29便: 自己位置推定の方式の検証（案 A と案 A3）**（作業記録 `reports/worklog/2026-10-17_rev056_057_localization_verification.md`、記録 `research/vehicle_pc/2026-10-17_localization_eval/`）。実装なし（DEC-106）。
- 人の回答（DEC-114）: A と A3 を重点的に検証、VM の使用を許可、合格基準は AI の案（95 % 点 0.3 m 以内、発散なし、0.5 m 超で不良）、次の実機試験も同じ場所を 2 回。
- 検証（VM、同じ走行の地図で楽観的）:
  - 走行全体の誤差の 95 % 点: A 0.124 m、A3 0.209 m（どちらも基準内）。
  - 初期姿勢が 5 m・90 度ずれると、A は誤った姿勢を「正常」として出し続けた（524 回中 510 回）。A3 は Monte Carlo の初期姿勢の探索ですぐ戻った。A3 は走行全体で 0.5 m 超を 1 回見逃した。
  - 処理は A3 の方が軽い（33 ms 対 55 ms、メモリ 205 MB 対 1.37 GB）。
- 承認待ち:
  - DEC-115: 第一候補を A3 に変える（最終は次の実機試験のデータで別の走行の地図での評価の後）。あわせて 0.5 m 超の見逃しの対策と、次の実機試験の段取り。
  - DEC-116: VM の試験の環境に Fast DDS の共有メモリの設定（G-DDS の対策）。
- G-DDS の原因を裏付けた: VM の中で約 2 MB の点群が DDS で落ちる。共有メモリの区画を大きくすると等倍でも 200/200 届いた。
- 別の走行の地図での評価は、今のデータに重なる走行がなくできない（173522 と 175857 は別の場所、181044 は rosbag なし）。

**第28便: 自己位置推定の方式の選定（提案）**（作業記録 `reports/worklog/2026-10-17_rev051_localization_selection.md`、提案 `proposals/localization_selection.md`）。
- 人の指示（DEC-109、原文）: map_creator の改良を一旦置き、自己位置推定の方式の選定に進む。DEC-107・DEC-098 は保留（未回答のまま）。
- 地面の推定の要否: 3D 照合方式なら、自己位置推定には要らない。Nav2 の 2D 地図は経路の高さ基準の帯で足りる見込み。2D 方式なら地図全体で要る。
- 推奨: 案 A（3D 照合）。odom は GLIM を odometry だけで、map→odom は lidar_localization_ros2（NDT_OMP）。比較に案 B（Nav2 AMCL）。
- 人の指示（DEC-110）で Cartographer を案 C として検討した。自身の地図でしか自己位置推定できず（地図作成も置き換え）、上流の保守は終了、品質の出力なし、点の時刻の形式が合わない。第一候補にしない（評価に加えるかは人の判断）。
- 人の指示（DEC-111）で LeGO-LOAM と Autoware の ndt_matching を検討した。どちらも ROS 1 だけのため外した。後継の Autoware Core の NDT（ndt_scan_matcher ＋ ekf_localizer）を案 A3 として評価に加えることを推奨（品質の出力が最も豊富。中継の node が二つ要り、依存が重い）。
- 人の回答（DEC-112）: KISS-ICP は以前の評価試験で目標性能を出せなかったため外す。案 A・A3・B のみを検討。rosbag は VM に移さない。提案を第2版に書き直した（3 案に共通の GLIM の odometry の設計、要求との照合の表、VM を使わない評価の計画）。推奨は第一候補 A、A3・B と比べて決める。
- **intent.md 第10版**（人の編集、機械比較で検出。DEC-113、AR-010）: 82 行に「OSSとして公開されており使用実績の豊富なものについては、Nav2に追加しても良い。」が加わった（RQ-I057 → RQ-I083、照合 C-026）。提案の承認事項 2 を、案 A・A3 がこれに当たるかの判断に変えた。
- 承認待ち（提案 §9 の 6 点）: 第一候補 A で A3・B と比べて決める進め方、intent の「Nav2 に機能を持たせ」の読み、実際のパッケージを動かす評価の場所（rosbag は VM に移さない）、合格の基準、同じ経路の 2 回の走行、実装時に要る独自の小さな node の承認の扱い。実装なし（DEC-106）。
- 全検査は終了コード 1。原因は、人が編集中の移行の原資料 `design/docs/SystemArchitecture.drawio` の SHA の不一致だけ（3 件の不合格がすべてこれ。設計整合性は違反 0）。drawio の扱いは人の判断。

**第27便: 夕方の x86 機の原図 3 件・rosbag 2 本の解析**（作業記録 `reports/worklog/2026-10-14_evening_maps_rosbag_analysis.md`、出力 `research/vehicle_pc/2026-10-14_evening_maps_rosbag.txt`）。実装・設定・正本の変更なし（DEC-106）。
- 原図の判定:
  - 173522・175857 は同じ場所の高さが一致（差の中央値 0.04 m）。175857 は出発点から 0.35 m で終了。
  - 地図全体が出発時の向きの左へ 2〜4 度傾く（未判定）。181044 は片道で rosbag なし。
- 地図の傾き（G-MAP-TILT）: rosbag の IMU の重力と LiDAR の地面から、IMU が LiDAR に対して約 2 度、左側が上がっている（走行中の平均からの参考値）。GLIM の T_lidar_imu は回転なし。地図の傾きの向きと合う。オフラインの GLIM での確認は VM 待ち。値の設定は人（RQ-I081）、DEC-105 の実測は残る。
- LiDAR の途切れ（G-LIDAR-DROPOUT）が夕方に 3 回再発（4.2・3.2・3.1 s、パケット全欠損）。リンク断かは x86 機のカーネルのログ待ち。
- recorder の不具合の疑い（実装）: 同じセッションで rosbag を再開すると同じ出力先に書こうとして黙って失敗し、181044 の rosbag が失われた（VM での再現は未実行）。
- 175310 の失敗: GLIM が gtsam の例外で異常終了。間隔 1 ms 未満の LiDAR の frame があり、二重起動に似る（x86 機は二重起動の防止の前の build）。mode_manager は異常終了に気づかなかった（TR-14 は未実装）。
- DEC-107 の根拠の数値（屋外の山 47 %、下の外れた点 0.6 %）は補正前の odometry で求めていた。取り直しが要る。
- 修正方針の候補（承認事項。判断台帳には未登録）: (1) IMU と LiDAR の回転、(2) LAN のリンク断、(3) recorder、(4) GLIM の異常終了の検出・表示、(5) 二重起動の防止を x86 機へ、(6) 地面の推定。
- 人への依頼: x86 機のログ（カーネル・logind・~/.ros/log）、3 件の経路、VM の起動と rosbag の写し。

前便（第26便）までの要約は以下。

**実機の地図作成の試験（廊下、二往復）**（作業記録 `reports/worklog/2026-10-14_rev045_field_mapping_judgement.md`）。
- 1 回目: 不合格。Gouda が 2 つ同時に動いていた（G-DUP-START）。
- 2 回目: 原図（3D）は往復で整合（区間の長さの差 2 m 以内、壁の差 0.15 m 以内）。
  - 廊下の向きに 4.15 度の一様な傾きがある（廊下が水平かを人に確認）。
  - 床より下の反射と推定される点（12 %）で地面の推定が下がり、2D 変換は不合格（G-FLOOR-REFLECTION。地面の推定の修正が次の作業）。
  - ゴミ箱は未判定（位置を人に確認）。
  - GLIM の処理周期 4.37 Hz。rosbag は未記録。
- x86 機の地図作成 2 件（REV-047）。
  - 廊下: 原図は整合。GLIM は 10.00 Hz を欠けなく処理し、出発点から 0.27 m で終了、壁が一致。
  - 廊下の不合格点: 4.40 度の傾きがあり、床の反射で 2D 変換は不合格。
  - 屋外: LiDAR の frame が 3 回、約 3 s 途切れ（G-LIDAR-DROPOUT）、約 9 m ずれた。同じ場所の高さが 1.8 m 違い、原図は不合格。
  - VM での処理周期の低さは VM に固有と見られる（G-DDS）。
- 人の回答（DEC-103）: 廊下は水平（傾きは誤差: G-MAP-TILT）、屋外は出発点に戻った（終点のずれは誤差）、使用環境は屋外、二重起動の防止を許可。
- 二重起動の防止を実装（gouda.sh の拒否、supervisor の device_in_use）。VM で試験合格。センサーありの試験は未実行。
- LiDAR の途切れ: 3 回とも有線 LAN（enp2s0）のリンク断と同じ秒。サスペンドはなし。蓋の開閉は journal で確認待ち。
- 承認待ち: DEC-104（スリープの抑止。計画 `design/proposals/sleep_inhibit_plan.md`）、DEC-107（地面の推定の修正。人の方針 DEC-108 に基づく設計 `design/proposals/ground_estimation_design.md`。承認は 4 点を個別に）。人の指示（DEC-106）により、個別の許可まで実装しない。
- 実測待ち: DEC-105（IMU と LiDAR の間の傾き。水平な床で静止して Record）。
- 人の作業: 蓋の開閉の時刻の確認（journal）、次の試験で Record を押す。

前便（第25便）: **設計のブランチを人が main に merge した**（PR #8）。README を現行の実装に合わせて書き換え、PC のセットアップと更新のスクリプトを用意した（ブランチ `docs/pc-setup-2026-10-14`。main への merge は人）。
- 初回: `bash setup.sh`（何度実行してもよい。足りないときだけ sudo）。更新: `bash gouda.sh stop` → `bash update.sh`（main へ fast-forward してから setup.sh）→ `bash gouda.sh start`。
- ドライバの commit は `third_party/drivers.repos` の 1 か所。ドライバは改変しない（DEC-075）。
- VM の別のワークスペースで setup.sh・update.sh を確認。何も入っていない PC での apt・PPA・接続の追加の部分は未試験。
- 承認待ち: DEC-101（旧実装のファイルの扱い）。作業記録 `reports/worklog/2026-10-14_rev044_readme_setup_update.md`。

前便（第24便）: **gouda_monitor に「地図」タブを新設**（intent.md 第9版 106 行目、DEC-092）。
- 原図を選び、変換設定を入力して再変換できる。変換のたびに新しい rev ができる。
- 人の回答: 高さの基準は地面（DEC-093）、今は GLIM を変えず移動して作った原図で密度を測る（DEC-096 C）、段差・坂の地図は確認用（DEC-097 A、条件付き承認。条件は確認中）。
- 変換を、点群から推定した地面からの高さで判定する方式にした（PRM-62〜64 を新設）。
- 1 つの rev として次を作る（DEC-095）。地図タブで切り替えて見られる。
  - 2D 占有格子（Nav2）
  - 3D 点群地図（PCD）
  - 表示用の傾き・段差・高さの図（走行には使わない）
- 確認: VM の試験スタック（実機の原図の写し）と DEMO。
- 暫定の推奨値は承認待ち（DEC-098）。実車の設定では既定値の欄は空で、値を入れれば再変換できる。
- これまでの原図はすべて静止して作られていた。地面の見え方（DEC-099）と点の密度・GLIM の処理周期（DEC-100）は、移動しての地図作成の実機試験（TS-34、手順 `docs/map_conversion.md` §5、解析 `map_inspect`）で測る。
- 作業記録 `reports/worklog/2026-10-14_rev039_040_map_tab.md`。

前便（第23便）: 起動経路を一つにした（`bash gouda.sh start` だけ、環境変数なし。DEC-090・DEC-091）。IMU 100 Hz、LiDAR 600 rpm を確定（REV-036〜038）。

前便（第22便）: センサーの受信表示と再接続時のドライバ作り直し（REV-034・035）。

前便（第21便）: GLIM の開始を VM で検証し、gouda.sh・mode_manager などの不具合を修正（REV-032・033）。

前便（第20便）: IMU デバイス名と XT-32 の時刻（PC 受信時刻）を確定、センサドライバの起動を実装（REV-031）。

前便（第19便）: XT-32 の IP・宛先・ポートと IMU の名前を宣言（REV-030）。

前便（第18便）: **工程5-5（車体出力）を実装し、Ubuntu の ROS 2 Jazzy 上で stub 試験合格（PC 側と firmware 中核の卓上 stub。ESP32 実機・車体なし）**。作業記録 `reports/worklog/2026-10-10_rev027_stage5-5.md`。次は DEC-076 の順序どおり、5-3 のセンサー有り試験 → 5-5 の実車試験（いずれも人のハード接続・判断が必要。着手前にセンサー・車体・ESP32 の接続状況を人に確認する）。実車向け firmware の書き込みは DEC-077（DAC 電圧の初期値）の回答待ち。

工程5-5 の内容: IFD-40 の独自型 `gouda_interfaces/msg/MotionHold` を確定、PC–ESP32 プロトコル v4 を設計（`docs/esp32_protocol_v4.md`、G-FIRMWARE）、ND-11 `gouda_motion_controller`・ND-12 `vehicle_bridge`（lifecycle node）、ND-17 新 firmware `firmware/gouda_esp32_v4`（PlatformIO、Bluepad32、MCP4922、NVS 設定）、mode_manager の `control/motion_hold` 発行、monitor の `/esp32/status` 表示。設定は generated/params から読み、未確定値は trial ファイル（stub 専用）。完了条件 (a) 手動優先 (b) 入力途絶時の中立化 (c) 一時停止中の中立出力 は、firmware 中核のホスト試験と PC 側の stub 試験で確認（実機・実車では未確認）。

前便まで: 工程5-1〜5-4 はソフト試験合格（5-3・5-4 はセンサーなし・合成データの範囲）。ゲート3は条件付き承認（DEC-064・065）。intent.md は第7版（`f69dd98b…`）。GLIM 1.2.2-0noble（DEC-062）。試験環境は Parallels の Ubuntu 24.04（`ssh -o BatchMode=yes VM`、`~/gouda_ws`。DEC-067）。firmware のビルド環境は Mac の PlatformIO（`~/.platformio/penv/bin/pio`）。

## 三つの状態（CLAUDE.md 1.4）＋報告用の三区分（DEC-057）

第87便（REV-119、2026-10-21）で書き直した（DEC-185、人の許可の転記）。件数は `design/reports/design_check.txt` の要約行と、各便の作業記録から取った。

- **移行が正確**: 違反。入力の照合（`reports/input_integrity.json`、76 件）のうち不一致は 3 件。人が編集中の `design/docs/SystemArchitecture.drawio` と、Finder が作る `design/docs/extraction_20261008_01a11af4/.DS_Store`・`raw_xlsx/.DS_Store`（第87便で 2 件と書いたのは誤り）。ほかの原資料・抽出結果・baseline は一致する。intent.md は第16版（AR-016、第137便）で、記録済みの版として検証している。drawio を新版として記録するか、変更を戻すかは人の判断。
- **設計検査に合格**: 未判定。17 ルールのうち合格 12・違反 0・未判定 5。未判定の内訳は、DR-04 が 5 件、DR-05 が 2 件、DR-10 が 2 件（版の照合）、DR-11 が 30 件（未確定の値）、DR-15 が 30 件（コードの中の数値。偶然の一致を含む、`reports/dr15_literal_audit_2026-10-21.md`）。違反 0 件は、未判定の解消や実車への適合の証明ではない。
- **ソフト試験**:
  - 工程 5-1〜5-5 は合格（stub・Ubuntu・VM。ESP32 の実機・ゲームパッド・車体なし）。
  - 工程 5-6 は一部だけ（2026-10-17、VM。ND-07・08 は loopback_sim で代用。FILE-STAGE56-VM-TEST）。
  - 第86便で TS-40（後退の正規化と不感帯の補償）を VM で確認した（単体と結合）。
  - 工程 5-7・5-8 は未実行。
- **実車検証済み／実車投入可能**: 人の判断待ち。判断の材料は次のとおり。
  - 実車試験は未実施。
  - ESP32 の firmware（設定値 PRM-43〜49 はすべて承認済み）は人が書き込み済み（人の申告、2026-10-21）。卓上の TS-17〜19・VL-01、DEC-050 の実機照合は未実施。
  - ND-07（案 A3）は実装済みで設定値も承認済み（第99・102便）。VM では模擬の点群で正常になったが、rosbag の再生と実車では未確認。Nav2 で使う 2D 地図は帯の地図に切り替えた（第104便。B＝5.1 m は DEC-225 で承認、第105便）。人が描く範囲は実装した（第107便）。禁止の範囲は global で膨らみ、VM では迂回して着く（第109便、DEC-227 案 A）。外付けの rosbag から原図と変換を作り直した（VM の `~/gouda_rebuild_2026-10-21/`）。

## 検査結果の件数

| 検査 | 合格 | 違反 | 未判定 | 時点・出所 |
|---|---|---|---|---|
| 入力の完全性（原資料・抽出・baseline・intent） | 73（一致 72、intent の新版 1） | 3（drawio、.DS_Store 2 つ） | 0 | REV-142 の後、`reports/input_integrity.json` |
| 設計整合性（17 ルール） | 12 | 0 | 5（DR-04 5、DR-05 2、DR-10 3、DR-11 30、DR-15 34） | REV-142 の後、`reports/design_check.txt` の要約行 |
| 検査器の試験（`design/rules`） | 82 | 1（実モデルの移行の照合。上の drawio と .DS_Store と同じ原因） | 0 | 第88便（`test_apply_revision.py` 4 件を追加）、`reports/migration_tests.txt` |
| gouda_core の単体試験 | Mac 258（10 skip）、VM 268 | 0 | 0 | 第109便（作業ツリー、3b4fb53 の上の未 commit の変更）。VM は `~/gouda_rev128_ws` |
| firmware 中核のホスト試験（g++） | OK 282 | 0 | 0（実機は未実行） | 第89便（VL-02 の 4 チェックを追加） |
| firmware のビルド（esp32dev） | 成功 | 0 | 0 | 第67・72便。書き込みは人（2026-10-21、申告） |
| 判断台帳 | 227 件（answered 150、recorded 56） | — | pending 21（下の一覧） | REV-142 の後 |

`run_checks.py` の終了コードは 1。原因は、上の入力の完全性の 3 件だけ。

## 承認待ち・実測待ち・人の作業・提案

判断台帳の pending（2026-10-22 第132便の時点で 46 件。下の一覧は REV-142 の時点の 21 件で、その後の分は各便の要約を見る）:

- MID-360（第235便）：承認 DEC-476〜479（REV-260 は適用済み、DEC は pending）、G3（地面分割を製品に入れるか、#85）、台帳の T08-5（提案）、計画 88 行の起動の方法、#87、#88。人の作業：Dell での `bash setup.sh`（A2）、REV-242 のコードのコミットと Dell への反映。
- 本番の方針（第132便）：DEC-305〜313（承認）、DEC-314（実測）。DEC-305 が決まるまで DEC-306〜311 の実装は止まる。
- KUAMS の工夫の取り入れ（第150便）：承認 DEC-365〜367・370・371・373、確認 DEC-368・369・372・380、実測 DEC-374〜379。
- intent.md 第15版の確認（第133便）：DEC-316。
- 許可待ち（第133便）：RQ-I074 を superseded にする（既存の移行の違反 1 件の解消）。試験の見本の差し替えは第135便で済んだ。

- 方式・照合: DEC-021（Q-02 自己位置推定の方式）、DEC-022（Q-03 車両通信と制御の校正）、DEC-024（Q-09 Bluetooth 切断時の P 状態）、DEC-050（配線・firmware・操作結果の実機照合）。
- 自己位置・GNSS: DEC-127（GNSS と地図の対応）、DEC-129（再起動後の初期位置の画面）、DEC-134（発散の監視と再初期化）、DEC-148（intent.md への運用の条件の追記）、DEC-152（NTRIP の検査ルール）。
- 地図: DEC-219（Nav2 タブに置く設定の範囲）、DEC-226（人が描く範囲の開始のときの (b) の確認。第106便で登録）、実測 DEC-229（禁止の範囲どうしの隙間の警告のしきい値 PRM-99。第108便で登録、VM のまっすぐの場合は第109便で測定）、実測 DEC-099（地面が映るか）・DEC-100（点の密度と GLIM の周期）・DEC-105（IMU と LiDAR の傾き）。
- 運用・環境: DEC-101（旧実装のファイルの扱い）、DEC-104（スリープの抑止）、DEC-138（VM の Fast DDS の設定）。
- 構成: DEC-184（Hokuyo を今年使うか。第87便で登録）。
- 検査: DEC-189（DR-15 の許容の一覧の案 28 件と、走査器の修正）、DEC-190（gouda.sh の PRM-77 の写しの扱い）。第88便で登録。

実装の許可待ち（`reports/handover_2026-10-21.md` §5 のうち残るもの）:

- sensor_supervisor の host_ip の AttributeError の修正（第107便で発見、試験の基盤で落ちる）。
- 以前からのもの：なし（1 mV の非対称は DEC-186 で直さずに保留し、VL-02 の試験は第89便で追加。DR-15 は DEC-189、`--dry-run --check` の試験は第88便で済み）。

決定待ち（台帳の外）:

- G-RECOVERY-COUNT（復旧できないときの扱い。工程 5-7 の設計のとき。最初の自律走行の後：DEC-206 の (3)）。

人の作業:

- 卓上の TS-17〜19、VL-01（ポートを開くと ESP32 がリセットされるか）、DEC-050。
- 不感帯の補償の最低倒し量・しきい値の実測と、monitor の /config「自律走行の出力」タブへの入力（第86便）。
- 詳細設計書（スプレッドシート）の修正（`proposals/spreadsheet_change_requests_2026-10-21.md`、DEC-183）。
- VM の `~/gouda_ws` と x86 機への反映（main を update.sh で取り込む。第97〜101便は main に入った：PR #13。第102便は PR #14）。

提案（承認済みの仕様ではない）: `proposals/` の各ファイル（最新は `dr15_allowlist_proposal_2026-10-21.md`、`spreadsheet_change_requests_2026-10-21.md`）。

## 原本未照合

- つくばチャレンジの規則（一時停止・3 分の滞留が失格、衝突は失格でない）は、人の発言（DEC-304）だけによる。規則の原文は読んでいない（第132便）。
  - 第150便の注：その後、`docs/regulations_2026.md` の本文は原本照合済になっている。この行の記述は古い可能性がある（DEC-381）。照合の範囲は同じファイルの冒頭を見る。
- 実車 PC の Nav2 はパッケージ版（1.3.13）で照合した。バイナリの中の IDL は直接読んでいない。
- 第235便：MID-360 の 1 枚の点数（データシート）と XT-32 の雑音・データシートは、地面分割の調査と比較（`research/ground_segmentation_2026-11-07/`）で原本未照合。比較の値の多くは比較用の仮定。
- 実機の ESP32 の配線と、書き込まれた firmware（DEC-050 は未実施。どのビルドを書いたかは未確認）。
- 詳細設計書は、2026-10-21 に Google スプレッドシートの「モジュール定義」「使用モード定義」を読んだ（gviz の CSV）。それ以外のシートは今回読んでいない。リポジトリの xlsx の写しは最新ではない（人の指摘）。

## 次の作業

- 人の指示を待つ。候補は上の承認待ち・決定待ち。
- 人の確認待ち：DEC-220〜224 の転記の確認と、人が描く範囲の実装への着手。
- 止まっている: 実車試験。VM の `~/gouda_ws` のコードの更新（main に入った後に update.sh：人）と Gouda の起動。

## 主要ファイルの場所（CLAUDE.md 1.9 の対応表。パスはリポジトリ `tsukuba-autonomous-robot/` 相対）

| 役割 | 場所 | 備考 |
|---|---|---|
| 設計意図（人が所有） | `design/intent.md` | 第14版（SHA 9bf08d3e…、108 行）。写し `baselines/intent_history/`（`intent_v14_9bf08d3ebe24.md` など） |
| 正本（YAML） | `design/model.yaml`、`design/schema.json` | 変更は `revisions/REV-xxx.yaml` → `tools/apply_revision.py REV-xxx --dry-run --check` → 本適用。最新 REV-136。番号は `tools/reserve_ids.py` で予約する |
| 正本（Markdown） | `design/docs/` | `implementation_stages.md`、`esp32_protocol_v4.md`、`vehicle_output_timing.md`、`speed_filter_design.md`、`map_conversion.md`、`sensor_supervision.md`、`regulations_2026.md`、`git_management_plan.md`、`deferred_verification.md` |
| 判断台帳 | `model.yaml: decisions`（DEC-001〜226） | ビュー: `generated/pending_classification.md`、`conflicts.yaml`、`intent_open_items.yaml` |
| トラブルシューティング台帳 | `design/troubleshooting/ledger.yaml`（TRB-001〜）、スキーマ `design/troubleshooting/schema.json` | DEC-321 で作成（第138便）。検査は `rules/test_troubleshooting_ledger.py`。承認した設定が原因になりうる症状を先に登録し、起きたら `occurrences` に追記する |
| 検査器・ルール一覧・試験 | `tools/validate_model.py`、`tools/check_design.py`、`rules/` | `rules/README.md` |
| スクリプト | `tools/` | `run_checks.py`、`render_views.py`、`generate_params.py`、`render_migration_review.py`、`apply_revision.py`、`reserve_ids.py`、`hardcode_scan.py` |
| 生成物（手で編集しない） | `generated/`（`params/` に node ごとの設定、`firmware_config.yaml`）、`conflicts.yaml`、`intent_*.yaml`、`reports/*.json` | firmware のビルド時のヘッダはビルドのときに生成する（コミットしない） |
| 提案 | `proposals/` | 承認済みの仕様として使わない |
| 調査・証拠 | `research/` | `vehicle_pc/`（試験の記録、DAC の実測と配線）、`joystick270_firmware/`、`upstream_jazzy/`。MID-360 の接続試験の台帳と道具は `vehicle_pc/2026-11-06_mid360_connection/`（`ledger.yaml`、`tools/`、`tools/p4_driver/`）、地面分割の調査と比較は `ground_segmentation_2026-11-07/`、ドライバの作り方は `upstream_sensors/livox_ros_driver2_colcon_2026-11-07.md`（第235便） |
| 報告・作業記録 | `reports/`、`reports/worklog/` | 引き継ぎ `reports/handover_2026-10-21_2.md`。最新の作業記録 `2026-10-21_rev136_dec220_224_transcribed.md` |
| ロボットの実装 | `gouda_interfaces/`、`gouda_core/`、`gouda.sh`、`setup.sh`、`update.sh`、`third_party/drivers.repos`、試験用 `gouda_core/test/stack.sh` | 起動は `bash gouda.sh start` だけ |
| firmware | `firmware/gouda_esp32_v4/` | 旧 `firmware/gouda_esp32`・`gouda_dualsense_usb` は置き換えの対象 |
