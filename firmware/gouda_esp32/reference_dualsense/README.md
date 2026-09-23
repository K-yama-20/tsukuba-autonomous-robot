# Joystick270 DualSense control

## 現在の状態

2026-09-20：通信・DAC出力・円形制限・通信途絶処理を実装し、ESP32向けビルドとホスト上の制御計算テストが成功。実機への書き込みとDualSense実接続は未実施。

電圧範囲0.23〜4.7 V、停止2.5 V。右へ倒すとR1の電圧上昇、前へ倒すとR2の電圧上昇。ユーザー回答を反映して操作を有効にした。

既存の `Joystick270_SerialControl` と他の試験プロジェクトは変更していない。

### 再起動後の再接続修正（reconnect-fix-1）

初版は接続コールバックで `isGamepad()` を調べ、falseなら切断していた。Bluepad32では、機種情報が確定して接続通知が来ても、最初のHID操作レポートはまだ届いていない場合がある。`isGamepad()` はそのレポートのクラスを参照するため、正しいDualSenseをこの時点で拒否してしまう競合があった。

接続時はプロパティのPS5機種情報だけで対象を判定し、`isGamepad()` の確認を操作データ受信時へ移動した。最初の有効な入力が届くまでは2500 mV指令を保持する。保存ペアリングキーの削除は行わない。

操作レポートより接続通知が先に来る模擬テストを追加し、初版で失敗、修正版で成功することを確認。ESP32を実際に電源再投入した再接続の成功は、ユーザー実機での再確認待ち。

書き込み後に `BOOT reconnect-fix-1` が表示されることを確認し、ペアリング済みのDualSenseでESP32電源再投入→PSボタンによる再接続を試す。改善しない場合は、起動から接続失敗までの115200 bpsシリアルログを確認する。

## 確定した動作

- 対象は従来型ESP32（`esp32dev`）。DualSenseはBluetooth Classicを使うためESP32-S3/C3等へはそのまま移植しない。
- MCP4922 A → R1 → X：左右旋回。B → R2 → Y：前後進。
- 車両向け出力はJ1-5が左右旋回、J1-4が前後進、J1-2が信号GND。J1-6/3はそれぞれ純正ジョイスティックのX/Yを受ける入力側。
- 起動時、SPI初期化直後に両軸2500 mV指令を書き込む。Bluetooth APIの接続設定はその後。
- 2500 mVはソフトウェアの指令。電源投入からコード実行前までの端子電圧や、車両接続時の実電圧を保証するものではない。最大4700 mVという従来の仮校正を継承している。
- リレーは物理的にバイパスされた現構成を対象とし、GPIO32はLOWのまま。
- GPIO21/22はINPUT_PULLUP。ADC読取り機能は付けない。
- 操作入力は左スティック。中央の半径8%を無操作域とし、その外側を連続的に0〜100%へ変換する。
- 接続・再接続後は、一度左スティックを中央に戻した受信データを確認してから操作を受け付ける。
- 切断、または有効なコントローラ入力の更新が250 ms以上途切れたときは両軸2500 mV指令に戻す。更新再開後も一度中央を確認する。
- PS5型として認識されたゲームパッド1台を受け付ける。タッチパッドの仮想マウスは無効。ボタンに走行機能は割り当てない。
- ペアリングキーを起動ごとに消去しない。初回ペアリング後の再接続に利用する。

## 電圧平面での円形制限

円の中心は(2.465 V, 2.465 V)、半径2.235 V。指令値は次を満たす。

```text
(X - 2.465)^2 + (Y - 2.465)^2 <= 2.235^2
```

停止点は円の中心から両軸とも35 mVずれた(2.500 V, 2.500 V)。停止点からスティック方向へ引いた線と円周の交点を求め、スティック量に比例してその線上を移動する。これで停止2.5 Vを維持し、出力領域も真円に収める。最後の整数mV丸めでも円外へ出ないよう補正する。DACの量子化と実際の電圧誤差は別途存在する。

| 左スティック | X / R1指令 | Y / R2指令 |
|---|---:|---:|
| 中央 | 2.500 V | 2.500 V |
| 右いっぱい | 4.699 V | 2.500 V |
| 左いっぱい | 0.231 V | 2.500 V |
| 前いっぱい | 2.500 V | 4.699 V |
| 後いっぱい | 2.500 V | 0.231 V |
| 右前45度いっぱい | 約4.045 V | 約4.045 V |

