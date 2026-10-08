# H-009 対応表: 車体出力段階の時間値（700 ms・1 s・250 ms・その他）

作成 2026-10-09。対象: 実装リポジトリ `tsukuba-autonomous-robot` HEAD a091ed39、参照 firmware `Joystick270-Firmware` commit 2961d372、intent.md 第3版 102 行。値はすべて出典のコード・文書から転記。実車採用値ではない。

## 1. 値ごとの対応

| 値 | 由来 | どの入力の途絶か | 判定する部品 | 期限切れのときの動作 | 根拠（コード・設定の場所） | 状態 |
|---|---|---|---|---|---|---|
| 700 ms | intent.md:102「PC指令のtimeout=700ms」（RQ-I075） | PC 内の指令。cmd_vel（Nav2→motion_controller）か、joystick_command（motion_controller→bridge）かは文面から一意でない | PC 側 node（ND-11 または ND-12。設計案） | 中立を出す（RQ-I063）。設計案では motion_hold（IFD-40）とは独立の保険 | 実装なし。設計: PRM-08（cmd_vel 途絶）・PRM-09（joystick 期限）。intent.md:102 | 要求値。配分は未決 |
| 1 s | intent.md:102「ESP32のwatchdog=1s周期」（RQ-I075） | PC→ESP32 の指令フレームの途絶 | ESP32 firmware | 中立を出す（RQ-I068）。新 firmware（DEC-030）では参照 firmware の方式に従えば「DAC を即時中央、10 ms 後にリレー解除」 | 実装なし（新 firmware を書く）。参照 firmware では設定項目 `watchdog_ms`（`common/include/emc270/model.hpp` kDefaultWatchdogMs=300、SET_PRESET 8番目、`docs/SPECIFICATION.md` §5・§7・§9） | 要求値。新 firmware の設定値として採用可 |
| 250 ms（firmware） | `firmware/gouda_dualsense_usb/include/control.hpp:9` `kLinkTimeoutMs = 250` | (a) Bluetooth ゲームパッド報告の途絶、(b) PC COMMAND フレームの途絶 | 現 firmware gouda_dualsense_usb（ESP32） | (a) `tick()`: centered=false、manual 消去、auto_enabled=false、rearm_required=true → 出力中立（`control.hpp:133-136`）。(b) `tick()`: auto_enabled=false、rearm_required=true → 以後 PC 指令を出力しない（`control.hpp:137-139`）。ARM 受理にも PC 指令が 250 ms 以内であることを要求（`control.hpp:116`） | `control.hpp:9, 82, 97-100, 116-117, 133-139`。`docs/gouda_protocol_v3.md`「Ownership and fault behavior」 | 既存実装の値。新 firmware で置き換わる（DEC-030） |
| 250 ms（bridge） | `gouda_vehicle/gouda_vehicle/hardware_bridge.py:96-99` `_fresh_status()` `< .25` | ESP32→PC の STATUS フレームの途絶（または connected/fresh フラグ偽） | PC bridge（現実装 HardwareSerialBridge） | 指令送信を止め、ARM 要求中なら DISARM を送る（`hardware_bridge.py:237-241`）。ARM 要求も拒否（`:136-138`） | `hardware_bridge.py:96-99, 136-138, 237-241` | 既存実装の値。新 bridge（ND-12）で再設計 |
| 150 ms（bridge） | `hardware_bridge.py:236` `drive_fresh ... <= .15` | PC 内の `/gouda/control/drive` 指令の途絶 | PC bridge（現実装） | 指令送信を止め、ARM 要求中なら DISARM（`:237-241`） | `hardware_bridge.py:236-241` | 既存実装の値。700 ms（PRM-09）と同じ役割 |
| 200 ms | `control.hpp:10` `kNeutralResumeMs = 200` | （途絶ではない）手動介入後、スティックが中立で安定している時間 | 現 firmware | 200 ms 中立が続いてから PC 指令が両軸を再取得（`gouda_protocol_v3.md`） | `control.hpp:10`、`docs/gouda_protocol_v3.md` | 既存実装。新 firmware で再定義 |
| 50 ms | `firmware/gouda_dualsense_usb/src/main.cpp:14` `kStatusPeriodMs = 50` | （周期）STATUS 送信周期 | 現 firmware | — | `main.cpp:14, 104-111` | 既存実装 |
| 20 ms | `hardware_bridge.py:65` `create_timer(.02)` | （周期）bridge の送信・受信処理周期 | PC bridge | — | `hardware_bridge.py:65` | 既存実装 |
| 300 ms | 参照 firmware `model.hpp` `kDefaultWatchdogMs = 300` | PC→ESP32 指令の途絶 | 参照 firmware（Joystick270-Firmware） | DAC 即時中央、10 ms 後リレー解除（`hardware_config.hpp` kFailsafeRelayDelayMs=10、SPECIFICATION §7） | `common/include/emc270/model.hpp`、`firmware/include/hardware_config.hpp`、`docs/SPECIFICATION.md` §5・§9 | 参照値（設定可能） |
| 500 ms | 参照 firmware `hardware_config.hpp` `kArmNeutralHoldMs = 500` | （途絶ではない）ARM 前に正規化指令が中央付近で継続する時間 | 参照 firmware | 継続後にリレー投入 | `hardware_config.hpp`、SPECIFICATION §8 | 参照値 |
| 200 ms | 参照 firmware `hardware_config.hpp` `kEncoderStaleMs = 200` | エンコーダ ESP32 からの速度 UART の途絶 | 参照 firmware | 通常走行は継続して警告、較正中は中止（SPECIFICATION §9） | `hardware_config.hpp`、`docs/ENCODER_UART.md` | 参照値 |

