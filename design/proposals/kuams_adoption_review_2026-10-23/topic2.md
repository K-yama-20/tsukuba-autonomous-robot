# トピック 2：waypoint を区間ごとに送り、失敗した区間だけを自動で送り直すか

状態：分析（提案）。実装・設定の変更はしていない（DEC-106）。読んだもの：gouda の作業ツリー（HEAD `31a6e1d` ＋未コミット 231 件、第146便まで）、
KUAMS の写し（waypoint_manager@7671afa、kuams@750934a）、上流 Nav2 1.3.13 のソース（下の【出典】）。規則の原文は AI は読んでいない（**原本未照合**。規則の中身は人の発言 DEC-339・DEC-345 による）。
KUAMS の本番の設定は公開されておらず、写しは本番の約 2 か月前のもの。

【出典の略号】
- `N/` ＝ 上流 Nav2 1.3.13 の写し `/private/tmp/claude-501/-Users-AYARyoya-Desktop------TsukubaChallenge/a668aa83-a964-4524-b73d-0fadd4db972f/scratchpad/research_c/nav2_1313/`（`nav2_bt_navigator/package.xml` の version が 1.3.13）。一部はリポジトリの `design/research/upstream_jazzy/`（`U/`）にもある
- `K/` ＝ `/private/tmp/claude-501/-Users-AYARyoya-Desktop------TsukubaChallenge/907b342e-7b82-468e-ae6d-8443c1e4af9a/scratchpad/kuams_src/`
- `G/` ＝ `/Users/AYARyoya/Desktop/自己学習/TsukubaChallenge/tsukuba-autonomous-robot/`

## 1. 問い

全 waypoint を 1 つの NavigateThroughPoses で送る今の形（RemovePassedGoals 0.7 m、外側の RecoveryNode の回数 PRM-18＝9999999、BT が失敗したら TR-07 で待機）をやめて、
waypoint 1 つずつ（KUAMS）か、`kind: stop` で区切った区間ごとに送り、失敗した区間（または waypoint）だけを自動で送り直す形にするか。

## 2. gouda の現状

【事実】動き
- goal は 1 つ。残りの waypoint を全部 1 つの NavigateThroughPoses に入れる（`G/gouda_core/gouda_core/autonomy_client.py:272-290`、`autonomy_core.py:125-127`）。
- BT は上流の `navigate_through_poses_w_replanning_and_recovery.xml` に 3 つの値だけを入れたもの（`nav2_config.py:251-263`）：外側の回数 PRM-18＝9999999、RemovePassedGoals の radius PRM-11＝0.7 m、経路の引き直し PRM-103＝1 Hz（`design/generated/params/bt_params.yaml:5-7`）。
- goal の結果（`mode_manager_node.py:500-515`）：成功 → TR-08（最後の waypoint、待機）。取り消し → 記録だけ。それ以外（ABORTED）→ **TR-07 plan_failure で待機**（`mode_core.py:190-195`）。
- 送り直しの仕組みはすでにある：TR-10（人の再開）で、フィードバックから計算した「まだ通過していない最初の waypoint」（`autonomy_core.py:135-137`、`mode_manager_node.py:488-498`）から goal を出し直す（`mode_manager_node.py:371-387`。ND-07 が正常でなければ拒否）。**自動で出す契機がないだけ**。
- waypoint の `kind`（pass／stop）は保存されているが（`waypoints.py:43`）、`resolve_mission` で Mission に渡すときに落ちる（`autonomy_core.py:100` は `(x, y, yaw)` だけ）。
- 実際に起きた中止：VM で 1 回、`status 6`・`error_code 0` で TR-07。bt_navigator のログは「Timed out while waiting for action server to acknowledge goal request for compute_path_through_poses」→「Goal failed」。人の再開で最後まで走った。再現していない（`design/reports/worklog/2026-10-21_rev134_plan_c_driving_nav2.md:44-48`、未解決）。

