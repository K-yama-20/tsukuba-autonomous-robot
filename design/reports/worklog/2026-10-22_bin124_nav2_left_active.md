# 第124便：人が本当の位置で開始した試行の調べ（REV-153、DEC-287）

日付：2026-10-22

## 読んだもの

- 作業ツリー：c2b8d65 に、第117〜123便（未コミット）を足したもの。
- VM の `gouda_core.launch.log`、`records/20261022_035620/log/events.jsonl`、`autonomy_client.py`（start・stop・_call）。

## 人の発言（原文）

- 「本当の位置を設定した」

## 分かったこと（読むだけ。VM の操作はしていない）

- 人は新しい地図と waypoint（地図 20261022_031430_5e5b16fc、waypoint 20261022_031654_5320af、03:14〜03:16 に作成）で、初期姿勢 (−1.316, −1.429, −90°) を設定し、自律走行開始を送った（1792609384、run-c1f3ac83）。
- ND-07：28.7 秒で (−0.39, −0.24) に合い、29.6 秒で正常。
- Nav2：1792609413.72 の STARTUP で「Failed to change state for node map_server」。
  - 続いて TR-07（Nav2 STARTUP failed、stop_reason node_failure）。今も一時停止（mode 4）。
- 原因：第123便（Claude の試行）の残り。
  - STARTUP は 1792608998 に始まり、1792609005.2 に TR-07（ekf_covariance_large）、1792609005.54 に Nav2 が active になった。
  - autonomy_client の _call は、STARTUP の応答の後に開始が捨てられていると Abandoned を出し、nav2_active = True に届かない。stop() は nav2_active のときだけ RESET するので、終了（TR-12）で RESET されず、Nav2 は動いたまま残った。
  - 人の試行の STARTUP は、map_server が active のままなので configure に失敗した。
- 原因の分類：実装（競合）。直し方は承認事項 DEC-287（推奨は案 a：STARTUP を送る直前に動いているかもしれないと記録し、終了のときは必ず RESET。案 c：開始の最初にも RESET、は一緒にできる）。
- 位置
  - 一時停止中の推定は (−0.36, −0.20)、向き約 −97°、照合の良さ 3.23、EKF の標準偏差 0.503 m。
  - 人が設定した位置から約 1.5 m 違う（向きは近い）。NDT が違う場所に合ったのか、設定した位置がずれているのかは分からない。
- 記録：`design/research/vehicle_pc/2026-10-22_nav2_restart/`。

## 実行した検査・試験

- `apply_revision.py REV-153 --dry-run --check`：新しい違反 0。適用と生成物の作り直しは終了コード 0。
- run_checks：design_check は合格（違反 0、未判定 5）。違反は既存の 6 件だけ。
- 単体試験：未実行（コードは変えていない）。

## 残るリスク

- 今の VM では Nav2 が動いたまま残っている。人の試行を終了しても RESET されない見込み。直すまでは、Gouda を起動し直さないと次の開始が通らない（起動し直すのは人の確認の後）。
- 推定の位置が人の設定と 1.5 m 違う。

## 次の作業

- 人の判断：DEC-287、DEC-286。今の Gouda を終了して起動し直してよいか。
- 人の確認：推定の位置 (−0.36, −0.20) と本当の位置のどちらが正しいか。
- 第117〜124便のコミット・PR はまだ。
