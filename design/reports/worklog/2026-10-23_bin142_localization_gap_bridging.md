# 作業記録 2026-10-23 第142便: 推定不能の間の補い方の調べと提案（REV-168、DEC-350〜354）

## 読んだもの

- 作業ツリー `31a6e1d9881459a62976bc042f9941063ece7eac` ＋ 未コミットの変更（第141便まで）。`design/reports/status.md`、`design/intent.md`（人の 15:08 の編集の版、SHA-256 9012e5f2…、第17版として未記録）、CLAUDE.md の共通ルール。
- 判断台帳: DEC-114・208・286・290〜293・305・306・334・340・342・345・346・349。PRM-82〜93・102・103、TR-07、TRB-004。最新の作業記録（第141便）。
- 提案: state_transition_redesign（§3）、competition_no_auto_pause、crowd_robust_localization、localization_selection（§6.1）。
- コード: `localization_core.py`、`global_localization_node.py`、`mode_manager_node.py:459-478`、`odometry_core.py`、`gouda_localization_a3.launch.py`、`nav2_config.py`。上流の写し（Nav2 1.3.13 `controller_server.cpp`・`costmap_2d_ros.cpp`）。
- 実車の記録: `research/vehicle_pc/2026-10-22_*`、`2026-10-14_x86_lidar_dropout.txt`、`2026-10-17_localization_eval/`。
- VM（読むだけ、ssh）: 上流の設定（ekf_localizer・ndt_scan_matcher 1.9.0）、パッケージの版、apt の候補、地図の dump 5 つ（odom_lidar・traj_lidar を scp で一時領域へ）。VM の Gouda・ファイルには触れていない。

## 1. 人の要望（原文、チャット）

「つくばチャレンジ用ロボット Gouda（リポジトリ tsukuba-autonomous-robot）で、自己位置推定が「推定不能」になった間を数理的な手法で補い、走行を続けられるかを、慎重に調査・比較して提案にまとめてほしい。実装はしない（DEC-106）。」
「人の要望（今回）：推定不能の間はフィルタなどの数理的な手法で補完して走行を続けたい。簡単な回帰式など適当な補完は失敗しうるし、カルマンフィルタのようにパラメータの調整が難しい手法は期待した性能が出ない可能性もあるので、慎重に調査すること。」
（依頼の全文は調べてほしいこと 1〜5 と出してほしいものを含む。チャットに残る。）

調べと記録の依頼として扱った。実装の許可（DEC-106）としては使っていない。

## 2. 行ったこと

- 提案 `design/proposals/localization_gap_bridging_2026-10-23.md` を作った（原因の区分、手法 (a)〜(f) の比較、戻し方、ずれの検出、推奨、評価の方法、承認事項）。
- GLIM の odometry のずれの下限を、地図の dump から見積もった（読むだけの解析）。証拠 `research/vehicle_pc/2026-10-23_glim_odom_drift/`（notes.txt・glim_odom_drift.py・glim_odom_drift_output.txt）。
- 上流のソース（autoware_core 1.9.0、glim・glim_ros2 1.2.2）と文献・apt の調べを、読むだけのエージェント 1 つに頼んだ。結果は提案 §12。私が自分で行を確かめたのは EKF の棄却と NDT の姿勢を出す条件だけ（提案 §12 の冒頭に明記）。
- 番号は reserve_ids.py で予約（REV-168、DEC-350〜354、第142便）。REV-168 を `--dry-run --check`（新しい違反 0・未判定 0）の後に適用。承認 DEC-350〜353、実測 DEC-354 を pending で登録。証拠のファイル 3 つを FILE-GLIM-ODOM-DRIFT-* として登録。

## 3. 分かったこと（要点。詳細と出典は提案）

- 事実: NDT は収束しないと姿勢を出さない（`ndt_scan_matcher_core.cpp:742`）。そのとき EKF は GLIM の速度で予測を続けるので、今の作りでも map→odom はほぼ一定（GLIM で進むのと近い）。
- 事実（私が確かめた）: EKF の棄却は 2 乗でない距離と `pose_gate_dist` 49.5 を比べる（`ekf_module.cpp:302-306`、`mahalanobis.cpp`）。設定の注（有意水準 10⁻¹⁰、2 乗の値）と違い、49.5σ まで棄却しない。誤って収束した NDT の姿勢を止める仕組みは実質ない。PRM-91 の説明「マハラノビス距離での棄却を含む」は実際にはほとんど起きない。
- 事実（エージェントの読み）: GLIM 1.2.2 は LiDAR の frame ごとにだけ odometry を出す。途切れの間は何も出さない。odometry の共分散は 0、劣化の指標はない。
- 記録: GLIM の odometry のずれの下限は 50 m あたり p95 0.06〜1.18 %、最大 0.65 m（基準は真値でない）。止まっている間はずれない。LiDAR の途切れは 2.7〜4.2 s。人混み・段差・走行中の推定の失敗の記録はない。
- 「frame gap」の文言は GLIM 1.2.2・Gouda のコードに見つからない。2026-10-14 の記録の行をどの部品が出したかは未確認（途切れの長さとカーネルのリンク断の時刻が合うことは変わらない）。
- 推奨: 新しいフィルタは足さず、GLIM で進む＋距離・時間の予算＋止まって待つ＋止まったまま再初期化、を原因の区分ごとに使い分ける。戻すときは確かめてから寄せる。値はすべて rosbag の再生に故障を入れて測る。

