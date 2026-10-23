# 作業記録 2026-10-22 第129便: GNSS が衛星を追尾しない件の調べ（REV-158）

## 読んだもの

- コミット `31a6e1d` ＋ 作業ツリー。status.md（第128便）、`reports/worklog/2026-10-22_bin114_sensor_status.md`（屋外の確認）、`research/vehicle_pc/2026-10-19_gnss_first_start.txt`・`2026-10-19_gnss_outdoor_check.txt`・`2026-10-19_mosaic_mrtk_query_followup.txt`・`2026-10-20_gnss_driver_indoor_check_dualant.txt`、`gouda_core/gouda_core/gnss_config.py`、VM のドライバの params（rtk_settings の部分、秘密は無い）と ROS の message の一覧（読むだけ）。

## 1. 人の指示（原文）

- 「以前屋外試験を行ったが、衛星測位は一切出来なかった。プログラムに問題があるのだと思う。徹底的に調べよ。君が分からないことを勝手に仮定をおいて実装していたりはしないか？」

## 2. 結論（記録 FILE-GNSS-NO-TRACKING-INVESTIGATION）

- 受信機は衛星の信号を 1 つも受けていない（MeasEpoch n 0、時刻不明）。屋外でも同じ。
- 2026-10-19 朝は屋内で衛星 13〜17 を捕まえていた。捕まえなくなったのは、AI が勧めて行った DualAnt と reset（DEC-145・146）の後から。
- Gouda のコード（ドライバの設定の差し込み、`sto`、中継、rtk_settings.serial_1）が追尾を止めている証拠はない。10-20 の観測 0 の時点では中継も serial_1 もまだ無かった。
- 最も疑わしいのは DualAnt。Hardware Manual §4.2.3.2 の条件（利得 35 dB 未満、2 本の差 5 dB 以内）を AI は確かめずに勧めた（推測、未確認）。
- AI の誤り（原因の分類: 試験の判断の誤り・確かめていない仮定）: 2026-10-20 に観測 0 を「屋内だから（期待どおり）」と書いた（REV-083）。同じ屋内で 10-19 は衛星を捕まえていたので、ここで異常に気づくべきだった。
- 確かめずに置いた仮定を 5 つ挙げた（記録 §6）。

## 3. 行ったこと

- 調べの記録、REV-158（DEC-299〜302 pending、G-GNSS-NO-HEADING の next_action に追記）。番号は reserve_ids.py で予約（REV-158、DEC-299〜302、第129便）。
- 受信機は VM につながっていない（触れていない）。コード・設定は変えていない。

## 4. 検査

- `apply_revision.py REV-158`、`run_checks.py`（31a6e1d ＋ 作業ツリー）: 設計検査 違反 0・未判定 5。移行の検査の違反は既存の 6 件。単体の試験: 未実行（コードの変更なし）。

## 5. 次

- 人の確認: 10-19 の後にアンテナ・ケーブルを替えたか。
- 人の判断: DEC-299（T1 読むだけ）→ DEC-300（T2 Nominal に戻す）、DEC-301（caster の確かめ）、DEC-302（改善）。commit はしていない。
