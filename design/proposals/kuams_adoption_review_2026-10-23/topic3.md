# トピック 3：waypoint の skip 条件（KUAMS の skip_server 相当）

- 読んだ時点：gouda リポジトリ HEAD `31a6e1d`、それにコミットされていない作業ツリー。status.md は第146便まで。読むだけで、リポジトリには何も書いていない
- KUAMS のコード：scratchpad/kuams_src の写し（waypoint_manager@7671afa）。大会当日の設定は公開されていない
- Nav2 の上流：`design/research/upstream_jazzy/`（jazzy 645abd95）と GitHub の同じコミット

## 1. 問い

waypoint が物でふさがれて先へ進めないとき、その waypoint を諦めて次へ進む条件を gouda に入れるか。入れるなら次を決める。
- どこに入れるか
- どんな制約を付けるか（DEC-344 (2)：kind: stop は飛ばさない、確認走行区間の外だけ。DEC-310 の段 3）
- 閾値をどう測るか

## 2. gouda の現状

### 2.1 実装されている動き【事実】

- **Nav2 に送る goal**
  - 自律走行の開始のとき、offset から後の waypoint を全部、NavigateThroughPoses の 1 つの goal にして送る（`gouda_core/gouda_core/autonomy_core.py:6`、`:125-128`）
  - feedback の残りの数から「まだ通っていない最初の waypoint」を出す（`autonomy_core.py:135-137`、`mode_manager_node.py:492`）
  - waypoint を飛ばす仕組みはない
  - `kind` は pass か stop だけ（`waypoints.py:43`、`:67`）。どちらも通過の判定は Nav2 が行う（intent.md:9「waypointの通過や到達の判定はNav2が行う」）
- **BT**：上流の `navigate_through_poses_w_replanning_and_recovery.xml` に、次の 3 つの値だけを入れたもの（`nav2_config.py:250-263`）
  - RemovePassedGoals の radius＝PRM-11＝0.7 m
  - 外側の RecoveryNode の回数＝PRM-18＝9999999
  - 経路の引き直しの頻度＝PRM-103＝1 Hz
- **planner**：NavFn は上流の雛形のまま（`nav2_params.yaml:283-287`）。tolerance 0.5、allow_unknown true
- **costmap**
  - inflation＝PRM-72＝1.0 m
  - footprint＝PRM-69（前 0.55・後 0.24・幅 0.60 m）
  - 障害物を付ける距離は上流の既定 2.5 m（`nav2_params.yaml:223`・`:253`）
- **関係する pending**
  - DEC-310：滞留から抜ける段 1〜3。段 3 は「今の waypoint を飛ばして次へ」
  - DEC-344 (2)：段 3 の制限
  - DEC-313・314：窮屈な設定を緩める向きの見直しと、その実測
  - DEC-307：Nav2 が失敗したら出し直す
  - DEC-343：kind: stop ごとに区切って goal を出す
  - 提案 `proposals/state_transition_redesign_2026-10-23.md` §5（86 行）
  - KUAMS との比較の報告（`reports/KUAMSとgoudaの比較.md:152-153`）は「飛ばす条件は設計されていない」とまとめている
- **bins 121〜126**：屋内や VM で、自己位置推定の開始と Nav2 の後始末を試したもの。waypoint の上に物がある場面の記録や rosbag はない（各作業記録を検索して確かめた）
  - 推奨案 A で使う帯の段の rosbag は、人が用意するまで待ちになっている（status.md 第138便）

### 2.2 ふさがれた waypoint で Nav2 がどう動くか（上流のソースで確かめた）

**【事実】**
1. ComputePathThroughPoses は、waypoint の対ごとに計画を作ってつなぐ。1 区間でも失敗すると、全体が NO_VALID_PATH などで終わる（`upstream_jazzy/nav2_planner/src/planner_server.cpp:413-437`、`:476-479`）
   - つまり、goal を「全部まとめて」送っても、ふさがれた途中の点を Nav2 が自動で飛ばすことはない
   - NavigateToPose で 1 つずつ送る場合（KUAMS）と、止まる点では同じ
2. NavFn は、goal の格子が障害物でも、tolerance が 0 でなければ失敗しない。goal を中心に「半幅 tolerance の正方形」を探し、届く格子のうち goal に最も近いものを終点にする（navfn_planner.cpp の makePlan。https://github.com/ros-navigation/navigation2/blob/645abd95f2be02a13ca539b29c2ddc065db34f89/nav2_navfn_planner/src/navfn_planner.cpp）
   - 正方形の中に届く格子がなければ NoValidPathCouldBeFound になる
   - NavFn は、inscribed（253）と lethal（254）の格子を通れないとみなす（navfn.cpp の setCostmap、同じコミット）