【事実】関係する pending の判断（中身は繰り返さず参照）
- DEC-305（自動の待機は TR-08 だけ）、DEC-307（Nav2 の失敗では待機せず、現在地から残りへ goal を出し直し続ける。回数の上限なし）、DEC-310（「最後に 1 m 進んでから」の時間で段階を上げる。段 3 は waypoint を飛ばす）、
  DEC-343（`kind: stop` までの区切りごとに goal を出し、成功したら `rule_stop_hold` で人の「横断を始める」を待つ）、DEC-344（stop は飛ばさない、段 3 は確認走行区間の外だけ）、DEC-314（各段の時間の実測）。
- 提案 `design/proposals/state_transition_redesign_2026-10-23.md` §2・§4 は、**区間ごとの goal（B）と `goal_retry` をすでに提案している**。本稿はその上に、Nav2 の中止の原因ごとの分析と、送り直しの作りの詳細を足す。

## 3. KUAMS がしていたこと

【事実】コードで確かめたこと
- `waypoint_navigator.cpp:32` NavigateToPose のクライアント。waypoint を 1 つずつ送る（`:110-148`）。
- 結果が ABORTED なら同じ waypoint をすぐ送り直す（`:132-135` → `ToSameWaypoint()` `:217-221`）。**回数の上限も待ち時間もない**。SUCCEEDED なら次の waypoint（`:127-130`、`:205-215`）。
- 取り消しの理由が "Next" なら次へ進む（`:137-140`、`:198-203`）。skip_server がこれを使う（`waypoint_function_example_server/src/skip_server.cpp:22, 96-99`。トピック 3）。
- action server が 10 s 見つからないと、送らずに戻る（`:112-116`）。そのあとの再試行はない（そこで止まる）。
- BT（`kuams/kuams_navigation/behavior_trees/navigate_to_pose_w_replanning_and_recovery.xml`）：外側の RecoveryNode は 6 回（`:8`）。**回復の前に「回復が効く失敗か」を確かめる条件がない**（`:26-39`）。経路の引き直しは 1 Hz（`:10`）。
- `kuams_navigation/config/params_nav2.yaml`：MPPI（`:76`、vx_max 0.8、wz_max 0.3）。goal checker は stateful、xy 0.50 m・yaw 1.00 rad（`:69-73`）。progress checker 0.5 m／5 s（`:65-68`）。NavFn tolerance 0.5、A*、allow_unknown（`:272-275`）。SpeedFilter はない。
- README は ROS 2 Humble（`kuams/README.md:40`）。

【推測】
- KUAMS の実質は「BT の中で何でも 6 回回復 → 中止 → 送り直しで BT を初めからやり直す」の繰り返し。つまり上限のない回復は、gouda の PRM-18＝9999999 と同じ向き。違いは、**どんな失敗でも回復か送り直しに入る**こと（gouda の Jazzy の BT は、回復が効かないと判断した失敗で中止する。§4.1）。
- サンプルの waypoint（`map_divider/data/indoor_outdoor_wp.csv`、23 点）の間隔は中央値 6.0 m（本番のものではない）。goal checker の広い許容（0.5 m・1 rad）と MPPI で、waypoint ごとの止まりを小さくしていたと推測する。本番の間隔は不明。

【前提の違い】
| | KUAMS | gouda |
|---|---|---|
| ROS／Nav2 | Humble | Jazzy 1.3.13（BT に回復の可否の条件がある） |
| 制御器 | MPPI、goal の向き 1.0 rad | RPP（上流の既定のまま：近づくと 0.6 m から減速、goal の向きへその場で回る） |
| goal checker | 0.5 m・1.0 rad | 上流の雛形 0.25 m・0.25 rad |
| 速度上限 | なし（参照なし） | SpeedFilter（位置で決まる。goal の形とは無関係） |
| 停止線 | waypoint の機能（pause 等、トピック 4） | `kind: stop`（DEC-332・343） |
| 方針 | 任意課題をすべて飛ばして 2200 m | 必達は 2.2 km の完走（intent.md 2 行）、「waypoint の通過・到達の判定は Nav2」（intent.md 15 行）、「Navigation の実行主体は Nav2。Gouda 側で二重に実行しない」（intent.md 26 行） |

