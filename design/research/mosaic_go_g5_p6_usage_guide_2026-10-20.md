# mosaic-go G5 P6 の使い方のまとめ（開発のセッション向け、2026-10-20）

状態: 調査の記録のまとめ（読むだけ）。人の指示「主な開発は別のチャットで行っているが、そっちはrtklibを使おうとしているらしい。mosaic-goの使い方も分かっていない。全部教えてやってくれ。」による。
根拠の詳細: `gnss_mosaic_g5_p6_dual_antenna_survey_2026-10-19.md`（§2〜§7。公式の資料・Reference Guide v1.1.1 との照合）、`gnss_mosaic_g5_dual_antenna_2026-10-19.md`、`vehicle_pc/2026-10-19_mosaic_mrtk_query.txt`（第41便の照会）・`vehicle_pc/2026-10-19_mosaic_mrtk_query_followup.txt`（第42〜44便の DualAnt・Boot 保存・reset。REV-082 で分けられた）。推測は「推測」と書く。

## 1. 何をどこで計算するか（いちばん大事な点）

- **位置・速度・方位は、受信機（mosaic-G5 P6）の中で計算される。** PC は結果を USB で受け取るだけ。PC 側で RTKLIB・MRTKLIB で測位し直す必要はない。
  - 受信機の中の測位: 単独、SBAS、DGNSS、RTK（rover。補正は外から入れる）、Galileo HAS（補正なしで水平 0.1 m 級）。根拠: P6 データシート（YH 04/2026）、受信機の能力の照会（`grc`: SBAS、DGNSSRover、RTKRover、RTKBase、RTCMv3x、MovingBase、PPPGalileoHAS-SIS など）。
  - 方位（2 本のアンテナ）: 受信機が main と aux1 の基線から計算し、AttEuler（SBF）・HDT/HRP（NMEA）で出す（Reference Guide v1.1.1 §1.11）。
  - 速度: 3 cm/s（データシート）。
  - 出力の上限: RTK と方位で 50 Hz、遅延 10 ms 未満（データシート。今のドライバの設定は 100 ms ごと）。
- **RTKLIB が要るのは NTRIP の補正の中継だけ**（DEC-139 の案 B1）。理由: mosaic-Go G5 には TCP/IP がなく、受信機が自分で NTRIP の caster につなげない（Septentrio のサポート記事「mosaic-G5: Getting started guide」「FAQ - overview」）。PC が NTRIP から RTCM を受けて受信機の USB2 に書き、受信機が USB2 に出す GGA を caster に返す。
  - 中継の候補: apt の `rtklib`（2.4.3 b34）の `str2str`（VM の apt で確認済み、未導入）。`ros-jazzy-ntrip-client` もあるが、ドライバは補正を ROS の topic から受けられない（シリアル・TCP・受信機の NTRIP だけ）ので、topic をシリアルに書く中継が別に要る。
  - MRTKLIB（VM の ~/MRTKLIB）は、照会の道具として使った（DEC-143）。システムの部品としては要らない。PC 側で測位するのは、QZSS の L6（CLAS）を使う場合だけ（受信機は L6 を受信できるが、CLAS の測位の能力は持たない。G5 の SBF でできるかは未照合）。

## 2. つなぎ方

- USB 1 本で、シリアル（CDC）が 2 本見える。
  - `/dev/serial/by-id/usb-Septentrio_Septentrio_USB_Device_0100012541-if00` = 受信機の **USB1**: ROS ドライバが使う（PRM-65）。
  - `...-if02` = **USB2**: 空き。NTRIP の補正の入力と GGA の出力に使う案（ドライバの `rtk_settings.serial_1.port: USB2` で `sdio, USB2, <RTCM>, +SBF+NMEA` と GGA を送る。提案 `proposals/ntrip_gga_proposal.md`）。
- **by-id の名前を使う。** 受信機の reset で USB がつなぎ直され、ttyACM の番号は変わる（第44便で if02 が ttyACM1 → ttyACM2）。
- シリアルは raw・エコー無効で開く（人の資料 §2。ドライバ・MRTKLIB の relay はそうしている）。エコーが有効だと NMEA が受信機に送り返され、無効なコマンドになる（第35・39便）。
- Ethernet・WebUI はない（公式の FAQ）。設定はコマンド（`$R` の応答）だけ。

## 3. 受信機の今の設定（2026-10-19 時点）

