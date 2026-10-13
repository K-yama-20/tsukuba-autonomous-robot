# H-011 / H-001 再比較: Speed Filter の採用根拠、区間上限と領域上限の違い、復帰後の再適用

作成 2026-10-09。対象版: 実車PC Nav2 1.3.13（DEC-012）＝上流 jazzy commit 645abd95（package 版一致。バイナリ内の直接照合はしていない）。実行構成は本プロジェクトの案（ND-10、`generated/params/`）。

## 1. Speed Filter を採用した決定と根拠

| 項目 | 内容 |
|---|---|
| 決定 ID | **DEC-031**（2026-10-09、answered）。原文「H-001：speed filter(costmap filter)が発行。」 |
| 根拠 | 人の決定。AI の事前比較（DEC-011 の note、`docs/speed_limit_publisher.md`）は Gouda 側発行器を推奨し、Speed Filter は「折れ線区間を平面領域に塗る幾何定義が未決、境界の意味が『進入する区間の値』と一致しにくい」として非推奨だった。人が Speed Filter を選び、AI はそれに従って IFD-14/41/42 を設計した（REV-005）。 |
| 上位要求 | RQ-I020「速度上限は、Nav2標準のSpeedLimit経路を単一の発行元から適用する」、RQ-I021「SpeedLimitの発行手段（Speed Filter／Route Server／Gouda側の発行器）は…AIが提案し、人が承認する」、RQ-I010「区間（waypoint i → i+1）の属性…区間境界では、進入する区間の値を適用する」 |

## 2. 区間ごとの上限と、地図上の領域ごとの上限は別物である（確認）

- RQ-I010 の上限は **区間（進行の順序）の属性**: 「いま何番目の区間を走っているか」で決まる。
- Speed Filter の上限は **地図上の位置（mask の cell）の属性**: 「いまどの cell にいるか」で決まる（`speed_filter.cpp:195-220`）。
- 両者が一致するのは、区間の帯が互いに重ならず、同じ場所を別の区間として再訪しない場合に限る。往復・交差・重複があると静的 mask では区間ごとの異なる上限を表現できない（1 cell に 1 値）。
- 前回の推奨「地図全体に最低区間速度を敷き、帯だけ上書き」は、帯外を低速にする**運用方針の追加**であり、区間上限の要求をそのまま実現する方法ではない。本書では推奨を取り下げ、定義方法だけを示す。

## 3. 定義方法（値は tbd。Q-06・Q-07・Q-12 が未決）

| 対象 | 定義方法（案） | 値・状態 |
|---|---|---|
| 帯幅 | 区間 i の線分 W[i]→W[i+1] から法線方向に半幅 w_i の帯を mask に塗る。w_i は迂回許容範囲（Q-06・Q-07・Q-12）から決める。PRM-19 | tbd |
| 重複部分 | 1 cell に 1 値しか持てない。候補: (1) 進行方向で後の区間を優先、(2) 低い方の上限を優先、(3) 重複を禁止し生成時にエラー。どれも運用方針で、人が決める | tbd（H-011） |
| 帯外・マスク外 | 帯外（mask 内で cell=0）: SpeedFilter は `NO_SPEED_LIMIT`（0.0）を発行し controller は上限なし（controller 自身の最大速度）。マスク外（`worldToMask` 失敗）: `process()` が早期 return し **何も発行しない**＝直前に適用された上限が controller に残る（`speed_filter.cpp:198-200`） | 定義済み（Nav2 の挙動）。運用上の扱いは tbd |
| マスク未読込時 | `filter_mask_` 未受信なら 2 秒ごとに警告して return、**何も発行しない**＝controller は起動時の上限なし（`speed_filter.cpp:181-187`）。filter info 未受信でも mask を購読しないため同じ | 定義済み。Gouda は開始前に mask・filter info の latched 配信を確認する（TS-01） |
| cell 値 0 | 「速度制限なし」であり「停止」ではない（`SPEED_MASK_NO_LIMIT`→`NO_SPEED_LIMIT`） | 確認済み |
| 上限の大きさ | 6 km/h を超えてよい（人の決定。制約なし）。PRM-20 の刻み × 100 が表現できる最大値 | 確認済み |

マスク外・未読込時は「無制限になる」のではなく「発行されない」。結果として controller は**直前値（あれば）または上限なし**で走る。どちらも区間上限が効いていない状態なので、Gouda は mask 配信の有無を開始条件に入れる（IFD-42 の latched 受信確認）。

## 4. 復帰後の再適用（RQ-I069）の調査結果

