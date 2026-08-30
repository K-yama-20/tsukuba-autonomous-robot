# ADI_IMU_TR_Driver_ROS2

ROS2 driver for Analog Devices MEMS IMU sensors connected via USB serial.

[Click here](https://github.com/technoroad/ADI_IMU_TR_Driver_ROS1) for ROS1 version.

## Demo movie

Click the thumbnail to open the youtube video.

[![Adi-IMU-TR](http://img.youtube.com/vi/2emmX7TSa1U/0.jpg)](https://www.youtube.com/watch?v=2emmX7TSa1U "Adi-IMU-TR")

## Supported Platforms

This driver supports two product lines, each with two generations:

|  | IMU Board | IMU Platform |
|--|-----------|-------------|
| **1st gen** | TR-IMU1647X (ADIS164xx) | TR-IMU-Platform |
| **2nd gen** | TR-IMU166XX (ADIS166xx) | TR-IMU-Platform2 |

Documentation is organized by generation and communication protocol:
- **1st gen** — CSV over Serial → [doc/gen1_csv.md](doc/gen1_csv.md)
- **2nd gen** — Binary over Serial → [doc/gen2_binary.md](doc/gen2_binary.md)

### How to identify your board

- IMU Board product number starts with **164xx** → 1st gen / **166xx** → 2nd gen
- IMU Platform board name: **TR-IMU-Platform** → 1st gen / **TR-IMU-Platform2** → 2nd gen


See each platform's document for details.

## Cloning and Updating

The IMU library lives in the `lib/` git submodule, so it must be fetched
together with the main repository.

```bash
# First clone (fetch submodules at the same time)
git clone --recurse-submodules <repo-url>

# Update an existing checkout
git pull
git submodule update --init --recursive
```

## License

MIT
