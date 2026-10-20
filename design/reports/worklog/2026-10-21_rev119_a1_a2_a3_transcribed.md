# 作業記録 2026-10-21 第87便: 分岐セッションの A1〜A3 の回答（転記）の反映（REV-119、DEC-182〜185）

## 読んだもの

- コミット `0f40106`（ブランチ design/field-mapping-2026-10-14。作業ツリーの変更は人のファイルだけ）。
- 転記（人がこのメインのチャットに貼ったもの）: 分岐セッションが人に示した A1〜A3 の判断材料と、人の回答の原文。
- `design/model.yaml` の ND-08・ND-10・M-013・M-014・M-021・M-033・M-039・DEC-123。`gouda_core/gouda_core/local_odometry_node.py`、`gouda_core/launch/gouda_core.launch.py`。作業記録 第61便。
- 詳細設計書: Google スプレッドシート（ID 1YsDMMmeVlaqwRGtAY7-fJNq4Pycb_bJa-KiKO9JsEwE）。人が URL を示して「これを読め。ローカルのxlsxは最新ではない」と指示した。内蔵ブラウザで開き、「モジュール定義」「使用モード定義」を gviz の CSV で読み取った（読み取りだけ）。最初にローカルの xlsx（`docs/architecture/`、2026-10-14 の保存）を読んだが、人の指摘で Google のシートに切り替えた（ローカルの写しには 41 行目の M-039 がない）。

## 人の回答（原文、分岐セッションからの転記）

- 「A1は案1でよい。」（DEC-182）
- 「A2: 推奨案で問題ない。」（DEC-183。(5) Hokuyo は DEC-184 で pending の質問として登録）
- 「A3: status.mdを今の状態に合わせて書き直して良い。」（DEC-185）
- 「メインのチャットで別の作業が進行中である為、今は何も変更を加えてはならない。後で指示します。」 → 第86便の commit・push の後に人がこの転記を貼ったので、それを着手の指示とした（AI の解釈。DEC-182 の note に記録）。

## 変更

- REV-119:
  - DEC-182〜185 を記録した。
  - ND-08: lifecycle を plain_node、process_group を gouda_core にした。責務（作り方）を実装に合わせた（/tf の odom_glim→base_link と最新の odom→odom_glim を合成し、直前の 2 つの姿勢の差から速度を出す。GLIM が止まっている間は出さない）。配置の理由に、常時起動でも車体指令は生まれないこと、lifecycle 化の判断は ND-07 の設計のときに行うことを書いた。
  - ND-10: 起動する server の名前（gouda_nav2.launch.py の 10 個）を責務に補った。
  - `apply_revision.py REV-119 --dry-run --check` の 1 回目は、4 件の新しい違反を出した。原因は 3 つ。ASCII のコロンを含む文が引用されていなかった（2 件）。pending の DEC の answer_verbatim が null だった。disposition が「pending」だった（正しくは open_human）。3 つを直した後の試し適用は、新しい違反 0・新しい未判定 0。そのあと本適用。
- 提案 `design/proposals/spreadsheet_change_requests_2026-10-21.md`: シートの変更案。自律走行の行から safety_supervisor・Safety_gate を外す。シートにない node の扱い。41 行目の GNSS を M-040 にする案。行の番号は CSV の順（空の行を飛ばす点を注記）で示した。
- `design/reports/status.md`: 後半（三つの状態、検査結果の件数、承認待ち・人の作業、原本未照合、次の作業、主要ファイルの場所）を今の状態に書き直した（DEC-185）。古い記述（DEC-160 の 4800 mV、REV-050 の時点の件数、回答済みの DEC-077・079 など）を除いた。

## 自律判断した変更（理由）

- ND-08 の active_in_mode_refs（MODE-AUTO・PAUSE）は変えなかった。出力が出る期間を表しており、責務の文で「node は常に起動、GLIM が止まっている間は出さない」と書き分けた。publishes・subscribes の参照（GLIM を含む ND-08 全体の IF）も変えなかった。
- 「使用モード定義」の「車両操作」の列（P ボタン）は、変更案に入れず注記だけにした。firmware の振る舞いとの差は判断台帳に未登録で、A2 の範囲の外のため。

## 検査・試験

- `design/.venv/bin/python design/tools/run_checks.py`（REV-119 の後）: 終了コード 1。設計検査は合格 12・違反 0・未判定 5（DR-04 5、DR-05 2、DR-10 2、DR-11 49、DR-15 30）。終了コード 1 の原因は入力の照合の不一致 2 件（drawio、.DS_Store。以前から）。
- コードは変えていないので、gouda_core の試験は実行していない（未実行）。

## 残るリスク

- シートの「使用モード定義」の P ボタンの記述と、firmware v4（deadzone の外を手動とする）の差は、台帳に未登録のまま。
- DEC-123 の ND-08 と、案 A3（Autoware の EKF）の役割が重なるかは未確認（推測）。ND-07 の設計で確かめる。
- 転記の発言は、このセッションでは人の発言を直接見ていない（分岐セッションの転記による）。

## 更新した生成物

- design/generated/ の各ビュー、design/generated/params/*（ハッシュの行）、design/migration_review.md、design/intent_index.yaml、design/reports/model_diff_rev-119.md と検査の結果のファイル。

## 次に進められる作業・止まっている作業

- 人の作業: シートの修正（変更案）、DEC-184 の回答。
- 止まっている: ND-07（DEC-115）、Nav2 の実車の値。commit・push は人の指示を待つ。

## 訂正（第88便、2026-10-21）

- 「終了コード 1 の原因は入力の照合の不一致 2 件（drawio、.DS_Store。以前から）」と、status.md の「不一致は 2 件」は誤り。`reports/input_integrity.json`（コミット 8f50ef5 の時点）の不一致は 3 件で、`design/docs/SystemArchitecture.drawio`、`design/docs/extraction_20261008_01a11af4/.DS_Store`、同じ場所の `raw_xlsx/.DS_Store`。不一致の一覧を数えるときに `raw_xlsx/.DS_Store` を見落とした。status.md は第88便で直した。
