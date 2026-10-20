# 作業記録 2026-10-21 第77便: DR-15 の走査の改訂（REV-110、DEC-175）、STATUS の uptime_ms の確認、USB の差し直しの改善案

## 読んだもの

- コミット `33416021655e587d0ae5f2c949d9bf81698ef44e`（作業ツリーは未 commit の変更あり。他のセッションの REV-107〜109 を含む）。`design/tools/check_design.py`、`design/rules/test_check_design.py`、`design/rules/README.md`、`firmware/gouda_esp32_v4/include/gouda_v4/control.hpp`・`src/main.cpp`、`gouda_core/gouda_core/vehicle_bridge_node.py`、`device_watch.py`。
- このセッションは分岐したセッション（元は local_6403013d…）。

## 人の指示（原文。DEC-175）

「・usbを差し直したときにvehicle_bridgeがesp32を認識できないのは大問題なので、改善策を考えてほしい。／・esp32のuptime_ms が STATUS を作った瞬間の値であるかどうかを確かめてほしい。／・検査器（DR-15）の調べる範囲が狭い件は修正してほしい。本番に謎の原因でgoudaが停止して、完走失敗となることが最も怖い。」

## 1. DR-15 の改訂（実装。人の承認 DEC-175）

- 新規 `design/tools/hardcode_scan.py`：コメント・docstring・文字列を除いたコードだけを走査。Python（tokenize）、C++・JavaScript（字句の簡易解析。HTML は script の中だけ）、シェル。報告は (1) 承認値と同じ数（小数は全言語、10 以上の整数は宣言の言語だけ）、(2) 待ち・期限・周期・再試行の行の 0 以外の数。同じ行の同じ数は 1 件。
- `check_design.py` の DR-15 の走査をこれに置き換え。旧来の「同じファイルに param_key があれば報告しない」例外は廃止。
- `hardcode_scan_roots.json` に scan（web、firmware の src・include、gouda.sh・setup.sh・update.sh）と exclude（生成ヘッダ build_config.hpp）を追加。roots（DR-17 も使う）は変えていない。
- 新規 `hardcode_allowlist.json`（空）。項目の追加は人の判断。一致しない項目は報告する。
- 試験 `HardcodeScanV2Tests` 6 件を追加。既存の `test_legitimate_settings_not_flagged` の最後の assert を「DR-15 の結果が合格」から「DR-15 の違反が 0」に変えた（REV-103 以降は未判定があり常に失敗していた。改訂後の DR-15 では未判定は人の判断の対象で、この試験の目的（正当な設定を違反にしない）は違反の有無で表す）。合否の基準を緩める変更ではないと判断したが、試験の期待値の変更なので人に報告する。
- `rules/README.md` の DR-15 の表を更新。
- 番号: reserve_ids.py で REV-110・DEC-175・第77便。作業中にコードへ先に書いた「DEC-173」は他のセッションが使っていたため DEC-175 に書き換えた。

## 2. STATUS の uptime_ms（調査のみ）

- `control.hpp` の sendStatus は payload の 36〜39 バイトに `now_` を入れる。`now_` は Core::tick(now) の最初に設定され、tick の中で sendStatus を呼ぶ。main.cpp の loop は最初に `now = millis()` を取り、BT の処理の後に tick(now) を呼ぶ。
- したがって uptime_ms は「その loop の始めの millis()」で、STATUS の中身（出力の主・電圧・DAC のコード）を決めたのと同じ時刻（1 ms 単位）。実際にシリアルへ書くのは同じ loop の後半（Serial.write）で、その差は loop の処理時間だけ。
- GET_STATUS への応答も、受信を処理したときの now_（feed(now)）。
- フレームの header の時刻（encodeFrame に now_）も同じ値。
- 結論: uptime_ms は STATUS を作った時刻（ESP32 のタイマー）。試験・実機での確認は未実行（コードを読んだだけ）。

## 3. USB の差し直しの改善案（提案。実装していない）

- 現状: SerialTransport の受信スレッドは、読み出しが例外になると 0.5 s ごとに再試行するだけで、ポートを開き直さない。差し直すとデバイスは同じ by-id の名前で戻るが、古いファイル記述子のままなので、configure をやり直すまで通じない。
- 案: (1) 読み出し・書き込みの失敗、または by-id のリンクの消失で「切断」と判断し、ポートを閉じる。(2) by-id の名前の再出現を見張る（sensor_supervisor と同じ device_watch の同一性。イベントまたは短い間隔の確認）。(3) 再出現したらポートを開き直し、HELLO・SET_CONFIG からセッションを始め直す（ESP32 は USB の給電で再起動する見込み。boot_token が変わる）。(4) lifecycle の状態は変えない（active のまま再接続）。切断の間は COMMAND を送れず、firmware は PRM-13 で中立になる。(5) 切断・再接続を DecisionEvent に記録し、monitor に表示（同種は ×N）。(6) 自律走行中の切断を一時停止にするかは承認事項（mode_manager が vehicle_bridge の状態を見ていない）。
- 確かめること: pyserial はポートを開くと DTR・RTS を立てる。ESP32-DevKitC の自動リセットの回路で、開くたびに ESP32 が再起動するか、書き込みモードに入らないか（実機で未確認）。

## 検査・試験（作業ツリー）

- `design/.venv/bin/python design/tools/run_checks.py`: 終了コード 1。設計検査 合格 12・違反 0・未判定 5（DR-15 19 件、DR-04 5、DR-05 2、DR-10 2、DR-11 50）。
- 検査器の試験（run_checks の unit tests）: 79 件中 1 件失敗（test_validate_model.MigrationTests.test_real_model。drawio・intent.md の人の編集による移行の照合の違反で、以前から）。HardcodeScanV2Tests 6 件を含む test_check_design.py は 38 件すべて合格。

## DR-15 の 19 件（許容の一覧は空）

- 承認値と同じ数: glim_runner.py:146（sleep 0.2）、map_convert.py:143・303（0.5）、map_creator_node.py:79（0.1）、speed_mask.py:66・67・76（0.5）、vehicle_bridge_node.py:68（timeout 0.05）・79（sleep 0.5）。
- 時間の値: gnss_calibration.py:180（/2）、monitor_server.py:63（join 5）、septentrio_query.py:86（sleep 0.01）、vehicle_bridge_node.py:96（join 1）、main.cpp:20（5 ms）・98（delay 1）、gouda.sh:101（seq 1 20、sleep 1）・119（sleep 1）、setup.sh:53（--retry 3）。

## 次に進められる作業・止まっている作業

- 人の判断: 19 件を許容の一覧に入れるか（理由つき）、設定にするか。USB の差し直しの案の実装の許可と (6) の承認。
