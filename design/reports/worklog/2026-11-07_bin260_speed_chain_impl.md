# 作業記録 2026-11-07 第260便: 速度の値を 1 本の鎖にし、速度マスクの帯の外に勾配を付け、不感帯の下限を ND-11 で持つ（REV-285、DEC-505〜508、PRM-164〜166）

## 読んだもの

- コミット `8ca1551`（ブランチ chat/confirmation-plan-2026-11-07、worktree tsukuba-worktrees/confirmation-plan）。
- `CLAUDE.md` 1.1〜1.8・1.10〜1.14、`design/reports/status.md` の冒頭（第258便まで）、提案 `design/proposals/speed_chain_and_mask_gradient_2026-11-07.md`（issue #105 と同じ本文）、第258便・第251便・第219便・第236便・第192便の作業記録、`design/revisions/REV-240.yaml`・`REV-276.yaml`。
- 正本：PRM-19・20・39・66・131・152・162、DEC-045・047・055・056・480。
- コード：`speed_mask.py`、`autonomy_core.py`（resolve_mission・speed_limit_state）、`nav2_config.py`（TUNABLES・mppi_follow・apply_tunables・write）、`monitor_node.py`（_save_waypoints）、`mode_manager_node.py`（_start_precheck・_tr05_start_autonomy）、`motion_core.py`・`motion_controller_node.py`（REV-241 の層）、`web/app.js`（区間の制限の入力）、`design/tools/check_design.py`・`hardcode_scan.py`、模擬の試験用ファイル。
- 上流：nav2_mppi_controller 1.3.13 の `src/optimizer.cpp`（`gh api` で tag 1.3.13 を取得、488〜510 行）。

## 1. 人の回答（原文）

- AI の質問「A・B・C のどこまで実装に進めますか？」に、人の回答「A・B・C 全部」。
- 続けて「A,B,C全部を採用した状況でのシミュレーションを回せ。」
- 提案の推奨値（V_slow 0.3 m/s、L_ramp 2.0 m、ヒステリシス 0.02 m/s）は、人が値を述べず、提案の承認で暫定に認めたもの（DEC-508、実測の裏付けなし）。

## 2. 番号（reserve_ids.py、印は共有の common dir）

- 予約：REV-285、DEC-505・506・507・508、PRM-164・165・166、第260便。すべて使った（欠番なし）。
  - DEC-505＝A、DEC-506＝B、DEC-507＝C、DEC-508＝暫定の 3 値。PRM-164＝V_slow、PRM-165＝L_ramp、PRM-166＝ヒステリシス。

## 3. 変更（ファイルごと）

### 正本（REV-285）

- 決定 DEC-505〜508（approval、answered、chat、2026-11-07、answer_verbatim は上の 2 文）。affected_refs に ND-10・ND-11・ND-02・ND-03・IFD-41・IFD-14・IFD-54・PRM-19・20・39・66・131・162・旧 DEC（045・047・055・056・480・490・491・445）。前の決定は書き換えていない。
- 新しい PRM：PRM-164 `speed_mask_outside_speed_mps` 0.3、PRM-165 `speed_mask_ramp_length_m` 2.0（どちらも gouda_monitor、owner ND-02、PRM-19・20 の隣）、PRM-166 `floor_hysteresis_mps` 0.02（gouda_motion_controller、owner ND-11）。requirement_refs は RQ-I104（PRM-131・162 と同じ）。measurement は「暫定。…実測の裏付けなし（未実測）」。
- 修正：PRM-131（名前を「自律走行の上限 V_auto（MPPI の vx_max と velocity_smoother の前進の上限）」、purpose）、PRM-66（名前に「PRM-131 から導出」、値 1.25→0.5、purpose・measurement は導出）、PRM-162（値 0.27→0.0、approval_decision_ref DEC-507）、PRM-39・ND-10・ND-11・ND-02・ND-03・IFD-41（interpretation_append）。
- 生成物：`generate_params.py`・`render_views.py`・`render_migration_review.py` の出力（gouda_nav2.yaml の `mppi_vx_min_mps: 0.0`・`max_linear_velocity_mps: 0.5`、gouda_monitor.yaml の PRM-164・165、gouda_motion_controller.yaml の PRM-166、他はハッシュの行）。`design/reports/model_diff_rev-285.md`。

### A（DEC-505）：速度の 1 本の鎖

- `gouda_core/gouda_core/nav2_config.py`
  - `apply_tunables`：velocity_smoother の `max_velocity[0]` を `mppi_vx_max_mps`（PRM-131、/config の値を含む）にする。旋回・後退の値はそのまま。
  - `auto_speed_limit(params_dir, trial, config_dir, in_use_overrides)`：V_auto を返す。Nav2 が起動時に書いた overrides.json の値（使用中）＞ /config の次回の値 ＞ PRM-131。
  - PRM-66 は `REQUIRED` に残した（RPP の desired_linear_vel と、値の有無の確認に使う）。
- `monitor_node.py` `_save_waypoints`：区間の制限が V_auto（次の起動の値）を超えると保存を拒む（区間の番号と値を返す）。生成の記録（manifest の generator）に V_slow・L_ramp・V_auto を足した。
- `autonomy_core.py` `start_mask(mission, v_auto, out_dir, fallback)`、`mode_manager_node.py` `_start_precheck`・`_tr05_start_autonomy`：TR-05 で V_auto（Nav2 が使っている値）を超える区間を頭打ちにし、マスクを `<data_root>/run/start_mask/<set>_<rev>/` に作り直して使う。保存した組（ハッシュで固定）は変えない。記録 `speed_mask_made_at_start`（「区間 n：1.25 → 0.5」）。REV-285 より前に保存したマスク（generator に outside_mps がない）も、ここで勾配つきで作り直す。値が足りなければ開始を拒む（推測で埋めない）。
  - 場所の選び方：マスクは保存時に monitor が作り、開始時は mode manager がファイルを読むだけだった。頭打ちは「Nav2 が使っている V_auto」に合わせる必要があり、それを知るのは開始時の mode manager なので、TR-05 の検査（resolve_mission の直後）に置いた。保存済みの組を書き換えると内容のハッシュ（RQ-I078）が変わるので、run の下に別に書く形にした。
