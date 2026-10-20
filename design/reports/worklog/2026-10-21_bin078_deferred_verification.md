# 作業記録 2026-10-21 第78便: 「後で検証する項目」の文書を作り、VL-01 を追加

## 読んだもの

- コミット `33416021655e587d0ae5f2c949d9bf81698ef44e`（作業ツリーは未 commit の変更あり）。分岐セッション（local_802fcba2…）からの人の指示の転送。`gouda_vehicle/gouda_vehicle/hardware_bridge.py`（dtr・rts）、`design/generated/measurement_plan.md`、`design/docs/` の一覧。

## 人の指示（転送、転記）

「これの優先事項は低いが、試験する価値は高いと考える。後で検証する項目に追加してくれないか？適切な保存先が現在存在していないのなら、新たに保存先の文書を作っても良い。」

## 変更

- 新規 `design/docs/deferred_verification.md`（後で検証する項目）。適切な置き場がなかった（measurement_plan.md は PRM の実測の生成物で手編集不可、DEC-050 は車体・配線の実機照合）。VL-01「PC がシリアルを開くと ESP32 がリセットされるか」を、分岐セッションの机上の調査（事実と推測を分けた）、確かめていないこと、手順とともに記録。
- 正本（model.yaml）・コードは変えていない。番号は reserve_ids.py で予約（第78便）。

## 検査

- `design/.venv/bin/python design/tools/run_checks.py`: 終了コード 1。設計検査 合格 12・違反 0・未判定 5。新しい文書による違反・未判定はない。移行の照合の違反は以前から。

## 次に進められる作業

- VL-01 の試験（ESP32 だけ、約 5 分。人の協力）。
