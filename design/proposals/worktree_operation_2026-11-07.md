# 提案：並列のチャットを git worktree で動かす運用（2026-11-07、第257便）

- 状態：**提案**（AI が作った案）。人の指示（原文は DEC-499）の 2〜4 への案。
- 2026-11-07 追記：6 節の Q1〜Q7 に人が「推奨どおりで」と答えた（DEC-501）。Q7（CLAUDE.md）、Q5（.gitattributes）、Q4 の update.sh の引数は実施した。push、車載 PC での実行、Q6 の道具は未実施。下の本文は回答の前の文のまま。
- 前提にしている未回答の項目：この文書の「6. 人に決めてほしいこと」の Q1〜Q7。回答で変わったら作り直す。
- 実施済みなのは「2. 番号の予約」の道具の変更だけ（人の指示 2 による）。それ以外（CLAUDE.md、update.sh、統合の道具、車載 PC）は何も変えていない。

## 1. 今の問題（確認した事実）

- 共有の作業ツリー 1 つに複数のチャットが書いていた。2026-11-07 05:00 の時点で、コミット 9c449b5 の上に未コミットの変更が 541 項目（変更 124 ファイル、未追跡 417 項目）あった。
- 製品コードと `drive_sim*` のほとんどは、複数の便の変更が同じファイルに重なっている（例：`nav2_config.py` は 16 便、`mode_manager_node.py` は 14 便の作業記録に出る）。
- `design/model.yaml`・`design/reports/status.md`・`design/generated/`・`design/reports/*.json` は、すべての便が書き足す。
- 車載 PC（x86）は、第220便の記録では、ブランチ dev-tab-vehicle-test の 9caaa65 にローカルの変更 99 件がある状態だった（今の状態は未確認）。
- `update.sh` は main だけを fast-forward で取り込む。統合ブランチのコミットを指定して反映する道はない。

## 2. 番号の予約（実施済み。人の指示 2）

- `design/tools/reserve_ids.py` を変えた。単体試験は `design/rules/test_reserve_ids.py`（15 件。前からの 5 件は変えていない）。
- 印の置き場所：git の common dir の下の `gouda-reservations/`（`git rev-parse --git-common-dir`。この clone の全 worktree で共有される。コミットも checkout もされない）。
- 予約できる番号：REV、DEC、便、PRM、IFD、ND（`--prm N --ifd N --nd N` を足した）。
- 次の番号＝次のうち最大のもの＋1
  - 共有の場所の印
  - 全 worktree（`git worktree list`）の REV ファイル名、model.yaml と REV ファイルの中の番号、status.md の便の番号
  - 旧い場所（各 worktree の `design/reports/reservations/`）の印。旧い印は共有の場所へ写す（旧い場所からは消さない）
- REV は、共有の印と、呼んだ worktree の `design/revisions/REV-NNN.yaml`（予約の注記だけ）の両方を作る。
- `--design <worktree の design>`：自分の worktree の写しが旧い版のとき、新しい版を持つ checkout の道具を呼んで、自分の worktree を指す。
- 限界
  - 共有の場所は 1 つの clone の中だけ。予約は worktree のある Mac でだけ行う。車載 PC・ワークステーションの clone では予約しない。
  - どの worktree にも checkout されていないブランチだけにあり、この道具で予約していない番号は数えない。
  - 旧い版の `reserve_ids.py` を worktree の中で直接動かすと、その worktree の中だけを見るので番号が重なる。

## 3. CLAUDE.md の変更案（人の承認の後に、人か AI が書き換える）

### 3.1 新しい節「1.14 worktree と番号の予約」（追加）

```markdown
### 1.14 worktree と番号の予約

- 並列のチャットは、チャットごとに自分の git worktree とブランチで作業する。共有の作業ツリー（統合ブランチの checkout）には書かない
  - 統合の担当のチャットだけが、統合ブランチの checkout に書く
  - 他のチャットの worktree のファイルは読むだけにする
- 番号（REV、DEC、便、PRM、IFD、ND）は、使う前に `design/tools/reserve_ids.py` で予約する。「最新の番号＋1」を自分で取らない
  - 予約の印は git の common dir（全 worktree で共有）に置かれる。印を手で作らない、消さない
  - 自分の worktree の `reserve_ids.py` が旧い版のときは、統合ブランチの checkout の版を `--design` を付けて呼ぶ
  - 予約して使わなかった番号は欠番にする。作業記録に書く
- 区切りごとに、自分のブランチにコミットする。push はしない（1.10）
  - コミットに入れるのは、自分の便のファイルだけ。`git add` は明示のパスで行う
  - 作業記録に、ブランチ名とコミット ID を書く
- 統合は、統合ブランチで merge する
  - model.yaml と生成物は、文字の merge の結果を使わない。merge の後に、取り込んだ REV を統合ブランチの model.yaml へ当て直し、生成物を作り直し、設計検査と単体試験を実行する
  - merge で衝突したコードを、どちらかの版で黙って上書きしない。衝突の一覧と解決の内容を作業記録に書く
- 車載 PC には、ファイルを手で写さない。統合ブランチのコミットを checkout して反映し、作業記録にコミット ID を書く
  - 反映の前に、車載 PC のローカルの変更を消さずに退避する
```

