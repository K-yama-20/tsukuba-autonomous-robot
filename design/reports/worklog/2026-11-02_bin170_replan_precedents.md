# 第170便 作業記録：再計画が間に合わない問題の先行事例の調査（読むだけ、実装なし）

- 日付：2026-11-02
- 読んだコミット：origin/main 8ee7162（第168便の報告を起点に分けたチャット。作業ツリーの変更は別のチャットのもので、触れていない）
- 人の発言（原文）：「再計画が間に合わない問題について、既存のOSSや先行事例、KUMASのリポジトリ調査等から、彼らの解決策を探せ。そもそもこんな問題が生じていない可能性が高い」
  - 「KUMAS」は KUAMS と解釈した
- 変更：コード・設定・正本は変えていない。VM には触れていない

## 1. 結論

- 人の見立てのとおり、KUAMS には同じ形の問題が生じにくい構成である。再計画を速くして解いているのではなく、**障害物の回避を controller（local）に任せている**
- gouda の「猶予 1.08 s に対し再計画まで最悪 2.15 s」は、RPP を選んだ（DEC-122）ために global 側に回避を負わせた結果である（推測を含む）
- 第168便で示した「周期と距離を上げる」案は、この構造を変えない対症の案である

## 2. 読んだ原文

### 2.1 KUAMS（2025 完走、kzm784/kuams@750934a、2025-10-03）

`kuams_navigation/config/params_nav2.yaml`、`behavior_trees/navigate_through_poses_w_replanning_and_recovery.xml`、`kuams_bringup/launch/utils/mid360.launch.py`、`kuams_navigation/launch/navigation.launch.py`

| 項目 | KUAMS | gouda（main） |
|---|---|---|
| controller | MPPI、20 Hz、2000×56×0.05 s（ObstaclesCritic あり） | RPP、20 Hz |
| 再計画 | RateController 0.333 Hz（3 s ごと） | 1 Hz（PRM-103） |
| global costmap の更新 | 1 Hz | 1 Hz |
| 障害物の印 | global 2.5 m・消去 3.0 m。local は指定なし（既定 2.5／3.0 m） | 2.5／3.0 m |
| local costmap | 10 Hz、8×8 m、LaserScan の ObstacleLayer | 5 Hz、3×3 m |
| 最高速度 | vx 0.8 m/s、wz 0.3 rad/s | 1.25 m/s、1.0 rad/s |
| failure_tolerance／進みの監視 | 0.1 s／0.5 m・5 s | 0.3 s／0.5 m・10 s |
| 減速・停止 | collision_monitor（PolygonStop、FootprintApproach 2 s） | なし（RQ-I072） |
| LaserScan | pointcloud_to_laserscan、range_min 0.45、range_max 30.0、use_inf true。costmap に inf_is_valid の記載なし | range_max 未指定（第168便。第169便で修正中）、inf_is_valid true |

- 読み方：再計画は gouda より遅く、global の更新・印の距離は同じ。それでも 2200 m を完走している。差は controller、local costmap、速度、collision_monitor
- 注意：この commit が本走行の設定と同じかは未確認。完走の要因を MPPI だけに帰せない（0.8 m/s と collision_monitor も効いている）

### 2.2 Nav2 の上流

- `nav2_regulated_pure_pursuit_controller/README.md`（jazzy）40 行：pure pursuit は動く障害物を考慮しない。経路を作る planner と組で使うものと書かれている
- 同 48・62 行：RPP の衝突の検査は止めるためのもの。検査の距離は lookahead まで
- `design/research/upstream_jazzy/nav2_bringup/params/nav2_params.yaml`：Jazzy の既定の controller は MPPI。BT の再計画は 0.333 Hz、global 1 Hz、local 5 Hz・3 m
- つまり上流の既定値は「遅い global ＋ 避ける local」の組である。gouda は local だけ RPP に替え、残りをこの組のまま受け継いだ（読み取り）
- `nav2_mppi_controller/README.md`：4 世代 i5 で 50 Hz 以上（11 行、上流の記載。実車 PC では未測定）。time_steps×model_dt×vx_max が costmap の半分を超えると速度が頭打ちになる（348 行）。計算：2.8 s×1.25 m/s＝3.5 m なので local は 8 m 程度が要る（3 m のままでは足りない）
- `nav2_mppi_controller/src/controller.cpp` 124 行：setSpeedLimit あり（SpeedFilter を使える）
- `navigate_w_replanning_only_if_path_becomes_invalid.xml`（jazzy）：IsPathValid で経路が無効になったときだけ引き直す BT が上流にある

