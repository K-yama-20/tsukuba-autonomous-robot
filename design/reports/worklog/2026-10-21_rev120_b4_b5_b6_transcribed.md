# 作業記録 2026-10-21 第88便: 分岐セッションの B4〜B6 の回答（転記）の反映（REV-120、DEC-186〜190）

## 読んだもの

- コミット `8f50ef5`（ブランチ design/field-mapping-2026-10-14。作業ツリーの変更は人のファイルだけ）。
- 転記（人がこのメインのチャットに貼ったもの）: 分岐セッションが人に示した B4〜B6 の判断材料と、人の回答の原文。
- `design/docs/deferred_verification.md`、作業記録 第71便（rev104）・第83便（bin083）、`design/tools/apply_revision.py`、`design/rules/`（README と既存の試験）、`design/tools/hardcode_scan.py`・`hardcode_allowlist.json`、`design/reports/design_check.json` の DR-15。
- コード: `firmware/gouda_esp32_v4/include/gouda_v4/control.hpp:31-46`（mapVoltage）、`gouda_core/gouda_core/esp32_sim.py:53-68`、`gouda_core/test/test_vehicle_core.py`、DR-15 の各行（glim_runner.py、map_creator_node.py、gouda.sh、setup.sh、monitor_core.py、vehicle_bridge_node.py、main.cpp など）。

## 人の回答（原文、分岐セッションからの転記）

- 「B4: さしあたっては案Aを採用し、保留とする。これは後の試験事項としてしかるべき文書に保存せよ。どの文書に保存したか報告せよ。」（DEC-186）
- 「B5: A案を採用」（DEC-187）
- 「B6: A案を採用」（DEC-188）
- 転記には「メインのチャットで別の作業が進行中である為、今は何も変更を加えてはならない。後で指示します。」もある。第87便の commit・push の後に人がこの転記を貼ったので、それを着手の指示とした（AI の解釈。第87便と同じ扱い）。

## 変更

- REV-120（正本の要素は変えない）: DEC-186〜188 を answered、DEC-189（DR-15 の許容の一覧の案の承認と走査器の修正）・DEC-190（gouda.sh の PRM-77 の写し）を pending で登録した。`--dry-run --check` は新しい違反 0・新しい未判定 0。そのあと本適用し、再生成した。
- B4: `design/docs/deferred_verification.md` に VL-02 を追加した（表の行と節。VL-01 の書き方に合わせた）。承認値での斜めの 4 方向の出力を、Python の模型で計算して書いた。(1,1)→(4069, 4070)、(1,−1)→(4069, 930)、(−1,1)→(931, 4070)、(−1,−1)→(931, 930) で、x の振れ幅がいつも 1 mV 小さい。
- B5:
  - `design/tools/apply_revision.py` に引数 revisions_dir（既定は今までと同じ `design/revisions`）と、終了の判定の関数 has_new_violations を足した。コマンドの振る舞いは変えていない。
  - 試験 `design/rules/test_apply_revision.py`（4 件）を追加した。変更セットは一時ディレクトリに置き、共有の作業ツリーの `design/revisions/` には書かない。確かめることは 4 つ。(1) 正しい変更セットは、新しい指摘が 0 で、model.yaml・schema.json を書かない。(2) 空の source_refs が DR-01 のスキーマの違反として出る。(3) recorded の決定を承認の根拠にすると、DR-01 の APPROVAL_EVIDENCE として出る。(4) 未判定だけでは失敗にしない。
  - `design/rules/README.md` にこの試験を書き足した。
- B6:
  - DR-15 の 30 件を 1 件ずつ分類した。時間の値（B6 の 8 項目）9 件、偶然の一致 18 件、PRM の写し 1 件（gouda.sh:119 の sleep 1＝PRM-77）、8 項目にない値 1 件（setup.sh の curl --retry 3）、走査器の誤検出 1 件（setup.sh:148。ダブルクォートの中のシングルクォートの取り違えで、文字列の中の PRM-50 の 50 を拾う）。
  - 許容の一覧の案（28 件）を `design/proposals/dr15_allowlist_proposal_2026-10-21.md` に書いた。`hardcode_allowlist.json` は変えていない（DEC-189 の承認の前）。

## 自律判断した変更（理由）

- apply_revision.py に revisions_dir を足した。試験の変更セットを共有の作業ツリーの `design/revisions/` に置くと、ほかのセッションの番号の予約や変更セットと混ざるため。既定の値は今までと同じなので、コマンドの振る舞いは変わらない。
- 許容の一覧の案には、偶然の一致 18 件も入れた。DR-15 を合格にするには一覧か走査器の変更が要り、B6 の案 A（30 件を分類して一覧の案を作る）の範囲と読んだ。承認は DEC-189 で、まとめて求める。

## 承認事項・実測待ち

- DEC-189（pending）: 許容の一覧の 28 件と、走査器の修正。
- DEC-190（pending）: gouda.sh の PRM-77 の写し。推奨は、生成物から読むこと。
- 人に確認すること: DEC-186 の「案Aを採用」が、VL-02 の試験の追加（承認値で x と y の差が 1 mV 以内であることを確かめる。期待値の変更ではない）の許可に当たるか（DEC-106）。
- 承認の材料（DR-15 の 24 番）: firmware の 5 ms は、出力を決める処理を呼ぶ間隔で、出力の経路の上にある（時間切れの判定の刻み）。分岐セッションの説明「どれも指令の経路・安全の期限に関わらない」は、この 1 件については正確でない。提案の注に書いた。

## 検査・試験（コミット 8f50ef5 ＋ この作業ツリー）

- `design/.venv/bin/python -m unittest design/rules/test_apply_revision.py`: 4 件合格（約 28 s）。不合格側の 2 件は、狙った誤りの文言（source_refs の non-empty、APPROVAL_EVIDENCE PRM-78）で検出されることを、出力を表示して確かめた。
- 許容の一覧の案の確認: 案の 28 件をメモリの上で scan に与えた。28 件がすべて使われ、残るのは 28 番（PRM-77）と 30 番（誤検出）の 2 件だけ。一覧のファイルには書いていない。
- `design/.venv/bin/python design/tools/run_checks.py`（REV-120 の後）: 終了コード 1。設計検査は合格 12・違反 0・未判定 5（DR-15 は 30 のまま）。検査器の試験は 83 件中 1 件不合格（test_real_model。入力の照合の不一致と同じ原因で、以前から）。入力の照合は 76 件のうち一致 72・intent の新版 1・不一致 3（drawio、.DS_Store 2 つ）。
- gouda_core の試験: コードは変えていないので未実行。

## 訂正

- 第87便で status.md と作業記録に「入力の照合の不一致 2 件」と書いたのは誤り。正しくは 3 件（`raw_xlsx/.DS_Store` を見落とした）。コミット 8f50ef5 の時点でも 3 件。status.md を直し、第87便の作業記録に訂正を追記した。

## 残るリスク

- VL-02 の 1 mV が実車に影響するかは、未測定（推測で小さい）。
- 検査器の試験が約 28 s 長くなった（run_checks の全体で約 72 s）。

## 更新した生成物

- design/generated/ の各ビュー（pending の一覧など）、design/generated/params/*（ハッシュの行）、design/migration_review.md、design/reports/model_diff_rev-120.md と検査の結果のファイル。

## 次に進められる作業・止まっている作業

- 人の回答待ち: DEC-189、DEC-190、VL-02 の試験の追加の許可。
- commit・push は人の指示を待つ。
