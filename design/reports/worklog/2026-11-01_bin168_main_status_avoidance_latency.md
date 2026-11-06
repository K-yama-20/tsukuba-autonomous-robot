# 第168便 作業記録：main の現状と、回避機動が遅い原因の調査（読むだけ、実装なし）

- 日付：2026-11-01
- 読んだコミット：origin/main 8ee71628f37f45a682bebcecb901dee356932fa0（作業ツリーは test/plan-a-scan-band-2026-11-01。コードは main と同じで、status.md と第167便の記録に未コミットの追記がある）
- 人の発言（原文）：「mainを見て、現状を報告せよ。特に、実機の回避機動等がとても遅い。各種パラメータ、更新周期とかが遅すぎるのだと思う。dec-336のA案による実機走行実験はまだ出来ていない。」
- 読んだもの：status.md、第160・163・164・165・167便の記録、DEC-336・337・371・395、main の nav2_config.py・gouda_nav2.launch.py・生成した params、`design/research/vehicle_pc/` の 2026-10-24 の log と実行時の設定、上流のソース（下記）
- 変更：コード・設定・正本は変えていない。VM には触れていない（ssh は 2 回とも VM のアドレス:22 の時間切れ）。x86 の PC につなぐ方法は不明
- 上流のソースは Mac の一時領域に取得し、リポジトリには入れていない：navigation2 1.3.13 の obstacle_layer.cpp・RPP の parameter_handler.cpp・collision_checker.cpp、laser_geometry の rolling・humble の laser_geometry.cpp、pointcloud_to_laserscan の humble の node。**VM・x86 の PC に入っている laser_geometry の版とは未照合**

## 1. 確かめた事実

### 1.1 A案の設定では、点のない方位が消去に使われない疑い（DEC-322 と不一致）

- `scan_parameters` は pointcloud_to_laserscan の `range_max` を指定しない。既定値は double の最大値で（`design/research/upstream_jazzy/pointcloud_to_laserscan_2.0.2/node_excerpt.txt` 74 行）、float32 の `range_max` に入ると inf になる
- ObstacleLayer の `laserScanValidInfCallback` は inf を `range_max - 0.0001` に置き換える（obstacle_layer.cpp 375〜379 行）。inf のままである
- laser_geometry は `range < range_cutoff`（既定で cutoff = range_max）の点だけを残す（humble 183〜191 行。rolling も同じ形）。`inf < inf` は偽なので捨てられる
- Mac で同じ計算を実行した結果：`range_max=inf inf_replaced=inf kept=0`
- したがって、帯の中に何も当たらない方位では raytrace の点ができず、印が消えない（ひらけた場所で、人が去った跡が消えない）。推測の部分：実機では未実行。第167便の確かめは LaserScan の中身までで、costmap の消去は見ていない（同便 §5 に明記）

### 1.2 記録の読み違い：controller は「平均 10 Hz」ではない可能性が高い

- 警告は周期に遅れた回だけ出て、値は「その 1 回の処理時間の逆数」（controller_server.cpp 543〜549 行）。第157・160・163便の「平均 10 Hz」は、遅れた回だけの平均である
- run-574fe6d7：253 回、間隔の中央値 0.200 s（p10 0.197、p90 0.202）、値の中央値 10.0 Hz。run-cdde4c29：44 回、間隔の中央値 0.199 s、値の中央値 10.2 Hz
- 読み方：0.2 s ごとに 1 回、約 0.1 s かかる周期がある。残りの約 0.1 s は 20 Hz で回っているなら 2 回で、全体は 15 Hz 程度（計算。実測ではない）
- 推測：0.2 s は local costmap の update_frequency 5 Hz と一致する。RPP は costmap の mutex を取る（regulated_pure_pursuit_controller.cpp 172 行）ので、voxel layer の更新の間 controller が待っている可能性がある。未確認

### 1.3 記録の誤り：「controller が 1.6 Hz」は planner_server の行

- 第163便・第164便 B-5・第165便の「controller が 1.6 Hz」の元は `[planner_server-9] Planner loop missed ... Current loop rate is 1.5783 Hz`（1792783450.79）。controller の最低は 5.54 Hz（run-574fe6d7）
- PRM-105 の推奨値 200 ms の理由（第165便「controller が 1.6 Hz まで落ちた詰まり」）は根拠の読み直しが要る

### 1.4 経路の計画そのものは重くない（この 2 回の走行では）

- planner_server は 1 回の計画が 50 ms（expected_planner_frequency 20 Hz）を超えると警告する（planner_server.cpp 560〜568 行）。run-574fe6d7 の約 63 s で 1 回（0.63 s）、run-cdde4c29 の抜粋の範囲で 0 回
- 第164便 D-2「1 回の計画が重い」の懸念は、この 2 回については当たらない。地図が大きい場合は未確認

### 1.5 応答の遅れの見積もり（計算。上流の値を含む）

- 見える距離：obstacle_max_range 2.5 m（base_link から。鼻先 0.55 m を引くと 1.95 m）
- RPP が止める距離：衝突の検査は carrot まで（lookahead 0.6 m。collision_checker.cpp）で、足跡の前端 0.55 m を足して base_link から約 1.15 m
- 猶予（見えてから RPP が止めるまで）：(2.5 − 1.15) / 1.25 m/s = 1.08 s。1.0 m/s で 1.35 s
- 避ける経路が来るまで：点群 0.1 s ＋ global costmap 最大 1.0 s ＋ 再計画 最大 1.0 s ＋ 計画 約 0.05 s ＝ 最悪 2.15 s（平均 1.1 s 程度）
- 結論（推測）：間に合う場合と間に合わない場合が半々になる値である。間に合わないと RPP が止め、0.3 s（B-1）で FollowPath が中止され、回復に落ちる

