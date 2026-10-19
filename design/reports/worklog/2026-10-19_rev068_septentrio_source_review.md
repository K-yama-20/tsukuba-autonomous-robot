# 作業記録 2026-10-19 第36便: 上流ドライバのソースの確認（人の指示の順序の手順 1、REV-068）

## 読んだもの

- コミット `2ce59ea3eb892b4a430f7f38f179b13aab4c37c9` ＋ 未コミットの REV-060〜067。
- 上流 septentrio_gnss_driver tag v1.4.8（commit 5613af2969e3f4aac4ddc0b819e773d43a71ce9b）を AI の作業領域に clone（build・実行なし）。VM の Boost 1.83 の posix_serial_port_service.ipp。
- 人の資料 `reports/mosaic-G5_P6_取扱上の注意事項.md`（ワークスペース）。

## 1. 人の指示（原文は会話。手順の表）

1. 上流ドライバのソースで、シリアルの開き方と configure_rx が書くストリーム・Boot 保存の有無を調べよ。 2. PRM-65 を if00 に決める（人の承認が必要） 3. ブランチの commit と VM の更新を決める 4. 屋外でアンテナに空を見せて、単独測位と方位 5. NTRIP（案 B）で RTK fix 6. 較正の走行と実データでの検証。人の連絡: ドライバは VM に入れた。起動は一度も行っていない。

## 2. 結果（FILE-SEPTENTRIO-SOURCE-REVIEW）

- シリアル: Boost の open が cfmakeraw（エコー・行単位の入力を外す）。ドライバがフロー制御なし・8N1 を設定。
- configure_rx true: 起動のたびに `sso, all, none, none, off`・`sno, all, none, none, off` で受信機の全出力を止め、Stream1 から自分の SBF を作り、`sntp, on` など、最後に `eccf, Current, Boot` で Boot に保存。終了時は補正の接続と GGA のストリームと主接続先の出力を戻すが、SBF のストリームと Boot の内容は残る。
- 接続の最初のエスケープの列 `\rSSSSSSSSSS\r\r` は configure_rx に関係なく送る。
- gnss の種類では TF から主→副の方位・仰角のオフセット（sto）だけ。主アンテナの位置は補正しない。/config の取付が UNKNOWN だとオフセットは 0 度。
- 案 B は rtk_settings.serial_1（例 USB2）で、補正の入力と GGA の出力を受信機に設定する（configure_rx true のときだけ）。

## 3. 承認事項

- DEC-140（新規）: configure_rx を使うか。推奨は false（受信機の設定と Boot 保存は人の手順で）。ドライバの最初の起動（手順 4）の前に決める必要がある。
- 手順 2（PRM-65 を if00）は人の承認待ち。

## 4. 検査

- 全検査（REV-068 適用後）: 終了コード 1、不合格は人の drawio だけ。設計整合性 違反 0、未判定 4。
- 製品のコードは変えていないので単体試験は再実行していない。

## 5. 次

- 人の承認: PRM-65（手順 2）、DEC-140、手順 3（commit と VM の更新）。
- commit はしていない。
