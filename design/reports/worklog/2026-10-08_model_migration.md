# 抽出結果から下位設計モデルへの移行

作業対象はスキーマ・既存情報のモデル移行・出典対応・矛盾整理・移行検査。最新の依頼とintentを上位とし、新しい詳細設計、ROS Node実装、完成図表生成は行っていない。

確認したもの：`design/intent.md`（97行）、既存抽出README・Excel行/セルの既存抽出・定義ID一覧・drawio要素抽出・48項目の検証結果・原本ハッシュ、CLAUDE.md、status.md、workspaceと実装リポジトリ構成。元Excel/drawioの抽出は再実行していない。今回の出典・原文照合は既存抽出を読み、原資料のバイト同一性はハッシュで確認した。

workspaceのdesignはロボット実装リポジトリの外。確認時の`tsukuba-autonomous-robot` HEADは `a091ed39eb154b2dff7065840dc13c6478b153da`。実装側の既存変更 `docs/architecture/Gouda_architecture_detail.xlsx`、`docs/architecture/SystemArchitecture.drawio`、未追跡バックアップには触れていない。モデル成果物をcommit/pushしていない。

## 自律判断と根拠

- ユーザー指定の`design/model.yaml`を使用。CLAUDE.mdの複数ファイル推奨より今回の単一ファイル指定を優先した。
- 原文をsourcesに一度だけ置き、各設計項目から参照する。各行の原区分と下位設計の状態を別管理し、原区分「確定の明示なし」は人の承認待ちへ一括変換しない。
- 198件の定義IDを保持。行抽出に存在するCH-01〜CH-04は旧ID抽出パターンの対象外だったため、202件対応表で別枠にした。既存成果物には書き込んでいない。
- IDなしモジュール行にM-039、その他のIDなし項目に固定IDを割当。初回registryを保存。図のIDはページ+元要素IDと対応させ、意味的な同一性を推測して統合しない。
- パラメータの具体値、Node分割、process配置は未設計として保持。旧原文のパラメータ群24件を個別実車値へ推定変換していない。
- 最新intentによる変更/具体化13件と、未解消の資料衝突3件を分離。変更対象モジュールから分離した保持状態・故障応答・実行配置・パラメータにも同じC番号参照を継承し、派生項目だけで旧仕様を採用する抜け道を防いだ。
- 接続先IDのない線はU-DRAW-001。targetPointを保持し、接続先参照はnullのまま。非常停止検知線、heartbeat/collision_stop、旧変更記録と現在図の時点差は別問題にした。

## 問題・未設計

問題25件：技術12、人の判断7、資料不足6。人の判断はQ-04/Q-05/Q-06/Q-07/Q-10/Q-12/H-001だけに選択肢・推奨・影響IDを付けた。復旧回数上限は値未提示のためQ-05へ含め、SpeedLimit発行手段はintentが明示する人の承認としてH-001に記録。採用Nav2版未定のため発行方式そのものの推奨は未定と明記し、方式比較後の承認を推奨手順とした。

原資料で未実施の25試験を試験済みにしていない。モデル629要素、出典486件。未設計364、案265、下位設計承認済み0。これらは図要素等も含む台帳件数であり、設計進捗率ではない。

## 実行した検査

正確なコマンド、終了コード、実行時刻、検査対象モデルとスクリプトのSHA-256は`../migration_check_run.json`に記録。対象Git HEADは上記。design成果物自体はGit外のため、対象版をファイルハッシュで識別する。

今回の環境：バンドルPythonと一時依存`/private/tmp/gouda-model-deps`。YAML/JSON Schemaライブラリが標準環境に無かったため一時フォルダへruamel.yaml/jsonschemaを取得。既存環境へ上書きせず、依存バージョンをrequirements.txtに固定した。

```sh
cd /Users/AYARyoya/Desktop/自己学習/TsukubaChallenge
PYTHONPATH=/private/tmp/gouda-model-deps /Users/AYARyoya/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 design/tools/run_migration_checks.py
PYTHONPATH=/private/tmp/gouda-model-deps /Users/AYARyoya/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 design/tools/render_migration_review.py
```

- 形式・移行検査5,316比較/規則、違反0。入力全ファイルの変更なし、198/198対応、追加CH4件、原文・出典・図の全要素と端点を確認。
- 検査器試験20件合格。人工の小さなYAMLでID重複・参照切れ・出典欠落等を検出。実モデルのコピーに原文改変、既存ID対応の削除、問題の削除、接続先の推測補完、派生項目の置換参照欠落を注入して検出。
- 設計妥当性：未判定。実車試験・ROS動作・Nav2採用版確認・新詳細設計：未実行。
- 前段の48項目一致は別の抽出忠実性結果。今回の形式/移行検査合格から設計整合性・実車可否を推定しない。

原因分類：環境のライブラリ不足は移行ツール用依存の配置で解消。原資料の衝突・不足は仕様/資料の問題として台帳へ保持。検査条件を緩めたり、旧情報を削除したりして合格にしていない。

## 成果物と境界

新規：schema.json、model.yaml、migration_manifest.json、migration_review.md、移行/検査/報告スクリプト、検査器試験と人工データ、検査結果。status.mdは今回の状態を追記し、大会遵守事項の既存記録を保持した。完成版の図表は生成していない。

今回の移行は完了。次段階の技術事項には進めるが、今回依頼では着手しない。人の決定や資料不足に依存する項目はそのIDに限定して未確定とする。原資料・intentは人の所有物として保全済み。
