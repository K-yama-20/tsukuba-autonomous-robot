# mosaic-G5 P6 のデュアルアンテナ方位: 公開資料の調査（2026-10-19）

状態: 調査の記録（読むだけ。受信機・VM には触れていない）。人の指示「p6でdual antennaをやる方法を徹底的に調査せよ」による。調査は AI 3 体（ROS ドライバ、公式文書、販売店・コミュニティ）と、AI が内蔵ブラウザで読んだ Septentrio のサポート記事による。PDF は AI の作業領域に取得して pdftotext で読んだ（リポジトリには入れない）。
前提の記録: `gnss_mosaic_g5_dual_antenna_2026-10-19.md`（第41便）、`vehicle_pc/2026-10-19_mosaic_mrtk_query.txt`（第41便）と `vehicle_pc/2026-10-19_mosaic_mrtk_query_followup.txt`（第42〜44便。DualAnt を Boot に保存・reset 済み、屋外の確認は未実行。REV-082 で分けられた）。

## 1. 結論

- **P6 はデュアルアンテナの方位に対応する。ただし出荷時は無効で、frontend mode を DualAnt にして Boot に保存し、再起動して有効にする。** 第43〜44便で行った手順は公式の手順と同じ。
- ROS ドライバ（どの版も）・ArduPilot・PX4 は setFrontendMode を送らない。P6 ではドライバ任せでは有効にならない（今回の Nominal の状態の原因と整合）。
- 残る条件はアンテナ側（利得 15〜35 dB、2 本の差 5 dB 以内、ANT_2 を空けない）と、/config のアンテナ位置（方位のオフセット）。屋外の確認は未実行。

## 2. 読んだ資料（事実）

| 資料 | 版・日付 | 取得元 | 要点 |
|---|---|---|---|
| Septentrio サポート記事「mosaic-G5: FAQ - Heading support」 | 閲覧 2026-10-19 | https://customersupport.septentrio.com/s/article/mosaic-G5-FAQ-heading-support | 表で P6・P8 は「Yes*」。注記: P6・P8 では attitude の機能は既定で有効でなく、有効にする設定は Firmware Reference Guide の「frontend operating mode」の周辺にある |
| 同「Product variant differentiation」 | 同 | https://customersupport.septentrio.com/s/article/mosaic-G5-Variant-differentiation | Heading dual antenna: P3H・P6・P8 が Yes。P6 は RTK rover/base、moving base、raw data、Galileo HAS、最大 100 Hz |
| 同「FAQ - overview」 | 同 | https://customersupport.septentrio.com/s/article/mosaic-G5-FAQ-overviewpage | 「dual antenna の許可は P3H」とだけ書く（古い記述。上の 2 記事と食い違う）。G5 に WebUI・TCP/IP はない |
| 同「Getting started guide」 | 同 | https://customersupport.septentrio.com/s/article/mosaic-G5-getting-started | mosaic-Go G5 に TCP/IP はなく、NTRIP は外から RTCM を流し込む（RxControl の NTRIP forwarder の例） |
| 同「Log observations from both antennas」 | 同 | https://customersupport.septentrio.com/s/article/Is-It-Possible-to-Log-and-Analyze-Observations-from-Both-Antennas-on-a-Dual-Antenna-Receiver | dual-antenna mode では main・aux 両方の観測を記録できる。SBF Analyzer で Aux1 を選んで確かめられる |
| mosaic-G5 Hardware Manual | **v2.0.0（2026-05）** | https://cdn.shopify.com/s/files/1/0991/6262/0236/files/mosaic-g5_hardware_manual_v2.0.0.pdf （gnss.store が掲載） | 下の §3。改版履歴に「P6・P8 の型番を追加」。§3.1.1 の表で Dual-antenna は P3H, P6, P8（能力名 Antennas / Aux1）。手元の v1.1.1 の「P3H だけ」は古い |
| mosaic-G5 Firmware Reference Guide | v1.0.1（2025-11-13） | docs.sparkfun.com（P3 向けの掲載） | setFrontendMode の値は SingleAnt・DualAnt、次の reset から有効。sga・sto・AttEuler・AuxAntPositions の定義（§5） |
| mosaic-G5 P6 データシート | YH 04/2026 | gnss.store・gps-world.biz の PDF | Single or dual antenna support、GNSS Heading、RTK + attitude 50 Hz、heading 0.15°（1 m）、前置増幅 15〜35 dB（DA） |
| ARK Electronics の資料（ARK G5 RTK Heading GPS、第三者） | 2026-10 | https://docs.arkelectron.com/products/gps/ark-g5-rtk-heading-gps/firmware.md 、修正 commit https://github.com/ARK-Electronics/gitbook/commit/d77456ce | P6・P8 は単一アンテナで出荷、P3H はデュアルで出荷。P6・P8 は SEP_ANT_MODE=2 でデュアル。方位は ambiguity が Fixed のときだけ出る。アンテナ間隔 30 cm 以上（ARK の目安） |
| Septentrio の公開ハードウェア（mosaicG5-HAT の文書） | commit 363b031c | https://github.com/septentrio-gnss/mosaicG5-HAT | 手順は Hardware Manual と同じ。P3H・P6・P8 は単一・デュアルのどちらでも動く |
| septentrio_gnss_driver | v1.4.8（5613af2）、master = v1.5.0（459dd41） | https://github.com/septentrio-gnss/septentrio_gnss_driver | §4 |

