# 第199便 作業記録：XT-32 の見える範囲の台帳と TRB-001 の訂正（REV-215・216、DEC-426・427）

- 日付：2026-11-06
- 読んだコミット：0e260f3（作業ツリーに未コミットの変更あり。ほかのセッションと共有）
- 読んだもの：CLAUDE.md、`design/reports/status.md`、DEC-418・REV-207（IMU の台帳）、TRB-001、`research/vehicle_pc/2026-10-14_evening_maps_rosbag.txt`、XT-32 に触れた提案・作業記録
- 人の指示：DEC-426 に原文で記録した（2 通）。TRB-001 を直すかの回答「直して」は DEC-427 に原文で記録した

## したこと

- 人の外付けドライブ（Crucial）の rosbag 2 本（2026-10-14 夕方、x86 の PC の地図作成）から、`/sensors/xt32/points` を 10 通に 1 通（1172 通）読み、見える範囲を求めた。読み取りだけ。生データはリポジトリに入れていない。
  - 読み取りは既存の `2026-10-14_evening_scripts/mcap_min.py`（外部パッケージなし）。
  - 新しいスクリプトと出力：`research/vehicle_pc/2026-11-06_xt32_visible_range/`。REV-215 で証拠として登録。
- 台帳 `design/docs/lidar_xt32_spec.md` を新規に作った（IMU の `imu_adis16607_spec.md` と同じ形）。
- 人の回答（DEC-427）で、`design/troubleshooting/ledger.yaml` の TRB-001 を実測の値に直した（REV-216）。mechanism の式を 1.182 − d·tan15.98° に、計算を 2.5 m で 0.47 m・1.5 m で 0.75 m・1.0 m で 0.90 m に、how_to_confirm (1) の目安を物の高さからの式に。旧値は mechanism に残した。decision_refs に DEC-427、related_refs に PRM-125（obstacle_max_range、未確定で上流の既定 2.5 m）を足した。K-6（過去の提案）は直していない。

## 結果（実測、rosbag）

- ビーム 32 本：ring 0 +15.05°〜ring 31 −15.98°、間隔 1.00°。垂直の視野 31.04°。
- 水平 360°、2000 列（0.18°）。返りの割合 0.982（1 通の中央値）。方位による差は小さい。
- 車体・取付具による固定の死角は見つからなかった（2 m 未満の点が同じ升に出る割合は 9 % 以下）。
- 地面からの高さ 1.182 m。地面が見え始める距離 4.0〜4.2 m（計算 4.13 m）。
- 一番遠い点は 1 通の中央値 130 m（場所による）。一番近い点 0.052 m（雑音かどうかは未確認）。
- 2 本目の bag の 5 通は 63744 点（32 × 1992）で、集計から外した（`results.txt` に時刻）。

## 自律判断

- 「台帳（imuのデータとかを載せてるやつ）」を DEC-418 の IMU の仕様の文書と解釈し、同じ置き場に XT-32 の文書を並べた。IMU の文書に足して名前を変えるのは、ファイルの改名で承認事項になるため（1.9）。
- 台帳の文書は証拠として登録していない（後で取付の実測などを足すため）。スクリプトと出力だけ登録した。
- 車体の方位は、記録時の /config（人の入力）の取付の軸と yaw から求めた。

## 原因の分類（1.6）

- TRB-001 の訂正：設計（安全解析の前提の値の誤り。base_link からの取付の高さを地面からの高さとして使った）。人の承認（DEC-427）を得て台帳を直した。

## 検査・試験

- 解析：`design/.venv/bin/python -I xt32_fov.py ../2026-10-14_evening_scripts fov.npz 10 <bag 2 本>`、`xt32_fov_sum.py`、`xt32_near_persist.py`（Mac、作業ツリー 0e260f3＋未コミット）。出力は `results.txt`。
- `apply_revision.py REV-215 --dry-run --check`：新しい違反 0、新しい未判定 0。その後に適用。
- `render_views.py`・`generate_params.py`・`render_migration_review.py`：終了コード 0。
- `run_checks.py`：終了コード 1。設計検査 違反0件・未判定5件（合格 12）。generate_params・intent_identity は PASS。input_integrity・migration_validator・migration_tests の FAIL は、第184便で記録済みの不一致（`SystemArchitecture.drawio` と `.DS_Store`）で、今回の変更によるものではない（`migration_tests.txt` の path）。
- REV-216：`apply_revision.py REV-216 --dry-run --check` で新しい違反 0・未判定 0、適用、再生成 3 件は終了コード 0。`run_checks.py` は終了コード 1 で結果は REV-215 の後と同じ（設計検査 違反0件・未判定5件、FAIL は同じ既存の不一致）。台帳の試験 `test_troubleshooting_ledger`（スキーマ、キーの順序、参照先、ID の重複）は ok。
- 単体試験・実車：未実行（コード・設定は変えていない）。

## 承認事項・実測待ち

- TRB-001 の直し：issue K-yama-20/tsukuba-autonomous-robot#73 に登録し（1.10・1.12）、人が承認（DEC-427）、直した。
- 承認の候補（未登録）：1.015 m を地面からの高さとして使った他の記録の洗い出し（#73 の案 2）。
- 実測待ち：Q-04・DEC-099（取付の傾き、2026-10-14 の後の取付の変更、遮り）。データシートの原本（距離の仕様、最小の距離、精度）は原本未照合。

## 残るリスク

- TRB-001 の旧値を判断の材料にした過去の決定（costmap の帯、距離など）は見直していない。低い物が見えなくなる距離は旧値より遠い（1.5 m 先で 0.75 m より低い物は見えない）。
- 値は 2026-10-14 の取付のもの。その後に取付が変わっていれば合わない。
- 走行の場所は未確認。距離の値は場所による。

## 更新した生成物

- `design/model.yaml`（REV-215 の適用：DEC-426、FILE 4 件。REV-216 の適用：DEC-427）、`apply_revision.py` が出す差分の報告、`design/generated/` の再生成（スクリプトで）、`design/reports/` の検査結果。

## 次の作業

- 進められる：1.015 m を使った他の記録の洗い出し（承認があれば）。
- 止まっている：Q-04・DEC-099 の実測（人）。
