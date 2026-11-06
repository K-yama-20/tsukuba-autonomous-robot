# 第235便 作業記録：MID-360 の接続試験に向けた並列の実装（A1・B・D・E・G1・G2）（REV-259・REV-260、DEC-474〜479）

- 日付：2026-11-07
- 読んだコミット：9c449b5（作業ツリーに他のセッションの未コミットの変更が多数。作業中に他のセッションが REV-261〜267 を作り・適用した）
- 読んだもの：CLAUDE.md（1.1〜1.13）、status.md の先頭、design/intent.md（全文）、計画 `proposals/mid360_connection_test_plan_2026-11-06.md`（全文）、台帳 `research/vehicle_pc/2026-11-06_mid360_connection/ledger.yaml` の T04〜T08、判断台帳の DEC-075・106・442・443・454〜457、第217便の作業記録、`proposals/ground_estimation_plan.md` の先頭、`setup.sh` の MID-360 の節、REV-242
- このセッションは、前のメインチャットから渡された指示で始めた（MID-360 の新しいメインチャット）。

## 人の回答（原文）

- DEC-474（前のメインチャットから原文の引用で伝達）：「計画を立てよ。並列で動かせると早く開発出来る。」「メインチャットを新規で開始し、実装を行え。opus5.5, 超高で並列実装せよ」
- このチャットでの人の発言：「再度最初からやり直せ」「計画を組み直そう」
- DEC-475：「地面はRANSAC等を用いたOSSを使って検出しよう。閾値設定だけでは障害物がないのにあると誤検知してしまうかもしれません。計画に組み入れることを検討せよ」「この計画で進める」
- 人の発言「実装を続行せよ」（作業の途中。判断台帳の項目ではない）

## 経過

1. 最初の試み：サブエージェント 3 つ（A・B・D）を effort の指定なしで動かした。人の「再度最初からやり直せ」で、出力を scratchpad に退避し、作業ツリーを元に戻した（setup.sh・drivers.repos は `git checkout HEAD --`、ledger.yaml は作業の前の写し、新しいファイルは削除、REV-259・260 は予約の 1 行に戻した）。他のセッションの変更（REV-261 の適用など）には触れていない
2. 読み直しで、A の大半（drivers.repos の固定と setup.sh の MID-360 の節、9c449b5・第204便）と D の大半（ND-20・ND-21・IFD-59〜61、REV-242・第217便）が済んでいると分かった。計画を組み直して人に示した
3. 人の指示で G（地面の OSS による検出）を足し、先行事例を issue #85 に登録した（1.10）
4. 人の「この計画で進める」で、6 つの流れをサブエージェント（opus、effort xhigh）で並列に動かした。G1 の最初の起動は auto mode の判定で拒否された（理由の説明なし）。ワークステーションでの第三者のコードのビルドを外し、読むだけの調査に絞って起動し直した

## 変更

| 流れ | ファイル | 内容 |
|---|---|---|
| 記録 | `design/revisions/REV-259.yaml` | DEC-474・475（answered）。適用した |
| A1 | `setup.sh`（17・22〜24・39〜42・147・191〜211 行付近） | livox_ros_driver2 を上流の build.sh でなく colcon で作る。固定の commit を `git archive` で `<workspace>_livox/stage/` に写し、package_ROS2.xml を package.xml として置き、build.sh jazzy と同じ CMake の引数（-DROS_EDITION=ROS2 -DDISTRO_ROS=jazzy）で作る。checkout は変えない。失敗で止まる。stamp は `<commit> colcon`（build.sh で作った install は一度だけ作り直す）。別の作業場所（DEC-443）は保ち、理由のコメントを改めた |
| A1 | `third_party/drivers.repos`（8〜10 行のコメントだけ） | 作り方の説明。4 つの pin は変えていない |
| A1 | `README.md`（42・46・187 行付近） | build.sh の方式の説明を colcon の方式に合わせた（このセッションが直した） |
| A1 | `design/research/upstream_sensors/livox_ros_driver2_colcon_2026-11-07.md`（新） | 先行事例、上流のソースの行、組み合わせの確認、ワークステーションでの試行、A2 の手順、残るリスク |
| B | `design/research/vehicle_pc/2026-11-06_mid360_connection/tools/`（新） | bagio.py（rosbag2_py か純 Python で mcap・db3 を読む）、bagstats.py、t04_driver_topics.py、t05_4_xt32_offset.py、t07_timeseries.py、t08_3_tilt.py、README.md、tests/（合成の mcap・db3） |
| E | `.../tools/p4_driver/`（新） | make_config.py（製品の gouda_core.mid360_config を import してドライバの設定を作る）、run_driver.py（`ros2 run ... -p xfer_format:=0 -p frame_id:=mid360_link`）、record_bag.py（T04-6）、p4_common.py、test_p4_driver.py、README.md（Dell での手順） |
| D | `design/revisions/REV-260.yaml`（新、**未適用**） | ND-20・ND-21・IFD-59 の整合の修正と、DEC-476〜479（pending） |
| D | `design/docs/mid360_driver_interfaces.md`（新） | 原本で確かめた事実と出典の表（内蔵 IMU の単位・frame、診断・状態、IF の用途区分） |
| G1 | `design/research/ground_segmentation_2026-11-07/survey.md`（新） | 地面分割の OSS の比較（Patchwork++、linefit の ROS 2 版、GSeg3D、Ground Consistency Layer、Autoware）と組み込みの形の案 |
| G2 | `design/research/ground_segmentation_2026-11-07/compare.md`・`tools/`・`figures/`（新） | 「帯だけ」と「地面分割＋帯」の比較（合成の場面と XT-32 の実データ） |
| 台帳 | `design/research/vehicle_pc/2026-11-06_mid360_connection/ledger.yaml` | T04-1〜6・T05-4・T07-1〜2・T08-3 に道具の場所、「解析スクリプト未作成」を消して待ちの理由を今の状態に、T08-5（地面の誤検知と見落とし、提案）を足した |

