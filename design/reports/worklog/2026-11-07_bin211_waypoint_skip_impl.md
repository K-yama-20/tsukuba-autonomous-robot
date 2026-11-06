# 作業記録 2026-11-07 第211便: waypoint を飛ばす処理の実装（REV-235・238、DEC-446、PRM-137〜140、IFD-58）

## 読んだもの

- コミット `7f0c7ae`＋作業ツリー（他のセッションの未コミットの変更を含む）。
- 判断台帳の DEC-367・DEC-441・DEC-446、第200便の結果と試験用コピーの差分（`research/vehicle_pc/2026-11-06_waypoint_skip_sim/`）。
- `gouda_core/gouda_core/` の waypoints・autonomy_core・autonomy_client・mode_manager_node・nav2_config、`web/app.js`・`index.html`。
- 上流の `nav2_costmap_2d/src/costmap_2d_publisher.cpp`（QoS と値の変換）、`nav2_msgs/action/NavigateThroughPoses.action`（number_of_recoveries）。

## 1. 人の指示（原文）

- DEC-446：「実装してよい」（DEC-367 の方式、選択式の回答「目印の点だけ」の後）。

## 2. 実装したこと（コード、未コミット）

- `waypoints.py`：Waypoint に skip_allowed（既定 false）を足した。
  - 印のある点だけ保存する。印のないセットの内容ハッシュは前と同じ。
  - stop の点と最後の点には付けられない（validate）。
- `autonomy_core.py`
  - Mission.skip_allowed を足した。
  - parse_footprint・footprint_max_cost（waypoint に置いた footprint の格子の最大の値。unknown は数えない）を足した。
  - SkipSettings（PRM-137〜140。どれかが未確定なら働かない）と WaypointSkip を足した。
- `autonomy_client.py`：/global_costmap/costmap（IFD-58）を購読し、feedback の number_of_recoveries と向きを持つ。skip_to は今の handle を外してから新しい goal を送る（bt_navigator の preemption。古い goal の終わりを失敗とみなさない）。
- `mode_manager_node.py`
  - skip_* の parameter を足した。
  - Nav2 の feedback ごとに _skip_check を呼ぶ。飛ばしたら DecisionEvent waypoint_skipped とログに残し、次の点から goal を出し直す。
  - 印があるのに値が未確定なら、開始のときに waypoint_skip_disabled を記録する。
- `nav2_config.py`：GLOBAL_COSTMAP_TOPIC を足した。
- monitor の waypoint タブ
  - 「塞がれたら飛ばしてよい waypoint」の欄を足した（stop と最後の点は出さない）。
  - 印の点は、地図の上に点線のオレンジの輪で描く。
  - 「最後の点を削除」で新しく最後になった点の印は外す。

## 3. 正本（REV-235・238）

- PRM-137（skip_stall_s）・138（skip_cost_threshold）・139（skip_occupied_s）・140（skip_progress_m）は未確定（tbd）で追加した。
  - 問題 G-WAYPOINT-SKIP を付けた。
  - ソフト試験用の仮値は 10 s・99・3 s・1 m（AI の仮値。実車採用値ではない）。
  - 実車（trial でない起動）では値がないので、飛ばす処理は働かない。
- IFD-58 /global_costmap/costmap を足した。QoS は reliable・transient_local・depth 1。always_send_full_costmap は生成した nav2_params.yaml で true。

## 4. 試験

- Mac：`/opt/anaconda3/bin/python3 -m unittest discover -s gouda_core/test` で 359 件 OK（skip 15）。新しい `test_waypoint_skip.py` は 15 件。
- 規則を壊した写し 7 通り（印・recovery・推定・持続・最後の点・未確定・保存）は、どれも不合格になった。
- ワークステーション（`~/gouda_ws_skip`、`.git` を外した写し）：359 件中 1 件不合格。
  - `test_drive_sim_layers` の「git の作業コピーの中では patch しない」で、写しに `.git` がないため。環境の違いで、コードの誤りではない。
  - 原因の分類：試験（環境）。
- `test_tr05_start_order` の偽の node に skip_settings と skip_allowed を足した。
  - 原因の分類：試験基盤。新しい属性を偽物が持っていなかった。合否の基準は変えていない。
- 模擬（実際の Nav2、`drive_sim.sh`、仮値）
  - 足した場面：skip_blocked・skip_blocked_unmarked・skip_person（`drive_sim_core.py`、`drive_sim_fixture.py` が印を付ける）。
  - 結果：skip_blocked は飛ばし 0、進捗 0.43 で時間切れ（印なしと同じ）。skip_person はゴール着、飛ばし 0。
  - 調べ（試験用の写しにだけ足したログ）：塞がれた点の上の cost は 28〜54 で、仮値 99 に届かなかった。車体は塞がれた点の周りを ±2 m 動き回っていて、移動で数え直す時計が満ちなかった。
  - 原因の分類：設計（条件の定義が場面に合わない）。人に提示し、第240便で直した。

## 5. 残るリスク

- 実車での確認はまだ。値は tbd。
- DEC-344 (2)（確認走行区間で飛ばすか）は未回答。区間の情報は waypoint セットにないので、目印を付けるかで人が決める。

## 6. 次

第240便を見る。
