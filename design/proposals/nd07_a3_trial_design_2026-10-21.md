# ND-07 を案 A3 で試す設計、推定不能での一時停止、recovery の回数の変更、setup.sh（提案 第1版。実装は許可まで行わない）

状態: 提案。DEC-203・205・206 は人が回答し、§2・§3・§5 は REV-128 で正本に入れて実装した（第99便。値は DEC-208、段 5 は DEC-209 で承認待ち）。§4 の「goal の behavior_tree」の案は DEC-204・207 で採らない（gouda.sh start で BT を作る）。2026-10-21、第97便（REV-126）。

- 根拠（人の回答。分岐セッションからの転記）: DEC-200（E-1、推定不能・Nav2 の失敗で一時停止）、DEC-201（E-2、recovery の回数を monitor で変える）、DEC-202（E-4、setup.sh の改修）、DEC-115（E-3、ND-07 は案 A3 を試す）。
- 読んだもの（コミット 4b44f75。分岐先は 34bc9e0 を読んだ）: `proposals/localization_selection.md`（§4 A3、§6.1、§7）、`proposals/stage56_navigation_localization_plan.md`、model.yaml の ND-03・07・08・10、TR-05・07、IFD-18・25・33・34・52、PRM-18、D-13、SO-05、G-RECOVERY-COUNT、`gouda_core/gouda_core/mode_manager_node.py`、`nav2_config.py`、`launch/gouda_nav2.launch.py`、`monitor_node.py`・`monitor_core.py`（/config のタブ）、`setup.sh`、評価の道具 `research/vehicle_pc/2026-10-17_localization_eval/tools/run_eval_A3.sh`・`a3_init.py`・`params/eval_A3_ekf.param.yaml`。
- VM（2026-10-21 に ssh で確かめた事実）: autoware_ndt_scan_matcher・autoware_ekf_localizer・autoware_map_loader は 1.9.0 が入っている。pcl_ros 2.6.5 も入っていて（autoware_utils_pcl の依存）、`filter_voxel_grid_node`・`filter_crop_box_node` がある。Nav2 1.3.13 の NavigateThroughPoses の goal には `string behavior_tree` がある。feedback には `int16 number_of_recoveries` がある。
- 事実と、AI の推奨・推測を分けて書く。推測は「推測」と書く。

## 1. 転記の前提と、今の実装の食い違い（事実）

| 転記の前提 | 今の実装（4b44f75） | 扱い |
|---|---|---|
| E-2「反映は次に自律走行を開始したとき（TR-05 で mode_manager が Nav2 の設定を作り直す時）」 | Nav2 の設定と BT は **gouda.sh start のときに一度だけ** 作る（`gouda_nav2.launch.py` が `nav2_config.write` を呼ぶ）。TR-05 では作り直さない。lifecycle の起動だけ | §4 の案。goal の `behavior_tree` を使えば、Nav2 を作り直さずに走行ごとに回数を変えられる |
| E-4「setup.sh が Nav2 を入れるかも確かめ…」（stage56 の計画の 23 行「setup.sh は Nav2 も入れない」） | setup.sh は **Nav2 を入れている**（DEC-121。`ros-jazzy-nav2-bringup` ほか 12 個） | Nav2 の追加は不要。Autoware の 3 つだけ |
| E-3「点群の間引き」（評価では C++ の小さな node） | 上流の pcl_ros 2.6.5 に VoxelGrid と CropBox の node がある（VM） | §2 の案。独自の node を作らずに済む見込み |

## 2. ND-07 の構成（案 A3 を試す）

### 2.1 部品

| 部品 | 種類 | 中身 | 出典・根拠 |
|---|---|---|---|
| autoware_pointcloud_map_loader | 上流（apt 1.9.0、改変しない） | 選んだ地図の 20 m 格子の PCD を読み、ndt に差分で渡す（`/service/get_differential_pcd_map`） | 評価 run_eval_A3.sh |
| autoware_ndt_scan_matcher | 上流（同上） | 間引いた点群と EKF の姿勢から ndt_pose_with_covariance を出す。Monte Carlo の初期姿勢の探索 `ndt_align_srv`。起動・停止 `trigger_node`（SetBool） | 評価、localization_selection §4 |
| autoware_ekf_localizer | 上流（同上） | NDT の姿勢と速度を融合して ekf_pose_with_covariance と map→base_link の TF を出す。起動・停止 `trigger_node` | 同上 |
| 点群の間引き | 上流の pcl_ros（`filter_crop_box_node` で 1〜100 m、`filter_voxel_grid_node` で格子 0.5 m） | IFD-21 → 間引いた点群 | 評価の eval_voxel_filter と同じ処理（評価は C++ の独自 node）。pcl_ros の node の出力が評価と同じかは**未確認**（実装の最初の試験で比べる） |
| gouda_global_localization（ND-07 の本体） | Gouda の lifecycle node（Python、gouda_core） | 下の 4 つの内部コンポーネント | — |

