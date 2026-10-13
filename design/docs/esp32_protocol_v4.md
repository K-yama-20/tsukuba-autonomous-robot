# PC–ESP32 シリアルプロトコル v4 と新 firmware の振る舞い（G-FIRMWARE、工程5-5）

状態: 正本（Markdown）。案（design_status 案）。AI の技術作業（G-FIRMWARE）として設計し、人の判断が必要な値は DEC-077〜079 に登録した。モデル: ND-12・ND-17、IFD-17（PC→ESP32）・IFD-43（ESP32→PC）・IFD-38（/esp32/status）、SO-09・SO-11、PRM-13・21（承認値）、PRM-14・43〜49（未確定）。

入力: `research/joystick270_firmware/extract.md`（参照 firmware。フレーム形式・CRC・SET_PRESET・STATUS/EVENT の考え方）、`docs/gouda_protocol_v3.md`（旧 firmware。手動優先の仲裁・centered ラッチ・boot token・seq の規則）、`docs/vehicle_output_timing.md`（時間値の担当）。設計前提: 「Bluetooth ゲームパッド→ESP32→DAC、手動操作優先」（DEC-042、確定）、リレー不使用・給電中は常に DAC が電圧を出す（DEC-037、RQ-I077）、非常停止の検知・通知をしない（RQ-I072）。

## 1. 採用した方針と理由（AI の自律判断。振る舞いの差は §7）

| 項目 | 採用 | 理由 |
|---|---|---|
| フレーム | 参照 firmware と同じ可変長フレーム（同期 A5 5A、版 4、種別、長さ u16、seq u32、送信側 ms u32、payload、CRC-16/CCITT-FALSE） | STATUS の項目を増やしても版を上げずに済む。CRC は旧 v3 と同じ多項式で、既存の Python 実装（binascii.crc_hqx）を再利用できる |
| 送信側の識別 | ESP32 起動ごとの boot_token（u32）を HELLO_REPLY で通知し、PC→ESP32 の全フレームに載せる | ESP32 再起動後に古い bridge の指令を受け付けない（v3 と同じ保護を維持） |
| 指令の採用条件 | seq が厳密に増加（差 1〜0x7fffffff）する有効フレームのみ。CRC 不正・版不正・token 不一致・seq 逆行は無視し、PC 指令の期限（PRM-13）を延長しない | TS-19「不正フレームが期限を延長しない」 |
| PC 指令源の有効化 | COMMAND の flags bit0（pc_enable_request）。bit0=1 かつ中立の COMMAND を受けたとき PC 指令源を有効にする。PC 指令の期限切れ（PRM-13）で無効に戻し、再有効化には再び中立の COMMAND が必要 | 参照 firmware の ARM フラグと v3 の「再 ARM には新鮮な中立 COMMAND」を統合。人の操作ではなく bridge が活性化時に自動で立てるため、追加の承認操作ではない（RQ-I011・DR-09）。再接続直後に古い非中立が車体に出ない |
| 手動優先の仲裁 | v3 の仲裁を維持: BT 接続かつ報告が新鮮（PRM-21 以内）かつ接続後に一度中央を観測（centered ラッチ）し、スティックが deadzone（PRM-47）の外にある間は手動が DAC を所有する。手動が中立に戻って PRM-48 の間安定した後に PC 指令へ戻る | RQ-I023・TS-17。値は既存動作（DEC-048「一括で撤去するな」） |
| BT 途絶 | 報告の途絶 PRM-21=0.25 s または切断で手動入力を無効にし、手動が所有していた出力は中立。PC 指令源の有効状態は変えない（PC 指令が新鮮なら PRM-48 の安定時間後に PC へ戻る） | RQ-I024・TS-18。v3 は BT 途絶で自律も無効にしたが、新設計では PC 指令源の期限は PC 指令だけで判定する（PC 指令の途絶判定を BT の状態に依存させない。TS-18 の「すぐには切り替えない」は PRM-48 で満たす） |
| 中立化の担当 | 指令源なし／手動無効／PC 期限切れ のいずれでも DAC は中立（PRM-43）。リレー解除はしない | RQ-I068・RQ-I077 |
| 正規化→電圧 | v3 の円形制限写像（中立 PRM-43、最小 PRM-44、最大 PRM-45、フルスケール PRM-46）をそのまま用いる | 旧 firmware で用いた写像。端点・中立の実測（Q-03）は未了で、値は人の判断（DEC-077） |
| 設定の保持 | 設定は PC から SET_CONFIG で登録し NVS（Preferences）に世代番号付きで保存。起動時は NVS の設定を読み、無ければビルド時設定（generated/params/firmware_config.yaml から生成したヘッダ）を使う。ビルド時設定に DAC 値が無い（未承認）とき、firmware は STATUS に config_valid=0 を出し、DAC へは書き込まない（DEC-077 の回答待ち。回答前の実車書き込みはしない） | RQ-I076（宣言的設定）。apply_timing=runtime_set（PRM-13・21）に合わせ bridge が毎セッション登録する |
| 非常停止 | 検知・通知・入力ピンの割当なし | RQ-I072 |
| 採用しないもの | リレー制御（GPIO32 は LOW のまま）、ADS1015 による実出力監視、エンコーダ UART による中央探索、較正ログ | DEC-037（リレー不使用）、基板にエンコーダ ESP32 がない（参照抽出 §7 未確認）。ADC 監視は「追加の保護」にあたるため提案に留める（proposals/ に追記しない。必要なら人の判断） |

