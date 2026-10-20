# 作業記録 2026-10-19 第45便: mosaic-G5 P6 のデュアルアンテナの方法の調査

## 読んだもの

- コミット `33416021655e587d0ae5f2c949d9bf81698ef44e`。status.md（第44便まで）、`research/vehicle_pc/2026-10-19_mosaic_mrtk_query.txt`。

## 人の指示

「p6でdual antennaをやる方法を徹底的に調査せよ。複数エージェントを起動しても良い。…」（ROS ドライバと製品ページの URL を添えて）

## 実行

- 調査 AI 3 体（ROS ドライバ、公式文書、販売店・コミュニティ）を並行で起動。読むだけ。受信機・VM には触れていない。
- AI が内蔵ブラウザで Septentrio のサポート記事（customersupport.septentrio.com）を読んだ。septentrio.com の製品ページは Cloudflare の人の確認で止まり、操作していない。
- Hardware Manual v2.0.0 の該当箇所（§4.2.3.2、Appendix C、§7.2.2、改版履歴）を AI が pdftotext で照合した。

## 成果物

- `design/research/gnss_mosaic_g5_p6_dual_antenna_survey_2026-10-19.md`

## 分かったこと（要点）

- P6 はデュアルアンテナの方位に対応するが出荷時は無効。setFrontendMode DualAnt → Boot 保存 → reset で有効（公式のサポート記事・Hardware Manual v2.0.0）。第43〜44便の手順と同じ。
- ROS ドライバ・ArduPilot・PX4 は setFrontendMode を送らない。
- 条件: 前置増幅 15〜35 dB（AGC 30〜50 dB）、2 本の差 5 dB 以内、ANT_2 を空けない。

## 自律判断

- なし（記録だけ。正本・設定・コードは変えていない）

## 承認・実測待ち

- 屋外の確認（第44便の次の作業のまま）。
- 実測: アンテナの利得とケーブルの損失（AGC の値で確かめる）、/config の主・副アンテナの位置。

## 検査・試験

- 未実行（正本を変えていないため）。

## 残るリスク

- firmware 1.1.x の Reference Guide は未入手（Nominal の意味は原本未照合）。
- /config にアンテナ位置がない間、方位のオフセットは 0 で送られる。

## 次

- 人: 屋外で Gouda を起動し、AI が調査記録 §5 の項目を確かめる。必要なら人が septentrio.com から firmware 1.1.x の Reference Guide を取得する。

## 追記 2026-10-20: 原本との照合

- 人が Septentrio から取得した資料を渡した（Reference Guide v1.1.1、P6 Release Notes v1.1.1、Hardware Manual v2.0.0、データシート、firmware 一式）。AI は作業領域に写して pdftotext で読んだ（リポジトリには入れない。SHA-256 は記録 §7）。
- setFrontendMode（RG v1.1.1 §3.2.4 p.98）: Nominal は「普通は SingleAnt、方位が主目的の製品では DualAnt」。→ P6 の Nominal は単一アンテナの意味（第41便の推測を原本で確認、原本未照合を解消）。DualAnt・Boot 保存・reset の手順は記述どおり。
- §1.11（p.26〜27）: 既定は main が後ろ・aux1 が前。直角なら setAttitudeOffset ±90。sga の引数は v1.0.1 に MovingBase が加わっただけ。
- Release Notes: frontend mode・デュアルアンテナの変更はない。firmware の更新は不要。
- 更新: 記録 §6・§7。検査は未実行（正本を変えていない）。受信機・VM には触れていない。

## 追記 2026-10-20: アンテナの利得の事前確認は行わない

- 人の発言（原文）: 「アンテナは動作確認済み品をレンタルしているから、調べる必要ないと思う」
- 対応: 型番・ケーブルからの事前の確認はしない。屋外の確認で ReceiverStatus の AGC（main・Aux1）を読むことは残す（追加の作業なしで同時に見られるため）。

## 追記 2026-10-20: 開発のセッションへの共有

- 人の指示（原文）: 「configにgnssの設定値を記録した。主な開発は別のチャットで行っているが、そっちはrtklibを使おうとしているらしい。mosaic-goの使い方も分かっていない。全部教えてやってくれ。」
- 読んだもの: VM の ~/gouda_ws/gouda_data/config/sensor_config.json（読むだけ。config_revision 18）。main (0.45, 0.17, 0.77)、aux1 (0.45, −0.17, 0.77) m → 左右に 0.34 m。DEC-130 の「0.6 m」と合わない（人に確認が要る）。
- 成果物: `design/research/mosaic_go_g5_p6_usage_guide_2026-10-20.md`。開発のセッション（Global localization/Navigation ノード検討）に SendMessage で要点と場所を送った（情報の共有で、承認ではないと明記）。
- 検査は未実行（正本を変えていない）。受信機には触れていない。

## 追記 2026-10-20: アンテナ間隔の人の確認（REV-080、DEC-149）

- 人の回答（原文、AI が示した選択肢の文）: 「現在の車体のアンテナ間隔は 0.34 m で、config の値が正しい。DEC-130 の 0.6 m は古い値。」
- 変更セット `design/revisions/REV-080.yaml`（DEC-149 confirmation。DEC-130 は書き換えない）を `design/.venv/bin/python design/tools/apply_revision.py REV-080` で適用（終了コード 0）。render_views・generate_params・render_migration_review を再実行（いずれも 0）。
- 全検査 `design/.venv/bin/python design/tools/run_checks.py`（作業ツリー、HEAD 3341602 ＋未 commit の変更）: 終了コード 1。設計検査 合格 13・違反 0・未判定 4。input_integrity の不一致は design/docs/SystemArchitecture.drawio（人が編集中）と extraction の .DS_Store だけで、migration_validator・migration_tests の不合格もこれによる（第41便と同じ原因）。
- ガイドの §4・§6 を更新し、開発のセッションに連絡。