ND-07 の本体の内部コンポーネント（1 つの node の中。node を増やさない）:

1. **速度の中継**: IFD-25（localization/odometry、ND-08 が出す）を TwistWithCovarianceStamped（base_link）にして EKF に渡す。評価の twist_relay.py と同じ役割。
2. **map→odom の中継**: EKF の /tf は launch の remap で、誰も読まない名前（例 `localization/a3/ekf_tf`）に逃がす。ekf_pose_with_covariance（map→base_link）と、同じ時刻の odom→base_link（TF、ND-08 系）から map→odom を計算して /tf に出す。**map→odom を出すのはこの node だけ**（D-17、RQ-I004）。
3. **初期化の手順**: IFD-34（人が指定した初期姿勢）を受けたら、`ndt_align_srv`（Monte Carlo の探索）→ 成功したらその姿勢を EKF の初期姿勢に出す → EKF・NDT の `trigger_node` を true。各段の成否を DecisionEvent に残す。探索が失敗したら map→odom を出さず「未初期化」のまま（推測で姿勢を出さない）。
4. **推定の状態（EstimatorStatus）**: §3。

起動と停止（案）:
- ND-03 が TR-05 で ND-07 を configure（選んだ地図の ID と格子の場所を渡す。このとき ND-07 が map_loader・ndt・ekf・pcl_ros を子の launch で起動する）→ activate（初期化の手順）。TR-11・TR-12 で deactivate → cleanup（子の launch を止める）。ND-08（GLIM の odometry）の起動・停止と同じ置き場所（ND-03）。
- 理由: map_loader は起動のときに地図の場所を受け取るので、地図を選んだ後（TR-05）でないと起動できない。地図作成の GLIM と同時に動かさない（RQ-I004）こともこれで守れる。
- TR-05 の guard「ND-07 が活性」は、activate の後に「正常」（§3）になったことで確かめる案。初期化に失敗したら TR-05 は TR-07（stop_reason は estimator_unavailable、§3）で一時停止。

### 2.2 TF の木（変わらない）

map →（ND-07 の中継）odom →（GLIM、単位行列）odom_glim →（GLIM）base_link。EKF の map→base_link は /tf に出ない（remap）。試験で、/tf の map→odom の発行者が 1 つであること、base_link の親が 1 つであることを確かめる。

### 2.3 地図の 20 m 格子

- 地図の変換（ND-05、map_convert）で、原図の点群から 20 m 格子の PCD と map_loader の metadata を作り、変換後の地図の横に置く。評価の tile_pcd.py と同じ処理。
- 地図の変換の出力が増えるので、変換後の地図のハッシュの対象（TR-05 の guard）に含めるかを決める（案: 含める）。
- 間引きの格子（評価は 0.2 m で作った PCD）は、地図の変換の新しい設定値（tbd）。

## 3. 推定不能での一時停止（E-1、DEC-200）

### 3.1 EstimatorStatus（新しい IF。D-13 の案を元にする）

- topic `localization/status`（案）、新しい型 `gouda_interfaces/EstimatorStatus`（header、state、reason、主な数値）。reliable・transient_local・depth 1。状態が変わったときと、周期（tbd）で出す。
- state: 未初期化／初期化中／正常／推定不能。「推定不能」には理由の区分を付ける（NDT の照合の不良、EKF の姿勢の更新の途絶、EKF のマハラノビス距離による棄却、共分散の大きさ、入力の途絶、中継の TF が古い）。
- 判定の材料（DEC-115 の問い 2 の案 (b)、EKF の診断を加える）:
  - NDT: nearest_voxel_transformation_likelihood（または transform_probability）、照合を飛ばした回数。
  - EKF: diagnostics の pose_no_update_count、姿勢の棄却（pose_gate_dist、評価の既定値 49.5）、誤差の楕円の大きさ（既定 error_ellipse_size 1.5 m・横 0.3 m）。
  - 中継: 最後に map→odom を出してからの時間。