## 4. 自律判断した変更とその理由

- 提案・証拠・台帳の記録だけ（DEC-106 の範囲）。コード・設定・パラメータは変えていない。
- 地図の dump を VM から一時領域へ写した（読むだけ。VM の元のファイルは変えていない）。

## 5. 承認事項と実測待ち

- 承認待ち: DEC-350（方針）、DEC-351（回復の判定と戻し方）、DEC-352（ずれへの備え）、DEC-353（再初期化）。前提は DEC-305・342（pending）。
- 実測待ち: DEC-354（rosbag の再生の評価。外付けの接続と新しい記録は人の作業）。関係: DEC-346・293・349・286。
- 同じ時間に別のセッションが REV-169（第143便、DEC-355〜360）を適用した。DEC-356（探索の範囲を段階的に広げる）は DEC-353 の再初期化の探索と、DEC-358（PRM-92 を暫定 0.7 m）は DEC-352 の「EKF の共分散をずれの目安に使わない」と関係する。台帳の上で互いを書き換えてはいない。両方の REV が model.yaml にあることを確かめた。

## 6. 原因の分類（1.6）

- 修正はしていない。見つけた問題の分類（直すのは承認の後）:
  - 推定不能で即止まる（TR-07）: 仕様（DEC-305・306・342 で扱い中）。
  - EKF の棄却が実質ないこと: 設計（上流の作りの前提を正本が誤って説明している：PRM-91 の purpose）。直し方（自前の見張り DEC-352、または上流の設定の値の見直し）は承認事項に含めた。正本の説明の訂正は、DEC-352 の回答の後に行う。
  - EKF の共分散が GLIM の実際のずれと関係ない（PRM-82・83 が固定値）: 設定・物理特性（DEC-286・354 で実測）。

## 7. 検査・試験

対象: 作業ツリー（`31a6e1d` ＋ 未コミットの変更 ＋ REV-168）。
- `design/.venv/bin/python design/tools/apply_revision.py REV-168 --dry-run --check` → 新しい違反 0、新しい未判定 0。本適用 exit 0。
- `render_views.py`・`generate_params.py`・`render_migration_review.py` → exit 0。
- `design/.venv/bin/python design/tools/run_checks.py` → exit 1。内訳:
  - design_check: 合格 12・違反 0・未判定 5（`design/reports/design_check.txt` の要約行 `{"合格": 12, "違反": 0, "未判定": 5} 違反0件・未判定5件`）。DR-15 の未判定 35 件は第141便と同じ。
  - generate_params・intent_identity: PASS。
  - migration_validator: 違反 2 件（intent の改訂の連鎖が今のファイルに届かない、AR-016 からの再現）。第139〜141便と同じ、intent.md の未記録の編集による。
  - migration_tests: 88 件中 1 件不合格（test_real_model、同じ原因）。
  - input_integrity: 違反（drawio と .DS_Store 2 つの不一致）。HEAD の input_integrity.json と同じ 3 件で、この便の変更によるものではない。
- 解析: `python3 -I glim_odom_drift.py <dump 5 つ>`（Mac、2026-10-23）→ 出力を証拠に保存。
- 未実行: 単体試験（gouda_core を変えていないため）、rosbag の再生の評価（外付けがつながっていない）、実車の試験。

## 8. 残るリスク

- ずれの割合は下限しかない。人混み・段差での値はない。D を決める根拠が足りないまま実装すると、ずれたまま走る。
- 予算・見張りは位置が正しいことの証明ではない（誤った回復、NDT と GLIM が同じ向きに狂う場合）。
- 上流のソースの読みの多くはエージェントによるもので、私は EKF の棄却と NDT の出す条件しか確かめていない。
- 計算の余裕は VM の値だけ。

## 9. 更新した生成物の変更箇所

- REV-168 の適用による `model.yaml`（decisions、files）と、その生成物（`generated/pending_classification.md` など、`conflicts.yaml`、`intent_open_items.yaml`、`reports/*.json`・`*.txt`）。生成物は手で編集していない。

## 10. 次に進められる作業と、止まっている作業

- 進められる: 評価用の故障を入れる再生のスクリプトの下書き（評価用で製品のコードではない）、DEC-286 の測り方の準備。
- 止まっている: localization_wait の実装（DEC-305・342・350〜353 の回答待ち）、値の確定（DEC-354、外付けと新しい記録が要る）、実車での走行。
- コミットはまだ。
