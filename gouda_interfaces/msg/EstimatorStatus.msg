# IFD-53 localization/status (REV-128, DEC-200 / DEC-203): the state of the global localization ND-07 (trial A3).
# NORMAL only when every input is fresh and every check passes; missing or unreadable inputs are never NORMAL (IF-010).
std_msgs/Header header
uint8 STATE_UNINITIALIZED=0
uint8 STATE_INITIALIZING=1
uint8 STATE_NORMAL=2
uint8 STATE_UNAVAILABLE=3
uint8 state
string reason                      # reason code when not NORMAL (localization_core.REASONS), empty when NORMAL
string detail                      # human-readable explanation
float64 ndt_nvtl                   # last nearest_voxel_transformation_likelihood of the NDT diagnostics (NaN: none)
int32 ekf_pose_no_update_count     # last pose_no_update_count of the EKF diagnostics (-1: none)
float64 ekf_xy_stddev_m            # square root of the larger eigenvalue of the EKF pose's x-y covariance (NaN: none)
float64 last_input_age_s           # age of the oldest of the inputs (EKF pose, NDT diagnostics, odometry) (NaN: one never came)
string map_id                      # converted map directory in use (empty: not configured)
