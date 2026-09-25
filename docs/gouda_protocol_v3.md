# Gouda PC–DualSense USB protocol v3

This document specifies the binary USB serial link used by `firmware/gouda_dualsense_usb/` and the Gouda PC serial bridge. USB serial is 115200 baud. Application telemetry uses v3 binary frames. ROM or library startup text may still appear; the host parser resynchronizes at a valid frame. Device status is sampled every 50 ms when the UART transmit ring has space. A status frame is dropped rather than blocking controller processing if a complete 64-byte frame cannot be queued.

All multi-byte integers are little-endian. Signed values are two's-complement. Every frame is exactly 64 bytes:

| Offset | Size | Field | Meaning |
|---:|---:|---|---|
| 0 | 2 | magic | `A5 5A` |
| 2 | 1 | version | `3` |
| 3 | 1 | kind | `1 COMMAND`, `2 ARM`, `3 DISARM`, `128 STATUS` |
| 4 | 8 | boot token | Random nonzero token created at ESP32 boot; echoed in all host commands |
| 12 | 4 | sender sequence | Strictly increasing per sender; wrap is accepted only when the unsigned forward difference is in `1..0x7fffffff` |
| 16 | 4 | sender monotonic ms | Sender-local wrapping milliseconds. Informational only; device freshness uses its own receive clock, so this field does not claim host/device clock synchronization. |
| 20 | 40 | payload | Kind-specific fields below; unused bytes must be zero. |
| 60 | 2 | reserved | Must be zero |
| 62 | 2 | CRC | CRC-16/CCITT-FALSE over bytes `0..61`, init `FFFF`, polynomial `1021`, no reflection, xorout `0000`; stored little-endian |

The CRC check value for ASCII `123456789` is `29B1`. A COMMAND golden vector is covered by the host tests: token `0123456789ABCDEF`, sequence `3`, sender time `12345678`, right `-375`, forward `625` encodes as:

```text
a55a0301efcdab8967452301030000007856341289fe710200000000000000000000000000000000000000000000000000000000000000000000000000008360
```

## PC to ESP32 payloads

**COMMAND** uses signed `right_norm` at byte 20 and `forward_norm` at byte 22. Each is in `[-1000,1000]`; the remaining 36 payload bytes are zero. Positive right requests a right turn; positive forward requests forward travel. The value is a normalized request, not a measured vehicle response. Valid COMMAND frames are accepted while autonomy is disarmed so the latest command and heartbeat can be checked before ARM. A valid frame must have the current boot token, valid CRC/reserved/payload fields, and a strictly newer sequence. The sender timestamp is not used as a synchronized clock.

**ARM** and **DISARM** have an all-zero 40-byte payload. ARM is accepted only when autonomy is currently disabled, a neutral COMMAND is still fresh, and the DualSense has a fresh centered report. It never arms on boot or reconnect by itself. DISARM disables autonomous ownership and requires a later explicit ARM, but it does not suppress a currently valid manual stick override.

## ESP32 to PC STATUS payload

The ESP32 uses its current boot token, an independent increasing outgoing sequence, and its local `millis()` in the common header. Payload layout:

| Frame offset | Type | Field |
|---:|---|---|
| 20 | `u8` | owner: `0 stopped`, `1 manual`, `2 autonomous` |
| 21 | `u8` | reason enum: `0 stopped`, `1 boot/disarmed`, `2 BT disconnected`, `3 BT report stale`, `4 waiting for centered BT report`, `5 manual override`, `6 PC command stale`, `7 waiting for stable neutral`, `8 autonomous control` |
| 22 | `u16` | flags: bit 0 BT connected, bit 1 BT report fresh, bit 2 centered-after-connect readiness latch (not current stick neutral), bit 3 autonomous enabled; all other bits zero |
| 24 | `i16` | last raw DualSense left-stick X (`-512..511`) |
| 26 | `i16` | last raw DualSense left-stick Y (`-512..511`) |
| 28 | `i16` | normalized manual right request (`-1000..1000`) |
| 30 | `i16` | normalized manual forward request (`-1000..1000`) |
| 32 | `i16` | last accepted PC right request (`-1000..1000`) |
| 34 | `i16` | last accepted PC forward request (`-1000..1000`) |
| 36 | `i16` | applied normalized request after ownership/safety arbitration (`-1000..1000`) |
| 38 | `i16` | applied normalized forward request (`-1000..1000`) |
| 40 | `u16` | MCP4922 X DAC code (`0..4095`) |
| 42 | `u16` | MCP4922 Y DAC code (`0..4095`) |
| 44 | `u16` | requested X millivolts (`230..4700`) |
| 46 | `u16` | requested Y millivolts (`230..4700`) |
| 48 | `u32` | last accepted PC sequence; zero before any accepted PC frame |
| 52 | `u32` | Bluetooth report age in device milliseconds; `FFFFFFFF` if none observed |
| 56 | `u32` | last accepted PC frame age in device milliseconds; `FFFFFFFF` if none observed |

The millivolt values are software requests derived from the existing provisional mapping. They are **not voltage measurements**. DAC conversion and the requested range do not prove the output voltage at a connector or vehicle input.

## Ownership and fault behavior

- At boot the system is disarmed. Manual control remains available without a PC connection after a fresh DualSense report and one centered report. Until those BT conditions are met, output requests remain neutral.
- The existing radial 8% deadzone and stick mapping are retained. A fresh stick outside the deadzone owns both axes; there is no software obstacle guard in manual mode.
- While the stick is neutral, autonomous ownership requires an explicit ARM, a fresh PC command, and fresh centered BT. After manual override, neutral must remain stable for 200 ms before the latest fresh PC command can own both axes again.
- BT disconnect or a BT report age of 250 ms or more stops output, clears autonomous enable, and requires explicit re-ARM after a new centered BT report and fresh neutral PC COMMAND.
- A PC COMMAND age of 250 ms or more clears autonomous enable. Manual control remains available while BT is fresh. New PC traffic does not automatically resume autonomy; the host must send a fresh neutral COMMAND and a new ARM.
- Sequence replay, old/duplicate frames, wrong boot token, bad CRC, nonzero reserved bytes, out-of-range values, and nonzero unused payload bytes are ignored. Parsing uses fixed-size storage and bounded per-loop byte processing; malformed traffic cannot grow memory or starve the controller loop.
- The firmware does not read or report an emergency-stop switch. No MCU input for the physical drive-power cut is specified here.

## Shared implementation

The C++ codec and state machine are in `firmware/gouda_dualsense_usb/include/protocol.hpp` and `control.hpp`. The independent PC bridge must produce byte-identical frames, use its own sequence space, echo the STATUS boot token, and treat STATUS DAC/mV fields as device-reported requests rather than measurements. Host tests include the shared golden vector and every documented STATUS offset.
