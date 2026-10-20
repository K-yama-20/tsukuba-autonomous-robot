# 作業記録 2026-10-19 第41便: 副アンテナの確認（マニュアルと MRTKLIB での照会、REV-075）

## 読んだもの

- コミット `3341602` ＋ 未コミットの REV-073・074 の作業。status.md（第40便）、G-GNSS-NO-HEADING、人の資料 `reports/mosaic-G5_P6_取扱上の注意事項.md`。
- Septentrio の mosaic-G5 Reference Guide（firmware 1.0.1、2025-11-13）と mosaic-G5 Hardware Manual v1.1.1（2025-05-28）。公開の PDF を AI の作業領域に取得し pdftotext で読んだ（リポジトリには入れない）。製品のページは HTTP 403 で読めなかった。P6 の型は両方の資料に載っていない（**原本未照合**）。
- MRTKLIB v0.7.11（VM の ~/MRTKLIB、git dd325d6）のソース: openserial（raw・エコー無効）、strsendcmd（-c のコマンドの送り方）、str2str の readcmd。MRTKLIB の quickstart（Web）は MADOCA-PPP の Docker の手引きで、副アンテナの記述はない。

## 1. 人の指示と回答（判断台帳に原文）

- 指示: 「mainとauxのアンテナを入れ替えたところ、mainのみ受信できた。…mosaic-go g5 p6のマニュアルを参照して、mrtklibを使って動作確認をせよ。mrtklibはvmにいれてある」
- DEC-143（照会の許可）: 「許可する。USB2（if02）で mrtk relay を使い、grc・gfm・gga・lif,Permissions の照会だけを送ってよい。設定は変えないこと。」
- 経緯: 最初に許可なしで照会を送ろうとしたところ、Claude Code の権限の判定で止められた（何も送っていない）。その後、人の許可を得て実行した。

## 2. 実行したこと

- VM で `mrtk relay -in serial://serial/by-id/...-if02:115200 -out file://<記録先>/usb2_reply.log -c cmds.txt`（15 秒で停止）。送ったのは CR と照会 4 件だけ。前に fuser で USB2 を誰も開いていないことを確かめた。Gouda は動いたまま（ドライバは USB1）。
- 結果（FILE-MOSAIC-MRTK-QUERY）: 4 件とも受理。能力 Main+Aux1、許可 nb_ant 2・attitude mode 2・movingbase、方位の計算 MultiAntenna, Fixed、**frontend mode は Nominal**。NMEA は 0 行（位置なし）。生の記録は VM の ~/gnss_records/mrtk_check_20261018T132131/（VM の時計は 10-18 を示す）。

## 3. 判断と残る点

- 型・許可は原因ではない。Hardware Manual §4.2.3.2 では 2 本の動作に `setFrontendMode, DualAnt` を Boot に保存して再起動する必要がある。Nominal は 1.0.1 の資料にない値で、意味は原本未照合（単一アンテナの動作と推測）。
- 承認事項（新規）DEC-144: (a) `help, setFrontendMode` で 1.1.1 の値の一覧を照会、(b) DualAnt があれば Gouda を止めて sfm DualAnt・Boot 保存・再起動、(c) 屋外で副アンテナの観測と方位を確かめる。
- 自律判断: 証拠のファイル 2 つの作成と REV-075 の記録だけ。コード・設定は変えていない。

## 4. 検査

- `design/.venv/bin/python design/tools/apply_revision.py REV-075`、`design/.venv/bin/python design/tools/run_checks.py`（コミット 3341602 ＋ 未コミットの作業ツリー）: 設計検査 合格 13・違反 0・未判定 4（DR-04 5、DR-05 2、DR-10 2、DR-11 66）。移行の検査は違反: 人の drawio の SHA-256 と、`design/docs/extraction_20261008_01a11af4/` の `.DS_Store` 2 件（macOS が書くファイル。AI は触っていない。扱いは人の判断）。
- 単体の試験: 未実行（コードの変更なし）。

## 5. 残るリスク

- Nominal の意味が未確認のまま。DualAnt での利得の条件（2 本の差 5 dB 以内など）は今のアンテナで原本未照合。
- frontend mode の変更は Boot 保存と再起動を伴う（人の資料 §6）。ドライバは起動のたびに Boot へ保存するので、Current の変更はいずれ Boot に入る。

## 6. 生成物・次の作業

- 更新: design/model.yaml（REV-075 による）、生成物（apply_revision の再生成）、status.md、本記録。
- 次: DEC-144 の回答待ち。DEC-139（NTRIP 案 B1）も回答待ち。commit はしていない。