### 3.2 既存の節の変更

| 節 | 今の文 | 変更案 | 理由 |
|---|---|---|---|
| 1.1 作業記録 | 「読んだコミットID」 | 「読んだコミットID、作業したブランチ名、区切りで作ったコミットID」 | worktree ごとに起点が違う |
| 1.1 status.md | 「`design/reports/status.md` を短く更新する」 | 「自分のブランチの `status.md` には自分の便の項目だけを足す。件数と一覧の全体は、統合の後に統合ブランチで更新する」 | 全チャットが先頭に足すので、merge のたびに衝突する |
| 1.5 禁止事項 | （なし） | 「他のチャットの worktree・ブランチに書くこと、他のチャットの未コミットの変更をコミットに混ぜること」を足す | 人の指示 1 の「他のチャットの途中の変更は混ぜない」 |
| 1.9 ディレクトリ構成 | （なし） | 対応表に「予約の印：`.git/gouda-reservations/`（リポジトリの外）」と「worktree の置き場所」を足す | 置き場所が変わった |
| 1.10 | 「push と PR は、これまでどおり人の指示で行う」 | 変えない | 車載 PC への反映には統合ブランチの push が要る（Q4）。push のたびに人の指示を受ける |

## 4. 手順の案

### 4.1 チャットの作業（人の指示 3）

1. worktree を作る。起点は統合ブランチの先頭（Q1）。
   ```bash
   git -C <統合ブランチの checkout> worktree add ../tsukuba-worktrees/<話題> -b chat/<話題>-<日付> <統合ブランチ>
   ```
   - 置き場所は、既存の `tsukuba-worktrees/process-issue-workflow` と同じ、リポジトリの隣のフォルダ（Q2）。
   - `design/.venv` は worktree にはない（`.gitignore`）。python は統合ブランチの checkout の `design/.venv/bin/python` を絶対パスで呼ぶ。
2. 番号を予約する（2 節）。
3. 自分の worktree で、変更セット・コード・作業記録を書く。`apply_revision.py` と `run_checks.py` は自分の worktree で実行する（自分のブランチの中で検査が通ることを確かめるため）。
4. 区切りごとに、明示のパスで `git add` してコミットする。コミットの前に identity を確かめる。push はしない。
5. 統合の担当に、ブランチ名とコミット ID を知らせる。

### 4.2 統合（人の指示 3）

1. 統合ブランチの checkout で、チャットのブランチを `git merge --no-ff --no-commit` する。
2. 衝突の扱い
   - コード・試験：両方の変更を残す形で直す。直せないものは止めて、持ち主のチャットに戻す。
   - `design/model.yaml`、`design/generated/`、`design/reports/*.json`・`*.txt`、`model_diff_rev-*.md`：統合ブランチの側の版を取る（文字の merge の結果を使わない）。
   - `design/reports/status.md`：両方の項目を残す（Q5 の union merge を使えば自動）。
3. 取り込んだ REV を、番号の順に `apply_revision.py` で統合ブランチの model.yaml に当てる（`apply_revision.py` は同じ REV の二度目の適用を拒否する）。
4. `run_checks.py` を実行する（生成物の作り直しを含む）。単体試験を実行する。
5. 結果を作業記録に書いて、merge をコミットする。
- 未検証の点
  - 「REV を当て直すと、チャットのブランチで作った model.yaml と同じ内容になる」ことは、まだ確かめていない（別のセッションが試している）。
  - 分かっている例外：第220便は model.yaml の 22 欄を REV を通さずに書き換えた（証拠の sha256 15 件など）。こういう変更は当て直しでは再現しない。
  - 対策の案：REV を通さない model.yaml の変更を禁止する（1.5 に足す）。当て直しの後に、チャットのブランチの model.yaml との差分を取り、差があれば止める。
- 必要な道具（案。未実装、Q6）：`design/tools/integrate_branch.py`。上の 2〜4 を順に行い、差分があれば止める。

### 4.3 車載 PC への反映（人の指示 4。実行は人の許可の後）

AI が行うのは、人の「はい」の後だけ。Gouda の起動・停止は人が行う。

1. 状態を読む（読むだけ）：`/mode/state`、Gouda が動いているか、`git status --short`、`git rev-parse HEAD`、ブランチ名、`git stash list`。
   - Gouda が動いていたら止めて人に聞く（AI は `gouda.sh stop` をしない）。
