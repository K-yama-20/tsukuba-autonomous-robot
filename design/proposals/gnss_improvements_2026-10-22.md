# GNSS まわりの現状と改善点（提案 第1版、2026-10-22）

状態: 提案（AI の作業）。人の指示「現状の構成を把握して、GNSS回りの改善点を考えよ」による。実装はしていない（DEC-106）。承認事項は DEC-294〜298。

## 1. 今の構成（2026-10-22 に確かめた事実）

| 部分 | 中身 | 状態 |
|---|---|---|
| 受信機 | mosaic-go G5 P6、firmware 1.1.1。frontend mode は DualAnt（Boot に保存、2026-10-19）。2 本のアンテナは左右に 0.34 m（DEC-149） | 屋外での方位の確認は**まだ**（G-GNSS-NO-HEADING が open） |
| ドライバ ND-19 | septentrio_gnss_driver 1.4.8、USB1（PRM-65）、configure_rx true（起動のたびに受信機を設定し Boot に保存）。方位のオフセット 90 度は /config から | 起動のたびに `sntp, on` が拒否される（雛形の ntp_server: true） |
| 補正（案 B1） | 段 1〜4 は実装・導入済み（記録の伏せ字、gnss_rtk.yaml の ntrip の節、supervisor が str2str を USB2 で起動、setup.sh に rtklib）。VM に str2str と gnss_rtk.yaml（mode 600）がある。最後の起動の記録では「ntrip from gnss_rtk.yaml」（ファイルは有効） | 受信機をつないだ状態で中継が動いた記録は**ない**。段 5（monitor）・段 6（VM の試験・屋外の RTK fix）は未着手。NTRIP v1・TLS なしの受け入れ（第66便の問い）と DEC-152 は回答待ち |
| 記録 | 地図作成の間、navsatfix・pvtgeodetic・atteuler・attcoveuler を gnss.jsonl に全項目で記録し、manifest に SHA-256 と件数 | **実の地図作成 3 回（2026-10-22）の GNSS はすべて mode 0（解なし）、方位も mode 0・error 1**。2026-10-19 の地図の gnss.jsonl は 0 行。今ある地図はどれも GNSS と対応づけられない |
| 地図作成の開始の警告 | 点群と IMU だけ（`monitor_core.MAPPING_START_SENSORS`） | GNSS の解がないまま地図を作っても何も出ない |
| 自己位置推定 ND-07 | NDT＋EKF（案 A3）。GNSS は使っていない | GNSS による初期位置（DEC-133）・見張り（DEC-134）・融合（DEC-290）はどれも、地図と GNSS の対応（DEC-127・135）が前提 |
| 較正 | gnss_calibration.py（DEC-135、実データで検証してから採否） | 実データ（RTK fix の地図作成）がないので未検証 |

依存の鎖: **屋外で fix・方位 → RTK（中継）→ RTK fix の地図作成 → 地図と GNSS の対応（較正）→ 初期位置・見張り・融合**。今は最初の段で止まっている。

## 2. 改善点（優先の順）

### 2.1 すぐ確かめること（コードの変更なし。人の作業と AI の確認）

1. **屋外の確認を 1 回でまとめて行う**（推奨）。受信機を VM につなぎ、Gouda を起動して空の開けた所で:
   - 方位: MeasEpoch に副アンテナ（番号 1）の観測、AGC（main・Aux1）、AuxAntPositions の基線 ≈ 0.34 m、AttEuler の mode ≠ 0（ガイド §6）。
   - RTK（段 6 の屋外の部分）: supervisor が中継を起動し、`ntrip_relay_state` が「接続・通信中」になり、PVTGeodetic の mode が 4（RTK fixed）、mean_corr_age が有限。
   - 時間の実測（DEC-147 の tbd）: 電源を入れてから単独測位・RTK fix・方位 fix までの時間。
   - 前提: NTRIP v1・TLS なしの受け入れ（DEC-298）。Point One が v1 を受け付けるかは、このとき初めて分かる。
2. **地図作成は空の見える場所で、RTK fix を確かめてから行う**（DEC-135 の検証のため）。今の 3 つの地図は GNSS と対応づけられない。

### 2.2 小さな実装（それぞれ許可が要る）

| # | 改善 | 理由 | DEC |
|---|---|---|---|
| A | 地図作成の開始の警告に GNSS を足す（RTK fix でない・方位が出ていないときに「この地図は GNSS と対応づけられない」と出す。地図作成は止めない） | 今回、解のないまま 3 つの地図が作られ、気づく手段がなかった | DEC-294 |
| B | 地図の manifest に GNSS の質の要約（RTK fixed・float・単独・解なしの件数、方位 fixed の件数）を書き、地図の一覧に「GNSS 対応の可否」を出す | DEC-133 の条件 (7)「対象は対応のある地図だけ」を、地図を開かずに判断できる。今の要約は件数と SHA-256 だけ | DEC-294 |
| C | 副アンテナの見張り: 主アンテナで衛星が見えているのに方位が「測定が足りない」（AttEuler error 1）のまま続くとき、monitor に「副アンテナの観測なし（frontend mode・ケーブルを確認）」と出す | ドライバは setFrontendMode を送らない。受信機を工場出荷に戻すと黙って単一アンテナに戻る（2026-10-19 と同じ症状） | DEC-295 |
| D | 雛形の `ntp_server` を false にする | 受信機（firmware 1.1.1）が毎回 `sntp, on` を拒否し、起動のたびに ERROR が出る。Gouda は受信機の NTP を使わない（第40便からの承認待ちの扱いを正式に登録） | DEC-296 |
| E | 段 5（monitor に中継の状態・補正の年齢・RTK の mode） | 補正の途切れを走行の前に見える形にする（DEC-133 の初期化の判断の材料） | 既存（DEC-151 の段 5） |
| F | 地図作成の記録に、受信機の状態（ReceiverStatus の AGC、QualityInd）を低い頻度で足す | 方位・RTK が出なかったとき、後から原因（アンテナの利得、干渉）を調べられない。今は 4 つの topic だけ | DEC-297 |

### 2.3 設計（後で。前提がそろってから）

- GNSS による NDT の見張り（DEC-134、crowd 提案の案 c→a）: 地図と GNSS の対応ができた後に、RTK fix の位置と NDT の位置の差を見張る。今は前提（対応のある地図）がない。
- 方位の精度: 基線 0.34 m では、データシートの 1 m で 0.15 度より悪い（推測で 0.4 度前後）。初期の向きとしては十分と見込むが、屋外の確認で AttCovEuler から実測する。
- configure_rx true は起動のたびに Boot に書く（DEC-140 で受け入れ済み）。受信機のフラッシュの書き込みの回数が増える。問題が出たら configure_rx false の案（提案 mosaic_receiver_setup_configure_rx_false.md）に戻れる。

## 3. 承認していただきたいこと

| DEC | 内容 | 推奨 |
|---|---|---|
| DEC-294 | A・B（地図作成の開始の GNSS の警告、manifest の GNSS の質の要約と地図の一覧の表示） | 承認 |
| DEC-295 | C（副アンテナの観測なしの見張りを monitor に） | 承認 |
| DEC-296 | D（雛形の ntp_server を false） | 承認 |
| DEC-297 | F（地図作成の記録に ReceiverStatus・QualityInd を足す） | 承認（頻度は雛形の 500 ms のまま） |
| DEC-298 | NTRIP v1・TLS なし（認証は base64 で暗号化されずに流れる）を受け入れて、屋外で RTK を試すか | 受け入れて試す（Point One が TLS の接続を出しているかは人が契約の資料で確かめ、あれば別に検討） |
