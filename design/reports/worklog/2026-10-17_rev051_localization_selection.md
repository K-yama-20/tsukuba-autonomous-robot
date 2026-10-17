# 作業記録 2026-10-17 第28便: 人の指示（map_creator の改良を置き、自己位置推定の方式の選定へ）と選定の提案（REV-051）

## 読んだもの

- コミット `6b86d92`（ブランチ design/field-mapping-2026-10-14）。加えて、第27便の未コミットの記録（作業記録 `2026-10-14_evening_maps_rosbag_analysis.md`、研究記録 `2026-10-14_evening_maps_rosbag.txt`）。
- 正本: DEC-009・DEC-021・DEC-098・DEC-103・DEC-106・DEC-107、Q-02、M-007・M-008（と原表の行 SRC-X01-0008・0009、SRC-X02-0008・0009・0011）、ND-07〜ND-09、IFD-25・33・34、H-007。
- `intent.md`（第9版）の体験 9〜10、設計規約、交換性・デバッグ性の受入条件。
- 上流のページ（2026-10-17）: GLIM（README・docs・config_ros.json・tags）、lidar_localization_ros2（README・docs・CHANGELOG）、hdl_localization、FAST_LIO、KISS-ICP、small_gicp、emcl2_ros2、pointcloud_to_laserscan。手元の `research/upstream_jazzy/nav2_bringup/params/nav2_params.yaml`（AMCL の設定）。
  - 読めなかったもの: docs.nav2.org の設定のページ（404）、small_gicp_relocalization（404）、glim_ros2 のソース（未取得）。

## 1. 人の指示（DEC-109 に原文）

「地面を推定する必要はあるのか？また、一旦mapcreatorの現在の改良は置いておいて、別の部分の改良に回せないかな？自己位置推定の方式の選定に進みたい。」

## 2. したこと

- 地面の推定の要否に答えた（`design/proposals/localization_selection.md` §1）。地面の推定が要るかは、自己位置推定の方式で決まる。
  - 3D 照合方式: 自己位置推定に地面の推定は要らない。Nav2 の 2D 地図は「軌跡の高さ − 1.18 m」を基準にした帯で足りる見込み。
  - 2D 方式: 地図全体で正確な地面の推定が要る。
  - 走行中の障害物（ND-09）の地面の除去は、どちらでも別に要る。
- 選定の提案を置いた（同 §2〜§8）: 正本からの要求、候補 7 件の上流の事実、構成の案、評価の計画、承認事項。
  - 推奨: 案 A（3D 照合）。odom→base_link は GLIM を odometry だけで、map→odom は lidar_localization_ros2 の NDT_OMP。
  - 比較: 案 B（Nav2 AMCL ＋ pointcloud_to_laserscan）。
  - 候補から外したもの: hdl_localization は ROS 1 だけ。FAST_LIO は ROS 2 版の Jazzy が未確認。
- REV-051 を適用した:
  - 第27便の解析を証拠として登録（FILE-EVENING-MAPS-ROSBAG）
  - 人の指示を記録（DEC-109、原文）
  - DEC-021 の備考に提案の参照を追記
  - DEC-107・DEC-098 の備考に「DEC-109 により保留」を追記（未回答のまま）

## 3. 自律判断した変更とその理由

- 提案の文書（`proposals/`）と判断台帳の記録（REV-051）だけ。DEC-106 の範囲（計画・分析・記録）。
- 正本の構成要素（node・IF・設定）は変えていない。実装・設定は変えていない。
- DEC-021 は「AI の技術選定」として人の承認待ちから外されていた（ゲート3）。ただし、方式は自己位置推定の振る舞いを変える。分類に迷うものは承認に回す（CLAUDE.md 1.2）ので、承認事項として示した。

## 4. 承認事項・実測待ち（提案 §8）

1. 案 A を第一候補として評価に進めてよいか（案 B も比べる）。
2. intent の「Navigation に関しては、なるべく Nav2 に機能を持たせ」の読み。案 A は Nav2 の AMCL ではなく外部の推定器を使う。AI は、正本がすでに ND-07 を Nav2 と別に設計しているので、規約の範囲内と読む。
3. 評価のため、VM の別のワークスペースに候補を build し、rosbag を VM に写してよいか。
4. 合格の基準の値（AI の案: 位置の誤差の 95 % 点 0.3 m 以内、発散なし、誤差 0.5 m 超で不良を出す）。
5. 次の実機試験で、同じ経路を 2 回（地図作成と、rosbag の記録だけ）走るか。