2. ローカルの変更を消さずに退避する（Q3）。
   - a. 作業ツリーの全体（`.git` を含む。build・install・log は除く）を、リポジトリの外の日付つきのフォルダに tar で写す。sha256 を記録する。
   - b. `git status --short` と `git diff HEAD` の出力を、同じフォルダに保存する。
   - c. `git stash push --include-untracked -m "vehicle-pc-local-<日付>"` で作業ツリーを HEAD に戻す（stash は消さない）。
     - 無視されているファイル（`.env` など）は stash に入らず、その場に残る。a の tar には入る。
   - d. リポジトリの外にある控えは触らない。分かっているもの：x86 の車載 PC のホームの `deploy_bin217`・`deploy_bin236`・`deploy_bin241` の `backup/` と、名前が `backup_rev240_` で始まるフォルダ（別のセッションが、第215・217・236・241便のファイルを手で写す前の元の版を置いた。そのセッションからの連絡で、こちらは未確認）。
3. 統合ブランチのコミットを取り込む。
   ```bash
   git fetch origin <統合ブランチ>
   ```
   ```bash
   git switch --detach <コミット ID>
   ```
   - 車載 PC が取り込めるのは origin に push されたコミットだけ。push は人の指示で行う（Q4）。
4. `bash setup.sh` を実行する（依存とビルド）。
5. 退避したものと、反映したコミットとの差分を取り、車載 PC だけにあった変更の一覧を作る。人に示す（取り込むか捨てるかは人が決める）。
6. 作業記録に書く：反映したコミット ID、退避の場所と sha256、5 の一覧、setup.sh の結果。
- 必要な道具（案。未実装、Q4）：`update.sh` に、ブランチとコミットを指定する引数を足す（今は main だけ）。足すまでは、上の 3〜4 を手で打つ。
- 車載 PC は複数ある（VM と x86）。1 台ずつ、同じ手順で行う。x86 の模擬用の workspace（`~/gouda_ws_sim`）は対象にしない。

## 5. 先行事例（1.11）

| 探した場所 | 候補 | 採否 | 理由 |
|---|---|---|---|
| git の機能（`git worktree`、`git rev-parse --git-common-dir`） | common dir に共有の印を置く | 採用 | git の標準。追加のソフトなし。worktree の間で共有される場所として文書化されている |
| git の機能（`.gitattributes` の `merge=union`） | status.md の merge | 提案（Q5） | git の標準。両側の行を残す。順序は保証されない |
| git の機能（`.gitattributes` の `merge=ours` ドライバ） | model.yaml・生成物を統合側で取る | 不採用の案 | clone ごとに `git config` が要る。車載 PC の clone で設定がないと普通の merge になる |
| この リポジトリ（`tsukuba-worktrees/process-issue-workflow`、第220便の統合の記録） | worktree の置き方、番号の付け直しの表 | 参考にした | 第220便は番号が重なって 14 便・12 REV を付け直した。今回の共有の予約で防ぐ対象 |
| 公開の道具（YAML の構造 merge、ID の採番サービスなど） | — | 未調査 | — |
| 他チームのリポジトリ、論文、技術記事 | — | 未調査 | — |

ROS 2 Jazzy への対応・ライセンス・保守：採用したのは git の機能と Python の標準ライブラリだけで、該当なし。

## 6. 人に決めてほしいこと

| | 質問 | 推奨 | 代替 | 決まらないと止まる作業 |
|---|---|---|---|---|
| Q1 | 統合ブランチはどれか | 今の `design/mppi-sim-2026-11-03` を、今の checkout のまま統合ブランチにする | 新しいブランチ `integration/<日付>` を切る | 4.1 の起点、4.3 |
| Q2 | worktree の置き場所とブランチ名 | `tsukuba-worktrees/<話題>`、`chat/<話題>-<日付>` | アプリが作る `.claude/worktrees/` | 4.1 |
| Q3 | 車載 PC の退避の方法 | tar の写し＋`git stash push --include-untracked` | 退避用のブランチにコミットする（車載 PC に commit の identity が要る） | 4.3 |
| Q4 | 車載 PC がコミットを取り込む道 | 統合ブランチを origin に push し、`update.sh` にブランチ・コミットの引数を足す | main へ merge してから今の `update.sh` を使う（PR が要る） | 4.3 |
| Q5 | status.md を union merge にするか（`.gitattributes` に 1 行） | する | 便ごとに別ファイルにする（構成の変更） | 4.2 の自動化 |
| Q6 | `integrate_branch.py` を作るか | 作る（当て直しの再現の確認の後） | 統合の担当が手順どおり手で行う | 4.2 の自動化 |
| Q7 | CLAUDE.md の 3 節の案を入れるか | 入れる | 直して入れる | 規則の反映 |

## 7. 指摘（1.12。判断は人）

- ワークステーションと車載 PC（x86）での模擬は、今は Mac の作業ツリーのファイルを写して動かしている（第250便の記録）。人の指示 4 は車載 PC だけを対象にしている。模擬にも「コミットを checkout する」を適用するかは未定。適用するなら、チャットのブランチごとに push が要る。
- 旧い worktree（`dev-tab-vehicle-test`、`process-issue-workflow`、別のセッションの scratchpad の worktree）は、旧い版の `reserve_ids.py` を持つ。そこで予約すると番号が重なる。
- 共有の予約の印は git の外にあるので、Mac の `.git` を作り直す（clone し直す）と消える。そのときは、全ブランチのファイルから最大値を読み直す必要がある（道具は未対応）。
