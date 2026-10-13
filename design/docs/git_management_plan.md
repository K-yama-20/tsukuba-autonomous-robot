# design/ の Git 管理案と実装リポジトリの版との対応（案）

状態: 提案。実行していない（`git init` は人の判断）。

## 現状

- `design/` はワークスペース直下にあり、ロボット実装 `tsukuba-autonomous-robot/`（別 Git リポジトリ、確認時 HEAD `a091ed39eb154b2dff7065840dc13c6478b153da`、作業ツリーに `docs/architecture/*.xlsx|*.drawio` の未コミット変更あり）の外にある。
- `design/.gitignore` は既にあり、`.venv/`・`__pycache__/`・`.DS_Store`・`scratch/` を除外する。
- 正本・生成物・baseline・報告の対応は `reports/status.md` の対応表のとおり。

## 案A（推奨）: `design/` を独立リポジトリにする

1. `design/` で `git init`。最初のコミットを「初回移行 baseline（migration_v1）」として `baselines/migration_v1/snapshot.json` のハッシュと一致する状態で作る。タグ `design-baseline-migration_v1`。
2. 2つ目のコミットを REV-002（本作業）とし、タグ `design-REV-002`。以後、モデルの変更は `revisions/REV-xxx.yaml` 1件＝1コミット（適用結果・再生成した生成物・検査結果を同じコミットに含める）。
3. `design/intent.md` は人の編集をそのままコミットする。AI の変更は `authority_revisions` の記録を伴うコミットに限る。
4. 原資料（`docs/*.xlsx`、`docs/*.drawio`、`docs/extraction_*/`）は読み取り専用のまま管理し、`reports/input_integrity.json` で各コミットのハッシュ一致を確認する。
5. `.venv/` は除外（既存の `.gitignore`）。依存は `tools/requirements.txt` と `requirements.lock.txt`。

実装リポジトリとの対応: 実装側のコミットメッセージまたは `docs/DESIGN_REVISION` ファイルに、準拠した設計リビジョン（例 `design-REV-002`）を書く。設計側は `model.yaml` の `revisions[].basis_refs` とは別に、`reports/check_run.json` に実装 HEAD を記録している（本作業は a091ed39）。双方向に参照できる。

## 案B: 実装リポジトリ内に取り込む（`tsukuba-autonomous-robot/docs/design/`）

- 1リポジトリで済み、実装と設計の版が同じコミットで固定される。
- 一方、原資料 `docs/architecture/*.xlsx|drawio` と設計側の `design/docs/` に同じファイルが二重に置かれる。どちらを正本にするかの判断（既存ファイルの移動・改名は承認事項: CLAUDE.md 1.9）が必要。

## どちらでも共通

- 生成物（`generated/`、`conflicts.yaml`、`intent_open_items.yaml`、`intent_index.yaml`、`reports/*.json|txt`、`migration_review.md`）はスクリプトで再生成してコミットする。手編集しない。
- CI で `design/.venv/bin/python design/tools/run_checks.py` を実行し、終了コード 0 を要求する。