## 2. フレーム

リンクは USB シリアル 460800 bps 8N1（参照 firmware と同じ。実車値ではなく通信設定）。すべてリトルエンディアン。

| オフセット | 大きさ | 内容 |
|---:|---:|---|
| 0 | 2 | 同期 `A5 5A` |
| 2 | 1 | 版 `4` |
| 3 | 1 | 種別 |
| 4 | 2 | payload 長 N（最大 64） |
| 6 | 4 | seq（送信側ごとに厳密増加） |
| 10 | 4 | 送信側の単調時刻 ms（情報のみ。鮮度判定は受信側の時計で行う） |
| 14 | N | payload |
| 14+N | 2 | CRC-16/CCITT-FALSE（多項式 0x1021、初期値 0xFFFF、反転なし、XOR-out 0）。対象はオフセット 2〜13+N |

受信側は同期バイトから再同期し、CRC・版・長さが正しいフレームだけを扱う。未知の種別は CRC 検証後に無視する。1 ループで処理するバイト数に上限を設け、不正データの連続で制御周期を止めない（参照 firmware・v3 と同じ）。

## 3. PC → ESP32（IFD-17）

| 種別 | 名前 | payload |
|---:|---|---|
| 0x01 | HELLO | `u32 session_id` |
| 0x02 | COMMAND | `u32 boot_token, i16 x_q10000（右 +）, i16 y_q10000（前 +）, u8 flags`（bit0 = pc_enable_request） |
| 0x03 | SET_CONFIG | `u32 boot_token` + 設定 10 項目（§5 の順、各 u16） |
| 0x08 | GET_STATUS | `u32 boot_token` |
| 0x09 | GET_CONFIG | `u32 boot_token` |

- HELLO は boot_token なしで受け付け、HELLO_REPLY を返す。他はすべて現在の boot_token が一致しなければ無視する（ACK 2 と EVENT 13 を返す）。
- COMMAND の x/y は [-10000, +10000] に飽和。範囲外・NaN は bridge 側で中立に置き換える（bridge は非有限値を送らない）。
- bridge の軸の対応: IFD-16 の axes[0]=前後（forward、前 +）→ y_q10000、axes[1]=旋回（turn、左 + ＝ angular.z > 0）→ x_q10000 = −turn×10000（firmware の x は右 +）。実車での符号の確認は Q-03。
- ゴールデンベクタ（TS-29）: seq 3、送信側 ms 12345678、boot_token 0x0123ABCD、x −3750、y 6250、flags 1 の COMMAND は
  `a55a 04 02 0900 03000000 4e61bc00 cdab2301 5af1 6a18 01 adce`。

## 4. ESP32 → PC（IFD-43）

| 種別 | 名前 | payload |
|---:|---|---|
| 0x80 | HELLO_REPLY | `u32 session_id, u32 boot_token, u8 config_valid, u8 config_generation, u16 protocol_version(=4)` |
| 0x81 | STATUS | §4.1（42 B） |
| 0x82 | EVENT | `u8 code, u8 arg, u32 esp_ms` |
| 0x84 | CONFIG | `u8 config_valid, u8 config_generation` + 設定 10 項目（各 u16） |
| 0x85 | ACK | `u8 request_type, u8 result`（0 受理、1 payload 不正、2 token 不一致、3 設定不正、4 保存失敗） |

