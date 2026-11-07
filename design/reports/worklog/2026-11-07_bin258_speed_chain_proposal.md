# 作業記録 2026-11-07 第258便: 速度の値を 1 本の鎖にし、速度マスクに勾配を付ける提案

- ブランチ chat/confirmation-plan-2026-11-07（worktree tsukuba-worktrees/confirmation-plan）、c88791d から。
- 読んだもの：gouda_core/gouda_core/speed_mask.py、waypoints.py、autonomy_core.py（speed_limit_state）、nav2_config.py、design/generated/params の速度の値、第251便の不合格の本（車載 PC の plant_runs、pst_PM_+090_s1）の軌跡と stack log、合格の本 pst_P1_+000_s1。
- 人の指示（原文）は提案の 0 節。
- 作った物：design/proposals/speed_chain_and_mask_gradient_2026-11-07.md（提案。承認待ち）。issue に登録（本文は提案の要約）。
- 自律判断：提案だけで、コード・正本・生成物・設定は変えていない。REV・DEC はまだ作っていない（承認の後）。
- 分析で分かったこと（事実）：不合格の本では、角の頂点の約 0.7 m 手前で cmd_v が 0.27〜0.5 から 0.67〜0.68 に跳ね上がり（マスクの帯に入った時刻。0.27 × 1.25 ÷ 0.5 = 0.675）、その後 MPPI の「Optimizer fail to compute path」が 1150 回出る間も前進の指令（0.58、その後 0.27）が続き、最初の指令から約 14 秒で前端が外側の壁に 0.3〜0.4 m/s で達した。合格の本でも同じ跳ね上がりがあるが、中心線上で左旋回を始めていたため曲がれた。
- 推定（未確認）：右に切って −109° へ向いたのは、内側にずれた位置から角の頂点の waypoint へ向かったため。失敗時に下限で前進し続ける上流の仕組み。
- 検査・試験：実行していない（提案のみ）。
- 止まっていること：実装（承認待ち）。区間の制限を 0.5 に揃えた走らせ直しの結果（別の subagent、実行中）。
- 番号：第258便（reserve_ids.py、共有の印）。
