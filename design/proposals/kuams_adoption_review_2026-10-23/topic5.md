# トピック 5：速度・旋回の上限と collision_monitor（KUAMS との比較）

読んだもの：gouda リポジトリ HEAD 31a6e1d＋未コミットの作業ツリー（2026-10-23 時点。他の便が編集中）、KUAMS の写し kuams@750934a。読むだけで、ファイルの変更・実車・VM の操作はしていない。
記号：【事実】は出典（file:line）付き、【計算】は数値の計算、【推測】は確認していないこと。安全に関わる値（停止距離・速度・時間）は埋めず、tbd と計測の手段を書く（CLAUDE.md 1.5）。

## 1. 問い

gouda は、速度と旋回の上限を KUAMS 並み（0.8 m/s・0.3 rad/s）に下げるべきか。また、外した Nav2 の collision_monitor を戻すべきか（どちらか一方か、両方か、どちらもしないか）。

## 2. gouda の現状

### 2.1 速度・旋回（承認済みの値）
- 【事実】PRM-66 は 1.25 m/s、PRM-67 は 1.0 rad/s、PRM-68 は 1.2 m/s²、PRM-73 は 2.0 rad/s²（design/generated/params/gouda_nav2.yaml:7-14）。人の決定 DEC-192 の原文は「全体的に安全思想に偏りすぎ」「前進の最高速は4.5km/h」（model.yaml の DEC-192）。
- 【事実】1.25 m/s は、ジョイスティックを倒し切ったときの車椅子の最高速（PRM-39＝1.25、DEC-193「最高速度は4.5km/h」）。motion_controller は linear.x を PRM-39 で割って、倒す量に直すだけ（motion_core.py:159-160）。車椅子の速度は開ループで決まり、指令の速度と実際の速度の対応は測っていない（Q-06）。
- 【事実】旋回は PRM-40＝0.97 rad/s で正規化する（gouda_motion_controller.yaml:9）。PRM-67 の 1.0 は、ここで頭打ちになる（PRM-67 の measurement）。
- 【事実】nav2_config.py:129-131 は、FollowPath を RPP の 4 つのキー（plugin、desired_linear_vel、rotate_to_heading_angular_vel、allow_reversing）だけで置き換える。lookahead、衝突の検査の時間、曲率による減速などは、上流の既定値のまま設計されていない。
- 【事実】RPP の角速度は linear_vel×曲率（upstream_jazzy/.../regulated_pure_pursuit_controller.cpp:271）。velocity_smoother の上限は [vmax, 0, wmax]（nav2_config.py:174）。上流の雛形では scale_velocities は False（upstream_jazzy/nav2_bringup/params/nav2_params.yaml:363）。
- 【事実】local costmap の大きさは上流の雛形の 3 m×3 m（rolling、5 Hz。nav2_params.yaml:191,195-197）。nav2_config は変えていない。base_link から前に 1.5 m までしか入らない。footprint の前端は 0.55 m（PRM-69）。
- 【事実】区間ごとの速度上限はできている：speed_mask.py（区間の帯に上限を塗る）→ SpeedFilter（nav2_config.py:158-160）。帯の外は無制限（intent.md:28、autonomy_core.py:26 の SL_OUTSIDE_BAND）。
  - ただし、帯の半幅 PRM-19 と刻み PRM-20 は unresolved（model.yaml の PRM-19・PRM-20）。monitor は、要求に値がなければ保存を断る（monitor_node.py:386-390）。
- 【事実】NDT への点群は、gouda_a3_points で切り取りと間引きをするだけで、動きによる歪みの補正（deskew）はしない（gouda_localization_a3.launch.py:5-12）。XT-32 は 600 rpm＝10 Hz（hesai_ros_driver.yaml:12、PRM-60）。

### 2.2 collision_monitor を外した理由
- 【事実】DEC-122（2026-10-17、人の回答「DEC-120〜124 をすべて許可する」）の問いに「collision_monitor は使わない（RQ-I072）」とある。note には「近づいたら止める PC 側の機構はない（障害物は costmap と計画で扱う）」。
- 【事実】RQ-I072 は intent.md の次の行に当たる（今の版では 102 行）。「非常停止検知/非常停止ボタン押下検知は行わないし、PC側で非常停止機構は存在させない。これは絶対決定事項であって、反論を許さない。」
  - 検査 DR-06 が、これを機械で確かめている（tools/check_design.py:146-152）。
  - stage56 の計画では、近づいたら止める機構は「PC 側の非常停止に当たりうる」として外した（proposals/stage56_navigation_localization_plan.md:55）。costmap の提案 STVL 版 §139 も、同じ理由で勧めていない。
