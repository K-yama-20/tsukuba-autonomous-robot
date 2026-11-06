# 作業記録 2026-11-07 第219便: Nav2 の失敗で待機に入らず goal を出し直す（REV-245、DEC-460、PRM-161）

## 読んだもの

- コミット `9c449b5`（ブランチ design/mppi-sim-2026-11-03）＋作業ツリー（他のセッションの未コミットの変更を含む）。
- `CLAUDE.md`（1.1〜1.12）、`design/reports/status.md` の冒頭、`design/model.yaml` の DEC-437・DEC-438・TR-07・PRM-136・RQ-I104、`design/revisions/REV-210.yaml`・`REV-240.yaml`、第215便の作業記録。
- コード：`gouda_core/gouda_core/mode_manager_node.py`（クラス全体）、`autonomy_client.py`（new_token・send_goal・skip_to・_result・cancel）、`autonomy_core.py`（nav2_failure_reason・localization_wait_action）。
- 車載 PC には触れていない。gouda.sh はどこでも起動していない。

## 1. 人の回答（原文）

- 「Nav2 の失敗で待機に入らず goal を出し直す変更を実装してよい。opus5.5のサブエージェントを新規で立てて実装させよ」（DEC-460）
- 「opus5.5」は Opus 5.5 と読んだ。実装は新しく立てた Opus 5.5 のサブエージェントが行った。
- 前の決定：DEC-437（Nav2 が失敗しても待機に入らない）。回復の構成は DEC-438（未決）のまま。この便では閉じていない。

## 2. 変更

- 正本（REV-245）：DEC-460（approval、answered）、PRM-161 `nav2_failure_resend_wait_s`（gouda_mode_manager、2.0 s、approved）。TR-07・ND-03 に追記。
  - 2.0 s は AI の推奨値。人は値を述べず（「値はあなたが決めてください」）、提案の承認で暗に認めただけ。実測の裏付けはない（DEC-460 の note と PRM-161 の measurement に記載）。
- `gouda_core/gouda_core/autonomy_core.py`：`nav2_failure_action`（値があり自律走行なら re-send、なければ今までの pause）、`nav2_resend_due`（待つ間に何も起きていないか）。モジュールの docstring に 1 項目。
- `gouda_core/gouda_core/mode_manager_node.py`
  - パラメータの宣言と読み込み（`optional_double(self, 'nav2_failure_resend_wait_s')`。値は書いていない：DR-15）。
  - `_on_nav_result` の最後の分岐：PRM-161 に値があり自律走行なら `_schedule_resend`、それ以外は今までの `_auto_pause('TR-07', ...)`。
  - 新しいメソッド `_schedule_resend`・`_start_resend_timer`・`_resend_fire`・`_resend_goal`。
  - モジュールの docstring の TR-07 の記述に 3 行。
- `gouda_core/test/test_autonomy_core.py`：`test_nav2_failure_action`・`test_nav2_resend_due`（Mac でも走る）。
- `gouda_core/test/test_nav2_failure_resend.py`（新規、12 件。rclpy・action_msgs がある所だけで走る。Mac では skip）。
- 生成物：`design/generated/params/gouda_mode_manager.yaml` に `nav2_failure_resend_wait_s: 2.0  # PRM-161`。ほかに generate_params.py・render_views.py・render_migration_review.py の出力。

### 今の動き

- Nav2 の goal が失敗（SUCCEEDED・CANCELED 以外）で終わり、PRM-161 に値があり、モードが自律走行で、localization_wait でないとき：
  1. 待機に入らない。自律走行のまま、motion_hold=true（drive_released=false）、goal_active=false。新しい token を取る。
  2. 記録 `nav2_goal_resend_scheduled`（TR-07）：理由（E-4 の error_code の区分 `failure_reason`、error_code、名前、error_msg）、出し直しの回数（その run の通し番号、上限なし）、待つ時間、next_offset。log にも warning で出す。
  3. PRM-161 の後（threading.Timer。executor でも lock を持ったままでもない）、lock の中で token・モード・localization_wait・goal_active を確かめ、何も起きていなければ `min(next_offset, 最後)` から send_goal。記録 `nav2_goal_resend`。speed_limit_application_state を unknown にし、新しい goal の 適用中 で hold を解く（localization_wait の再送と同じ、DEC-056）。
  4. 待つ間に人の一時停止・終了、新しい開始、localization_wait が起きたとき（どれも token を変える）は出し直さない。記録 `nav2_goal_resend_dropped`。