| 案（すべて未承認） | 猶予 @1.25 m/s | 経路まで最悪 |
|---|---|---|
| 今（2.5 m、先読み 0.6 m、global 1 Hz、再計画 1 Hz） | 1.08 s | 2.15 s |
| 第165便の推奨（3.0 m、先読み最大 1.8 m、global 2 Hz、再計画 1 Hz） | 0.96 s（検査 1.25 m ＋ 0.55 m） | 1.65 s |
| 案（5.0 m、先読み最大 1.8 m、global 4 Hz、再計画 2 Hz） | 2.56 s | 0.90 s |

- 第165便の推奨は先読みを伸ばす（高速での追従と停止距離の検査に必要）ぶん猶予が減り、見える距離を伸ばさないと今より短くなる

### 1.6 走行の記録で一番長い遅れは回復（周期ではない）

- run-574fe6d7：12.1 s に collision ahead → 12.3 s に中止。その後 13〜63 s は前進なし（第163便）。周期の秒単位の遅れより 1 桁長い
- この 50 s を作るのは、0.3 s の中止（B-1）、10 s の進みの監視（B-2）、回復の順（消去 → 回転 → 5 s 待ち → 後退）、消えない印（C-1、1.1）。A-1・E-4 は 955a242 で main に入ったが実車は未実行

## 2. 現状

- main：8ee7162。第156〜167便（REV-180〜185）が入った。VM の Gouda には第165〜167便は未反映。VM は今 ssh がつながらない
- x86 の PC：人の話では 249f34c（第156〜167便の前）に pointcloud_to_laserscan を導入（未確認）。REV-185 を動かすには update.sh が要る
- A案の実車走行：未実行（人の発言）
- MID-360：人の予定 2026-11-04。main に MID-360 のコードはない（gouda_*・setup.sh・third_party で livox・MID-360 の grep 0 件）

## 3. 三つの状態

- 移行が正確：不合格のまま（input_integrity 違反、intent_identity DIFFERENT、migration_validator 違反、migration_tests 2 件失敗。いずれも intent.md の未記録の編集 AR-017 に由来すると記録されているもの。今回は由来を再確認していない）
- 設計検査：違反 0・未判定 5（合格 12）。未判定があるので「合格」ではない
- 実車投入可能：人の判断待ち。材料：設計検査は上記、停止距離などの実測は未確定（DEC-378、Q-06）、A案の実車試験は未実行
- 判断台帳：pending 80（承認 51、確認 2、実測 17、質問 10）

## 4. 実行した検査・試験

| 検査 | コマンド | 対象 | 結果 |
|---|---|---|---|
| 単体試験（Mac） | `/opt/anaconda3/bin/python3 -m unittest discover -s gouda_core/test` | main 8ee7162 の export | 305 件 OK（skip 15） |
| 設計検査 | `/opt/anaconda3/bin/python3 design/tools/run_checks.py` | 同上 | design_check 違反 0・未判定 5。generate_params PASS。input_integrity・intent_identity・migration_validator・migration_tests は FAIL |
| inf の計算 | 3 行の C++ を Mac でコンパイルして実行 | double 最大値 → float → −0.0001 → `r < range_max` | range_max=inf、kept=0 |
| log の集計 | git show した nav2 log を python で集計 | §1.2・1.4 の 2 回の走行 | 上記 |
| VM の結合試験・実車 | — | — | 未実行 |

## 5. 原因の分類（1.6）

- 1.1：実装（DEC-322 の「点のない方位は消去に使う」を、設定が満たしていない疑い）。実機で確かめる前に確定しない
- 回避が遅い全体：設定（距離・周期）＋設計（失敗の扱い）＋物理特性（車体の応答と停止距離は未測定、DEC-378）
- 1.2・1.3：記録の誤り（元の記録は書き換えず、ここで訂正を記す）

## 6. 承認の候補（DEC にはまだしていない。人の指示待ち）

1. pointcloud_to_laserscan の `range_max` を raytrace_max_range より大きい有限の値にする。推奨：入れる。代替：`use_inf: false`（点のない方位は range_max + inf_epsilon になるが、同じ判定で捨てられないよう値の確認が要る）。振る舞い：ひらけた場所で印が消える。影響：ND-09、IFD-57、PRM-125・126。決まらない場合に止まる作業：A案の実車試験の意味のある評価
2. /config の値（表 1.5 の案）。obstacle_max_range 5.0 m は、坂の地面が遠くで帯に入る誤検出が増える恐れがあるので、段階的に試す
3. controller の failure_tolerance（B-1）と進みの監視（B-2）を /config に出す。値を変えるのは 1.5 の timeout の延長にあたる恐れがあるので、承認のうえ、1 の修正の後の記録で決める
4. 試験走行で rosbag を取る（points、scan、/tf、/tf_static、local・global costmap、cmd_vel）。AI の作業は手順まで、実行は人

## 7. 残るリスク

- 1.1 は実機未実行。VM・x86 の PC の laser_geometry の版で確かめる必要がある
- 表 1.5 は計算で、車体の応答・停止距離（tbd）を含まない。見える距離を伸ばしても停止の保証にはならない
- 2026-10-24 の log は A案の前（VoxelLayer）で、rosbag がない。人が感じている遅さのうち、どこが効いているかは測っていない

## 8. 次に進められる作業／止まっている作業

- 進められる：候補 1 の実装（人の承認の後）、試験の手順の作成
- 止まっている：A案の実車試験（人、x86 の PC の update.sh。AI からの接続方法が不明）

更新した生成物：なし。