- 【事実】intent.md:27 は「cmd_velの後段で独自に速度を抑える処理は加えない」。intent.md:1 は「ロボット自体の安全機構は極限まで削減すべき」。intent.md:39 は「追加の保護は、必要性・根拠・開発への影響を添えた提案として出す」。
- 【事実】今の指令の経路は次のとおり（gouda_nav2.launch.py:54-61、vehicle_output_timing.md:8）。PC 側で障害物の前で止まるのは、local costmap と RPP の衝突の検査だけ（costmap 第2版 §7）。
  - controller / behavior_server → cmd_vel_nav → velocity_smoother → cmd_vel → motion_controller → vehicle_bridge（0.1 s 周期、PRM-14）→ ESP32 → DAC → EMC-270

### 2.3 関係する pending と記録（繰り返さず参照する）
- DEC-339（人が規則を確認）：コーン（確認走行区間）と歩行者への接触は失敗。DEC-341（pending）：DEC-321・322 の見直し（推奨は、3 次元の local と MID-360）。
- TRB-001（2 次元の local で低い物が消える）、TRB-002（点のない方位を消去）、TRB-003（途絶を検出しない、DEC-325）、TRB-004（段差で推定が乱れる。対策の候補 (c) に「段差の区間の速さを下げる」がある）。
- DEC-348（障害物を遠くから認識する）、DEC-344（区間ごとの inflation）、DEC-342・354（推定不能のとき止まって待つ）。
- 第138便の作業記録 6.1：「RPP は前方の走行帯（約 1.15 m）に物があれば止まる」「置かれたコーンの前で RPP が止まり、経路が引き直されるまで待つ」〔推〕。

## 3. KUAMS が実際にしていたこと、gouda との前提の違い

### 3.1 コードで確かめたこと（kuams_navigation/config/params_nav2.yaml）
- 【事実】MPPI の設定（:75-131）：vx_max 0.8、vx_min 0.0、wz_max 0.3、batch 2000×56 段×0.05 s、PreferForwardCritic の重み 5。velocity_smoother は 0.8 m/s・2.5 rad/s・2.5 m/s²、OPEN_LOOP（:316-326）。旋回を縛っているのは MPPI の 0.3。
- 【事実】collision_monitor（:332-362）と指令の経路（navigation.launch.py:126,192）。
  - 経路：controller → cmd_vel_nav → smoother → cmd_vel_smoothed → collision_monitor → cmd_vel
  - PolygonStop：[1.0, ±0.30]〜[0.0, ±0.30]、max_points 3、stop
  - FootprintApproach：time_before_collision 2.0 s
  - source：/livox_scan（LaserScan）、source_timeout 5.0
- 【事実】/livox_scan は Mid-360 の点群を pointcloud_to_laserscan で切ったもの（sensors.launch.py:76-94）：target_frame front_sensor_link、高さ ±0.2 m、range_min 0.45、use_inf true。front_sensor_link は base_link の (0.6, 0, 0.3)（kuams.xacro:189）。footprint の前端は 0.80（params_nav2.yaml:186）。
- 【計算】KUAMS の停止の四角は、見た目ほど効いていない。
  - 四角は x 0〜1.0 なので、footprint の前端（0.80）から外に出るのは 0.2 m だけ。
  - その 0.2 m の帯の点は、センサからの水平の距離が多くの所で 0.45 m 未満になり、range_min で捨てられる。例：(1.0, 0) は 0.40 m、(0.9, 0.3) は 0.42 m、(1.0, 0.3) は 0.50 m。
  - 見えるのは、x がほぼ 0.93 以上で、四角の左右の端に近い所だけ。range を target_frame の hypot(x, y) で測るのは、上流のコードの記憶による【推測】。
- 【推測】効いていたのは、0.8 m/s の上限と、FootprintApproach（2 s 先に当たるなら減速）と、MPPI の障害物の評価だと思われる。
- 【推測】本番の設定は公開されていない。写しはレースの約 2 か月前のもの。待機列の lineup の node は cmd_vel を直接出すので、collision_monitor を通らない可能性がある（reports/KUAMSの工夫まとめ.md:65）。
- 【事実】本番では 2200 m を 70 分で走った（11:30〜12:40）。平均は約 0.52 m/s で、停止を含む（reports/KUAMSとgoudaの比較.md:200-207）。

