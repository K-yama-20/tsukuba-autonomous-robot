# 作業記録 2026-10-09 第11便: Ubuntu 試験環境の指示、旧起動スクリプトの削除（REV-017）

## 読んだもの

- リポジトリ HEAD `f208066`。`reports/worklog/2026-10-09_rev015_016_stage5-1.md`、`scripts/gouda.sh`・`gouda_gui.sh`・`smoke.sh`、README.md、docs/*.md の `scripts/gouda.sh` 参照、`scripts/setup.sh`・`configure_host.py`。

## 1. 人の指示（原文で台帳へ）

- **DEC-067**: Parallels 上の Ubuntu 24.04 へ `ssh -o BatchMode=yes aya@10.211.55.4`、開発対象 `~/gouda_ws`、以後の Ubuntu コマンドは SSH 経由、ROS 2 Jazzy は `/opt/ros/jazzy/setup.bash` を先に読む、この環境で試験（センサー未接続）。
- **DEC-068**: 「旧scripts/gouda.sh類は一式削除して良い。」

## 2. Ubuntu への接続

- `ssh -o BatchMode=yes -o ConnectTimeout=10..25 aya@10.211.55.4` を 3 回試行: 1 回目 "Operation timed out"、2 回目 ping 不達・"Host is down"、3 回目 "Operation timed out"。VM が停止または休止と推定（推測）。`~/gouda_ws` と Git の状態、ビルド・ROS 上の試験は**未実施**。VM 起動後に第10便 worklog §5 の手順を SSH で実行する。
- 記憶（memory）の接続情報を更新（鍵認証可。パスワードは使わない）。

## 3. 旧起動スクリプトの削除（DEC-068）

- `git rm`: `scripts/gouda.sh`、`scripts/gouda_gui.sh`、`scripts/smoke.sh`（旧 gouda.sh を直接呼ぶ煙試験）。
- 参照の更新: README.md の起動節を新 `gouda.sh` に差し替え、旧版移行節の参照を修正。`scripts/setup.sh` の完了メッセージ、`scripts/configure_host.py` の案内文。`docs/gouda_gui.md`・`gouda_recording_glim.md`・`autonomy_mvp.md`・`phone_field_runtime.md` は先頭に削除の注記を付け、本文は履歴として保持。
- 残したもの: `gouda_gui` パッケージ本体、`scripts/setup.sh`、`configure_host.py`、`scripts/test.sh`（旧試験の実行。gouda_gui の test を含むため、gouda_gui 撤去時に合わせて見直す）。gouda_gui の撤去は旧実装の置き換えとして別の判断事項。
- 新 `gouda.sh` の注記を更新。ND-01 の記述を REV-017 で更新。

## 4. 検査（`design/.venv/bin/python design/tools/run_checks.py`、終了コード 0）

入力の完全性・設定の生成・intent 同一性 PASS。移行忠実性 5,896 検査・違反 0。設計整合性 15 ルール 違反 0・未判定 4。検査器の試験 63 件 OK。gouda_core 単体試験 17 件 OK（Mac、第10便）。ROS 上の試験・ビルドは未実施（VM 不達）。

## 5. 残るリスク・判断事項

1. VM 不達のため、工程5-1 の ROS 上の確認（colcon ビルド、launch、サービス、rosbag 子プロセス）は未実施。
2. 旧文書の本文に `scripts/gouda.sh` の手順が残る（注記で削除済みと明記）。gouda_gui 撤去時に文書も整理する。
3. REV-014〜017、新実装、旧スクリプト削除は未コミット。

## 6. 次の作業

- VM 起動後: `~/gouda_ws` と Git の確認 → 作業ツリーの同期（コミット・push のうえ pull、または rsync。方法は人に確認）→ `colcon build --packages-select gouda_interfaces gouda_core` → 単体試験 → `gouda.sh start` とサービス呼出し → 出力を `research/vehicle_pc/` に保存。
