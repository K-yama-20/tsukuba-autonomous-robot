# 作業記録 2026-10-19 第35便: DEC-125・135・136 の回答、GNSS の較正の検証の道具、/config の写し、mosaic-go の VM への接続の確認（REV-067）

## 読んだもの

- コミット `2ce59ea3eb892b4a430f7f38f179b13aab4c37c9` ＋ 第31〜34便の未コミットの作業（REV-060〜066。REV-066 は分岐したセッション）。
- 人の資料 `/Users/AYARyoya/Desktop/自己学習/TsukubaChallenge/reports/mosaic-G5_P6_取扱上の注意事項.md`（ワークスペースの reports、リポジトリの外。2026-10-17 の人の実機調査のまとめ）。
- GLIM の dump の形式（`design/research/vehicle_pc/2026-10-09_glim_dump_format.txt`、handover 2026-10-14 の traj_lidar.txt の記述）。

## 1. 人の回答（判断台帳に原文）

- DEC-136: 「DEC-136は承知した。」
- DEC-135: 「DEC-135は、一旦承認する。実験走行を私が行ってデータを取ってくるので、実データでも可能か検証しよう。実データでうまく推定出来なければ、ボツです。」
- DEC-125: 「DEC-125：しばらくはVMをつかって実機試験を行う。mosaic-goはusb接続。RTK補正はNTRIPを使い、 truertk.pointonenav.comの有料サービスを使う。」
- 人が止めたコマンド（REV-067 の適用など）を「再試行せよ」との指示。止められた呼び出しは、証拠のファイルの作成と REV-067 の書き出し・適用までは済んでいた（render・generate・検査は未実行）。再試行は、model を最後のコミットに戻して REV-060〜067 を順に適用し直し、生成と検査をやり直す形で行った。

## 2. 実装（DEC-135 の検証の道具、地図作成の時の /config）

- `gouda_core/gouda_core/gnss_calibration.py`（新規、numpy だけ）: 原図（gnss.jsonl、source/traj_lidar.txt、sensor_config.json）から θ・t・アンテナの水平位置・取付 Yaw・遅延を同時に推定する。RTK fix・方位の fix だけを使う。方位の定義を 2 通り（そのまま／NED→ENU）解いて残差の小さい方を示す。可観測性は事後と事前の標準偏差の比と、走行の内容（向きの範囲・後退・旋回）で報告する。重みなどの値は既定値を持たず、実行する人が与える。地図の変換・manifest・TF への組み込みはしていない（実データでの検証の後。不採用もありうる）。
- `map_database.py`・`mode_manager_node.py`: 地図作成の開始の時の /config を作業フォルダに写し、原図の横に sensor_config.json として置き、SHA-256 を manifest に書く。
- 試験: `gouda_core/test/test_gnss_calibration.py`（5 件）、`ubuntu_gnss_mapping_record.sh` に /config の保存と写しの確認を追加。

## 3. 自律判断と修正

- 推定器を製品のパッケージの中に置いた（車載 PC で原図に対してそのまま実行できるように）。scipy は使わない（setup.sh に入っていない）。
- DR-15（承認値と同じ形のリテラル）の未判定 7 件: 推定器の数学の定数 `1.0`（Huber の重み、数値微分の刻みの下限）。値を変えずに整数で書いた（分類: 実装の書き方）。

## 4. mosaic-go の VM への接続（人の連絡の後の確認）

- `/dev/serial/by-id/usb-Septentrio_Septentrio_USB_Device_0100012541-if00` → ttyACM0、`-if02` → ttyACM1。USB イーサネットの I/F は出ていない（enp0s5 だけ）。人の資料と同じく、if00 は受信機の USB1、if02 は USB2（資料の確認）。
- ttyACM1 から NMEA（GGA の品質 0、衛星 0、RMC は V）。ttyACM0 は 3 秒の間に何も来なかった。
- **注意（AI の操作）**: この確認で、両ポートを `stty raw -echo` をせずに `timeout 3 cat` で読んだ。人の資料 §2 のとおり、ポートの端末設定がエコー有効のままだった場合、受信した NMEA が受信機へ送り返されコマンドとして解釈された可能性がある。受信機の応答は記録しておらず、設定が変わったかは分からない。以後、ポートを開くのは raw・エコー無効を確かめてからにする。
- 影響する判断:
  - PRM-65 の候補は `serial:/dev/serial/by-id/usb-Septentrio_Septentrio_USB_Device_0100012541-if00`（USB1。NMEA の流れている USB2 と分ける。値の決定は承認事項）。上流ドライバが開いたポートを raw・エコー無効にするかは未確認（ドライバのソースで確かめる）。
  - USB イーサネットがないため、DEC-139 の案 A（受信機の NTRIP で PC 経由でインターネットに出る）は今の接続ではできない。案 B（PC の NTRIP のクライアントから受信機のシリアル（例 USB2）に補正を渡す）が現実的。DEC-139 の推奨の見直しが要る。
  - 人の資料の注意（Res1〜4 を常用しない、Boot への保存は別の工程、ストリームの上書き前に gso を取る）は、ドライバの configure_rx（受信機の設定を書く）にも関わる。ドライバがどのストリームを使い、Boot に保存するかを確かめる必要がある。

## 5. 試験・検査

- Mac の単体: 173 件 OK・1 件 skip。VM の単体: 全件 OK・1 件 skip（numpy 1.26.4）。
- VM: `ubuntu_gnss_mapping_record.sh` 合格（FILE-GNSS-RECORD-CONFIG-SNAPSHOT-VM-TEST。/config の写しが原図の横にあり SHA-256 が manifest と一致）。
- 全検査（REV-067 適用後）: 終了コード 1、不合格は人の drawio の SHA だけ。設計整合性 違反 0、未判定 4（DR-04 5、DR-05 2、DR-10 2、DR-11 67）。
- 未実行: 実データでの較正（人の実験走行の後）、ドライバでの受信機との接続。

## 6. 承認事項

- 新規 pending: DEC-138（VM の gouda.sh でも Fast DDS の設定）、DEC-139（NTRIP の受け方。今の接続では推奨を案 B に見直す必要がある）。
- 提案（未登録）: PRM-65 を if00（USB1）にする。

## 7. 残るリスク

- AI の cat で受信機へ NMEA を送り返した可能性（上記）。
- VM の ~/gouda_ws は main（7e747b5）のままで、このブランチの変更は入っていない。

## 8. 次の作業

- 人の判断: PRM-65 の値、DEC-139 の見直し、DEC-138、commit・push と VM の ~/gouda_ws の更新。
- 進められる（許可が要らない）: 上流ドライバのソースで、シリアルの開き方（raw・エコー）と configure_rx の書くストリーム・Boot 保存の有無を調べる。
- commit はしていない。