- 出し直しが失敗したとき（action server がない、goal の拒否：StepFailed）：待機に入らず、同じ PRM-161 の後にまた出し直す（回数を 1 増やして同じ記録）。Abandoned（人の操作が先）のときは何もしない。
- PRM-161 に値がないとき：今までどおり TR-07 で待機（stop_reason は E-4 の区分）。
- 変えていないもの：TR-08（最後の waypoint）、人の一時停止・終了、取り消された goal、localization_wait の間の失敗（`nav2_goal_ended` のみ）、推定不能（DEC-419・423）、開始の手順の失敗（TR-05 の `_run_steps` は今までどおり TR-07）、localization_wait の終わりの再送、waypoint を飛ばす処理。

## 3. 自律判断

- 出し直しが拒否・失敗したときは、同じ時間の後にまた出し直す。理由：承認の意図「Nav2 の失敗で待機に入らない」。_run_steps を使うと StepFailed で TR-07 に入るので、出し直しだけは別のメソッド（`_resend_goal`）にした。大きな作り直しは要らなかった。
- 待つ間は motion_hold=true にした。理由：再利用を承認された localization_wait の経路と同じ。今の動き（失敗で待機＝hold）から hold を外すことにならない。
- 取り消しの判定は、localization_wait と同じ token（`auto.new_token()`）で行う。予定を取った時点で token を新しくするので、その後の new_token（TR-06・10・11・12・05、localization_wait）はすべて出し直しを止める。
- 出し直しの回数は記録用で、run_id ごとに数え直す（TR-05 は変えていない）。
- processing_state に新しい値（例：出し直しの待ち）は足していない。mode/state の外から見た値が増えるため（承認の範囲外）。待つ間の monitor の表示は decision の記録だけ。
- 要求の参照は RQ-I104（intent.md:19、生きている）と RQ-I076（値をコードに書かない）。REV-240 と PRM-136 と同じ形。

## 4. 原因の分類（1.6）

- 仕様の変更（DEC-437・DEC-460）による実装の変更。不具合の修正ではない。
- 試験の期待値：変えた期待値はない。「Nav2 の失敗で待機」を確かめていた既存の単体試験は見つからなかった（`test_autonomy_core.py` 168 行は `mode_core.automatic_pause` 自体の試験で、関数は変えていない）。`ubuntu_stage5-6.sh` の T2 は「stop_reason が plan_failure なら再開する」という条件付きの手順で、失敗で待機することを assert していない（PRM-161 があると、その分岐に入らなくなるだけ）。T1〜T6 は実行していない。

## 5. 先行事例（1.11）

