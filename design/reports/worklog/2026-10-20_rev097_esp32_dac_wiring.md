# 作業記録 2026-10-20 第65便: ESP32 の DAC 出力と基板の配線の実測の記録（REV-097、DEC-161〜164）

## 読んだもの

- コミット `33416021655e587d0ae5f2c949d9bf81698ef44e`（作業ツリーは未 commit の変更あり）。
- 分岐したセッション（local_d45b61f7…）からの引き継ぎのメッセージ（人の指示「元のセッションで記録させる」による）。`firmware/gouda_esp32_v4/include/gouda_v4/control.hpp`（mapVoltage、dacCode）、`src/main.cpp`（writeDac のコマンド値）、`config.hpp`（Config::valid）。

## 引き継ぎの扱い

- 引き継ぎの「0. 状態」の未実行・未作成（run_checks、第63便の作業記録、status.md）は、このセッションで第63便として済ませていた。その後に DEC-159（REV-096）を記録済み。引き継ぎにある PRM-49 の「未決定」と、円の中心 2465 と中立 2500 のずれ（候補 c）は、DEC-159（最小 200・最大 4800 で中心 2500、STATUS 500 ms）で解消済み。そのため候補 c・e は登録していない。
- 人の発言・実測値は引き継ぎからの転記。このセッションは直接見ていない。図面は読み直していない（原本未照合）。証拠ファイルに明記した。

## 変更（REV-097。番号は reserve_ids.py で予約: REV-097、DEC-161〜164、第65便）

- 証拠 `design/research/vehicle_pc/2026-10-20_esp32_dac_wiring_measurement.md`（FILE-ESP32-DAC-WIRING-20261020）を登録。
- 新規（pending）：DEC-161（実測：フルスケールと USB 5V への依存。候補 a・b）、DEC-162（承認・実測：R7 除去後に EMC の入力が浮く。候補 d、安全）、DEC-163（承認：RQ-I020 の補足。候補 f）、DEC-164（承認＝実装の許可：コメント「gain 1x」の修正。候補 g）。
- 追記：DEC-160（人の補足の転記、円の中心と半径、4800 mV は今の給電では出せない）、DEC-050（照合項目の追加。候補 i）、ND-17・PRM-46 の解釈（候補 h の記録）。
- 再生成: render_views.py、generate_params.py、render_migration_review.py（params の値は変化なし）。

## 自律判断

- 記録した側で確かめた事実：writeDac のコマンド値 0x1000・0x9000 は GA=0（2 倍）、mapVoltage の円の中心は (最小＋最大)/2。それ以外（実測、図面の読み取り）は転記。
- コード・設定は変えていない（DEC-164 は許可待ち）。

## 検査（作業ツリー）

- `design/.venv/bin/python design/tools/run_checks.py`: 終了コード 1。設計検査 合格 13・違反 0・未判定 4。generate_params・intent_identity は合格。移行の照合の違反は drawio と extraction 内の .DS_Store（第63・64便と同じ。この便の変更が原因ではない）。
- firmware のビルド・試験: 未実行。

## 残るリスク

- DEC-162：電源断時に EMC の入力が浮く。EMC-270 の振る舞いは不明で、安全の根拠がない。
- 実測の条件（PC・ケーブル・テスター）が欠けている。

## 次に進められる作業・止まっている作業

- 止まっている: 実車向け firmware の書き込み（DEC-160・161）、実車の走行試験（DEC-162）。
- 人に確かめる: X の空中配線の先と R5・R6、リレーと JP2・JP3、測定の条件、ESP32 の電源断時の車体の振る舞い。

## 追記: REV-095・096 の後の単体試験の不合格（分岐セッションの報告を再現）

- `cd gouda_core && python3 -m pytest -q test/test_vehicle_core.py`（作業ツリー、2026-10-20）: 12 failed・10 passed。原因は FileNotFoundError: firmware の 9 項目がすべて承認値になり、generate_params.py が `firmware_config.trial.yaml` を作らなくなった。`test_vehicle_core.py:36` はこのファイルがある前提で読む。
- 原因の分類: 試験基盤（試験が trial ファイルの存在を前提にしている）と、変換スクリプト（全項目が承認されると trial ファイルを作らない）の食い違い。合否の基準は変えずに直せるが、コードの変更なので人の許可待ち（未修正）。
- 読み込みを直しても、承認値（最大 4800 ＞ フルスケール 4700）は設定として不正なので、有効な設定を前提にする試験は DEC-160 が決まるまで通らない見込み（推測、未実行）。
- 同じ前提を持つもの（未確認）: `gen_build_config.py --trial`（esp32dev_trial のビルド）、`esp32_sim_pty --trial`、`stack.sh`（trial:=true）、vehicle_bridge の trial 読み込み。
