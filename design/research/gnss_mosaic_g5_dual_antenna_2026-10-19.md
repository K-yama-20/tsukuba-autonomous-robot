# mosaic-G5 の副アンテナ（Aux1）と方位: マニュアルの確認と MRTKLIB での確認の手順（2026-10-19）

状態: 調査の記録。G-GNSS-NO-HEADING（屋外で AttEuler が mode 0 / error 1、MeasEpoch は antenna 0 だけ）と、人の確認（main と aux を入れ替えても main 側だけ受信 → アンテナ・ケーブルは正常）を受けたもの。

## 1. 読んだ資料（Septentrio の公開 PDF。AI の作業領域に取得して pdftotext で読んだ。リポジトリには入れない）

- mosaic-G5 Reference Guide, Firmware 1.0.1（2025-11-13）。実機の firmware は 1.1.1 なので、版の差がありうる（人の資料 §12）。
- mosaic-G5 Hardware Manual v1.1.1（2025-05-28）。
- 製品のページ（septentrio.com）は取得できなかった（HTTP 403）。**P6 という型は、上の 2 冊のどちらにも出てこない**（Hardware Manual の型の表は P1・P3・P3H だけ）。P6 が副アンテナに対応するかは**原本未照合**。

## 2. 分かったこと（ページは pdftotext の出力で確かめた節の番号）

| 項目 | 内容 | 出典 |
|---|---|---|
| 副アンテナに対応する型 | 表「mosaic-G5 Models and Capabilities」で Dual-antenna は P3H だけ。対応する能力の名前は「Antennas / Aux1」 | Hardware Manual §3.1.1 |
| mosaic-go G5 の端子 | MAIN と AUX の 2 つ。内部の module の ANT_1・ANT_2 につながる | Hardware Manual §7.2.2 |
| 能力がない場合 | Aux1 の能力がなければ、module は常に単一アンテナで動く | Hardware Manual §4.2 |
| 2 本で動かすための設定 | `setFrontendMode, DualAnt`（次の起動から有効）、`exeCopyConfigFile, Current, Boot`、`exeResetReceiver, Hard, none`。**Boot への保存と再起動が要る** | Hardware Manual §4.2.3.2、Reference Guide の sfm/gfm |
| 2 本で動かすときの注意 | 前置増幅の利得は全帯域で 35 dB 未満、ANT_1 と ANT_2 の差は 5 dB 以内。同じ型のアンテナ・同じケーブルを勧める。DualAnt では ANT_2 を開放にしない | Hardware Manual §4.2.3.2 |
| 方位の計算の指定 | `setGNSSAttitude, MultiAntenna`（第 2 引数 Float/Fixed）。能力に依存するコマンド | Reference Guide sga/gga |
| 能力の照会 | `getReceiverCapabilities`（`grc`）。返答の最初が使えるアンテナの一覧（Main、Aux1） | Reference Guide §1.1、grc |
| 許可の照会 | `lstInternalFile, Permissions`（`lif, Permissions`）。dual-antenna などの任意機能の許可 | Reference Guide §1.17 |
| AttEuler の Error | bit 0〜1 が Main-Aux1 の基線の誤り。1 は「測定が足りない」。bit 7 は利用者が方位を求めていないとき | Reference Guide AttEuler (5938) |
| AttEuler の Mode | 0 は方位なし、1〜4 は float/fixed の方位 | 同上 |
| MeasEpoch の antenna | Type1 の bit 5〜7 が antenna ID（0 main、1 Aux1、2 Aux2） | Reference Guide MeasEpoch |

## 3. 屋外の結果の読み方（推測を含む）

- Error 1（bit 7 が 0）: 方位は要求されている（ドライバの `sga, MultiAntenna` が受け付けられた）が、Main-Aux1 の基線の測定が足りない。MeasEpoch に antenna 1 がないことと合う。
- 入れ替えても main 側だけ受信 → アンテナとケーブルは正常（人の確認）。残る原因の候補（推測）:
  1. 受信機に Aux1 の能力がない（型や許可）。`grc` の最初の値が `Main` だけなら、これ。
  2. 能力はあるが frontend mode が SingleAnt。`gfm` が SingleAnt なら、これ。DualAnt への変更は Boot 保存と再起動を伴う（人の資料 §6 の別の工程。承認事項）。
- どちらでもない場合: 利得の差（§2 の注意）など。

## 4. MRTKLIB での照会（2026-10-19 実行。DEC-143 の許可。結果は FILE-MOSAIC-MRTK-QUERY）

- MRTKLIB v0.7.11（VM の ~/MRTKLIB、build 済み）の `mrtk relay` は、シリアルを開くと c_iflag・c_oflag・c_lflag を 0 にする（`src/stream/mrtk_stream.c` の openserial。raw・エコー無効。人の資料 §2 を満たす）。path は `/dev/` の後ろを書く（`serial://serial/by-id/...`）。
- `-c FILE` は開いたときに FILE の行を CR LF 付きで送る（`strsendcmd`。`!WAIT ms`・`!HEX` が使える。`@` の後の行は終了時のもの）。
- 照会は USB2（if02。今は誰も開いていない。Gouda のドライバは USB1）で、**読むだけのコマンド**: `grc`、`gfm`、`gga`、`lif,Permissions`。設定は変えない。返答は VM の ~/gnss_records/ に生のまま残す（位置を含みうるのでリポジトリに入れない）。
- 実行の案:

```
mrtk relay -in serial://serial/by-id/usb-Septentrio_Septentrio_USB_Device_0100012541-if02:115200 -out file://<記録先>/usb2_reply.log -c <記録先>/cmds.txt
```

  cmds.txt: `!HEX 0d`、`!WAIT 500`、`grc`、`!WAIT 1500`、`gfm`、`!WAIT 1500`、`gga`、`!WAIT 1500`、`lif,Permissions`、`!WAIT 3000`（15 秒で SIGINT で止める）。

## 5. 照会の結果（FILE-MOSAIC-MRTK-QUERY）と次の段

- `grc`: アンテナは Main+Aux1。`lif,Permissions`: 2 本のアンテナ・方位（mode 2）が許可されている。**型・許可は原因ではない**（§3 の候補 1 は外れ）。
- `gga`: MultiAntenna, Fixed（ドライバの設定が効いている）。
- `gfm`: **Nominal**。Reference Guide 1.0.1 の値（SingleAnt・DualAnt）にない値で、意味は**原本未照合**。副アンテナの観測が一つもないことから、単一アンテナの動作と推測（未確認）。
- 次の段（承認事項 DEC-144）: (a) 読むだけの `help, setFrontendMode`（または `help, sfm`）で firmware 1.1.1 の値の一覧を確かめる。(b) 値に DualAnt があれば `sfm, DualAnt`、`exeCopyConfigFile, Current, Boot`、`exeResetReceiver, Hard, none`（設定の変更・Boot 保存・再起動。人の資料 §6 の別の工程）。Gouda は先に止める。(c) 屋外で MeasEpoch に antenna 1 があり、AttEuler の mode が 0 でないことを確かめる。
- 2 本で動かすときの注意（Hardware Manual §4.2.3.2）: 前置増幅の利得の上限・2 本の差 5 dB 以内。今のアンテナ・ケーブルの利得は**原本未照合**（人の機材の資料で確かめる）。
- 参考: ドライバ（configure_rx true）は起動のたびに `eccf, Current, Boot` を送る（FILE-SEPTENTRIO-SOURCE-REVIEW §3）ので、Current に入れた frontend mode はドライバの次の起動で Boot にも保存される。
