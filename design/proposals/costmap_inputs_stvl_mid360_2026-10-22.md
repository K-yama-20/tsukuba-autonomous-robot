# costmap の入力の作り直し（段階 1）: pcl_ros の帯・切り出し＋STVL、MID-360 の追加（提案 第1版、2026-10-22）

**注（第134便、2026-10-22）: この第1版は、完走を最優先とする方針（intent.md 第15版、SHA-256 b24fce29…）より前に書いた。完走優先で見直したレビューでは、P-1（STVL）・P-3（減衰を長くする向き）・P-6（expected_update_rate）・P-8（MID-360 を costmap に入れる）の向きが逆、または本番前には入れない方がよいという結論になった（作業記録 `reports/worklog/2026-10-22_bin134_costmap_review_completion.md`）。人の判断の前に、この版を根拠に実装・登録しないこと。第2版 `proposals/costmap_inputs_completion_v2_2026-10-22.md` に置き換えた。**

状態: 提案（AI の作業）。実装はしていない（DEC-106）。承認事項・実測の項目は判断台帳に**未登録**（この文書の番号 P-1〜P-9・M-1〜M-11 は仮の番号。登録のときに reserve_ids.py で DEC を取る）。

経緯（チャット、2026-10-22）:
- 人の指示（原文）「現状のgouda内でのデータの送受信の無駄を探索せよ。リモートの最新のmainを見ること。特に点群データの扱いに無駄があるようだ」
- 人の指示（原文）「自作プログラムよりも、なるべく既存の公開されているプログラムを使ってこれらの課題を解決できないか考えたい。複数エージェントを起動して、徹底的に調べよ。」
- 人の指示（原文）「Write a proposal in design/proposals: stage 1 = pcl_ros band/crop + STVL for the local costmap, global stays ObstacleLayer; MID-360 via livox_ros_driver2; list approval items (frustum clearing, decay, D revised, A superseded) and measurement items. No implementation.」

読んだもの: リモートの main `d85a56d`（PR #18 のマージ）を書き出した写し。上流のソース（Nav2 1.3.13、spatio_temporal_voxel_layer 2.5.5、perception_pcl の jazzy ブランチ、HesaiLidar_ROS_2.0 e7e112f、glim_ros2 v1.2.2、livox_ros_driver2、Autoware Core）。Jazzy の apt 索引（packages.ros.org noble/main/binary-amd64、2026-10-06 版）。車両の VM には接続できず（SSH がタイムアウト）、**実機での計測は一つもしていない**。

## 0. この提案の前提にしている未回答・未登録の項目

| 項目 | 状態 | この提案での扱い |
|---|---|---|
| チャットでの人の回答 A「許可する。」（costmap の格子に合わせた、実点を残す間引きの自作ノード） | 台帳に未登録 | P-5 で置き換えを提案する。A は書き換えず、登録のときに原文で記録する |
| 人の回答 D「採用」（前処理ノードを lifecycle にして lifecycle_manager_navigation に監視させる） | 台帳に未登録 | P-6 で修正を提案する（pcl_ros は lifecycle ではない） |
| 人の回答 E「実行してもかまわない。」（NDT の前処理 gouda_a3_points は段階 1 では分けたまま） | 台帳に未登録 | そのまま前提にする（§2） |
| B（遠い点を光線の消去用に残す） | 人の回答なし | 段階 1 では不要になる（§3.3）。取り下げを提案する |
| 人の発言 C「地面をRANSACで推定しよう。それなら解決かな？」 | 台帳に未登録 | 段階 2 で既製品を比べる（§6）。段階 1 は base_link 基準の帯まで |
| 人の発言「MID-360は前方の足元が主に見えています。よって、xt-32でも障害物を認識しておく必要はありますが、どうでしょうか。」 | 台帳に未登録 | XT-32 と MID-360 の両方を costmap に入れる（§4） |

これらの回答が変わったら、この提案は作り直す。

## 1. 解く課題（確かめた事実）

