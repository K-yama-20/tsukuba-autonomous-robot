# 第165便 作業記録：A-1・E-4 の実装と、/config で変えられる Nav2 の値（REV-183、DEC-393、PRM-105〜129）

- 日付：2026-10-24
- 読んだコミット：1d7ee4663687a69ba101121964757405ff16cc00（作業ツリーに未コミットの変更あり：REV-180〜182 ほか）
- 読んだもの：第164便の列挙、nav2_config・mode_manager_node・autonomy_client・monitor_node・monitor_core・web/app.js、Nav2 1.3.13 の上流のソース（RPP の parameter_handler、costmap の obstacle_layer・voxel_layer・costmap_2d_ros・observation_buffer）
- 人の回答（原文、DEC-393）：
  ```
  A1, E4: 採用
  E1,2,3; 検討

  A2,4,5,B3,4,C2,3,4,6D1,4: /configで設定できるようにする。推奨値も考えて
  ```

## 1. 解釈（自律判断。DEC-393 の note にも記録）

- 「採用」＝実装の承認。「検討」＝提案を作る（実装しない）。「/configで設定できるようにする」＝monitor の /config「Nav2」タブの項目にする
- 値は今の振る舞いのまま（PRM は未確定。値がない間は Gouda は書かず、Nav2 1.3.13 の値がそのまま効く）。推奨値は案として示し、承認を待つ
  - 記載値（source_value）にしなかった理由：上流の既定値を出典として正本に登録する手段がない（出典は Excel・drawio・intent だけ。DR-11 が出典の原文に値を探す）。変更セットの試しで 14 件の DR-11 違反が出たので、未確定にした
- B-3（RPP は障害物を避けない）：RPP の衝突の検査の 2 つの値を変えられるようにすることと解釈した。controller の種類の変更（避ける controller にする）は含めない
- D-1（再計画の頻度）：PRM-103 で既に変えられるので変更なし
- D-4：cost_scaling_factor（PRM-129）と、膨らませの半径（承認済みの PRM-72 を /config で上書き）
- B-1（controller の失敗の許容 0.3 s）・B-2（進みの監視 0.5 m／10 s）は回答に含まれていないので変えていない

## 2. 変更

### 2.1 A-1（承認：DEC-393）

- `nav2_config.build_bt`：BT の外側の RecoveryNode（NavigateRecovery）の回復の前にある Fallback（WouldAControllerRecoveryHelp・WouldAPlannerRecoveryHelp）を除いた。error_code のない失敗（受け付けの時間切れなど。run-574fe6d7 の終わり）でも、回復（costmap の消去・旋回・待ち・後退）を試してから続ける
- 上流の BT の形が違えば、作らずに止める（ValueError）
- 残るリスク：回復できない失敗でも、PRM-18（9999999 回）まで回復を繰り返す。人は一時停止・終了できる

### 2.2 E-4（承認：DEC-393）

- 一時停止の理由を Nav2 の error_code で分ける。表は nav2_msgs の action の定数から作る（数字をコードに書かない。`autonomy_client.error_code_table`）
  - ComputePath*（TF_ERROR 以外）→ `plan_failure`
  - FollowPath の PATIENCE_EXCEEDED・FAILED_TO_MAKE_PROGRESS・NO_VALID_CONTROL → `blocked`
  - FollowPath のその他 → `controller_failure`
  - TF_ERROR（FollowPath・ComputePath*）→ `nav2_tf_error`
  - error_code 0 → `nav2_no_error_code`、表にない code → `nav2_unclassified`
- 記録（automatic_pause の decision）に error_code の名前（例 `FollowPath.TF_ERROR`）を足した
- 正本：TR-07 の actions の停止原因区分を書き直した

### 2.3 /config で変えられる値（承認：DEC-393）