### 2.3 他チーム（TC2025 の結果は `research_notes/tc2025_他チーム公開コード/本走行結果_2025.csv`）

| チーム | 距離 | 追従・回避 | 出典 |
|---|---|---|---|
| Arcanain | 250 m | 独自の pure pursuit ＋ DWA | 調査の記録（crosscut、group1）。今回は読み直していない |
| TERABO | 200 m | DWB、0.45 m/s。RPP の設定がコメントアウトで残る | terabo-navigation@0ff2f7e（tsukuba2025）nav2_params_scan2d.yaml |
| SICK wagen | 700 m | DWB、0.6 m/s、10 Hz、local 6 m・印 6 m | sick_wagen_workspace2@af60196 nav2_params.yaml |
| Orange papa／go | 650／50 m | DWB、1.6 m/s、5 Hz、local 10 Hz、global の印 10 m | orange2025@9962dfc（2026-05 の commit。本走行と同じかは不明） |
| k2 | 1000 m | pure pursuit ＋ 独自の回避経路の node（d2_controller@45da721）、TEB も依存に含む | ヘッダの先頭と調査の記録だけ。中身は未読 |

- 読んだ範囲で、RPP だけで global の再計画に回避を任せるチームは見つからなかった。網羅ではない（gh のコード検索は結果を取れなかった）
- **完走 7 チームのうち、走行の設定を確かめられたのは KUAMS だけ**（UNITE・Voyager・Ruby は未発見、Mercury・fuGoW・Kerberos は部品のみ）。DWB・pure pursuit＋DWA のチームは完走していないが、原因は別と思われ、controller の優劣の証拠にはならない

## 3. 過去の記録との関係

- DEC-122（2026-10-17）：代替案に MPPI を明記して RPP を人が承認。提案の理由は「計算が軽く説明しやすい」「MPPI は CPU を使う」（`proposals/stage56_navigation_localization_plan.md`）
- 第138便 §：「置かれた障害物を素早く避ける力はほぼない」と既に記している
- `proposals/kuams_adoption_review_2026-10-23/topic5.md`：S-C（MPPI に替える）は「CPU 未測定、やり直し、本番前には勧めない」。当時の前提は VM。x86 の PC への移行で前提が変わった可能性がある（人の話、未確認）
- 第164便の優先の案 B-1・B-2（failure_tolerance・進みの監視を緩める）：KUAMS はむしろ厳しい値で完走している。緩める必要性は読み直しが要る
- 第168便 §1.5 の表と第6節の候補 2：対症の案に格下げする

## 4. 承認の候補（DEC にはまだしていない。人の指示待ち）

1. DEC-122 の見直し：controller を MPPI に替える試験を行うか。推奨：行う。RPP を切り戻し先に残す。代替：RPP のまま周期と距離を上げる（第168便の表）。影響：ND-10、PRM-66・67、PRM-124（local 8 m 程度）、PRM-114〜123（RPP の値は使われなくなる）、DEC-371。決まらない場合に止まる作業：回避の評価
2. 速度：まず 0.8 m/s で試すか（KUAMS の値。推奨）。PRM-66 は変えず、試験の値か速度マスクで下げる
3. 減速・停止の層：DEC-372（collision_monitor）。MPPI は止まる保証をしない。KUAMS は collision_monitor と組にしている。RQ-I072 との関係は人の判断

## 5. 残るリスク・未確認

- MPPI の CPU は実車の PC で未測定（DEC 候補の前に測れる）
- gouda の DAC は開ループで、エンコーダがない。指令と実速度のずれが MPPI の予測を悪くする恐れ（推測）。KUAMS の台車（WHILL）とは条件が違う
- wz の上限：KUAMS の 0.3 rad/s をそのまま使うと gouda の waypoint で曲がれるかは未確認
- MPPI は経路から離れるので、keepout は costmap に入っていることが前提。第157便の local の keepout フィルタの TF の失敗は未解決（安全に関わる）
- 人混みの回避の良し悪しは KUAMS の設定を読んだだけでは分からない。走行の記録は見ていない

## 6. 実行した検査・試験

- 試験・設計検査：未実行（読むだけ）
- コマンド：curl・gh api で上記の commit の原文を取得（Mac の scratchpad、リポジトリには入れていない）。docs.nav2.org は本文を取得できなかったので README で読んだ

## 7. 次に進められる作業／止まっている作業

- 進められる：MPPI の試験の提案の作成、実車 PC の CPU の測定の手順
- 止まっている：MPPI の実装（人の承認）

更新した生成物：なし。
