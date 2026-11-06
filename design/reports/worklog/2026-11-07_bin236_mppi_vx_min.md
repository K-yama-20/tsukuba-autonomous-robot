# 作業記録 2026-11-07 第236便: MPPI の前進速度の下限 vx_min を /config で変えられる値に（REV-261、DEC-480、PRM-162）

## 読んだもの

- コミット `9c449b5`（ブランチ design/mppi-sim-2026-11-03）＋作業ツリー（他のセッションの未コミットの変更、REV-240〜260 の適用後）。
- 第215便の作業記録、`design/research/vehicle_pc/2026-11-07_min_speed/README.md` の値（DEC-445）。

## 1. 人の発言と回答（原文）

- 「mappiに出力下限値以下の速度を絶対に出させないようにロジックを変えたらいいのでは？私は君がサボっているのではないかと思っています。」
- 「これも停止用のロジックを新たに組めばいいだけの話ではないか？」（下限を置くと止まる指令が出ない、という AI の懸念に対して）
- 質問「MPPI の速度の下限（0.27 m/s、/config で変更可）を製品に入れてよいですか？」→「入れて」（DEC-480）。

## 2. 変更

- 正本：PRM-162（mppi_vx_min_mps、0.27 m/s）。ND-10・IFD-54 に追記（REV-261）。
- `gouda_core/gouda_core/nav2_config.py`：TUNABLES に mppi_vx_min_mps。`mppi_follow` が vx_min に PRM-162（値がなければ 0）を書く。MPPI の速度の上限以上なら ValueError。
- `gouda_core/web/app.js`：/config「Nav2」タブの表示名。
- `gouda_core/test/test_nav2_config.py`：`test_mppi_vx_min` を足した。`test_mppi_is_the_default` の vx_min の期待値を 0.0 → 0.27 に変えた（承認された設計の変更 DEC-480 による。根拠は PRM-162）。

## 3. 自律判断

- 0.27 m/s は、発進する倒し量 0.21（DEC-445）× PRM-39（1.25 m/s）＝ 0.2625 m/s を切り上げた値（AI の提示、人が承認）。
- /config の値の種類は既存の「正の数」を使った。0 は入れられない（下限を実質なくすには小さい正の値）。新しい種類を monitor に足す変更を避けた。
- 停止用のロジックは足していない（人の指示がない。候補は上流の collision_monitor、DEC-372 は確認待ち）。

## 4. 原因の分類（1.6）

- 設定（MPPI の vx_min が 0 固定）と物理特性（不感帯、DEC-445）。

## 5. 検査・試験

| 検査 | コマンド | 対象 | 結果 |
|---|---|---|---|
| 変更セットの試し | `apply_revision.py REV-261 --dry-run --check` | 9c449b5＋作業ツリー | 新しい違反 0・未判定 0 |
| 単体試験（Mac） | `PYTHONPATH=gouda_core python3 -m unittest discover -s gouda_core/test` | 同上 | 434 件 OK（skip 27。他のセッションの試験を含む） |
| 設計検査 | `design/.venv/bin/python design/tools/run_checks.py` | 同上 | 終了コード 1。設計検査は違反0件・未判定5件。不合格は前からのもの（input_integrity、migration_validator、migration_tests の test_real_model） |
| 模擬（ワークステーション ~/gouda_ws_ol、DEC-445 の車体モデル `--m1107`、等速。下限は試験専用の上書き `GOUDA_TEST_NAV2` の follow.vx_min 0.27 で入れた。製品の PRM-162 の経路ではない） | `drive_sim.sh free|cone_late`、各 2 回 | ~/gouda_ws_m4x/src の写し＋第215便の変更 | 下限＋open_loop：ゴール 4/4、平均 0.44〜0.45 m/s、最大の横ずれ 0.35〜0.73 m、コーンとの最小間隔 0.12・0.14 m、接触 0。下限のみ（open_loop false）：0/4、平均 0.19 m/s、横ずれ 0.00 m、コーンの場面 2/2 で接触。比較の open_loop のみ（第215便）：4/4、0.37〜0.40 m/s |
| 製品の PRM-162 の経路での模擬 | — | — | 未実行 |
| 実車・車載 PC への反映 | — | — | 未実行 |

