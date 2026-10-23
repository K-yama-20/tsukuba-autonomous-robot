# 作業記録 2026-10-23 第144便: Gouda から見た GNSS の 2 アンテナと NTRIP（ネットワーク RTK）の状態の確認（読むだけ）

## 読んだもの

- 作業ツリー `31a6e1d` ＋ 未コミットの変更（第143便まで）。status.md、第128・129便の記録（GNSS）、`gouda_core/gouda_core/gnss_config.py`・`monitor_core.py`・`monitor_node.py`・`sensor_supervisor_node.py`。
- mosaic-G5 Firmware v1.1.1 Reference Guide（人の手元の PDF、AttEuler ブロック 5938 の Error・Mode の定義を原本で読んだ）。

## 1. 人の指示（原文）

「vmを起動した。goudaの認識でdualanntenaになっているかどうか、nrtkは有効かどうか調査せよ。」

読むだけの調べとして扱った。受信機・Gouda・設定には触れていない（コマンドの送信、再起動なし）。

## 2. 確かめたこと（VM、2026-10-23 19:57〜20:00、epoch 1792753045〜1792753106）

- Gouda は動いていて、モードは手動走行（monitor の /api/state）。受信機は USB でつながっている（/dev/serial/by-id に Septentrio の if00・if02）。ドライバ（septentrio_gnss_driver）と NTRIP の中継（str2str）が動いている（`pgrep -l`）。
- **2 アンテナの設定**: Gouda が作ったドライバの設定（`gouda_data/run/septentrio_gnss_driver.params.yaml`、キーだけを grep）は `receiver_type: gnss`、`multi_antenna: true`、`aux1_frame_id: gnss_aux1_link`、`configure_rx: true`。
- **2 アンテナの実際**: `/sensors/gnss/atteuler` を 1 通読んだ（Gouda の Fast DDS の設定で）: `mode: 0`（向きなし）、`error: 1`、`nr_sv: 255`（Do-Not-Use）、heading は NaN。Reference Guide の AttEuler の定義では、Error の bit 0-1 = 1 は「Main-Aux1 の基線: 測定が足りない（Not enough measurements）」、bit 7（向きを要求していない）は 0。**つまり受信機は 2 アンテナでの向きを計算しようとしているが、副アンテナ（Aux1）側の測定が足りず、向きが出ていない。**
- monitor の GNSS の表示: 「単独測位、衛星 16、水平精度 8.20 m、向きなし」。
- **NTRIP**: 起動の記録（`gouda_data/run/gouda_core.launch.log`）で、ドライバの設定は「ntrip from …/config/gnss_rtk.yaml」（接続の情報が読めた）、中継は ttyACM1（if02）で起動、状態は「input waiting, output connected」（1792752925）。その後 181 秒、状態の変化の記録はない。測位は単独測位のまま。**中継は動いているが、caster からの補正データが届いておらず、RTK は効いていない。**
- VM からインターネットへは届く（https で 200）。gnss_rtk.yaml は所有者だけが読める（-rw-------）。中身は読んでいない。
- 別の観察: ドライバの設定の送信で「`sntp, on : Invalid command!`」が 1 件（受信機がこのコマンドを受け付けない。DEC-296 の ntp_server と関係する可能性。推測）。19:3x ごろに USB が一度外れて付き直した記録（AsyncManager connection lost、中継の device_absent → present）。

## 3. 推測（確かめていない）

- 副アンテナの測定が足りない原因の候補: 副アンテナが屋内・遮られている、ケーブル・コネクタ、副アンテナへの給電、受信機のアンテナの設定（第129便で DualAnt の設定と reset の後に追尾が変わった件）。主アンテナは衛星 16 を捕まえている。
- NTRIP の入力が待ちのままの原因の候補: caster への接続・認証の失敗、mountpoint が GGA を要るのに GGA が送られていない、caster 側の契約。中継の詳細の状態の行は接続の情報を含みうるので読んでいない。

## 4. 検査・試験

- 実行したもの: 上の読むだけのコマンド（ssh、`pgrep -l`、`curl` で monitor の /api/state、`ros2 topic echo --once`、設定と launch のログのキーを grep。接続の情報は伏せ字のフィルタを通した）。
- 設計検査・単体試験: 未実行（正本・コードを変えていない）。

## 5. 残るリスク・次

- RTK と方位は、Gouda の起動中の今は効いていない。地図と GNSS の対応づけ（DEC-131・135）、走行中の GNSS（DEC-290）は進められない。
- 次の候補（どれも人の判断）: 副アンテナの配線と設置の確認（人）、受信機の状態（AGC・アンテナの給電）を読む T1（DEC-299）、中継の接続の状態を伏せ字で読む手順を決める。
- 認証の情報は記録に出していない（DEC-139）。コミットはまだ。
