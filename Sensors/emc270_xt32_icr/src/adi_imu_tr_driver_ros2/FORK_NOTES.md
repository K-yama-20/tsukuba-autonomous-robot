# EMC-270 telemetry fork

This directory is based on TechnoRoad
`ADI_IMU_TR_Driver_ROS2` branch `jazzy` at commit
`742b7babec7e7a20937d4e8be0df77a771a1294a`. Its embedded `TR_IMU_LIB`
content corresponds to commit `324cb47c0160d7b249ad2d0ed75c3fbd72ce6382`.

The fork keeps the existing `/imu/data_raw` topic and `/imu/cmd_srv` service,
and adds the following behaviour:

- non-blocking serial polling that drains every complete telemetry packet;
- `imu_counter` duplicate rejection and gap accounting;
- `/imu/telemetry` at the sensor sample rate using SensorData QoS;
- the upstream reliable QoS and configured rate on `/imu/data_raw`;
- a robust affine MCU-time to ROS-time model with an explicit quality state;
- `/imu/reset_clock_model` for coordinated estimator resets;
- optional legacy TF publication, disabled by the EMC-270 bringup; and
- serialization of command-response and telemetry reads for composed or
  multi-threaded executors.

`CLOCK_PPS_OBSERVED` means only that the input bit was observed. It does not
claim that the IMU clock is disciplined. Do not connect PPS to the IMU_16607
board until TechnoRoad confirms the terminal function and 3.3 V electrical
conditions.