### 3.2 前提の違い
| | KUAMS | gouda |
|---|---|---|
| 車体と速度の制御 | WHILL CR。ドライバが速度を受けて閉ループで制御し、オドメトリも出す | 電動車椅子のジョイスティックの電圧を DAC で出す開ループ。車輪のエンコーダはない |
| 低い所の観測 | Mid-360 を下向き 20° で 0.3 m の高さに付けている | XT-32（取り付け 1.015 m、最下のビーム −16°）。1.5 m 先で 0.585 m より下は見えない（TRB-001）。MID-360 は第3版で設計中 |
| controller | MPPI。v と ω を一緒に標本化し、曲がるときは自分で減速する | RPP。ω＝v×曲率。ω を上限で切ると、v は落とさないまま、曲がり方だけが足りなくなる【推測】 |
| 意図 | — | PC 側の非常停止の機構を置かない（intent.md:102、絶対）。cmd_vel の後段で速度を抑えない（intent.md:27） |
| ROS | Humble（README.md:27。max_points の定義） | Jazzy / Nav2 1.3.13（min_points。source_timeout の扱いは版で違いうる【推測】） |

## 4. 選択肢

### 4.1 速度・旋回
- **S-A（推奨）：大域の上限（PRM-66・67）は今のまま。遅くしたい所は、区間の速度上限（speed mask）で下げる。** 回転だけは、実測の後に「その場の回転」の上限を分けて下げるかを決める。
  - 遅くする区間の候補：確認走行区間（約 400 m、コーン）、横断歩道の手前（TK-25 の早めの減速）、人の多い所、公園、段差（TRB-004）。
  - 理由 1（時間）：完走に必要な平均は、待ち時間 W と余裕で決まる（下の表）。速く走れる区間で稼いだ時間を、待ちや回復に回せる。
  - 理由 2（RPP）：RPP のまま ω を 0.3 に下げると、角を曲がり切れずに外へふくらむ【推測】。曲がれる最小の半径は v/ω で、1.25/1.0＝1.25 m、0.8/0.3＝2.67 m、1.25/0.3＝4.17 m【計算】。KUAMS の 0.3 rad/s は、MPPI だから成り立つ値である。
  - 理由 3（推定）：NDT は deskew していない点群を使う。1 周 0.1 s の間に、1.0 rad/s なら 0.1 rad 回り、20 m 先の点で最大約 2 m ずれる。0.3 rad/s なら約 0.6 m。並進は 1.25 m/s で 0.125 m、0.8 m/s で 0.08 m【計算】。歪みは並進より回転で大きくなる。効くのは主に、その場の回転（rotate_to_heading と spin）である【推測。NVTL への影響は未測定】。
  - 前提：PRM-19（帯の半幅）を実測で決める。PRM-20（刻み）は計算で決まる（1.25/100＝0.0125 m/s 以上、PRM-20 の measurement）。区間の上限の値は、人が waypoint_manager で入れる（intent.md:14）。
  - 弱み：迂回で帯の外に出ると無制限、つまり 1.25 m/s になる（intent.md:28）。コーンの区間でこそ迂回が起きる（H4）。
- **S-B：KUAMS 並みに、大域の上限を下げる（例：0.8 m/s。旋回は RPP に合わせて 0.3 より大きく）。** 帯の外の問題が起きず、単純である。
  - ω を下げるなら、smoother の scale_velocities を true にするか、MPPI に替えないと、曲がり方が足りなくなる。
  - 時間の余裕は減る。さらに開ループのため、0.8 を指令しても 0.8 m/s 出るとは限らない（倒す量 0.64。対応は未測定）。
- **S-C：MPPI（PreferForward）に替える**（DEC-122 の代替案）。ω の上限と回避を一緒に扱える。
  - ただし、CPU（2000×56 段を 20 Hz）を実車 PC で測っていない（G15）。設定と試験を一からやり直すことになる。本番前には勧めない。
- **S-D：取り入れない（今のまま 1.25 / 1.0 を全区間で使う）。** 確認走行区間のコーンと歩行者の危険（H1）が、そのまま残る。

