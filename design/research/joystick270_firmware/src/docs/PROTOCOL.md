# EMC-270 Binary Protocol

## Frame

All multi-byte values are little-endian.

| Offset | Size | Field |
|---:|---:|---|
| 0 | 1 | Sync `0xA5` |
| 1 | 1 | Sync `0x5A` |
| 2 | 1 | Protocol version `1` |
| 3 | 1 | Message type |
| 4 | 2 | Payload length, maximum 192 |
| 6 | 4 | Sequence number |
| 10 | 4 | Sender monotonic time in milliseconds |
| 14 | N | Payload |
| 14+N | 2 | CRC-16/CCITT-FALSE |

CRC parameters: polynomial `0x1021`, initial `0xFFFF`, no reflection,
XOR-out `0x0000`. The CRC covers bytes at offsets 2 through `13+N`; it does
not cover the two sync bytes or the CRC field. Check value for ASCII
`123456789` is `0x29B1`.

## PC to joystick controller

| Type | Name | Payload |
|---:|---|---|
| `0x01` | HELLO | `u32 session_id, u8 options` |
| `0x02` | COMMAND | `i16 x_q10000, i16 y_q10000, u8 flags` |
| `0x03` | SET_PRESET | 11 `u16` values in `PresetPayload` order |
| `0x04` | ARM | empty |
| `0x05` | DISARM | empty |
| `0x06` | START_CALIBRATION | `u32 calibration_session_id` |
| `0x07` | ABORT_CALIBRATION | empty |
| `0x08` | GET_STATUS | empty |
| `0x09` | GET_CONFIG | empty |
| `0x0A` | LOG_INFO_REQUEST | empty |
| `0x0B` | LOG_CHUNK_REQUEST | `u32 offset` |
| `0x0C` | CLEAR_LOG | empty |

COMMAND flag bit 0 is ARM. X/Y are independently clamped to
`-10000..+10000`.

SET_PRESET order:

1. `x_negative_mv`
2. `x_positive_mv`
3. `y_negative_mv`
4. `y_positive_mv`
5. `x_seed_mv`
6. `y_seed_mv`
7. `dac_full_scale_mv`
8. `watchdog_ms`
9. `slew_full_scale_ms`
10. `motion_threshold_mm_s`
11. `output_warn_tolerance_mv`

## Encoder ESP32 to joystick controller

| Type | Name | Payload |
|---:|---|---|
| `0x40` | ENCODER_SPEED | `i32 left_mm_s, i32 right_mm_s, u16 status` |

Status bit 0 means the velocity values are valid. Both speeds are signed.
The default transmission rate is 50 Hz; the joystick controller declares the
data stale after 200 ms.

## Joystick controller to PC

| Type | Name | Payload size |
|---:|---|---:|
| `0x80` | HELLO_REPLY | 5 |
| `0x81` | STATUS | 43 |
| `0x82` | EVENT | 20 |
| `0x83` | CALIBRATION_SAMPLE | 34 |
| `0x84` | CONFIG | 42 |
| `0x85` | ACK | 8 |
| `0x86` | LOG_INFO | 9 |
| `0x87` | LOG_CHUNK | 10 + data |

The canonical layouts and numeric enumerations are defined in
`common/include/emc270/messages.hpp` and `common/include/emc270/model.hpp`.
Unknown message types must be ignored after their CRC and declared payload
length have been validated.

STATUS contains `rearm_required` immediately after `encoder_valid`. When it is
1, repeating COMMAND with ARM set does not retry. Send an accepted ARM request,
or send COMMAND with ARM clear before raising it again.

Calibration phase values are `0=IDLE`, `1=SEED_CHECK`, `2=COARSE_SEARCH`,
`3=FINE_SEARCH`, `4=COMPLETE`, `5=FAILED`, `6=ABORTED`, and `7=ARMING`.

ACK reason values are `0=accepted`, `1=malformed payload`, `2=invalid state`,
`3=invalid configuration`, `4=encoder unavailable`, `5=ADC unavailable`,
`6=log unavailable`, `7=configuration store unavailable`, and
`8=post-switch ARM verification failed`. An ACK only reports whether the
request was accepted by the serial receiver; completion and failures are
reported by EVENT and STATUS.

Calibration failure values are `0=none`, `1=invalid preset`,
`2=encoder unavailable`, `3=seed moves vehicle`,
`4=no motion before configured endpoint`, `5=session timeout`,
`6=host command watchdog`, `7=aborted by host`, `8=ARM verification`,
`9=internal`, `10=ADC unavailable`, `11=log unavailable`, and
`12=configuration store unavailable`.

ROS `ControllerEvent` adds a human-readable `description`. Code `32769` is a
PC-driver-only event meaning the USB link was lost during calibration; it does
not appear on the ESP32 wire protocol.
