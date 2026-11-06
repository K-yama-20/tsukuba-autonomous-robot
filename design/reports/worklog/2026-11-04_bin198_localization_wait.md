# 第198便 作業記録：推定不能が 30 秒を超えたら止まって自動で回復を待つ（REV-212、DEC-423）

- 日付：2026-11-04
- 読んだコミット：0e260f3（作業ツリーに未コミットの変更あり）
- 人の回答：「止まって自動で回復待ち」（DEC-423）
- 変更：`mode_manager_node.py`（localization_wait）、`autonomy_core.localization_wait_action`、試験。`ubuntu_stage5-6.sh` の T5・T6（承認された仕様の変更による）
- 原因の分類（1.6）：仕様の変更。途中の実装の誤り 2 つ（待ちの間に速度上限の処理が hold を解く、取り消しの後に goal_active が残る）を結合試験で見つけて直した

## 検査

| 検査 | 対象 | 結果 |
|---|---|---|
| 単体試験（Mac、VM） | 作業ツリー | OK（VM 332 件） |
| `ubuntu_stage5-6.sh`（VM、模擬） | 同上 | exit 0。T5・T6：30 秒続行、hold true で停止、正常で goal を出し直し hold false。記録で確認 |
| 設計検査 `run_checks.py` | 同上 | 違反0件・未判定5件 |
| LiDAR の途切れ、実の推定器、実車 | — | 未実行 |

## 残るリスク

- 待つ時間に上限がない。確認走行区間の 3 分の滞留に当たりうる
- 回復の判定は状態が正常に戻ることだけ（DEC-351 は未対応）
- LiDAR の途切れで GLIM が止まる場合、Nav2 の失敗が先に来ると待機に入る。IMU で進む部分は未実装
- PC 出力の中立は車体の停止の保証ではない
- monitor の hold の理由の文は localization_wait でも「適用中を待つ」と出る。表示の `processing_state` は localization_wait

## 次

- 止まっている：LiDAR の途切れの方式の調査と実装、コミット