- **判定のしきい値はすべて新しい PRM で、値は tbd**（実走で決める。上流の既定値をそのまま採用値にしない）。stale・未初期化を「正常」にしない。生存の信号で品質を代用しない（IF-010）。
- 未確認: 評価で見逃した 0.546 m の跳ね（localization_selection §6.1）のとき、EKF の診断が出ていたか。評価の記録は NDT の diagnostics だけで、EKF の diagnostics は残っていない（評価の道具 eval_logger.py の引数）。次の評価（rosbag の再生）で EKF の diagnostics も記録して確かめる。

### 3.2 一時停止の経路

- ND-03 は自律走行の間、IFD（localization/status）を購読する。state が「推定不能」になるか、status が届かない時間が PRM（tbd）を超えたら:
  1. motion_hold=true（IFD-40）を先に出す。
  2. Nav2 の goal を取り消す（今の TR-07 は Nav2 の result を待つ形で、goal はもう終わっている。推定不能では goal がまだ動いているので、TR-06 と同じ取消が要る）。
  3. TR-07 の一時停止。stop_reason は新しい区分 `estimator_unavailable`（今の `plan_failure`・`node_failure` と分ける。RQ-I029、intent.md:15「経路閉塞と、推定不能・通信異常は区別する」）。DecisionEvent に理由の区分と数値を残す。monitor は理由を表示する。
- 一時停止の間も ND-07 は推定を続ける。再開（TR-10）の guard に「state が正常」を足す（案）。
- 一時停止の後に自動で再初期化して走り出すこと（推定不能からの自動復帰 TR-13）は作らない。DEC-134（pending：NDT と GNSS の差とスコアの劣化で停止して再初期化、TR-13 の具体化）は工程 5-7 の側に残る。この案は DEC-134 の「停止」の部分だけを先に作る形で、食い違わない（AI の読み）。
- Nav2 の失敗（今の TR-07、`plan_failure`）はそのまま。PRM-18＝9999999 では BT はほぼ失敗を返さない（DEC-194）ので、推定が狂ったときに止まる経路はこの推定不能の経路になる。

### 3.3 安全の注意（CLAUDE.md 1.5）

- 一時停止は PC の出力の中立化（motion_hold）で、車体の停止の保証ではない（手動の優先、ESP32・駆動系の故障、慣性・斜面）。
- 推定不能の判定は、判定の材料に現れる失敗だけを検出する。誤った姿勢を「正常」とみなすことは残る（評価の 0.546 m の例）。これを人に見えるようにするため、monitor に推定の状態と数値を常に表示する案。

## 4. recovery の回数を monitor で変える（E-2、DEC-201）

- 既定値は PRM-18（9999999、承認値）のまま。
- monitor の /config に入力欄を置く。置き場所は案 (a) 新しいタブ「Nav2」、案 (b) 今の「自律走行の出力」タブ（DEC-181）に足す。推奨は (a)（不感帯の補償は motion_controller の値で、recovery は Nav2 の値なので分ける）。
- 保存先は `<data_root>/config/nav2_recovery.json`（DEC-181 と同じ考え方で、センサの /config とは別のファイル）。範囲の検査: 1 以上 9999999 以下の整数（推奨）。0（recovery をしない、最初の失敗で一時停止）も受け付けるかは人の判断。保存のたびに DecisionEvent（変更の前後の値）を残す。
- **DEC-181 の扱いと合わない点**: 不感帯の補償の値は「generated/params の PRM にはしない」運用値だった。recovery の回数は承認済みの PRM-18 がある。案: 「monitor に値がなければ PRM-18、あれば monitor の値」。monitor には「保存した値」「次の走行で使う値と出所（PRM-18 か monitor か）」「今の走行で使っている値」を常に表示する。
- 反映（§1 の食い違いへの案）: TR-05 で ND-03 が、上流の BT に PRM-11 とその時点の回数を入れた XML を `<run_dir>/nav2/bt_<run_id>.xml` に書き、NavigateThroughPoses の goal の `behavior_tree` にその場所を入れる。同じ走行の再開（TR-10）は同じファイルを使う（「次の走行で反映」の読み。走行中の goal には効かない、DEC-201 の原文 3）。Nav2 の起動のときに作る既定の BT（PRM-18）はそのまま残す（goal に BT がないときの既定）。
- Nav2 の本体は改変しない（goal の `behavior_tree` は上流の機能）。

## 5. setup.sh（E-4、DEC-202）

