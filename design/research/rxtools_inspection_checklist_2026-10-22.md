# RxTools（RxControl）での mosaic-go の検査の手順（2026-10-22、第131便）

人の指示（原文）:「RXtoolsをvmのwindowsにいれた。まずこれで色々検査したい。衛星測位を何度も試したって無駄なことです。受信機は今屋内にあります」

目的: 衛星の信号を 1 つも捕まえない原因を、測位を試さずに受信機の側から調べる（記録 `gnss_no_tracking_investigation_2026-10-22.md`）。メニューの道筋と項目の意味は mosaic-G5 Reference Guide（firmware 1.0.1。実機は 1.1.1、版の差がありうる）から。

## 0. 始める前に（大事）

- 今、受信機は Ubuntu の VM につながっている（`/dev/serial/by-id/...-if00`・`-if02` がある。2026-10-22 に確かめた）。Gouda は止まっている。
- Parallels で USB の「Septentrio USB Device」を Windows の VM に渡す。Windows には仮想の COM ポートが 2 つ出る（USB1・USB2）。RxControl はどちらにつないでもよい（同時に開くのは RxControl だけ）。
- **検査の間、Ubuntu で Gouda を起動しない。** Ubuntu に受信機を戻して Gouda を起動すると、ドライバ（configure_rx true）が受信機を設定し直して Boot に保存する。RxControl で見た状態が上書きされる。
- **設定を変えない・Boot に保存しない**（1〜6 は読むだけ）。RxControl を閉じるときに設定の保存（Copy Configuration）を聞かれたら保存しない。
- 各段の結果（画面の写し、Expert Console の文）を保存しておく。Expert Console の出力はファイルにして渡してもらえれば、AI が読む（位置を含む画面は、リポジトリに入れない）。

## 1. 受信機に今入っている設定をすべて写す（最優先）

AI とドライバが受信機に何を書いたかを、推測でなく受信機から確かめる。RxControl の Expert Console（コマンドを打つ窓）で:

```
lstConfigFile, Current
lstConfigFile, Boot
lstConfigFile, RxDefault
```

- Current と Boot が RxDefault（工場の設定）と違う行が、これまでに書かれた設定のすべて。
- 特に見る行: `setFrontendMode`（DualAnt のはず）、`setAGCMode`、`setSatelliteTracking`、`setSignalTracking`、`setElevationMask`、`setCN0Mask`、`setNotchFiltering`（または Frontend Settings の notch）、`setAntennaOffset`、`setGNSSAttitude`、`setAttitudeOffset`、`setDataInOut`、`setSBFOutput`。
- 衛星の追尾を止めうるのは、追尾の対象（衛星・信号）を減らす設定、高度角・C/N0 のマスク、AGC の固定（frozen）、notch、frontend mode。

## 2. アンテナの給電（電流が流れているか、過電流で切れていないか）

- 受信機の状態の表示（ReceiverStatus の内容。RxControl の受信機の状態の画面。画面の名前は版で違いうる）で:
  - **RxState の ACTIVEANTENNA**: アンテナの端子から電流が流れていると立つ。立っていなければ、アンテナに給電されていない（接続・ケーブル・過電流）。
  - **RxError の ANTENNA**: アンテナの過電流を検出すると立つ。Hardware Manual §4.2: 2 本の合計 150 mA を超えると、**主・副の両方の給電が切れる**。
  - RxError のほかの bit（INVALIDCONFIG など）も写す。

## 3. 前段ごとの AGC（アンテナの信号が届いているか、飽和していないか）

- ReceiverStatus の AGCState（前段ごと、アンテナの番号 0 main・1 Aux1 つき）:
  - **Gain（dB）**: −128 は「前段の PLL が lock していない」。DualAnt の条件は AGC が 30〜50 dB（前置増幅 15〜35 dB）、main と Aux1 の差は 5 dB 以内（Hardware Manual §4.2.3.2）。
  - **SampleVar**: 標準は 100。
  - main と Aux1 の両方の行があるか。
- 屋内でも、アンテナが給電されていれば AGC は意味のある値になる（測位とは関係なく見られる）。

## 4. スペクトル（RF が来ているか）

- **View > Spectral View**。main と Aux1 の両方（選べれば）。
- アンテナの LNA の雑音で、L1・L2・L5 の帯にふくらみが見えるのが普通（推測を含む）。平らなら、その前段に RF が来ていない。
- 狭い帯の干渉（第114便で 1188・1202・1252 MHz 付近の記録）も見える。

## 5. 追尾を止めうる設定を直接読む

Expert Console で（すべて get。設定は変えない）:

```
gfm
gam, all
gst
gnt
gem
gcm
lif, Permissions
```

（引数を省いた get の書き方が通るかは未確認。`$R?` なら引数を足す（例 `gst, all`）。意味: frontend mode、AGC のモード、追尾する衛星、追尾する信号、高度角のマスク、C/N0 のマスク、許可。RxControl では Navigation > Advanced User Settings > Frontend and Interference Mitigation > Frontend Settings、Navigation > Advanced User Settings > Tracking、Navigation > Receiver Operation > Masks）

## 6. （任意）追尾の数

- 衛星の追尾の画面（C/N0）。測位ではなく「信号を 1 つでも捕まえるか」を見る。2026-10-19 は同じ屋内の置き方で衛星 13〜17 を捕まえていたので、屋内でも差は出うる（参考）。

## 7. その後（人の判断。設定の変更）

- 1〜5 の結果で原因が絞れたら、DEC-300（frontend mode を Nominal に戻して比べる）などを人が決める。RxControl で行う場合も、変える前と後の `lstConfigFile, Current` を写す。