- firmware 1.1.1（最新。更新は不要: P6 Release Notes v1.1.1 にデュアルアンテナの変更なし）。
- **frontend mode = DualAnt（Boot に保存済み、reset 済み）**。gnss の方位の設定 `MultiAntenna, Fixed`。
  - P6 は出荷時 `Nominal` で、これは P6 では**単一アンテナ**の意味（Reference Guide v1.1.1 §3.2.4: 普通は SingleAnt、方位が主目的の製品では DualAnt）。そのため最初は副アンテナの観測が一つもなかった。
  - 有効にする手順（一度だけ）: `setFrontendMode, DualAnt` → `exeCopyConfigFile, Current, Boot` → `exeResetReceiver, Hard, none`（Hardware Manual v2.0.0 §4.2.3.2）。
  - **ROS ドライバ（どの版も）・ArduPilot・PX4 は setFrontendMode を送らない。** 受信機を工場出荷の状態に戻した（factoryReset など）ときは、この手順をやり直す。
- ドライバ（configure_rx true）は起動のたびに出力を設定し直し、最後に `eccf, Current, Boot` を送る。frontend mode には触れないので DualAnt は残る。

## 4. ROS ドライバ（septentrio_gnss_driver 1.4.8、apt）の振る舞い

- 方位に対応するかを `grc` の応答に「Heading」か「Main+Aux1」があるかで判断し、`multi_antenna: true` なら `sga, MultiAntenna` を送る（Gouda の設定 `gnss_config.py` 90-93 行は `multi_antenna: True`）。
- `sto, <heading>, <pitch>`（方位のオフセット）は TF の base_link→gnss_link・gnss_aux1_link（ND-13 が /config から出す）から計算して送る。heading = atan2(dy, dx)（aux1 − main）、`use_ros_axis_orientation: true`（既定）で符号を反転。
- **今の /config（VM の sensor_config.json、config_revision 18）**: main (0.45, 0.17, 0.77)、aux1 (0.45, −0.17, 0.77) m。→ 2 本は車体の左右（main が左、aux1 が右）、間隔 **0.34 m**。ドライバは `sto, 90, 0` を送るはず（推測。Reference Guide §1.11 の「aux1 が main の右なら setAttitudeOffset,90」と合う）。この配置では受信機の「pitch」は roll として読む（§1.11）。
  - **人が確認（DEC-149、2026-10-20、原文）**: 「現在の車体のアンテナ間隔は 0.34 m で、config の値が正しい。DEC-130 の 0.6 m は古い値。」
  - 間隔と精度: データシートは 1 m で 0.15°。0.34 m ではそれより悪い（推測。ARK の資料は 30 cm 以上を目安としている）。
- issue（septentrio_gnss_driver #162: P3H で DualAnt・MultiAntenna でも AttEuler の error 1、解決の記録なし）。
- apt の次の同期で 1.5.0 が入る可能性がある（rosdistro の jazzy は 1.5.0-1。G5 の最低 firmware 1.1.0 は満たす。方位まわりのロジックは同じ）。

## 5. アンテナの条件（Hardware Manual v2.0.0）

- デュアルでは前置増幅（アンテナの利得 − ケーブルの損失）が 15〜35 dB（受信機の AGC で 30〜50 dB）、2 本の差 5 dB 以内。同じ型のアンテナ・同じケーブル。**ANT_2（AUX）を空けない。**
- mosaic-go G5 は MAIN（ANT_1）・AUX（ANT_2）の両方に 5 V を出す（合計 150 mA まで）。
- デュアルでは aux で E6/L6・B2b を受けない。L-band は単一アンテナのときだけ。
- 人の判断（2026-10-20、原文）: 「アンテナは動作確認済み品をレンタルしているから、調べる必要ないと思う」→ 事前の確認はしない。屋外の確認で AGC を読むだけ。

## 6. 屋外の確認（まだしていない。次の作業）

1. 電源の入れ直しの後も `gfm` が DualAnt。
2. ReceiverStatus の AGCState に Aux1 の行があり、AGC が main・aux とも 30〜50 dB、差 5 dB 以内。
3. MeasEpoch に アンテナ番号 1 の観測がある（Type の bit 5〜7。0 main、1 Aux1）。
4. AuxAntPositions の基線の長さが 0.34 m（DEC-149）と合い、AmbiguityType が fixed。
5. AttEuler の Error の bit 0〜1 が 0（1 は「測定が足りない」）、Mode 2（heading・pitch、fixed）。ARK の資料では方位は fixed のときだけ出る。
- 方位に外部の補正（NTRIP）が要るかは、Reference Guide §1.11 に書かれていない（2 本のアンテナの基線は受信機の中で解く）。補正なしで方位が出るかを屋外で確かめる（推測）。

## 7. しなくてよいこと

- firmware の更新、Septentrio への問い合わせ（必要な資料は人が取得済み）。
- RTKLIB・MRTKLIB で位置や方位を計算すること。
- アンテナの利得の事前の調査（人の判断）。
