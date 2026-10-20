# DEC-140 の判断の材料: configure_rx を false にする場合の受信機の事前設定と、人が行う手順の案（提案 第1版。実行しない）

状態: 提案（判断の材料）。2026-10-19。人の指示（DEC-141 の 3）に基づく。**受信機のポートには触っていない**（AI は読むことも含めて、raw・エコー無効の確認と人の許可の後まで触らない）。

根拠:
- 上流ドライバのソース（FILE-SEPTENTRIO-SOURCE-REVIEW、tag v1.4.8 commit 5613af2）: `configureRx()` が configure_rx true のときに送るコマンド（communication_core.cpp 286〜1016 行）。
- Gouda の雛形の設定（`design/research/upstream_sensors/septentrio_gnss_driver_1.4.8/gnss.yaml` と `gouda_core/gouda_core/gnss_config.py` の差し込み）。
- 人の資料 `reports/mosaic-G5_P6_取扱上の注意事項.md`（以下「資料」）§2〜§7・§11。
- コマンドの書式で実機の応答で確かめられているのは、資料 §4 の 4 つ（`lif,Identification`・`gso`・`getDataInOut`・`sso,Stream4,USB1,Support,sec1`）だけ。それ以外の書式（`+` で並べる block の指定、`sga`・`sto`・`sdio`・`sno`）はドライバのソースの書き方で、**実機の応答では未確認**（Reference Guide v1.0.1 と実機 1.1.1 の差もありうる: 資料 §12）。

## 1. configure_rx の違い（要約）

| | 案 1: true（雛形のまま） | 案 2: false |
|---|---|---|
| 起動のたび | 全出力を止め（`sso/sno, all, none, none, off`）、Stream1 から作り、`eccf, Current, Boot` で Boot に保存 | エスケープの列（`\rSSSSSSSSSS\r\r` を 3 回）を送って接続先の名前を得るだけ。受信機の設定は変えない |
| 終了時 | 主接続先の出力を止める（`sdio, USB1, auto, none`）。SBF のストリームと Boot の内容は残る | 何もしない（`resetSettings()` は configure_rx true のときだけ） |
| 人の資料との関係 | §5（既存の用途を上書きしない）・§6（Boot 保存は別工程）と合わない | 合う。ただし受信機の設定は人の手順で行う（下の §3） |
| RTK（案 B） | `rtk_settings.serial_1` で USB2 の補正の入力と GGA の出力をドライバが設定 | 人の手順で設定（手順 5 のとき） |
| 方位のオフセット | TF（/config）から `sto` をドライバが設定 | 人の手順で `sto` を設定（値は AI が /config から計算して示す） |
| 電源の再投入 | Boot に保存されているので残る | Boot に保存しない間は失われ、毎回やり直し（資料 §6: 再投入後の保持は未確認） |

## 2. configure_rx が false のとき、受信機に先に設定しておく SBF の出力

ドライバはどの block が来ても読み、届いた block から topic を作る（`auto_publish` は false のまま。届かない block の topic は出ない）。

### 2.1 案 2-a: ドライバが configure_rx true のときに作るものと同じにする（Gouda の今の publish の設定のまま）

| 用途 | ブロック名 | 出力先 | 間隔 | ストリーム |
|---|---|---|---|---|
| 位置・速度・方位（ドライバの PVT の周期 polling_period.pvt = 100 ms → `msec100`） | PVTCartesian, PVTGeodetic, PosCovCartesian, PosCovGeodetic, VelCovGeodetic, AttEuler, AttCovEuler, MeasEpoch, ChannelStatus, DOP | USB1 | msec100 | 未使用の Stream（§3 の手順 4 で決める。Stream1〜10 から。Res1〜4 は使わない） |
| 状態（polling_period.rest = 500 ms → `msec500`） | QualityInd, RFStatus, ReceiverSetup, ReceiverStatus | USB1 | msec500 | 未使用の Stream（同上） |

由来（Gouda の gnss.yaml の publish と、ドライバの block の選び方。communication_core.cpp 784〜819 行（状態のストリーム）・857〜974 行（PVT のストリーム）・825〜854 行（NMEA））:
- PVTGeodetic: pvtgeodetic・navsatfix・gpsfix・pose・latency_compensation のため。PosCovGeodetic: poscovgeodetic・navsatfix・gpsfix・pose。AttEuler・AttCovEuler: atteuler・attcoveuler・gpsfix・pose。VelCovGeodetic: velcovgeodetic・gpsfix。PVTCartesian・PosCovCartesian: 同名の publish。MeasEpoch: measepoch・gpsfix。ChannelStatus・DOP: gpsfix。
- QualityInd: diagnostics。RFStatus: aimplusstatus。ReceiverSetup・ReceiverStatus: ドライバが常に付ける（診断と受信機の情報）。
- NMEA の出力はドライバは作るが block が空（Gouda は gpgga などを publish しない）なので、案 2 では不要。

### 2.2 案 2-b: Gouda の IF に要るものだけにする（publish の設定も減らす。設定の変更なので別の承認）

| 用途 | ブロック名 | 出力先 | 間隔 |
|---|---|---|---|
| IFD-47 navsatfix、IFD-48 pvtgeodetic | PVTGeodetic, PosCovGeodetic | USB1 | msec100 |
| IFD-49 atteuler、IFD-50 attcoveuler | AttEuler, AttCovEuler | USB1 | msec100 |
| 受信機の状態（記録・診断） | ReceiverStatus（必要なら QualityInd, RFStatus） | USB1 | msec500 |