- `speed_mask.py`：`clamp_limits`・`limits_above`。
- `design/tools/check_design.py`：DR-18（PRM-66 = PRM-131）、DR-19（PRM-131 ≤ PRM-39）。値が承認済みの数でなければ未判定。`design/rules/test_check_design.py` に 4 件、`design/rules/README.md` に 2 行。DR-新2（区間の制限 ≤ PRM-131）は正本にない実行時の値なので、検査ルールにせず、monitor の拒否と `start_mask` と単体試験（`test_autonomy_core.StartMaskTests`）で担う。
- 区間の制限の既定値：製品のコードにはなかった（画面は空欄で人が入れる）。1.25 の既定値は模擬の場面（`drive_sim_core.Scenario.limit_mps`、試験専用）のもの。模擬では頭打ちが働くことを確かめるため、1.25 のままにした。

### B（DEC-506）：マスクの勾配

- `speed_mask.py` `generate(..., outside_mps, ramp_m)`（2 つは必須の引数）：帯（d ≤ PRM-19）は区間の制限（重なりは低い方、DEC-045 のまま）、帯の外 L_ramp の間は最も近い帯の制限から V_slow へ直線、それより外と帯のない所は V_slow。0 のセルは作らない（V_slow が正でなければ ValueError）。`MaskResult` に `outside_mps`・`ramp_m`・`ramp_cells`。
- `autonomy_core.speed_limit_state`：コードは変えず docstring で読み替えを書いた。「適用中」＝マスクの中で正の制限を受けた。今の生成器のマスクには 0 がないので outside_band は出ない。状態の定数は、REV-285 より前に保存したマスクのために残した（開始時に作り直すので、実際に読み込まれるマスクに 0 は残らない）。

### C（DEC-507）：不感帯の下限を ND-11 へ

- `motion_core.py`
  - `AxisFloor.target(v, v_move, h)`：|v| = 0 → 中立、|v| < V_move/2 ± h/2 → 中立、< V_move → ±V_move、それ以上 → v。中立から動き出すしきい値は V_move/2 + h/2、動いている間は V_move/2 − h/2。符号が変わったら中立から。
  - `MotionCore(settings, feedforward, floor_hysteresis_mps)`：表が使え（`feedforward_problems` が空）、PRM-166 があるときだけ床が働く（`floor_ready`）。
  - 帰還の層が無効（既定）のとき：`_floor_output`。軸ごとに、人が /config で DEC-171 の補償を入れた向きはそのまま補償、それ以外は床＋表（`FeedforwardAxis.stick`）。記録の mode は新しい `floor`。今までの無効のときの出力（PRM-39 での正規化）は、表か PRM-166 がないときだけ。
  - 帰還の層が有効のとき：`_feedback_output` の PI の目標に床を掛ける（0 なら軸を中立にし積分を戻す、V_move 未満は V_move を目標にする）。
  - V_move は前進 PRM-152（0.09 m/s）、後退 PRM-155（0.075 m/s）、旋回 PRM-158（0.075 rad/s）。動き出す倒し量は表の V_move での値（PRM-151 0.21・154 0.24・157 0.195）。旋回の h は h × PRM-158 ÷ PRM-152（rad/s）。
  - 中立の理由（hold・古い cmd_vel など）と deactivate で床の状態も戻す（`reset_feedback`）。
- `motion_controller_node.py`：`floor_hysteresis_mps` を宣言して渡す。軸ごとの床の分岐が変わるたびに DecisionEvent `motion_floor`。configure の記録に `floor_hysteresis_mps`・`floor_used`。
- `nav2_config.py`：PRM-162 の注記だけ（値は生成物から 0.0。`mppi_follow` は今までどおり書く）。
- 既存の層の再利用：表（`FeedforwardAxis`）と PI（`AxisPI`）はそのまま使い、目標の前に床を置いただけ。並行の別の経路は作っていない。

### 試験・試験用ファイル

- 新規 `gouda_core/test/test_motion_floor.py`（8 件）：前進の全分岐、ヒステリシス（しきい値の上下を行き来しても動いたまま／止まったまま）、後退と符号の変化、旋回（その場の旋回を含む）、hold での戻し、補償の向きの優先、帰還の層の目標、PRM-166 なしで変わらないこと。値は生成物から読む。
- `test_waypoints_core.py`：勾配の形（帯の中・勾配の 5 点・外）、0 のセルがないこと（帯の制限 3 通り、L_ramp 0）、最も近い帯から始まる勾配（2 本の平行な区間）、刻みの量子化（0.05 m/s 刻みで 6〜10）、`clamp_limits`・`limits_above`。既存の 4 件は新しい引数を渡す形に直した（「帯の外は 0」の期待値は V_slow に変えた：DEC-506）。
- `test_autonomy_core.py`：勾配のマスクで適用中（帯の外を含む）、`StartMaskTests` 5 件（V_auto 以下はそのまま、頭打ちの区間と作り直したマスクの最大・最小、古いマスクに勾配、値が足りないときの拒否、開始後の区間はすべて V_auto 以下＝DR-新2 の実行時の性質）。
- `test_nav2_config.py`：smoother が V_auto に従う（/config 0.4 のとき）、`auto_speed_limit` の優先順位。既存の期待値 1 件を変えた：`vx_min` 0.27 → 0.0（DEC-507。根拠は人の回答）、smoother の上限＝vx_max の確認を足した。
- 試験用の写し：`drive_sim_fixture.py`・`stage56_fixture.py`・`drive_sim_course.py` は `generate` に生成物の PRM-164・165 を渡し、generator にも記録する。`drive_sim_fixture.py` は `skip_marks` がない古い `Scenario`（模擬の機械の m4x 版）でも動くようにした。`drive_sim_course.py` に `course_A_L05`・`course_B_L05`（区間の制限 0.5、比較用）。

## 4. 自律判断と理由