3. 計画が失敗したときの BT の流れ
   - planner の RecoveryNode は、global costmap を消して 1 回だけやり直す（BT の xml 13-22 行）
   - それでも失敗すると PipelineSequence が失敗し、FollowPath も止まる
   - 外側の recovery（消去・spin・wait・backup）を PRM-18 回、実質は無限に繰り返す
   - 障害物が残る間は、その場で滞留する
4. RemovePassedGoals は、ロボットが先頭の点から radius 以内にいるときだけ、その点を消す（`remove_passed_goals_action.cpp:71-77`）。最後の点は消さない
5. 走行の終わりの判定は、計画の最後の点（`controller_server.cpp:635`）に対して行う。最後の点が代わりの点に置き換わっていれば、その点で成功になる

**【推測】**（ソースから考えたもので、試していない）
- **人が 1 人立つ、コーン 1 本**：障害物の格子と inscribed の帯を合わせると、waypoint から 0.4〜0.5 m ほどの円になる。正方形の隅（最大 0.71 m）で代わりの点が見つかり、計画は失敗しない可能性が高い
- **自転車・人の集まり・コーンの集まり**：半幅 0.5 m の外まで通れない場合は NO_VALID_PATH になり、無限の recovery に入る
  - TK-13 の、ランダムに置かれる複数の緑コーン（確認走行区間の外）が、この場面に当たりうる
- **今の設計の別の弱点（skip とは関係なく起きうる）**
  - 代わりの点は waypoint から最大 0.71 m 離れる。一方、PRM-11 は 0.7 m で、RPP は角を内側に回る
  - そのため、迂回のときに waypoint の 0.7 m 以内を通らないことがある。消えずに残った点へ、通り過ぎた後の 1 Hz の引き直しで戻る経路ができる（Uターン）
  - 実測で確かめる（§7 の M1）

## 3. KUAMS がしていたこと

### コードで確かめたこと【事実】

- **有効にする waypoint**：CSV の命令 `skip` がある waypoint だけ（その waypoint へ向かうときに有効にする）
  - `skip_server.cpp` の FunctionCallback と Update
  - 例：`waypoint_editor/data/test.yaml:14` の `skip:2`。`:2` の数値は skip_server.cpp の中では使っていない
- **判定**：次の 2 つを両方満たすと、`/nav2_cancel` に "Next" を出して Nav2 を取り消し、次の waypoint へ進む（scanCallback、executeSkip）
  - ロボットが waypoint から `dist_tolerance` 以内にいる
  - 2 次元の LaserScan の点のうち `scan_tolerance` 個以上が、waypoint から同じ `dist_tolerance` 以内にある
- **点の変換**：点は current_pose だけで map に写す。LiDAR の取り付け位置は無視している
- **持続時間**：条件を何秒続けて満たしたかは見ない。1 回の scan で発動する
- **設定**：`config_waypoint_manager.yaml:11-14` で dist 2.5 m・点 5 個（コード内の既定は 3.0 m・10 個）
- **goal の送り方**：NavigateToPose で 1 つずつ送る（`waypoint_navigator.cpp:118-145`）
  - ABORTED のときは同じ waypoint を送り直す（ToSameWaypoint）
  - CANCELED で "Next" のときだけ次へ進む

### 推測【推測】

- 半径 2.5 m の中には、歩道の壁・縁石・人がほぼいつも入る。このため、skip を付けた waypoint では、実質「2.5 m まで近づいたら通過とみなす」ゆるい通過判定として働いていたと考えられる
- 大会でどの waypoint に付けたかは分からない

### gouda との前提の違い

| 項目 | KUAMS | gouda |
|---|---|---|
| センサ | 2 次元の scan | XT-32 の 3 次元点群（＋MID-360 の予定）。点を数えるなら、高さの帯（PRM-70・71）と地面・草の扱いが要る |
| goal の送り方 | NavigateToPose で 1 つずつ。到達しないと進めないので、skip の必要が大きい | NavigateThroughPoses。RemovePassedGoals 0.7 m で、近くを通った点は消える |
| 規則（2026） | — | 滞留 3 分で失敗になるのは確認走行区間だけ（EV-25）。全体の制限時間は 100 分 |
| 方針 | — | 通過の判定は Nav2（intent.md:9）。異常のときの人の操作は失敗（DEC-345） |

