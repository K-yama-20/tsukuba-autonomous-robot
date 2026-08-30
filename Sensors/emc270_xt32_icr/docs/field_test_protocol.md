# EMC-270 field validation protocol

This protocol measures repeatability. It does not establish absolute position
relative to the physical rear axle.

1. Use a flat, dry, non-slip floor and a static, geometrically rich LiDAR
   environment. Establish a two-metre exclusion radius, an observer, and an
   accessible emergency stop.
2. Record front tyre pressure (230--250 kPa), rear pressure (200--220 kPa),
   fixture revision, correction-file hashes, software commits, temperature,
   and the secured load profile. Never use a person as the test ballast.
   Before collecting acceptance data, verify the measured static transform:
   a wall in front must lie on positive `xt32_link.x`, a wall to the left on
   positive `xt32_link.y`, and a counter-clockwise turn must produce positive
   yaw rate. Confirm that `xt32_link`, `hesai_lidar_native`, and `imu_link`
   each have exactly one TF parent. Do not adjust signs in the estimator to
   compensate for an unverified native-frame transform.
3. Warm the IMU while stationary for at least 60 seconds. Record 30 seconds of
   stationary data before and after the motion trials. Confirm
   `imu_gravity_compensated=true` and `imu_accel_bias_calibrated=true` in
   `/icr/diagnostics`; otherwise the acceleration lever-arm check is disabled
   and the acceptance exporter will not retain samples. If `/icr/reset` is
   called, keep the robot stationary until the bias-calibrated flag returns.
4. For both the completed no-load robot and the secured representative load,
   perform two complete rotations in each direction in measured yaw-rate bands
   0.15--0.25, 0.30--0.45, and 0.50--0.70 rad/s. Repeat every condition three
   times. Begin counting the two rotations only after `/icr/smoothed` is
   `VALID` with the `IMU_ACCEL` source bit; the report requires at least
   `4*pi` radians of valid, gap-bounded coverage in every repeat.
5. Record `/lidar_points`, `/kiss/odometry`, `/imu/telemetry`, `/icr/fast`,
   `/icr/smoothed`, `/icr/diagnostics`, `/diagnostics`, the Hesai packet-loss
   and PTP status topics, `/tf`, and `/tf_static`.
   Use `record_trial.py` for each motion run so pressure, load, direction,
   repeat number, fixture hash, and Hesai correction hashes are inseparable
   from the bag. Use separate bags for the 30-second pre- and post-test static
   records.
6. Generate the geometry report with `generate_repeatability_report.py` and
   the timing result with `check_runtime_acceptance.py`. A condition
   passes only when the smoothed 95% confidence radius and maximum pairwise
   repeat-median distance are both at most 0.010 m. Timing passes only when the
   scan-end-to-fast-publication p95 is below 100 ms and smoothed processing p95
   is below 200 ms.
7. Replay at least one representative bag twice with `icr_replay.launch.py`,
   setting a different `output_bag` each time. Export both smoothed streams and
   require `compare_icr_csv.py` to return `DETERMINISTIC_PASS`.

If a condition fails, check the real unit's angle/firetime corrections,
fixture, floor slip, and KISS-ICP tracking first. Then add fixed targets; add
wheel odometry only as a comparison input. Add common PTP/PPS only after a
timing fault is demonstrated and TechnoRoad confirms the IMU_16607 board input.
