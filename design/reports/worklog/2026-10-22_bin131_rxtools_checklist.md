# 作業記録 2026-10-22 第131便: RxTools での検査の手順（REV-159）

## 読んだもの

- コミット `31a6e1d` ＋ 作業ツリー。status.md（第129便）、記録 `research/gnss_no_tracking_investigation_2026-10-22.md`、mosaic-G5 Reference Guide 1.0.1（AI の作業領域の pdftotext の写し: lstConfigFile、ReceiverStatus の RxState・RxError・AGCState、Spectral View、setAGCMode・setFrontendMode・setSatelliteTracking・setSignalTracking・setElevationMask・setCN0Mask の RxControl の道筋）。
- VM（読むだけ）: by-id（受信機は Ubuntu の VM にある）、Gouda は止まっている（`gouda.sh status`、`pgrep -l`）。

## 1. 人の指示（原文、DEC-303）

- 「RXtoolsをvmのwindowsにいれた。まずこれで色々検査したい。衛星測位を何度も試したって無駄なことです。受信機は今屋内にあります」

## 2. 行ったこと

- 手順 `research/rxtools_inspection_checklist_2026-10-22.md`: 受信機を Windows の VM に渡す、検査の間は Ubuntu で Gouda を起動しない・Boot に保存しない、(1) Current・Boot・RxDefault の設定の全体の写し、(2) アンテナの給電（ACTIVEANTENNA、ANTENNA の過電流）、(3) 前段ごとの AGC（−128 は PLL が lock していない、DualAnt の条件 30〜50 dB）、(4) スペクトル、(5) 追尾を止めうる設定の get、(6) 任意の追尾の数、(7) その後の判断。
- 未確認の点を手順に書いた: 引数を省いた get の書き方、RxControl の画面の名前、firmware 1.1.1 との版の差。
- REV-159（DEC-303 recorded、FILE-RXTOOLS-INSPECTION-CHECKLIST）。番号は reserve_ids.py で予約（REV-159、DEC-303、第131便。第130便は別のセッション）。
- 受信機・コード・設定には触れていない。

## 3. 検査

- `apply_revision.py REV-159`、`run_checks.py`（31a6e1d ＋ 作業ツリー）: 設計検査 違反 0・未判定 5。移行の検査の違反は既存の 6 件。単体の試験: 未実行。

## 4. 次

- 人が RxControl で 1〜5 を行い、結果（特に `lstConfigFile` の出力、AGC、ACTIVEANTENNA・ANTENNA）を渡す。AI が読み、原因を絞る。commit はしていない。
