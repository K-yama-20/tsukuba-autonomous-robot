# 作業記録 2026-11-07 第257便: 番号の予約を全 worktree で共有にする、worktree 運用の案（DEC-499）

## 読んだもの

- コミット `9c449b5`（ブランチ design/mppi-sim-2026-11-03）＋共有の作業ツリー（他のセッションの未コミットの変更を含む。2026-11-07 05:00〜05:40）。
- 便ごとのコミット（第255便）の後：`c37020e`（同じブランチ。`c88791d` が REV-281・DEC-499、`c37020e` がこの便の道具・試験・提案・作業記録と status.md の項）。
- この便のコミット（ブランチ design/mppi-sim-2026-11-03、push なし）
  - `c37020e`：第255便のセッションが作った、この便の 4 ファイル＋status.md の項。
  - 2 つ目（REV-283 の適用、update.sh、.gitattributes、試験、CLAUDE.md の控え、この作業記録）：ID は status.md の第257便の項と、次の作業記録に書く。
- `CLAUDE.md`（1.1〜1.12）、`design/reports/status.md` の冒頭、`design/tools/reserve_ids.py`、`design/rules/test_reserve_ids.py`、`design/tools/apply_revision.py`（適用の拒否の条件）、`design/tools/run_checks.py`、`update.sh`、作業記録 第220便・第250便。
- 車載 PC・ワークステーションには触れていない。Gouda は起動・停止していない。

## 人の指示（原文は DEC-499。第255便のセッションが記録する）

- 指示は 4 項目（便ごとのコミット、予約の印の共有化と PRM・IFD・ND の予約、worktree とブランチでの作業と統合、車載 PC への反映）。
- 同じ指示を受けたセッションが複数あった。担当を分けた。
  - 第255便のセッション：1（便ごとのコミット）と、指示の原文の記録（DEC-499、REV-281）。
  - この便：2（予約）と、3・4 の手順の案、CLAUDE.md の案。
  - ほかのセッション（3 つ）は手を引いた。

## 行ったこと

### 予約の道具（人の指示 2。実装）

- `design/tools/reserve_ids.py`
  - 印の置き場所を、git の common dir の下の `gouda-reservations/` にした（全 worktree で共有。コミットされない）。
  - PRM・IFD・ND を予約できるようにした（`--prm N --ifd N --nd N`）。
  - 次の番号は、共有の印、全 worktree の REV ファイル・model.yaml・status.md、旧い場所の印の最大＋1。
  - 旧い場所（`design/reports/reservations/`）の印は共有の場所へ写す。旧い場所からは消さない。
  - `--design` を足した（旧い版を持つ worktree から、新しい版の道具を呼ぶため）。
  - git の外（単体試験の一時フォルダ）では、前と同じ `design/reports/reservations/` に印を置く。
- `design/rules/test_reserve_ids.py`：10 件を足した。前からの 5 件は変えていない。
- 実際のリポジトリで 1 回実行した：`--label worktree-reserve-ids --bin --no-revision` → 第257便。旧い印 510 件が `.git/gouda-reservations/` に写った（実行後 514 件）。作業ツリーに新しい印は出なかった。
- 共有の作業ツリーの道具を直接変えたので、05:10 頃から、ここで予約する全セッションが新しい版で動いている。

### 案（提案。実装していない）

- `design/proposals/worktree_operation_2026-11-07.md`
  - CLAUDE.md の変更案（新しい節 1.14 と、1.1・1.5・1.9 の変更）
  - チャットの作業・統合・車載 PC への反映の手順の案
  - 必要な道具の案（`update.sh` の引数、`integrate_branch.py`、`.gitattributes`）
  - 人に決めてほしいこと Q1〜Q7、指摘 3 件
- CLAUDE.md は書き換えていない。

## 自律判断（理由）

- 結果の辞書に `prm`・`ifd`・`nd` の欄を、求めたときだけ入れる：前からの単体試験の期待値（3 欄の辞書）を変えないため。
- 旧い印を消さずに写す：旧い印は第255便のセッションがコミットに入れる予定で、こちらが消すとそのコミットと食い違うため。
- `run_checks.py` を実行しない：`design/reports/` と `design/generated/params/` を書き換える。第255便のセッションが同じ作業ツリーでコミットを作っている最中で、途中の変更を混ぜないため。

## 検査・試験（共有の作業ツリー、9c449b5＋作業ツリー）

| 内容 | コマンド | 結果 |
|---|---|---|
| 予約の単体試験 | `design/.venv/bin/python -m unittest design/rules/test_reserve_ids.py` | 15 件 OK（`reserve_ids.py` sha256 先頭 fd3c21820d1d48f2） |
| 設計の単体試験の全体 | `design/.venv/bin/python -m unittest discover -s design/rules -p 'test_*.py'` | 98 件のうち失敗 1 件（`test_validate_model.test_real_model`：`design/docs/SystemArchitecture.drawio` などの hash の不一致。予約の道具とは別。status.md に前からある drawio の FAIL と同じものかは未確認） |
| 実際のリポジトリでの予約 | 上の「行ったこと」のとおり | 第257便を取得 |
| 設計検査（`run_checks.py`） | — | 未実行（理由は上） |
| 実際の 2 つの worktree からの同時の予約 | — | 未実行（単体試験は、一時の git リポジトリと worktree 1 つで確かめた） |
| 車載 PC・ワークステーション | — | 未実行 |

- 三つの状態：移行が正確＝この便では変えていない。設計検査＝違反 0 件・未判定 5 件（REV-283 適用後）。実車投入可能＝人の判断待ち。

## 人の回答（DEC-501、原文）と、その後に行ったこと

