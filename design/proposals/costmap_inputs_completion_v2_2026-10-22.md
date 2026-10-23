# costmap の入力の直し 第2版（完走優先）: XT-32 だけ、base_link の帯、距離の明示（提案、2026-10-22）

**注（第138便、2026-10-23）: 人の回答を DEC-319〜338 に記録した。人の申告（DEC-327：目の前に置かれたコーンの回避と、ランダムに置かれたコーンの区間の通過が要る。XT-32 だけでは無理）により、この版の「本番前は XT-32 だけ」「MID-360 は本番の後」（§2.5・V2-5・判断 7）は取り下げる。MID-360 を本番前に入れる第3版を作る。決まった項目：DEC-320（帯の段は rosbag で比べる）、DEC-321（local は 2 次元、一旦採用）、DEC-322（inf_is_valid true）、DEC-325（途絶を検出しない）、DEC-328（凍結 12/1、暫定）。確認待ち：DEC-324・336・337・338。**

状態: 提案（AI の作業）。実装はしていない（DEC-106）。承認事項は判断台帳に**未登録**（この文書の番号 V2-1〜V2-6・判断 1〜9 は仮の番号）。
第1版 `proposals/costmap_inputs_stvl_mid360_2026-10-22.md`（第130便）を置き換える。第1版は完走優先の方針より前に書いたもので、P-1・P-3・P-6・P-8 の向きが逆だった（第134便）。

人の指示（原文）「Rewrite the costmap proposal as v2 for completion-first: XT-32 only, base_link band (compare pcl_ros vs pointcloud_to_laserscan on rosbag), explicit ranges, no expected_update_rate, STVL/MID-360/Nebula/PTP after the final, plus the decision questions. No implementation.」

読んだもの: 作業ツリー `31a6e1d` ＋ 未コミットの変更。`design/intent.md` 第15版（SHA-256 b24fce29a261…）と、書き終えた後に読み直した版（SHA-256 23170969d338…。1 行目が「自動的にgoudaが一時停止モードに入って自律走行が出来なくなったり」に変わった。この提案の内容は変わらない）。第130便の提案、第134便の作業記録（4 つのレビュー）、`proposals/competition_no_auto_pause_2026-10-22.md`、`docs/regulations_2026.md`。上流のソース: Nav2 1.3.13、perception_pcl jazzy（2.6.5）、pointcloud_to_laserscan jazzy（2.0.2）。車両の VM・G15 での計測は一つもしていない。

## 0. 方針

- intent.md 第15版の優先の順「0. 本番で完走できる」に従い、**滞留・一時停止を増やさないこと**を第一にする。衝突そのものは失格ではない（EV-17、ただし復帰できない場合）。歩行者に衝突しそうになるのは失格（EV-18）なので、歩行者の検出は完走のための機能として残す。
- 本番（12/6）までの変更は、**設定と既製品の起動だけ**にし、自作のコードを増やさない。新しい依存（STVL、Livox の SDK）は入れない。
- 変える前に、記録した rosbag で今の構成と比べる（§3）。

## 1. 直す問題（第130便・第134便で確かめた事実）

| # | 問題 | 完走への影響 |
|---|---|---|
| K-3 | 高さの帯 PRM-70（−0.065 m）・PRM-71（1.185 m）は正本では base_link 基準なのに、Nav2 は costmap の global frame（odom・map）の z で当てている（Nav2 1.3.13 `observation_buffer.cpp` の `bufferCloud`）。odom の原点は自律走行の開始地点 | 開始地点から下ると、帯が地面から上へずれ、地上 1.35 m より上の枝・看板・庇が lethal になる → 木の下・標識の下で滞留（レビュー 1 の推測）。同時に低い物を見落とす。0.10 m 上ると地面が帯に入りうる |
| K-4 | local の VoxelLayer の柱（origin_z 0、16 段）は odom に固定 | 下ると柱から外れた点が捨てられる |
| K-2 | 2 つの costmap が生の点群全体（1.66 MB、10 Hz）を受け、全点を TF 変換してから大半を捨てる | CPU。計算の詰まりは推定不能 → 一時停止につながる（レビュー 3） |
| K-7 | `obstacle_max_range` 2.5 m・`raytrace_max_range` 3.0 m は承認なしの上流既定が暗黙に効いている | 障害物を見つける距離の根拠が台帳にない |

## 2. 本番前の構成（案）

```
XT-32 driver（公式、受信時刻のまま）──/sensors/xt32/points──┬─> GLIM（今のまま）
                                                              ├─> gouda_a3_points → NDT（今のまま）
                                                              └─> [帯の段]（新、案 X か案 Y のどちらか）
                                                                     └─> local・global の ObstacleLayer
```

### 2.1 帯の段の 2 案（§3 の比べ方で選ぶ）