**入手できなかったもの（2026-10-19 時点）**: firmware 1.1.x の Reference Guide と Release Notes（septentrio.com は Cloudflare の人の確認で止まり、AI は操作していない）。→ 2026-10-20 に人が取得して渡した（§7）。

## 3. 手順と条件（Hardware Manual v2.0.0）

- §4.2.3.2（p.15）: 一度だけ `setFrontendMode, DualAnt` → `exeCopyConfigFile, Current, Boot` → `exeResetReceiver, Hard, none`。
- 利得（§4.2.1・4.2.2 p.14、Appendix C p.43）: デュアルでは前置増幅（アンテナの能動利得 − 1.6 GHz のケーブル損失）が **15〜35 dB**、受信機の AGC で **30〜50 dB**。35 dB を超えると副アンテナから主アンテナへの漏れ（crosstalk）で性能が落ちる。高利得のアンテナでは減衰器を入れる。
- 2 本の差（p.15）: 前置増幅の差は **5 dB 以内**。同じ型のアンテナ、同じ型・長さのケーブルを勧める。合わないときは強い方を減衰させる。
- **デュアルでは ANT_2 を空けない**（p.15）。単一のときは ANT_2 を空けることを勧める。
- 電源: ANT_1・ANT_2 に同じ電圧、オン・オフは一緒、合計 150 mA まで（§4.2）。mosaic-go G5 は MAIN・AUX の両方に 5 V を出す（§7.2.2 p.36。MAIN = ANT_1、AUX = ANT_2）。
- 周波数（§3.1.2 の図。調査 AI が p.8 を画像で確認）: デュアルでは Aux で E6/L6 と B2b を受けない。L-band は単一アンテナのときだけ。
- 消費電力: デュアルで 785 mW（全信号）。
- 基線長の上下限・アンテナの向きの規定: Septentrio の文書には見つからない。

## 4. ROS ドライバ（septentrio_gnss_driver）の振る舞い

- `communication_core.cpp`（v1.4.8 549-561 行、v1.5.0 629-641 行）: `multi_antenna: true` かつ受信機が方位対応なら `sga, MultiAntenna`。方位対応の判定は ReceiverCapabilities に「Heading」または「Main+Aux1」を含むか（`telegram_handler.cpp` 81-93 行。G5 対策で v1.4.6 から）。
- `sto, <heading>, <pitch>` は常に送る（v1.4.8 563-585 行）。TF を使う場合は主→副の差から heading = atan2(dy, dx)、pitch = atan2(−dz, 水平距離)、`use_ros_axis_orientation: true`（既定）で符号を反転（`rosaic_node.cpp` 343-366・393-407 行）。主・副の TF が同じ位置なら 0, 0 が送られる（エラーにならない）。
- `sao, Aux1, 0, 0, 0, ...` を送る（425-455 行）。
- **setFrontendMode はどの版・どのブランチでも送らない**（git log -G で 0 件）。最後に `eccf, Current, Boot`（1014 行）。
- v1.5.0 で G5 の最低 firmware は 1.1.0（受信機の 1.1.1 は満たす）。rosdistro の jazzy は 1.5.0-1。
- issue #162（P3H、sfm DualAnt と sga MultiAntenna でも AttEuler error 1）は返答なしで投稿者が閉じ、解決策の記録なし。#165 は G5 の grc に Heading がない件（Main+Aux1 の判定を追加）。
- Gouda の設定（`gouda_core/gouda_core/gnss_config.py` 90-93 行）は `multi_antenna: True`、`get_spatial_config_from_tf: True`、atteuler・attcoveuler を出す。`sga, none` が Boot に保存される心配はない。
- ArduPilot（AP_GPS_SBF.cpp）・PX4（septentrio.cpp）も sfm を送らず、`sga, MultiAntenna`（と `sto`）だけ。PX4 は AttEuler の Mode 2・4（fixed）だけを採る。

## 5. 屋外での確かめ方（Reference Guide v1.0.1 の定義）

1. 電源の入れ直しの後も `gfm` が DualAnt。
2. ReceiverStatus の AGCState に Aux1 の行があり（FrontEndID の bit 5〜7 がアンテナ番号）、AGC が main・aux とも 30〜50 dB、差が 5 dB 以内。
3. MeasEpoch に アンテナ番号 1 の観測がある（Type の bit 5〜7）。
4. AuxAntPositions の基線（√(dE²+dN²+dU²)）が巻尺の測定と合う。AmbiguityType 0（fixed）。
5. AttEuler の Error の bit 0〜1 が 0、Mode が 2（または 4）。ARK の記述では方位は fixed のときだけ出る。
- RxTools の SBF Analyzer で Aux1 の C/N0 を描ける（サポート記事）。

## 6. 推測（未確認）