| # | 課題 | 根拠（確認した箇所） |
|---|---|---|
| K-1 | 生の XT-32 点群（64,000 点 × 26 B = 1.66 MB、10 Hz）を、自律走行中に 4 つのプロセス（GLIM、gouda_a3_points、controller_server、planner_server）が別々に購読し、それぞれ逆シリアライズしている | `gouda_localization_a3.launch.py`、`nav2_config.py:54,104`、`mode_manager_node.py:77`。点数は `research/vehicle_pc` の記録「points:64000」 |
| K-2 | costmap は 2.5 m（印）・3.0 m（消去）までしか使わないのに、120 m までの全点を受け、点群全体を TF 変換してから捨てている。global（1 Hz）は 10 回のうち 9 回、local（5 Hz）は半分を、変換してから捨てる | Nav2 1.3.13 `observation_buffer.cpp` の `bufferCloud`・`purgeStaleObservations`。`obstacle_max_range`・`raytrace_max_range` は未設定（上流の既定 2.5・3.0） |
| K-3 | 高さの帯（PRM-70 −0.065 m・PRM-71 1.185 m、正本では base_link 基準）を、Nav2 は costmap の global frame（odom・map）の z で当てている。odom は GLIM の 3 次元の推定で、原点は自律走行の開始地点。開始地点から Δ 下ると地面から Δ＋0.10 m 以下の物が見えなくなり、0.10 m 上ると地面が障害物になる | `observation_buffer.cpp` の `bufferCloud`（変換後の z で比較）、`local_odometry_node.py`（x・y・z を合成） |
| K-4 | VoxelLayer の柱（origin_z 0、z_voxels 16）は odom に固定。柱より上の点は捨てられ、下の点は床に押し込まれる | `voxel_layer.cpp`（1.3.13）227 行付近 |
| K-5 | `expected_update_rate` が未設定（0）なので、点群が途絶えても `isCurrent()` は常に真で、Nav2 は気づかない | `observation_buffer.cpp` の `isCurrent` |
| K-6 | XT-32（取り付け高さ 1.015 m、最下のビーム −16.02°）は、車体の周り約 3.5 m の地面が見えず、近くの低い物が見えない。local costmap の窓（3 m 四方）には、高さ約 0.5 m 未満の物が XT-32 からはほぼ入らない | 取り付け高さ: model.yaml の VM の廊下の記録。−16.02°: Nebula の PandarXT32.csv（Hesai の公式マニュアルは**原本未照合**）。窓: 上流の nav2_params.yaml |

## 2. 段階 1 の構成（提案）

```
XT-32 driver ──/sensors/xt32/points (IFD-21, raw)──┬─> GLIM（今のまま）
                                                     ├─> gouda_a3_points → NDT（今のまま、人の回答 E）
                                                     └─> [pcl_ros PassThrough: 帯]（新、P-4）
                                                              │ input_frame base_link, z ∈ [PRM-70, PRM-71]
                                                              │ output_frame 空 → 元の xt32_link に戻して出す
                                                              ├─> global costmap ObstacleLayer（今のまま。帯は広げる）
                                                              └─> [pcl_ros CropBox: 距離]（新）
                                                                       │ input_frame base_link, ±R の箱の内側
                                                                       └─> local costmap STVL（新、P-1）
                                                                              XT-32: 印のソース＋錐台で消すソース
MID-360 driver（新、P-8）─/sensors/mid360/points─> [pcl_ros PassThrough: 帯]─> [CropBox: 車体の除去]
                                                                       └─> local costmap STVL: 印だけのソース（減衰で消える）
```

- 生の点群を購読するのは GLIM・gouda_a3_points・帯の PassThrough の 3 つになる（K-1）。costmap が受けるのは、帯の外（主に地面と頭上）を落とした点群（K-2）。
- pcl_ros のフィルタは、`input_frame` が空でなければその座標系に変換してから切り、`output_frame` が空なら元の座標系に戻して出す（perception_pcl jazzy ブランチ `filter.cpp` で確認）。header の frame と stamp は保たれるので、STVL・ObstacleLayer はセンサの原点を正しく取れる。
- jazzy ブランチの pcl_ros のフィルタは、出力の購読者がいないあいだは入力の購読を外す（`filter.cpp` の matched_callback で確認。jazzy ブランチの package.xml の版は apt と同じ 2.6.5。版の後に入った未リリースの変更がないかは M-1 で確かめる）。Nav2 が inactive の間（自律走行・一時停止以外）は、生の点群を受けない見込み。
- pcl_ros のフィルタはどれも component として登録されている（`RCLCPP_COMPONENTS_REGISTER_NODE`、jazzy ブランチの crop_box.cpp・passthrough.cpp で確認）。1 つの component container に載せて、フィルタどうしは intra-process でつなぐ。container は `gouda_nav2.launch.py` から起動する（gouda.sh の 1 つの起動経路のまま、DEC-090）。
- 1.8 の対応: モジュール ND-09（障害物の扱い）／内部コンポーネント「帯」「距離」「車体の除去」／ROS node は pcl_ros の PassThrough・CropBox の各インスタンス／プロセスは新しい component container（名前は登録のときに決める）。新しい topic は IF として登録する（名前は案。`sensors/xt32/points_band`、`sensors/xt32/points_near`、`sensors/mid360/points`、`sensors/mid360/points_band`）。用途区分はいずれも「データ」。安全の印を付ける。

