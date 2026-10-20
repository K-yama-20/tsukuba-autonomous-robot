# 作業記録 2026-10-19 第38便: DEC-140 の回答（configure_rx true）、起動の前後の記録の道具、DEC-139 と GGA の提案（REV-070・071）

## 読んだもの

- コミット `2ce59ea3eb892b4a430f7f38f179b13aab4c37c9` ＋ 未コミットの REV-060〜069。
- 人の資料 `reports/mosaic-G5_P6_取扱上の注意事項.md` §2〜§7。上流ドライバの確認（FILE-SEPTENTRIO-SOURCE-REVIEW）。
- VM の apt: rtklib 2.4.3.b34+dfsg-1build2、ros-jazzy-ntrip-client 1.4.1（どちらも未導入。apt-cache policy で確認だけ）。

## 1. 人の回答（DEC-140 に原文）

「DEC-140 は true。受信機の設定は Gouda（ドライバ）が持つ。注意事項 §5・§6 は手での調査の規則として残す。最初の起動の前後で gso と getDataInOut を記録すること。GGA の出し方は DEC-139 と一緒に提案すること。」

## 2. 変更

| 変更 | 内容 |
|---|---|
| REV-070 | DEC-140 を回答済み（原文）、PRM-74（configure_rx）を承認値 true に。generated/params/septentrio_gnss_driver.yaml に device と configure_rx がそろった |
| `gouda_core/gouda_core/septentrio_query.py`（新規） | 起動の前後の記録の道具。照会だけ（lif,Identification・gso・getDataInOut）、by-id の名前だけ、他のプロセスが開いていれば送らない、raw・エコー無効・フロー制御なしを読み直してから送る、最初に CR、受信を先に始める、送受信の生のバイトを時刻つきで JSON に残す、応答（$R: / $R; / $R?）で判定。待ち時間は実行する人が与える |
| `gouda_core/test/test_septentrio_query.py`（新規 3 件） | 疑似端末を受信機の代わりに |
| REV-071 | TS-35 の手順の追記、DEC-139 の note（推奨を案 B1 に見直し） |
| `design/proposals/ntrip_gga_proposal.md`（新規） | DEC-139 と GGA の出し方の提案 |

## 3. 影響（重要）

- PRM-65・PRM-74 がそろったので、**このブランチの Gouda を起動すると、sensor supervisor が GNSS のドライバを起動する**（configure_rx true: 受信機の全出力を止め、自分の設定を作り、Boot に保存）。VM の ~/gouda_ws は main（7e747b5）のままなので、今の VM の gouda.sh start では起動しない。試験スタック（stack.sh）は septentrio の設定のファイルを除くので起動しない。
- したがって、ブランチを VM に反映して gouda.sh start をした時が「最初の起動」になる。その前に、記録の道具で起動の前の gso と getDataInOut を取る必要がある（人の許可の後）。

## 4. 修正

- 疑似端末の試験が VM（Linux）でだけ失敗した: 受信機の代わりの側が疑似端末の slave を閉じていて、Linux では master の読み出しが EIO で止まった（macOS では止まらない）。分類: 試験の基盤。slave を開いたままにした（合否の基準は変えていない）。

## 5. 試験・検査

- Mac の単体: 180 件 OK・1 件 skip。VM の単体: 180 件 OK・1 件 skip。
- 全検査（REV-071 適用後）: 終了コード 1、不合格は人の drawio だけ。設計整合性 違反 0、未判定 4（DR-04 5、DR-05 2、DR-10 2、DR-11 66）。
- 受信機のポートには触っていない。ドライバは起動していない。

## 6. 承認事項

- DEC-139: 推奨を案 B1 に見直し（提案 ntrip_gga_proposal.md）。B1 を承認した場合の実装（rtklib の導入、supervisor が str2str を起動、gnss_rtk.yaml の形、rtk_settings.serial_1）はそれぞれ許可を得る。
- 最初の起動の前後の記録の実行（受信機のポートに触る）は人の許可の後。

## 7. 次

- 人の手順 3（commit と VM の更新）。その前に、起動の前の記録をいつ取るか（VM の更新の前）を決める必要がある。
- commit はしていない。