- （2026-10-20 に §7 で原本と照合済み。Nominal は P6 では単一アンテナの意味だった。）
- 利得: 使っているアンテナの利得とケーブルの損失は未確認。35 dB 級の LNA でケーブルが短いと上限に近く、減衰器が要る場合がある。
- 方位のオフセット: /config に GNSS のアンテナ位置が入っていない間（第40便の記録）、主・副の TF は同じ位置で `sto, 0, 0` が送られる。既定の配置（main が後ろ・aux1 が前、前後軸の上）以外では方位がずれる。
- （2026-10-20 に §7 で照合済み。sga の Source に MovingBase が加わっただけで、MultiAntenna・Fixed・sto の引数は同じ。）

## 7. 原本との照合（2026-10-20。人が Septentrio から取得して渡した資料）

人が渡した資料（AI は ~/Downloads から作業領域に写して pdftotext で読んだ。リポジトリには入れない）:

| 資料 | 版・日付 | SHA-256（先頭 16 桁） |
|---|---|---|
| mosaic-G5 Firmware v1.1.1 Reference Guide | 2026-06-12、firmware 1.1.1 | 1ac20c84ddd1ed03（firmware 一式の manuals/ にある同名の PDF と同一） |
| mosaic-G5 P6 Firmware v1.1.1 Release Notes | 2026-06-18 | 3b4375e69d3d36b5 |
| mosaic-G5 Hardware Manual v2.0.0（septentrio.com の URL の版） | May 2026 | 4c083bb3cae2c60e（本文は gnss.store の版と同じ。差は改行 1 か所） |
| mosaic-G5 P6 データシート | YH 04/2026 | 13f64ea26bb0d29d（以前に読んだものと同一） |
| firmware 一式 mosaic-G5 P6_fwp_1.1.1 | 1.1.1 | suf 2 個（本体・failsafe）、Reference Guide・Reference Card。suf は読んでいない |

Reference Guide v1.1.1 で分かったこと（事実）:

- **setFrontendMode（§3.2.4、p.98）**: 値は **Nominal・SingleAnt・DualAnt** の 3 つ。Nominal は「製品に最もよい動作を選ぶ。普通は SingleAnt、方位が主目的の製品では DualAnt」。DualAnt は「受信機に dual-antenna の能力があるときだけ、デュアルに強制する」。次の reset・再起動から有効で、exeCopyConfigFile で Boot に保存する必要がある。
  - → 第41便の `gfm` の Nominal は、P6 では単一アンテナとして動く既定値だった。副アンテナの観測がなかったことと一致する（原本で確認）。第43〜44便の DualAnt・Boot 保存・reset は、この記述どおり。
- **§1.11「Main と Aux のアンテナからの GNSS の姿勢」（p.26〜27）**: Aux1 の能力がある受信機に適用。手順は (1) ほぼ同じ長さのケーブルで 2 本を付ける。既定は車体の前後軸の上で **main が後ろ・aux1 が前**。高さの差を避け、間隔は広いほどよい。前後に置けないときは基線を車体に直角にし、`setAttitudeOffset,90`（aux1 が main の右）または `-90`（左）。(2) 高さの違い・平行のずれは setAttitudeOffset で補正。(3) `setGNSSAttitude,MultiAntenna`。出力は AttEuler、NMEA の HDT・HRP。基線が直角のとき pitch は roll と読む。
  - §1.11 は setFrontendMode に触れていない（P6 でそれが要ることは §3.2.4 とサポート記事から分かる）。
- **sto（p.133）**: Heading −360〜360 度、Pitch −90〜90 度。受信機は与えた値を姿勢から引いてから出力する。
- **sga（p.134）**: Source は none・MovingBase・MultiAntenna、第 2 引数 Float・Fixed（最高の精度には Fixed）。v1.0.1 に MovingBase が加わった。今の受信機の設定 `MultiAntenna, Fixed` はこの定義に合う。
- **AttEuler（5938）**: Error の bit 0〜1 は Main-Aux1 の基線（0 誤りなし、1 測定が足りない）、bit 7 は利用者が姿勢を求めていない。Mode 0 姿勢なし、1・2 は heading・pitch（1 float、2 fixed）、3・4 は roll も（3 float、4 fixed）。Info の bit 0〜1 が姿勢の出どころ（1 マルチアンテナ、2 moving base）。
- **MeasEpoch の Type**: bit 5〜7 がアンテナ番号（0 main、1 Aux1、2 Aux2）。第40便の「番号の読み方は原本未照合」はこれで照合済み。

Release Notes v1.1.1（P6）で分かったこと（事実）:

- 1.1.1 の改善は 2 件だけ（setAntennaOffset に APCOutput の引数を追加、GLOAlm の出力の不具合の修正）。1.1.0 で moving base・SBAS・Galileo HAS・CMR の入力などを追加。**frontend mode やデュアルアンテナの変更の記載はない**。
- 既知の制約: 内部ディスクへの 10 Hz を超える記録は途切れる、など。デュアルアンテナに関するものはない。
- 受信機は既に firmware 1.1.1（第39〜40便の記録）なので、firmware の更新は要らない。
