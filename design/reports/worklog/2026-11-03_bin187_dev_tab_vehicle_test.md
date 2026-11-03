# 第187便 作業記録：/dev タブと車体試験、動き出しの試験（REV-200、DEC-411・412）

- 日付：2026-11-03
- 読んだコミット：0e260f3
- 人の指示の原文：DEC-411
- DEC-409・410 は元のチャットの作業ツリーの REV-198・199 で読んだ（このブランチには未コミットなので参照 ID にしていない）

## 自律判断した変更と理由

- 指令の経路は IFD-16 へ直接（DEC-412 で承認待ち）。motion_hold は手動走行で常に true、補償は軸ごとで T の測定を歪める。下流は実走と同じ
- 実行は別の node（ND-20）、要求は Action（IFD-58）。intent の「長時間で取消可能な処理は Action」と IFD-37 に合わせた
- 条件は YAML と画面の入力。実測値はコードに持たない。初期値は提案
- ロックは続く段差の遅れで判定する。IMU でロックの瞬間を見分ける根拠がないため
- 中止のボタンは入力欄の上に置いた（画面が低いと入力欄の下は隠れるため）

## 修正の原因の分類（1.6）

- 実装：遅れた IMU の標本で遅れが負になった（x86 の試験で発見）。区間の開始より前の標本を検出から除いた
- 実装：ND-20 の説明の語が DR-06 に当たった。文言を直した

## 先行事例（1.11）

| 探した場所・検索語 | 候補 | 採否と理由 |
|---|---|---|
| リポジトリ内 | map/convert の Action、MonitorServer の追加ルート、DecisionEvent、esp32_sim、stack.sh | 採用 |
| Web「ROS 2 step response latency cmd_vel IMU dead time」 | AlbericDeLajarte/IMU_transfer_function（2 個の IMU で伝達関数）。Jazzy 対応・ライセンス・保守は未確認 | 不採用。IMU が 1 個で、段差の無駄時間と状態遷移を測りたいため |
| Web「Nav2 calibration vehicle characterization deadband」 | 該当なし（docs.nav2.org に走行特性の測定の道具は見当たらない） | — |
| rosbag | 既存の記録 | 併用可。試験の結果の計算には CSV を使う。つくばチャレンジの他チームは未調査 |

検索 2 回だけで、網羅ではない。

## 実行した検査・試験

| 検査 | コマンド | 対象 | 結果 |
|---|---|---|---|
| 単体試験（Mac） | `unittest discover -s gouda_core/test` | 作業ツリー（0e260f3 ＋変更） | 342 件 OK（skip 15）。その後の新規 1 件と文言の変更を含め test_vehicle_test_core は 14 件 OK |
| 結合（x86、~/gouda_ws_sim、esp32_sim、合成 IMU、stack.sh） | `bash gouda_core/test/ubuntu_vehicle_test.sh` | 同上 | 全項目 PASS：完走、T・遅れ・t_lock の回収、中止、続けての実行、実行中の自律走行・地図作成の拒否、手動以外の拒否 |
| 画面 | デモのサーバに x86 の結果を読ませて目視 | 同上 | 表と波形を確認。実行・中止のボタンは API で確認（画面からは押していない） |
| 設計検査 | `run_checks.py` | 同上 | 違反 0・未判定 5。input_integrity・intent_identity・migration の FAIL は変更前と同じ（migration_tests の失敗 2 件も同じ） |
| 手動の優先で中止 | — | — | 未実行（模擬でゲームパッドを出していない） |
| 実車 | — | — | 未実行 |

## 残るリスク

- 実際の IMU で、静止のノイズと解除の衝撃・継続の判定が足りるかは未確認
- 残った動きで、短い中立の後の段差の遅れは短めに出る。t_lock の境界付近は波形を確かめる
- COMMAND の周期 0.1 s がパルス幅の分解能を決める
- ファームは変えていない。STATUS の 50 ms が DAC の時刻の分解能

## 承認事項・実測待ち

- 承認待ち：DEC-412
- 実測待ち：T、t_lock、動き出しの遅れ（DEC-409、DEC-378）

## 次の作業

- 人：実車の試験（docs/vehicle_tests.md）、DEC-412 の回答、push の判断
