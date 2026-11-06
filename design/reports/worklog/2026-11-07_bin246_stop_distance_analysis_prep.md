# 作業記録 2026-11-07 第246便: 停止距離の解析の準備（REV-275、DEC-495）

## 読んだもの

- コミット `9c449b5`（ブランチ design/mppi-sim-2026-11-03）＋作業ツリー（他のセッションの未コミットの変更を含む）。
- 第243・244便の作業記録、`design/model.yaml` の DEC-346・377・378・488、`design/research/vehicle_pc/2026-11-07_min_speed/`（README・extract.py・analyze.py）、`design/research/vehicle_pc/2026-11-03_vehicle_measurements/vehicle_measurements_2026-11-03.md` の 7 節、`gouda_interfaces/msg/MotionHold.msg`・`DecisionEvent.msg`、`gouda_core/gouda_core/mode_manager_node.py`（motion_hold の発行、`_rule_stop_hold`）、`recorder_node.py`（rosbag の -a）、`local_odometry_node.py`（localization/odometry）、`gouda_core/test/drive_sim_stop_watch.py`、`design/tools/hardcode_scan_roots.json`。
- 車載 PC・模擬の機械には触れていない。gouda.sh は起動していない。

## 1. 人の指示（原文）

- 「作って」（AI の質問「停止距離の計測の手順と解析スクリプトを作りますか？」への回答）
- 「停止距離の計測については、私が様々な速度で実験したものをrosbagに記録するから、それを読んでもらうことにする。よって、今計測手順等を製作する必要はない。代わりに、それ以外の部分を準備せよ。」（DEC-495）
- AI の読み：計測の手順は作らない。「それ以外の部分」は、人が取る rosbag を読むための抜き出しと解析のスクリプトと、記録に何が要るかの説明。

## 2. 変更

- 正本（REV-275）：DEC-495（confirmation、recorded）。実体の変更はない。
- 新しいファイル（基盤。製品のコードではない）：`design/research/vehicle_pc/2026-11-07_stop_distance/`
  - `extract.py`：rosbag（mcap）から control/motion_hold・localization/odometry・log/decision（rule_stop_hold だけ）・/esp32/status を CSV に抜き出す。
  - `stop_distance.py`：止める合図（motion_hold が true に変わった時、または ESP32 の applied_y が 0 になった時）ごとに、直前の速さ・停止距離（進行方向）・横・止まるまでの時間・止まった後の動きを出す。位置は odom.csv か GLIM の軌跡（TUM）。判定できないものは未判定と理由。
  - `test_stop_distance.py`：合成の軌跡での単体試験 10 件。
  - `README.md`：記録に要るもの、使い方、限界。
- 製品のコード・設定・launch・値：**変えていない**。
- 生成物：generate_params.py・render_views.py・render_migration_review.py の出力（値の変更はない）。

## 3. 自律判断

- 置き場所と作りは第210便（`2026-11-07_min_speed/`）にそろえた（rosbag の抜き出しは ROS のある計算機、解析は ROS なし）。
- 速さは位置の差から出し、twist と IMU の積分は使わない（第210便で IMU の積分は傾きで使えなかった。GLIM の軌跡には twist がない）。
- 止める合図を 2 通り（hold・neutral）にした。人がどの走らせ方で記録するかが決まっていないため。
- 解析の条件の既定値（直前 0.5 s、窓 6 s、最後 1 s、0.02 m）は AI が置いた。車体の値ではなく、引数で変えられ、結果の 1 行目に出る。

## 4. 原因の分類（1.6）

- 修正はしていない。

## 5. 先行事例（1.11）

| 探した場所 | 見たもの | 採否と理由 |
|---|---|---|
| リポジトリの中の既存の解析（`2026-11-07_min_speed/`） | rosbag2_py での抜き出し、GLIM の軌跡の位置の差で速さを出す方法 | 採用（同じ形）。区間を手で指定する作りなので、合図の検出は新しく書いた |
| `gouda_core/gouda_core/vehicle_tests/motion_start.py`・`vehicle_test_core.py` | 車体試験の枠組み（発進） | 不採用。PC が指令を出す試験で、この便は人が取った記録を読むだけ |
| `gouda_core/test/drive_sim_stop_watch.py` | 模擬で止まった位置を出す処理 | 考え方は同じ（止まった後の位置）。生の topic を見張る作りなので移していない |
| 公開パッケージ・他チーム・論文 | — | 未調査 |

## 6. 検査・試験

| 検査 | コマンド | 対象 | 結果 |
|---|---|---|---|
| 解析の単体試験（Mac） | `cd design/research/vehicle_pc/2026-11-07_stop_distance && python3 -m unittest test_stop_distance` | 9c449b5＋作業ツリー | 10 件 OK |
| extract.py の構文 | `python3 -m py_compile extract.py` | 同上 | 成功 |
| extract.py を実際の rosbag で | — | — | **未実行**（ROS のある計算機で、記録が来てから） |
| 変更セットの試し | `design/.venv/bin/python design/tools/apply_revision.py REV-275 --dry-run --check` | 同上 | 終了コード 0（本適用に進んだ）。出力の最後の行は DR-15 の未判定 1 件（`vehicle_test_core.py:263` の 1.0、他のセッションのファイル）で、集計の行は確かめていない |
| 本適用 | `apply_revision.py REV-275` → `generate_params.py` → `render_views.py` → `render_migration_review.py` | 同上 | どれも終了コード 0 |
| 設計検査 | `design/.venv/bin/python design/tools/run_checks.py` | 同上 | 終了コード 1。design consistency 0：合格 12・違反 0・未判定 5。generate params 0、intent identity 0。前からの不合格：input integrity、fidelity validator、migration の unit tests |
| 製品の単体試験、模擬、車載 PC、実車 | — | — | 未実行（この便では） |

## 7. 状態

- 移行が正確：変わらず。
- 設計検査：違反 0 件・未判定 5 件（合格ではない）。
- 実車投入可能：人の判断待ち。

## 8. 承認事項・実測待ち

- 実測待ち：停止距離（DEC-346 (1)・DEC-377 (1)・DEC-378 (1)）。人が rosbag を取り、AI が読む。
- 承認待ち：DEC-489（TK-25 の早めの減速）、DEC-343（別のボタン・再起動の後）。

## 9. 残るリスク

- 手動走行モードだけの記録（GLIM が動いていない）には位置がなく、停止距離を出せない。
- 手動の停止と自律走行の停止は ESP32 までの経路が違い、同じ停止距離になるかは未確認。
- 時刻のずれ（GLIM の位置の時刻と PC の時計、位置の遅れ）は直していない。ずれ L 秒で、停止距離は 速さ × L だけずれる。
- extract.py は実際の rosbag で動かしていない。

## 10. 次の作業

- 人：rosbag の記録。
- AI：記録が来たら抜き出しと解析をし、結果を実測の候補として出す。
- 止まっている作業：停止点を置く位置の数値の確定（DEC-488 の d）。
- コミット：していない。車載 PC への反映：未実行。