## 2. PC 側の処理時間の見積り（判断材料）

- Nav2 controller の cmd_vel 周期は `controller_frequency`（上流既定 20 Hz = 50 ms。PRM-17 未確定）。
- bridge の送信周期は現実装 20 ms。新設計 PRM-14（未確定。ESP32 watchdog に対し十分短く）。
- したがって「PC 指令途絶」を PC 側で判定する最短の意味ある値は controller 周期の 2〜3 倍（100〜150 ms）。700 ms は 14 周期分で、cmd_vel 停止後も最大 0.7 s 最後の速度で走る。一時停止の正規経路は Nav2 取消＋motion_hold（IFD-40）であり、timeout は異常時の保険。

## 3. 要求値（700 ms・1 s）を維持する場合の変更箇所

| 箇所 | 変更 |
|---|---|
| 新 ESP32 firmware（DEC-030 で書き直し） | 指令 watchdog を 1000 ms に設定（参照 firmware の `watchdog_ms` に相当する設定値を持たせ、既定を 1000 にする。または起動時に PC から設定）。期限切れ動作: 中立（RQ-I068）。リレー方式を採るかは H-012 |
| 新 PC bridge（ND-12） | 現実装の 0.25 s STATUS 鮮度・0.15 s drive 鮮度は廃止または再定義。joystick_command の期限 PRM-09、送信周期 PRM-14（watchdog 1 s より十分短く。例: 現実装と同じ 20〜50 ms） |
| motion_controller（ND-11） | cmd_vel 途絶判定 PRM-08。700 ms を PRM-08 と PRM-09 のどちら（または合計）に割り当てるかは H-009 の決定 |
| intent.md | 変更なし |
| リスク | PC 側 700 ms の間、最後の速度で走行が続く（最大 0.7 s）。ESP32 1 s は PC 全体が止まった場合の後詰め |

## 4. 250 ms を採用する場合に必要な要求変更

| 箇所 | 変更 |
|---|---|
| intent.md:102（人が編集） | 「ESP32のwatchdog=1s周期」→ 250 ms（または新 firmware の設定値）。「PC指令のtimeout=700ms」→ 250 ms 以下にしないと、PC が途絶を認識する前に ESP32 が先に中立化する順序になる（PC 側が先に中立、ESP32 が後詰め、の順序を保つなら PC timeout < ESP32 watchdog が必要） |
| 新 firmware | watchdog 250 ms（現 firmware と同じ）。bridge 送信周期は 250 ms に対し十分短く（現 20 ms なら余裕 12 倍） |
| 判断台帳 | DEC-029（H-009）の回答として記録。RQ-I075 は置換（新しい authority revision） |

## 5. 補足: 既存の停止条件の扱い

DEC-006「既存の実装に停止条件が既にある場合は、AI の判断で外させません」は現 firmware・現 bridge に対するもの。DEC-030 で firmware を初めから書き直す決定が出たため、現 firmware の 250 ms は「置き換え対象の既存値」になる。新 firmware・新 bridge の値は H-009 の決定に従う。現実装の値を参考値として本表に残す。
