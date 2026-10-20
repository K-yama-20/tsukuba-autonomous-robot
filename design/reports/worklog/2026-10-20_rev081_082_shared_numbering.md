# 作業記録 2026-10-20 第48便: 複数のセッションの番号の重なりの解消と、登録済みの証拠のファイルの修正（REV-081・082）

## 読んだもの

- コミット `3341602` ＋ 未コミットの REV-073〜080（REV-080 は別のセッション）。status.md（REV-080 の時点）、design/tools/apply_revision.py、design/rules/README.md、run_checks.py。

## 1. 人の指示（原文、DEC-150）

- 「この問題を解決せよ」（AI の報告の 2 点を引用: status.md の第45便の重なり、同じ作業ツリーでの REV の番号の取り合い）。

## 2. 行ったこと

- status.md の便を時系列に並べ直した: 第45便 = P6 の調査（別のセッション、そのまま）、第46便 = 運用の条件（REV-079、元の AI の第45便）、第47便 = ガイドとアンテナ間隔（REV-080、元の第46便）。AI の作業記録の見出しも第46便に直した。別のセッションの作業記録には便の番号の見出しがないので触れていない。
- 道具 `design/tools/reserve_ids.py`（新規）: REV は design/revisions/REV-NNN.yaml を、DEC と便は design/reports/reservations/ の印のファイルを O_CREAT|O_EXCL で作って番号を取る。次の番号は使用中の最大＋1。`--no-revision` で DEC・便だけも取れる。
- `apply_revision.py`: 中身が予約の印だけの REV を拒否する（「only reserved」）。
- 試験 `design/rules/test_reserve_ids.py`（5 件: 次の番号、二つ目のセッションは続きの番号、8 スレッドの同時の予約で重ならない、REV なしの予約、書いた変更セットは予約と見なさない）。
- 実際に使った: REV-081・第48便・DEC-150・REV-082 をこの道具で取った。予約だけの REV-081 を apply すると拒否されることを確かめた。
- 別のセッション 2 つ（gnss_localization_submodule 責務設計、btw: dec-131~134の中身）に使い方を送った。

## 3. 修正（見つけた AI の誤り）

- 検査の結果で、REV-075 で登録した証拠のファイル 2 つ（FILE-MOSAIC-MRTK-QUERY、FILE-MOSAIC-DUAL-ANTENNA-NOTE）の SHA-256 が記録と合わない違反が見つかった。原因: 登録の後に AI が追記した（第42〜44便、2026-10-20 の §6）。分類: 実装（記録の手順の誤り）。第42〜45便の報告では、移行の検査の違反を「drawio と .DS_Store だけ」と書いていたが、実際はこの 2 件も含まれていた（違反の一覧を読み直さなかった）。
- 直し方（REV-082）: 2 つのファイルを登録の時の内容に戻した（切り詰めた内容の SHA-256 が記録と一致することを確かめてから）。追記の部分は内容を変えずに新しいファイル `research/vehicle_pc/2026-10-19_mosaic_mrtk_query_followup.txt`（FILE-MOSAIC-MRTK-QUERY-FOLLOWUP）に移して登録し、DEC-144〜146 の resulting_refs をそれに向けた。
- REV-082 の最初の適用で、summary の「分類: 実装」の `: ` が YAML で読めなかった（REV-079 と同じ誤り）。引用符で囲んで適用し直した。

## 4. 検査

- `design/.venv/bin/python design/tools/apply_revision.py REV-081`・`REV-082`、`design/.venv/bin/python design/tools/run_checks.py`（3341602 ＋ 作業ツリー）: 終了コード 1。設計検査 合格 13・違反 0・未判定 4。移行の検査の違反は人の drawio と .DS_Store 2 件だけ（証拠のファイル 2 件は解消）。単体の試験 73 件のうち失敗 1 件（test_real_model。上と同じ移行の違反による）、test_reserve_ids の 5 件は合格。

## 5. 残るリスク

- 道具を使わずに番号を取るセッションがあれば、また重なりうる（記憶と、各セッションへの連絡で周知した）。
- 予約した印（design/reports/reservations/）は消さずに残す（次の番号の計算に使う）。

## 6. 次

- GNSS: 受信機を VM につなぎ直し、屋外で副アンテナと方位の確認。DEC-148（intent.md への追記）の回答待ち。commit はしていない。
