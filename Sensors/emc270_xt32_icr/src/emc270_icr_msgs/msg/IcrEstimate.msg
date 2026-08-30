uint8 STATUS_UNINITIALIZED=0
uint8 STATUS_VALID=1
uint8 STATUS_LOW_YAW=2
uint8 STATUS_DEGENERATE=3
uint8 STATUS_STALE_INPUT=4
uint8 STATUS_ODOM_RESET=5
uint8 STATUS_EXCESS_RESIDUAL=6
uint8 STATUS_SENSOR_DISAGREEMENT=7

uint8 SOURCE_LIDAR=1
uint8 SOURCE_IMU_GYRO=2
uint8 SOURCE_IMU_ACCEL=4

std_msgs/Header header
geometry_msgs/Point center_in_lidar
float64[4] covariance_xy
float64 yaw_rate_rad_s
builtin_interfaces/Duration window
builtin_interfaces/Time valid_until
float64 fit_rms_m
float64 condition_number
uint8 status
uint8 source_mask