| | 案 X: pcl_ros PassThrough | 案 Y: pointcloud_to_laserscan |
|---|---|---|
| 入手 | apt `ros-jazzy-pcl-ros` 2.6.5（入っている） | apt `ros-jazzy-pointcloud-to-laserscan` 2.0.2（今は入っていない。setup.sh に足す） |
| 帯の当て方（確認） | `input_frame: base_link` に変換して z で切り、`output_frame` 空で元の xt32_link に戻して出す（`filter.cpp`） | `target_frame: base_link` に変換し、`min_height`・`max_height` で切る（`pointcloud_to_laserscan_node.cpp:170,191`） |
| 出力 | PointCloud2（帯の中の全点、全 field） | LaserScan（base_link の水平面、方位の刻みごとに一番近い点だけ。`:199-232`） |
| Nav2 での扱い | 光線の起点は xt32_link（正しい） | 光線の起点は base_link の原点（xt32_link との水平のずれの分だけ違う） |
| 点のない方位 | 光線なし（消えない） | `use_inf: true` で inf。ObstacleLayer の `inf_is_valid: true` なら `raytrace_max_range` まで消す（判断 3） |
| 遅延の購読（確認） | 出力の購読者がいないと入力を外す（`filter.cpp` の matched_callback） | 同じ（`subscriptionListenerThreadLoop`、0.1 s ごとに確認） |
| component | はい | はい（`:237`） |
| 危険 | PCLPointCloud2 の経路。同じ点の並び（FLOAT64 が offset 18）で pcl_ros の **VoxelGrid** が落ちた記録がある（第119便）。PassThrough は単独で試していない | 方位ごとに一番近い点だけなので、手前の物の陰の情報は捨てる。3 次元の情報はなくなる |
| 公開の例 | — | つくばチャレンジの orne-box（MID-360 → pointcloud_to_laserscan → ObstacleLayer） |

どちらの案でも、TF が取れないときはその点群を捨ててエラーを記録する（両方のソースで確認）。xt32_link → base_link は静的 TF（ND-13）だけなので、起動の後は失敗しない見込み（推測）。

### 2.2 costmap の層

- **local**: VoxelLayer を上流の **ObstacleLayer（2 次元）** に替える（V2-2）。K-4（odom に固定した柱）がなくなる。2 次元の光線は残像をよく消す（滞留を減らす向き）。代わりに、低い物を 3 次元で覚えておく働きはなくなる（XT-32 は車体の近くの低い所をもともと見ていない: 最下のビーム −16°、取り付け 1.015 m）。
- **global**: ObstacleLayer のまま（plan C の `combination_method` 2、DEC-216 は変えない）。
- 両方とも、入力を帯の段の出力に替え、Nav2 側の `min_obstacle_height`・`max_obstacle_height` は**帯を実質無効にする広い値**にする（V2-1）。理由: Nav2 は帯を global frame の z で当てる。案 Y の LaserScan の点も、z は base_link の高さ（odom の z）になるので、下り坂で Nav2 の帯の下に出て捨てられる（`obstacle_layer.cpp` の updateBounds で z を比べる）。広い値そのものも PRM として宣言する（DR-15、RQ-I076）。

### 2.3 距離の明示（V2-3）

- 両方の層の `obstacle_max_range` を 2.5 m、`raytrace_max_range` を 3.0 m として PRM で宣言する。**今と同じ値**で、振る舞いは変わらない。根拠を台帳に置くための変更。
- 案 Y では `range_max` を `raytrace_max_range` 以上にする（導出値）。小さいと、遠い物のある方位が inf になり、消去の範囲が変わる。
- 値を変えるかは、停止距離の実測（Q-06）と §3 の比べ方を見て、別の承認事項にする。

### 2.4 途絶の検出はしない（V2-4、保護の削減）

- `expected_update_rate` は今の 0 のままにする（第1版の P-6 を取り下げる）。
- 理由（Nav2 1.3.13 で確認）: costmap が古いと controller は `costmap_update_timeout`（0.3 s）で CONTROLLER_TIMED_OUT を返す（`controller_server.cpp:528`）。このコードは BT の「回復が効く失敗」（`would_a_controller_recovery_help_condition.cpp`: UNKNOWN・PATIENCE_EXCEEDED・FAILED_TO_MAKE_PROGRESS・NO_VALID_CONTROL）に入っていないので、NavigateThroughPoses が失敗し、今の作りでは一時停止（TR-07）になる。LiDAR の途切れ 2.7〜3.5 s（第134便）がそのまま失格になる。
- 代わりに失うもの: 点群が止まっても、Nav2 は最後の costmap のまま走り続ける。その間に現れた障害物は見えない。CLAUDE.md 1.5 のとおり、途絶の検出はもともと誤値・固着を検出しない。
- 途絶は、monitor の受信の表示（IFD-56、今もある）とログで人に見せる。
- intent.md 第15版 39 行目（走行失敗を防ぐための保護の削減は、報告し、判断台帳に記録する）に従い、**保護の削減として台帳に記録する**。