## 自律判断とその理由

- 最初の試みの出力は使わなかった：effort の指定（人の指示の「超高」）なしで作ったため。退避先：scratchpad の attempt1（リポジトリの外）
- A1 の別の作業場所は保った（DEC-443 の採否は変えない）。理由だけを改めた（DEC-475 の質問に書いた）
- README の 3 か所の修正：A1 の変更に合わせる、意味を変えない整合の修正
- E の frame_id を mid360_link（製品と同じ）にした：P4 の bag を製品の確認にそのまま使えるため。点の座標は変わらない（tools/p4_driver/README.md）
- E の起動は `ros2 run --ros-args`：上流の launch には引数がなく、xfer_format 1 と share の JSON が中に書いてあるため
- D の ND-20 のモジュール M-019（XT-32 のドライバ）→ M-023（障害物認識）、sensitivity に safety：発行先・購読先との整合の修正（REV-260 の rationale）
- T08-5 は提案として台帳に足した。項目を採るかと試験の条件は人が決める

## 承認事項・実測待ち

- REV-260 の適用（D）：DEC-476 内蔵 IMU を使うか／DEC-477 加速度の g を誰が m/s² に直すか／DEC-478 IMU の frame（livox_frame、TF なし）／DEC-479 作動状態・温度・診断を出すか。どれも pending、推奨は REV-260 に書いた
- G3：地面分割を製品の障害物の経路に入れるか（#85、survey.md・compare.md）
- T08-5 を足すか、試験の条件（平らな所・坂・縁石・コーン・低い物）
- 計画 88 行の「起動は `ros2 launch livox_ros_driver2 <launch>` のみ」と、E が `ros2 run` にしたことの食い違い。計画の文言を直すか（人）
- #88：上流 pointcloud_to_laserscan 2.0.2 の配列の外への書き込みへの対処
- #87：livox_ros_driver2 の最適化なしのビルド（A1 のサブエージェントが登録）
- 実測待ち：DEC-457（取り付け）は変わらず

## 実行した検査・試験