## 4. 選択肢

### 推奨案 A：DEC-310 の段 3 として、costmap で確かめる「opt-in の skip」を入れる

発動の条件（すべて満たすとき）：
1. 滞留：最後に 1 m 進んでから T3 が経った（DEC-310 の時計）。かつ、Nav2 の feedback の number_of_recoveries が増えている、または ComputePathThroughPoses が失敗している
2. 今の目標：残りの数から求めた先頭の waypoint i（`autonomy_core.py:135`）
3. ふさがっている：global costmap の get_cost service（`get_cost_global_costmap`、`upstream_jazzy/nav2_costmap_2d/src/costmap_2d_ros.cpp:260`）で見た、waypoint i の footprint の cost が閾値 C 以上の状態が、T_occ 続いた
4. 近い：ロボットが waypoint i から d_near 以内にいる
5. waypoint i に、人が waypoint_manager で付けた `skip_allowed: true` がある。既定は false
   - kind: stop には付けられないことを、保存のときの検査で守る
   - 走行中にも、もう一度確かめる
6. 場所：確認走行区間の外（DEC-344 (2)）。かつ、横断歩道・待機列の区間の外
7. 回数：連続で飛ばすのは 1 点まで。1 m 進むまで、次の skip はしない
8. 自己位置推定が正常であること（トピック 1）

条件がそろったときの動き：
- i を除いた残りで、NavigateThroughPoses の goal を出し直す（トピック 2 の仕組みを使う）
- 出し直しの計画も失敗したら、skip を取り消す扱いにはせず、段 1・2 に戻る
- 発動・見送りの理由・cost・持続時間を、ログと monitor に出す（intent.md:16 の「判断と理由」）

理由：
- 生の点ではなく costmap を見るので、高さの帯・raytrace による消去・keepout・地図の静的な障害物を、Nav2 と同じ見方で扱える。「planner が通れないと見ている」ことと判定が一致し、草・反射・地面の点を別に扱う必要がない
- 人が付けた点だけを飛ばすので、角・停止線・横断歩道を飛ばさない（コースから外れる・EV-22 を構造的に防ぐ）
- 持続時間 T_occ と滞留の時計を使うので、一時的に立ち止まった人で飛ばさない

### 代替案 B：Nav2 の設定だけで「代わりの点」にする

- NavFn の tolerance を広げ、PRM-11 を「tolerance×√2＋追従のずれ」以上にそろえる。コードは変えない
- 利点：通過の判定が Nav2 のまま（intent.md:9 と合う）
- 欠点
  - tolerance は区間ごと・点ごとに変えられない。最後の goal（kind: stop）にも効くので、停止の位置がずれる（EV-22、DEC-346 (1)）
  - PRM-11 を広げると、すべての角が内側に回る。昔の 5 m を流用しない判断（DEC-016）と同じ問題になる
- PRM-11 と tolerance の不整合（§2.2 の推測）を直すことだけは、A と別に検討する価値がある

### 代替案 C：KUAMS と同じ、生の点を数える方式（r・N、即時に発動）

- 推奨しない
- 理由
  - 3 次元の点群では、高さの帯と地面の除去を自分で作り直すことになる
  - r＝2.5 m だと、歩道の壁・縁石・人で誤って飛ばしやすい
  - 持続時間がない
  - Nav2 の costmap と判定がずれる（costmap は空いているのに飛ばす、またはその逆）

### 代替案 D：上流の RemoveInCollisionGoals（BT のノード）

- 上流の main にはある（`nav2_behavior_tree/plugins/action/remove_in_collision_goals_action.cpp`、GetCosts を使う）。jazzy 645abd95 にはない（GitHub の tree で確かめた）
- 使うには、C++ の BT plugin を移植する必要がある
- 遠くの点も含めて、cost が閾値以上の点をすべて消す。点ごとの属性（stop など）を見ないので、制約を守れない
- 推奨しない

### 代替案 E：取り入れない

- DEC-310 の段 1・2 と、DEC-307 の出し直しだけにする
- 利点：コースから外れる・停止線を飛ばす危険がない
- 欠点：持続する障害物（集まったコーン、止めてある自転車）で NO_VALID_PATH が続き、どけられるまで滞留する
  - 確認走行区間の外では失敗にならないが、100 分の制限を食う
  - 動かない障害物なら完走できない（優先順位 0 と衝突）

## 5. 振る舞いの違いと、影響を受ける ID