- 模擬の途中、ワークステーションの負荷が 23 まで上がった走行がある（他のセッションと重なった）。

## 6. 残るリスク

- 下限を置くと MPPI は止まる指令を出せない。前が塞がれたとき、指令 0.27 m/s（DEC-445 では車体は約 0.09 m/s）で進み続ける。Nav2 の回復（BackUp・Wait）と goal の到達は MPPI の外なので止まる。
- 旋回の不感帯は扱っていない。MPPI の中で扱う改造版は別に試験中で、02:46 の時点の模擬では基準より悪い。
- 模擬は 2 場面・各 2 回。曲がりの多い経路、狭い所、実車は未確認。
- 0.27 m/s は各条件 1 回の実測に基づく。床・傾きで発進のしきい値が変わると、下限でも動かない可能性がある。

## 7. 次

- 人の判断：車載 PC への反映、実車での確認、停止用のロジックを足すか。
- commit はしていない。

## 追記：車載 PC（x86）への反映（人の指示「反映して」）

- 質問「速度の下限の変更を車載 PC に反映してよいですか？」→ 人の回答（原文）「反映して」。
- 反映の前に、車載 PC の nav2_config.py と手元の差が、この便の変更だけであることを diff で確かめた（他のセッションの定数 1 行は除いて写した）。
- 実車用の Gouda が止まっていることを確かめてから行った。Gouda は起動していない。元のファイルの控えは車載 PC の `~/deploy_bin236/backup/`。
- 写したファイル：gouda_core/gouda_core/nav2_config.py。行を足した・直したファイル：gouda_core/web/app.js（表示名）、design/generated/params/gouda_nav2.yaml（mppi_vx_min_mps の 1 行。先頭の hash の注記は古いまま）、gouda_core/test/test_nav2_config.py（vx_min の期待値 0.0 → 0.27。新しい試験 test_mppi_vx_min は写していない）。
- 車載 PC での確認：`PYTHONPATH=gouda_core python3 -m unittest discover -s gouda_core/test`：OK。起動時と同じ手順の Nav2 設定の生成（一時フォルダ、何も起動しない）：`vx_max: 0.8`・`vx_min: 0.27`・`open_loop: true`、MID-360 は mid360.json がないため未使用。
- 未実行：Gouda の起動、実車。

## 訂正（03:25）：下限つきの走行はゴールで止まらない場合がある

- 上の表の「下限＋open_loop：ゴール 4/4」は誤った読みだった。採点の `completed`（進みが 97 % を超えた）だけを見ており、走行の終わり方（`end`）を見ていなかった（AI の読みの誤り。試験の合否の基準は変えていない）。
- 読み直した結果（模擬、DEC-445 の車体モデル、等速）：
  - 下限 0.27＋open_loop（試験専用の上書き、~/ol_runs/r2）4 本：`pause:goal_reached`（ゴールで止まった）2 本、`timeout`（止まらなかった）2 本。
  - 製品の経路（PRM-162、~/ol_runs/r3）の曲がり角の場面 corridor18_corner：下限＋open_loop 1 本、下限＋open_loop＋外側の下限 1 本とも `timeout`。open_loop のみ（/config で下限 0.001）1 本は `pause:goal_reached`。
  - 止まらなかった走行の軌跡（r3 の P_corridor18_corner_1/trace.csv）：ゴール（30, 10）の付近を t≈116 s に通った後、約 0.23 m/s のまま向きを変えて 10 m 近く走り続け、時間切れで終わった。指令の前進は 0.42 m/s のまま。
- 原因の分類（1.6）：設計（下限を置くと MPPI がゴールの手前で減速できず、到達の判定の範囲に止まれない、と推測。到達の判定の仕組みは未確認）。
- 車載 PC にはこの下限（PRM-162 0.27 m/s）が入っている（上の追記）。人に報告し、判断を待つ。