- V_auto は PRM-131 のまま（提案 7 節の未回答の項目）。理由：回答「A・B・C 全部」は提案の既定の読み。番号を変えると /config・模擬・記録の参照が全部変わる。
- 勾配は「最も近い帯」から始める（勾配どうしの重なりで低い方を取らない）。理由：低い方にすると、別の区間の勾配が帯の縁で値を段に下げる（例：角で、もう一方の区間の勾配が帯の縁を 0.5 → 0.37 にする）。DEC-506 の note に AI の読みとして書いた。確認が要る。
- 床は帰還の層が無効のときも働かせた。理由：今までの MPPI の下限は常に働いていた。床が /config の層の中だけだと、vx_min 0 にしたとき既定の設定で下限がなくなる。その結果、無効のときの倒し量は「PRM-39 での正規化」から「表」に変わる（0.5 m/s で 0.40 → 0.49）。承認された C の文（v ≥ V_move は表）のとおり。
- 人が /config で DEC-171 の補償を入れた向きは補償を優先した。理由：人が明示した設定を黙って無効にしない。補償も不感帯の下限の一種で、二重に掛けない。
- 旋回のヒステリシスは PRM-166 から換算した（番号を増やさない）。DEC-507 の note に書いた。確認が要る。
- その場の旋回の倒し量（左 0.30・右 0.18、第192便）は使っていない。正本にない実測の候補（DEC-409 未決）で、値をコードに書けない（DR-15）。その場の旋回は表（PRM-156〜160、前進中の旋回の実測）のまま。未判定。
- 区間の制限の頭打ちは V_auto の「Nav2 が使っている値」、保存の拒否は「次の起動の値」で比べた。理由：開始時は今動いている Nav2 に合わせる。保存時は Nav2 が動いていないこともある。
- PRM-162 の値 0.0 のため、DR-15 の走査で「承認値と同じ数（PRM-162）」の未判定が 100 件増えた（43 → 143 件。0.0 はコードのどこにでもある）。走査器の変更（承認値の 0 を数えない）は検査の緩和にあたるので変えていない。**承認事項として残す**（下の 9 節）。

## 5. 原因の分類（1.6）

- A・B：設計（速度の値の関係の決まりがない、帯の外の扱いが未設計）。正本を直して再生成し、検査をやり直した。
- C：設計（下限を MPPI の中に置いたため止まれない）＋設定（PRM-162 の値）。
- 試験の期待値：上の 2 件（帯の外 0 → V_slow、vx_min 0.27 → 0）。どちらも人の回答（DEC-506・507）が根拠。

## 6. 先行事例（1.11）

| 探した場所 | 見たもの | 採否と理由 |
|---|---|---|
| Nav2 1.3.13 の SpeedFilter（type 2、絶対値） | セルの値 × multiplier ＋ base が速度の制限（m/s）。0 は制限なし（NO_SPEED_LIMIT）。勾配はマスクの値だけで表せる | 採用：Nav2 本体は変えず、マスクの値で勾配を作る（RQ-I056） |
| nav2_mppi_controller 1.3.13 `optimizer.cpp` 488〜510 行（`gh api` で tag 1.3.13 を読んだ） | 絶対値の制限は `double ratio = speed_limit / s.base_constraints.vx_max;` で、vx_max・vx_min・vy・wz の全部に同じ比を掛ける。制限なしなら基準値に戻す | 確認した事実。比が 1 を超えると引き上げるので、A で区間の制限 ≤ V_auto を守る。V_slow 0.3 のとき wz の上限も 0.3 rad/s に下がる（提案 3 節の確認事項のまま） |
| 上流の issue での議論、他チームの「経路からの距離で減速」 | — | 未調査 |
| KUAMS（第238便の調べ） | 速度マスクの勾配の記述はない | 参考なし |
| 不感帯の下限（ND-11） | REV-241 のフィードフォワード＋PI（自作、DEC-445 の実測の表） | 再利用。新しい部品は作っていない |

## 7. 検査・試験（実行したもの）

| 検査 | コマンド | 対象 | 結果 |
|---|---|---|---|
| 単体試験（Mac、変更前） | `PYTHONPATH=gouda_core python3 -m unittest discover -s gouda_core/test` | 8ca1551 の worktree | 489 件 OK（skip 35）（status.md の 99a5be6 の数と同じ。変更前の数は worktree での実行の数で、`git archive` の写しでは 1 件不合格：`test_drive_sim_layers.test_patch_copy_only_on_a_copy`。リポジトリの外の写しでは起きる既知の差） |
| 単体試験（Mac、変更後） | 同上 | 1676896 | 510 件 OK（skip 35） |
| 変更セットの試し | `apply_revision.py REV-285 --dry-run --check` | 同上 | 0 new violations、108 new undetermined（DR-15 の 0.0、4 節） |
| 本適用と生成 | `apply_revision.py REV-285` → `generate_params.py` → `render_views.py` → `render_migration_review.py` | 同上 | 成功 |
| 設計検査 | `run_checks.py` | 同上 | 終了コード 1。design_check PASS：合格 14・違反 0・未判定 5（DR-04・05・10・11・15）。DR-18・19 合格。既存の不合格：input_integrity・migration_validator（SystemArchitecture.drawio・.DS_Store だけ）、migration_tests 92 件中 1 件（test_real_model、同じ原因） |
| 構文 | `python3 -m py_compile` mode_manager_node・monitor_node・motion_controller_node | 同上 | 成功（rclpy がないので Mac では import していない） |
| 模擬（ROS 2 Jazzy、実の Nav2） | 8 節 | 1676896 の写し | 8 節 |

- 単体試験の実行に使った interpreter：検査は統合の checkout の `design/.venv/bin/python` で、この worktree の `design/tools/*.py` を実行した（道具はファイルの場所から design を決めるので、worktree の design を読んだ）。

## 8. 模擬（A・B・C を入れた状態）

人の指示「A,B,C全部を採用した状況でのシミュレーションを回せ。」による。試験専用。製品・正本は 1676896 のまま。

### 8.1 基盤（作業場所・写し・入力）

