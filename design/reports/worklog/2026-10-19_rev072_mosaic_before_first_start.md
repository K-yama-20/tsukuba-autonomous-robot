# 作業記録 2026-10-19 第39便: 最初の起動の前の受信機の記録（REV-072）

## 読んだもの

- コミット `2ce59ea3eb892b4a430f7f38f179b13aab4c37c9` ＋ 未コミットの REV-060〜071。人の資料 §2・§4・§7。

## 1. 人の許可（DEC-142 に原文）

「起動の前の記録を USB2（if02）で取ってよい。待ち時間は 1 秒とする」

## 2. 実行（VM、~/gouda_fix_ws の作業ツリー）

- 前に確かめたこと: by-id の名前（if00 → ttyACM0、if02 → ttyACM1）、Gouda・ドライバ・launch のプロセスなし、`fuser -v` で使用者なし。USB2 の端末の設定は既定（icrnl・ixon など）だった。
- コマンド: `python3 -m gouda_core.septentrio_query --port /dev/serial/by-id/usb-Septentrio_Septentrio_USB_Device_0100012541-if02 --label before_first_start --out ~/gnss_records/2026-10-19_before_first_start.json --reply-wait-s 1`
- 結果: 送る前の端末の設定の読み直しで echo・icanon・icrnl・ixon・ixoff・opost がすべて無効。CR は error（下記）、lif,Identification は `$R;`、gso と getDataInOut は `$R:` で受理。受信 11073 bytes。実行の後もポートは raw のまま（資料 §2: 開くプログラムが毎回設定する）。

## 3. 分かったこと（FILE-MOSAIC-BEFORE-FIRST-START）

- gso: Stream1（COM1）・Stream2（COM2）・Stream3（USB2）は MeasEpoch など 15 の block の組で off。Stream4〜10・Res1〜4 は none・off。2026-10-17 の人の調査の Stream4（USB1/Support/sec1）は残っていない（Boot に保存していなかったため、と推測。電源の再投入の有無は不明）。
- getDataInOut: DSK1 off、COM1・COM2・USB1・USB2 は入力 auto・出力 SBF+NMEA（on）。
- 受信機: mosaic-G5 P6、serial 0100012541、ファームウェア 1.1.1（260612）。
- 最初の CR で `$R? GNGGA,…: Invalid command!`: 受信機のコマンドの入力に GGA の断片が残っていた。NMEA が以前に受信機へ送り返されていたことを示す。2026-10-19 に AI が raw にせずに cat で読んだこと（資料 §2）と整合するが、原因と断定はできない。受信機は無効なコマンドとして捨てたので、設定は変わっていない（gso・getDataInOut の内容で確認）。
- USB2 の NMEA では単独測位（GGA の品質 1、衛星 18）。位置を含むため、リポジトリの写しからは NMEA を除き、生の記録は VM の ~/gnss_records/ にだけ置いた。

## 4. 検査

- 全検査（REV-072 適用後）: 終了コード 1、不合格は人の drawio だけ。設計整合性 違反 0、未判定 4。
- 製品のコードは変えていない。

## 5. 次

- 人の手順 3（commit と VM の更新）→ 最初の起動 → 起動の後の記録（改めて許可を得る）。
- DEC-139（案 B1）は回答待ち。
- commit はしていない。
