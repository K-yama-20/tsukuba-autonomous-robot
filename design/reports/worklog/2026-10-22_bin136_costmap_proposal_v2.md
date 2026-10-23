# 作業記録 2026-10-22 第136便: costmap の入力の直しの提案 第2版（完走優先）

## 読んだもの

- 作業ツリー `31a6e1d` ＋ 未コミットの変更（別のセッションの第127〜135便）。`design/intent.md`: 書き始めは第15版（SHA-256 b24fce29a261…）、書き終えた後に読み直した版は SHA-256 23170969d338…（1 行目の言い回しの変更。内容への影響なし）。
- 第130便の提案（第1版）、第134便の作業記録、`proposals/competition_no_auto_pause_2026-10-22.md`、`docs/regulations_2026.md`、status.md（第104便の外付けの rosbag の記述）。
- 上流のソース: pointcloud_to_laserscan jazzy ブランチ（2.0.2）の `pointcloud_to_laserscan_node.cpp` を新しく読んだ。Nav2 1.3.13、perception_pcl jazzy は第130・134便で読んだもの。

## 1. 人の指示（原文）

「Rewrite the costmap proposal as v2 for completion-first: XT-32 only, base_link band (compare pcl_ros vs pointcloud_to_laserscan on rosbag), explicit ranges, no expected_update_rate, STVL/MID-360/Nebula/PTP after the final, plus the decision questions. No implementation.」

## 2. 行ったこと

- 提案 第2版 `design/proposals/costmap_inputs_completion_v2_2026-10-22.md` を新規に作成した。承認事項 V2-1〜V2-6、人の判断 1〜9（仮の番号、台帳に未登録）。
- 第1版の冒頭の注に、第2版に置き換えたことを書き足した。
- 番号は reserve_ids.py で予約した（第136便のみ）。

## 3. 新しく確かめた事実（pointcloud_to_laserscan jazzy 2.0.2）

- `target_frame` が点群の frame と違えば、点群全体を TF で変換する（170 行）。`min_height`・`max_height` で z を切る（191 行）。距離は target_frame の x・y の hypot（199 行）。方位の刻みごとに一番近い点だけを残す（229-232 行）。
- `use_inf: true` なら、点のない方位は inf（160-163 行）。
- 出力の購読者がいないと入力の購読を外す（`subscriptionListenerThreadLoop`、108-135 行）。component として登録（237 行）。
- 推論: LaserScan を ObstacleLayer に入れると点の z は base_link の高さ（odom の z）になるので、Nav2 の帯を広げないと下り坂で捨てられる。

## 4. 自律判断した変更

- なし（提案の文書と記録だけ）。

## 5. 検査・試験

- 設計検査: 未実行（正本を変えていない）。単体試験: 未実行。rosbag の比べ方・実機の計測: 未実行（VM に接続できない）。

## 6. 残るリスク

- 案 X（pcl_ros）が XT-32 の点の並びで落ちないかは未試験。
- 10/14 の外付けの bag に、木の下・坂・人の場面と、必要な topic があるかは未確認。
- 人の回答 A〜E（第130便）、第134・136便の結論は台帳に未登録。

## 7. 次

- 進められる: 人の判断 1〜9 の回答を受けて、承認事項を台帳に登録する。rosbag の比べ方の手順と解析のスクリプトの計画（試験基盤）。
- 止まっている: 実装（DEC-106）、比べ方の実行（VM に接続できない）。