| 探した場所 | 見たもの | 採否と理由 |
|---|---|---|
| KUAMS（`design/research/kuams_tc2025_2026-10-23/kuams_comparison.md` 140 行・179 行、`kuams_summary.md` 26〜31 行） | ABORTED のとき同じ waypoint を上限なく送り直す。waypoint を 1 つずつ送る | 採用（上限なしの送り直し）。gouda は全 waypoint を一括で送るので、next_offset からの残り全部を送り直す形にした |
| `design/proposals/competition_no_auto_pause_2026-10-22.md` 98〜102 行（DEC-307 の案） | 一時停止せず、現在地から残りの waypoint へ出し直し続ける。上限なし。同じ場所の繰り返しは DEC-310 と組にする | 同じ考え。DEC-307・310 は pending のまま |
| 上流 nav2_simple_commander 1.3.13（模擬の機械に入っている版。`demo_security.py`・`example_nav_through_poses.py`・`robot_navigator.py`） | `robot_navigator.py` に retry・resend の処理はない。`demo_security.py` は TaskResult.FAILED のとき経路を最初から（反対側から）送り直すループ | 送り直しは使う側で書く、という点の確認。流用できる部品はない |
| 上流 nav2_waypoint_follower 1.3.13 | `stop_on_failure`（nav2_bringup の既定 false）：FollowWaypoints で失敗した waypoint を飛ばして次へ進む | 不採用。waypoint を飛ばすのは DEC-367 の範囲で、承認の範囲外。NavigateThroughPoses には同じ設定はない（ヘッダーの宣言のみ確認、ソースは読んでいない） |
| Nav2 の BT（PRM-18 の number_of_retries） | BT の中の回復は今の設定のまま | 変えていない |
| 上流の issue、他のチーム（KUAMS 以外）、論文 | — | 未調査 |

## 6. 検査・試験

| 検査 | コマンド | 対象 | 結果 |
|---|---|---|---|
| 単体試験（Mac、変更前） | `PYTHONPATH=gouda_core python3 -m unittest discover -s gouda_core/test` | 9c449b5＋作業ツリー（変更前） | 386 件 OK（skip 15） |
| 単体試験（Mac、変更後） | 同上 | 9c449b5＋作業ツリー（変更後） | 400 件 OK（skip 27。増えた 14 件のうち 12 件は rclpy がないため skip） |
| 変更セットの試し | `design/.venv/bin/python design/tools/apply_revision.py REV-245 --dry-run --check`（2 回、適用の直前にも） | 同上 | 0 new violations, 0 new undetermined |
| 本適用 | `apply_revision.py REV-245` → `generate_params.py` → `render_views.py` → `render_migration_review.py` | 同上 | 本適用は 02:19 ごろ（model.yaml の更新時刻 02:19:03）。生成は 02:19:19 まで |
| 設計検査 | `design/.venv/bin/python design/tools/run_checks.py` | 同上 | 終了コード 1（02:20:55 に終了）。design_check PASS：合格 12・違反 0・未判定 5。既存の不合格：input_integrity（SystemArchitecture.drawio・.DS_Store）、migration_validator、migration_tests 88 件中 1 件（test_real_model） |
| 単体試験（模擬の機械、ROS 2 Jazzy） | `PYTHONPATH=gouda_core python3 -m unittest discover -s gouda_core/test`（~/gouda_ws_resend、下敷き ~/gouda_ws） | ~/gouda_ws_m4x/src の写し＋Mac の gouda_core と generated/params | 400 件、不合格 1：`test_drive_sim_layers.LayerTests.test_patch_copy_only_on_a_copy`（SystemExit が出ない）。この便の変更が触れないファイルの試験で、原因は調べていない（未解決）。`test_nav2_failure_resend` の 12 件はすべて OK |
| 模擬（実の Nav2、drive_sim） | 7 節 | 同上＋Mac の gouda_interfaces | 未判定（Nav2 の goal が失敗で終わらなかった） |

## 7. 模擬

