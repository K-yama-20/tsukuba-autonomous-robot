# 作業記録 2026-10-20 第54便: 案 B1 の段 2 の設計の案（REV-088）

## 読んだもの

- コミット `3341602` ＋ 未コミットの REV-073〜087。status.md（第53便）、`gouda_core/gouda_core/gnss_config.py`、雛形 `design/research/upstream_sensors/septentrio_gnss_driver_1.4.8/gnss.yaml` の rtk_settings、FILE-SEPTENTRIO-SOURCE-REVIEW §5、PRM-65。

## 1. 人の指示（原文）

- 「段 2 の設計（gnss_rtk.yaml の書式と、追加する PRM の案）を示せ。実装はまだしない。」

## 2. 行ったこと

- 提案 `proposals/ntrip_gga_proposal.md` §8: gnss_rtk.yaml の書式（ntrip の節の 5 項目、検証、権限、旧い書式の扱い）、ドライバに渡す値（serial_1.port だけ Gouda が書く、他は雛形のまま）、中継が使う値、gnss_config の変更の範囲、承認事項。
- REV-088: DEC-154（pending）。番号は reserve_ids.py で予約（REV-088、DEC-154、第54便）。PRM は承認の後に正本に足す（今は足していない）。
- 自律判断: 誤りのときに止めるのは中継だけで、ドライバは補正なしで起動する案を推奨にした（単独測位は使えるため）。例の値はすべて架空（example.invalid）。

## 3. 検査

- `apply_revision.py REV-088`、`run_checks.py`（3341602 ＋ 作業ツリー）: 設計検査 違反 0・未判定 4。移行の検査の違反は人の drawio と .DS_Store だけ。単体の試験: 未実行（コードの変更なし）。

## 4. 未確認

- Point One のポート・マウントポイント・GGA の要否・RTCM の版・NTRIP の版（原本未照合）。

## 5. 次

- DEC-154 の回答待ち。その後に段 2 の実装の許可を求める。commit はしていない。