- `wanted` に `ros-jazzy-autoware-ndt-scan-matcher`・`ros-jazzy-autoware-ekf-localizer`・`ros-jazzy-autoware-map-loader` を足す（依存は apt が入れる。pcl_ros は依存で入る）。
- 版: ROS の apt は**最新の build だけを置く**（VM の版の文字列は `1.9.0-1noble.20260921.041620` のように build の日時を含み、arm64 と amd64 で違う。推測を含む）。GLIM のように版の文字列そのものでは固定できない。案: 上流の版（`1.9.0-`）を確かめ、違う版が入っている・入ろうとするときは止まって理由を言う（GLIM の DEC-062 と同じく、版の変更は設計の判断）。代わり: 版を見ない。
- 未確認: x86 機の apt に今 1.9.0 があるか（上流は 2026-10-15 に v1.10.0。apt に来ていれば 1.9.0 は入れられない）。実装の前に確かめる。
- x86 機での実行は人。

## 6. 工程 5-7（自動の復帰）は最初の自律走行の後（E-5）

- 分岐先の推奨は「最初の走行の後に回す。推定不能の検知だけは先に作る」。人は E-1（DEC-200）で推定不能の一時停止を採った。工程 5-7 の TR-09・TR-13〜16、G-RECOVERY-COUNT、BT の recovery の 50 回ごとの記録を後に回すことを、人が明示した原文はない（DEC-206 で確かめる）。
- 参考（事実）: NavigateThroughPoses の feedback の `number_of_recoveries` は int16 で、32767 を超える数は表せない。50 回ごとの記録を設計するときの材料。

## 7. 「駄目」の判断の材料（試験で観測する項目。基準値は tbd、推測で決めない）

- 初期化: 人の初期姿勢から「正常」になるまでの時間と成否（同じ場所で出発の前に 10 秒以上止まった状態）。
- 走行中: 「推定不能」の回数・続いた時間・理由の区分。GLIM の軌跡（同じ走行の地図）や、別の走行の地図での位置の差。跳ね（短い時間の大きな位置の変化）の回数。
- 処理: x86 機の CPU とメモリ、照合の時間、等倍で取りこぼさないか。
- Nav2: 自律走行の中で、推定不能による一時停止と計画の失敗による一時停止の回数。
- これらを DecisionEvent・rosbag・EstimatorStatus から読み出す解析の道具を用意する（実装の許可の範囲に含める）。

## 8. 実装の段（許可の単位の案）

| 段 | 中身 | 試験 |
|---|---|---|
| 1 | setup.sh（§5） | x86 機で人が実行。VM は導入済み |
| 2 | 地図の 20 m 格子（§2.3） | 単体（格子の数・点の数・metadata）。実機の原図の写し |
| 3 | ND-07 の本体と launch（§2）、EstimatorStatus の型と IF（§3.1）、しきい値の PRM（tbd） | 単体（中継の計算、状態の判定、初期化の手順の順序）。VM で rosbag の再生（評価と同じ地図・同じ区間）で、評価の結果と比べる |
| 4 | ND-03 の推定不能の一時停止（§3.2）、再開の guard | 単体（mode_core）。VM の試験スタック（status を模擬して一時停止・取消・理由の記録） |
| 5 | recovery の回数のタブと BT の反映（§4） | 単体（monitor_core の範囲の検査、BT の生成）。VM で goal の behavior_tree が使われること |
| 6 | 結合（rosbag の再生 → 実車の低速） | 実車の判断は人 |

## 9. 承認していただきたいこと（判断台帳）

| ID | 内容 | 推奨 |
|---|---|---|
| DEC-203 | ND-07 の構成（§2）、推定不能の判定と一時停止の経路（§3）を正本に入れ、段 2〜4 を実装する | 承認 |
| DEC-204 | recovery の回数（§4）: 置き場所 (a)、範囲 1〜9999999、「monitor に値がなければ PRM-18」、goal の behavior_tree で走行ごとに反映し同じ走行の再開は同じ値。段 5 を実装する | 承認 |
| DEC-205 | setup.sh（§5）: Autoware の 3 つを足し、上流の版 1.9.0 でなければ止まる。段 1 を実装する | 承認（実装の前に x86 機の apt の版を確かめる） |
| DEC-206 | 転記の解釈の確認: (1) 原文 2「9999999野間まで良い」は「9999999 のままで良い」、(2) 推定不能の判定に EKF の診断を使う（DEC-115 の問い 2 の (b)）、(3) 工程 5-7 は最初の自律走行の後 | 確認 |

決まらない場合に止まる作業: DEC-203 → ND-07 と自律走行の開始。DEC-204 → recovery の回数の変更だけ（PRM-18 のまま走れる）。DEC-205 → x86 機での A3 の起動。DEC-206 → 記録の確定だけ（(2) が違えば §3.1 を作り直す）。