### 4.2 collision_monitor
- **C-A（推奨）：今は戻さない。** 守りたいもの（急に置かれたコーン、近くの低い物）は、costmap 第3版（MID-360、DEC-341）と、確認走行区間の速度の上限で守る。あわせて、RPP の衝突の検査と lookahead を PRM として明示し、停止距離の実測と照らし合わせる。
  - 理由：intent.md:102（絶対）・27 と DR-06 に当たりうる。XT-32 を源にすると、近くの低い物は見えないので、TRB-001 の穴を埋められない。誤った停止は滞留を生む（H2）。
- **C-B：確認走行区間だけ、approach 型（向きを見る）を入れる。** 源は MID-360、高さの帯は base_link 基準。走行中に有効と無効を切り替える【推測：Jazzy で動的に切り替えられるかは要確認】。
  - 前提：intent.md:102・27 の範囲を、人が解釈・改訂すること（AI は反論しない。範囲の確認として尋ねる）。
- **C-C：KUAMS と同じに戻す（stop の四角＋approach を全区間で）。** 勧めない。
  - stop の四角は向きを見ないので、中に物があると後退も回転も止まる【推測】。四角の中にコーンが置かれると抜け出せず、確認走行区間では 3 分の滞留で失敗になる。
  - Jazzy では、source が古くなると止める動きの可能性がある【推測、1.3.13 のソースで要確認】。これは、途絶で止めないと決めた DEC-325 とぶつかる。
- **C-D：取り入れない（恒久）。** C-A と違い、MID-360 の後も検討しない。

## 5. 振る舞いの違いと、影響を受ける ID

- S-A
  - 速度：区間の帯の中では上限まで落ちる。帯の外と、帯のない区間では 1.25 m/s のまま。
  - 回転：分けた場合は、その場の回転だけが遅くなる。90° に 1.0 rad/s で 1.6 s、0.3 rad/s で 5.2 s【計算】。
  - 影響：PRM-19・20、IFD-14・41・42、waypoint のデータ（section_limits_mps）、PRM-67（分ける場合は新しい PRM）、nav2_config.py:130,171（rotate_to_heading と behavior の max_rotational_vel）。
- S-B
  - 全区間が遅くなる。PRM-66・67、velocity_smoother（nav2_config.py:174）。
  - PRM-39・40 は倒し切りの正規化なので変えない（下げると倒す量の対応が変わる）。
- C-A
  - 振る舞いは今と同じ。MID-360 と RPP の PRM 化で、止まる距離と見える距離が変わる。
  - 影響：DEC-341、TRB-001・002、PRM-69・72、RPP の新しい PRM（lookahead、衝突の時間）、local costmap の大きさ（今は上流の 3 m）。
- C-B / C-C
  - cmd_vel の経路に node が 1 つ増える（smoother → cmd_vel_smoothed → monitor → cmd_vel）。gouda_nav2.launch.py:61 の remap、IFD-15 の発行元、LIFECYCLE_NODES・KEPT（nav2_config.py:67-71）が変わる。
  - 停止は smoother の傾き（1.2 m/s²）を通らずに、すぐ 0 を出す。
  - 影響：RQ-I072、C-017、DR-06、intent.md:27・102、ND-10・11、TS-07・13。

## 6. ハザードと安全上の根拠（警告の有無にかかわらず重大なもの）

- **H1 コーン・歩行者への接触（失敗、DEC-339・EV-18）。**
  - 【計算】PC 側の周期の和（controller 0.05＋smoother 0.05＋motion_controller 0.05＋bridge 0.1＋local costmap 0.2＋LiDAR 0.1）は約 0.55 s。この間に、1.25 m/s で 0.69 m、0.8 m/s で 0.44 m 進む。
  - 【計算】smoother の傾き（1.2 m/s²）で 0 まで落とすと、1.25 m/s から 1.04 s・0.65 m、0.8 m/s から 0.67 s・0.27 m かかる。
  - この二つの計算には、処理時間、ESP32、車椅子の制御器の減速、慣性、坂を入れていない。**停止距離ではない。停止距離は tbd（M1）。**
  - 見える範囲：local costmap は base_link の前 1.5 m まで。RPP の検査は約 1.15 m（第138便）。RPP の既定値（lookahead 0.6 m など）は記憶による【推測】。1.25 m/s では、PC 側の計算だけでも検査の範囲を超える可能性がある。
