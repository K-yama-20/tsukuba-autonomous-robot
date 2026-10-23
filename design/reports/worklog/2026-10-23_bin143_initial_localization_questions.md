# 作業記録 2026-10-23 第143便: 初期位置の推定・開始の速さ・確認用の表示（REV-169、DEC-355〜360）

## 読んだもの

- 作業ツリー `31a6e1d` ＋ 未コミットの変更（第141便まで。別のセッションが REV-168 を書いている最中）。
- status.md の第29便・第116便以降、作業記録 `2026-10-21_rev128_nd07_a3_implementation.md`（模擬の試験 5 m・90 度）、`research/vehicle_pc/2026-10-22_nav2_restart/`（nav2_lifecycle.txt・notes.txt）、`2026-10-22_autonomy_run4/decisions.txt`。
- `gouda_core/gouda_core/global_localization_node.py`（ndt_align_srv の呼び出し、240〜285 行）、`localization_core.py`（twist の分散、EKF の標準偏差の判定）、生成物 `gouda_global_localization.yaml`（PRM-82・83・92）。
- 上流：Autoware Core main の `ndt_scan_matcher_core.cpp`（align_pose、1144〜1185 行）、`tree_structured_parzen_estimator.cpp`（向きは −π〜π の一様、81 行）、`ndt_scan_matcher.param.yaml`（particles_num 200、output_pose_covariance 0.0225）、`ekf_localizer.param.yaml`。apt 1.9.0 との照合はしていない。
- VM：dpkg で ros-jazzy-rviz2 14.1.23、ros-jazzy-nav2-rviz-plugins 1.3.13、`/opt/ros/jazzy/share/nav2_bringup/rviz/nav2_default_view.rviz` を確認。

## 1. 人の発言（原文）

DEC-355 に原文で記録した（確認用の表示、探索の半径を広げる案、90 度ずれの問い、地図との違い・人混み・スタート地点、DEC-286 を暫定 0.7 m、DEC-287 の推奨案の向き）。

## 2. 分かったこと

- 90 度ずれの失敗：失敗したのは模擬の「5 m・90 度」（REV-128）。同じ試験で 1 m・10 度と 2.8 m・30 度は成功。2026-10-17 の評価（実の点群）では 5 m・90 度から戻っていた。探索は向きを一周一様に試すので、向きのずれは原因でない見込み。位置のずれ 5 m は、探索の広がり（PRM-84、標準偏差 0.5 m）の 10 倍で、ほぼ試されない（推測）。このときは照合の良さ 2.03＜2.3 で「推定不能」と正しく判定し、誤った位置を正常とはしなかった。
- ND-07 は ndt_align_srv を 1 回だけ呼び、success だけを見ている（global_localization_node.py 265〜270 行）。探索を広げて呼び直す作りはない。
- EKF の標準偏差：上流の既定（pose_smoothing_steps 5、proc_stddev_vx_c 10.0）と NDT の出力の共分散（0.0225 m²）、Gouda の twist の分散（PRM-82 0.04、PRM-83 0.01）。止まっていて照合が良くても 0.50 m 前後。0.5 m は Autoware の error_ellipse_size 1.5 ÷ ellipse_scale 3。実際のずれではなく、設定と NDT の姿勢の遅れで決まるモデル上の値の可能性（推測）。
- Nav2 の STARTUP は約 7.5 s（第123便の記録、998.08 → 1005.54）。今も開始のたびに STARTUP している。終了のときの RESET は「Nav2 が起動済み」の印があるときだけで、STARTUP の途中で捨てられると印が立たない（notes.txt）。
- 確認用の表示：monitor は waypoint・地図作成の終わりの姿勢・初期姿勢を描くが、走行中の推定の位置と軌跡は描かない（app.js）。VM には rviz2 と Nav2 の表示の部品・既定の設定ファイルがある。

## 3. 行ったこと

- REV-169（DEC-355 recorded、DEC-356〜359 承認、DEC-360 試験・実測）を `--dry-run --check`（新しい違反 0・未判定 0）の後に適用。番号は reserve_ids.py で予約（REV-169、DEC-355〜360、第143便）。REV-168 は別のセッション（localization-gap-bridging）が予約・作成中で、触れていない。
- コード・設定は変えていない。DEC-286・287 は人の明示の承認ではないので pending のまま（DEC-358・359 で確認）。

## 4. 検査

- run_checks（31a6e1d ＋ 作業ツリー）：設計検査 合格 12・違反 0・未判定 5。移行の違反 2 件と検査器の試験の不合格 1 件は intent.md の未記録の編集による（前と同じ）。単体試験・実機：未実行。

## 5. 次

- DEC-360 (1)：VM の模擬の試験で、向きと位置のどちらで失敗するかを切り分ける（AI が行える。人の許可があれば）。
- DEC-357：rviz2 の設定ファイル。DEC-358・359：人の確認の後に実装。
