# Test procedure

This procedure separates software build success, board electrical checks, and
vehicle qualification. A result from one stage does not pass a later stage.

## 1. Software-only checks

```bash
~/.platformio/penv/bin/pio test -e native
~/.platformio/penv/bin/pio run -e joystick270
~/.platformio/penv/bin/pio run -d encoder_mock
python3 -m py_compile tools/*.py
```

On Ubuntu 24.04 / ROS 2 Jazzy:

```bash
cd ros2_ws
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths src --ignore-src --rosdistro jazzy -y
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release
colcon test --event-handlers console_direct+
colcon test-result --verbose
```

## 2. Unpowered board inspection

1. Confirm there is no person in the vehicle and EMC-270 power is off.
2. Confirm component orientation and the actual ESP32 module marking.
3. Confirm MCP4922, ADS1015, MCP6002, TQ2-5V, Q6, and D1 orientation.
4. Confirm JP2/JP3 2–3 selects the pure joystick wipers.
5. Confirm JP1 open prevents relay energization.
6. Measure for a short between +5 V, +3.3 V, and GND.
7. Confirm J11-1 is GND and J11-2 is 3.3 V. Do not join two powered 3.3 V rails.

## 3. Board-only powered test

1. Keep J1 disconnected from EMC-270 and JP1 open.
2. Flash the controller and initialize LittleFS:

   ```bash
   ~/.platformio/penv/bin/pio run -e joystick270 -t upload
   ~/.platformio/penv/bin/pio run -e joystick270 -t uploadfs
   ```

3. Confirm GPIO32 and the relay remain de-energized during reset and flashing.
4. Confirm MCP4922 X/Y outputs are near the configured 2500 mV seed.
5. Confirm ADS1015 reports known voltages applied to J2-2/J2-3 through the board path.
6. Connect the encoder mock. Enter `0 0` and confirm encoder status is valid.
7. Stop the mock and confirm the ESP32 reports stale encoder data without stopping normal DRIVE logic.

## 4. EMC monitor-only gate

This is required because the existing E-06 observation is unresolved.

1. Keep JP1 open so the relay cannot energize.
2. Set JP2/JP3 to the pure joystick side.
3. Connect J1/J2 to EMC-270 exactly as documented in the final schematic.
4. Power EMC-270 with its wheels unable to cause an uncontrolled departure.
5. Record pure joystick center and four directional end voltages from ADS1015.
6. Move the joystick through all directions and check for E-06, beeps, or motor disable.
7. If any fault occurs, stop. Do not run calibration. Investigate the ADC divider loading and wiring.

Pass condition: normal manual operation remains unchanged while ADC monitoring is connected.

## 5. Relay and post-switch verification

1. Keep the commanded DAC values at the measured manual center.
2. Install JP1 and request ARM with a zero command.
3. Confirm the sequence is DAC write, relay energize, 30 ms wait, ADC verification.
4. Confirm a deliberately wrong center causes immediate relay release and an event containing target and actual mV.
5. Confirm removing JP1 or USB returns K1 to the selected JP2/JP3 non-energized source.

## 6. Calibration in a controlled area

1. No person rides the chair. Keep an operator at the independent EMC power-off button.
2. Use a flat, unobstructed area. Mark a physical exclusion zone.
3. Enter measured four endpoints; do not use invented example values.
4. Confirm both wheel speeds are signed, fresh, and close to zero when stationary.
5. Start calibration and retain the ROS CSV.
6. Confirm X-left, X-right, Y-reverse, Y-forward are tested in order.
7. Confirm each direction has three boundary measurements and a common neutral range.
8. Compare the PC CSV with the recovered ESP32 `.frames` log.

## 7. Fault injection

Perform each separately and record status/event timestamps.

- Stop PC command publication: center must be written by 300 ms plus scheduling tolerance, then relay released 10 ms later.
- Unplug USB: relay must drop to JP2/JP3 non-energized source.
- Reconnect USB: the host must send neutral for 600 ms, and the ESP32 must
  observe at least 500 ms of fresh neutral commands before re-ARM.
- Stop encoder UART during DRIVE: warning only, DRIVE continues.
- Stop encoder UART during calibration: calibration aborts and relay releases.
- Disconnect ADS1015 during DRIVE: warning only.
- Make ARM center verification exceed tolerance: ARM fails and reports both mV values.
- Keep publishing ARM=true after that failure: no automatic retry may occur;
  `rearm_required` must remain visible until DISARM or explicit ARM handling.
- Break USB during calibration: event 32769 must be published and automatic
  normal ARM must remain blocked after reconnect.
- Corrupt one NVS slot: the other valid generation must load.

## 8. Unresolved acceptance values

The final limits for center error, output error, stop distance, and total
watchdog-to-stop time remain `UNKNOWN`. Record measured distributions before
setting pass/fail numbers.