### 2.5 本番の後に回すもの（V2-5）

STVL（第1版 P-1〜P-3）、MID-360 を costmap に入れること（第1版 P-8）、Nebula、PTP、地面の推定（人の C「RANSAC」、DFKI の層など）、composition・zero-copy、costmap の間引きの自作（人の回答 A）。
理由: どれも新しい依存か自作のコードで、残る実験日（11/7・11/28・11/29・12/4・12/5、公式サイト）で確かめきれない。MID-360 を印のソースにすると、床の誤検出で滞留する恐れが大きい（レビュー 1）。Nebula は受信時刻で時刻を付けられない（分岐したセッションの調査、レビュー 2 で再確認）。

## 3. 案 X と案 Y の比べ方（rosbag、車上ではない所で）

**使う記録（候補）**: x86 機の屋外の地図作成の外付けの rosbag `20261014_173522`（第104便で原図の作り直しに使った）、`20261014_175847`。生の XT-32 点群と IMU が入っているかを最初に確かめる。木の下・坂・人のいる場面があるかは未確認。足りなければ 11/7 の実験日にコースで記録する（判断 6）。

**手順（案）**
1. bag を流し、GLIM（odometry だけの設定、今の glim_runner と同じ）で odom → base_link を作る。
2. 次の 3 つの構成を、同じ bag で別々に動かす（Nav2 の costmap だけを動かす。controller は動かさない）。
   - 今: 生の点群 → VoxelLayer（local）・ObstacleLayer（global）、odom の帯
   - 案 X: pcl_ros PassThrough（base_link の帯）→ ObstacleLayer（local・global）、Nav2 の帯は広い値
   - 案 Y: pointcloud_to_laserscan（base_link の帯）→ ObstacleLayer（local・global）、Nav2 の帯は広い値。`inf_is_valid` は true と false の両方
3. 比べるもの
   - 前方の走行帯（RPP の衝突の先読み、base_link から約 1.15 m・車幅）の lethal のセルの数の時系列。誤検出（木の下・坂・地面）で走行帯がふさがった時間
   - 人・物が去った後に印が残る時間（残像）
   - コーン・細い柱・縁石など、置いた物・写っている物が lethal になるか（1〜2.5 m）
   - costmap の更新 1 回の時間（`costmap_update_timeout` 0.3 s に対する余裕）、各プロセスの CPU
   - 30 分流して落ちないこと（案 X は特に。XT-32 の点の並び）
4. 受入条件（案。値は判断を受けて決める）: 走行帯の誤検出の時間が今より短い、残像が今より短い、置いた物を今と同じかそれ以上に検出する、更新の時間に余裕がある、落ちない。
5. 両案とも条件を満たすなら、**案 Y を推奨**（PCL の経路を通らない、公開の例がある、残像に強い）。案 X は陰になった物を保つ点で優る。

この比べ方のために、bag を流して数を数える短い解析のスクリプトが要る（試験基盤。車上では動かさない）。

## 4. 承認事項（台帳に未登録。仮の番号）

| # | 質問 | 推奨 | 振る舞いの違い | 影響 |
|---|---|---|---|---|
| V2-1 | 高さの帯 PRM-70・71 を、帯の段（案 X か Y）で base_link に当て、Nav2 の帯は広い値にしてよいか | はい | 開始地点からの標高差に影響されない。一定の坂では帯が車体と一緒に傾く。坂の変わり目（前に 6° 以上傾く、谷形 12% 以上）では 2.5 m 以内に地面が入りうる（レビュー 1 の計算） | PRM-70・71、ND-09、ND-10、IFD-21、新しい IF（帯の段の出力） |
| V2-2 | local の VoxelLayer を ObstacleLayer（2 次元）に替えてよいか（DEC-122 を変える） | はい | 柱の問題がなくなる。残像が消えやすい。低い物を 3 次元で覚えない | DEC-122、ND-09、TS-37 |
| V2-3 | 距離 2.5・3.0 m を PRM として宣言してよいか（値は今と同じ） | はい | なし | ND-10、新しい PRM |
| V2-4 | `expected_update_rate` を 0 のままにし、保護の削減として記録してよいか（第1版 P-6 の取り下げ） | はい | 点群が止まっても Nav2 は止まらない | ND-10、RQ-I012 |
| V2-5 | STVL・MID-360（costmap）・Nebula・PTP・地面の推定・composition を本番の後に回してよいか | はい | なし（今のまま） | — |
| V2-6 | 人の回答の扱い: A（自作の間引き）は本番の後へ、B は取り下げ、C（RANSAC）は本番の後へ、D（lifecycle の監視）は帯の段が lifecycle でないので取り下げ、E（NDT の前処理は分けたまま）はそのまま | はい | — | 人の回答 A〜E（第130便、台帳に未登録） |

