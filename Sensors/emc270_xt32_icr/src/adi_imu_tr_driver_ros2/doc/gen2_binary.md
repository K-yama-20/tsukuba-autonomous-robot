# TR-IMU-Platform2 (2nd Gen / Binary)

Driver for the TR-IMU-Platform2, which communicates IMU data via a binary protocol.
Outputs quaternion, acceleration, and angular velocity simultaneously, publishing both TF broadcasts and IMU topics.

## Compatible Sensors

Supports all ADI IMU sensors mounted on the TR-IMU-Platform2 board. The sensor model is auto-detected at startup.

## Supported Environments

| OS | ROS2 | Branch |
|----|------|--------|
| Ubuntu 22.04 LTS | Humble | `humble` |
| Ubuntu 24.04 LTS | Jazzy | `jazzy` |

## Setup

### Port Permissions

Add the user to the `dialout` group to access the USB port. (Skip if already done.)

```
$ sudo usermod -aG dialout $USER
```

Log out and log back in for the change to take effect.

### Install

```
$ cd [your package directory]
$ git clone --recursive https://github.com/technoroad/ADI_IMU_TR_Driver_ROS2
$ cd [your workspace directory]
$ rosdep update
$ rosdep install --from-paths src --ignore-src --rosdistro ${ROS_DISTRO} -y
```

### Build
Navigate to the `src` directory of your workspace and run the following commands.
```
$ cd [your workspace directory]
$ colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release --packages-select adi_imu_tr_driver_ros2
$ source ./install/setup.bash
```

## Usage

Unlike the 1st gen driver, there is no mode selection. Quaternion, acceleration, and angular velocity are always output simultaneously.

### Launch

```
$ ros2 launch adi_imu_tr_driver_ros2 adis_rcv_bin.launch.py
```

### Launch Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `device` | `/dev/ttyACM0` | Serial device path |
| `frame_id` | `imu` | IMU frame name |
| `parent_id` | `odom` | Parent frame name |
| `rate` | `100.0` | Publish rate [Hz] |
| `publish_tf` | `True` | Publish the IMU attitude TF |
| `with_rviz` | `True` | Whether to launch RViz2 |

Example:
```
$ ros2 launch adi_imu_tr_driver_ros2 adis_rcv_bin.launch.py device:=/dev/ttyACM0 rate:=100.0 with_rviz:=False
```

## Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/imu/data_raw` | sensor_msgs/Imu | Quaternion + acceleration + angular velocity |
| `/tf` | tf2_msgs/TFMessage | IMU pose TF broadcast (disabled when `publish_tf` is false) |
| `/diagnostics` | diagnostic_msgs/DiagnosticArray | Sensor status |

## Service Commands

Commands can be sent to the device via `/imu/cmd_srv` (adi_imu_tr_driver_ros2/srv/SimpleCmd).

- `cmd`: Command ID in hex string (e.g. `'0x30'`)
- `args`: Data bytes in hex strings, up to 8 bytes. Missing bytes are zero-padded.

### Action Commands

| cmd | Description | Example |
|-----|-------------|---------|
| `0x30` | NOP (connectivity check) | `"{cmd: '0x30', args: []}"` |
| `0x31` | Start periodic telemetry | `"{cmd: '0x31', args: []}"` |
| `0x32` | Stop periodic telemetry | `"{cmd: '0x32', args: []}"` |
| `0x33` | Reset attitude estimation | `"{cmd: '0x33', args: []}"` |
| `0xB0` | Reboot the MCU | `"{cmd: '0xB0', args: ['0x00']}"` |
| `0xB1` | Enter DFU mode (key 0x12,0x34,0x56,0x78) | `"{cmd: '0xB1', args: ['0x12', '0x34', '0x56', '0x78']}"` |

### Settings Commands

| cmd | Description | Example |
|-----|-------------|---------|
| `0x70` | Read settings | `"{cmd: '0x70', args: []}"` |
| `0x71` | Save settings to flash | `"{cmd: '0x71', args: ['0x12', '0x34']}"` |
| `0x72` | Reset settings to defaults | `"{cmd: '0x72', args: []}"` |
| `0x73` | Set peripheral enable (bit0:USB, bit1:FDCAN, bit2:UART) | `"{cmd: '0x73', args: ['0x05']}"` |
| `0x74` | Set 32-bit read ON(1)/OFF(0) | `"{cmd: '0x74', args: ['0x01']}"` |
| `0x75` | Set attitude estimation filter (0-5) | `"{cmd: '0x75', args: ['0x02']}"` |
| `0x76` | Set gravity correction ON(1)/OFF(0) | `"{cmd: '0x76', args: ['0x01']}"` |
| `0x77` | Set IN0 pin config (pull resistor, trigger) | `"{cmd: '0x77', args: ['0x02', '0x00']}"` |

Example:
```
$ ros2 service call /imu/cmd_srv adi_imu_tr_driver_ros2/srv/SimpleCmd "{cmd: '0x33', args: []}"
$ ros2 service call /imu/cmd_srv adi_imu_tr_driver_ros2/srv/SimpleCmd "{cmd: '0x75', args: ['0x02']}"
```

**Note**: To persist settings changes (`0x73`-`0x77`), run `0x71` (save) after making changes, then `0xB0` (reboot) to apply. `0xB0`/`0xB1` are option commands and return no response. Reboot takes ~3 s, periodic telemetry does not auto-resume, and the spec recommends waiting ~1 min for output stability.

## Protocol Overview

See the communication specification document for full details.

- Packet structure: `Header(0xAA,0xAA) + CommandID + Length + Data + Checksum`
- Byte order: Little-endian (LSB first)
- Checksum: One's complement of individual byte sum
- Telemetry response: 70 bytes fixed (Length=64)
- Settings response: 70 bytes fixed (Length=64)