- 機械：ワークステーション（`~/gouda_ws_abc`、結果 `~/abc_runs`）と車載 PC（模擬だけ、`~/gouda_ws_abc`、結果 `~/abc_runs`）。`~/gouda_ws_course/src` を写し、この worktree の `gouda_core/`（`test/drive_sim_core.py`・`drive_sim_node.py` を除く）・`gouda_interfaces/`・`design/generated/params/` を重ねた。`nav2_config.py` には写しだけに `GOUDA_TEST_NAV2` の上書き（`patch_nav2_copy.py`）を足し直した。下敷きは各機械の `~/gouda_ws/install`（source だけ。変えていない）。build は `colcon build --packages-select gouda_interfaces gouda_core`（2 台とも成功）。sha256 の先頭 16 桁：motion_core.py 544ded7deb528462、speed_mask.py c55191dc7ea5666a、autonomy_core.py 22c7be1b95421d60、mode_manager_node.py 142f541ed13fc0c8、nav2_config.py（写し）41e6f23ce3674d50、gouda_nav2.yaml bd6a2a29344c7115。
- `drive_sim_node.py`（m4x の写し）に試験専用の `--joy` を足した（`patch_joy.py`、写しだけ）。今までの模型は Nav2 の cmd_vel を直接入力にしていて、ND-11 の出力を通らない（C が模擬に効かない）。`--joy` では ND-11 の `vehicle/joystick_command` を入力にする（前進は倒し量×max_v、後退は×max_reverse_v、旋回は×max_w）。`--m1107` の模型は「指令÷max_v」の倒し量の単位で不感帯を掛けるので、`--joy` での模型の入力は ND-11 の倒し量そのものになる。不感帯は 1 回だけ掛かる。速度側に別の不感帯はない。
  - 模型の不感帯の値（`drive_sim_core.M1107` と `STICK_THRESHOLD`、変えていない）：前進は動き出し 0.21・保持 0.195、後退 0.24・0.215、最低速度は前進 0.09・後退 0.075 m/s、走行中の旋回は 0.19 未満で曲がらない、その場の旋回は左 0.28・右 0.165（第200便）。DEC-445 の表（前進の止まる倒し量 0.185、走行中の旋回 0.184／0.195）や第192便の候補（左 0.30・右 0.18）とは少し違う。前の結果と比べられるように、模型は変えていない。
  - 模型の倒し量→速度（前進）：0.09 + 1.125 ×（倒し量 − 0.21）。ND-11 の表は倒し切り 1.0 で 1.25 m/s とする（PRM-39、実測ではない）。そのため、0.5 m/s の指令（倒し量 0.489）は模型では 0.40 m/s になる（計算、軌跡の速度で確かめた）。
- 区間の制限：模擬の場面は 1.25（既定）。開始時に V_auto 0.5 へ頭打ちになった。map_server が開始時に作ったマスク（`run/start_mask/.../speed_mask.yaml`）を読んだことを、stack のログで確かめた（free_s1、course_A_combo_s1 など）。`tail_*_L05`（区間の制限 0.5）では、保存したマスク（`routes/.../speed_mask.yaml`）を読んだ。頭打ちと、それ以外の変更とを分けた。
- Nav2 の値（実行の nav2_params.yaml）：vx_max 0.5、vx_min 0.0、velocity_smoother max_velocity [0.5, 0.0, 0.5]。C なしの比較：vx_min 0.27。
- C なしの比較（基盤の変更と C の効果を分けるため）：写し `~/gouda_ws_abc_noc`。生成物から PRM-166 の行を消した写しで、ND-11 の床が働かず今までの正規化になる。/config の値 `{"mppi_vx_min_mps": 0.27}`。A・B はそのまま。
- 条件：すべて 1 倍速、`--m1107 --joy --seed N`。植込みの場面は第251便と同じ（`COURSE_EXT=drive_sim_course_starts MAX_SIM_S=480 STOP_RESUME_WALL_S=2.5`）。コーンの組み合わせ（第238便）は `RAYTRACE_MIN_M=2.0` と values.json `{"obstacle_max_range_m": 5.0, "raytrace_max_range_m": 6.0}`。
- 同時に走らせた数と domain：ワークステーションは自分の本が最大 2 本（domain 200・201、C なしは 206）。車載 PC は最大 3 本（202・203・204、追加の本は 205）。開始の間隔は 40 s 以上。load1 が 16 を超えている間は待った。開始時の load1 はワークステーション 3.1〜15.2、車載 PC 1.0〜16.9（starts.log）。車載 PC で開始の前に `ps -eo args | grep -c "[l]aunch gouda_core gouda_core.launch.py params_dir:=/home"` が 0 であることを確かめた。走らせている間は 20 s ごとに記録した（guard.log：一度も 0 以外にならなかった）。gouda.sh は実行していない。

### 8.2 結果（本ごと）

列：終わり／ゴール／接触（場所 s m）／1 m 進まない最長 s（最初の指令から最後の動きまで）／自動の待機／出し直し／spin・backup・wait／時間 s（植込み・コースは解析の時間）／平均 m/s／cmd_v の 1 % 点と最大／止まって再び動いた回数［始めた時刻 s、止まった長さ s］（車体の |v|・|w| < 0.02 が 0.5 s 以上。一時停止線の約 2.7 s を含む）／終わりの load1／その他。

