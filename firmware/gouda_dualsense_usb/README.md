# Gouda DualSense USB firmware

Target: ESP32-DevKitC-VE with ESP-WROVER-E module, PlatformIO `esp32dev`, 8 MB flash, Arduino + pinned Bluepad32 4.1.0 package. The established MCP4922 mapping is retained: A/X/R1 for right/left and B/Y/R2 for forward/reverse. SPI uses GPIO18 SCK, GPIO23 MOSI, GPIO5 chip select; GPIO32 relay control stays LOW in the documented relay-bypass build. GPIO21/22 remain pull-up inputs and are not assigned a stop function.

The USB serial port at 115200 baud carries protocol v3 frames only. It does not emit text mixed into the link. The frame contract and state ownership rules are in [gouda_protocol_v3.md](../../docs/gouda_protocol_v3.md). The device reports requested mV and DAC codes; it has no voltage feedback. The existing 230–4700 mV circle and 2500 mV neutral mapping are inherited software requests and do not establish connector voltage calibration.

Pair a DualSense using Create + PS if it is not already paired. Stored pairing data is preserved. The code matches the PS5 controller model at the connection callback, then waits for a real HID/gamepad report before processing input, so the first connection notification cannot prematurely reject the controller. One fresh centered report is required after each connection or stale-input event.

Build the ESP32 image without uploading:

```sh
pio run -d firmware/gouda_dualsense_usb -e esp32dev
```

Run native host tests for packet layout/CRC, parser recovery, owner arbitration, explicit ARM, manual behavior through PC loss, both link watchdogs, rollover, and circular DAC bounds:

```sh
firmware/gouda_dualsense_usb/test/run_host_tests.sh
```

The CI workflow builds `firmware.bin` as an artifact and runs host tests. It does not upload firmware or open a serial device. No flash or physical controller/vehicle test was performed for this implementation. Boot behavior, Bluetooth reconnection, requested direction, requested DAC output, and actual voltage remain separate hardware acceptance checks.
