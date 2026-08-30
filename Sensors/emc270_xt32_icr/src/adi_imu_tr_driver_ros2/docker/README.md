# Docker Development Environment

This document describes how to use the Docker-based development
environment for the ADI IMU TR Driver ROS2 (Robot Operating
System 2). It packages the ROS2 build, run, and test environment
into a container so you can develop without polluting the host.

## Files

Table 1. Files under `docker/`

| File | Purpose |
|---|---|
| `Dockerfile.humble` | Image definition for ROS2 Humble (Ubuntu 22.04) |
| `Dockerfile.jazzy` | Image definition for ROS2 Jazzy (Ubuntu 24.04) |
| `docker-compose.yml` | Service definitions for the `humble` / `jazzy` services |
| `.env` | UID/GID and device-path environment variables (not tracked by git) |

The Humble and Jazzy images are built separately and used as two
switchable services (`humble` / `jazzy`) in `docker-compose.yml`.

## Prerequisites

- Docker and Docker Compose v2 installed
- For a real IMU (Inertial Measurement Unit), it must be connected
  over USB (Universal Serial Bus) serial
- For GUI tools (RViz, etc.), the host must run X11

## Setting up .env

`.env` is not tracked by git (it is in `.gitignore`), so you must
create it yourself after cloning. Create `docker/.env` as follows:

```dotenv
DEV_UID=1000
DEV_GID=1000
DEV_USER=hogehoge
VIDEO_GID=44
RENDER_GID=110
# Enable only when using a real IMU. If unset, it falls back to
# /dev/null so the container can still start.
# IMU_DEVICE=/dev/ttyACM0
```

Table 2. Variables in `.env`

| Variable | Default | Description |
|---|---|---|
| `DEV_UID` | 1000 | UID of the container user |
| `DEV_GID` | 1000 | GID of the container user |
| `DEV_USER` | hogehoge | Name of the container user |
| `VIDEO_GID` | 44 | GID of the `video` group for GPU access |
| `RENDER_GID` | 110 | GID of the `render` group for GPU access |
| `IMU_DEVICE` | (unset) | Device path of the real IMU |

Matching `DEV_UID` / `DEV_GID` to your host values keeps the build
artifacts (`build/`, `install/`, etc.) on the mounted workspace
owned by your host user. Check them on the host with:

```bash
id -u   # -> set as DEV_UID
id -g   # -> set as DEV_GID
```

If you use a GPU, match `VIDEO_GID` / `RENDER_GID` to the actual
host group GIDs:

```bash
getent group video    # -> VIDEO_GID
getent group render   # -> RENDER_GID
```

## Build

Build the container images. Humble and Jazzy are built separately.

```bash
# Run from the docker/ directory
cd docker

# Build the Humble image
docker compose build humble

# Build the Jazzy image
docker compose build jazzy
```

ROS dependencies are baked in at build time via `rosdep`, so there
is no need to install them on every container start.

## Start and work inside the container

```bash
cd docker

# Start the Jazzy service (detached)
docker compose up -d jazzy

# Open a bash shell inside the container
docker exec -it adi-imu-tr-driver-jazzy bash

# Stop and remove
docker compose down
```

For Humble, replace the service and container names with
`humble` / `adi-imu-tr-driver-humble`.

Table 3. Services and container names

| Service | Image | Container name |
|---|---|---|
| `humble` | `adi-imu-tr-driver:humble` | `adi-imu-tr-driver-humble` |
| `jazzy` | `adi-imu-tr-driver:jazzy` | `adi-imu-tr-driver-jazzy` |

The workspace is mounted read-write at
`~/ros2_ws/src/adi_imu_tr_driver_ros2` inside the container, so
`colcon build` artifacts remain on the host.

## Build and run inside the container

```bash
# The working directory is ~/ros2_ws (set in .bashrc)
cd ~/ros2_ws

# Build the package
colcon build --packages-select adi_imu_tr_driver_ros2
source install/setup.bash

# Launch with defaults (Attitude mode, 100 Hz, with RViz)
ros2 launch adi_imu_tr_driver_ros2 adis_rcv_csv.launch.py
```

Sourcing `/opt/ros/<distro>/setup.bash` and `install/setup.bash` is
wired into `.bashrc`, so it happens automatically when you enter the
container.

## Connecting a real IMU

`docker-compose.yml` does not use `privileged`; it maps only the USB
serial device explicitly. When using a real device, set `IMU_DEVICE`
in `.env`:

```dotenv
IMU_DEVICE=/dev/ttyACM0
```

Check the device path on the host:

```bash
ls -l /dev/ttyACM*
```

When `IMU_DEVICE` is set, the host device always appears as
`/dev/ttyACM0` inside the container. If it is unset, it falls back to
`/dev/null`, so the container can still start without a real device.

## Using the GUI (RViz)

With `network_mode: host` and the X11 socket mount, RViz running
inside the container can be displayed on the host. Allow X11 access
on the host before starting:

```bash
xhost +local:docker
```

The `DISPLAY` environment variable is inherited from the host by
`docker-compose.yml`, so no extra configuration is needed.

## Mounts

Table 4. Host-to-container mounts

| Host | Container | Purpose |
|---|---|---|
| `..` (repository) | `~/ros2_ws/src/adi_imu_tr_driver_ros2` | Source and artifacts |
| `/tmp/.X11-unix` | `/tmp/.X11-unix` | X11 GUI display |

## Troubleshooting

Table 5. Common issues and fixes

| Symptom | Fix |
|---|---|
| Artifacts owned by root | Match `DEV_UID`/`DEV_GID` in `.env` to the host `id` and rebuild |
| RViz does not show up | Run `xhost +local:docker` on the host |
| IMU not found | Set `IMU_DEVICE` in `.env` to the real device path and restart |
| GPU not available | Reflect `getent group video/render` GIDs in `.env` |