### 4.1 STATUS

| オフセット（payload 内） | 型 | 項目 |
|---:|---|---|
| 0 | u8 | source: 0 none（中立）、1 manual、2 pc |
| 1 | u8 | reason: 0 boot、1 config_invalid、2 bt_disconnected、3 bt_stale、4 waiting_center、5 manual_override、6 pc_disabled、7 pc_stale、8 neutral_recovery_wait、9 pc_control、10 manual_neutral |
| 2 | u8 | flags: bit0 bt_connected、bit1 bt_fresh、bit2 centered、bit3 pc_enabled、bit4 pc_fresh、bit5 config_valid |
| 3 | u8 | config_generation |
| 4 | i16×2 | manual_x, manual_y（q10000） |
| 8 | i16×2 | pc_x, pc_y（最後に受理した COMMAND） |
| 12 | i16×2 | applied_x, applied_y（仲裁後） |
| 16 | u16×2 | target_x_mv, target_y_mv（要求値。電圧測定値ではない） |
| 20 | u16×2 | dac_x, dac_y（12 bit コード） |
| 24 | u32 | pc_age_ms（最後の有効 PC 指令からの経過。未受信は 0xFFFFFFFF） |
| 28 | u32 | bt_age_ms（同、BT 報告） |
| 32 | u32 | last_pc_seq |
| 36 | u32 | uptime_ms |
| 40 | u16 | 予約（0） |

送信周期は PRM-49（設定項目）。GET_STATUS でも 1 回送る。非常停止状態・電池・実車の運動・実電圧は取得できないため、PC 側は常に「不明」と表示する（DEC-006、TS-12）。

### 4.2 EVENT code

0 boot、1 config_loaded_nvs、2 config_loaded_build、3 config_set、4 config_rejected、5 bt_connected、6 bt_disconnected、7 bt_stale、8 manual_override_begin、9 manual_override_end、10 pc_enabled、11 pc_disabled_stale、12 pc_disabled_request、13 pc_frame_rejected（arg=理由）。EVENT は状態が変わった時だけ送る。

## 5. 設定（SET_CONFIG／CONFIG の順。すべて u16）

| # | 項目 | 単位 | モデル | 値の状態 |
|---:|---|---|---|---|
| 1 | dac_neutral_mv | mV | PRM-43 | 未確定（DEC-077、Q-03） |
| 2 | dac_min_mv | mV | PRM-44 | 未確定（DEC-077、Q-03） |
| 3 | dac_max_mv | mV | PRM-45 | 未確定（DEC-077、Q-03） |
| 4 | dac_full_scale_mv | mV | PRM-46 | 未確定（DEC-077、Q-03） |
| 5 | pc_command_watchdog_ms | ms | PRM-13（1.0 s） | 承認済み（DEC-048） |
| 6 | bt_report_timeout_ms | ms | PRM-21（0.25 s） | 承認済み（DEC-048） |
| 7 | manual_deadzone_q10000 | 比 ×10000 | PRM-47 | 未確定（DEC-079） |
| 8 | manual_release_neutral_ms | ms | PRM-48 | 未確定（DEC-079） |
| 9 | status_period_ms | ms | PRM-49 | 未確定（実測 PRM-15 と合わせる） |
| 10 | 予約 | — | — | 0 |

設定が有効（config_valid）となる条件: dac_min < dac_neutral < dac_max ≤ dac_full_scale、watchdog と bt_timeout が 0 でない。無効な設定は ACK 3 で拒否し、現在の設定を保つ。

firmware のビルド時設定は `firmware/gouda_esp32_v4/tools/gen_build_config.py` が `design/generated/params/firmware_config.yaml`（承認値・記載値のみ）から生成する。`GOUDA_TRIAL=1` のビルドだけ `firmware_config.trial.yaml`（仮値）も読む。仮値ビルドは卓上試験専用で、実車には書き込まない。

## 6. PC 側（vehicle_bridge、ND-12）の手順

