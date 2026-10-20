# 作業記録 2026-10-20 第64便: DAC の最小・最大の変更と STATUS 周期（REV-096、DEC-159・160）

## 読んだもの

- コミット `33416021655e587d0ae5f2c949d9bf81698ef44e`（作業ツリーは未 commit の変更あり）。第63便の作業記録、model.yaml の PRM-43〜49、`firmware/gouda_esp32_v4/include/gouda_v4/config.hpp`（Config::valid）・`control.hpp`（dacCode）、`generated/params/gouda_monitor*.yaml`（PRM-15）。

## 人の指示（原文。DEC-159 に記録）

「中立2500mv, 最大4800mv最小200mvに変更する。／statusは500msとする。」

## 変更（REV-096。番号は reserve_ids.py で予約: REV-096、DEC-159・160、第64便）

- DEC-159（answered）を新しく登録。DEC-077 は書き換えず、PRM-44＝200 mV、PRM-45＝4800 mV を DEC-159 で置き換えた。PRM-43 は 2500 mV のまま。PRM-49＝500 ms を承認値に。
- DEC-160（pending）を登録: フルスケール PRM-46 の値と「x,y軸の合計値」の意味。
- 再生成: render_views.py、generate_params.py、render_migration_review.py。firmware_config.yaml に 9 項目すべてが入った。

## 食い違い（承認事項 DEC-160）

- 最大 4800 mV ＞ フルスケール 4700 mV。firmware の Config::valid は dac_max_mv ≤ dac_full_scale_mv を要求するため、この設定は不正で config_valid=0、DAC に書かない（安全側で止まる）。dacCode も 4095 で頭打ちになり、4700 mV を超える値は出せない。
- 設計検査（DR-01〜17）はこの関係を検査していない（違反 0 のまま）。検査ルールの追加は承認事項の候補（未登録）。

## 自律判断

- PRM-15 の stub 試験の仮値 0.25 s は、PRM-49＝500 ms より長いという関係を満たさないが、変えていない。stub 試験は firmware の仮値（50 ms）で動くため。PRM-15 の実車値は 500 ms より長くする必要があることを DEC-159 の note に書いた。

## 検査（作業ツリー）

- `design/.venv/bin/python design/tools/run_checks.py`: 終了コード 1。設計検査 合格 13・違反 0・未判定 4（DR-04 5、DR-05 2、DR-10 2、DR-11 59）。generate_params・intent_identity は合格。input_integrity・migration_validator・migration_tests の違反は第63便と同じ（drawio、extraction 内の .DS_Store）。この便の変更による違反はない。
- firmware のビルド・試験: 未実行。

## 原因の分類

- 修正ではない（人の指示の記録）。

## 残るリスク

- DEC-160 が決まるまで実車向け firmware は DAC に書かない。
- 4 つの電圧は人の指示の値で、測定値ではない（Q-03・DEC-050 の実機確認が残る）。

## 次に進められる作業・止まっている作業

- 止まっている: 実車向け firmware の書き込み（DEC-160 待ち）。
- 進められる: DEC-160 の回答の後、実車向けビルド（書き込みは人の許可の後）。