- 作業場所：模擬の機械の ~/gouda_ws_resend（~/gouda_ws_m4x/src の写しに、Mac の gouda_core/・design/generated/params/ を重ねた。下敷き ~/gouda_ws）。結果は ~/resend_runs/。ROS_DOMAIN_ID 173。指示の `--m1107` は今の drive_sim_node.py にないので `--seed 1` だけで走らせた。
- 1 回目（新・旧の 2 本）：両方とも開始が拒否された（start_refused）。gouda_motion_controller が `MotionFeedback` を import できずに落ち、gouda_monitor も落ちた。他のセッションの gouda_core の変更が新しい gouda_interfaces を要るのに、gouda_interfaces を重ねていなかった（試験基盤の誤り、1.6）。PRM-161 を外した旧の動きでも同じだったので、この便の変更によるものではない。
- 2 回目：Mac の gouda_interfaces/ も重ねて作り直し、新（PRM-161 あり）の 1 本：`SIM_ARGS="--seed 1" bash gouda_core/test/drive_sim.sh skip_blocked_unmarked ~/resend_runs/new_skip_blocked_unmarked`。開始は受け付けられ、end=timeout（151.5 s）、progress 0.428、接触 0。Nav2 の中の ComputePathThroughPoses・FollowPath は abort したが（failed_progress 2）、BT の回復が続き、NavigateThroughPoses の goal は 150 s の間に失敗で終わらなかった。`nav2_goal_resend_scheduled` も `automatic_pause` も 0 件。
- 判定：未判定。この場面では Nav2 の goal が失敗で終わらないので、新・旧どちらの動きも通らなかった。旧の 1 本は同じ結果になる見込みのため走らせていない（未実行）。goal を失敗で終わらせる場面（例：BT の回復の回数を小さくした試験用の設定）を作るのは、30 分の打ち切りにより行っていない。
- 誤り：2 回目を始めたとき、機械では既に 5 本の模擬が走っていた（上限は約 5 本）。この便の 1 本で 6 本になった。
- `ubuntu_stage5-6.sh`（T1〜T6）：未実行。

## 8. 残るリスク

- 道が物理的に塞がれていると、その場で出し直しを続けて止まり続ける。確認走行区間ではそれが 3 分続くと失格になる。waypoint を飛ばす機能（DEC-367）と組になる（人に一度伝えた懸念。この便では何もしていない）。
- 2.0 s は実測の裏付けのない値。
- 出し直しの送信の途中で人が一時停止したとき（Abandoned）、Nav2 が受け付けた goal の handle を持たないことがある。TR-10・localization_wait の再送と同じ既存の作り。motion_hold は true のまま。
- 待つ間の状態は decision の記録でしか見えない（processing_state は idle のまま）。
- 実車・車載 PC では未確認。

## 9. 次

- 人の判断：車載 PC への反映、実車での確認、DEC-438 をこの形で閉じるか、待つ間の表示（processing_state）を足すか。
- 進められる作業：goal が失敗で終わる模擬の場面を作り、新・旧を比べる（試験基盤、承認に依存しない）。ubuntu_stage5-6.sh の実行。
- 連絡への対応：統合のセッションの REV の連続適用の連絡を受けた時点で、REV-245 は既に本適用済み（02:19 ごろ）だった。それ以後の適用・生成・検査はしていない。
- commit はしていない。

## 追記：Nav2 の失敗を起こした模擬（第219便の続き）

### 読んだもの

- コミット `9c449b5`＋作業ツリー。`CLAUDE.md` 1.1・1.3〜1.6、この作業記録、`status.md` の第163〜165便・第219便。
- Mac の `mode_manager_node.py`（sha256 ae37ddd4d58cc483…）と `autonomy_core.py`（009b630653a36602…）は、模擬の機械の作業場所 ~/gouda_ws_resend の写しと同じ（試験の前に確かめた）。作り直しはしていない。

### 人の指示（原文）と、場所の変更

1. AI の質問「出し直しの結合試験を、車載 PC の模擬用の作業場所で実行してよいですか？」に、人の回答「実行して」。
2. 結合試験の台本 `ubuntu_stage5-6.sh` は Nav2 の loopback の模擬とその Python の依存を要るが、車載 PC にも模擬の機械にも入っていない。その場での導入はしない（すべて `setup.sh` から入れる決まり）。そのため、失敗は模擬の機械（ワークステーション）で `drive_sim.sh`（実の Nav2）を使って起こすことに変えた。車載 PC には触れていない。
3. その後、人の指示「opusに一連の作業をさせよ。」（この追記の作業は Opus 5.5 のサブエージェントが行った）。
4. さらに人の指示「workstationで実験を行う。」。以下の模擬はすべて模擬の機械で行った。

