# 第114便：VM のセンサーの状態（LiDAR の待機、GNSS とネットワーク RTK）

日付：2026-10-22

## 読んだもの

- コミット `a27de9e`（main）。VM の `~/gouda_ws` は a86a7d0 で、Gouda は人が起動したもの（止めていない）。

## 人の指示（原文）

- 「センサ状態を確かめて。network rtkが使えているかどうかも知りたいし、lidarのデータが届いていないのではないかと心配。」

## 確かめたこと（読むだけ。機器の設定は書き換えていない）

- LiDAR（XT-32）
  - USB-LAN の口 enx6c6e0754b24a に 192.168.1.100/24 があり、192.168.1.201 への経路もこの口。ping は応答あり。ドライバは PTC につながった（ptc connect success）。
  - 確認を始めた時点では、点群が届いていなかった。口に届くパケットは 10 秒で 11 個だけだった。
  - XT-32 の Web の API（GET だけ）で、`standbymode: 1`（待機）、`lidar_mode: 1`。設定の宛先は DestIp 192.168.1.100、DestPort 2368 で、PRM-51・52 と一致。
  - 記録済みの設定（DEC の note、Pandar Console の PDF）は「Standby Mode In Operation」。Gouda のコードと Hesai ドライバの設定（standby_mode −1）は待機を切り替えない。誰が待機にしたかは分からない。
  - その後（1792595723 から）、`standbymode: 0` になり、点群が届きはじめた（10 Hz、1 フレーム 64000 点、250 パケット）。monitor では points が RECEIVED。この切り替えは Claude ではない（GET だけ）。
- IMU：RECEIVED。
- GNSS（Septentrio、ROSaic 1.4.7）
  - ドライバは動いていて、pvtgeodetic・measepoch などが出ている。
  - measepoch は n 0（追尾している衛星の信号 0）、tow・wnc は不明。pvtgeodetic は mode 0、error 1（測位なし、測定が足りない）。そのため navsatfix は出ず、monitor では gnss が NOT_RECEIVED。
  - 屋内か、アンテナが接続されていない可能性（推測、未確認）。
  - 起動のとき、ドライバが「Invalid command just sent to the Rx!」を 2 回出した（受信機の応答の中身は、秘密を含みうるので読んでいない）。
- ネットワーク RTK（NTRIP の中継、ND-19）
  - gnss_rtk.yaml はあり（中身は読んでいない）。中継は起動している。
  - 状態は起動のときから変わらず、入力（caster）は waiting、出力（受信機の ttyACM1）は connected、受け取った量は 0 バイト。
  - 補正は届いておらず、ネットワーク RTK は使えていない。測位がない（GGA を送れない）ことが原因の候補（推測）。caster への接続そのものは確かめていない。

## 追加の確認（人がアンテナを空の見える所に出した後）

- 人の指示（原文）：「GNSS のアンテナを空の見える所に出した。測位とネットワーク RTK をもう一度確かめて。」
- 1792595915〜918 に、Septentrio と IMU の USB が付け直された（monitor の記録：device_absent、device_reconnected）。GNSS のドライバと NTRIP の中継は、sensor supervisor が自動で再起動した。IMU も再起動し、受信を続けている。
- 付け直しの約 70 秒後と約 155 秒後（1792596073）に確かめた。
  - measepoch は n 0（追尾している信号 0）、tow・wnc は不明のまま。
  - pvtgeodetic は mode 0、error 1（測位なし）。navsatfix は出ていない。
  - rfstatus は、1188 MHz と 1252.5 MHz の帯の干渉の記録（info 2・66）だけ。aimplusstatus は interference 1（干渉を検出）。
- NTRIP の中継は、入力が waiting、出力が connected、補正は 0 バイトのまま。ネットワーク RTK は使えていない。
- 空が見えれば数十秒で信号を捕まえるのがふつうなので、アンテナの信号が受信機に届いていない可能性が高い（推測）。候補は、ケーブル・コネクタ、MAIN と AUX の差し違い、受信機からのアンテナへの給電。確かめるには、人が配線を見るか、受信機の Web 画面を見る。

## 受信機の USB の確認と、VM の再開の後（2026-10-22 00:2x〜00:45）

- 受信機を Mac につないだときも、USB の中身はシリアルポート（CDC ACM）2 つだけで、ネットワーク用の部分（RNDIS・ECM・NCM）はなかった。`http://192.168.3.1/` は応答なし。VM と Mac で同じなので、受信機が USB のネットワークを出していない（設定か版かは未確認）。
- その間、VM は一時停止していた（Claude は止めていない）。人が VM を再開した後の状態は次のとおり。
  - `~/gouda_ws` は a27de9e。
  - USB-LAN（cdc_ncm）は結び付いた。口は UP で、192.168.1.100/24。
  - 00:44〜00:45 に確かめた。carrier は 1 だが speed は 0。192.168.1.201 は ARP が失敗（FAILED）し、ping は応答なし。5 秒間に届いたパケットは 0。XT-32 から何も届いていない。
  - Septentrio は Mac につながったまま（Connected-To-Vm NO）。
  - Gouda は動いていない（gouda.sh status は not running）。launch のログの最後は 00:28:59 の停止。

## 人が接続を直し Gouda を起動した後（1792597609〜1792597694）

- Gouda は running。センサーの機器は 4 つとも VM にある。sensor supervisor が、付け外しの後に各ドライバを起動し直した記録がある（XT-32 は停止に SIGTERM の後 5 s かかり、強制に進んだ記録もある）。
- XT-32：192.168.1.201 は ping で応答あり。リンクは 1000 Mb/s。5 秒で 12510 パケット（約 10 Hz × 250）。standbymode は 0。monitor の points は RECEIVED。
- IMU：RECEIVED。
- GNSS：ドライバの起動から約 33 秒後と約 85 秒後に確かめた。measepoch は n 0、tow は不明のまま。pvtgeodetic は mode 0、error 1。navsatfix は出ず、monitor は NOT_RECEIVED。
  - 干渉の記録は 1252.5 MHz と 1202.8・1203.5 MHz で、1584 MHz（L1 の近く）は出ていない。それでも信号は 0 なので、L1 の近くの干渉だけでは説明できない（推論）。
- NTRIP：入力は waiting、出力は connected、0 バイト。ネットワーク RTK は使えていない。

## 実行した検査・試験

- 上の確認だけ（読むだけ）。設計検査・単体試験は未実行（コードと正本は変えていない）。

## 残るリスク

- XT-32 が、知らないうちに待機になることがある（原因不明）。待機の間は、ドライバも monitor も、点群が来ないことしか分からない。
- GNSS の起動のときの「Invalid command」の中身は未確認。

## 次の作業

- 人の作業：GNSS のアンテナを空の見える所に出す（または接続を確かめる）。測位が出た後に、NTRIP の入力が connected になり、補正の量が増えるかを確かめる。
- 人の判断：XT-32 の待機の原因を調べるか。起動のときに待機を確かめて記録・警告する仕組みは提案（承認事項）。