判断台帳への承認事項としての登録は、人の回答の後に行う（今は DEC-021 の備考で参照するだけ）。実測待ちは前から変わらない（DEC-105 など）。

## 5. 実行した検査（コマンド、対象、結果）

- `design/.venv/bin/python design/tools/apply_revision.py REV-051`: 成功（added_files: FILE-EVENING-MAPS-ROSBAG）。
- `design/.venv/bin/python design/tools/run_checks.py`（作業ツリー。6b86d92 ＋ 未コミットの第27・28便の記録 ＋ 人の編集中の drawio）: **終了コード 1**。
  - 不合格は 3 つで、原因はどれも同じ。人が 2026-10-17 02:25 に編集した移行の原資料 `design/docs/SystemArchitecture.drawio` の SHA-256 が baseline と違う（c958ce2f… ≠ f185b6c7…）。
    - input_integrity: 76 件中 drawio の 1 件だけ不一致
    - migration_validator: 3 件とも drawio
    - migration_tests: test_real_model の 1 件
  - 合格: generate_params、intent_identity、design_check（17 ルール。違反 0、未判定は DR-04 5・DR-05 2・DR-10 2・DR-11 59 で前と同じ）。
  - 人のファイルは触っていない。原資料を変えるなら、移行の扱い（新版としての記録か、変更の取り消し）は人の判断になる。
- 未実行: 単体試験（コードを変えていない）、候補の build と rosbag での評価（承認待ち。VM が止まっていて、外付けも今は外れている）。

## 6. 残るリスク

- 候補の事実は README と docs から。ソースは読んでいない。特に、GLIM を odometry だけで動かしたときに map→odom の TF を出すか（照合器と重なるか）が未確認。
- lidar_localization_ros2 は保守者が 1 人で、更新が速い（v1.2.0 が 2026-07、v1.3.0 が 2026-10）。版の固定が要る。
- 評価に使える rosbag は、同じ走行の地図との組み合わせだけ（楽観的）。別の走行の地図での評価は、二つの走行が同じ場所かを確かめてから（外付け待ち）。
- 第27便の修正方針の候補（IMU と LiDAR の回転、LAN のリンク断、recorder、GLIM の異常終了の検出、二重起動の防止の x86 機への反映）は、判断台帳に未登録のまま。

## 7. 更新した生成物

- REV-051 の適用で model.yaml。
- run_checks.py の出力: `reports/input_integrity.json`・`migration_validator.txt`・`migration_tests.txt`・`design_check.*` ほか。drawio の不一致が記録されている。

## 8. 次に進められる作業と止まっている作業

- 進められる（承認に依存しない分析）:
  - glim_ros2 のソースで TF の出し方を確かめる
  - 上流の候補の版を調べて、評価の手順書を書く
  - rosbag から評価用の点群地図を分析用に作る（外付けのつなぎ直しの後）
- 止まっている:
  - 候補の build と評価（承認 3）
  - 方式の採用（承認 1・2）
  - map_creator の改良（DEC-109 で保留）
  - 全検査の終了コード 0（人の drawio の扱い待ち）

## 9. 追加: Cartographer の検討（REV-052）

人の指示（DEC-110 に原文）: 「googleのcartographerも検討してほしい。」

確かめたこと（2026-10-17、上流のページ。出典は提案 §7）:
- 保守:
  - 上流の README に「Cartographer is no longer actively maintained」。最後の版は cartographer 2.0.0（2021-03-11）、cartographer_ros 1.0.0（2018）。
  - ROS 2 は ros2/cartographer・ros2/cartographer_ros の fork（ros2 ブランチ）から Jazzy のバイナリ（2.0.9004・2.0.9003）が出ている。上流の README はこの fork を「limited capacity」で保守と書く。
- 機能:
  - 自己位置推定（pure localization）は、自身の地図（.pbstream）を読んで動く。外部の点群地図（PCD）を読む方法は文書にない。
  - 3D は IMU が必須。
  - map→odom だけを出して odom→base_link を他に任せる設定がある（published_frame = odom）。
  - 初期姿勢は start_trajectory サービス。大域の再初期化の設定がある。
  - 推定の品質を出す専用の出力はない（metrics・ログ・score）。
- 点の時刻:
  - Cartographer は `time`（float32、header.stamp からの相対秒）だけを読む。最後の点の時刻が最大でないと CHECK で process が止まる。
  - Hesai のドライバは `timestamp`（float64、絶対時刻。rosbag で確認済み）。