### 2.1 local costmap

- `plugins` の `voxel_layer`（nav2_costmap_2d::VoxelLayer）を `stvl_layer`（spatio_temporal_voxel_layer/SpatioTemporalVoxelLayer）に替える。`inflation_layer` と keepout の filter はそのまま。
- STVL の層の値（案。`tbd` は M 項目で決める。どれも nav2_config.py が生成する）:

| 項目 | 値 | 根拠 |
|---|---|---|
| `voxel_size` | costmap の resolution と同じ（雛形 0.05） | 導出値 |
| `voxel_decay` | tbd（P-3、M-4） | 安全と走行のしやすさの両方に効く |
| `decay_model` | 0（線形） | 減衰の時間を秒で説明できる |
| `mark_threshold` | 0（1 つのボクセルで lethal） | 小さい物を消さない（上流の既定） |
| `track_unknown_space` | true | RQ-I012 |
| `update_footprint_enabled` | true | 車体の下の印を消す（上流の既定） |
| `combination_method` | 1（最大値） | local は今も上書きではない（VoxelLayer の既定 1 と同じ） |
| 各ソースの `filter` | `passthrough` | `voxel` は PCL VoxelGrid の重心を出す（`measurement_buffer.cpp` で確認）。実点を残すため使わない |
| 各ソースの `min_obstacle_height`・`max_obstacle_height` | 帯を実質無効にする広い値（P-4） | 帯は前段の pcl_ros が base_link で当てる。STVL の帯も global frame の z で当たる（`measurement_buffer.cpp` で確認）ので、ここで当てると K-3 が戻る |
| 各ソースの `expected_update_rate` | tbd（P-6、M-6） | K-5 |
| XT-32 の消去ソース | `marking: false`、`clearing: true`、`model_type: 1`、`vertical_fov_angle`＝XT-32 の 31°（上下対称の近似、M-10）、`horizontal_fov_angle`＝2π、`min_z`・`max_z`＝水平距離の範囲 tbd、`decay_acceleration` tbd（P-2、M-4） | 錐台で消す（§3.3） |
| XT-32 の印のソース | `marking: true`、`clearing: false` | — |
| MID-360 の印のソース | `marking: true`、`clearing: false` | STVL 2.5.5 は垂直の FOV を上下対称でしか表せず、MID-360 の −7°〜+52° を表せない（`vertical_fov_offset` は ros2 ブランチだけ、STVL #341）。対称で近似すると見ていない範囲を消すので、MID-360 では消去しない |

- `update_frequency`（今は雛形の 5 Hz）は変えない。10 Hz にするかは M-2 の CPU を見てから別に決める。

### 2.2 global costmap

- ObstacleLayer のまま（plan C の `combination_method` 2、DEC-216 を保つ。STVL には 0・1 しかない: `spatio_temporal_voxel_layer.cpp` で確認）。
- 入力を帯の出力（`points_band`）に替え、Nav2 の帯は広げる（P-4）。距離では切らない（遠い点は光線の消去に使われる: `obstacle_layer.cpp` の raytrace は `raytrace_max_range` で打ち切るだけ）。
- `obstacle_max_range`・`raytrace_max_range` を、今の暗黙の上流既定（2.5・3.0）から明示の値にする（P-7）。値を変えるかどうかは別に決める。

## 3. 承認事項（台帳に未登録。仮の番号）

各項目: 質問／推奨とその理由・代替／振る舞いの違い・影響を受ける ID／決まらない場合に止まる作業。