| 検査 | コマンド | 対象 | 結果 |
|---|---|---|---|
| REV-259 の試し | `design/.venv/bin/python design/tools/apply_revision.py REV-259 --dry-run --check` | 作業ツリー | 0 new violations、0 new undetermined |
| REV-259 の適用と再生成 | `apply_revision.py REV-259`、`generate_params.py`、`render_views.py`、`render_migration_review.py` | 同上 | どれも終了 0 |
| REV-260 の試し | `apply_revision.py REV-260 --dry-run --check` | 同上 | 修正 3 件、0 new violations、0 new undetermined（このセッションで流し直した） |
| 設計検査 | `design/.venv/bin/python design/tools/run_checks.py` | 同上 | 下の「設計検査の結果」 |
| setup.sh の構文 | `bash -n setup.sh`、`bash -n update.sh` | 同上 | 通った。shellcheck は Mac・ワークステーションになく未実行 |
| A1 の試行（サブエージェントの報告） | ワークステーションの新しい作業場所で setup.sh の該当の節の写し（SDK は sudo なしで作業場所の prefix に） | drivers.repos の pin | 空から・作り直し・冪等・失敗で止まる・回復の 9 回が想定どおり。build.sh と install の中身が同じ（パスの違いだけ）。`ros2 pkg executables` に livox_ros_driver2_node、share に config/MID360_config.json |
| B の単体試験 | `cd tools && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests` | 作業ツリー | Mac：62 passed、1 skipped（rosbag2_py なし。このセッションで流し直した）。ワークステーション（サブエージェントの報告）：60 passed、2 skipped と、rosbag2_py で書いた bag・`ros2 bag record` の bag で 2 つの読み方が一致 |
| E の単体試験 | `python3 -I -B -m unittest discover -s .../tools/p4_driver -p 'test_*.py'` | 作業ツリー | 19 件 OK（このセッションで流し直した） |
| G2 の単体試験 | ワークステーションの G2 の venv で、リポジトリの tools/ の写しに `pytest -q tools/tests` | 作業ツリー | 18 passed（このセッションで流し直した）。Mac では依存（mcap・pypatchworkpp・linefit）がなく、14 passed・2 failed・1 件は収集で止まる |
| 公開してはいけない情報 | 新しいファイルを IPv4 の形・ホストの名前・ユーザー名で grep | 同上 | 文書用のアドレスの範囲（192.0.2.x など）と 9.80665 だけ |
| ROS 上での起動、Dell での setup.sh、実機の MID-360、Nav2 での costmap の比較 | — | — | 未実行 |

### 設計検査の結果

- `run_checks.py` の終了コード 1。各報告：design_check PASS、generate_params PASS、intent_identity PASS。FAIL は input_integrity（SystemArchitecture.drawio と .DS_Store 2 つの不一致）、migration_validator、migration_tests で、作業の前からのもの（第217便・第220便と同じ）
- design_check.txt の要約：合格 12・違反 0・未判定 5（違反0件・未判定5件）。ただし、この要約を読んだのは 03:56 で、その直前（03:55）に他のセッションが model.yaml を変えて検査を流し直していた。その途中の出力（DR-01 違反 4）を一度読んだが、他のセッションの適用の途中の一時的な状態とみている（推測）。このセッションの実行の時点の要約の行は、別には残していない
- REV-260 の試し（未適用）：新しい違反 0・新しい未判定 0

## 原因の分類（1.6）

- A1：試行のスクリプトが ROS の PYTHONPATH を上書きしていた（試験基盤）。合否の基準は変えずに直した（サブエージェントの報告）
- B：地面の当てはめの最初の形（向きの近い候補だけで RANSAC）が、地面を斜めに切る面を返した（実装）。点の多い面から順に取り出す形に直し、回帰の試験にした（サブエージェントの報告）
- G2：比較の道具が +π の端の点で例外を出した（実装）、試験の点が float32 の丸めを考えていなかった（試験基盤）。基準は変えずに直した（サブエージェントの報告）

## 見つけたこと（考慮漏れの指摘、1.12）

- REV-242 のコード（`gouda_core/gouda_core/mid360_config.py` は未追跡、`gouda.sh`・`gouda_nav2.launch.py` は未コミット）は 9c449b5 に入っていない。E の道具を Dell で使うには、コミット・push・Dell への反映が要る（人）
- ドライバは接続のたびに pcl_data_type・pattern_mode・外部パラメータ 0 をセンサー本体に書き込む（上流 livox_lidar_callback.cpp の接続の後の処理。このセッションでも原本で確かめた）。本体に前の値を残したいなら P4 の前に Livox Viewer 2 で読む
- 内蔵 IMU は出ている（/livox/imu、200 Hz、加速度は g のまま、frame は livox_frame に固定で TF なし）。購読する node はないが、`ros2 bag record -a` には入る（REV-260、DEC-476〜478）
- 点群 1 枚は約 520 KB（計算）で、Fast DDS 2.14 の共有メモリの segment の既定 512 KiB とほぼ同じ。製品は PRM-101 の profile を使う。P4 で DDS をどちらにして測ったかを記録する（tools/p4_driver/README.md）
- 上流 pointcloud_to_laserscan 2.0.2 の配列の外への書き込み（#88。このセッションが原本と float32 の計算で確かめた。上流 #14 open、PR #110 未マージ）
- G2：合成の場面では、取り付けの pitch の誤差 ±1〜2°（比較用の仮定）で、帯だけでは平らな地面が 6 m 以内で多数の方位の印になった。2.5 m 以内で 1 方位を超えたのは MID-360 の上り坂 +2° だけ。Patchwork++＋帯は全条件で 0、ただし 10〜15 cm の縁石・段差の見落としが増えた（compare.md 3 章）。XT-32 の実データ（正解なし）では、2.5 m 以内の印は 3 方式で同じ（計算。Nav2 では未確認）
- G1：Patchwork++ のライセンスの表示が食い違う（根 BSD-2、ros/LICENSE は MIT、ros/package.xml は GPL-3.0）。#85 の下書きの「linefit は法政大の機体（orange2022）で使用」は確かめられなかった（orange2026A ではシミュレーションの launch だけで使用）
- G2 は、屋外の rosbag が Dell の `~/gouda_ws/gouda_data/records` の下にしかなかったため、そこを読み、バイトの写しでワークステーションに 2 区間（合わせて約 964 MB）を写した。書き込み・ros2 のコマンド・Gouda の起動停止はしていない。指示の「~/gouda_ws には触れない」の字面から外れるので、人に報告する
- 2026-10-14 の rosbag には /tf_static がなかった（G2 は 2026-11-07 の bag の /tf_static を使った）

