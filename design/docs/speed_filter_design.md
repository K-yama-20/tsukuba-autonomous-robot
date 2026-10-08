# 区間速度上限の適用: Nav2 Speed Filter（costmap filter）による発行（DEC-031）

状態: 案。人の回答 DEC-031「H-001：speed filter(costmap filter)が発行。」に基づく。`docs/speed_limit_publisher.md`（Gouda 側発行器案、DEC-011 の暫定採用）は本書で置き換えられ、履歴として残す。モデル上の対応: IFD-14（発行元 = Nav2 costmap の SpeedFilter）、IFD-41（速度マスクのファイル契約）、IFD-42（costmap_filter_info・mask topic）、PRM-19・PRM-20、TS-01〜TS-06、H-011。

## 1. 上流 jazzy での動作（645abd95、nav2 1.3.13。実車PC と版一致）

- `SpeedFilter`（`nav2_costmap_2d/plugins/costmap_filters/speed_filter.cpp`）は `filter_info_topic`（`CostmapFilterInfo`、QoS KeepLast(1) transient_local reliable）と `filter_mask_topic`（`OccupancyGrid`、同 QoS）を購読し、ロボット位置の mask cell 値 `data` から `speed = data × multiplier + base` を計算（`type=2` で m/s、`type=1` で %）。
- mask cell が 0（free）は無制限、-1（unknown）はエラーで無視、1..100 が通常値。cell 値は int8 のため上限は 100 段階に量子化される（例 base=0, multiplier=0.02 なら 0.02 m/s 刻みで最大 2.0 m/s）。
- `speed_limit_` が前回と変わったときだけ `SpeedLimit` を `speed_limit_topic`（QoS(10)）へ発行する（`speed_filter.cpp:242-258`）。**値が変わらない限り再発行しない。**
- `CostmapFilterInfo.filter_mask_topic` で mask topic 名を指定。Nav2 標準の `costmap_filter_info_server` と `map_server`（mask 用インスタンス）で配信できる。

## 2. 設計

| 項目 | 内容 |
|---|---|
| 発行元 | Nav2 costmap（ND-10）の SpeedFilter プラグイン。Gouda は SpeedLimit を発行しない（RQ-I020 の「単一の発行元」を満たす） |
| マスクの生成 | gouda_monitor 内 waypoint_manager（ND-02）が waypoint セット保存時に区間 i→i+1 の上限 v[i] から mask（PGM/PNG + YAML、`type=2`、base=0、multiplier=PRM-20 の刻み）と filter info を生成し、waypoint セットと同じ由来 ID・内容ハッシュで保存（IFD-41、IFD-30 の拡張） |
| 区間の領域 | 区間 i の線分 W[i]→W[i+1] の周囲、半幅 PRM-19（tbd）の帯を cell に塗る。重複 cell は**低い方の上限**（DEC-045。再訪・重複ルートには同じ値を設定する運用）。帯の外（cell=0）は Nav2 の挙動どおり無制限。境界の揺らぎは TS-16 で実機調整し追加の境界対策は行わない（DEC-049） |
| 配信 | 自律走行開始（TR-05）で ND-03 が選択した waypoint セットの mask・filter info を Nav2 の `map_server`（mask 用）と `costmap_filter_info_server` に読み込ませる（IFD-42。lifecycle の configure/activate、または load_map サービス）。transient_local のため後から購読する costmap にも届く |
| 復帰 | 復帰手順は lifecycle cleanup→configure→activate の 1 つ（DEC-046、TR-13）。フィルタが再生成され最初の process() で現在値が発行される。TS-06 は同じ cell で deactivate→activate と cleanup→configure を試し、再走行前に controller が実際に保持している上限（直線 stub 経路の cmd_vel 最大値で観測）の一致で判定 |
| 適用状態の記録 | mask 未読込・マスク外では何も発行されないため、ND-03 が mask・filter info の latched 配信、speed_limit の最終受信値・時刻、位置が mask 範囲内かを観測し speed_limit_application_state を IFD-01・DecisionEvent に記録、monitor に表示（DEC-047、TS-15）。観測のみで発行しない |
| DEC-011 の 5 項目 | 初回区間: 開始地点が W[0] 付近の帯内なら v[0]。帯外は H-011。複数減: 影響なし（位置で決まる）。再 goal・再開・再計画・取消: 影響なし（mask は不変）。最終到達: 最終区間の帯の値が残る。controller の再起動: SpeedFilter は**値が変わるまで再発行しない**ため、controller_server 再起動後は mask 値が変わる cell に入るまで上限なし（Nav2 の制約。改変しない） |
| 記録 | ND-03 は feedback の number_of_poses_remaining から区間番号（SO-01 current_section_index）を記録用に求める（RQ-I030 の区間 ID）。SpeedLimit の発行には使わない |

## 3. 制約と未決

- controller_server 再起動後の再適用は Nav2 側の挙動（値変化時のみ発行）に依存する。再起動時に SpeedFilter の `speed_limit_prev_` も初期化されるのは costmap（SpeedFilter を持つ node）の再起動時のみ。controller のみ再起動した場合は mask 値が変わるまで上限が適用されない。回避は Nav2 改変になるため行わない（RQ-I056）。試験 TS-06 で挙動を記録し、人に報告する。
- 帯の半幅（PRM-19）、mask 解像度と速度刻み（PRM-20）は未確定。帯外の扱い（無制限か、全体に既定上限を敷くか）は H-011。
- mask は地図（変換後地図）と同じ frame・原点・解像度で作る（IFD-29 の manifest を参照）。地図版が変われば再生成。