| 本 | 機械 | 終わり | ゴール | 接触 | 無進捗 s | 待機 | 出し直し | s/b/w | 時間 s | 平均 | cmd_v 1%／最大 | 止まって再開 | load | その他 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| course_A_combo_s1 | ws | pause:goal_reached | True | {} | 8.1 | 0 | 0 | 0/0/0 | 1045.4 | 0.383 | 0.13 / 0.5 | 1 [[859.8, 2.7]] | 9.86 | 最大横ずれ 0.96 m、無進捗の場所 s=384.5（cone_field） |
| course_B_combo_s1 | ws | pause:goal_reached | True | {} | 8.2 | 0 | 0 | 0/0/0 | 1043.8 | 0.383 | 0.116 / 0.5 | 1 [[855.6, 2.8]] | 9.31 | 最大横ずれ 0.9 m、無進捗の場所 s=384.4（cone_field） |
| free_s1 | ws | pause:goal_reached | True | 0 | 6.6 | 0 | 0 | 0/0/0 | 105.0 | 0.371 | 0.073 / 0.5 | 0 [] | 4.81 |  |
| free_s2 | ws | pause:goal_reached | True | 0 | 6.4 | 0 | 0 | 0/0/0 | 105.1 | 0.371 | 0.089 / 0.5 | 0 [] | 6.35 |  |
| free_s3 | ws | pause:goal_reached | True | 0 | 6.3 | 0 | 0 | 0/0/0 | 105.4 | 0.37 | 0.063 / 0.5 | 0 [] | 4.75 |  |
| noc_free_s1 | ws | pause:goal_reached | True | 0 | 9.1 | 0 | 0 | 0/0/0 | 144.9 | 0.269 | 0.27 / 0.5 | 0 [] | 10.09 |  |
| noc_free_s2 | ws | pause:goal_reached | True | 0 | 9.1 | 0 | 0 | 0/0/0 | 144.8 | 0.269 | 0.27 / 0.5 | 0 [] | 23.36 |  |
| noc_pst_PMs_+000_s1 | ws | pause:goal_reached | True | {} | 7.6 | 0 | 0 | 0/0/0 | 62.7 | 0.254 | 0.18 / 0.5 | 1 [[30.1, 2.8]] | 7.0 | 植込み 0.482・内壁 0.873・外壁 1.009・柱 1.296 |
| noc_pst_PMs_+090_s1 | ws | pause:goal_reached | True | {} | 10.9 | 0 | 0 | 0/0/0 | 66.2 | 0.242 | 0.191 / 0.5 | 1 [[32.7, 2.9]] | 6.11 | 植込み 0.174・内壁 0.938・外壁 0.745・柱 1.15 |
| person_stands_s1 | ws | pause:goal_reached | True | 0 | 9.7 | 0 | 0 | 0/0/0 | 115.0 | 0.339 | 0.035 / 0.5 | 0 [] | 7.76 |  |
| person_stands_s2 | ws | pause:goal_reached | True | 0 | 11.7 | 0 | 0 | 0/0/0 | 115.8 | 0.337 | 0.023 / 0.5 | 1 [[41.4, 0.6]] | 10.96 |  |
| sidewalk_cone_s1 | ws | pause:goal_reached | True | 0 | 4.9 | 0 | 0 | 0/0/0 | 80.7 | 0.36 | 0.134 / 0.5 | 0 [] | 6.69 |  |
| sidewalk_cone_s2 | ws | pause:goal_reached | True | 0 | 4.9 | 0 | 0 | 0/0/0 | 80.4 | 0.361 | 0.144 / 0.5 | 0 [] | 5.65 |  |
| tail_A_L05_combo_s1 | ws | pause:goal_reached | True | {} | 9.8 | 0 | 0 | 0/0/0 | 173.5 | 0.346 | 0.051 / 0.5 | 1 [[119.2, 2.3]] | 11.66 | 最大横ずれ 0.96 m、無進捗の場所 s=374.4（cone_field） |
| tail_B_L05_combo_s1 | ws | pause:goal_reached | True | {} | 8.1 | 0 | 0 | 0/0/0 | 170.9 | 0.351 | 0.075 / 0.5 | 0 [] | 11.08 | 最大横ずれ 0.81 m、無進捗の場所 s=384.2（cone_field） |
| noc_pst_PM_+090_s1 | vpc | pause:goal_reached | True | {} | 9.2 | 0 | 0 | 0/0/0 | 65.6 | 0.244 | 0.18 / 0.5 | 1 [[29.2, 2.8]] | 7.24 | 植込み 0.874・内壁 0.981・外壁 1.069・柱 1.495 |
| noc_pst_PMs_+135_s1 | vpc | pause:goal_reached | True | {} | 14.3 | 0 | 0 | 0/0/0 | 72.4 | 0.223 | 0.21 / 0.5 | 1 [[38.7, 2.7]] | 4.52 | 植込み 0.174・内壁 1.065・外壁 0.84・柱 1.023 |
| pst_P1_+000_s1 | vpc | pause:goal_reached | True | {} | 6.4 | 0 | 0 | 0/0/0 | 57.2 | 0.321 | 0.029 / 0.5 | 1 [[35.7, 2.8]] | 10.46 | 植込み 0.86・内壁 0.95・外壁 1.123・柱 1.2 |
| pst_P1_+090_s1 | vpc | pause:goal_reached | True | {} | 8.4 | 0 | 0 | 0/0/0 | 61.0 | 0.299 | 0.009 / 0.5 | 1 [[36.1, 2.8]] | 4.6 | 植込み 0.772・内壁 0.915・外壁 1.072・柱 0.926 |
| pst_P1_+090_s2 | vpc | pause:goal_reached | True | {} | 8.5 | 0 | 0 | 0/0/0 | 55.2（result の値） | 0.3 | 0.009 / 0.5 | 1 [[35.8, 2.7]] | 7.19 | 植込み 0.747・柱 0.931。下の注 |
| pst_P1_+180_s1 | vpc | pause:goal_reached | True | {} | 13.9 | 0 | 0 | 0/0/0 | 66.2 | 0.274 | 0.007 / 0.5 | 1 [[49.2, 2.6]] | 5.21 | 植込み 0.877・内壁 0.957・外壁 0.824・柱 1.208 |
| pst_P2_+045_s1 | vpc | pause:goal_reached | True | {} | 6.7 | 0 | 0 | 0/0/0 | 63.3 | 0.304 | 0.021 / 0.5 | 1 [[47.9, 2.7]] | 10.37 | 植込み 0.869・内壁 0.955・外壁 1.068・柱 0.952 |
| pst_P2_+090_s1 | vpc | pause:goal_reached | True | {} | 8.5 | 0 | 0 | 0/0/0 | 66.0 | 0.292 | 0.021 / 0.5 | 1 [[40.9, 2.9]] | 8.92 | 植込み 0.74・内壁 0.916・外壁 1.07・柱 1.097 |
| pst_PM2_+090_s1 | vpc | pause:goal_reached | True | {} | 10.8 | 0 | 0 | 0/0/0 | 40.2 | 0.306 | 0.039 / 0.5 | 1 [[15.1, 2.6]] | 6.52 | 植込み 0.874・内壁 0.885・外壁 1.072・柱 2.797 |
| pst_PM_+090_s1 | vpc | pause:goal_reached | True | {} | 7.8 | 0 | 0 | 0/0/0 | 52.9 | 0.306 | 0.001 / 0.5 | 1 [[27.2, 2.7]] | 7.69 | 植込み 0.794・内壁 0.913・外壁 1.071・柱 1.495 |
| pst_PM_+090_s2 | vpc | pause:goal_reached | True | {} | 7.9 | 0 | 0 | 0/0/0 | 53.1 | 0.306 | 0.003 / 0.5 | 1 [[28.1, 2.6]] | 5.16 | 植込み 0.797・内壁 0.913・外壁 1.073・柱 1.495 |
| pst_PM_+135_s1 | vpc | pause:goal_reached | True | {} | 9.4 | 0 | 0 | 0/0/0 | 54.5 | 0.295 | 0.006 / 0.5 | 1 [[26.7, 2.8]] | 4.87 | 植込み 0.844・内壁 0.949・外壁 1.068・柱 1.467 |
| pst_PM_-090_s1 | vpc | pause:goal_reached | True | {} | 8.7 | 0 | 0 | 0/0/0 | 54.8 | 0.294 | 0.003 / 0.5 | 1 [[30.2, 2.6]] | 7.88 | 植込み 0.736・内壁 0.928・外壁 0.824・柱 1.714 |
| pst_PMs_+000_s1 | vpc | pause:goal_reached | True | {} | 6.9 | 0 | 0 | 0/0/0 | 51.8 | 0.318 | 0.022 / 0.5 | 1 [[25.2, 2.5]] | 11.5 | 植込み 0.472・内壁 0.884・外壁 1.094・柱 1.296 |
| pst_PMs_+090_s1 | vpc | pause:goal_reached | True | {} | 11.9 | 0 | 0 | 0/0/0 | 59.6 | 0.272 | 0.009 / 0.5 | 2 [[85.9, 1.2], [97.6, 2.7]] | 7.56 | 植込み 0.174・内壁 0.869・外壁 1.095・柱 1.15 |
| pst_PMs_+135_s1 | vpc | pause:goal_reached | True | {} | 12.5 | 0 | 0 | 0/0/0 | 59.3 | 0.274 | 0.006 / 0.5 | 2 [[21.8, 0.9], [32.9, 2.8]] | 5.81 | 植込み 0.174・内壁 0.866・外壁 1.095・柱 1.023 |
| pst_PMs_+135_s2 | vpc | pause:goal_reached | True | {} | 12.4 | 0 | 0 | 0/0/0 | 53.5（result の値） | 0.274 | 0.004 / 0.5 | 2 [[23.2, 1.0], [34.6, 2.7]] | 7.58 | 植込み 0.174。下の注 |
| tail_A_combo_s1 | vpc | pause:goal_reached | True | {} | 9.6 | 0 | 0 | 0/0/0 | 172.5 | 0.348 | 0.113 / 0.5 | 1 [[137.0, 1.8]] | 16.87 | 最大横ずれ 0.96 m、無進捗の場所 s=384.3（cone_field） |
| tail_A_combo_s2 | vpc | pause:goal_reached | True | {} | 6.8 | 0 | 0 | 0/0/0 | 169.8 | 0.353 | 0.145 / 0.5 | 0 [] | 11.99 | 最大横ずれ 0.93 m、無進捗の場所 s=384.5（cone_field） |
| tail_A_combo_s3 | vpc | pause:goal_reached | True | {} | 8.6 | 0 | 0 | 0/0/0 | 170.8 | 0.351 | 0.065 / 0.5 | 1 [[137.0, 1.0]] | 12.45 | 最大横ずれ 0.96 m、無進捗の場所 s=384.3（cone_field） |
| tail_A_def_s1 | vpc | pause:goal_reached | True | {'cone': (2, [375.3, 391.8])} | 8.8 | 0 | 0 | 0/0/0 | 166.5 | 0.36 | 0.109 / 0.5 | 1 [[148.5, 0.7]] | 9.98 | 最大横ずれ 0.54 m、無進捗の場所 s=390.5（cone_field） |
| tail_A_def_s2 | vpc | pause:goal_reached | True | {'cone': (2, [375.3, 391.6])} | 14.8 | 0 | 0 | 0/0/0 | 173.8 | 0.345 | 0.063 / 0.5 | 2 [[149.5, 1.4], [156.9, 0.6]] | 17.13 | 最大横ずれ 0.48 m、無進捗の場所 s=390.4（cone_field） |
| tail_A_def_s3 | vpc | pause:goal_reached | True | {'cone': (2, [375.3, 391.8])} | 8.0 | 0 | 0 | 0/0/0 | 167.6 | 0.358 | 0.127 / 0.5 | 0 [] | 3.0 | 最大横ずれ 0.59 m、無進捗の場所 s=382.5（cone_field） |
| tail_B_combo_s1 | vpc | pause:goal_reached | True | {} | 8.3 | 0 | 0 | 0/0/0 | 171.2 | 0.35 | 0.107 / 0.5 | 0 [] | 11.11 | 最大横ずれ 0.83 m、無進捗の場所 s=384.4（cone_field） |
| tail_B_combo_s2 | vpc | pause:goal_reached | True | {} | 8.2 | 0 | 0 | 0/0/0 | 171.9 | 0.349 | 0.06 / 0.5 | 0 [] | 10.19 | 最大横ずれ 0.82 m、無進捗の場所 s=384.4（cone_field） |
| tail_B_combo_s3 | vpc | pause:goal_reached | True | {} | 8.2 | 0 | 0 | 0/0/0 | 170.7 | 0.351 | 0.092 / 0.5 | 0 [] | 16.68 | 最大横ずれ 0.94 m、無進捗の場所 s=384.3（cone_field） |
| tail_B_def_s1 | vpc | pause:goal_reached | True | {'cone': (2, [375.3, 391.7])} | 13.3 | 0 | 0 | 1/0/1 | 175.6 | 0.342 | 0.099 / 0.5 | 2 [[146.8, 0.9], [171.3, 1.2]] | 19.05 | 最大横ずれ 0.53 m、無進捗の場所 s=397.5（cone_field） |
| tail_B_def_s2 | vpc | pause:goal_reached | True | {'cone': (2, [375.2, 391.9])} | 10.2 | 0 | 0 | 0/0/0 | 169.2 | 0.355 | 0.053 / 0.5 | 1 [[124.4, 1.4]] | 5.37 | 最大横ずれ 0.65 m、無進捗の場所 s=382.2（cone_field） |
| tail_B_def_s3 | vpc | pause:goal_reached | True | {'cone': (2, [375.3, 391.9])} | 6.8 | 0 | 0 | 0/0/0 | 166.2 | 0.361 | 0.136 / 0.5 | 0 [] | 1.1 | 最大横ずれ 0.66 m、無進捗の場所 s=382.4（cone_field） |
| pst_P2_+045_s2 | vpc | pause:goal_reached | True | 0 | 7.7 | 0 | 0 | 0/0/0 | 58.0（result の値） | 0.303 | 0.027 / 0.5 | 1 [[45.4, 2.7]] | 14.96 | 植込み 0.859・柱 0.957。下の注 |