提案の更新（`proposals/localization_selection.md`）:
- §3 の表に Cartographer を加えた。§4 に案 C（C1: 地図作成も Cartographer、C2: GLIM の地図と二重。C2 は勧めない）を加えた。§6 の評価の表に C1 を任意で加えた。§8 に承認 6 を加えた。
- AI の評価: 技術的には成り立つが、Gouda では地図作成の置き換え・保守の停止・品質の出力がない点で案 A より不利。第一候補にはしない。評価に加えるかは人の判断。

検査:
- `apply_revision.py REV-052`: 成功。
- `run_checks.py`: 終了コード 1。原因は前と同じ、人が編集中の `design/docs/SystemArchitecture.drawio` だけ（input_integrity の不一致 1 件、migration_validator、migration_tests の 1 件）。design_check は違反 0、未判定は DR-04 5・DR-05 2・DR-10 2・DR-11 59。

## 10. 追加: LeGO-LOAM と Autoware の ndt_matching の検討（REV-053）

人の指示（DEC-111 に原文）: 「https://github.com/RobustFieldAutonomyLab/LeGO-LOAM／autowareのndt_matching,／も検討をしてほしい」（／は原文の改行）

確かめたこと（2026-10-17、上流のページ。出典は提案 §7）:
- **LeGO-LOAM:**
  - ROS 1 だけ（indigo・kinetic・melodic）。最後の更新は 2020-07-02。作者は後継の LIO-SAM を案内している。
  - odometry と地図作成の機能で、保存地図での自己位置推定はない。loop closure は簡易で既定は無効。
  - 水平に置いた VLP-16 向けに最適化と明記。センサーの段数などはコンパイル時の定数。9 軸の IMU が任意。
  - ROS 2 への移植 LeGO-LOAM-SR は Dashing で試験、最後の更新は 2020-09、IMU を取り除いてある。LeGO-LOAM-BOR は ROS 1 の整理版で、保守の終了を明記。
- **Autoware.AI の ndt_matching:** ROS 1。Autoware.AI は 2022 年末で終了し、リポジトリは 2023-03-10 に archive された。
- **後継の Autoware Core（autoware_core リポジトリ）:**
  - autoware_ndt_scan_matcher（v1.10.0、Apache-2.0 と BSD、TIER IV の保守者 4 人、autoware_* の依存が 12）
    - 入力は点群と EKF の姿勢。出力は ndt_pose_with_covariance、豊富な score と diagnostics。
    - Monte Carlo で初期姿勢を探すサービスがある。地図は PCD（1 つか 20 m 格子）。
  - autoware_ekf_localizer: NDT の姿勢と速度を融合し、map→base_link の TF を出す。
  - Autoware の予定では Jazzy の完全対応が 2026-04。このパッケージの Jazzy での build は未確認。

提案の更新:
- §3 の表に 3 件を加えた。§4 に案 A3（GLIM の odometry ＋ Autoware Core の NDT と EKF）と、LeGO-LOAM・ndt_matching を外す理由を書いた。§6 の評価の表に A3 を加えた。§8 に承認 7 を加えた。
- AI の評価:
  - A3 は品質の出力が最も豊富。ただし、TF の形（map→base_link）を正本の分担（map→odom、odom→base_link）に合わせる中継と、速度の中継の二つの独自の node が要り、依存も重い。
  - 同じ NDT の lidar_localization_ros2 と比べる価値があるので、評価に加えることを推奨した。第一候補は案 A のまま。

検査:
- `apply_revision.py REV-053`: 成功。
- `run_checks.py`: 終了コード 1。原因は前と同じ、人が編集中の `design/docs/SystemArchitecture.drawio` だけ。design_check は違反 0、未判定は DR-04 5・DR-05 2・DR-10 2・DR-11 59。

## 11. 人の回答「案 A・A3・B のみ」と提案の第2版（REV-054）

人の指示（DEC-112 に原文）: 「kiss-icpは以前の評価試験で目標性能を出せなかった為、検討から外す。案A, A3, Bのみを検討せよ。rosbagをVMに移すのは一旦するな。」