## 5. 人に決めていただきたいこと（推奨の答え付き）

1. **帯の段は案 X と案 Y のどちらにするか。** 推奨: §3 の比べ方で決める。両方が条件を満たせば案 Y。
2. **local の層を ObstacleLayer（2 次元）にするか。** 推奨: する（V2-2）。代わりは、VoxelLayer のまま柱を標高差の分だけ広げる（16 段では粗くなる）。
3. **案 Y のとき、点のない方位を消去に使うか（`inf_is_valid`）。** 推奨: true（残像が消えて滞留が減る）。代償: 反射の返らない物（黒い物・ガラス）のある方位も消える。比べ方では両方を試す。
4. **帯の上端 PRM-71（地上 1.35 m、DEC-192 で人が決めた値）を下げるか。** 推奨: 車体の一番高い所を実測し、それに余裕を足した値へ下げることを検討する（張り出し物での誤検出が減る）。決めるまでは 1.35 m のまま。
5. **`expected_update_rate` を 0 のままにし、保護の削減として記録するか。** 推奨: はい（V2-4）。
6. **比べ方に使う記録。** 推奨: まず 10/14 の外付けの bag で行い、木の下・坂・人の場面が足りなければ 11/7 にコースで記録する。
7. **MID-360 は本番前に何もしないか。** 推奨: costmap には入れない。記録だけでも driver の組み込み（setup.sh、supervisor）が要るので、本番の後にまとめて行う。本番前に床の誤検出の率を測りたい場合は、別の判断にする。
8. **costmap の変更の凍結日。** 推奨: 11/28 の実験日より前に入れて実車で確かめ、それ以降は値だけを変える。
9. **随行者の歩く位置を運用で決めるか。** 推奨: 決める（車体の後ろ〜斜め後ろ、base_link から 1 m 以上、前方 2 m に入らない、旋回中は離れる）。コードの変更なしで滞留を減らせる（レビュー 1。規則 SF-27 も随行員の距離を定めている）。

## 6. この提案の外で、関係するもの（第134便のレビューから。別の判断）

- LiDAR の LAN のリンク断（r8169、Link Down／Up）の物理的な対策と、G15 での確認（最も効く。人の作業）。
- 自動の一時停止をなくす方針（別のセッションの DEC-305〜313）。とくに CONTROLLER_TIMED_OUT と costmap の消去の直後の打ち切り（`ObstacleLayer::reset` が current を偽にする）は、BT の回復の外にある。
- 停止線・道路端での自律的な停止（EV-22）。今は未設計。
- gouda_a3_points の numpy の書き直し、monitor の実行器と SSE の間引き、rosbag の記録の topic の一覧、ドライバの printf の出し先。
- 計算資源の計測は G15 で行う（今の数値はすべて VM）。

## 7. 重大な要求・危険・前提（警告の有無にかかわらずレビューの対象）

- PC 側で障害物の前で止まるのは local costmap と RPP だけ（DEC-122、collision_monitor なし）。その入力を変える提案である。
- 点群の途絶を Nav2 は検出しない（V2-4。保護の削減）。
- local を 2 次元にすると、XT-32 の死角に入った低い物は、奥へ通る光線で消える（V2-2）。衝突しうる（衝突そのものは失格ではないが、挟まって動けなくなる恐れ）。
- 案 Y の `inf_is_valid: true` は、反射の返らない物のある方位を空きとして消す（判断 3）。
- 坂の変わり目では、base_link の帯でも地面が入りうる（V2-1）。
- 障害物を見つける距離 2.5 m は、停止距離の実測（Q-06）の前の値。
- PC 出力の中立化は車体全体の停止の保証ではない（CLAUDE.md 1.5）。

## 8. 出典

- Nav2 1.3.13: https://github.com/ros-navigation/navigation2 （`nav2_costmap_2d/src/observation_buffer.cpp`、`plugins/obstacle_layer.cpp`、`nav2_controller/src/controller_server.cpp`、`nav2_behavior_tree/plugins/condition/would_a_controller_recovery_help_condition.cpp`）
- perception_pcl jazzy（2.6.5）: https://github.com/ros-perception/perception_pcl （`pcl_ros/src/pcl_ros/filters/filter.cpp`）
- pointcloud_to_laserscan jazzy（2.0.2）: https://github.com/ros-perception/pointcloud_to_laserscan （`src/pointcloud_to_laserscan_node.cpp`）
- 規則: `design/docs/regulations_2026.md`（EV-17〜22）、日程 https://tsukubachallenge.jp/2026/about/schedule
- orne-box: https://github.com/open-rdc/orne-box
