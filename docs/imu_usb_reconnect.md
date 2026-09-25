# IMU USB reconnection

`setup.sh` applies the reconnect overlay after the existing termios and acquisition-clock adapters. It preserves originals under `ADI_IMU_TR_Driver_ROS2/.imu_reconnect_patch_backup` and rejects unexpected edits. The clock adapter recognizes the exact reviewed overlay so setup can be repeated.

Configure the IMU using its `/dev/serial/by-id/...` identity. Do not bind it to a transient ttyACM number. The node reopens only this configured path; it never scans or selects other serial devices.

If no new measurement arrives for 1.5 seconds, the node closes its stale descriptor and retries after one second. Opening or settings-read failures also retry. Reads and drain bursts are bounded. Reconnection discards old buffered packets, sensitivity settings, sample-counter history, PPS history, and the MCU-to-host clock fit. An exact settings response and valid sensitivity values are required before starting telemetry. IMU samples resume only after the clock mapper relocks; `imu/clock_status` reports `disconnected` then `unlocked` before `host_mapped`.

The serial setup disables inherited RTS/CTS flow control and asserts host DTR/RTS when supported (PTYs may not support modem control). The read loop drains queued bursts rather than accumulating stale measurements at lower ROS publish rates.

## Verification

Run the upstream driver's CTest suite after building it. The overlay updates its fake MCU clock to advance instead of staying at zero, and updates its disconnected-log expectation.

A separate end-to-end PTY test exercises invalid settings responses, changed device paths behind a stable symlink, fresh clock learning, and continued operation without a node restart:

```bash
source /opt/ros/jazzy/setup.bash
source ~/gouda_ws/install/setup.bash
python3 tests/test_imu_usb_reconnect.py ~/gouda_ws/install/setup.bash
```

The test uses its own ROS domain and does not open physical USB devices.

This change does not synchronize the LiDAR clock, calibrate USB latency, or validate vehicle motion. A connected IMU and a valid software clock fit are separate from LiDAR–IMU synchronization.
