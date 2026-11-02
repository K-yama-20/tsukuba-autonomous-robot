# 第176便 作業記録：MPPI・平滑化の回答の記録と、waypoint の渡し方・衝突監視の検討（REV-189、DEC-400・401）

- 日付：2026-11-02
- 読んだコミット：f61a71b（作業ツリーに別のチャットの未コミットの変更あり。人が編集した intent.md を含む）
- 人の回答・発言（原文）：
  ```
  MPPI: 使用
  パスの平滑化：行う
  waypointの順次追従は現状の全点を一括で渡す方法よりも適切なのでは？
  衝突監視はどうしたらいい？（独自実装はなるべく避けたい）
  ```
- 読んだもの：intent.md、DEC-122・344・366・367・372・380、TRB-006・008・011、第170〜172便、提案 mppi_trial、KUAMS の比較。navigation2 1.3.13 の waypoint_follower.cpp、nav2_collision_monitor（README、collision_monitor_node.cpp、source.cpp、params）、smooth_path_action.hpp、nav2_smoother.cpp（Mac の一時領域に取得）
- 変更：判断台帳の記録だけ。コード・設定は変えていない

## 1. 記録（REV-189）

- DEC-400（MPPI）、DEC-401（平滑化）を answered。DEC-122 は書き換えていない。実装の着手の許可（DEC-106）と「使用」の範囲は未確認

## 2. waypoint の渡し方

- 上流の waypoint_follower は点ごとに NavigateToPose を送り、stop_on_failure false なら失敗した点を飛ばす（ソース）。失敗は BT の回復が尽きてから返るので、PRM-18（9999999）のままでは飛ばす前に滞留する（ソースからの推測、実機未確認）
- 案：kind: stop で区切った区間ごとの NavigateThroughPoses（DEC-366）、PRM-11 の見直し（TRB-006）、飛ばす条件（DEC-367）。前提 DEC-380 (1)（Mission が kind を落とす）。いずれも未回答

## 3. 衝突監視

- 独自実装を避けるなら上流の nav2_collision_monitor。source_timeout 0 で、途絶による停止を無効にできる（collision_monitor_node.cpp・source.cpp の `getSourceTimeout() != 0`）
- 案：approach の 1 つだけ（stop の四角を置かない）。intent.md の「PC側で非常停止機構は存在させない」「cmd_velの後段で独自に速度を抑える処理は加えない」に入るかは人の判断（DEC-372、未回答）

## 4. 実行した検査・試験

| 検査 | コマンド | 対象 | 結果 |
|---|---|---|---|
| 変更セットの試し | `apply_revision.py REV-189 --dry-run --check` | 作業ツリー | 新しい違反 0・新しい未判定 0 |
| 適用・再生成 | apply_revision・render_views・generate_params・render_migration_review | 同上 | いずれも 0 |
| 設計検査 | `design/.venv/bin/python design/tools/run_checks.py` | 同上 | 下記の status.md の第176便の値 |
| 単体試験・結合試験・実車 | — | — | 未実行（コードの変更なし） |

## 5. 原因の分類（1.6）

- 修正なし（判断の記録）

## 6. 残るリスク

- 上流のソースの読みは実機で未確認。MPPI・平滑化・衝突監視の組み合わせは未試験
- VM に ssh がつながらず、x86 の PC への接続方法も不明なので、実装しても Mac の単体試験までしか AI では確かめられない

## 7. 次に進められる作業／止まっている作業

- 止まっている：MPPI・平滑化の実装（着手の許可）、衝突監視（DEC-372）、waypoint の区間分け（DEC-366・367・380）

更新した生成物：再生成による変更（`design/reports/model_diff_rev-189.md`）。パラメータの値は変わっていない。
