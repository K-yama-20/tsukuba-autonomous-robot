# 作業記録 2026-10-20 第67便: DEC-160 の回答、実車向け firmware のビルド（REV-099）

## 読んだもの

- コミット `33416021655e587d0ae5f2c949d9bf81698ef44e`（作業ツリーは未 commit の変更あり）。`firmware/gouda_esp32_v4/platformio.ini`・`tools/gen_build_config.py`・`src/main.cpp`（setup の設定の読み込み順）・`test/host/run_host_tests.sh`。

## 人の回答（原文。DEC-160）

「最大を4720mv, 最低を280mv, フルスケールを4720とする。firmwareを修正し、ビルドするコマンドを生成せよ。」

## 変更（REV-099。番号は reserve_ids.py で予約）

- DEC-160 を answered。PRM-44＝280、PRM-45＝4720、PRM-46＝4720 mV。中立 2500 mV は変わらず、円の中心 2500 mV・半径 2220 mV。最大＝フルスケールで設定の検査に合格。
- 再生成: render_views.py、generate_params.py、render_migration_review.py。
- firmware のソースは変えていない。値はビルドのたびに gen_build_config.py が firmware_config.yaml から build_config.hpp（コミットしない）を作って入る。DEC-164（コメント「gain 1x」の修正）は人の回答がないため未実施。

## 検査・試験（作業ツリー）

- `design/.venv/bin/python design/tools/run_checks.py`: 終了コード 1。設計検査 合格 13・違反 0・未判定 4。移行の照合の違反は drawio と .DS_Store（以前から）。
- `~/.platformio/penv/bin/pio run -e esp32dev`: SUCCESS。生成ヘッダ has_config=true、trial=false、items = {2500, 280, 4720, 4720, 1000, 250, 800, 200, 500, 0}。
- `bash firmware/gouda_esp32_v4/test/host/run_host_tests.sh`: OK 256 checks。trial ファイルがないため承認値で実行された（read_flat はファイルがなければ空）。第18便の 274 checks と件数が違う。値に依存する繰り返しの回数の違いと推測（未確認）。
- `cd gouda_core && python3 -m pytest -q test/test_vehicle_core.py`: 12 failed・10 passed（FileNotFoundError、firmware_config.trial.yaml がない。第65便の追記と同じ。許可待ちで未修正）。
- 書き込み: 未実行（人が行う）。

## 原因の分類

- 修正ではない（回答の記録とビルド）。試験の不合格は第65便の追記のとおり、試験基盤の問題（未修正）。

## 残るリスク

- ESP32 の NVS に以前の設定（SET_CONFIG で登録した値や、卓上の試験の値）があると、起動時はビルドの値より NVS が優先される（main.cpp の setup）。PC の vehicle_bridge が接続時に firmware_config.yaml の値を SET_CONFIG で登録すれば置き換わる。書き込み前の flash の消去を人に提案した。
- DEC-162（EMC の入力が浮く）、DEC-161（実車の給電での実測）は未決。

## 次に進められる作業・止まっている作業

- 進められる: 人の書き込み → 卓上で TS-17〜19 の実機確認。
- 許可待ち: 試験基盤の修正（trial ファイル、案 A・B）、DEC-164。
