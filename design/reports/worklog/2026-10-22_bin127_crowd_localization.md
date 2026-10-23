# 第127便 作業記録: 人混み・他のロボットの中での自己位置推定の対策（REV-156、DEC-290〜293）

日付: 2026-10-22

## 読んだもの

- コミット `31a6e1d9881459a62976bc042f9941063ece7eac`（作業ツリーに未 commit の変更あり。第126便まで）
- `design/reports/status.md`、`design/intent.md`（v14、`9bf08d3ebe24`）、CLAUDE.md の 1 章
- `design/proposals/localization_selection.md`、`gnss_localization_submodule_responsibility.md`、`stage56_navigation_localization_plan.md`
- `design/docs/regulations_2026.md`（SR-04・08・15）、model.yaml の DEC-037・130・134・144
- `gouda_core/gouda_core/a3_points_node.py`、`gouda_core/launch/gouda_localization_a3.launch.py`

## 人の指示（原文）

「現状だと、slamベースのナビゲーションとなっているが、当日は観客や他のロボットが周囲にたくさんいる為、lidarによるslamは性能が悪くなる恐れがある。これに対する対処を考えよ。例えば、事前地図とimuとgpsによるナビゲーションをメインとし、lidarは何らかの方法で補助的に活用する、など。」

## したこと

- 提案 `design/proposals/crowd_robust_localization_2026-10-22.md` を作った。
- REV-156 で DEC-290〜292（承認）と DEC-293（実測）を登録した。正本の内容（entity）・コード・設定は変えていない。

## 自律判断した変更とその理由

- なし（提案と記録だけ）。

## 要点

- 自律走行中は SLAM ではなく事前地図の上の自己位置推定（GLIM の odometry、NDT・EKF）。GNSS は初期位置だけ。
- 車輪のエンコーダがないため、GNSS が切れると位置を保てるのは LiDAR だけ。人の例示の「GNSS＋IMU が主、LiDAR は補助」は、GNSS の切れ目で破綻するか NDT に頼って跳ぶ（推測と AI の計算）。
- 推奨: c（NDT の入力を人の頭より高い点に絞る、食い違いの見張り）をすぐ → 人混みの記録で評価 → a（RTK fix の GNSS と NDT を品質で重み付けして融合）。

## 承認事項と実測待ち

- DEC-290 方針（推奨 c → 評価 → a）
- DEC-291 NDT の入力の高さの帯（推奨 足す、h は tbd）
- DEC-292 車輪のエンコーダ（推奨 評価の後に判断）
- DEC-293 人混みの記録と評価（実測）

## 実行した検査・試験

- `design/.venv/bin/python design/tools/apply_revision.py REV-156 --dry-run --check`（作業ツリー、基点 31a6e1d）: 新しい違反 0、新しい未判定 0。
- `apply_revision.py REV-156`、`render_views.py`・`render_migration_review.py`・`generate_params.py`: 終了コード 0。
- `run_checks.py`: 終了コード 1。design_check は違反 0・未判定 5（第126便と同じ）。migration の違反は第115便からの 6 件（原本 drawio・`.DS_Store`、intent の旧要求の行）だけ。
- 単体試験・VM の試験: 未実行（コードの変更なし）。

## 原因の分類（1.6）

- 修正ではないため該当なし。

## 残るリスク

- 人混みで NDT・GLIM が実際にどれだけ崩れるかは未確認（推測）。評価（DEC-293）まで、対策の効果は分からない。
- GNSS の RTK fix・方位は実車で未確認（DEC-139、DEC-144 の (c)）。a は、これが確かめられるまで進められない。
- XT-32 の上側の視野 +15° は記憶によるもので原本未照合。
- autoware_ekf_localizer が複数の姿勢の入力を扱えるかは上流で未確認。

## 更新した生成物

- `design/model.yaml`（DEC-290〜293 の追加）と、render_views 等で再生成した `design/generated/` の判断台帳の一覧。

## 次に進められる作業と、止まっている作業

- 進められる: DEC-291 の帯の比較をオフラインで行うスクリプトの準備（既存の rosbag で、承認に依存しない基盤作業として）。
- 止まっている: GNSS を走行中に使う設計（DEC-290）、gouda_a3_points の変更（DEC-291）、値の決定（DEC-293）。