## 追記（第42便、REV-076）

- 人の回答 DEC-144（原文）: 「DEC-144 を承認する。まず help, setFrontendMode で値の一覧を照会し、結果を報告してから DualAnt の設定に進むこと。」
- 照会（USB2、mrtk relay、fuser で空きを確認、Gouda は動いたまま）: `help, setFrontendMode` → `$R;` で「setFrontendMode (=sfm), fmMode / getFrontendMode (=gfm) / "Operating mode of the frontend"」。値の一覧はない。`help, fmMode` → `$R?`（引数が無効。設定は変わらない）。記録は FILE-MOSAIC-MRTK-QUERY の追記、生の記録は VM の ~/gnss_records/mrtk_help_*/。
- Web: firmware 1.1.x の mosaic-G5 P 系の Reference Guide は見つからなかった。
- 判断: 指示は「一覧を照会し、報告してから設定に進む」。一覧で DualAnt を確かめられなかったので、設定（sfm・Boot 保存・再起動）には進まず報告した。
- 検査: apply_revision REV-076、run_checks（3341602 ＋ 作業ツリー）: 設計検査 違反 0・未判定 4。移行の検査の違反は第41便と同じ。
- 次の案（人の判断）: `sfm, DualAnt` を Current にだけ送る（Boot 保存なし）。`$R:` なら値として有効、`$R?` なら無効で設定は変わらない。受理されたら gfm で確かめ、Gouda を止めて Boot 保存・再起動に進む。

## 追記（第43便、REV-077）

- 人の許可 DEC-145（原文）: 「sfm, DualAnt を Current にだけ送ってよい（Boot 保存・再起動はしない）。応答と gfm を報告すること。」
- 送ったもの（USB2、mrtk relay、fuser で空きを確認）: CR、gfm、sfm, DualAnt、gfm。返答: `$R: gfm` FrontendMode, Nominal → `$R: sfm, DualAnt` FrontendMode, DualAnt → `$R: gfm` FrontendMode, DualAnt。生の記録 VM の ~/gnss_records/mrtk_sfm_20261018T133616/。
- 受信機の設定の変更（Current のみ）。Boot 保存・再起動はしていない。効くのは次の reset から（Reference Guide 1.0.1）。
- 残るリスク: ドライバ（configure_rx true）が起動し直すと eccf, Current, Boot で DualAnt が Boot に入る（人の資料 §6 の別工程の外で保存される）。DualAnt では ANT_2 を開放にしないこと、2 本の利得の差 5 dB 以内（Hardware Manual §4.2.3.2。今の機材は原本未照合）。
- 検査: apply_revision REV-077、run_checks: 設計検査 違反 0・未判定 4。移行の検査の違反は第41便と同じ。
- 次（人の判断）: Gouda を止め、eccf, Current, Boot と exeResetReceiver, Hard, none を送る。再起動の後に gfm を確かめ、Gouda を起動して屋外で MeasEpoch の副アンテナの観測と AttEuler の mode を確かめる。

## 追記（第44便、REV-078）

- 人の許可 DEC-146（原文）: 「Gouda を止め、eccf, Current, Boot と exeResetReceiver, Hard, none を送ってよい。再起動の後に gfm を確かめて報告すること。」
- 実行: VM で bash gouda.sh stop（グループ 159455 の残りなし）、fuser で両ポートが空き。USB2 で mrtk relay（CR、gfm、eccf, Current, Boot、exeResetReceiver, Hard, none）。返答の記録は 0 bytes（reset で USB が切れたためと推測）。by-id の名前は作り直され、if02 は ttyACM2 に変わった。
- reset の後の照会（USB2）: `$R: gfm` FrontendMode, DualAnt、`$R: gga` GNSSAttitude, MultiAntenna, Fixed。生の記録は VM の ~/gnss_records/mrtk_boot_reset_* と mrtk_after_reset_*。
- 判断: Boot 保存と reset は効いた（eccf と reset の個々の応答は未記録）。
- 検査: apply_revision REV-078、run_checks: 設計検査 違反 0・未判定 4。移行の検査の違反は第41便と同じ。
- 残るリスク: 副アンテナの観測と方位は未確認。DualAnt では副アンテナを外さないこと（Hardware Manual §4.2.3.2）。ttyACM の番号が変わったが、Gouda は by-id の名前だけを使うので影響しない（DEC-141）。
- 次: Gouda を起動（bash gouda.sh start）し、屋外で MeasEpoch の副アンテナの観測と AttEuler の mode を確かめる。commit はしていない。