- 質問：提案の Q1〜Q7 を推奨どおりで進めてよいか。回答：「推奨どおりで」。
- 変更セット `design/revisions/REV-283.yaml` に記録した（予約：REV-283、DEC-501）。
  - 最初の試し適用（`apply_revision.py REV-283 --dry-run --check`、9c449b5＋作業ツリー）：新しい違反 1 件（DR-01、basis_refs の DEC-499 が正本にない）。
  - 原因の分類：設計でも実装でもなく、適用の順序。DEC-499 を入れる REV-281（第255便）がまだ適用されていなかった。
  - `c37020e`（REV-281 適用済み）の上で適用した：`apply_revision.py REV-283` → 実体の追加・変更 0、決定 1 件（DEC-501）。
- Q7：`CLAUDE.md`（リポジトリの一つ上）を書き換えた。1.14 節の追加、1.1（作業記録の欄、status.md）、1.5（2 行）、1.9（リポジトリの外に置くもの）。追加 27 行、削除 1 行（1.1 の「読んだコミットID」を置き換え）。
  - 書き換える前の版の控え：`design/research/claude_md/CLAUDE.md.before_dec501_6d6b3096`。後の sha256 先頭：538f85b23507a8a5。
  - 提案の文との違い：1.14 に、Q1 の統合ブランチ名、「予約は Mac でだけ」、`bash update.sh <ブランチ> <コミット>`、Q3 の退避の方法を書き足した。1.5 に「REV を通さずに model.yaml を書き換えること」を足した（提案の 4.2 の対策の案）。
- Q5：`.gitattributes` に `design/reports/status.md merge=union` を足した。
- Q4：`update.sh` に `bash update.sh <ブランチ> <コミット>` を足した。引数なしの動きは変えていない。
  - origin からそのブランチを取得し、コミットがそのブランチにあることを確かめ、detached で checkout して `setup.sh` を実行する。
  - Gouda が動いているとき、管理下のファイルにローカルの変更があるときに止まるのは、前と同じ。
- 行っていないこと：push、車載 PC への接続・退避・checkout、Gouda の起動・停止、`README.md` の更新の節（他の便の未コミットの変更が重なっている）、Q6 の `integrate_branch.py`。

### 追加の試験

| 内容 | コマンド | 結果 |
|---|---|---|
| update.sh と union merge | `design/.venv/bin/python -m unittest tests/test_update_sh.py` | 9 件 OK（一時の git リポジトリと、代わりの setup.sh。Mac） |
| update.sh の文法 | `bash -n update.sh` | OK |
| 実際の車載 PC での update.sh | — | 未実行 |
| 設計検査（REV-283 適用後、c37020e＋作業ツリー） | `design/.venv/bin/python design/tools/run_checks.py` | 終了コード 1。design consistency：違反 0 件・未判定 5 件（合格 12 ルール）。input integrity・fidelity validator・unit tests の FAIL は前からのもの（`design/docs/SystemArchitecture.drawio` と `.DS_Store` 2 件の hash の不一致、`test_validate_model.test_real_model` も同じ原因）。generate params・intent identity は PASS |
| 本物の setup.sh とつないだ実行 | — | 未実行 |

- 試験の修正 1 件（原因の分類：試験。手順・試験基盤）：自分で書いた試験の、遠隔ブランチの一覧の比べ方が誤っていた。合否の基準（何も取得されていないこと）は変えていない。

## 残るリスク

- `update.sh` の新しい道は Mac の一時のリポジトリでしか試していない。車載 PC の git の版、single-branch の clone、ネットワーク越しの取得では未確認。
- detached で checkout した後に引数なしの `bash update.sh` を実行すると、main に切り替わる（前からの動き）。
- union merge は両側の行を残すだけで、順序と重複は保証しない。同じ行を両側が直した場合は両方が残る。

- 旧い worktree（dev-tab-vehicle-test、process-issue-workflow、別のセッションの scratchpad の worktree）の `reserve_ids.py` は旧い版。そこで直接動かすと番号が重なる。
- 共有の印は `.git` の中にある。Mac の clone を作り直すと消える。
- どの worktree にも checkout されていないブランチだけにある番号は数えない。
- 統合の手順の「REV の当て直しで model.yaml を作る」は未検証。第220便の、REV を通さない 22 欄の書き換えは再現しない。

## 欠番

- REV-282・DEC-500・第256便：別のセッション（つくばチャレンジ走行戦略）が予約して、使わないと連絡してきた。印は残る。

## 更新したファイル

- `design/tools/reserve_ids.py`（変更）
- `design/rules/test_reserve_ids.py`（変更）
- `design/proposals/worktree_operation_2026-11-07.md`（新規、提案）
- `design/reports/worklog/2026-11-07_bin257_shared_reservations_worktree_proposal.md`（新規）
- `design/reports/status.md`（第257便の項目）
- `design/revisions/REV-283.yaml`（新規、適用済み）、`design/model.yaml`（DEC-501）、`design/reports/check_run.json`・`migration_tests.txt`・`migration_validation.json`・`migration_validator.txt`（検査の結果）
- `update.sh`（変更）、`.gitattributes`（変更）、`tests/test_update_sh.py`（新規）
- `design/research/claude_md/CLAUDE.md.before_dec501_6d6b3096`（新規、控え）
- リポジトリの外：`CLAUDE.md`（変更）
- リポジトリの外：`.git/gouda-reservations/`（印 514 件）

## 次に進められる作業と、止まっている作業

- 進められる：各チャットが統合ブランチの先頭から worktree を切る（新しい版の道具が入っているので `--design` は要らない）。
- 止まっている
  - 車載 PC への反映：統合ブランチの push（人の指示）と、退避・checkout の実行の許可（人）。
  - `integrate_branch.py`（Q6）：REV の当て直しで model.yaml が再現するかの確認。
  - `README.md` の更新の節：統合の後。