| 項目 | キー | PRM | 今の値（Nav2 1.3.13） | 推奨値（未承認） |
|---|---|---|---|---|
| A-2 | bt_default_server_timeout_ms | PRM-105 | 20 ms | 200 |
| A-4 | recovery_spin_enabled | PRM-106 | true | false |
| A-4 | recovery_spin_dist_rad | PRM-107 | 1.57 | 1.57 |
| A-4 | recovery_wait_s | PRM-108 | 5.0 | 5.0 |
| A-4 | recovery_backup_enabled | PRM-109 | true | true |
| A-4 | recovery_backup_dist_m | PRM-110 | 0.30 | 0.30 |
| A-4 | recovery_backup_speed_mps | PRM-111 | 0.15 | 0.15 |
| A-5 | replan_recovery_retries | PRM-112 | 1 | 2 |
| A-5 | follow_path_recovery_retries | PRM-113 | 1 | 2 |
| B-3 | rpp_use_collision_detection | PRM-114 | true | true |
| B-3 | rpp_max_time_to_collision_s | PRM-115 | 1.0 | 1.0 |
| B-4 | rpp_lookahead_dist_m | PRM-116 | 0.6 | 0.6 |
| B-4 | rpp_min_lookahead_dist_m | PRM-117 | 0.3 | 0.5 |
| B-4 | rpp_max_lookahead_dist_m | PRM-118 | 0.9 | 1.8 |
| B-4 | rpp_lookahead_time_s | PRM-119 | 1.5 | 1.5 |
| B-4 | rpp_use_velocity_scaled_lookahead_dist | PRM-120 | false | true |
| B-4 | rpp_use_regulated_linear_velocity_scaling | PRM-121 | true | true |
| B-4 | rpp_use_cost_regulated_linear_velocity_scaling | PRM-122 | true | true |
| B-4 | rpp_regulated_linear_scaling_min_speed_mps | PRM-123 | 0.25 | 0.25 |
| C-2 | local_costmap_size_m | PRM-124 | 3 | 6 |
| C-3 | obstacle_max_range_m | PRM-125 | 2.5 | 3.0 |
| C-3 | raytrace_max_range_m | PRM-126 | 3.0 | 4.0 |
| C-4 | voxel_mark_threshold | PRM-127 | 0 | 0 |
| C-6 | global_costmap_update_hz | PRM-128 | 1.0 | 2.0 |
| D-4 | inflation_cost_scaling_factor | PRM-129 | 3.0 | 3.0 |
| D-4 | inflation_radius_m | PRM-72（上書き） | 1.0（承認済み） | 1.0 |

- 推奨値の理由は各 PRM の interpretation（正本）にある。主なもの：spin は人のそばで回らないため false、timeout 200 ms は controller が 1.6 Hz まで落ちた詰まりに耐えるため、local costmap 6 m・印を付ける 3 m・消す 4 m は 1.25 m/s で約 2.4 s 先まで見て窓の端の古い印も消すため、先読みは速度で伸ばす（0.5〜1.8 m）。mark_threshold は C-1（高さの帯）を直すまで低い物を見落とす方向に変えない
- 今の値の出典：`design/research/vehicle_pc/2026-10-24_nav2_runtime_config/upstream_defaults_1.3.13.txt`（上流 1.3.13 のソースの行。VM の版は 1.3.13-1noble）
- 仕組み：`nav2_config.TUNABLES`。/config に正しい値があればそれ、なければ PRM の値、PRM も未確定なら書かない。`overrides.json` にどこから来た値かを記録。monitor の Nav2 タブに入力欄と「PRM の値／次の起動／今の起動」の表を足した。新しい欄の型：positive_int（1 以上の整数）・whole（0 以上の整数）

### 2.4 E-1〜E-3（検討）

- 提案 `design/proposals/failure_handling_E1-E3_2026-10-24.md`（提案。実装しない）

### 2.5 試験

- `test_nav2_config.py`：test_bt を A-1 に合わせた（承認された仕様の変更による期待値の変更。除いた Fallback 以外は上流と同じことを確かめる）。TunableTests 4 件（未保存なら何も変わらない、保存した値が書かれる、正しくない値は書かれない、型の判定）
- `test_nav2_error_codes.py`（新規）：規則 2 件、本物の nav2_msgs の定数の表 1 件（VM だけ）
- `test_monitor_core.py`：新しい欄の型の試験 1 件