- **H2 滞留（確認走行区間では 3 分で失敗、EV-25）。** collision_monitor の誤った停止（壁・草・縁石・坂）と、stop の四角での抜け出せない状態。経路の計画は collision_monitor の四角を知らないので、「計画できるのに進めない」状態が回復で繰り返される【推測】。
- **H3 推定の乱れ。** 回転が速いと、deskew していない NDT の入力が歪む。段差（TRB-004）。推定不能になると、今の作りでは待機に入る（TR-07）。
- **H4 速度の帯の外は無制限（intent.md:28）。** 遅くした区間で迂回すると、1.25 m/s に戻る。
- **H5 PC 出力の中立化は、車体全体の停止の保証ではない（CLAUDE.md 1.5）。** collision_monitor も PC の上の node である。
  - 落ちると cmd_vel が途絶え、700 ms 後に中立になる（PRM-08）。これは「受信していない」ことしか検出しない。誤った値や古い値は検出しない。
  - 安全の根拠になっている前提：ESP32 の watchdog 1 s（PRM-13）、BT の手動操作が ESP32 で優先されること（intent.md:35）、ESP32・駆動系の故障、慣性・斜面。どれも、collision_monitor があってもなくても変わらない。新しい firmware で成り立つかは未確認（vehicle_output_timing.md:3）。
- **H6 100 分の超過（EV-25）。** 大域の上限を下げ、待ち・回復・推定の待ち（DEC-342）が重なる場合。
- **H7 角でふくらんでコースを外れる・車道に入る（EV-15・16）。** RPP のまま ω を下げた場合。
- **H8 開ループ。** 指令した速度と実際の速度が合っているかは、未測定（Q-06）。最高速度 6 km/h（SP-09・10）を超えないことは、車椅子の仕様 4.5 km/h に頼っている【推測：仕様の原本は未照合】。

### 時間の予算【計算】（2200 m。W は停止線・横断・信号の待ちの合計で tbd、M5 で測る）
| 目標のゴール時刻 | W＝10 分 | W＝20 分 | W＝30 分 |
|---|---|---|---|
| 80 分（余裕 20 分） | 0.52 m/s | 0.61 m/s | 0.73 m/s |
| 70 分（余裕 30 分） | 0.61 m/s | 0.73 m/s | 0.92 m/s |

- 余裕なしの全体の平均は 2200/6000＝0.37 m/s。KUAMS は全体で 0.52 m/s（停止を含む）。
- 表の値は、走っている間の平均として要る速さ。0.8 m/s の上限で 0.7 m/s 以上を保てるかは疑わしい【推測】。W が 20 分を超えると、0.8 の大域の上限では余裕 30 分が取れない。

## 7. 実測が要る値と、計測の手順の案

- **M1 車体の停止応答・停止距離。**
  - 誰が：人が運転と安全の確保をする。AI は記録と解析のスクリプトを書く。
  - 何を：指令 0.3／0.5／0.8／1.0／1.25 m/s から、(a) smoother 経由で 0 にする場合と、(b) joystick_command を中立にする場合。平地と、コースの坂で行う。
  - 記録：rosbag（cmd_vel、joystick_command、GLIM の odometry）に、外部の基準（巻尺の目印と動画）を添える。
  - 合否の基準の案：各速度で、停止距離の 95 パーセンタイル＋余裕 ＜ その区間で物が確実に見える距離（M6）。余裕は tbd。
- **M2 倒す量と速度の対応（Q-06）。** 倒す量 0.2〜1.0 の各段で、平地の速度を GLIM と GNSS で測る。合否：指令と実測の差を表にする（基準は人が決める）。
- **M3 推定の質と (v, ω) の関係。** 同じ周回を (v, ω) の組で走る。組は v 0.5／0.8／1.25 と、その場の回転 0.3／0.6／1.0 rad/s。見るもの：NDT の NVTL、推定不能の回数、GLIM と NDT の差。合否：推定不能 0 回、NVTL の低下は tbd 以内。
- **M4 誤った停止の率（collision_monitor を検討する場合）。** 記録した rosbag（人が用意する分、DEC-326）を VM で collision_monitor に通す。人が「本当の物」と「誤り」を付け、1 km あたりの誤った停止の回数と、最長の停止時間を出す。確認走行区間の合否：最長の停止 ＜ 3 分から余裕を引いた値（tbd）、または 0 回。
- **M5 待ち時間 W と区間ごとの所要時間。** 試走で区間ごとに時間を記録する（停止線・横断・信号の周期は、人の遵守事項 TK-85）。
- **M6 コーンが見える距離。** XT-32、MID-360、帯の段の出力のそれぞれで、緑のコーンを 0.5〜3 m に置いて記録し、印が付く距離と消える距離を出す。
- **M7 帯の半幅 PRM-19。** 経路追従の誤差と、迂回の横幅の実測。

