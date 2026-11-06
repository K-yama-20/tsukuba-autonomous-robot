# 第245便 作業記録：MID-360 の層に残る印のたまり方を測る模擬の道具（REV-272、DEC-493、issue #90 の段階 1）

- 日付：2026-11-07
- 読んだコミット：9c449b5（作業ツリーに他のセッションの未コミットの変更が多数。drive_sim_core.py・drive_sim_node.py・drive_sim.sh にも他のセッションの未コミットの変更がある）
- 読んだもの：CLAUDE.md（1.1〜1.13）、status.md の先頭、`design/troubleshooting/ledger.yaml` の TRB-001・TRB-002、issue #29・#35・#76・#78、
  `gouda_core/gouda_core/nav2_config.py`（costmap の層と MID-360 の部分）、`gouda_core/test/` の drive_sim_core.py・drive_sim_node.py・drive_sim_layers.py・drive_sim.sh、
  上流の写し `design/research/upstream_jazzy/nav2_costmap_2d/src/` の costmap_2d_ros.cpp（231〜245 行）・costmap_2d_publisher.cpp（57〜82 行）、
  回復動作の BT（上流の写しと `design/research/vehicle_pc/2026-10-24_nav2_runtime_config/navigate_through_poses.xml`）、第242便の作業記録、REV-262・REV-265（形の手本）
- Gouda の起動・停止、車載 PC・模擬の機械への接続はしていない。コミットはしていない

## 人の指示（原文、DEC-493）

「実装して」

AI の問いは「段階 1（試験専用の道具の追加）を実装してよいですか？」。承認の範囲は issue #90 の段階 1 だけと読んだ。
それまでの人の発言の原文は DEC-493 の note に書いた。調査と計画は issue #89・#90。

## 変更（すべて試験専用。製品のコード・設定・値は変えていない）

| ファイル | 内容 |
|---|---|
| `gouda_core/test/drive_sim_blind.py`（新） | 場面 8 つ（下）と、残った印を数える関数 stale_marks |
| `gouda_core/test/drive_sim_core.py` | `Obstacle` に stop_after_s（現れてからこの時間で止まる。既定はなしで今までどおり）。`scenario()` が `blind_` で始まる名前を drive_sim_blind に渡す。既存の場面と `SCENARIOS` の一覧は変えていない |
| `gouda_core/test/drive_sim_node.py` | 約 1 秒おきに obstacles.csv（物の位置と有無）と costmap_marks.csv（格子ごとの lethal・残った印・車体の近くの残った印）を書く。report.json に marks（格子ごとの最大と最後の値）を足した。読む格子は local_costmap の costmap・obstacle_layer・mid360_layer |
| `gouda_core/test/drive_sim.sh` | result.json の log に clear_local・clear_global（回復動作の丸ごと消去の回数。起動ログの行を数える）を足した |
| `gouda_core/test/test_drive_sim_blind.py`（新） | 16 件（下） |
| `design/revisions/REV-272.yaml` | DEC-493（answered）。entities・modifications はなし |

場面（寸法・速度・位置は仮の値。模擬の物は車体を避けない）

| 名前 | issue #90 | 内容 |
|---|---|---|
| L10・L11（既存） | P1 | 経路の上に静止した低い物 |
| blind_pass_h30・_h50 | P2 | 向かいから 0.5 m/s、横 0.8 m を通る。その先で経路が左へ曲がる |
| blind_overtake | P3 | 後ろから 1.0 m/s で左を抜け、車線へ寄る（車体が 1.0 m/s より遅い間だけ抜く） |
| blind_cross | P4 | 前を左から右へ 0.5 m/s で横切る |
| blind_wait | P5 | 前を 20 秒ふさがれる間に、左右を 3 台が通る |
| blind_stop_h30・_h50 | P6 | P2 の相手が、経路の曲がる内側（14.0, 0.9）で止まる |
| blind_clear | P7 | 横に低い静止物がある所で前を 40 秒ふさぎ、回復動作を出させる |

残った印の数え方：格子の lethal（OccupancyGrid の値 100）のセルのうち、その時刻にある物のどれからも 0.5 m より遠いもの。
そのうち車体から 2.0 m 以内を「車体の近く」とした。0.5 m と 2.0 m は数え方の仮の値で、合否の線ではない。

## 決めたこと（自律判断）とその理由