## 4. 分析と選択肢

### 4.1 Nav2 1.3.13 で、回数 9999999 でも NavigateThroughPoses が中止になる場合【事実】

外側の RecoveryNode の回復の枝は `Sequence(Fallback(WouldAControllerRecoveryHelp, WouldAPlannerRecoveryHelp), RoundRobin…)`（`U/nav2_bt_navigator/behavior_trees/navigate_through_poses_w_replanning_and_recovery.xml:32-49`）。
条件が両方とも失敗すると枝が失敗し、RecoveryNode は回数に関係なく失敗を返す（`N/nav2_behavior_tree/plugins/control/recovery_node.cpp:105-107`）。回復が効くとみなす符号は：
- 制御：UNKNOWN 100・PATIENCE_EXCEEDED 104・FAILED_TO_MAKE_PROGRESS 105・NO_VALID_CONTROL 106（`N/.../would_a_controller_recovery_help_condition.cpp:26-30`）
- 計画：UNKNOWN 300・TIMEOUT 307・NO_VALID_PATH 308（`would_a_planner_recovery_help_condition.cpp:26-32`）

したがって次で**すぐ中止**する（9999999 は効かない）：
| 原因 | 符号 | 出所 | 送り直しで直るか |
|---|---|---|---|
| BT の action ノードが server の受け付けを待ちきれない | 更新されない（0 のまま） | `N/nav2_behavior_tree/include/nav2_behavior_tree/bt_action_node.hpp:227-233` | **直る**（一時的。VM で実際に起きた件） |
| costmap が時間内に更新されない | CONTROLLER_TIMED_OUT 107 | `U/nav2_controller/src/controller_server.cpp:526-530`（0.3 s） | 直る（更新が戻れば）。今は観測源に expected_update_rate がないので起きにくい（第134便） |
| ロボットの姿勢の TF が引けない | TF_ERROR 102／302 | controller・planner | 直る（TF が戻れば）。【推測】LiDAR の途切れで GLIM が止まると odom→base_link・map→odom が止まり（`global_localization_node.py:20-21`）、これになりうる。未観測 |
| 現在地が地図の外 | START_OUTSIDE_MAP 303 | `N/nav2_navfn_planner/src/navfn_planner.cpp:143-147` | 直らない（推定の飛び。トピック 1 の扱い） |
| waypoint が地図の外・経路が空・waypoint なし・plugin 名 | 304・103・309・301・101 | | 直らない（データ・設定の誤り） |

次は回復の対象なので、**中止されずに BT の中で回復を延々と繰り返す**（その場で止まって clear → spin → wait 5 s → backup）：NO_VALID_PATH（塞がり）、FAILED_TO_MAKE_PROGRESS（progress checker 0.5 m／10 s）、PATIENCE_EXCEEDED、NO_VALID_CONTROL。
送り直しをしても同じ goal なので同じ所で同じことが起きる。**3 分の滞留を防ぐのは送り直しではなく DEC-310 の段階**（トピック 3・5）。

### 4.2 全経路を 1 つの goal にしていることの、ほかの弱点【事実と推測】
- 【事実】経路の引き直し（1 Hz）のたびに、残りの waypoint の区間を全部 NavFn で計画してつなぐ（`U/nav2_planner/src/planner_server.cpp:413-436`）。1 つでも計画できない区間があると全体が NO_VALID_PATH になる。NavFn は区間ごとに costmap 全体を写す（`N/nav2_navfn_planner/src/navfn_planner.cpp:251`、costmap の mutex を持ったまま）。
- 【推測】2.2 km の地図（0.1 m 格子、PRM-33）で残りが数十〜百を超える waypoint だと、1 回の計画が重く、遠くの区間の不具合が目の前の走行を止めうる。計画の時間は未計測（§7 M-2）。
- 【事実】停止線で止まれない：goal の途中の waypoint では Nav2 は止まらない（goal checker は経路の終わりだけを見る、`controller_server.cpp:635`）。DEC-332（決定済み）の「waypoint の属性で止まる」には、区切りの goal が要る。