| 調査項目 | 結果（根拠） |
|---|---|
| Speed Filter が載る costmap | 設定で選ぶ（`Costmap2DROS` の param `filters`、`costmap_2d_ros.cpp:124`）。local costmap は controller_server の内部 node（`controller_server.cpp:71`）、global costmap は planner_server の内部 node（`planner_server.cpp:67`）。本案では **local costmap** に載せる（controller と同じプロセス・同じ lifecycle に従うため） |
| controller_server 再起動でフィルタも再初期化されるか | **プロセス再起動／lifecycle cleanup→configure**: costmap の `on_cleanup` が `layered_costmap_.reset()`（`costmap_2d_ros.cpp:367-377`）→ フィルタは破棄・再生成され `speed_limit_prev_=NO_SPEED_LIMIT`（`speed_filter.cpp:53`）→ 次の `process()` で現在値が無制限でなければ**再発行される**。**deactivate→activate のみ**: `CostmapFilter::deactivate()`=`resetFilter()`（購読・発行器を破棄）、`activate()`=`initializeFilter()`（再作成）だが `speed_limit_prev_` は保持（`speed_filter.cpp:57-95, 262-271`）→ 同じ cell に留まると**再発行されない** |
| lifecycle_manager の bond で controller 単独再起動が起こり得るか | 既定 `bond_timeout` 4.0 s、`attempt_respawn_reconnection` true（`lifecycle_manager.cpp:44-46`）。bond が切れると `reset(true)` で**管理下の全 node を deactivate＋cleanup**（`:481-500`）、respawn timer で全 server の復帰を待ち `startup()`（configure＋activate）し直す（`:514-545`）。したがって bond 有効時は「controller 単独の再起動」にならず、全体が cleanup→configure される→フィルタは再生成される。`bond_timeout` を 0 にすると bond なしとなり単独再起動が起こり得る。nav2_bringup 既定は composition（1 コンテナ）で `use_respawn` は非 composition 時のみ（`navigation_launch.py:103-118, 133`） |
| SpeedLimit topic の QoS | 発行（SpeedFilter）`rclcpp::QoS(10)`（`speed_filter.cpp:86-87`）、購読（controller_server）`rclcpp::QoS(10)`（`controller_server.cpp:255-257`）。**transient_local なし**（volatile）。後から購読しても過去値は届かない |
| controller プラグイン側の上限保持 | RPP は `setSpeedLimit` で `params_->desired_linear_vel` を書き換える（`regulated_pure_pursuit_controller.cpp:492-507`）。deactivate→activate では保持、cleanup→configure で既定へ戻る。MPPI は optimizer に保持（`controller.cpp:124-126`） |

結論: 「同じ cell に留まったまま再起動しても再適用される」のは、**フィルタを持つ costmap が cleanup→configure される場合**（プロセス再起動、lifecycle_manager の bond による全体 reset、Gouda が明示的に cleanup→configure を行う場合）に限る。deactivate→activate だけの復帰では再適用されない。

## 5. 2 案の比較（Nav2 無改変・単一発行元）

| 観点 | (a) controller 再構成に合わせてフィルタを再初期化し現在値を再発行させる手順 | (b) Speed Filter を Gouda 側の単一発行器へ置き換える（`docs/speed_limit_publisher.md`） |
|---|---|---|
| 発行元 | Nav2 costmap の SpeedFilter（1 箇所） | gouda_mode_manager（1 箇所）。SpeedFilter は無効化 |
| 区間上限の意味 | 位置依存（領域上限）。再訪・重複で区間ごとの値を表現できない（§2） | 進行依存（区間上限）。RQ-I010 の意味に一致。Nav2 の feedback（`number_of_poses_remaining`）で区間を判定し独自の通過判定は持たない |
| **復帰後の再適用** | controller／costmap の復帰を **lifecycle cleanup→configure→activate**（deactivate→activate ではない）で行う。bond 有効なら lifecycle_manager が全体 reset で同じ効果。同じ cell に留まっていても、再生成後の最初の `process()` で現在値が発行される（現在値が「無制限」なら発行されないが、それは上限なしで正しい）。Gouda は復帰後に mask・filter info の latched 配信と `speed_limit` の到着を確認してから motion_hold を解除する | Gouda が controller の `transition_event`（activate）を購読して現在区間の上限を再発行。発行器を `transient_local keep_last 1` にすれば controller が後から購読しても最新値を受け取る。同じ cell／区間に留まっていても再発行できる |
| mask 未読込・マスク外 | 発行なし→上限なし／直前値（§3）。開始前の配信確認が必須 | 該当なし（mask を使わない） |
| 帯幅・重複の幾何定義 | 必要（PRM-19、重複規則）。Q-06/07/12 待ち | 不要 |
| 境界の意味 | mask の cell 境界で切り替わる（境界の位置は帯の塗り方次第） | waypoint 通過（Nav2 の RemovePassedGoals、PRM-11）で切り替わる＝RQ-I010 の「進入する区間」 |
| 実装負担 | mask・filter info の生成器（ND-02）、Nav2 の filter info server・mask 用 map_server の起動、復帰手順の作り込み | 発行器（ND-03 内）と feedback の監視。Gouda 独自コードが増える（RQ-I057 との関係は「Nav2 に含まれる機能」ではないため抵触しないと読むが、人の確認が要る） |
| 上位要求との関係 | RQ-I020 を満たす。RQ-I010 は帯が重ならない場合に限り満たす | RQ-I020・RQ-I010 を満たす。RQ-I021 の「人が承認」が必要 |
| TS-06 合格条件「同じ cell に留まったまま再起動しても現在の上限が controller へ再適用される」 | cleanup→configure を伴う復帰で合格。deactivate→activate のみでは不合格 | 合格（transition_event での再発行） |

「既存の発行元に再送器を追加する」案（SpeedFilter＋Gouda 再送）は単一発行元（RQ-I020）に反するため比較から除外した。最終判断は人（H-011 の承認は本比較を見てから）。

## 6. 本案に入れた変更

- TR-13（自律走行中の自動復帰）の controller／costmap 復帰は lifecycle **cleanup→configure→activate** とし、復帰後に `speed_limit` の再発行（または mask・filter info の latched 配信）を確認してから motion_hold を解除する（案 (a) の手順。(b) に変わればこの手順は不要）。
- TS-06 に合格条件「同じ cell に留まったまま再起動しても、現在の上限が controller へ再適用されること」を追加。
- 推奨「帯外に最低速度を敷く」は取り下げ、H-011 は定義方法のみ。
