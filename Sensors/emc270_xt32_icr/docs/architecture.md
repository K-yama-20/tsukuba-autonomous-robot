# Architecture and safety boundaries

## Data flow

1. The Hesai driver publishes `/lidar_points` with each point's sensor
   timestamp. KISS-ICP deskews the scan and publishes `/kiss/odometry` for
   `xt32_link`.
2. The forked TechnoRoad driver drains all binary telemetry packets, fits an
   affine map from MCU boot time to ROS time, and publishes `/imu/telemetry`.
3. The ICR estimator produces a 100 ms fast result and a robust two-second
   result. The fast message is published before the smoothed fit runs. IMU data
   is only used after both the affine clock lock and an excited LiDAR/IMU
   correlation check; a measured offset may be held for at most 120 seconds
   while constant-rate motion makes correlation temporarily unobservable. A
   gyro that differs from LiDAR by more than the configured gate is rejected,
   and an acceleration fit must satisfy residual, conditioning, and position-
   uncertainty gates before it counts as an independent validation.
4. Valid estimates are published as messages and auxiliary TF children of
   `xt32_link`. The fixed robot frames are never re-parented or moved.

## Observable quantity

For planar body twist `(v_x, v_y, omega)`, the ICR axis in the current LiDAR
frame is `(-v_y / omega, v_x / omega)`. It is undefined for straight motion.
The smoothed estimator solves `p_i = c + R_i r` with Huber weights; its reported
centre is `-r` in the moving LiDAR frame.

## Safety contract

- The estimator never publishes drive commands.
- Invalid, stale, ill-conditioned, reset, or low-yaw input suppresses TF.
- Time synchronization failure disables IMU assistance but not LiDAR-only ICR.
- Missing or constant per-point timestamps invalidate precision output because
  KISS-ICP cannot satisfy the deskew contract.
- The odometry `child_frame_id` must be `xt32_link`; a mismatch invalidates and
  clears the estimation window.
- LiDAR/IMU disagreement is reported; the values are not forcibly fused.
- A downstream controller must fall back to its fixed vehicle model whenever
  the message is invalid or expired.

KISS-ICP v1.3.0 has no explicit tracking status output. The diagnostic field
`kiss_tracking_state` is therefore labelled `DERIVED`; it combines point-cloud
and odometry freshness, reset detection, frame agreement, condition number,
and residual gates rather than claiming an internal KISS state.