### 失敗を起こした手段（試験の条件であり、車両の設定ではない）

- `drive_sim.sh skip_blocked_unmarked`（waypoint (15, 0) の上に直径 2 m の茂み、印なし）、`SIM_ARGS="--seed 1"`、ROS_DOMAIN_ID 174。/config の値（IFD-54）を試験用のファイルで渡した。
- 1 回目の手段 `{"recovery_number_of_retries": 1}`：外側の RecoveryNode は 1 になった（navigate_through_poses.xml 4 行）が、150 s の間 NavigateThroughPoses の goal は失敗で終わらなかった（出し直し 0 件・TR-07 0 件、end=timeout、progress 0.428、stopped_s 0.4、接触 0）。最後の `Aborting handle` は打ち切りの終了処理の中。
- 2 回目の手段 `{"recovery_number_of_retries": 1, "replan_recovery_retries": 0, "follow_path_recovery_retries": 0}`（PRM-18・112・113 の /config の値）：外側 1・ComputePathThroughPoses 0・FollowPath 0 になった（xml 4・9・20 行、overrides.json の source は「monitor /config Nav2 tab」）。この手段で goal が失敗で終わった。新・旧・free はすべてこの手段。
- 車両の値：PRM-18 は 9999999（`bt_params.yaml`）。この値では BT の回復が続き、この経路に入るのは回復で吸収されない失敗だけになる。記録にある例は第163便（回復の後、planner が 20 ms 以内に受け付けを返さず BT が失敗、error_code 0）で、第164便はこれを「BT の回復が error_code のない失敗で 1 回も試されない」（A-1）とし、第165便の A-1 で外側の回復を error_code のない失敗でも試すように変えた。今の構成で、PRM-18 が 9999999 のままこの経路に入る失敗の種類は確かめていない（未確認）。

### 結果

| 走行 | 手段 | 前提の確認（xml の retries 外/計画/追従） | goal の失敗 | 出し直し | 待機 | end | progress | 接触 |
|---|---|---|---|---|---|---|---|---|
| fail_new（新、PRM-161 あり） | retries 1 のみ | 1 / 1 / 1 | 0 | 0 | なし | timeout（150.1 s） | 0.428 | 0 |
| 新（PRM-161 あり） | 2 回目の手段 | 1 / 0 / 0 | 2（error_code 308 NO_VALID_PATH、105 FAILED_TO_MAKE_PROGRESS） | 2 | なし | timeout（150.5 s） | 0.43 | 0 |
| 旧（PRM-161 の行を作業場所の写しから外す） | 2 回目の手段 | 1 / 0 / 0 | 1（error_code 105） | 0 | あり（TR-07、stop_reason blocked） | pause:blocked（82.5 s） | 0.428 | 0 |
| free（新） | 2 回目の手段 | 1 / 0 / 0 | 0 | 0 | なし | pause:goal_reached（63.9 s、completed） | 0.975 | 0 |

- 新：`[navigate_through_poses] [ActionServer] Aborting handle.` の 1.5 ms 後に
  `nav2_goal_resend_scheduled: Nav2 goal ended with status 6: error_code 308 (ComputePathThroughPoses.NO_VALID_PATH); no pause (DEC-437): the goal is sent again after 2.0 s (PRM-161), re-send 1`。
  その 2.001 s 後に bt_navigator `Begin navigating from current location through 6 poses to (30.00, 10.00)`（最初の goal は 8 poses）。2 回目も同じ形（error_code 105、re-send 2、2.001 s 後に 6 poses）。