- 注：pst_P2_+045_s2・pst_P1_+090_s2・pst_PMs_+135_s2 の 3 本は、終わった後で、同じ名前の本を走らせる 2 本目の lane に車載 PC の結果のディレクトリを上書きされた（下の 8.5）。表の値は、上書きの前（06:42〜06:44）に読んだ解析の出力と、Mac に写した trace.csv のもの。植込みの解析（plant.json）の接触の分類と最小の隙間は、上書きの前に読めた分だけ書いた。
- `{}`・`0` は接触なし。コーン区間・全コースの接触の列は course.json の接触（壁・柱・植込み・コーン）。植込みの場面は plant.json（植込み・内壁・外壁・柱）。「その他」は最小の隙間（m）と、最も長く進まなかった場所。
- 「自動の待機」は、終わりが `pause:goal_reached` 以外の本の数。0 本。出し直し（PRM-161）と waypoint の飛ばしも、全本で 0。

### 8.3 まとめ（場面ごと）

1. 発進（#61、free）：A・B・C では 3 本ともゴール（105.0〜105.4 s、平均 0.37 m/s、接触 0）。最初の指令から動き出すまで 0.76〜0.80 s。止まって再び動くことは 0 回。ND-11 の最初の倒し量は 0.21（動き出す倒し量）。C なし（--joy、vx_min 0.27、ND-11 は正規化）では 2 本ともゴール（144.8〜144.9 s、0.27 m/s）。動き出しは 0.95 s。前の結果との比較：下限＋open_loop（第236便）は平均 0.44〜0.45 m/s、open_loop のみ（第215便）は 0.37〜0.40 m/s。今の版が遅いのは、次の 2 つによると見ている（計算と軌跡から。前の本の軌跡は読んでいない）。
   - (i) 区間の制限が 0.5 に頭打ちになり、比 2.5 の引き上げ（vx_max 1.25）がなくなった。
   - (ii) この場面では、出発点から最初の waypoint までの約 27 m が帯の外で、V_slow 0.3 になる（B）。
   - C なしがさらに遅いのは、0.3 m/s の指令が正規化で倒し量 0.24 になり、模型では 0.12 m/s しか出ないため。床と表では 0.25 m/s 出る（軌跡、`png/noc_free_s1.png`・`free_s1.png`）。
