# エンコーダーESP32 UART仕様

## 1. 役割分担

エンコーダー用ESP32は左右の車輪エンコーダーを解析し、各輪の速度をmm/sへ変換する。
Joystick270側ESP32は生のパルスを解釈せず、受信した左右輪速度を中央無動作範囲の判定と
状態通知にだけ使う。通常走行の閉ループ速度制御は本版の範囲外である。

## 2. 電気接続

| エンコーダーESP32 | Joystick270 J11 | Joystick270 ESP32 |
|---|---|---|
| TX（3.3 V） | J11-3 | GPIO33 / UART2 RX |
| RX（将来拡張、任意） | J11-4 | GPIO13 / UART2 TX |
| GND | J11-1 | GND |

- UARTは3.3 Vロジック、230400 bps、8 data bits、no parity、1 stop bit。
- 両基板を別々に給電する場合、J11-2の3.3 V同士は接続しない。
- J11をUARTに使うときはSW1をCOMM側にし、表示LEDをGPIO33/GPIO13から切り離す。
- 写真に写る純正ジョイスティックの線色は、このUART配線の識別に使わない。

## 3. 速度の定義

- `left_mm_s`: 左輪の符号付き速度。
- `right_mm_s`: 右輪の符号付き速度。
- 車体前進方向を正、後退方向を負とする。
- 直進前進では両方が正、その場左旋回では左が負・右が正になる。
- 両輪を同じ単位、同じ符号規約、同じ時間基準で算出する。
- 両方の値が利用可能で、センサ診断が正常なときだけstatus bit 0 (`VALID`)を立てる。

## 4. 送信周期とフレーム

標準周期は50 Hz（20 ms）である。1フレームのpayloadは次の10 bytes。

| Offset | 型 | 内容 |
|---:|---|---|
| 0 | `int32 little-endian` | `left_mm_s` |
| 4 | `int32 little-endian` | `right_mm_s` |
| 8 | `uint16 little-endian` | status、bit 0=`VALID` |

message typeは`0x40`。同期語、sequence、送信時刻、CRCを含む外側フレームは
[`PROTOCOL.md`](PROTOCOL.md)と同一である。sequenceはフレームごとに1増加させ、
送信時刻は起動後の単調増加ミリ秒を32 bitで送る。

Joystick270側は最後の正常フレームから200 msでstaleと判定する。通常DRIVE中は警告を
PCへ送って走行を継続し、較正中は理由`ENCODER_UNAVAILABLE`で較正を中止する。

## 5. 組込み前の確認

実エンコーダーコードが未完成でも、次で受信経路を試験できる。

- 別ESP32: [`encoder_mock/`](../encoder_mock/) を書込み、USB端末で
  `<left_mm_s> <right_mm_s>`を入力する。
- USB-UARTアダプター: `tools/encoder_uart_simulator.py`を使う。

実機化するときは、停止中のノイズ分布、左右の符号、mm/s換算係数、欠相・断線時の
`VALID`解除、50 Hzのジッタを記録してから、`motion_threshold_mm_s`を決める。
