# 作業記録 2026-10-20 第49便: DualAnt の後のドライバの屋内の検査（REV-083）

## 読んだもの

- コミット `3341602` ＋ 未コミットの REV-073〜082。status.md（第48便）、G-GNSS-NO-HEADING、`research/mosaic_go_g5_p6_usage_guide_2026-10-20.md` §6。

## 1. 人の指示（原文）

- 「vmをつないだ。ドライバ等の検査をせよ。屋内なので衛星電波の受信は出来ない」

## 2. 行ったこと（読むだけ）

- VM で by-id・fuser・プロセス・Gouda の状態、起動のログ、GNSS の topic（hz・echo --once）、/diagnostics を見た。受信機のポートには触れていない（USB1 はドライバ、USB2 は誰も開いていない）。
- 結果（FILE-GNSS-DRIVER-INDOOR-CHECK-DUALANT）:
  - supervisor が by-id の USB1 を見つけてドライバを起動し、ドライバは設定を終えた。拒否は既知の `sntp, on` だけ。「Multi antenna … not support」の警告なし。
  - /config revision 18 の静的 TF の後に起動し、方位のオフセット 90 度（主→副が右）。
  - PVT・方位・観測 10 Hz、RFStatus 1 Hz。屋内のため観測 0、測位・方位とも mode 0、受信機の時刻は未確定。navsatfix は一覧になかった（解がないためと推測）。干渉・なりすましなし。
- 位置を含む値は記録に書いていない（屋内で位置は出ていない）。

## 3. 判断

- 屋内で確かめられる範囲では、ドライバは正常。副アンテナ・方位は屋外で確かめる。
- frontend mode の照会はしていない（ポートに触る許可を求めていないため）。必要なら屋外の確認の前に USB2 で gfm を照会する（人の許可）。

## 4. 検査

- `reserve_ids.py` で REV-083・第49便を予約。`apply_revision.py REV-083`、`run_checks.py`（3341602 ＋ 作業ツリー）: 設計検査 違反 0・未判定 4。移行の検査の違反は人の drawio と .DS_Store だけ。単体の試験: 未実行（コードの変更なし）。

## 5. 次

- 屋外の確認（ガイド §6）: gfm が DualAnt、AGC（main・Aux1）、MeasEpoch の番号 1、AuxAntPositions の基線 0.34 m、AttEuler の Error 0・Mode 2。commit はしていない。Gouda は VM で動いている。