### P-1 local costmap の VoxelLayer を STVL に替える（DEC-122 を変える）
- 質問: local costmap の障害物の層を、上流の VoxelLayer から STVL（`ros-jazzy-spatio-temporal-voxel-layer` 2.5.5、apt、LGPL-2.1）に替えてよいか。setup.sh の apt の一覧に足す。
- 推奨: 替える。理由: OpenVDB で z の上限がない（K-4 が消える。z だけ車体に付いて動く TF を自作しなくてよい）、印が窓に縛られず減衰まで残る（K-6 の死角の記憶）、印が減衰で消えるので遠い点が要らない（K-2）。
- 代替: (a) VoxelLayer のまま、z だけ車体に付いて動く座標系を自作して local costmap の global_frame にする（TF の発行元が増える: RQ-I004）。(b) VoxelLayer のまま柱を標高差の分だけ広げる（16 段では分解能が粗い）。
- 振る舞いの違い: 印の消え方（P-2・P-3）。2D に落とすのは「列のボクセル数が mark_threshold 以上なら lethal」。
- 影響: DEC-122、ND-09、ND-10、IFD-21、`nav2_config.py`、setup.sh、TS-37（Nav2 の設定の生成と起動の可否。やり直し）。
- 既知の問題（STVL の issue）: #355「層が消える」未解決・原因不明。#362 は LaserScan のソースだけ。#324（距離による減衰）は Jazzy に入らない。
- 止まる作業: §2.1 の実装と、P-2・P-3・M-4。

### P-2 印の消し方: 光線ではなく錐台
- 質問: XT-32 の消去を、VoxelLayer の光線（点までの線上を消す）から、STVL の錐台（センサの視野の内側のボクセルの減衰を早める）に替えてよいか。
- 推奨: 替える（P-1 と一体）。
- 振る舞いの違い（安全に関わる）:
  - 錐台の内側は、**物陰になっているボクセルも**減衰が早まる。光線方式では、手前の物に遮られた奥は消えない。
  - 反射の返らない物（黒い物・ガラス）も、錐台の内側なら消える方向に働く。光線方式でも、奥の点への光線が通れば消える。
  - 錐台の外（XT-32 では最下のビーム −16° より下、つまり車体の近くの低い所）は消されず、`voxel_decay` まで残る。死角の記憶として働く。
  - 減衰の加速は 1/6·a·t³（`decay_acceleration` a）で、1 回見えなかっただけでは消えない。
- 代替: STVL を印だけにして、消去を減衰だけにする（物陰の問題はないが、立ち去った人の印が減衰まで残る）。
- 影響: ND-09、RQ-I012。止まる作業: `decay_acceleration`・`min_z`・`max_z` の決定（M-4）。

### P-3 減衰（voxel_decay）
- 質問: 印を残す時間 `voxel_decay`（線形、秒）を、M-4 の計測で決めることにしてよいか。決まるまでは `tbd` とし、実車で Nav2 を起動しない（intent.md:85 の扱いと同じ）。
- 振る舞いの違い: 長いほど死角の低い物を覚えている（後退・旋回で当たりにくい）が、立ち去った物の印が残って止まりやすい。短いほど逆。
- 影響: ND-09、DEC-193（後退は自由に使ってよい）、RQ-I012。止まる作業: 実車での Nav2 の起動。

### P-4 高さの帯を base_link で当てる場所を pcl_ros に移し、Nav2・STVL の帯は広げる
- 質問: PRM-70・71（base_link 基準と定義済み）を、pcl_ros PassThrough の `input_frame: base_link` で当て、Nav2 の ObstacleLayer と STVL の min/max_obstacle_height は実質無効の広い値にしてよいか。
- 推奨: そうする。理由: K-3 は「定義（base_link 基準）と実装（odom・map 基準）の不一致」で、原因の分類は**設計**。正本のとおりに当てる場所を直す。
- 振る舞いの違い: 開始地点からの標高差に影響されなくなる。勾配が一定の坂では、帯は車体と一緒に傾くので正しく働く。**坂の変わり目**（車体は平らで前方が上り、など）では、地面が帯に入る誤検出と、低い物の見落としが残る（段階 2 の課題）。
- 広い値そのものも設定値（PRM）として宣言する（DR-15、RQ-I076）。
- 影響: PRM-70・71、ND-09、ND-10、IFD-21、新しい IF。止まる作業: §2 の実装。

