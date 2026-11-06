# IFD-52 config/motion_compensation (REV-118, DEC-181): the dead-band compensation of gouda_motion_controller (DEC-171 plan A),
# entered by the human in the monitor's /config. Stick amounts in [0, 1); NaN = not set (that direction is not compensated).
std_msgs/Header header
uint32 config_revision
float64 forward_min
float64 forward_threshold
float64 reverse_min
float64 reverse_threshold
float64 turn_min
float64 turn_threshold
# REV-241 (DEC-450): the speed-feedback layer of gouda_motion_controller (feedforward from the measured stick -> speed map plus a
# PI on the GLIM speed, #65). Off unless speed_feedback_enabled is true (an unset field is false). Gains: stick amount per (m/s) or
# (rad/s) for P and per (m/s * s) or (rad/s * s) for I; i_limit: the largest |integral| in stick amount; odometry_timeout_s: an
# older localization/odometry drives on the feedforward alone. NaN = not set (then the PI is not used: feedforward alone).
bool speed_feedback_enabled
float64 forward_kp
float64 forward_ki
float64 forward_i_limit
float64 turn_kp
float64 turn_ki
float64 turn_i_limit
float64 odometry_timeout_s