### 4.3 waypoint ごと（C）にしたときの振る舞い【事実と推測】
- 【事実】goal の終わりでは RPP が 0.6 m 手前から 0.05 m/s まで減速する（`N/nav2_regulated_pure_pursuit_controller/src/parameter_handler.cpp:57-60`、`regulated_pure_pursuit_controller.cpp:477-479`）。xy 許容に入るとその場で waypoint の向きへ回る（use_rotate_to_heading 既定 true、`regulated_pure_pursuit_controller.cpp:319-337`）。到達で速度 0 を出す（`controller_server.cpp:554`）。
- 【推測】waypoint ごとに「減速 → 止まる → 向きを合わせる → 計画 → 加速」になる。1 点あたりの損失は未計測。間隔が短いほど 100 分の制限時間を食う。waypoint の向きが雑だと毎回その場で回る（トピック 6 の道具の質に強く依存）。
- 【事実】到達には goal checker の許容（0.25 m）に入る必要がある。今の通過の判定は 0.7 m（PRM-11）なので、避けて通ったときに「戻って取りに行く」動きが C ではもっと起きやすい。広げると停止線の位置の精度（DEC-346）と競合する。
- SpeedFilter は位置で決まり goal の形と無関係なので、どの案でも変わらない。ただし区間を新しく出すたびに motion_hold の解除（DEC-056、`mode_manager_node.py:525-532`）を通る作りなら、解除までの間ロボットが待つ（短いと推測。`limit_since_start` は Nav2 の開始でしか消えない、`autonomy_client.py:262`）。

### 4.4 選択肢

| 案 | 中身 | 長所 | 短所 |
|---|---|---|---|
| A | 全経路を 1 つのまま、中止したら残り全部を自動で送り直す（DEC-307 そのまま） | 変更が最小（TR-10 の仕組みを自動で呼ぶだけ） | 停止線で止まれない（DEC-332 と両立しない）。計画が重い・遠くの区間の失敗が全体を止める弱点が残る |
| **B（推奨）** | `kind: stop` で区切った区間ごとに NavigateThroughPoses（DEC-343）。中止したら、**今の区間の残りだけ**を自動で送り直す。stop を越えて送らない | 停止線で止まれる。区間の中は今と同じく止まらずに走る。計画の範囲が区間に限られる。送り直しの範囲が明確 | 区間の数が少ない（stop が少ない）と A と同じ重さが残る（M-2 で確かめ、必要なら区間の長さの上限を足す：§4.5） |
| C | waypoint ごとに NavigateToPose（KUAMS） | 1 点ずつの機能（skip・待ち）を作りやすい。計画が軽い | 各 waypoint で止まる・回る（§4.3）。到達の判定が厳しい。BT を NavigateToPose 用に別に作る（gouda の BT の作りが二つになる）。RemovePassedGoals の意味がなくなる |
| D | 取り入れない（今のまま TR-07 で待機） | 変更なし | 待機＝走行失敗（intent.md 1 行、DEC-304）。一時的な中止（§4.1 の上 3 行）でも人の再開が要り、それは規則上許されない（DEC-345） |
| E（B に足す案） | BT の外側の回復の条件に、上流の `AreErrorCodesPresent`（1.3.13 にある、`N/nav2_behavior_tree/plugins/condition/are_error_codes_present_condition.cpp`）で 107・102 などを足し、Wait だけで待つ | 中止せず BT の中で待てる。Nav2 本体は改変しない | `nav2_config.py` の「上流の BT に値を入れるだけ」をやめることになる。符号 0（受け付けの時間切れ）は条件で拾えない。見えにくい（デバッグ性） |