### P-5 A（自作の間引きノード）を置き換える
- 質問: 人の回答 A「許可する。」（costmap の格子に合わせ、実点を 1 つ残す間引きの自作ノード）を実装せず、STVL の `filter: passthrough`（実点のまま、voxel_min_points の影響なし）と `voxel_size`＝resolution で置き換えてよいか。A は台帳に原文で記録し、この項目が A を参照する（CLAUDE.md 1.5）。
- 推奨: 置き換える。理由: STVL が自分でボクセルにまとめるので、前段で間引く必要がない。既製品で R1（小さい物を消さない）を満たす。
- 振る舞いの違い: なし（目的は同じ）。点数は前段で減らさないので、STVL の CPU は M-2 で確かめる。
- 影響: A、ND-09。

### P-6 D（lifecycle_manager による監視）を、データの途絶の検出に修正する
- 質問: 人の回答 D「採用」は前処理ノードを lifecycle にする前提だった。pcl_ros のフィルタは普通の `rclcpp::Node` で lifecycle ではない（確認）。lifecycle_manager の bond の代わりに、STVL・ObstacleLayer の全ソースに `expected_update_rate` を設定し、途絶で costmap を「古い」にする方法に修正してよいか。
- 推奨: 修正する。controller_server は costmap が古いあいだ待ち、`costmap_update_timeout`（上流の既定 0.3 s）を過ぎると ControllerTimedOut にする（`controller_server.cpp` 527 行で確認）。プロセスが落ちても、TF が取れずに点群が出なくなっても、同じ経路で止まる。
- **残る穴**（今の構成にもある）:
  - 判定は受信した時刻で行い、header.stamp は見ない。古い stamp の点群が届き続ける故障は検出できない。
  - behavior_server の後退・旋回は costmap の鮮度を見ない（調査の報告。確かめるのは M-6）。センサが止まっていても、最後の costmap のまま後退・旋回が動く。
  - 途絶の検出は「一定時間の未受信」だけで、誤値・固着・意図しない発行は検出できない（CLAUDE.md 1.5）。
- 代替: (a) 穴を残すリスクとして記録して進む（推奨）。(b) stamp の古さと後退・旋回の前の鮮度を見る小さな自作の見張りを足す（別の提案にする）。(c) collision_monitor は base_link 基準の高さ・stamp による途絶・後退の監視を持つが、意図の「PC 側に非常停止機構を設けない」（RQ-I072、C-017）に反するので勧めない。
- 影響: D、ND-09、ND-10、TR-07（一時停止）、PRM（新: 各ソースの expected_update_rate）。

### P-7 costmap の距離の値を明示する
- 質問: 今は暗黙の上流既定の `obstacle_max_range` 2.5 m・`raytrace_max_range` 3.0 m（global）と、STVL の `obstacle_range`・錐台の `max_z`、CropBox の箱の大きさ R を、PRM として宣言してよいか。
- 理由: 障害物を見つける距離は、最高速度 1.25 m/s（PRM-66）での停止に関わる。今は承認なしの上流既定が効いている（1.4 の重大な前提）。
- 値: 今の 2.5・3.0 を当面の値とし、変えるかは停止距離の実測（Q-06）と別に決める。

### P-8 MID-360 を livox_ros_driver2 で加える
- 質問: Livox MID-360 を、livox_ros_driver2（MIT、v1.2.8、Jazzy 対応は v1.2.6 から）と Livox-SDK2（MIT）の固定版のソースビルドで加え、sensor_supervisor（ND-18）が XT-32 と同じく機器の有無を見て起動する形にしてよいか。
- 推奨の設定（案）:
  - `xfer_format: 0`（PointCloud2。x・y・z・intensity FLOAT32、tag・line UINT8、timestamp FLOAT64、point_step 26）。frame_id は `mid360_link`（IMU の frame_id は driver の中で "livox_frame" に固定。IMU は使わない）。
  - 時刻同期はまず「なし」（PC の受信時刻）。同期モードには、フレームが数秒出ない／小さなフレームが続く未解決の不具合がある（livox_ros_driver2 #261・#254、修正の PR #264 は未マージ）。
  - 外部の較正は small_gicp（`ros-jazzy-small-gicp-vendor`、apt、MIT）で、止まった状態でためた 2 つの点群を合わせる短いスクリプト（車上では動かさない道具）。代替は tier4 の mapping_based_calibrator（GPL-3、Autoware の一部が要る）。結果は /config の取り付けの値に入れ、静的 TF は ND-13 が出す（TF の発行元は 1 つのまま）。
  - 車体の点は pcl_ros CropBox（base_link の箱、`negative: true`）で除く。原点 (0,0,0) の点が出る報告がある（#88）ので、それも除く。
  - GLIM は XT-32 のまま（購読できる点群は 1 本。床を向いた MID-360 は構造物が少ない）。
