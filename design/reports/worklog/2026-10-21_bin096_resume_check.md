# 第96便: 引き継ぎからの再開と、main の上での検査（2026-10-21）

## 読んだもの

- コミット：手元 `cefa92b`（design/field-mapping-2026-10-14）、origin/main `416a6d6`（名前を指定して fetch）。
- `design/reports/status.md`（第95便まで）、`reports/handover_2026-10-21_2.md`、作業記録 `2026-10-21_bin094_main_merge.md`、CLAUDE.md の 1 章。

## 人の指示（原文）

- 引き継ぎ（第95便）の本文を貼られた。それ以外の指示はない。

## 実行した検査

- `python3 design/tools/run_checks.py`。対象は origin/main `416a6d6` の一時的な写し（git worktree、作業ツリーを書き換えないため。実行後に削除）。終了コード 1。
  - 設計整合性：合格 12・違反 0・未判定 5（DR-04 5、DR-05 2、DR-10 2、DR-11 30、DR-15 30）。第95便の記録と同じ。
  - 入力の完全性：不一致 2 件。`design/docs/extraction_20261008_01a11af4/.DS_Store` と `raw_xlsx/.DS_Store` が「無い」（current_sha256 が null）。drawio は一致。
  - 検査器の試験：`test_validate_model.MigrationTests.test_real_model` が不合格（同じ原因）。
- gouda_core の単体試験・firmware のホスト試験：未実行（main と cefa92b のコードは同じ。cefa92b での結果は第93・89便）。

## 分かったこと（事実）

- 2 つの .DS_Store は `design/.gitignore` の 4 行目で無視され、git に入っていない（`git ls-files` で 0 件）。一方で入力の照合の baseline には含まれている。このため、手元以外の取り出し（VM・x86 機・新しい clone）では、入力の完全性の検査はいつも違反になる。
- 手元の作業コピーの不一致 3 件のうち、.DS_Store の 2 件は「中身の変化」ではなく、この baseline の作りに由来する、と推測する（手元の .DS_Store は Finder が書き換えるため）。drawio の 1 件は人の編集。

## 自律判断した変更

- status.md の「設計検査に合格」の行で、DR-11 の件数が「49 件」になっていたのを、要約行（`design_check.txt`）と表の値に合わせて 30 件に直した（記録の整合性の修正）。

## 承認事項・実測待ち

- 新しい台帳の項目は作っていない。上の .DS_Store の扱い（baseline から外す、または検査で .DS_Store を除く）は、検査ルールの緩和にあたるので承認事項（人に提示する。台帳への登録は人の返事の後）。

## 残るリスク

- 入力の完全性の検査が手元以外でいつも違反になるので、ほかの違反が埋もれる。

## 更新した生成物

- なし（検査は一時的な写しの上で行い、手元の `reports/*.json` は書き換えていない）。

## ブランチの切り替えと commit（人の指示）

- 人の指示（原文）：「手元を main（416a6d6）に切り替えて、第94〜96便の記録を新しいブランチで commit して。」「メアドはryoya-1@g.ecc.u-tokyo.ac.jpにせよ。push前に私にメアドを報告せよ」
- `git switch -c design/records-2026-10-21 origin/main`（main と cefa92b の差は README.md だけで、未 commit の変更はそのまま移った）。
- commit の作者：`~/.gitconfig` が aaa111aaa-111a <ryoya-1@g.ecc.u-tokyo.ac.jp> で、指示のアドレスと同じなので、設定は変えていない。
- commit したのは第94〜96便の記録（作業記録 2 件、引き継ぎ、予約 3 件、status.md）だけ。人のファイル（drawio 2 つ・xlsx・*.bkp）は変更のまま残した。push は未実行（人にメールアドレスを報告してから）。

## 次の作業

- 人の判断待ち（引き継ぎ §5）。止まっているもの：ND-07（DEC-115）、2D 地図（DEC-107・TS-34）、実車試験。