推奨：**B ＋ 送り直し（下の作り）**。E は B の後、M-3 の結果で必要なら検討。C は取り入れない（KUAMS の利点の本体は「止まらずにやり直す」ことで、waypoint ごとに送ることそのものではない。gouda の B で同じ利点が得られ、止まり・回りの損失がない）。

### 4.5 送り直しと段階の作り（B の詳細、案）
1. 区間：`kind: stop` の waypoint（と最後の waypoint）で終わる。区間の goal が成功 → 終わりが stop なら `rule_stop_hold`（DEC-343）、最後なら TR-08。
2. 中止（ABORTED）のとき（`goal_retry`）：
   - 旧 goal の終了を確かめてから（intent.md 17 行の順序。今の `_result` は古い handle を無視する：`autonomy_client.py:298-300`）、**今の区間の、まだ通過していない最初の waypoint から区間の終わりまで**を出し直す。区間の外へは出さない。
   - ND-07 が正常でないときは出し直さず、`localization_wait`（トピック 1、DEC-342）に任せる（TR-10 の守りと同じ：`mode_manager_node.py:379-381`）。START_OUTSIDE_MAP・TF_ERROR は推定の異常の疑いとして記録する。
   - 出し直しの間に最小の間隔 `T_retry`（tbd）を置き、受け付けからすぐ中止される繰り返しは回数を数えて目立つ形で記録する（KUAMS には間隔がない）。回数の上限は置かない（DEC-307）。50 回ごとに理由を記録（G-RECOVERY-COUNT）。
   - 直らない符号（§4.1 の表の下 2 行）でも待機には入らない（DEC-305）。ただし出し直しを続けても進めないので、段階の上げ（次の 3.）に任せる。
3. 進めないとき（中止の有無に関係なく）：DEC-310 の「最後に 1 m 進んでからの時間」で段階を上げる。PRM-18＝9999999 では塞がりの多くは中止にならない（§4.1）ので、**送り直しの回数ではなく、進んだ距離と時間で判断する**。段 3（waypoint を飛ばす）は DEC-344 の制限つき（stop は飛ばさない）。確認走行区間では段の時間を 3 分より十分短く（値は DEC-314）。
4. 区間の長さの上限（M-2 の結果しだい）：stop の間が長く計画が重いなら、区間の中を「先の K 点だけを goal に入れ、通過に合わせて同じ action を新しい goal で置き換える」形にする（K は tbd）。今は推奨しない（計測の前に作りを増やさない）。
5. 記録：中止の status・error_code・error_msg・区間・offset・出し直しの回数・時刻。monitor に `processing_state` と回数を出す（提案 §1 の 5）。

## 5. 振る舞いの違いと影響を受ける ID

| 場面 | 今 | B |
|---|---|---|
| Nav2 の一時的な中止（符号 0・107・102） | 待機（TR-07）。人の再開が要る | `T_retry` の後、今の区間の残りを自動で出し直して走る |
| 塞がり（NO_VALID_PATH など） | BT の中で回復を延々（中止しない） | 同じ。加えて DEC-310 の段階 |
| `kind: stop` | 何もしない（通り過ぎる） | 区間の goal が成功して止まり、人の「横断を始める」を待つ |
| 途中の waypoint | 止まらない | 区間の中は止まらない（今と同じ）。区間の切れ目だけ止まる |
| 再開（TR-10） | 残り全部 | 今の区間の残り（`rule_stop_hold` 中なら次の区間は人の操作で） |
| 計画の範囲 | 残りの全経路（1 Hz） | 今の区間だけ |

影響を受ける ID：TR-07（plan_failure をなくす／`goal_retry`）、TR-08（最後の区間の成功だけ）、TR-10、新しい段階 `goal_retry`・`rule_stop_hold`、ND-03（mode_manager）、ND-10（Nav2。B では BT は変えない。E なら変える）、IFD-13（goal の中身）、IFD-01（`current_section`・`remaining_waypoints`・`processing_state` の意味）、IFD-04（横断の操作）、IFD-41（waypoint の kind）、RQ-I014・RQ-I067（再開の位置）、RQ-I091（intent.md 16 行の後継）、PRM-11・PRM-18・PRM-103、G-RECOVERY-COUNT、DEC-305・307・310・314・343・344・346。