- 残る自作のつなぎ: setup.sh・drivers.repos での `build.sh` の再現（package.xml の選び方、ROS_EDITION、SDK2 の入れ先）、ネットワーク（MID-360 の既定は 192.168.1.1XX、ホスト 192.168.1.50。XT-32 と同じ帯になるかの整理）、較正のスクリプト。
- 影響: ND-14（XT-32）と並ぶ新しい ND、ND-18、ND-13、/config、setup.sh、drivers.repos、新しい IF。止まる作業: §2 の MID-360 の部分。

### P-9 B を取り下げ、地面の推定を段階 2 に回す
- B（遠い点を消去用に残す）: local は錐台で消すので遠い点が要らない。global は距離で切らないので、今のまま光線に使われる。どちらでも B の処理は不要。取り下げを提案する（B は人の回答がないまま）。
- 人の発言 C（RANSAC）: 段階 1 は base_link 基準の帯まで。地面の推定は §6 の比べ方で選ぶ。

## 4. XT-32 と MID-360 の役割（段階 1）

| 範囲 | XT-32 | MID-360 |
|---|---|---|
| 前方の足元（近く・低い） | 見えない（K-6） | 主に見る（人の申告） |
| 横・後ろ・中くらいの距離・背の高い物 | 見る | 見えない（取り付け次第、M-7） |
| 横・後ろの近くて低い物 | 見えない | 見えない |

- 横・後ろの近くて低い物は、どちらからも見えない。段階 1 では、遠くで見えた物を STVL の減衰の時間だけ覚えていることで補う（P-3）。それで足りるかは M-4 で確かめる。足りなければ、後退の制限（DEC-193 を変える）か、後ろのセンサを別に提案する。

## 5. 実測・確認の項目（台帳に未登録。仮の番号）

| # | 項目 | 計測の方法（案） | 決めるもの |
|---|---|---|---|
| M-1 | pcl_ros の PassThrough・CropBox が XT-32 の点の並び（FLOAT64 が offset 18）で落ちず、正しく切るか。apt 2.6.5 が jazzy ブランチと同じく購読者がいないときに入力を外すか | 記録した rosbag を流して 30 分、出力を Python で照合（帯・箱の外の点が 0、内の点が全部残る）。`ros2 topic info` で購読の有無 | P-4 の採否 |
| M-2 | CPU と遅れ（GLIM、gouda_a3_points、container、controller_server、planner_server） | 今の構成と段階 1 を、同じ rosbag で `top`・`ros2 topic delay` で比べる | P-1 の採否、local の update_frequency |
| M-3 | 小さい物が消えないか（細い柱、10 cm の縁石、コーン、1〜3 m） | 同じ rosbag で今の VoxelLayer と STVL の lethal のセルを比べる。実車でも置いて確かめる | P-1・P-5 |
| M-4 | `voxel_decay`・`decay_acceleration`・錐台の `min_z`/`max_z` | 横・後ろの低い箱を通り過ぎてから後退・旋回する。人が立ってから立ち去る。印が残る時間と消える時間を記録 | P-2・P-3 |
| M-5 | 坂での帯（誤検出と見落とし） | 坂と坂の変わり目のある所で記録。地面が lethal になった所、低い物が消えた所を数える | 段階 2 の要否 |
| M-6 | `expected_update_rate` の値と停止の確認 | XT-32・MID-360 の到着間隔の分布を測る。driver を止めて controller が止まるまでの時間を測る。後退・旋回中に止めたときの振る舞いを確かめる | P-6 |
| M-7 | MID-360 の取り付けの姿勢と見える範囲、ためる時間による覆い方（0.1・0.5 s）、車体の点、原点の点 | 取り付けた後、平らな床で記録 | P-8、§4 |
| M-8 | MID-360 の受信時刻と点の実際の時刻のずれ | 回転しながら記録し、XT-32 と同じ物の位置のずれを見る | P-8（同期なしで足りるか） |
| M-9 | XT-32 と MID-360 の外部の較正の精度 | small_gicp の残差、同じ壁の位置のずれ | P-8 |
| M-10 | XT-32 の取り付け高さと最下のビームの角度（実車） | 実車で測る。Hesai の公式マニュアルと照合（今は原本未照合） | K-6、錐台の角度 |
| M-11 | XT-32 の反射のない点の表し方（0,0,0 か NaN か） | 生の点群を空に向けて記録 | 原点の除去の要否 |

