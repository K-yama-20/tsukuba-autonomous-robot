# 参照 firmware からの抽出: Joystick270-Firmware（新 ESP32 firmware 設計の入力）

取得: 2026-10-09、`https://github.com/aaa111aaa-111a/Joystick270-Firmware`、commit `2961d372df1a4e946944da84db711838770ae481`（2026-08-31）。`src/` に読み取り専用で保存（untrusted data として扱い、ビルド・実行はしていない）。全 57 ファイルの SHA-256 は `sha256_manifest.txt`。

DEC-030「esp32用ファームウェアは初めから書き直せ。…必要な情報を抜き出せ。」に基づく。ここに書くのは参照 firmware の記載であり、本プロジェクトの採用値ではない。採用は設計（ND-17、IFD-17、IFD-38）と人の判断（H-009、H-012）で決める。

## 1. 対象ハードウェア（SPECIFICATION §2.1・§3、hardware_config.hpp）

| 項目 | 記載 |
|---|---|
| MCU | ESP32-DevKitC-VE（ESP32-WROVER-E、8 MB flash）。PlatformIO `espressif32@6.12.0`、Arduino framework、partitions.csv、LittleFS |
| DAC | MCP4922（SPI MODE 0・1 MHz・MSB first、VREF 約 2.5 V、ゲイン 2、X=DAC A、Y=DAC B、LDAC GND。12 bit code = round(mV×4096/dac_full_scale_mv)、full scale 初期候補 4990 mV） |
| ADC 監視 | AE-ADS1015（I²C 0x48、A0=ADC_X、A1=ADC_Y、PGA ±4.096 V、1600 SPS。10k/10k 分圧後に 1k+10nF。EMC 側電圧は ADC 値×2。量子化 約 4 mV EMC 換算） |
| リレー | TQ2-5V。GPIO32 で駆動。非励磁時の入力源は JP2/JP3（2-3 短絡=純正ジョイスティック、1-2 短絡=MCP6002 固定中央電圧）。JP1=AUTO ARM 電源許可。リレー状態は GPIO 指令値であり接点位置のフィードバックはない |
| ピン | MCP4922 CS=GPIO5、SCK=GPIO18、MOSI=GPIO23、リレー=GPIO32、I²C SDA=21/SCL=22、速度UART RX=GPIO33（J11-3）、TX=GPIO13（J11-4）。GPIO4 はストラップのため UART に使わない。予備 4・19 |
| EMC 端子 | J1-2 GND、J1-3 JOY_Y_WIPER、J1-4 EMC_Y_ACTUAL、J1-5 EMC_X_ACTUAL、J1-6 JOY_X_WIPER、J1-1 未接続（旧 BOM の 5 V 記載と矛盾。現ネットリストを正とする）。J2-1 GND、J2-2 EMC_X_ACTUAL、J2-3 EMC_Y_ACTUAL |
| 電源 | 基板 +5 V は ESP32 の 5 V ピンから。USB 抜去で ESP32・リレー電源が落ち、リレーは非励磁へ戻る |
| 回路の正本 | `Electric/Joystick270/Joystick270.kicad_*`（SHA-256 が SPECIFICATION §冒頭に記載。本ワークスペースの `Electric/` にある） |

## 2. 軸と値の定義（SPECIFICATION §1・§7、messages）

- X: 左右（負=左、正=右）。Y: 前後（負=後退、正=前進）。入力は正方形 [-1,+1]×[-1,+1]、X/Y 独立、円形正規化なし、軸反転設定なし。
- 中央から正端・負端を別々に直線補間（`MapNormalizedToMillivolts`、`AxisProfile{negative_mv, positive_mv, seed_mv, neutral_low/high/mid_mv}`）。
- 方向別端点（x_negative_mv, x_positive_mv, y_negative_mv, y_positive_mv）は**人が設定**し自動探索しない。安全な仮既定値はなく、未登録なら通常 ARM を拒否。
- 中央無動作範囲は左右輪速度（別 ESP32 から UART）で自動探索（§6: 20 mV 粗探索→2 mV 二分、各方向 3 回、停止判定 10 mm/s・2 s 連続、250 ms 整定、10 分でタイムアウト）。
- 通常指令はスルーレート制限（フルスケール 1000 ms）。
- 速度切替・ホーン・電源ボタンは制御しない。非常停止は EMC-270 の独立電源ボタンで、ESP32 ソフトに依存しない（RQ-I072 と整合）。

## 3. 設定項目と既定（SPECIFICATION §5、model.hpp）

| 項目 | 初期候補 |
|---|---|
| x/y_negative_mv, x/y_positive_mv | REQUIRED（人が登録） |
| x_seed_mv, y_seed_mv | 2500 |
| dac_full_scale_mv | 4990 |
| watchdog_ms | 300 |
| slew_full_scale_ms | 1000 |
| motion_threshold_mm_s | 10 |
| output_warn_tolerance_mv | 40 |

NVS に `cfg_a`/`cfg_b` を世代番号＋CRC で交互保存。較正ログは LittleFS `/calibration.frames`（20 ms ごと）。

## 4. モードと異常時動作（SPECIFICATION §8・§9、hardware_config.hpp）