## 6. ハザードと安全上の根拠（重大なものは警告の有無にかかわらず挙げる）

- **推定がずれたままの出し直し**：誤った姿勢から計画し直すと、コースを外れる・車道に入る（失敗）。ND-07 が正常のときだけ出し直す。ただし「正常」でもずれはありうる（推定の正常の判定の限界。トピック 1）。
- **出し直しの空回り**：すぐ中止される符号で出し直しが連続し、ログ・CPU を食う（KUAMS の作り）。`T_retry` と連続回数の記録で抑える。
- **届かない waypoint での滞留**：waypoint の上に人・コースが立ち続けると、送り直しても同じ所で回復を繰り返す。確認走行区間では 3 分で失敗。DEC-310 の段階が要る（トピック 3）。
- **戻る動き**：避けて waypoint から 0.7 m 以上離れて通ると、その waypoint が残り、経路が後ろへ戻る。出し直しの offset も「通過していない最初の waypoint」なので同じく戻る。後ろの waypoint を捨てる判断は飛ばし（トピック 3）と同じ扱いで承認事項。
- **停止線を越える出し直し**：区間の外へ出さないことで作りで防ぐ。stop の waypoint が届かない場合も飛ばさない（DEC-344）。その場合は人の介入が要るが、それは規則上失敗（DEC-345）。
- **PC の出力の中立は車体全体の停止の保証ではない**（CLAUDE.md 1.5）：`rule_stop_hold`・出し直しの間の停止は motion_hold と Nav2 の速度 0 による。ESP32 で優先される手動操作、ESP32・駆動系の故障、慣性・斜面で動きうる。停止線での止まりの距離は未計測（DEC-346）。
- **受信途絶の watchdog（PRM-13）は誤った指令を検出しない**：誤った offset・誤った区間の goal、古い時刻の goal は検出できない。goal の中身（offset・区間・poses の数）を毎回記録して後から確かめられるようにする。
- 自動の待機がなくなるので、異常の間も自律走行のまま動き続ける（DEC-305 の前提）。止める手段は人の待機・終了・ゲームパッドで、本番ではどれも失敗になる（DEC-345）。
- 「設計検査 違反 0」は安全の証明ではない。「実車投入可能」は人の判断待ち。

## 7. 実測が要る値と計測の手順（案）

| 番号 | 値 | 誰が・何を | 合否の基準の案 |
|---|---|---|---|
| M-1 | `T_retry`（出し直しの最小の間隔）と、受け付けの時間切れの起き方 | AI：VM で負荷（load 2〜4）をかけて stack 試験を繰り返し、bt_navigator のログと中止の符号を集める。値は人が決める | 一時的な中止のあと、出し直しで走りに戻ること。空回り（1 s 未満の中止の連続）が起きないこと。値は tbd |
| M-2 | 全経路と区間ごとの、1 回の計画の時間と CPU | AI：VM で本番の地図・waypoint を使い、`/plan` の発行の間隔と planner_server の CPU を記録（全経路／区間ごと）。人は地図と waypoint を用意 | 区間ごとの計画が 1 Hz（PRM-103）の周期より十分短いこと（基準は人が決める）。超えるなら §4.5 の 4 |
| M-3 | LiDAR の途切れのときに Nav2 が返す符号（TF_ERROR か、回復か） | AI：rosbag の再生で点群を 3〜4 s 止める故障を入れ、Nav2 の結果を記録（DEC-354 と同じ基盤） | 結果を記録するだけ（E を採るかの材料） |
| M-4 | stop の waypoint で止まる位置のずれ | DEC-346 のまま（人が実車で） | 規則の指定の領域に入ること |
| M-5 | （C を検討する場合だけ）waypoint 1 点あたりの止まり・回りの時間 | 人が実車、または AI が VM で | 推奨は C を採らないので、今は計測しない |

