# 作業記録 2026-10-19 第40便: GNSS のドライバの最初の起動、起動の後の記録、測位と方位の確認（REV-073）

## 読んだもの

- コミット `33416021655e587d0ae5f2c949d9bf81698ef44e`（このブランチの HEAD、origin に push 済み）。VM の ~/gouda_ws も 3341602（人が更新）。

## 1. 人の指示

「VMは更新した。次に進め」→ 手順 4（屋外で単独測位と方位を確かめる）に進んだ。起動の後の記録は DEC-140 の回答の指示（「最初の起動の前後で gso と getDataInOut を記録すること」）による。

## 2. 実行（VM）

1. 確認: ブランチ 3341602、build に by-id の検査・static TF・ND-08 の中継がある、Gouda は動いていない、受信機のポートの使用者なし、/config に GNSS のアンテナの位置なし（方位のオフセットは 0 度で送られる）。
2. `bash gouda.sh start`（12:57:58）。sensor supervisor: GNSS のドライバの設定を書き（gnss_rtk.yaml なし: 補正なし）、by-id の名前 → ttyACM0 usb 3-7 でドライバを起動。ドライバ: USB1 で接続、Setting up Rx、**`$R? sntp, on : Invalid command!`**、Setup complete。Nav2 は未確定の値のため起動せず（記録どおり）。
3. 起動の後の記録（USB2、1 秒）: fuser では ttyACM0 をドライバだけが使用。lif・gso・getDataInOut とも受理。gso は Stream1（USB1、GALAuthStatus+ReceiverStatus+ReceiverSetup+QualityInd+RFStatus、msec500）、Stream3（USB1、MeasEpoch+AttEuler+PVTCartesian+PosCovCartesian+PVTGeodetic+PosCovGeodetic+VelCovGeodetic+DOP+ChannelStatus+AttCovEuler、msec100）、ほかは off。getDataInOut は起動の前と同じ。USB2 の NMEA は止まった（ドライバが全出力を止めたため）。
4. 測位と方位（ROS の topic を 25 秒）: PVT mode 1（単独）250/250、衛星 13〜17、h_accuracy 1106（約 11 m）。AttEuler mode 0・error 1 が 249/249、heading NaN、cov_headhead NaN。navsatfix の status 0。

## 3. 分かったこと

- ドライバの SBF の構成はソースの読み（FILE-SEPTENTRIO-SOURCE-REVIEW、DEC-140 の材料）のとおり。GALAuthStatus は雛形の osnma の設定（loose）による。
- 受信機は `sntp, on` を受け付けない（ファームウェア 1.1.1）。Gouda は受信機の NTP を使わないので影響は小さいと見るが、起動のたびに ERROR が出る。雛形の ntp_server を false にするかは承認事項（設定の変更）。
- 方位が出ない（G-GNSS-NO-HEADING）。屋内で受信が弱い。屋外での確認が要る。

## 4. 状態

- **Gouda は VM で動いたまま**（GNSS のドライバも動いている）。止めるのは `bash gouda.sh stop`。
- ドライバは Boot に保存したはず（ソースの読み。起動のログには出ない）。

## 5. 検査

- 全検査（REV-073 適用後）: 終了コード 1、不合格は人の drawio だけ。設計整合性 違反 0、未判定 4。

## 6. 次

- 人: 屋外で両方のアンテナに空を見せる（手順 4 の残り）。その時に AI が同じ確認（測位の種類・衛星数・方位）を行う。
- 承認事項（新規の提案）: 雛形の ntp_server を false にする（sntp の ERROR をなくす）。
- DEC-139（案 B1）は回答待ち（手順 5）。
- commit はしていない（この便の分）。

## 7. 追記: 屋外での確認（REV-074、FILE-GNSS-OUTDOOR-CHECK）

- 人の連絡: 「アンテナを屋外で空が開けた場所に出した。測位と方位をもう一度確かめて」。Gouda とドライバは動いたまま（同じ pid、同じ USB1）。受信機のポートには触らず、ROS の topic だけを読んだ。
- 60 秒: 単独測位 600/600、衛星 16〜21、h_accuracy 520〜1401（中央値 641、約 6.4 m）。方位は 599/599 が mode 0・error 1、方位の衛星数なし。
- 10 秒の MeasEpoch: 観測はすべてアンテナ番号 0（主）。副アンテナ（番号 1）の観測は一つもない（番号の読み方は SBF の定義で原本未照合）。主アンテナの C/N0 の中央値 約 41.5 dB-Hz。
- ドライバのログに「Multi antenna requested but Rx does not support it.」の警告はない（sga, MultiAntenna は送られたと見る）。
- 結論（事実の範囲）: 方位が出ないのは、副アンテナの観測がないため。空の見え方だけの問題ではない。原因（接続・給電・受信機の型や許可・設定）は未確定（G-GNSS-NO-HEADING）。
- 全検査（REV-074 適用後）: 終了コード 1、人の drawio だけ。
