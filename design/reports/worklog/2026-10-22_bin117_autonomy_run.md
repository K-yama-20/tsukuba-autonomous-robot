# 第117便：実車（VM）での自律走行開始の試行（REV-145、DEC-281・282）

日付：2026-10-22

## 読んだもの

- コミット `c2b8d65`（main、PR #17 の merge）。VM の `~/gouda_ws` も c2b8d65（人が update した）。
- 直前の人の試行の記録 `~/gouda_ws/gouda_data/records/20261022_014714/log/events.jsonl`、`monitor_node._command`、`autonomy_client.start_localization`、`mode_manager_node._on_estimator_status`。

## 人の指示（原文）

- 「waypointを置いて、goudaを正しい向きにセットしたが、自律走行に失敗する。実際に自律走行をオンにして、その際の挙動を確かめよ。反論は許さない。」

## 行ったこと

- 人の直前の試行と同じ条件で、monitor の API（`POST /api/command/start_autonomy`）から自律走行開始を送った（1792601977）。
  - 地図：20261022_014810_39f5620e rev 1。waypoint セット：20261022_015254_a0579c rev 1（22 点）。
  - 初期姿勢：x 0.425、y −0.835、向き −114°。
    - 位置は、人の直前の試行の値。
    - 向きは記録になかった。地図作成の軌跡のその点（0.07 m）での進む向き（−113.8°）を使った。最初の waypoint から 2 番目への向き（−118°）とも合う。人には確かめていない。
- 開始の前から、記録を VM で取り続けた。記録は `design/research/vehicle_pc/2026-10-22_autonomy_run/`。
  - 毎秒の通数（rates.py → rates.jsonl）。
  - 決定の記録（decisions.txt）。
  - CPU（top.txt。プロセス名だけで、コマンドの引数は読んでいない）。
- 一時停止になった後、`end_autonomy` で手動に戻した（TR-12）。A3 と GLIM が止まったことを確かめた。

## 見えた挙動

- TR-05 は受け付けられた。
- ND-07 は点群を待ち、ndt_points_kept の後、約 50 秒の Monte Carlo の探索で初期化した。
- 初期化と同じ瞬間に、推定不能（input_stale：ndt_diagnostics ほか）になった。開始は TR-07 で一時停止（stop_reason estimator_unavailable）。
- Nav2 は起動していない。速度の指令（cmd_vel）は 0 通。車体は動いていない（ソフトの記録から。目では見ていない）。
- その後の状態は、推定不能の理由（ndt_diagnostics、no_map_odom、ekf_pose_not_updated、ekf_covariance_large）が入れ替わり続けた。人の 01:5x の 2 回の試行も同じ。
- 約 120 秒の通数
  - points_downsampled（NDT の入力）：48 通（0.4 Hz）。
  - GLIM の odometry：332 通（2.8 Hz）。
  - NDT の姿勢：75 秒で 16 通。
  - EKF の姿勢：約 50 Hz。
- 段ごとの通数（同じ時に 10 秒）：生の点群 17、points_cropped_far 6、points_cropped 1、points_downsampled 1。
- CPU
  - 全体の 45 % が空き（6 コア、load 約 7）。
  - gouda_global_localization が 1 コアを使い切っていた（一時停止の後も主スレッドが 70 %）。gouda_monitor は 91 %。
  - gouda_monitor は生の点群を Python で購読している。
- 走行の間、ESP32 から manual_override_begin・end がくり返し記録された（ゲームパッドの操作か、推測）。

## 原因（推論。証拠は上の記録）

1. 初期化の直後の状態
   - 初期化の直後は、EKF の姿勢・診断がまだ届いていない。evaluate はそれを古いとみなして推定不能にする。
   - 開始の手順は、推定不能を一度でも受けると失敗する。そのため、開始は必ず失敗する（設計の誤り）。承認事項 DEC-282。
2. 点群の受け渡し
   - 点群が A3 の前処理と GLIM をほとんど通らない。このため NDT と GLIM が入力不足になり、推定は保てない（設定・設計）。
   - DEC-279 の profile だけでは足りない。承認事項 DEC-281。DEC-138 にも材料を足した。
   - ND-07 の CPU の高さの原因は未確認。

## 原因の分類（1.6）

- DEC-282：設計（ND-07 の状態の判定と、開始の手順の組み合わせ）。
- DEC-281：設定（Fast DDS）と設計（monitor の購読、A3 の前処理の組み方）。
- コード・設定は変えていない（DEC-106）。

## 実行した検査・試験

- VM：上の自律走行開始 1 回（記録は上）。
- `design/.venv/bin/python design/tools/apply_revision.py REV-145 --dry-run --check`（c2b8d65 の作業ツリー）：新しい違反 0、新しい未判定 0。
- REV-145 を適用し、render_views・generate_params・render_migration_review を実行した（終了コード 0）。
- `run_checks.py`：終了コード 1。
  - design_check は合格（違反 0、未判定 5）。
  - 違反は第115便と同じ 6 件だけ。原本 drawio・`.DS_Store` と、intent の旧要求の行。
- 単体試験：未実行（コードは変えていない）。

## 残るリスク

- 初期姿勢の向きは、Claude が軌跡から求めた値。人の設定とは違うかもしれない。
  - ただし今回の失敗は向きによらない。初期化の直後に必ず起きる。
- 車体が動かなかったことは、ソフトの記録（cmd_vel 0 通、Nav2 未起動）からの判断。
- ND-07 の CPU 100 % の原因は未確認。

## 次の作業

- 人の判断：DEC-282（推奨は案 a）、DEC-281（推奨は案 a と b）、DEC-138。
- 回答の後：実装、VM の試験、もう一度自律走行開始。
