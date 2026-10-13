> **履歴（2026-10-09）**: 本書の Gouda 側発行器案は DEC-011 で暫定採用されたが、DEC-031「H-001：speed filter(costmap filter)が発行。」により置き換えられた。現在の設計は `docs/speed_filter_design.md`。本書は履歴として保持し、更新しない。

# SpeedLimit 発行器（gouda_mode_manager）の設計（暫定採用 DEC-011）

状態: **案・暫定採用**。正式承認は人（H-001）。実車PC の版照合（V-001）は DEC-012 で完了（Nav2 1.3.13）。モデル上の対応: IFD-14、SO-01（goal_waypoint_offset・current_section_index）、ND-03、試験 TS-01〜TS-06。

## 前提（上流 jazzy 645abd95、nav2 1.3.13）

- controller_server は param `speed_limit_topic`（既定 `speed_limit`）を `rclcpp::QoS(10)`（reliable・volatile）で購読し、`setSpeedLimit(speed_limit, percentage)` を各 controller プラグインに適用する。
- NavigateThroughPoses の feedback に `number_of_poses_remaining`。既定 BT の `RemovePassedGoals radius`（PRM-11）で先頭 goal を除いたときに減る。通過判定は Nav2（RQ-I011）。
- `SpeedLimit.speed_limit = 0.0` は無制限。停止用途に使わない（REF-04）。

## 区間番号の定義

waypoint セット W[0..N-1]（N 点）。区間 i は W[i] → W[i+1]（i = 0..N-2）、上限 v[i]（m/s、IFD-30）。「初回区間」は開始地点 → W[0] ではなく、Nav2 goal の pose 列が W[k..N-1] のとき、最初に進入する区間は k-1 → k ではなく **W[k] に向かう区間** とする。この区間の上限は、開始地点が W[k-1] 付近でない場合も v[k-1]（進入する区間の値: RQ-I010）を適用する。k=0 のときは v[0] を用いる（開始地点→W[0] の区間に専用の値はないため。要確認: 人が別の値を望む場合は waypoint セットに「開始区間」の属性を追加する）。

goal を送るとき `goal_waypoint_offset = k`、goal の pose 数 `P = N - k`。feedback の `number_of_poses_remaining = r` のとき、次に向かう waypoint は `W[k + (P - r)]`、進入中の区間番号は `s = k + (P - r) - 1`（s < 0 のときは 0 とみなす）。`current_section_index = s`。

## 5 項目

| 項目 | 設計 | 試験 |
|---|---|---|
| 初回区間 | goal 送信の直前に `SpeedLimit(percentage=false, v[s0])` を 1 回発行。publisher は `transient_local, keep_last 1` にして、遅れて購読した controller にも届く（volatile 購読と互換）。発行後に goal を送る | TS-01 |
| 残り pose 数が一度に複数減る | r が Δ≥2 減ったときも、計算した現在区間 s の値を 1 回発行。飛ばした区間 s-Δ+1..s-1 を DecisionEvent に記録（独自の通過判定はしない） | TS-02 |
| 再 goal・再開・再計画・取消の後 | 再開・再 goal: 残 waypoint から goal を作り `goal_waypoint_offset` を更新、s を再計算して現在区間の値を発行。Nav2 内部の再計画: goal は変わらず、r も変わらないので発行しない。取消: 追加発行しない（最後の値を保持。停止は motion_hold IFD-40 と Nav2 の零速度） | TS-03、TS-04 |
| 最終到達 | result SUCCEEDED → TR-08（一時停止、remaining=[W[N-1]]）。発行は終える（最後の値を保持）。再開時は s = N-2 の値を再発行。result error_code ≠ NONE → TR-07（発行なし） | TS-05 |
| controller の再起動・購読開始 | transient_local により最新値を再受信。さらに ND-03 は controller_server の `transition_event`（activate）を購読し、同じ値を再発行する。上限が未適用の期間を記録 | TS-06 |

## 発行しないこと

- 停止のための 0.0（無制限の意味になる）。
- Nav2 の計画・追従への介入（RQ-I019・RQ-I020）。
- 区間境界時点の実速度保証（RQ-I062）。

## 未決

- 開始地点→W[0] の区間に専用の上限を持たせるか（上記）。人の確認が要る場合は H-001 の正式承認時に含める。
- 発行間隔の下限（feedback 周期に依存。Nav2 bt_navigator の feedback は BT ループ周期）。値は Q-05。
