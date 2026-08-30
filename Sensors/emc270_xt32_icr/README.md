# EMC-270 / PandarXT 32 online ICR estimator

ROS 2 Jazzy packages for estimating the horizontal instantaneous centre of
rotation (ICR) of an EMC-270 from PandarXT 32 LiDAR odometry. The co-mounted
ADIS16607-2 is used for time alignment, yaw-rate assistance, and an independent
lever-arm consistency check.

The output is an **operational, time-varying ICR**, not a surveyed rear-axle
centre. Without an external ground-truth survey, the supplied validation tools
report repeatability rather than absolute accuracy. `z = 0` denotes the point
where the vertical ICR axis intersects the LiDAR's horizontal plane; it is not
the floor height.

## Packages

- `emc270_icr_msgs`: `ImuTelemetry` and `IcrEstimate` interfaces.
- `adi_imu_tr_driver_ros2`: pinned TechnoRoad fork that drains every binary
  telemetry packet and preserves `/imu/data_raw` and `/imu/cmd_srv`.
- `emc270_icr_estimator`: fast SE(2) and robust two-second ICR estimators.
- `emc270_icr_bringup`: live/replay launch files, sensor configuration, and
  repeatability reporting.

## Ubuntu 24.04 / ROS 2 Jazzy quick start

```bash
source /opt/ros/jazzy/setup.bash
sudo apt install python3-colcon-common-extensions python3-vcstool python3-rosdep
vcs import . < emc270_icr.repos
git -C src/hesai_ros_driver submodule update --init --recursive
# Run `sudo rosdep init` once on a new Ubuntu installation.
rosdep update
rosdep install --from-paths src --ignore-src --rosdistro jazzy -y
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release
source install/setup.bash
colcon test --event-handlers console_direct+
colcon test-result --verbose
```

The Ubuntu account running the IMU node must have access to the selected
`/dev/ttyACM*` device (normally via the `dialout` group). Do not run the full
sensor stack as root to bypass a permissions problem.

Copy the real XT32 angle/firetime correction files into an untracked local
directory and update a local copy of the Hesai YAML before live operation. The
checked-in Hesai configuration intentionally contains `REQUIRED` placeholders
and the live launch refuses to start until they are replaced.

```bash
ros2 launch emc270_icr_bringup icr_live.launch.py \
  hesai_config:=/absolute/path/to/hesai_xt32.local.yaml \
  fixture_config:=/absolute/path/to/fixture_extrinsics.local.yaml
```

For rosbag replay, start the estimator and KISS-ICP without hardware drivers:

```bash
ros2 launch emc270_icr_bringup icr_replay.launch.py \
  bag:=/absolute/path/to/bag \
  fixture_config:=/absolute/path/to/fixture_extrinsics.local.yaml \
  output_bag:=/absolute/path/to/replay_output
```

Replay deliberately publishes only the recorded raw `/lidar_points` and
`/imu/telemetry`; it does not replay the old KISS/ICR outputs alongside newly
computed ones. The launch exits when playback ends and can record the derived
outputs with `output_bag`. Run it twice, export both `/icr/smoothed` streams,
using `export_icr_csv.py --allow-missing-manifest`, and compare them:

```bash
ros2 run emc270_icr_bringup compare_icr_csv.py replay_1.csv replay_2.csv \
  --output /absolute/path/to/determinism.json
```

See `docs/field_test_protocol.md` before using a result in control software.
Consumers must check both `status == VALID` and `valid_until`; a cached TF by
itself is never evidence that the estimate is current.

The live launch remaps the estimator's diagnostic array to
`/icr/diagnostics`. KISS-ICP v1.3.0 does not expose a tracking-health API, so
the reported KISS state is explicitly labelled as derived from point-cloud and
odometry freshness, reset detection, frame checks, and fit residuals.

## Record and score a controlled trial

After the 60-second warm-up and pre-test static recording described in the
field protocol, record one two-rotation motion trial with its configuration
hashes and test labels:

```bash
ros2 run emc270_icr_bringup record_trial.py \
  --output-root /absolute/path/to/trials \
  --profile no_load --load-kg 0 \
  --yaw-band 0.15-0.25 --direction ccw --repeat 1 \
  --front-pressure-kpa 240 --rear-pressure-kpa 210 \
  --fixture-config /absolute/path/to/fixture_extrinsics.local.yaml \
  --hesai-config /absolute/path/to/hesai_xt32.local.yaml
```

Stop recording after two complete rotations. The recorder refuses pressure
values outside the planned ranges and refuses to overwrite an existing trial.
It writes `trial_manifest.json` beside the bag.

Export each trial and combine the three repeats for each condition:

```bash
ros2 run emc270_icr_bringup export_icr_csv.py \
  --bag /absolute/path/to/trial/bag --output /absolute/path/to/trial.csv \
  --profile no_load --yaw-band 0.15-0.25 --direction ccw --repeat 1

ros2 run emc270_icr_bringup generate_repeatability_report.py \
  --output-dir /absolute/path/to/report /absolute/path/to/*.csv

ros2 run emc270_icr_bringup check_runtime_acceptance.py \
  --bag /absolute/path/to/trial/bag \
  --output /absolute/path/to/report/runtime.json
```

The runtime check returns `RUNTIME_MEASUREMENT_INVALID` instead of guessing if
the LiDAR point timestamps cannot be related to the ROS clock. The geometric
report deliberately uses `REPEATABILITY_PASS/FAIL`; absolute rear-axle accuracy
and floor Z remain `UNKNOWN`. Both acceptance commands exit non-zero for a
failed or invalid result so they can be used as test gates.

Acceptance CSVs require the completed `trial_manifest.json` created by the
recorder and embed its SHA-256. The report rejects missing manifests, reused
bags, incomplete repeat IDs, out-of-band yaw rates, LiDAR-only samples, or any
missing cell in the full 12-condition matrix.

## Local algorithm tests (without ROS)

The estimator core can be tested on macOS or Linux when Eigen3 is installed:

```bash
cmake -S . -B build/standalone
cmake --build build/standalone
ctest --test-dir build/standalone --output-on-failure
```
