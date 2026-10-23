# 作業記録 2026-10-22 第135便: 検査器の試験の見本の差し替え（REV-162、DEC-317）

## 読んだもの

- コミット `31a6e1d`＋作業ツリー（第127〜133便の未コミットの変更あり）。
- `design/rules/test_validate_model.py:140-143`、`design/tools/validate_model.py:324-330`、status.md（第133便）。

## 1. 人の指示（原文、DEC-317 に記録）

「検査器の試験の見本を RQ-I001 から今も置き換えられていない要求に替えてよい。合否の基準は変えないこと。」

## 2. 行ったこと

- 番号は reserve_ids.py で予約した（REV-162、DEC-317、第135便）。第134便は別のセッションの予約。
- 原因の分類：試験（試験基盤の見本の選び方）。
  - 試験 `test_superseded_requirement_needs_intent_justification` は、要求を superseded に変え、「superseded requirement justified」の違反が出ることを確かめる。
  - 見本の RQ-I001 は、AR-015（REV-161）で正当に superseded になっていた。そのため、変えても違反が出なかった。
- 試験の見本を RQ-I001 から RQ-I002 に替えた（`test_validate_model.py:141-142`、コメント 1 行を足した）。
  - RQ-I002 は adoption upper_requirement で、どの照合の affected_refs にもない。
  - 検査器の本体（`validate_model.py`）と、assert の条件は変えていない。
- REV-162 を適用した（DEC-317 recorded だけ）。

## 3. 検査

- 試験 1 件：`python -m unittest test_validate_model.MigrationTests.test_superseded_requirement_needs_intent_justification` は OK。
- 規則を壊した写しで、見本が検出されることを確かめた。
  - 実モデルのままでは、RQ-I002 に違反は出ない。
  - RQ-I002 を superseded に変えると、違反が出る。
  - このため、この試験は規則による検出でだけ合格する。
- `apply_revision.py REV-162 --dry-run --check`：新しい違反 0・新しい未判定 0。
- 適用の後の `run_checks.py`（31a6e1d＋作業ツリー）の終了コードは 1。
  - 設計検査：違反 0・未判定 5。
  - 検査器の試験：83 件中 2 件不合格。差し替えた試験は合格した。
    - test_real_model
    - test_current_intent_passes
  - intent_identity：違反。
  - migration_validator：違反 2。
    - intent revision chain reaches current file
    - intent reproduced from archived copy plus recorded lines AR-015
  - 原因は、**検査の途中（2026-10-22 23:45）に、人が intent.md をもう一度編集したこと**（下の §4）。この不合格は試験の差し替えによるものではない。
  - 既存の drawio・.DS_Store の違反は、intent の照合で止まったため今回の報告には出ていない（推測。intent を記録した後にもう一度確かめる）。
- gouda_core の単体試験：未実行（gouda_core の変更なし）。

## 4. 観測した人の編集（記録はまだ）

- intent.md の SHA-256 は `23170969d3388b0f58929d7c9edc7ad5bca640336f0da393d9232240041fac25`、23:45 に更新されていた。
- 第15版との差は 1 行目だけ。「自動的に一時停止モードに入ったり」が「自動的にgoudaが一時停止モードに入って自律走行が出来なくなったり」に変わった。
- 人が編集を終えたかを確かめていないので、AR-016 にはまだ記録していない。

## 5. 残るリスク

- intent.md の新しい版を記録するまで、移行の検査と intent の照合は違反のまま。

## 6. 次

- 人の確認：intent.md の編集を終えたか。終えていれば AR-016 として記録する。
- 人の判断：DEC-316、DEC-305〜314。
- commit はしていない。