- 新の出し直しの記録 `nav2_goal_resend` 自体と next_offset の値は、drive_sim の保存物（stack.launch.log ほか）に出ない（decision の記録は topic で、模擬の後に消える一時の場所にある）。送り直しは bt_navigator の新しい goal で確かめた。6 poses は茂みの上の (15, 0) から最後までの残り（route から数えた推定）。
- 待つ間の hold：trace.csv で、指令（cmd_v・cmd_w）が 0 の区間が 2 回の失敗の時刻に合う 2.7 s・1.9 s あり、その後に指令が戻った。motion_hold と speed_limit の「適用中」は保存物に出ないので、その値は未判定（指令が 0 になり、送り直しの後に戻ったことだけを確かめた）。
- 新でモードが自律走行のままだったこと：TR-07 の行 0 件、end が pause:* でない（drive_sim は待機に入ると pause:<理由> で終わる。旧と free はそうなった）。
- 旧：`TR-07: Nav2 goal ended with status 6: error_code 105 (FollowPath.FAILED_TO_MAKE_PROGRESS)`、end=pause:blocked。出し直しの行 0 件。
- 旧の後、作業場所の写しの `gouda_mode_manager.yaml` に `nav2_failure_resend_wait_s: 2.0  # PRM-161` が戻ったことを確かめた（行数 1、控えと同一）。
- free：goal 1 本、`Goal succeeded`、出し直し・TR-07 0 件。
- gouda_mode_manager の Traceback は、各走行の終了処理の `KeyboardInterrupt`（glim_runner.stop の sleep 中の SIGINT）だけ。出し直しの処理からの例外はない。
- 比べ：同じ手段で、新は失敗のたびに待機に入らず 2.0 s 後に残りの waypoint を送り直し、旧は 1 回目の失敗で待機（blocked）に入った。

### この便の変更に関係ない観察

- 4 本すべてで gouda_sensor_supervisor の監視の thread が起動直後に `AttributeError: 'Driver' object has no attribute 'host_ip'` で落ちている（`sensor_supervisor_node.py` 243 行の `d.host_ip`。`host_ip` を持つのは lidar の Driver だけ）。作業場所の写しは Mac の今のファイルと同じ（sha256 9fb3f770…）。直していない。原因の層は実装の可能性（推測、未確認）。

### 実行していないもの・判定していないもの

- `ubuntu_stage5-6.sh` の T1〜T6：未実行（道具がない）。
- 車載 PC、実車：未実行。
- 模擬の機械の単体試験の不合格 `test_drive_sim_layers.test_patch_copy_only_on_a_copy`：原因は未調査のまま（未解決）。
- 各条件 1 本ずつ。seed を変えた繰り返しは未実行。新と旧で失敗の時刻・種類が違った（新 64 s 付近の 308、旧 82 s 付近の 105）。
- motion_hold・speed_limit の状態の値：未判定（上記）。

### 残るリスク（観察したこと）

- 塞がれた waypoint（茂みの中の (15, 0)）を含む残りを送り直すので、新では 2 回の出し直し（13 s の間）の後、Nav2 が失敗を返さないまま茂みの周りを回り続けた（x 13〜17 m・y ±2 m を 76 s、stopped_s 5.0、progress 0.43 のまま打ち切り）。前に書いた「その場で出し直しを続けて止まり続ける」とは違う形で、止まらずに進まない。確認走行区間の 3 分の失格には同じく当たる。waypoint を飛ばす機能（DEC-367）の範囲で、この便では何もしていない。
- 車両の値（PRM-18 9999999）では、この模擬の失敗は起きない。試した手段は試験の条件だけ。
- 2.0 s は実測の裏付けのない値（前のとおり）。

### 原因の分類（1.6）

- この追記の範囲で直したものはない。1 回目の手段で失敗が起きなかったのは試験の条件の不足（試験基盤）で、2 回目の手段で補った。合否の基準は変えていない。

### 機械の使い方

- 模擬の始めの前に、機械で走る drive_sim の数を数えた：新 4、旧 2、free 2（上限 5）。1 本ずつ走らせた。
- 生成・正本の適用・設計検査は実行していない。コード・試験・期待値・model.yaml は変えていない。commit はしていない。