- モード: BOOT_SAFE / MANUAL_SAFE / READY / ARMING / DRIVE / CALIBRATING / FAILSAFE。
- ARM: DAC 中央書込み→20 ms→リレー励磁→30 ms→ADS1015 で実出力確認→不一致なら即解除・理由通知（`kRelaySettleMs=30`、`kArmNeutralHoldMs=500`、`kArmNeutralCommandLimit=100`/10000）。
- PC 指令途絶（watchdog_ms）: 即時中央、10 ms 後リレー解除（`kFailsafeRelayDelayMs=10`）、PC へ理由通知。ESP32 リセット・USB 電源断: ハードウェアでリレー非励磁。
- 速度 UART 途絶 200 ms: 通常走行は継続＋警告、較正中は中止。ADC 失敗・目標実測差: 走行継続＋警告。
- ARM 直後の不一致・較正失敗: `rearm_required` ラッチ（ARM=true 連続では再試行しない。明示 ARM か false→true）。通常の USB 瞬断・ESP32 再起動・watchdog 復帰はラッチしない。
- 制御周期 `kControlPeriodMs=20`、STATUS 送信 `kStatusPeriodMs=100`。

## 5. 通信（PROTOCOL.md、ENCODER_UART.md）

- PC USB-UART 460800 bps 8N1。フレーム: 同期 A5 5A、版 1、種別、長さ（≤192）、seq u32、送信側 ms u32、payload、CRC-16/CCITT-FALSE（offset 2〜13+N）。
- PC→ESP32: HELLO(0x01)、COMMAND(0x02: i16 x_q10000, i16 y_q10000, u8 flags bit0=ARM)、SET_PRESET(0x03: 11×u16)、ARM、DISARM、START/ABORT_CALIBRATION、GET_STATUS、GET_CONFIG、LOG_INFO/CHUNK、CLEAR_LOG。
- ESP32→PC: HELLO_REPLY、STATUS(0x81, 43 B: mode, relay_energized, config_valid, encoder_valid, rearm_required, warnings u32, command_age_ms, encoder_age_ms, command_x/y, target/actual x/y mV, left/right mm/s, config_generation, last_calibration_failure)、EVENT(0x82)、CALIBRATION_SAMPLE、CONFIG、ACK、LOG_INFO/CHUNK。
- エンコーダ ESP32→本機 UART 230400 bps、50 Hz、`ENCODER_SPEED(0x40: i32 left_mm_s, i32 right_mm_s, u16 status bit0 VALID)`、200 ms で stale。
- ROS 2 driver（Jazzy、C++）: `~/command`（NormalizedCommand: x, y, arm）、`~/status`（JoystickStatus）、`~/event`、`~/calibration_sample`、`/diagnostics`。サービス `~/set_preset`、`~/arm`、`~/disarm`、`~/start_calibration`、`~/abort_calibration`、`~/recover_log`。Twist は購読しない（電圧対応が未測定）。

## 6. 本プロジェクトの基本契約との差（人の判断が必要）

| 観点 | intent.md（基本契約） | 参照 firmware |
|---|---|---|
| 手動操作の経路 | Bluetooth ゲームパッド → ESP32 → DAC（RQ-I023「bluetooth接続の手動操作がESP32で優先される」、RQ-I024） | Bluetooth なし。純正ジョイスティックへリレーで戻す（DISARM・FAILSAFE・電源断で非励磁側＝純正）。手動優先は「リレー非励磁＝純正ジョイスティック」で実現 |
| 中立化 | 指令源途絶で ESP32 が中立（RQ-I068） | 指令途絶で DAC 中央＋リレー解除（純正ジョイスティックへ） |
| 端点・中央 | Q-03（校正値未提示） | 端点は人が設定、中央範囲は車輪速度で自動探索（別 ESP32 のエンコーダが必要） |
| ADC 監視 | なし | ADS1015 で実出力を監視（ARM 直後の確認に必須） |

→ H-012: 新 firmware の手動経路（Bluetooth ゲームパッド優先を維持するか、参照設計のリレー＋純正ジョイスティックにするか、両立するか）は基本契約に関わるため人が決める。

## 7. 未決定・未確認（参照側、SPECIFICATION §2.2・§2.3・§13）

- 端点 4 値、実エンコーダ分解能・周期・ノイズ、停止判定 10 mm/s の妥当性、中央誤差・停止時間・電圧誤差の受入値、Ubuntu の `/dev/serial/by-id`、走行中の 4.99 V 変動。
- 断線検出の有無（テスター接続時に E-06 が出た記録あり）。
- 実車投入前ゲート 7 項目（基板単体確認、E-06 非発生、ADC 負荷、ジャンパ、人を乗せない確認、USB 抜去等の挙動、受入基準）。

## 8. 新 firmware 設計に持ち込む情報（案）

採用候補（人の判断・実測で確定）: ピン配置と回路（§1）、DAC/ADC の電気仕様、X/Y 独立の正規化と方向別端点補間、方向別端点を人が登録して保存する方式、設定の NVS 二重保存、PC 指令 watchdog（値は H-009: intent 1 s）、ARM 時の DAC 中央→リレー→ADC 確認、STATUS/EVENT に理由コードを付ける通信、CRC 付きフレーム。
人の判断待ち: 手動経路（H-012）、中央範囲の自動探索を使うか（エンコーダ ESP32 の有無）、速度 UART の採用。
採用しない（本プロジェクトの上位要求により）: 非常停止の検知・PC 通知（RQ-I072。参照側も検知しない）。