- **A の振る舞い**
  - 今は：ふさがれた点で無限に recovery を繰り返す
  - A では：T3＋T_occ の後、opt-in の点に限って次の点へ向かう。到達していない点が記録に残る
- **影響を受ける ID**
  - 決定・要求：DEC-310・DEC-344・DEC-313・DEC-314・DEC-307・DEC-343、RQ-I011（通過の判定は Nav2）、RQ-I012
  - モデルの要素：ND-03（mode_manager）、ND-10（Nav2）、IFD-41（waypoint セットの形式）、IFD-13（goal）
  - パラメータ：PRM-11・PRM-18・PRM-72。新しい PRM（T_occ・C・d_near・連続の上限）
  - その他：G-RECOVERY、intent.md:9・:16
- **B の場合**：上の影響に加えて、PRM-11 と NavFn の tolerance（新しい PRM）が変わる
- **A・B どちらでも**：monitor の waypoint タブと、waypoint の形式の版（waypoints.py の SCHEMA）が変わる

## 6. ハザードと安全上の根拠

（警告があるかどうかに関係なく、重大なものを挙げる）

- **H1（重大）：角の点を飛ばす → コースから大きく外れる（EV-15）・車道に入る（EV-16）**
  - 計画 C（DEC-214・217）では、通った帯の外の未知の格子を、高い cost で通れるとみなしている。このため、角を飛ばした後の経路は、地図の外へ近道しうる
  - 対策
    - opt-in にする（A の 5）
    - 出し直した経路が通った帯・keepout の外へ出ないことを、出す前に確かめる（追加の条件案。承認）
- **H2（重大）：kind: stop を飛ばす → EV-22**
  - 対策：保存のときと走行中の二重の禁止。最後の goal・区切りの goal は飛ばさない
- **H3（重大）：待機列・横断中に飛ばす**
  - 前のロボットを「障害物」とみなして列を飛ばし、その横を進むおそれがある。90 秒の滞留の規則も絡む
  - 対策：その区間では無効にする（トピック 4 と一緒に決める）
- **H4：誤って飛ばす**
  - 原因の例：一時的な人、反射の残像、縁石・壁・草が近い点
  - 対策
    - costmap で判定し、T_occ の持続を条件にする
    - 壁が近すぎる点は、waypoint セットの保存のときに静的な地図の cost で警告する（新しい検査。承認）
  - 誤って飛ばしても、障害物の回避そのものは変わらない
- **H5：自己位置推定が誤っている間の判定**
  - 誤った位置で「ふさがれている」と判定し、遠くの点へ goal を出してしまう
  - 対策：推定が正常であることを条件にする（トピック 1）
- **H6：skip は安全の手段ではない**
  - 衝突を避けるのは、costmap と RPP の衝突検出だけ。collision_monitor は使っていない（RQ-I072）
  - skip で出し直すときの取り消しで PC の出力が中立になっても、車体全体が止まる保証にはならない（1.5）
- **H7：今の設計の Uターン（§2.2 の推測）**
  - 混雑の中で後ろへ戻る動きになる。skip の有無にかかわらず、M1 で確かめる
- **H8：確認走行区間で滞留すると失敗になる**
  - 区間の外だけで飛ばす（DEC-344 (2)）と、いちばん厳しい区間で段 3 が使えない。区間の中の 2 か所の横断歩道とコーンの課題（TK-50）との関係で、人の再確認が要る
  - AI は判断していない。「区間の中では段 1・2 だけ」にするのが今の提案

## 7. 実測が要る値と、計測の手順の案

担当：人が実車を操作し、障害物を置き、合否を決める。AI は手順・解析のスクリプト・設定への反映を担当する。証拠（ログ・条件・日付）のない値は確定扱いにしない。

**M1：今の設定で、ふさがれた点の上で Nav2 がどう動くか**（skip が要るかどうかを決める）
- 何をするか：直線の区間の途中の点と、角の点に、次のものを置く
  - コーン 1 本、コーン 3 本の集まり、人 1 人（立ち続ける・10 s で去る）、箱（1 m 角相当）
- 何を記録するか
  - planner のログ（"Failed to create plan with tolerance"）
  - NavigateThroughPoses の feedback（number_of_poses_remaining・number_of_recoveries）
  - 経路（/plan）、Uターンの有無、1 m 進むまでの時間
- 合否の案：Uターン 0 回。滞留が続いた場面だけを skip の対象にする