2. 植込みの始点：第251便で不合格だった 8 姿勢はすべてゴールで、接触 0（種 1。P2 +45・P1 +90・PM +90・PMs +135 は種 2 もゴール・接触 0）。前に合格だった 4 姿勢（P1 0、P1 180、PM -90、PM2 +90）も合格。全本で MPPI の「Optimizer fail」は 0 回、cmd_v の最大は 0.5（第251便の 0.675 は出ない）。
   - 仕組み A（角の手前で下限が 0.675 に上がり、外側の壁へ）：区間の制限の頭打ちで、比が 1 以下になって消えた。
   - 仕組み B（始めの旋回で前の角が植込みを掃く）：PMs +90・PMs +135 の植込みとの最小の隙間は 0.174 m で、接触はなかった。C ありの PMs +90 では、その場で右へ回る動き（v 0、w −0.44 rad/s）があった。
   - C なしの比較（PMs 0、PMs +90、PM +90、PMs +135 の 4 本）もすべてゴール・接触 0 で、隙間は同じ 0.174 m。平均は 0.22〜0.25 m/s で、C ありの 0.27〜0.32 m/s より遅い。**この場面の不合格をなくしたのは、主に A（頭打ち）で、C ではない**（比較から。ただし C なしでも B は入っている）。
3. コーン区間（tail_A・tail_B、各 3 本）：
   - 第238便の組み合わせあり：8 本（tail_A・tail_B 各 3 本、L05 各 1 本）すべてゴール、接触 0。
   - 組み合わせなし（既定の印）：6 本ともゴール。どの本もコーンに 2 回接触（s 375.3 m と 391.6〜391.9 m。第238便と同じ 2 か所の背の高いコーン）。
   - 止まって再び動いた回数：組み合わせありで 0〜1 回、なしで 0〜2 回（0.6〜2.3 s）。C で止まれるようになって出た動き。滞留（1 m 進まない最長）は 6.8〜14.8 s。
   - 区間の制限 1.25（頭打ち）と 0.5（L05）で、時間はほぼ同じ（169.8〜172.5 s と 170.9〜173.5 s）。