案 2-b は USB の帯域と記録の量が減る。ただし gpsfix・pose・measepoch などの topic は出なくなる（Gouda は使っていない）。AI の推奨は **案 2-a**（雛形の publish を変えずに済み、比較もしやすい）。間隔の 100 ms・500 ms は雛形の値で、実車の値としては未確定（必要なら別の承認）。

### 2.3 SBF 以外に、configure_rx true ならドライバが書くもの（案 2 では人の手順に入る）

| コマンド（ドライバのソースの書式） | 意味 | 案 2 での扱い |
|---|---|---|
| `sga, MultiAntenna` | 2 本のアンテナで方位を出す | **必要**（方位 IFD-49 のため）。今の受信機の値を `gga`（get の形。書式は未確認）か ReceiverSetup で確かめてから |
| `sto, <heading>, <pitch>` | 主→副のアンテナの方位・仰角のオフセット | **必要**（/config の主・副のアンテナの位置から AI が計算した値。取付が未入力なら 0, 0 になり、向きがずれる: FILE-SEPTENTRIO-SOURCE-REVIEW §4） |
| `sat`・`sao, Main/Aux1, ...` | アンテナの型・ARP のオフセット | 雛形は型 Unknown・オフセット 0。変更しないなら不要 |
| `sgd, Default` | 測地系 | 既定のままなら不要 |
| `sntp, on` | 受信機の NTP の server | Gouda は使わない（PC の時刻）。不要 |

## 3. 人が行う手順の案（資料 §4〜§6・§11 に沿う。実行は人の判断）

前提: Gouda も septentrio のドライバも動いていない。手順の中のコマンドは「シリアル経由で受信機へ送る文字列」（資料 §4）。終端は CR。各段で、送った文字列と応答をそのままログに残す。

1. **機器の特定**（資料 §3・§11 の 1）: `ls -l /dev/serial/by-id/` で `...0100012541-if00`（USB1）と `-if02`（USB2）を確かめる。以後 by-id の名前だけを使う（DEC-141）。
2. **競合の確認**（資料 §7）: `fuser -v` で両ポートを使うプロセスがないこと。
3. **端末の設定**（資料 §2）: 両ポートを `stty -F <by-id> raw -echo -ixon -ixoff` にし、`stty -a` で確かめる。
4. **応答を捕まえられる状態で照会**（資料 §4・§11 の 4）: 照会用のポート（資料の勧めでは USB2）の受信を先に記録し始めてから送る。`lif,Identification`、`gso`（SBF のストリーム）、`gno`（NMEA のストリーム。書式は未確認）、`getDataInOut`。**変更の前の値として保存する**。
5. **ストリームの番号を決める**（資料 §5）: `gso` の結果で `none` の Stream1〜10 から 2 つを選ぶ。Res1〜4 は使わない。2026-10-17 の Stream4（USB1/Support/sec1）が残っていれば、上書きしない（使い続けるかは人の判断）。
6. **設定**（必要な分だけ、一つずつ。資料 §11 の 5・§4）:
   - `sso,Stream<A>,USB1,PVTCartesian+PVTGeodetic+PosCovCartesian+PosCovGeodetic+VelCovGeodetic+AttEuler+AttCovEuler+MeasEpoch+ChannelStatus+DOP,msec100`
   - `sso,Stream<B>,USB1,QualityInd+RFStatus+ReceiverSetup+ReceiverStatus,msec500`
   - `sga,MultiAntenna`
   - `sto,<heading>,<pitch>`（値は AI が /config から計算して示す）
   - 書式（block の並べ方の `+`、空白の有無）は実機の応答で確かめる。最初に 1 つの block だけで試してから増やす案もある（段階を踏むかは人の判断）。
7. **確認**（資料 §4・§11 の 6）: 各コマンドの応答（`$R:` など。`$R?` はエラー）を確かめ、`gso` をもう一度取って設定が入ったことを確かめる。
8. **SBF の取得と検証**（資料 §8・§9・§11 の 7）: USB1 から 10 秒ほど生のまま保存し、長さと CRC を確かめる（AI が CRC の検査の道具を用意できる。ポートには触らない）。block の種類が §2.1 のとおりそろっていることも数える。
9. **Boot には保存しない**（資料 §6）: ここまでは RAM の設定。電源を入れ直すと消えうる。Boot への保存（`eccf, Current, Boot`）は、設定が確定してから人が明示して行う別の工程。
10. この後で初めて、Gouda（configure_rx false）でドライバを起動する（DEC-140 の決定の後）。

## 4. 手順 5（NTRIP の案 B）で足すもの（参考。今回は設定しない）

- 補正の入力を USB2 で受ける: ドライバのソースの書式では `sdio, USB2, <RTCMv3 など>, +SBF+NMEA`。今 USB2 に流れている NMEA（どのストリームかは `gno` で確かめる）を残すかを決める必要がある。
- ネットワーク RTK の多くは受信機の位置（GGA）を caster に送る必要があり、GGA を USB2 に出すストリーム（`sno,Stream<C>,USB2,GGA,sec1` の形）が要る。Point One の要否は**原本未照合**。
- PC の NTRIP のクライアント（ソフトの選定は承認事項）が USB2 に RTCM を書き、GGA を読む。USB2 を同時に読み書きするのはこのクライアントだけにする（資料 §7）。

## 5. AI の推奨（判断は人）

- **案 2（configure_rx false）で、SBF は 2.1（案 2-a）**。資料の §5・§6 に合い、受信機の設定と Boot の内容を人が管理できる。手順は §3。
- 案 1 を選ぶ場合は、起動のたびに受信機の全出力が止まり Boot に保存されることを受け入れる（2026-10-17 の Stream4 は消える）。