単軸の端が0.230/4.700 Vぴったりではないのは、もう一方の軸を円の中心2.465 Vではなく停止2.500 Vに保つため。

## 初回ペアリングと次回以降

1. ESP32でこのファームウェアを起動する。
2. USBケーブルを抜いたDualSenseで、CreateボタンとPSボタンをライトバーが点滅するまで長押しする。
3. シリアルに `DualSense connected` が出ることを確認する。
4. 次回以降は保存されたキーで再接続する。DualSenseがOFFならPSボタンで起動する。ESP32から電源OFFのコントローラを起こす機能はない。

コントローラがPS5やPCなど別の接続先を選んでいる場合、その接続を切り、必要ならESP32と再ペアリングする。新しいDualSenseの複数接続先スロットはコントローラ側でESP32に対応するものを選ぶ。

## ビルド

```sh
/Users/AYARyoya/.platformio/penv/bin/pio run -d "/Users/AYARyoya/.codex/.chatgpt-projects/g-p-6a795737fac081918d05e243cfcb0189/outputs/Joystick270_DualSense" -e dualsense
```

## 書き込み・接続確認

書き込み対象はこの `Joystick270_DualSense` フォルダ。旧シリアル版ではない。車両への信号線は書き込み中に外しておく。

```sh
/Users/AYARyoya/.platformio/penv/bin/pio run -d "/Users/AYARyoya/.codex/.chatgpt-projects/g-p-6a795737fac081918d05e243cfcb0189/outputs/Joystick270_DualSense" -e dualsense -t upload
```

```sh
/Users/AYARyoya/.platformio/penv/bin/pio device monitor -d "/Users/AYARyoya/.codex/.chatgpt-projects/g-p-6a795737fac081918d05e243cfcb0189/outputs/Joystick270_DualSense" -b 115200
```

基板単体で、起動・未接続・スティック中央・切断時にJ1-5(X)とJ1-4(Y)がGND基準で約2.5 Vになることを先に測る。接続後に一度中央を確認してから、表の各方向を測る。電圧は以前と同じくテスターで確認し、画面表示を実測とみなさない。

一度ペアリングしたあとにESP32を再起動し、DualSenseを起動して再接続できることも実機で確認する。コントローラ未接続時は2.5 V指令を保持する。

依存は `espressif32@6.12.0` とBluepad32公式Arduinoパッケージ4.1.0。配布ZIPのSHA-256を公式インデックスと照合済み：

`2b4916baba6c8d4e40b0330e12dd6a21ca7b95540337e6c2d2713831ccf3c394`

公式ZIP内のpackage.jsonはバージョンを4.0.2と表記しているためPlatformIOの一覧も4.0.2となる。取得先はplatformio.iniに固定した4.1.0公式リリースURL。

## 検証した範囲

`tests/control_test.cpp`：入力全域の格子点で円形制限・電圧上下限・極性を確認。斜め最大入力、中央、DAC換算、接続時のスティック倒れ、250 msタイムアウト、遅延パケット、再接続時の中央復帰、millisの桁あふれを確認した。

`tests/app_test.cpp`：実際の `src/main.cpp` を模擬Arduino/Bluetooth/SPI環境で実行し、接続設定より先に両DACへ停止コードを書き込む順序、A/Bチャネルと左右・前後の対応、別コントローラの拒否、切断と再接続、入力途絶時のDAC停止コードを確認した。GPIO32をHIGHにしないことも確認した。模擬試験でありBluetooth電波での接続試験ではない。

未検証：実機のペアリング・再接続、無線更新周期、実出力電圧、実車での方向と応答。ビルド成功と物理確認は別。

## 一次資料

- [Bluepad32 Arduinoガイド](https://bluepad32.readthedocs.io/en/latest/plat_arduino/)
- [Bluepad32対応ESP32とBluetooth方式](https://bluepad32.readthedocs.io/en/latest/FAQ/)
- [公式パッケージインデックス](https://raw.githubusercontent.com/ricardoquesada/esp32-arduino-lib-builder/master/bluepad32_files/package_esp32_bluepad32_index.json)
- [SonyのDualSenseペアリング手順](https://www.playstation.com/en-nz/support/hardware/pair-dualsense-controller-bluetooth/)