## 3. 実行した検査・試験

| 検査 | コマンド | 対象 | 結果 |
|---|---|---|---|
| 変更セットの試し | `apply_revision.py REV-183 --dry-run --check` | 作業ツリー | 1 回目（記載値）：新しい違反 14（DR-11）。未確定に直して：新しい違反 0・新しい未判定 25（DR-11 の値未確定、PRM-105〜129） |
| 適用・再生成 | `apply_revision.py REV-183`、render_views・generate_params・render_migration_review | 同上 | いずれも 0 |
| 設計検査 | `run_checks.py` | 同上 | 終了コード 1。design_check「違反0件・未判定5件」（規則の数は前と同じ。DR-11 の未判定の項目は 30 → 55）。intent 由来の既存の FAIL はそのまま |
| 単体試験（Mac） | `/opt/anaconda3/bin/python3 -m unittest discover -s gouda_core/test` | 同上 | 305 件 OK（skip 15） |
| 単体試験（VM） | `~/gouda_unit_tree_bin165`、ROS_DOMAIN_ID 95、discover | 同上 | OK（全件）。test_nav2_error_codes の 3 件、test_tr05_start_order の 3 件を -v で確認 |
| 結合試験（VM、模擬） | `~/gouda_ws165` に build（symlink）して `ubuntu_stage5-6.sh`（ROS_DOMAIN_ID 77、loopback simulator、ESP32 の模擬、実機なし） | 同上 | exit 0。T1〜T6 とも前と同じ振る舞い（T2 で最後の waypoint まで走り goal_reached、T4 の一時停止・再開・終了、T5・T6 の推定不能）。A-1 の BT で Nav2 が起動し goal を受け付けた |
| 結合試験（推奨値を /config に保存） | 試験の写し（`~/claude_scratch/st56_recommended.sh`）に nav2_recovery.json を書く 1 行を足して同じ試験 | 同上 | exit 0。T1〜T6 とも同じ振る舞い。§6 |
| 実車 | — | — | 未実行（VM の Gouda に反映していない） |

## 4. 原因の分類（1.6）

- A-1：設計（BT の回復の条件）。E-4：実装（停止原因の分類の誤り）。/config の項目：設定（値を変えられる場所の追加。値そのものは変えていない）

## 5. 残るリスク

- A-1 で、回復できない失敗でも回復を繰り返す（止まらない代わりに、同じ所で回り続けうる）
- 推奨値は計算と記録からの案で、実車で試していない
- local costmap を 6 m、global の更新を 2 Hz にすると CPU が増える（VM の詰まりの元になりうる）
- B-1・B-2 は未対応。進みの監視（0.5 m／10 s）と controller の失敗の許容（0.3 s）は今のまま

## 6. 推奨値での結合試験

- 保存した値：timeout 200、spin false、内側のやり直し 2・2、RPP の先読み 0.5〜1.8 m（速度で伸ばす）、local costmap 6 m、印を付ける 3.0 m・消す 4.0 m、global 2 Hz
- 生成された Nav2 の設定で確かめた：default_server_timeout 200、local 6×6、obstacle_max_range 3.0・raytrace_max_range 4.0、global update_frequency 2.0、FollowPath の min／max_lookahead_dist 0.5／1.8・use_velocity_scaled_lookahead_dist true、BT に Spin なし、内側の RecoveryNode 2・2、外側 9999999
- Nav2 はこの設定で起動し、模擬の車体は最後の waypoint まで走った（T2 goal_reached）
- 記録：`design/research/vehicle_pc/2026-10-24_nav2_tunables_sim/`（今の値と推奨値の 2 回の log）
- 試していないこと：E-4 の各停止理由（模擬では Nav2 が失敗しない）、A-1 で時間切れの後に回復すること（時間切れを起こせていない）、実車
