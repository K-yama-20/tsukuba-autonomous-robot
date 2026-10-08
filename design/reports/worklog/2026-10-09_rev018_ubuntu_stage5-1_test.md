# 作業記録 2026-10-09 第12便: Ubuntu 上での工程5-1 のビルド・試験、gouda.sh 停止不具合の修正（REV-018）

## 読んだもの

- ローカル HEAD `f208066` → 本便でコミット `2eb94c2`・`0f02397`。VM 側 `~/gouda_ws/src/tsukuba-autonomous-robot`（確認時 main `b0a3a36`、クリーン）。`reports/worklog/2026-10-09_rev017_ubuntu_legacy_removal.md` §6 の手順。

## 1. VM への同期

- origin/main は `f83a104`（feat/architecture の merge）。本ブランチは `a091ed3` を基点に 4 コミット先行、main に対し 1 コミット遅れ（内容は本ブランチの基点の merge のみ）。
- 未コミットだった REV-014〜017・新実装・旧スクリプト削除をコミット `2eb94c2` にして push。VM で `git fetch` → `git checkout -B design/gate3-baseline-2026-10-09 FETCH_HEAD`。VM の main は触っていない。

## 2. ビルドと試験（SSH 経由、ROS 2 Jazzy、センサー未接続。記録は `research/vehicle_pc/2026-10-09_stage5-1_ubuntu_test.txt`＝FILE-VEHICLE-PC-STAGE51）

| 項目 | 結果 |
|---|---|
| colcon build gouda_interfaces gouda_core | 成功（4.4 s）。SoftwareMode・DecisionEvent が生成 |
| 単体試験（Ubuntu、Python 3.12） | 17 件 OK（修正後はローカルで 18 件 OK） |
| 起動（TR-01） | mode/state: mode=1、state_revision=1、initial_pose_required=false。記録は開始されない（record/status: log_active False、rosbag_active False） |
| record/log start→stop | 成立。events.jsonl に record_start／record_stop |
| record/rosbag start→stop | 成立。`rosbag/bag/bag_0.mcap`＋metadata.yaml（/mode/state 1 件） |
| 再起動 TR-02（直前 autonomy） | mode=4、previous_mode=3、initial_pose_required=true、run_id 復元、state_revision 5→6 |
| 再起動 TR-02（直前 pause、人の一時停止フラグあり） | mode=4、human_pause_or_end_recorded=true、フラグは永続記録に残る |
| ログ停止→再開 | last_gap と gaps.jsonl に停止期間（stopped by human）が残る |
| 記録開始時の snapshot（修正後） | 開始前に受信した mode/state が元の受信時刻付きで snapshot として書かれる |
| gouda.sh stop（修正後） | 1 s で停止。グループの全プロセス消失を確認。残存 0 |

## 3. 検出した不具合と修正（1.6 の分類）

- **実装（gouda.sh）**: 初回試験で `stop` 後に node プロセスが残存（3 回の起動で同名 node が 3 組）。原因は非対話シェルの背景ジョブが SIGINT 無視を継承し、ros2 launch も無視のままだったこと、SIGTERM を launch にだけ送って子を待たなかったこと。修正: ジョブ制御（`set -m`）で launch を独自のプロセスグループにし、停止はグループへ SIGINT→SIGTERM→SIGKILL、`pgrep -g` で全消失を確認。`status` はグループのプロセス数を表示。
- **実装（recorder）**: 記録開始時に、開始前に受信していた最新の mode/state 等を元の受信時刻付き snapshot として書くようにした（開始時点の状態をたどれるようにするため。受信していない値は書かない）。単体試験を追加。
- 残存プロセスの掃除で `pkill -f` のパターンが SSH のシェル自身に一致して接続を切った（作業上の誤り。製品側の問題ではない）。パターンを `^/usr/bin/python3 .*gouda_(mode_manager|recorder)` にして解消。
- 期待値・合否基準は変えていない。

## 4. 検査（`design/.venv/bin/python design/tools/run_checks.py`、終了コード 0。REV-018 適用後 model.yaml SHA `4514fbab7a40ed3c…`）

入力の完全性・設定の生成・intent 同一性 PASS。移行忠実性 5,896 検査・違反 0。設計整合性 15 ルール 違反 0・未判定 4。検査器の試験 63 件 OK。gouda_core 単体試験 18 件 OK（ローカル）。

## 5. 状態の区別

- 工程5-1: **ソフト試験合格**（Ubuntu 上の ROS 環境で TS-23・TS-24 相当の確認が完了。合否は正本の execution_status ではなく本記録と証拠ファイルで管理）。実車検証は未実施（センサー・車体なし）。
- 設計検査は未判定（違反 0・未判定 4）。

## 6. 残るリスク・判断事項

1. rosbag は `-a`（全 topic）。対象 topic の限定と保存形式の設定は後の工程で parameter として宣言する。
2. 自動開始の契機を載せる記録 IF（5-3／5-6 の前）は未設計。
3. DEC-058 条件 3 の案の採否、gouda_gui 撤去、122 件の design_status は未回答。
4. 本便の REV-018・記録・修正は `0f02397` の後に行ったため未コミット（次でコミット・push し VM を同期）。

## 7. 次の作業

- REV-018 と記録をコミット・push、VM を同期。
- 5-2（gouda_monitor）の前提整理: ND-03 のサービス（IFD-02〜07）の受付部分と、monitor が表示する IFD-01・IFD-12。