## 6. 段階 2: 地面の推定（既製品の比べ方）

DEC-108 の必須の要件（人の原文）をすべて満たす既製品はなかった（調査の結論）。候補を記録した rosbag で比べてから選ぶ。

| 候補 | 入手 | 長所 | 短所 |
|---|---|---|---|
| GSeg3D ＋ DFKI `nav2_ground_consistency_costmap_plugin`（BSD-3） | ソースビルド。Nav2 公式の Jazzy 向けチュートリアルがある | 同じ座標系の中で地面との差を取るので、標高差と坂の変わり目に対処できる | 途絶を検出しない、初期値では約 4 点ないと lethal にしない、窓の外を覚えない |
| linefit_ground_segmentation の ROS 2 移植版（BSD） | ソースビルド | センサ高が固定、地面より下の点を消さない | 原作者の版は ROS 1。移植版の保守は個人 |
| autoware_ground_filter（Apache-2.0） | apt 1.9.0 | apt で入る | 点の並び PointXYZIRC が必要（driver を Nebula に替えるか変換）、地面より下の点は消える、診断出力なし |

足りないもの（どれも持っていない）: センサ高を設計値の周りに制約した補正、失敗したときの代わりの処理と記録、地面より下の点を負の障害物候補として残すこと。

## 7. 進め方（案）

1. 台帳への登録（P-1〜P-9、M-1〜M-11、人の回答 A・C・D・E の原文）。
2. M-1・M-2・M-3 を、記録した rosbag で車上ではない所で行う（VM。実車の走行なし）。
3. 承認を得てから段階 1 の XT-32 の部分を実装（nav2_config.py の生成、launch、setup.sh）。TS-37 をやり直す。
4. MID-360 の部分（P-8）。
5. 段階 2 の比べ方。

## 8. 重大な要求・危険・前提（警告の有無にかかわらずレビューの対象）

- collision_monitor を使わないので、PC 側で障害物の前で止めるのは local costmap と RPP だけ（DEC-122）。その入力の作り方を変える提案である。
- 錐台による消去は、物陰の印も消す方向に働く（P-2）。
- 途絶の検出は「一定時間の未受信」だけ。後退・旋回は鮮度を見ない（P-6）。
- 障害物を見つける距離 2.5 m は承認なしの上流既定（P-7）。
- 坂の変わり目の誤検出・見落としは段階 1 では残る（P-4）。
- 横・後ろの近くて低い物は、どちらのセンサからも見えない（§4）。
- PC 出力の中立化は車体全体の停止の保証ではない（CLAUDE.md 1.5）。

## 9. 出典（調査で読んだもの）

- Jazzy の apt 索引: http://packages.ros.org/ros2/ubuntu/dists/noble/main/binary-amd64/Packages.gz（2026-10-06 版）
- Nav2 1.3.13: https://github.com/ros-navigation/navigation2 （`nav2_costmap_2d/src/observation_buffer.cpp`、`plugins/obstacle_layer.cpp`、`plugins/voxel_layer.cpp`、`nav2_controller/src/controller_server.cpp`）
- spatio_temporal_voxel_layer 2.5.5: https://github.com/SteveMacenski/spatio_temporal_voxel_layer （`measurement_buffer.cpp`、`spatio_temporal_voxel_layer.cpp`、README）
- perception_pcl（jazzy ブランチ）: https://github.com/ros-perception/perception_pcl （`pcl_ros/src/pcl_ros/filters/filter.cpp`）
- livox_ros_driver2: https://github.com/Livox-SDK/livox_ros_driver2 、MID-360 の仕様: https://www.livoxtech.com/mid-360/specs
- small_gicp: https://github.com/koide3/small_gicp
- Nebula（XT-32 のチャンネル角）: https://github.com/tier4/nebula
- GSeg3D・DFKI の plugin: https://github.com/dfki-ric/ground_segmentation_ros2 、https://github.com/dfki-ric/nav2_ground_consistency_costmap_plugin
- つくばチャレンジの公開例（MID-360 → pointcloud_to_laserscan → ObstacleLayer）: https://github.com/open-rdc/orne-box

調査の各報告（AI の調査エージェントの出力）は、この提案の作業記録に要点を書いた。生の報告と取得したソースは、作業用の一時領域にあり、リポジトリには入れていない。