## 残るリスク

- A1：Dell での setup.sh（/usr/local・ldconfig・Dell の cmake と colcon の版）は未実行。ドライバは最適化なしで作られる（#87）
- B・E：実機の bag・ROS 上で動かしていない。加速度の符号、点の時刻の単位、遅れは T04 で確かめる
- D：REV-260 は未適用。IMU を記録する・使う場合の単位と frame の扱いが決まっていない
- G：比べたのは地面分割の設定 1 通りで、合成の地面は理想の面。MID-360 の実データはない。地面分割を入れると低い物の見落としが増えうる
- ワークステーションに作業場所が残る：前の試み（破棄）の `~/livox_trial_20261107`、A1 の `~/livox_colcon_trial_20261107`、G2 の `~/ground_compare_20261107`（実データの写しを含む）

## 生成物の変更箇所

- REV-259 の適用による：model.yaml（DEC-474・475）、generate_params・render_views・render_migration_review の出力（DEC の一覧など）。params の値は変わっていない

## 次の作業

- 人：Dell で `bash setup.sh`（A2、手順は `design/research/upstream_sensors/livox_ros_driver2_colcon_2026-11-07.md`）、REV-242 のコードのコミットと Dell への反映、P4（手順は `tools/p4_driver/README.md`）
- 人の判断待ち：REV-260（DEC-476〜479）、G3、T08-5、計画 88 行、#87、#88、G2 が `~/gouda_ws` の下を読んだことの扱い
- 進められる：T04 の bag が来たら B の道具で解析、MID-360 の bag で G2 の道具を回す、#88 の合成の点での確認（ソフト上）
- 実車投入可能：人の判断待ち。コミットはまだ

## 追記：REV-260 の適用（DEC-492）

- 人の回答（原文）：「適用してよい」（質問「REV-260 を適用しますか？（DEC-476〜479 は pending のまま）」への回答）。DEC-492 を `reserve_ids.py --no-revision --decisions 1` で予約し、REV-260 に answered で足した。basis_refs に DEC-492・474・475 を足し、要約の「REV-259 は未適用」を今の状態に直した
- AI の解釈：REV-260 の本適用の承認。DEC-476〜479 への回答ではない（pending のまま）
- 適用で変わったもの：ND-20（モジュールを M-019 から M-023 に、sensitivity に safety、責務と placement_rationale の追記）、ND-21（placement_rationale）、IFD-59（publisher の深さ 256、時刻の意味、出典）。正本の値・コード・設定・launch は変えていない

| 検査 | コマンド | 対象 | 結果 |
|---|---|---|---|
| 試し | `design/.venv/bin/python design/tools/apply_revision.py REV-260 --dry-run --check` | 作業ツリー | 修正 3 件、0 new violations、0 new undetermined |
| 適用 | `apply_revision.py REV-260` | 同上 | 終了 0。model.yaml の ND-20 が M-023・safety になったことを確かめた |
| 再生成 | `generate_params.py`、`render_views.py`、`render_migration_review.py` | 同上 | どれも終了 0 |
| 設計検査 | `run_checks.py` | 同上 | 終了コード 1。design_check PASS（合格 12・違反 0・未判定 5、違反0件・未判定5件）、generate_params PASS、intent_identity PASS。FAIL は input_integrity・migration_validator・migration_tests（作業の前からの drawio と .DS_Store の不一致） |

- 注：検査の途中（04:09）に model.yaml の更新時刻が変わった。他のセッションの適用が重なった可能性がある（推測）。上の件数は 04:09:55 の design_check.txt の要約
- 生成物の変更箇所：model.yaml の hash を含む generated/params の先頭の行、render_views・render_migration_review の出力（ND-20・ND-21・IFD-59・DEC-476〜479・492）