1. 場面と数える関数を新しいファイルに置いた。drive_sim_core.py には他のセッションの未コミットの変更があり、触る行を少なくするため
2. 記録を別の node にせず drive_sim_node.py に入れた。物の本当の位置と同じ時計で数えられるため
3. 記録は常に書く（切り替えの引数を足さない）。既存の走行の結果の値は変わらず、ファイルが 2 つ増えるだけ
4. 既存の `SCENARIOS` の一覧に足さなかった。この一覧を回す既存の道具の本数を変えないため
5. 待機の場面（P5）の 3 台は、車体が近づいた距離で順に動き出す形にした（時刻で動き出す仕組みは足していない）。車体が止まる前に通り始める場合がある

## 承認事項・実測待ち

- DEC-493（answered）：上の原文
- 人に確認中（issue #90 の 9）：相手の小型ロボットの寸法と速度、後退とその場旋回が出る場面
- 未承認：模擬の実行（段階 2・3）、issue #89 の案 B（印の寿命）・C（追跡）・D（回復動作の消す範囲）・E（MID-360 の横の見える範囲の実測）

## 実行した検査・試験

対象：9c449b5＋作業ツリー（他のセッションの未コミットの変更を含む）。Mac。

| 検査 | コマンド | 結果 |
|---|---|---|
| 新しい試験と模擬の既存の試験 | `python3 -m unittest test_drive_sim_blind test_drive_sim_core test_drive_sim_layers test_drive_sim_course`（gouda_core/test で） | 45 件 OK |
| 単体試験の全体（変更後） | `PYTHONPATH=gouda_core python3 -m unittest discover -s gouda_core/test` | 489 件 OK（skip 35） |
| 構文 | `python3 -m py_compile drive_sim_node.py`、`bash -n drive_sim.sh` | OK |
| 変更セットの試し | `design/.venv/bin/python design/tools/apply_revision.py REV-272 --dry-run --check` | 0 new violations、0 new undetermined |
| 本適用 | `design/.venv/bin/python design/tools/apply_revision.py REV-272` | 適用した |
| 設計検査の全体 | `design/.venv/bin/python design/tools/run_checks.py` | 終了コード 1。design_check：違反0件・未判定5件。generate_params・intent_identity は PASS。input_integrity・migration_validator・migration_tests は FAIL（違反 5 件はすべて SystemArchitecture.drawio と .DS_Store 2 つの不一致で、この便の前からのもの） |
| 単体試験の全体（変更前）、ROS 上での drive_sim_node の起動、drive_sim.sh の実行、模擬の機械・車載 PC・実車 | — | 未実行 |

新しい試験（16 件）：物が時間で止まる／止まる時間がなければ動き続ける／8 つの場面が drive_sim_core の scenario から作れる／知らない名前は拒む／既存の場面と一覧は変わらない／
止まる相手は曲がる内側で止まる／通り過ぎる相手は止まらない／ふさぐ物は消える／車体の近くの低い物は XT-32 の帯に点がなく MID-360 には点がある／
残った印の数え方（空の格子、物の上の印、離れた印、車体から遠い印、膨らませたセルと未知のセルは数えない、消えた物の印、動く物の古い位置）。

## 設計検査の状態（1.4）

- 設計検査：違反0件・未判定5件（この便の前と同じ）
- 移行が正確：この便では扱っていない。migration の FAIL は前からのものが残っている
- 実車投入可能：人の判断待ち。材料：この便は試験専用の道具だけで、製品の動きは変えていない

## 原因の分類（1.6）

- 修正ではなく、試験基盤の追加（試験。合否の基準は変えていない）
- 症状（死角に入った印が消える）の原因は TRB-001・TRB-002 に記録済みの設計の層のもので、この便では直していない

## 残るリスク

- 記録の部分（格子の購読と costmap_marks.csv）は ROS の上で動かしていない。層ごとの格子の topic 名（local_costmap/obstacle_layer・mid360_layer）は上流のソースの読みで、実行では未確認。出なければ全体の格子だけが数えられる
- 全体の格子の lethal には XT-32 の層の印も入る。層ごとの値が取れない場合、MID-360 の層だけの数は分からない
- 格子の時刻と物の位置の時刻は最大で 1 周期ほどずれる。0.5 m の幅で吸収する前提（1 m/s の物で約 0.1〜0.2 m）
- 場面の位置と速度は机上で決めた。車体の実際の速度によっては、すれ違い・追い抜きが意図した場所で起きない。段階 2 の少ない本数で obstacles.csv と trace.csv を見て直す必要がある
- 模擬の MID-360 は前端・中心線の仮定で、フレームの遮りと XT-32 への車体の写り込みは入っていない

## 次に進められる作業と、止まっている作業

- 進められる（人の許可の後）：段階 2（L10・L11・blind_pass・blind_stop を S0・S2 で各 2 回、模擬の機械で）
- 止まっている：相手のロボットの寸法と速度の確認（仮の値のまま）、issue #89 の案 B〜E
