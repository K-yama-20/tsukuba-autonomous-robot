# 作業記録 2026-10-23 第140便: 状態遷移の再設計の提案（REV-166、DEC-342〜346）

## 読んだもの

- 作業ツリー `31a6e1d` ＋ 未コミットの変更（第139便まで）。`design/intent.md`（人の 15:08 の編集の版、SHA-256 9012e5f2…、未記録）。
- `proposals/competition_no_auto_pause_2026-10-22.md`（DEC-305〜314）、model.yaml の MODE-*・TR-01〜16・ST-01〜20、`gouda_interfaces/msg/SoftwareMode.msg`、`gouda_core/gouda_core/mode_core.py`・`waypoints.py`・`autonomy_client.py`・`nav2_config.py`。
- 上流 Nav2 1.3.13：`inflation_layer.cpp`（449 行 dynamicParametersCallback）、`costmap_filters/binary_filter.cpp`、BT の写し（RateController 0.333 Hz）、`nav2_params.yaml`（goal の判定 xy 0.25 m）。

## 1. 人の指示（原文）

- 「Write the state-transition redesign proposal here, merging DEC-305..314, DEC-340 (no auto-standby, wait for estimation to recover) and DEC-332 (crosswalk stop with human resume). No implementation.」
- 作業の途中の人の問い：「inflationの範囲を場所毎に異なる値に設定することは可能か？例えば、確認走行区間ではinflationを少し大きくして、狭い歩道ではinflationを少し狭くする、とか。
costmapの更新が3秒おきというのは遅すぎる気もするが、何故このような設定にしているのか？また、障害物をcostmapに登録し始める範囲を2.5mとしている理由は何か？もっと大胆に広げた際のデメリットは何か？」

## 2. 行ったこと

- 提案 `design/proposals/state_transition_redesign_2026-10-23.md` を作った。要点：モードは 4 つのまま。自動で待機に入るのは最後の waypoint（TR-08）だけ。ほかは自律走行モードの中の処理の段階（processing_state：driving・rule_stop_hold・localization_wait・goal_retry・stuck_escalation・recovering）で表す。TR-07・TR-09 をなくす。横断歩道は既存の waypoint の kind: stop と区切りごとの goal で作る。
- REV-166（DEC-342〜346、pending）を `--dry-run --check`（新しい違反 0・未判定 0）の後に適用した。番号は reserve_ids.py で予約（REV-166、DEC-342〜346、第140便）。
- 別のセッションの提案（competition_no_auto_pause）と DEC-305〜314 は変えていない。提案の §8 で対応を示した。

## 3. 人の問いへの答え（チャットでも答えた）

- 場所ごとの inflation：可能（InflationLayer の inflation_radius は走行中に変えられる。確認）。区間の属性で切り替える案を DEC-344 にした。
- 「3 秒おき」：costmap の更新は local 5 Hz・global 1 Hz（上流の雛形の値）。3 秒おきなのは経路の引き直し（BT の RateController 0.333 Hz）。どちらも Gouda が雛形の値をそのまま使っているからで、この環境に合わせて決めた値ではない（nav2_config.py は雛形から PRM-11・18 だけを変える）。
- 2.5 m：Gouda が決めた値ではなく、上流の ObstacleLayer の既定（obstacle_max_range 2.5、raytrace_max_range 3.0）。Gouda の設定が値を与えていないので既定が効いている。広げる利点と欠点はチャットで答えた（推測を含む）。

## 4. 検査・試験（`run_checks.py`、31a6e1d ＋ 作業ツリー）

- 設計検査：合格 12・違反 0・未判定 5（前と同じ）。
- 移行の検査：違反 2 件（intent.md の人の未記録の編集による。第139便と同じ）。検査器の試験：88 件、不合格 1 件（同じ理由）。
- 単体試験・実機：未実行（コードの変更なし）。

## 5. 残るリスク

- 待機ボタンが規則上の失敗の操作に当たるかが未確認（DEC-345）。当たるなら、自動で止まらない設計では本番で止める手段がなくなる。
- 停止線の位置の精度は未確認（DEC-346）。
- DEC-305 が決まらないと段階の実装全体が止まる。横断歩道の一時停止だけは独立に進められる（DEC-343）。

## 6. 次

- 人の回答を待つ：DEC-305〜314（別のセッションの項目）、DEC-342〜346。
- costmap の提案 第3版（MID-360、コーンの迂回、歩行者、DEC-341、距離・引き直しの間隔の見直し）。
