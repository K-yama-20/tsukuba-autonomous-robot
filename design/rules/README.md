# 検査の範囲とルール一覧

三種類の検査を分けて実行する。いずれも設計承認・ROS動作確認・実車検証ではない。

| 検査 | スクリプト | 結果ファイル | 判定 |
|---|---|---|---|
| 入力の完全性（原資料・抽出・baselineのSHA-256） | `tools/run_checks.py`（input_integrity） | `reports/input_integrity.json` | 合格／違反 |
| 形式・移行忠実性 | `tools/validate_model.py` | `reports/migration_validation.json` | 合格／違反（既知問題は別集計） |
| 設計整合性 | `tools/check_design.py` | `reports/design_check.json` | ルールごとに 合格／違反／未判定 |
| 検査器の試験 | `python -m unittest discover -s design/rules` | `reports/migration_tests.txt` | 件数 |

実行: `design/.venv/bin/python design/tools/run_checks.py`（依存は `tools/requirements.txt`、仮想環境は `design/.venv`）。全体の記録は `reports/check_run.json`。

## 形式・移行忠実性（validate_model.py）

| 検査 | 根拠 | 合格の意味 |
|---|---|---|
| スキーマ適合（schema.json 1.1） | 依頼2・5 | 保存形式が有効 |
| 全ID重複・参照先・型（files/sources/entities/decisions/revisions） | 依頼2・5 | 台帳参照が壊れていない |
| 原文・根拠セル・フィールド参照 | 依頼3・5 | 既存抽出に忠実 |
| 198件およびCH4件の対応 | 依頼3 | 既存IDが保持されている |
| 図の全ID・接続端点・未接続線 | 依頼3・5 | 接続先を補完/欠落させていない |
| 未決問題・衝突の明示 | 依頼4・5 | 未解消事項を消していない |
| 4つの現在モード | intent.md:93 | 余分なソフトモードを追加していない |
| 入力全ファイルSHA-256 | 依頼1・5 | 原資料・抽出に書き込んでいない |
| baseline の凍結（snapshot.json） | 今回依頼1「初回移行baselineは変更しない」 | baseline ディレクトリが不変 |
| baseline 要素の保持と、追加・変更の記録（revisions） | 今回依頼6「モデルの差分」、CLAUDE.md 1.5「確定済みの判断を書き換えない」 | 削除なし。追加・変更は REV 記録と一致 |
| intent 新版の機械検証（authority_revisions） | 今回依頼1「差分が追記1文のみであることを機械的に確認」 | 旧版の保存コピー＋記録した追加行＝現ファイル。削除・変更行なし |
| 判断台帳の原文（answered は answer_verbatim 必須） | CLAUDE.md 1.1・1.3 | 回答のない承認を記録しない |
| 未確認（boundary）の要素が案・承認にならない | 今回依頼2 | 未確認要素を採用していない |

## 設計整合性（check_design.py）

| ルール | 内容 | 根拠 |
|---|---|---|
| DR-01 | 参照切れ・型不一致がない | 依頼5、CLAUDE.md 1.8 |
| DR-02 | 所有者不明がない（IFのデータ所有者、状態の所有者、TFの単独所有） | RQ-I059（intent.md:84）、RQ-I058（intent.md:83） |
| DR-03 | モード内の発行者競合がない（指令・データtopicとTF） | RQ-I004（intent.md:7）、RQ-I020（intent.md:26） |
| DR-04 | 状態遷移の整合（4モード、起動既定、到達可能性、必須7イベント、自律開始は人の操作のみ、各モードの復帰） | RQ-I065・RQ-I066・RQ-I025・RQ-I064、依頼4 |
| DR-05 | 要求の対応漏れがない（体験・Navigation・基本契約・個別要求の各行） | 依頼5、RQ-I061 |
| DR-06 | 非常停止検知・PC側非常停止機構を設計要素に含めない | RQ-I072（intent.md:100） |
| DR-07 | 未確認の境界要素を利用可能な機能として使わない | 依頼2 |
| DR-08 | 既存契約（手動優先・人の一時停止・ESP32中立化）を維持し参照している | RQ-I023・RQ-I026・RQ-I068・RQ-I024・RQ-I063 |
| DR-09 | 新しいモード・保護・承認操作を追加していない | RQ-I065・RQ-I027・RQ-I011 |
| DR-10 | 版依存IFを確定扱いしていない | RQ-I021、依頼4 |
| DR-11 | 実車値・未確定値を一般値で埋めていない（source_value は出典原文に数値があること） | RQ-I060、CLAUDE.md 1.5、依頼4 |
| DR-12 | 旧設計候補を自動採用せず、行全体の破棄・承認をしていない | 依頼3・4、CLAUDE.md 1.8 |
| DR-13 | 旧値の5 mを流用していない | 依頼4 |

未判定は、理由と解消手段（問題ID）を `reports/design_check.json` の `undetermined` に出す。未判定を合格に数えない。

## 試験

`test_validate_model.py`: 最小YAML（`fixtures/minimal.yaml`）＋意図的違反（`fixtures/violations.json`、ID重複・参照切れ・出典欠落）、承認根拠なし、未確定値0埋め、未接続の隠蔽、問題消失、原文改変、既存ID対応漏れ、未記録の追加・変更、baseline削除、intent改ざん・削除行の隠蔽、判断台帳の原文欠落。

`test_check_design.py`: 実モデルの複製に1件ずつ違反を注入（参照切れ、所有者欠落、同一モードでの二重発行、第5モード、自動での自律開始、必須イベント欠落、要求の対応漏れ、非常停止語、未確認要素の使用、契約の置換、人の承認の追加、版依存IFの確定扱い、一般値の記入、行全体の破棄、旧候補の承認、5 m流用）し、該当ルールが違反を返すことを確認。

baseline は `../baselines/migration_v1/`（凍結）。`build_migration.py` は初回移行専用で既存正本を上書きしない。モデルの変更は `revisions/REV-xxx.yaml` を `tools/apply_revision.py` で適用する。検査を通すための baseline 再生成・条件緩和は禁止。

| DR-14 | 判断台帳の項目がある | RQ-I073 |
| DR-15 | 設定値は正本で一度だけ宣言され生成物と一致 | RQ-I076 |

## DR-15 の検出項目と試験の対応（DEC-044）

| 検出項目 | 検出条件 | 試験 |
|---|---|---|
| 宣言先の欠落 | 設計パラメータ（adoption が designed_proposal／approved）に `declaration` がない | `test_parameter_without_declaration` |
| 宣言先・キー・型・適用時期の欠落 | declaration が ros_parameter／bt_xml／firmware_config 等で `target`・`param_key`・`value_type`・`apply_timing` のいずれかが空 | （上と同じ経路。`test_parameter_without_declaration` で検出） |
| 重複宣言 | 同じ `(target, param_key)` が 2 件以上 | `test_duplicate_parameter_declaration` |
| 生成物と正本の不一致 | `generated/params/*.yaml` が `generate_params.render(model)` の出力と一致しない | `test_generated_params_must_match_model` |
| ハードコード | 承認値（approved）と一致する数値リテラルが実装リポジトリの Gouda パッケージの `.py` にあり、同じファイルに `param_key` が無い → 未判定として報告 | 実装が無いため現在は対象 0 件（検査は実行される） |
| 正当な設定の非検出 | 別 target の同じキーは重複としない。実モデルは違反 0 | `test_legitimate_settings_not_flagged`、`test_real_model_has_no_violations` |
