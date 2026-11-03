# 第191便 作業記録：vehicle_bridge の seq を firmware に合わせる（REV-204、DEC-415、TRB-014）

- 日付：2026-11-03
- 読んだコミット：a88fd04（ブランチ claude/dev-tab-vehicle-test-6eb228、作業ツリーに第189・190便の未コミットの変更あり）
- 人の回答（原文）：「案 F を実装する」

## 変更

- `vehicle_core.BridgeCore.on_status`：STATUS の last_pc_seq が自分の seq より新しければ、そこまで進める（`esp32_protocol.newer_sequence`）。戻さない。ファームは変えていない
- `test_vehicle_core.py`：新しい session、戻らないこと、未受信、wrap の 4 件
- 台帳 TRB-014、正本 ND-12

## 原因の分類（1.6）

- 実装（bridge が firmware の seq の規則を守れていなかった）

## 実行した検査・試験

| 検査 | コマンド | 対象 | 結果 |
|---|---|---|---|
| 単体試験（Mac） | `PYTHONPATH=gouda_core python3 -m unittest discover -s gouda_core/test` | 作業ツリー | 350 件 OK（skip 15） |
| 結合（x86、~/gouda_ws_sim、esp32_sim、合成 IMU） | `bash gouda_core/test/ubuntu_vehicle_test.sh` | 同上 | 全項目 PASS。3 回続けて実行して pc_frame_rejected 0 件、pc まで 0.05〜0.15 s |
| 設計検査 | `design/.venv/bin/python design/tools/run_checks.py` | 同上 | 違反 0・未判定 5。input_integrity・intent_identity・migration の FAIL は前と同じ |
| Gouda・PC の再起動の後（模擬） | — | — | 未実行（同じ処理を単体試験で確認） |
| 実機の ESP32・実車 | — | — | 未実行 |

## 残るリスク

- 実機の ESP32 では未確認
- 最初の STATUS が届くまでの COMMAND は棄却されうる（STATUS の周期 50 ms）

## 次の作業

- 人：試験条件の安全の判断、x86 への反映の判断
- コミット・push はまだ。x86 の ~/gouda_ws には未反映

## 追記：x86 への反映（人の指示「x86 に反映する」）

- 手動走行・試験なしを確かめて、作業ツリーの変更 58 ファイルを x86 の ~/gouda_ws/src/tsukuba-autonomous-robot に写し、gouda_core を build、`bash gouda.sh stop` の後に `bash gouda.sh start`（05:31）
- 確認：MANUAL、IMU 受信 100 Hz、/api/vehicle_tests が新しい初期値を返す。ESP32 は接続なしで未確認
- x86 のブランチは dev-tab-vehicle-test（9caaa65）のまま、変更は未コミットのファイルの写し。update.sh は変更があると止まる
