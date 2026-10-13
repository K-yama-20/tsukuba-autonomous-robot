# ROS 2 Jazzy setup

## Install and build

On Ubuntu 24.04 with ROS 2 Jazzy installed:

```bash
sudo apt install python3-colcon-common-extensions python3-rosdep
cd /path/to/Joystick270_Firmware/ros2_ws
source /opt/ros/jazzy/setup.bash
rosdep update
rosdep install --from-paths src --ignore-src --rosdistro jazzy -y
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release
source install/setup.bash
```

The user running the node must have serial access, normally through the
`dialout` group. Do not run the node as root to bypass permissions.

## Stable USB path

```bash
ls -l /dev/serial/by-id/
```

Copy `config/driver.example.yaml` outside the installed package, replace
`REQUIRED` with that absolute path, and start:

```bash
ros2 launch emc270_joystick_driver driver.launch.py \
  config:=/absolute/path/to/driver.local.yaml
```

The launch file refuses a missing relative path or a file containing
`REQUIRED`.

## Set endpoint preset

The following numbers are placeholders and must not be copied to a vehicle.
Replace every `REQUIRED_*` token with measured values before running the call.

```text
ros2 service call /emc270_joystick_driver/set_preset \
  emc270_joystick_msgs/srv/SetPreset \
  "{x_negative_mv: REQUIRED_X_LEFT,
    x_positive_mv: REQUIRED_X_RIGHT,
    y_negative_mv: REQUIRED_Y_REVERSE,
    y_positive_mv: REQUIRED_Y_FORWARD,
    x_seed_mv: 2500, y_seed_mv: 2500,
    dac_full_scale_mv: 4990, watchdog_ms: 300,
    slew_full_scale_ms: 1000, motion_threshold_mm_s: 10,
    output_warn_tolerance_mv: 40}"
```

Confirm acceptance on `~/event`, `~/status`, and `/diagnostics`; the service
response only means that the request was queued to the serial link.

## Calibrate

Start the encoder-speed ESP32 first and confirm `encoder_valid: true`:

```bash
ros2 topic echo /emc270_joystick_driver/status
ros2 service call /emc270_joystick_driver/start_calibration std_srvs/srv/Trigger '{}'
```

Abort:

```bash
ros2 service call /emc270_joystick_driver/abort_calibration std_srvs/srv/Trigger '{}'
```

CSV samples are stored in `log_directory`. Recover the ESP32 copy after an
interrupted USB session:

```bash
ros2 service call /emc270_joystick_driver/recover_log std_srvs/srv/Trigger '{}'
python3 tools/decode_calibration_log.py \
  calibration_123.recovered.frames calibration_123.recovered.csv
```

## Send normalized commands

For a bench-only zero command:

```bash
ros2 topic pub --rate 50 /emc270_joystick_driver/command \
  emc270_joystick_msgs/msg/NormalizedCommand \
  "{x: 0.0, y: 0.0, arm: true}"
```

The driver treats an upstream command older than 300 ms as stale. It stops
asserting ARM rather than repeating an old motion command. After a fresh
command returns, it sends neutral for 600 ms so the ESP32 can observe its full
500 ms neutral qualification window before automatic re-ARM.

If `status.rearm_required` becomes true, continuously publishing `arm: true`
does not retry. Either publish `arm: false` once and then return to `arm: true`,
or make an explicit call:

```bash
ros2 service call /emc270_joystick_driver/arm std_srvs/srv/Trigger '{}'
```

During calibration, a USB link loss publishes event code `32769`, closes the
live CSV, and blocks automatic ARM. Restart calibration explicitly after
checking the recovered log and the vehicle state.

No `/cmd_vel` conversion is provided until the EMC-270 relationship between
joystick voltage and physical linear/angular velocity has been measured.
