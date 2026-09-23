# Gouda Serial protocol v2 (development)

The original six-byte CRC8 proposal was not an implemented compatibility contract.
This version deliberately replaces it with a 22-byte frame so that buffered commands
from before a fault/restart cannot rearm a new control session. USB: 115200 baud, 8N1.
No text is printed on the firmware protocol port. This is error detection, not authentication.

| Offset | Length | Meaning |
|---|---|---|
| 0 | 2 | A5 5A |
| 2 | 1 | version = 2 |
| 3 | 1 | COMMAND=1, ARM=2, DISARM=3, STATUS=128 |
| 4 | 8 | boot/session token, unsigned little endian |
| 12 | 4 | sequence, unsigned little endian |
| 16 | 1 | motion: STOP=0, FORWARD=1, BACKWARD=2, LEFT=3, RIGHT=4 |
| 17 | 1 | bit0 enable; other bits must be zero |
| 18 | 1 | command must be zero; status fault=1 means watchdog |
| 19 | 1 | reserved, zero |
| 20 | 2 | CRC-16/CCITT-FALSE, little endian |

CRC covers bytes 0–19, polynomial 0x1021, initial 0xffff, no reflection, xorout=0.
`123456789` gives 0x29b1. Sliding parser handles fragments, concatenation, and noise.
Only valid fresh commands renew the 250 ms deadline (`elapsed >= 250`).
Sequence advances modulo 2^32, accepting forward deltas in [1, 2^31-1].
Status is published every 50 ms; its sequence acknowledges the last accepted input.

Boot: disabled, fresh random 64-bit token. ARM must have STOP, enable=1, matching token,
fresh sequence and validated firmware calibration. COMMAND cannot arm.
DISARM or COMMAND enable=0 neutralizes and advances token. Watchdog does the same with
fault=1. Old ARM frames therefore cannot be reused after a fault. Token collision after
independent boots is probabilistically mitigated, not impossible or authenticated.

PC sends at 20 Hz only while status, upstream command, and final motion permit are fresh
(each <200 ms monotonic age). Loss latches PC arm off. Explicit `/gouda/arm` is needed again.
STOP callbacks immediately send STOP; they do not wait for the next heartbeat.
No automatic port reconnect/rearm. Current bridge only permits `/dev/pts/*` in simulation;
hardware transport remains gated until the calibration/profile work is completed.

Direction changes go through neutral. Firmware enforces 1000 ms neutral before a new
direction; it does not claim the vehicle has physically stopped. The PC follower also
requires observed near-zero twist for 200 ms. Initial movement after ARM has no extra
firmware delay. Vehicle model applies the separate 1 s startup and 1 s linear slowdown.
STOP cancels pending startup and repeated STOP does not reset slowdown.

Calibration currently uses a build-time `include/calibration.hpp`. `validated=false`
and all five entries neutral prevent autonomous motion. Its neutral request is inherited
from DualSense (2500 mV with provisional 4700 mV full scale). It is not newly measured.
Changing DAC calibration currently requires rebuilding/reflashing; versioned persistent
configuration with readback has NOT been implemented. Status does not prove DAC voltage
or physical speed. GPIO32 stays LOW because the existing circuit bypasses the relay.

The native emulator compiles the exact same C++ parser/state/watchdog/output table core
as the ESP32 build. It uses explicitly synthetic calibration and cannot control a DAC.
Its acknowledged state drives the vehicle model through real Serial/PTY transport.