## 8. 分類と、決まらない場合に止まる作業

| 項目 | 分類 | 台帳 | 決まらないと止まる作業 |
|---|---|---|---|
| 区間ごとの goal（B）と `rule_stop_hold` | 承認 | DEC-343（pending） | 横断歩道の一時停止の実装、区間の送り直し |
| 中止で待機せず、今の区間の残りを自動で出し直す（DEC-307 を区間に絞る。§4.5 の 2） | 承認 | DEC-307 の変更として新しい項目（未登録） | 自動の出し直しの実装 |
| 進めないときの判断を、送り直しの回数でなく距離と時間で行う | 承認 | DEC-310・DEC-344 に付記 | 段階の実装 |
| `T_retry`、区間の長さの上限 K | 実測（M-1・M-2）→ 人が決める | 新しい項目（未登録） | 値は tbd のまま。実装は既定値なしで止まる |
| BT の条件の追加（E） | 承認（Nav2 の振る舞いと `nav2_config.py` の約束を変える） | 未登録 | E だけ。B は進められる |
| 区間の index・残りの数の計算、記録の項目、Mission に kind を渡す | 自律判断（B の承認の範囲内） | — | — |
| waypoint ごとの送り（C） | 承認（推奨は採らない） | — | — |

## 9. 他のトピックとの依存

- トピック 1（推定不能で止まらない）：出し直しは ND-07 が正常のときだけ。START_OUTSIDE_MAP・TF_ERROR の中止は `localization_wait` へ渡す。M-3 は DEC-354 の故障入れと同じ基盤。
- トピック 3（skip の条件）：塞がりは送り直しでは直らない。飛ばすのは区間の中の pass の waypoint だけで、区間の残りから外して同じ区間を出し直す形にできる（B なら作りやすい）。後ろの waypoint を捨てる判断もここ。
- トピック 4（信号待ちの待機列か手動横断か）：区間の切れ目＝`kind: stop` の位置と、そこでの待ち方。B はその前提。
- トピック 5（速度・旋回の上限と collision_monitor）：区間の終わりの減速・その場の回り（RPP の既定値）、`T_retry` の間の停止。
- トピック 6（GLIM の軌跡から waypoint を作る道具）：waypoint の向き・間隔・`kind: stop` の付け方。C を採るなら影響が大きく、B なら区間の切れ目の向きだけが効く。

## 10. 実装するなら変える範囲（見積り、コードは書かない）

- `gouda_core/gouda_core/autonomy_core.py`：Mission に kind を持たせる、区間の分け方・区間の goal の poses・区間の中の index の計算（数十行）。
- `gouda_core/gouda_core/autonomy_client.py`：`send_goal` を「区間の offset から区間の終わりまで」にする（十数行）。
- `gouda_core/gouda_core/mode_manager_node.py`：結果の分岐（区間の成功 → `rule_stop_hold`／次の区間／TR-08、中止 → `goal_retry`）、`T_retry` のタイマー、回数と理由の記録、横断の操作の受け口（百〜二百行）。`mode_core.py`：段階の名前と遷移（数十行）。
- monitor（`gouda_gui`・web）：段階・回数の表示、「横断を始める」ボタン（DEC-343）。
- `nav2_config.py`：B では変えない（E のときだけ BT の作りを変える）。
- 試験：単体（区間の分け方、出し直しの範囲が stop を越えないこと、符号の分類）、VM の stack 試験（`gouda_core/test/stack.sh`）で中止を入れて自動で戻ること。
- 設計：`model.yaml` の TR-07・TR-08・TR-10・段階（ST）・IFD-01／13 の改訂（change set → apply_revision → run_checks）。規模は中（DEC-343 と DEC-307 の実装をまとめて 1 便〜2 便）。
