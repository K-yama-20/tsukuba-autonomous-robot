# 作業記録 2026-10-19 第37便: 人の指示 DEC-141（PRM-65 の承認、by-id の名前だけを受け付ける、DEC-140 の判断の材料）（REV-069）

## 読んだもの

- コミット `2ce59ea3eb892b4a430f7f38f179b13aab4c37c9` ＋ 未コミットの REV-060〜068。
- 上流ドライバ tag v1.4.8（commit 5613af2）の configureRx() の block の選び方（784〜974 行）、settings_helpers.hpp の autoPublish、initializeIo（AI の作業領域の clone）。
- 人の資料 `reports/mosaic-G5_P6_取扱上の注意事項.md` §2〜§7・§11。
- コード: device_watch.py、sensor_config.py、sensor_supervisor_node.py、gnss_config.py、既存の試験。

## 1. 人の指示（DEC-141 に原文）

1. PRM-65 を承認（serial:/dev/serial/by-id/usb-Septentrio_Septentrio_USB_Device_0100012541-if00、USB1。ttyACM の番号では指定しない）。
2. センサー（IMU も GNSS も）をいつも by-id の名前で探す。gnss_config に /dev/serial/by-id/ の名前だけを受け付ける検査（実装の許可）。IMU と GNSS を同時につないでも取り違えないことの単体試験。
3. DEC-140 はまだ決めない。決まるまで手でも Gouda でもドライバを起動しない。configure_rx false のときの SBF の出力と人の手順の案。受信機のポートには触らない。commit しない。

## 2. 変更

| 変更 | 内容 | 分類 |
|---|---|---|
| 正本（REV-069） | DEC-141（承認、原文）、PRM-65 を承認値に、configure_rx を PRM-74（未確定、決定先 DEC-140）として新設、ND-18・PRM-65 の解釈、DEC-140 の note | 記録・設定 |
| `device_watch.py` | `BY_ID_DIR`・`by_id_problem()`（/dev/serial/by-id/<名前> 以外を理由つきで拒否） | 実装 |
| `gnss_config.py` | serial: の値は by-id の名前だけ（それ以外は parse_device が None、ドライバを起動せず理由を記録）。configure_rx（PRM-74）を必須に（未確定ならドライバを起動しない） | 実装 |
| `sensor_supervisor_node.py` | IMU の device も by-id の名前でなければ起動せず理由を記録。GNSS の理由に PRM-74 を表示 | 実装 |
| 試験 | `test_serial_by_id.py`（新規 3 件）、`test_gnss_config.py`（configure_rx・ttyACM の拒否を追加、既存の試験を configure_rx を与える形に） | 試験 |

自律判断:
- configure_rx を未確定の設定にした: PRM-65 だけが決まると、Gouda の起動で supervisor がドライバを configure_rx true（雛形）のまま起動してしまい、指示 3 に反するため。値が決まるまでドライバは起動しない（理由は driver_not_started で記録・表示）。
- IMU にも同じ検査を加えた: 指示 2 の「センサー（IMU も GNSS も）をいつも by-id の名前で探すこと」による。それまでの IMU は PRM-54 の値が by-id であるだけで、検査はなかった（「IMU と同じく」とあったが、IMU に検査はなかった）。PRM-54 は by-id なので振る舞いは変わらない。
- 判断台帳の記録の誤り: DEC-141 を最初は確認（recorded）として書き、承認値の根拠の検査（DR-01 APPROVAL_EVIDENCE）に違反した。承認（answered）に直し、model を戻して REV-060〜069 を適用し直した（分類: 記録の誤り）。

## 3. 試験・検査

- Mac の単体: `cd gouda_core && python3 -m unittest discover -s test -p "test_*.py"` → 177 件 OK・1 件 skip。
- VM の単体: 同じ → 全件 OK・1 件 skip（VM の ~/gouda_fix_ws に写して build）。
- 同時接続の試験（模擬の /dev・/sys・/proc）: 両方を抜いて逆の順に差し ttyACM の番号が入れ替わっても、名前ごとに自分の機器の同一性を得て、それぞれのドライバだけを作り直す判定になる。使用中の判定は番号ではなく名前の指す実体で決まる。
- septentrio のドライバは起動していない（VM でプロセスなしを確認）。受信機のポートには触っていない。
- 全検査（REV-069 適用後）: 終了コード 1、不合格は人の drawio の SHA だけ。設計整合性 違反 0、未判定 4（DR-04 5、DR-05 2、DR-10 2、DR-11 67）。DR-15 合格。

## 4. DEC-140 の判断の材料

`design/proposals/mosaic_receiver_setup_configure_rx_false.md`。要点: configure_rx false なら、USB1 に 2 つの SBF のストリーム（msec100: PVTCartesian・PVTGeodetic・PosCovCartesian・PosCovGeodetic・VelCovGeodetic・AttEuler・AttCovEuler・MeasEpoch・ChannelStatus・DOP、msec500: QualityInd・RFStatus・ReceiverSetup・ReceiverStatus）と、`sga,MultiAntenna`・`sto,<heading>,<pitch>` を人の手順で先に設定する。ストリームの番号は gso で未使用の Stream1〜10 から選ぶ（Res1〜4 は使わない）。Boot には保存しない。

## 5. 残るリスク

- 手順のコマンドの書式（block の `+` での並べ方、sga・sto・gno）は実機の応答で未確認。
- configure_rx false で Boot に保存しない間は、電源の再投入で設定が消えうる。

## 6. 次

- 人の判断: DEC-140（と 案 2-a／2-b）、手順 3（commit と VM の更新）。
- commit はしていない。
