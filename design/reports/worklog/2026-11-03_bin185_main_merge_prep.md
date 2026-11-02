# 第185便 作業記録：main に入れる準備（確認だけ。コミットはしていない）

- 日付：2026-11-03
- 読んだコミット：f4dc4ea（作業ツリーに未コミットの変更あり）
- 人の指示（原文）：「main に入れる準備」（ボタンの回答）
- 変更：コード・設定・正本は変えていない

## 実行した検査・試験

| 検査 | コマンド | 対象 | 結果 |
|---|---|---|---|
| 単体試験（Mac） | `/opt/anaconda3/bin/python3 -m unittest discover -s gouda_core/test` | 作業ツリーの写し（REV-195 などを除く） | 328 件 OK（skip 15） |
| 設計検査 | `design/.venv/bin/python design/tools/run_checks.py` | 同上 | 違反 0・未判定 5。input_integrity・intent_identity・migration_validator・migration_tests は FAIL（前と同じ 4 つ。REV-195 の記録で扱うもの） |
| 単体試験（VM、Nav2 あり） | `python3 -m unittest discover -s gouda_core/test`（~/gouda_ws_prep） | 同上 | 328 件 OK |
| 結合試験（VM、模擬） | `ubuntu_stage5-6.sh` | 同上 | exit 0、T1〜T6。MPPI の読み込みと BT の SmoothPath を確認 |
| x86 の走行シミュレータ | 第183便 | コードの差分のハッシュが同じ（afedb74d9411ac59） | 有効 104 本 |
| 公開してはいけない情報の検索 | grep | 差分と未追跡のすべて | 0 件 |
| 実車 | — | — | 未実行 |

## 残るリスク

- 実の自己位置（ND-07）・実のセンサとの組み合わせは未実行。map→odom の時刻の変更（REV-191）は単体試験まで
- main に入れて update.sh を実行すると、実車の既定が RPP から MPPI に変わる

## 次の作業

- 止まっている：コミット・PR（人の指示待ち）、intent.md 第17版（REV-195、別のチャットで未適用）
