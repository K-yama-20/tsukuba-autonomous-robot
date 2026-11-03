# 第201便 作業記録：t_lock と T ロックの解析を方向別に（REV-210、DEC-421）

- 日付：2026-11-03
- 読んだコミット：a88fd04（作業ツリーに第189〜200便の未コミットの変更あり）
- 人の指示（原文）：「解析を直す」

## 変更

- `motion_start.py`：入力の直前の動きを IMU から読む `_before`、方向別の `_t_lock_table`、`_t_down_table` を追加。列 `angle`、`moving`、`yaw_before` を追加
- `vehicle_test_node.py`：解析に imu.csv を渡す
- `test_vehicle_test_core.py`、`vehicle_test_drive.py`、`docs/vehicle_tests.md` を更新
- パルスの `locked` と、試験の入力は変えていない

## 自律判断

- 判定の窓は `baseline_tail_s`、倍率は `noise_k` を使った。新しい値を増やさないため
- t_lock の基準は方向ごとに、同じ実行の遅れの表、なければその方向の止まっていた最長の中立の遅れにした
- 旋回はヨーの平均、前後は加速度のばらつきで判定した。前後は実車で確かめていない

## 期待値を変えた試験（1.6）

- `test_t_lock_turns_between_the_two_gaps_around_it`：中立 0.25、0.75、1 s の `locked` を False から None に
- `vehicle_test_drive.py` の `t_lock bracket`：中立 0.25 s を False から None に。`no delay is negative` は `n` のある行だけを見る
- 根拠：窓より短い中立は窓に走行が入り、遅れを読めない。実車でも最初の超過が 0.00〜0.01 s だった（第199便）。人の指示「解析を直す」の範囲とした

## 実車の 2 件の再計算（AI の手元で実行。x86 の result.json は変えていない）

- T ロック：止まる段は左 0.26〜0.30、右 0.15〜0.18。第200便の読みと一致
- t_lock：中立 1 s 以下は判定不可。1.5 s 以上は方向ごとに 1〜2 回で、左は 1.5 s ○、2・3 s ×、4・6 s ○、右は 1.5 s 以上すべて ○。回数が足りず、t_lock は未確定

## 検査・試験

| 検査 | コマンド | 対象 | 結果 |
|---|---|---|---|
| 単体試験（Mac） | `PYTHONPATH=gouda_core python3 -m unittest discover -s gouda_core/test` | 作業ツリー（a88fd04＋未コミット） | 361 件 OK（skip 15） |
| x86 の模擬 | `ubuntu_vehicle_test.sh`（~/gouda_ws_sim） | 同上 | FAILS なし（`ROS_DOMAIN_ID=82`）。ゲームパッドの介入の項目はない |
| 設計検査 | `run_checks.py` | 同上 | 合格 12・違反 0・未判定 5。intent_identity、migration_validator、migration_tests の FAIL は前の便と同じ表示で、この便では中身を読み直していない |
| 実車 | — | — | 未実行（解析だけの変更。x86 の本番の作業領域には未反映） |

原因の分類（1.6）：試験（解析の判定の誤り）。

## 残るリスク

- 自己基準：t_lock の基準に遅れの表がないとき、最長の中立の段は必ず ○ になる
- 前後の `moving` の判定は実車で確かめていない
- 手元の再計算のデータは scratchpad にだけ置いた（リポジトリには入れていない）

## 追記：x86 への反映（人の指示「x86 に反映する」）

- `/mode/state` が mode 1（手動走行）で、最後の試験（082639）が終わっていることを確かめた
- 変更 91 ファイルを写し、gouda_core を build、`bash gouda.sh stop` の後に `bash gouda.sh start`（08:54）
- 過去の実行の result.json は古い解析のまま。新しい解析は次の実行から

## 次の作業

- 進められる：遅れの試験
- 止まっている：コミット（人の指示待ち）
