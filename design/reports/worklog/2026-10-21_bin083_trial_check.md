# 作業記録 2026-10-21 第83便: 変更セットの試し適用（--dry-run --check）

## 読んだもの

- コミット `33416021655e587d0ae5f2c949d9bf81698ef44e`（作業ツリーは未 commit の変更あり）。`design/tools/apply_revision.py`（既存の --dry-run は要約を出すだけ）、`check_design.py`（run）、`validate_model.py`。

## 人の指示

記録の誤りが増えた原因の分析（第70〜82便の記録の誤り 6 件・報告の誤り 2 件。主因は適用の前に検査していないこと）の後、「試し機能の追加。」。

## 変更

- `design/tools/apply_revision.py`: `--check`（`--dry-run` と併用）を追加。変更セットを適用した後の正本を一時ファイルに書き、`check_design.run` で検査し、今の正本の検査結果に無い違反・未判定だけを表示する。新しい違反があれば終了コード 1。正本・スキーマ・報告は書かない。generated/params の不一致は正本のハッシュを含むため本適用の後の再生成まで必ず出るので数えない（その旨を表示）。
- 使い方: `design/.venv/bin/python design/tools/apply_revision.py REV-xxx --dry-run --check` → 新しい違反 0 を確かめてから `apply_revision.py REV-xxx`。

## 原因の分類

- 実装（ツール）の不足。記録の誤りの再発防止。

## 検査・試験

- 一時の変更セット（REV-TRIAL、試験の後に削除）で確認。正本・スキーマの md5 が試験の前後で同じ。
  - 出典欄が空の PRM（REV-108 と同じ誤り）: DR-01 の違反 1 を表示、終了コード 1。
  - PRM-10 の承認の根拠を recorded の DEC-179 に（REV-116 と同じ誤り）: DR-01 の違反 1 を表示、終了コード 1。
  - 最初の版は generated/params の不一致 20 件を新しい違反として出した（偽の検出）。除外して再確認。
- `design/.venv/bin/python design/tools/run_checks.py`: 終了コード 1。設計検査 合格 12・違反 0・未判定 5。検査器の試験 79 件中 1 件失敗（test_real_model、drawio と .DS_Store の以前からの違反）。移行の照合の違反は以前から（5 件）。
- --check 自体の単体試験は追加していない（未実行）。

## 次に進められる作業

- 以後の変更セットは試し適用の後に本適用する。