## 8. 分類と、決まらない場合に止まる作業

| 項目 | 分類 | 決まらない場合に止まる作業 |
|---|---|---|
| S-A の採用、遅くする区間の選び方 | 承認 | 区間の上限の運用の設計 |
| 区間の上限の値（確認走行区間など） | 実測（M1・M6）→ 人が入力 | 確認走行区間の走行試験 |
| PRM-19 | 実測（M7） | waypoint セットの保存（今は値がないと保存を断る） |
| PRM-20 | 承認（計算で決まるが、PRM の確定なので） | 同上 |
| その場の回転の上限を PRM-67 から分ける | 承認（M3 の後） | なし（今の値で走れる） |
| RPP の lookahead・衝突の時間などの PRM 化 | 承認（明示するだけなら振る舞いは同じ。値を変えると承認） | 停止距離と見える範囲の照合 |
| local costmap の大きさ（上流の 3 m） | 承認（第3版と一緒に） | 同上 |
| S-B（大域の上限を下げる） | 承認 | — |
| collision_monitor（C-B・C-C） | 承認。その前に、intent.md:102・27 の範囲を人に確認する（intent.md は人が直す） | C-B の設計 |
| 停止距離、誤った停止の率、推定と (v, ω)、W | 実測（M1・M3〜M5） | 上の各値の確定 |
| 時間の予算の計算、オフラインの再生のスクリプト | 自律判断（基盤） | — |

## 9. 他のトピックとの依存

- **トピック 1（推定不能で止まらない）**：推定が弱い間に速度を下げたくなる。ただし、SpeedLimit の発行元は 1 つ（intent.md:27-28）なので、mask 以外から上限を出すのは intent に当たる。M3 の結果は、推定不能の頻度の根拠になる。
- **トピック 2（区間ごとに waypoint を送る）**：区間の切り方は、速度の上限の区間と同じ単位にするのがよい。
- **トピック 3（skip の条件）**：collision_monitor の誤った停止と RPP の衝突の停止は、滞留と skip の引き金になる。
- **トピック 4（信号待ちの待機列か手動横断か）**：W の大部分を決める。待機列で前のロボットに近づく動きは、approach・stop と干渉する。KUAMS の lineup は collision_monitor を通らない可能性がある。TK-25（早めの減速）は、mask で表せる。
- **トピック 6（GLIM の軌跡から waypoint を作る）**：地図を作る走行の軌跡から、区間の上限と帯の半幅の候補（PRM-19）を作れる。

## 10. 実装するなら変える範囲の見積り（コードは書かない）

- **S-A**：コードはほぼ変えない。
  - PRM-19・20 の確定（change set → apply_revision → generate_params）。人が区間の上限を入力する。
  - 回転を分ける場合は、新しい PRM を 1 つ足し、nav2_config.py の 2 か所（FollowPath、behavior_server）と REQUIRED、test_nav2_config を変える。小さい。
- **RPP の PRM 化と local の大きさ**：nav2_config.py の follow の辞書と local_costmap に、キーを 4〜6 個足す。PRM と試験も足す。小〜中。
- **S-B**：PRM-66・67 の値の変更（change set）。scale_velocities を変えるなら、nav2_config.py:174 を変える。小さい。ただし、VM と実車での走行試験をやり直す。
- **C-B / C-C**：
  - コード：nav2_config.py（KEPT・LIFECYCLE_NODES・collision_monitor の節）、gouda_nav2.launch.py の remap、MID-360 の源。
  - 正本：PRM を 6〜10 個、IFD-15 の発行元、DR-06 との関係。
  - その他：monitor に collision_monitor_state を表示する（デバッグのため）。TS-07・13 と、VM での試験を足す。
  - 中くらい。さらに、intent.md の人による改訂が前提になる。