- KISS-ICP の以前の評価試験の結果の記録は、このリポジトリにない。ワークスペースの `Sensors/emc270_xt32_icr`（KISS-ICP を使う回転中心の推定）に手順だけがある。外す理由は人の判断として記録した。
- 3 案の未確認の点を上流のソースで確かめた（出典は提案 §8）:
  - **GLIM（glim_ros2・glim）:**
    - TF と odometry の topic は拡張モジュール librviz_viewer.so が出す。TF を止める設定は imu→lidar だけ。
    - map→odom は、global mapping が補正を更新しない限り単位行列（TrajectoryManager の初期値）。
    - frame の名前は設定で変えられる。
    - `~/odom` の子の frame は IMU で、角速度はない。
  - **lidar_localization_ros2:**
    - Nav2 用の設定では odom→base_link を TF から取り、map→odom を出す。
    - failure_category は診断だけ。棄却の間は map→odom を最後の値で止める。
    - ソースからの build だけ。
  - **Autoware Core:**
    - ekf_localizer は map→base_link を出し、止める設定はない（tf_rate だけ）。
    - ndt_scan_matcher と ekf_localizer は Jazzy に 1.10.0 が公開されている（2026-10-15）。CI は humble・jazzy。
  - **Nav2 AMCL（jazzy、1.3.13）:**
    - 入力は LaserScan だけで、LGPL-2.1-or-later。
    - 品質は amcl_pose の共分散と粒子の重みだけ。
- 提案を第2版に書き直した（第1版の控えは scratchpad。リポジトリには未コミットだったため履歴なし）:
  - 3 案に共通の GLIM の odometry の設計の案: frame の名前の付け替えで TF の重なりを避ける、publish_imu2lidar は false、odometry の中継の node。
  - 各案の事実と当てはめ、要求との照合の表、rosbag を VM に移さない評価の計画（机上 → 外付けを Mac で読む分析 → 場所未定の実評価）、推奨、承認事項 6 点、外した候補の付録。
- 推奨は変えない: 第一候補は A、A3 と B を比べて評価の結果で決める。

検査:
- `apply_revision.py REV-054`: 成功。
- `run_checks.py`: 終了コード 1。原因は前と同じ、人が編集中の `design/docs/SystemArchitecture.drawio` だけ。design_check は違反 0、未判定は DR-04 5・DR-05 2・DR-10 2・DR-11 59。

次に進められる作業:
- 外付けがつながれば、提案 §6 の 2 の分析（案 B の 2D スキャンの成り立ち、地図の照合の弱い区間、二つの走行が同じ場所か）。
- 止まっている:
  - 実際のパッケージでの評価（場所が未定。rosbag は VM に移さない）
  - 方式の採用（承認待ち）

## 12. intent.md 第10版の記録（REV-055）

- 機械比較で検出した。人が 2026-10-17 03:51 に、リポジトリ側の `design/intent.md` を編集していた（チャットでの言及なし）。
  - 差分は 82 行の置換だけ（106 行のまま）。
  - 文末に「OSSとして公開されており使用実績の豊富なものについては、Nav2に追加しても良い。」が加わった。
  - ワークスペース直下の `design/intent.md` は第6版のまま（正本はリポジトリ側）。
- AI は intent.md を編集していない。記録として次を行った:
  - 写し `baselines/intent_history/intent_v10_4bc97d43f757.md`（一字も変えない複製）
  - 第10版の登録（AR-010、FILE-INTENT-V10）
  - 82 行の要求の置換（RQ-I057 → RQ-I083、照合 C-026、RQ-I057 は superseded）
  - 人の編集の原文の記録（DEC-113）
  - RQ-I057 を根拠にしていた照合 C-004・C-012 の根拠を、RQ-I083 に替えた（前例 REV-011 と同じ。置換後の行に前段の同じ文がある）。
- 修正の記録（1.6、分類: 実装＝変更セットの誤り）:
  - 最初の REV-055 は、RQ-I057 の superseded と C-004・C-012 の根拠の置き換えが抜けていた。
  - 検査で「置き換えた要求が有効のまま」（移行の検査）と DR-01 の違反 2 件が出た。
  - model.yaml・schema.json・generated を最後のコミット（6b86d92）の状態に戻し、REV-051〜055 を順に適用し直した。
  - 直す前の model.yaml の控えは scratchpad にある。
- 提案（`proposals/localization_selection.md`）に第10版を反映した:
  - 要求の表を更新した。
  - 承認事項 2 を「案 A・A3 が『OSS として公開され使用実績の豊富なもの』に当たるかの判断」に変え、判断の材料を付けた。

検査:
- `apply_revision.py REV-051`〜`REV-055`（作り直し後）: すべて成功。
- `run_checks.py`: 終了コード 1。原因は人が編集中の `design/docs/SystemArchitecture.drawio` だけ（移行の検査 3 件と migration_tests の 1 件。input_integrity の不一致 1 件）。
  - design_check は違反 0、未判定は DR-04 5・DR-05 2・DR-10 2・DR-11 59。
  - intent_identity は合格。