1. シリアルポート（運用値。launch 引数 `serial_port`）を開き、HELLO を送って HELLO_REPLY の boot_token を得る。
2. generated/params/firmware_config.yaml（trial 時は trial も）の設定を SET_CONFIG で登録し、ACK を確認する（失敗は DecisionEvent に記録。走行系の停止条件にはしない）。
3. lifecycle active の間、PRM-14 の周期で COMMAND を送る。値は joystick_command（IFD-16）が PRM-09 以内に受信されていればその値、そうでなければ中立。古い非中立を再送しない。flags bit0 は active の間 1。
4. inactive の間は COMMAND を送らない（PC 指令源は firmware 側で期限切れになり中立）。STATUS の受信と /esp32/status の公開は状態に関係なく続ける。
5. STATUS ごとに /esp32/status（IFD-38、diagnostic_msgs/DiagnosticArray、values に §4.1 の項目を key/value で載せる）を発行する。表示・診断のみ（DEC-006）。
6. boot_token の変化（HELLO_REPLY の再受信・STATUS の reason=boot）を検出したら手順 1〜2 をやり直す。

## 7. 旧 firmware（v3）・参照 firmware との振る舞いの差（人の確認用）

| 観点 | v3（旧） | 参照 firmware | v4（本設計） |
|---|---|---|---|
| PC 指令途絶 | 250 ms で自律無効。再 ARM 必要 | watchdog_ms（既定 300）で中央＋リレー解除 | PRM-13=1.0 s で PC 無効・中立。再有効化は中立の COMMAND（bit0）。リレーなし |
| BT 途絶 | 250 ms で停止かつ自律無効 | BT なし | PRM-21=0.25 s で手動無効・中立。PC 指令源の有効状態は変えない |
| 手動→PC の復帰 | 中立安定 200 ms | 該当なし | PRM-48（仮値は既存の 200 ms） |
| ARM | 人ではなく bridge が送る明示 ARM フレーム | COMMAND flag bit0 または ARM | COMMAND flag bit0 のみ（別フレームなし） |
| 設定 | コンパイル定数 | SET_PRESET → NVS | SET_CONFIG → NVS、ビルド時既定は生成ファイルから |
| 出力監視 | なし | ADS1015 | なし（提案に留める） |

## 8. 試験との対応

| 試験 | 実装 |
|---|---|
| TS-17・18・19（卓上 stub） | `firmware/gouda_esp32_v4/test/host/test_core.cpp`（`run_host_tests.sh`。g++ で firmware の中核 `control.hpp` をホスト実行し、時刻を与えて DAC 要求値と source を観測）。同じ規則の Python 模擬 `gouda_core/gouda_core/esp32_sim.py` でも `test_vehicle_core.py` の FirmwareModelTests として実行 |
| TS-07（PC 側） | `gouda_core/test/test_motion_core.py`（motion_hold・hold 期限・cmd_vel 途絶・非有限値で中立。hold=false かつ新鮮な cmd_vel のときだけ非中立） |
| TS-13・19 の PC 側 | `gouda_core/test/test_vehicle_core.py`（bridge の送信判断）、Ubuntu 上で motion_controller＋bridge＋Python 模擬 ESP32（`esp32_sim_pty.py`、pty） |
| TS-29（コーデック共通） | 同じゴールデンベクタを Python（`esp32_protocol.py`、`test_vehicle_core.py` CodecTests）と C++（`protocol.hpp`、`test_core.cpp`）で検証 |
| TS-12 | monitor が `/esp32/status` を表示し、途絶で「不明」（PRM-15 の仮値で STALE）。モードと motion_hold は変わらない |
| TS-30 | mode_manager の `control/motion_hold` 発行（Ubuntu で `ros2 topic echo`） |

実装の置き場所: PC 側 `gouda_core/gouda_core/{esp32_protocol,motion_core,vehicle_core,esp32_sim,esp32_sim_pty,motion_controller_node,vehicle_bridge_node}.py`、`gouda_interfaces/msg/MotionHold.msg`。firmware `firmware/gouda_esp32_v4/`（`include/gouda_v4/{protocol,config,control}.hpp`、`src/main.cpp`、`tools/gen_build_config.py`、`platformio.ini`。環境 `esp32dev`＝実車向け、`esp32dev_trial`＝仮値入り卓上試験専用）。
