# 作業記録 2026-10-22 第128便: GNSS まわりの現状と改善点の提案（REV-157）

## 読んだもの

- コミット `31a6e1d` ＋ 作業ツリー（未コミット 27 件、別のセッションの作業を含む）。status.md（第127便）、`reports/handover_2026-10-21_2.md`、判断台帳の GNSS の項目、G-GNSS-NO-HEADING・G-INIT-POSE-GNSS・ND-07・ND-19、`gouda_core/gouda_core/` の gnss_log.py・monitor_core.py・mode_manager_node.py、提案 `crowd_robust_localization_2026-10-22.md` §5。
- VM（読むだけ）: /dev/serial/by-id（受信機なし）、str2str の有無、gnss_rtk.yaml の有無と権限（中身は読んでいない）、プロセスの名前（`pgrep -l`）、起動のログの GNSS の行、地図の gnss.jsonl の件数と mode の集計（座標は出していない）。

## 1. 人の指示（原文）

- 「現状の構成を把握して、GNSS回りの改善点を考えよ」（途中で「vm has started. if you need, you may access.」）

## 2. 分かったこと

- 2026-10-22 の実の地図作成 3 回（20261022_014810・031430・042035）の gnss.jsonl はすべて PVT mode 0・方位 mode 0／error 1。20261019 の地図の gnss.jsonl は 0 行。今の地図はどれも GNSS と対応づけられない（屋内か空が見えない所と推測）。
- 地図作成の開始の警告は点群と IMU だけで、GNSS の解なしに気づく手段がない。manifest の GNSS の要約は件数と SHA-256 だけ。
- VM には str2str（/usr/bin）と gnss_rtk.yaml（mode 600）がある。最後の起動で「ntrip from gnss_rtk.yaml」（ファイルは有効）。受信機をつないで中継が動いた記録はない。
- ND-07 は GNSS を使っていない。初期位置・見張り・融合はどれも RTK fix の地図作成と較正が前提。
- AI の記録漏れ 2 件: ntp_server の扱い（第40便）と NTRIP v1・TLS なしの問い（第66便）を台帳に登録していなかった。今回 DEC-296・298 として登録した。

## 3. 行ったこと

- 提案 `proposals/gnss_improvements_2026-10-22.md`（現状の表、依存の鎖、すぐ確かめること、小さな実装 A〜F、後の設計、承認事項）。
- REV-157: DEC-294〜298（pending）、G-GNSS-NO-HEADING の next_action に追記。番号は reserve_ids.py で予約（REV-157、DEC-294〜298、第128便）。
- コード・設定・受信機には触れていない。

## 4. 検査

- `apply_revision.py REV-157`、`run_checks.py`（31a6e1d ＋ 作業ツリー）: 設計検査 違反 0・未判定 5。移行の検査の違反は 6 件（第127便の時点と同じ）。単体の試験: 未実行（コードの変更なし）。

## 5. 次

- 人の判断: DEC-294〜298。人の作業: 受信機を VM につなぎ、屋外で方位と RTK を 1 回で確かめる（提案 §2.1）。commit はしていない。