4. 全コース 400 m（組み合わせあり、各 1 本）：A・B ともゴール、接触 0。時間はそれぞれ 1045.4 s・1043.8 s、平均 0.383 m/s。止まったのは一時停止線の 1 回だけ（2.7〜2.8 s、人の再開の台本）。Optimizer fail 0。2 倍速は走らせていない（未実行）。
5. 人とコーンの短い場面（2 本ずつ）：person_stands はゴール・接触 0、115.0〜115.8 s、人との最小の隙間 0.55〜0.57 m。止まって再び動いたのは 0〜1 回（0.6 s）。sidewalk_cone はゴール・接触 0、80.4〜80.7 s、隙間 0.35〜0.37 m。長い滞留はなかった（最長 4.9〜11.7 s）。帯の外の勾配で避けが滞ることはなかった。

- PNG（リポジトリの外）：`/private/tmp/claude-501/-Users-AYARyoya-Desktop------TsukubaChallenge/a373f789-0e60-47dc-8589-44fbbd888e46/scratchpad/abc/png/`（軌跡を車体の速度で色分けした図と、cmd_v・車体の速度・ND-11 の前進の倒し量の時系列。21 枚）。

### 8.4 判定

- 植込みの始点：第251便の基準で、12 姿勢（種 1）すべて合格。種 2 の 4 本も合格。未判定 0。
- そのほかの場面：ゴール・接触の事実だけを書く。合否の基準は人。
- 実車で同じになるかは未判定（模型の倒し量→速度の上側と、その場の旋回のしきい値は実測でない）。

### 8.5 模擬の進め方の誤り（試験の基盤、1.6）

- 植込みの最初の 3 本（V1〜V3）は、`STOP_RESUME_WALL_S` を渡していなかった。そのため一時停止線で止まったまま進まず、こちらで止めた（`aborted_no_resume/` に移した）。全コースの最初の 1 本（course_B）も同じ理由で止め、どちらも渡してから回し直した。
- C なしの最初の 4 本（domain 200）は開始の段階で失敗した（「waypoint set … not found」、node_failure）。同じ domain に別の stack がいて、開始の要求がそちらに届いたと見ている（推測。その時刻のプロセスは確かめていない）。domain 205・206 で回し直した（失敗した本は `failed_domain_clash/` に移した）。走らせている間に、ワークステーションで別のセッションが domain 207 を使っているのを見た。
- 植込みの解析（`drive_sim_course_starts.py analyze`）が、lane の中では gouda_core を import できず失敗した。後で写しの install を source して実行した（`an_pst.sh`）。
- 車載 PC への ssh の 1 回が、手元では返らずに時間切れになった。その後、遅れて実行された。その結果、C なしの写しが作り直され、2 本目の V4 の lane が動いた（06:48〜06:50）。この lane が pst_P2_+045_s2・pst_P1_+090_s2・pst_PMs_+135_s2 のディレクトリを上書きした。気づいてすぐ止めた（starts.log に記録した）。上書きの前に読んだ値で表を作った。
- 自分の本の数の上限（車載 PC 3、ワークステーション 2）は、2 本目の V4 の間も超えていない（V1〜V3 は終わっていた）。

### 8.6 未実行

- 全コースの 2 倍速。全コースの組み合わせなし。C なしでのコーン区間・全コース。不合格だった姿勢の 3 本目。その場の旋回の左右差を入れた模型。
- 前の結果（第236便・第215便）の軌跡との直接の比較（数だけ比べた）。

## 9. 承認事項・確認事項

- DR-15 の走査で、承認値 0.0（PRM-162）の行が未判定に 100 件増えた。走査器を変える（承認値の 0 を数えない）かどうかは人の判断。変えていない。
- 勾配どうしの重なりの決まり（最も近い帯から、DEC-506 の note）。
- 旋回のヒステリシスの換算（DEC-507 の note）。
- その場の旋回の倒し量の左右差（第192便の候補、DEC-409）を ND-11 の床に入れるか。
- /config に保存した `mppi_vx_min_mps`（正の数だけ受ける）が実車にあれば、C の下限 0 が効かない。実車の /config の確認は人。

## 10. 残るリスク

- V_slow・L_ramp・ヒステリシスは実測の裏付けがない暫定の値。
- 帰還の層が無効のときの倒し量が表に変わった（0.5 m/s で 0.40 → 0.49 の倒し量）。表の倒し切りの点（1.25 m/s）は実測でない（PRM-39 の仮定）。実車の速度は未確認。
- MPPI が止まれるようになり、障害物の前で止まったままになる場面が増えうる（滞留 3 分）。
- 帯の外が遅く、旋回の上限も比で下がる（V_slow 0.3 のとき 0.3 rad/s）。
- 開始時に作り直したマスクは run の下にあり、monitor の画面のマスクの絵（保存したもの）とは違う。
- C で止まれるようになり、コーン区間・人の場面で 0.6〜2.3 s の停止と再発進が出た（模擬）。実車の発進の遅れ（第192便：0.2〜1.4 s）が加わると、止まる時間は延びうる。
- 模擬の速度の上側は模型の仮定（倒し量 0.489 で 0.40 m/s）。表の倒し切り 1.25 m/s（PRM-39）と合わず、実車の 0.5 m/s の指令での速度は未確認。
- 出発点から最初の waypoint までは区間がなく帯もないので、V_slow 0.3 で走る（free の場面で約 27 m）。経路の作り方（最初の waypoint を出発点の近くに置く）は人の判断。
- 実車・車載 PC の実機の経路は未確認。

## 11. ブランチとコミット

- ブランチ chat/confirmation-plan-2026-11-07。実装・正本・生成物：`1676896`。作業記録・status.md・模擬の結果・試験用の写しの直し（`drive_sim_fixture.py` の skip_marks）：この後のコミット。push していない。
- 試験専用の道具（リポジトリの外）：`/private/tmp/claude-501/-Users-AYARyoya-Desktop------TsukubaChallenge/a373f789-0e60-47dc-8589-44fbbd888e46/scratchpad/abc/`（setup_abc.sh、patch_joy.py、lane.sh、guard.sh、an.py、an_pst.sh、plot.py、jobs_*.txt）。結果は各機械の `~/abc_runs/`。