**M2：何もない走行での cost の分布**（誤って飛ばす率）
- 何をするか：コースの rosbag（人の用意待ち）を VM で再生し、global costmap を作り直す
- 何を記録するか：各 waypoint の footprint の cost の時系列（ロボットが d_near 以内にいる間）
- 合否の案：障害物を置かない走行で、C と T_occ を満たす時間が 0 回

**M3：T_occ・T3 の時間の配分**
- 何をするか：実験走行日に、waypoint の上に人が立ち止まる時間の分布をとる（rosbag ＋ 動画）
- 時間の配分（tbd）
  - 確認走行区間で使う場合は、段 1＋段 2＋段 3＋出し直しの合計が 180 s より余裕をもって短いこと（余裕の大きさは承認事項）
  - 区間の外では、100 分のうちの余裕から決める

**M4：角を飛ばしたときの経路**
- 何をするか：地図の上で、skip_allowed の各点 i について、i−1 から i+1 への計画を作る
- 何を確かめるか：通った帯・keepout から外へ出ないか
- 地図だけでできる解析（VM）。合否の案：はみ出し 0

値の状態：C、T_occ、d_near、T3、連続の上限、NavFn の tolerance（B を採る場合）は、すべて tbd。決定先は DEC-314 と、新しい実測の項目。

## 8. 分類と、決まらない場合に止まる作業

| 項目 | 分類 | 決まらない場合に止まる作業 |
|---|---|---|
| skip を入れるか（A／B／E） | 承認（運動と達成の意味が変わる。intent.md:9 との整合を人が確かめる） | skip の実装すべて |
| opt-in の属性 `skip_allowed`、stop・横断歩道・待機列での禁止 | 承認（IFD-41 の形式。安全に関わる印を付ける） | waypoint_manager と monitor の変更 |
| 確認走行区間での扱い（H8） | 承認（DEC-344 (2) の再確認） | 確認走行区間の滞留の段の設計 |
| 出し直した経路が帯の中にあるかの確認、保存のときの静的な cost の警告 | 承認（新しい検査のルール） | その検査 |
| C・T_occ・d_near・T3・連続の上限・tolerance | 実測（M1〜M4） | 値の確定。それまで skip は無効のまま |
| PRM-11 と NavFn の tolerance の不整合の確認 | 実測（M1）。直すなら承認 | Uターンの対策 |
| ログ・monitor の表示の文言、M2・M4 の解析スクリプト | 自律判断（スクリプトは基盤の作業として先に作れる。正本は変えない） | なし |

DEC-106 により、どれも人の明示の許可があるまで実装しない。

## 9. 他のトピックとの依存

- **トピック 1（推定不能で止まらない）**：推定が正常であることを skip の条件にする。推定不能の段階の間は skip しない
- **トピック 2（区間ごとに送り、失敗区間だけ再送）**：skip は「i+1 からの出し直し」なので、トピック 2 の仕組みの上に作る。トピック 2 が先
- **トピック 4（待機列か手動横断か）**：待機列・横断歩道の区間では skip を無効にする。待機列での点の数え方（KUAMS の lineup）とは、判定を別にする
- **トピック 5（速度・旋回の上限と collision_monitor）**：skip は回避を変えない。衝突の保護は、トピック 5 の結論に従う
- **トピック 6（GLIM の軌跡から waypoint の候補を作る）**：その道具の中で次を行える
  - 角（曲率の大きい点）を skip 不可として印を付ける
  - 静的な地図の cost を検査する

## 10. 実装するなら変える範囲の見積り（A の場合。コードは書かない）

- `gouda_core/gouda_core/waypoints.py`：属性 `skip_allowed`、stop との排他の検査、SCHEMA の版
- monitor：`monitor_node.py`、web の waypoint タブ（切り替えの欄、飛ばした点の表示）、AUTO の状態の表示
- `mode_core.py`・`autonomy_core.py`
  - 判定の純粋関数（条件 1〜8）
  - 出し直す offset の計算
  - 連続の上限
- `mode_manager_node.py`：get_cost の client、feedback の監視、取り消しと出し直し（トピック 2 の部品）、ログ
- `nav2_config.py`：A では変更なし（B では tolerance と PRM-11）
- 正本：revision の change set
  - ND-03・IFD-41・IFD-13 の更新
  - 新しい PRM 4〜5 件、新しい RQ、DEC-310・344 の結果
  - 生成物の再生成
- 試験：判定の単体試験（stop・区間・連続・持続時間・推定不能の境界）、VM の stack の試験
- 規模の感じ：コードは 300〜500 行、試験は 200 行程度、正本の改訂は 1 回【推測】
