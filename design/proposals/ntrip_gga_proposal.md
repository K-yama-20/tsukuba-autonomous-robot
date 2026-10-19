# DEC-139（ネットワーク RTK の受け方）と GGA の出し方の提案（第1版。実装は承認の後）

状態: 提案。2026-10-19。人の指示（DEC-140 の回答）「GGA の出し方は DEC-139 と一緒に提案すること」による。

前提（確かめた事実）:
- 補正は Point One の TrueRTK（NTRIP、truertk.pointonenav.com、有料。DEC-125）。
- mosaic-go は VM に USB で、シリアルの 2 本だけ（if00 = USB1、if02 = USB2）。USB イーサネットはない（2026-10-19、VM で確認）。受信機の中の NTRIP の機能はインターネットに出られないので使えない（DEC-139 の案 A は今の接続では不可）。
- configure_rx は true（DEC-140）。ドライバは主接続先 USB1 で SBF を受け、`rtk_settings.serial_1` を書けば、受信機の別の接続先（例 USB2）で補正を受け、そこへ GGA を出す設定もする（FILE-SEPTENTRIO-SOURCE-REVIEW §5: `sdio, USB2, <rtk_standard>, +SBF+NMEA` と `sno, StreamN, USB2, GGA, <周期>`、send_gga が auto なら sec1）。
- VM の apt に RTKLIB（rtklib 2.4.3.b34、str2str を含む）と ros-jazzy-ntrip-client 1.4.1 がある（未導入）。

## 1. 推奨: 案 B1（ドライバが USB2 を補正の入力・GGA の出力にし、PC の str2str が NTRIP と USB2 を中継する）

```
Point One caster ──RTCM──► str2str（PC）──RTCM──► /dev/serial/by-id/...-if02（受信機の USB2: 補正の入力）
                 ◄──GGA───           ◄──GGA───  （受信機が USB2 に出す GGA、1 秒ごと）
受信機の USB1（/dev/serial/by-id/...-if00）──SBF──► septentrio_gnss_driver（ND-19）
```

- **GGA の出し方**: 受信機が USB2 に GGA を出す（ドライバの `rtk_settings.serial_1.send_gga: auto` → `sec1`）。GGA は受信機の今の位置なので、ネットワーク RTK（仮想基準点）の caster が必要とする位置になる。PC は GGA を作らない（Gouda が位置を作り替えない）。
- **中継**: RTKLIB の `str2str -in ntrip://<ユーザ>:<パスワード>@<caster>:<ポート>/<マウントポイント> -out serial://<USB2 の by-id>:<baud> -b 1`。`-b 1` は出力（シリアル）から受けたバイトを NTRIP の入力へ返す設定で、GGA を caster に送る。
- **Gouda への組み込み**（承認の後に設計）: sensor supervisor が GNSS のドライバの後に str2str を子プロセスとして起動し、USB2 の by-id の名前で見張る（DEC-141 の規則）。接続先・認証は公開しないファイル（`<data_root>/config/gnss_rtk.yaml`）から読む。RTK の状態は PVTGeodetic の mode で monitor に出る（実装済み）。
- **ドライバの設定に足すもの**（gnss_config の差し込み）: `rtk_settings.serial_1: {port: USB2, rtk_standard: <RTCMv3 か auto>, send_gga: auto, keep_open: <true か false>}`。keep_open が false なら、ドライバの終了で USB2 の補正の入力と GGA のストリームが戻される。

利点: Gouda の独自のコードは子プロセスの起動と見張りだけ。GGA は受信機が出し、補正は受信機が使う（RTK の計算は受信機）。RTKLIB は広く使われている（intent 82 行の OSS の扱い）。

注意:
- str2str の引数にパスワードが入り、同じ PC の利用者からはプロセスの一覧で見える（車載 PC は一人で使う前提。気になる場合は別の方法を検討）。
- USB2 を開くのは str2str だけにする（資料 §7）。ドライバが起動のたびに受信機の全出力を止めるので、今 USB2 に流れている NMEA はドライバの起動の後は GGA だけになる。
- 未確認（**原本未照合**）: RTKLIB の `serial://` の path の書き方（/dev/ の後ろを書く形か）と、開いたポートを raw にするか（導入の前に RTKLIB のソースで確かめる）。Point One のポート・マウントポイント・GGA の要否・RTCM の版（人の契約の資料で確かめる）。

## 2. 代わりの案

| 案 | 内容 | 評価 |
|---|---|---|
| B2 | ros-jazzy-ntrip-client（ROS の node）で NTRIP を受け、RTCM を ROS の topic に出す。GGA はドライバの NMEA の topic から渡す。RTCM を USB2 へ書く node は独自に作る | 独自の node が要る。ドライバは RTCM を ROS の topic から受けない（ソースの確認の範囲） |
| C | 受信機の USB イーサネットを有効にできるか調べ、PC から NAT でインターネットに出して受信機の中の NTRIP を使う（ドライバの rtk_settings.ntrip_1） | 受信機に USB イーサネットの設定があるかは未確認。PC の転送の設定（sudo）が要る。GGA は受信機が直接送る |
| A | 受信機の中の NTRIP（今の接続） | 不可（インターネットに出られない） |

## 3. 承認していただきたいこと

| 項目 | 内容 | 推奨 |
|---|---|---|
| DEC-139 | 案 B1（ドライバが USB2 を補正の入力・GGA の出力にし、str2str が中継）にする | 承認 |
| （B1 を承認した場合） | rtklib を setup.sh の apt に加える、sensor supervisor が str2str を起動する（新しい子プロセス）、gnss_rtk.yaml の書き方を NTRIP の接続先・認証の形にする、gnss_config に rtk_settings.serial_1 を差し込む | 承認の後に設計と実装（それぞれ許可を得る） |
| 実測・確認 | Point One の接続の情報（ポート、マウントポイント、GGA の要否、RTCM の版） | 人の契約の資料で確かめ、gnss_rtk.yaml に人が書く |

## 4. 最初の起動の前後の記録（DEC-140 の回答の指示）

- 道具 `python3 -m gouda_core.septentrio_query --port <by-id> --label before_first_start --out <file> --reply-wait-s <秒>`（照会だけ: `lif,Identification`・`gso`・`getDataInOut`）。資料 §2・§4・§7 に沿う（by-id の名前だけ、他のプロセスが開いていれば送らない、raw・エコー無効を読み直してから送る、最初に CR、受信を先に始める、応答で判定）。
- 照会は USB2（資料の勧め）で行う。起動の前（Gouda もドライバも止めた状態）と、起動の後（ドライバが USB1 を使っている間に USB2 で）に 1 回ずつ。起動の後の USB2 は、B1 を入れるまでは誰も開いていない。
- 実行は人の許可の後（受信機のポートに触るため: DEC-141 の 3）。待ち時間の値は実行する人が与える。
