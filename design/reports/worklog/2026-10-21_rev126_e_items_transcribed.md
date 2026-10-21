# 第97便: 分岐セッションの E 項目の回答（転記）の記録と、ND-07（案 A3）の設計の案（REV-126、DEC-200〜206、DEC-115）

## 読んだもの

- コミット：`4b44f75`（design/records-2026-10-21。PR #12 は未 merge）。分岐先が読んだのは `34bc9e0`（REV-120・121 の時点）。
- 人が貼った転記（E 項目の判断材料と人の回答）。CLAUDE.md 1 章、status.md、メモ（変更セットの手順、承認の前の実装の禁止）。
- 正本と提案：`proposals/localization_selection.md`、`proposals/stage56_navigation_localization_plan.md`、model.yaml の DEC-021・115・120〜124・134・171・181・194、ND-03・07・08・10、TR-05・07、IFD-18・25・33・34・52、PRM-18、D-13、SO-05、G-RECOVERY-COUNT、intent.md:15・16・41。
- 実装：`mode_manager_node.py`、`nav2_config.py`、`launch/gouda_nav2.launch.py`、`monitor_node.py`・`monitor_core.py`、`setup.sh`、評価の道具 `research/vehicle_pc/2026-10-17_localization_eval/`（run_eval_A3.sh、a3_init.py、eval_A3_ekf.param.yaml）。
- VM（ssh、読み取りだけ）：dpkg と apt-cache で Autoware の版、pcl_ros の node、`ros2 interface show nav2_msgs/action/NavigateThroughPoses`。

## 人の発言（原文、転記）

DEC-200〜202・DEC-115 の answer_verbatim に、転記の原文 1〜3 をそのまま記録した。転記の出所は分岐セッション（人がこのチャットに貼った）。分岐先での人の指示「メインのチャットで別の作業が進行中である為、今は何も変更を加えてはならない。後で指示します。」により、メインの作業（PR #12 まで）が終わってから着手した（人が貼ったことを着手の指示とした：引き継ぎ §3）。

## 記録したこと（REV-126）

- DEC-200（answered）：E-1。推定不能か Nav2 の失敗で一時停止し、原因を区別する。
- DEC-201（answered）：E-2。PRM-18 は 9999999 のまま、monitor で変え、次の走行から反映。
- DEC-202（answered）：E-4。setup.sh に A3 のパッケージを入れる（方針）。
- DEC-115（answered）：E-3。案 A3 を試す（試行の決定）。DEC-021 は pending のまま（最終の採用ではない）で、note に経緯を足した。
- DEC-203〜205（pending）：設計の案と実装の許可（提案 `proposals/nd07_a3_trial_design_2026-10-21.md`）。DEC-206（pending）：転記の解釈の確認（9999999 の読み、EKF の診断、工程 5-7 の後回し）。
- 解釈の追記：ND-07（名前を「案 A3 を試行中」に）、TR-07、PRM-18、G-RECOVERY-COUNT、Q-02。構成（ND-07 の部品、新しい IF・型・PRM）は正本に入れていない（DEC-203 の後）。

## 自律判断した変更とその理由

- 転記の作業の順序 3（ND-07 の構成を変更セットで正本に入れる）は、今回は提案の文書にとどめた。理由：構成の中に人が決める点（推定不能の判定の材料、recovery の回数の優先、setup.sh の版の扱い）があり、転記の前提と実装の食い違い（下）も見つかったので、正本に「案」として入れる前に人に示す方が戻しやすい。正本の構成は DEC-203 の後に別の変更セットで入れる。
- DEC の数は、承認と実装の許可を段ごとに分けた（DEC-106：許可は個別）。

## 確かめた事実（転記の前提との違い）

- Nav2 の設定と BT は gouda.sh start のときに一度だけ作る（`gouda_nav2.launch.py` が `nav2_config.write` を呼ぶ）。TR-05 では作り直さない。転記の「TR-05 で mode_manager が Nav2 の設定を作り直す時」とは違う。NavigateThroughPoses の goal に `string behavior_tree` がある（VM の Nav2 1.3.13）ので、走行ごとに BT を渡す案にした（DEC-204）。
- setup.sh は Nav2 をすでに入れている（DEC-121）。足すのは Autoware の 3 つ。
- VM の Autoware は 1.9.0（`ros-jazzy-autoware-ndt-scan-matcher 1.9.0-1noble.20260921.041620` など）。apt の一覧は 2026-10-06 のもの。pcl_ros 2.6.5 は Autoware の依存で入っていて、`filter_voxel_grid_node`・`filter_crop_box_node` がある。
- NavigateThroughPoses の feedback の `number_of_recoveries` は int16。
- DEC-134（pending、発散で停止して再初期化、TR-13 の具体化）と DEC-200 は食い違わない（AI の読み。提案 §3.2）。

## 実行した検査

- `design/.venv/bin/python design/tools/apply_revision.py REV-126 --dry-run --check`（4b44f75 の作業ツリー）：新しい違反 0、新しい未判定 0。
- 本適用の後、`render_views.py`・`generate_params.py`・`render_migration_review.py`（いずれも終了コード 0）、`run_checks.py`（終了コード 1）。
  - 設計整合性（`reports/design_check.txt` の要約行）：`{"合格": 12, "違反": 0, "未判定": 5} 違反0件・未判定5件`。前と同じ。
  - 入力の完全性：不一致 3 件（人の drawio、.DS_Store 2 つ）。前と同じ。
  - 検査器の試験：83 件中 1 件不合格（test_real_model、同じ原因）。
- gouda_core の単体試験：未実行（コードは変えていない）。

## 修正

- なし。

## 更新した生成物

- `generated/params/*.yaml`・`index.json`：元の正本のハッシュの行だけが変わった（値は同じ。`git diff` で確認）。
- `generated/pending_classification.md`、`gate3_package.md`、`lower_design_r2.md`、`review_r3.md`、`intent_open_items.yaml`、`reports/model_diff_rev-126.md`、検査の報告。

## 承認待ち・実測待ち

- DEC-203（ND-07 の構成と推定不能の経路、段 2〜4 の実装）、DEC-204（recovery の回数のタブ、段 5）、DEC-205（setup.sh、段 1）、DEC-206（解釈の確認）。
- 実測：推定不能の判定のしきい値（新しい PRM、tbd）、地図の格子の間引き（tbd）。

## 残るリスク

- 推定不能の判定は、誤った姿勢を「正常」とみなすことを防げない（評価の 0.546 m の例。EKF の診断がそのとき出ていたかは未確認）。
- ROS の apt に Autoware 1.10 が来ると、1.9.0 を x86 機に入れられない（推測を含む）。
- 一時停止は PC の出力の中立化で、車体の停止の保証ではない。

## 次の作業

- 進められる：人の回答の後、DEC-203 の構成を変更セットで正本に入れる。x86 機の apt の Autoware の版の確認（人か、x86 機に入れる時）。
- 止まっている：ND-07 の実装（DEC-203）、setup.sh（DEC-205）、monitor のタブ（DEC-204）、2D 地図（DEC-107・TS-34）、実車試験。
- commit：未実行（人の指示なし）。手元は design/records-2026-10-21（PR #12 が開いている）。
