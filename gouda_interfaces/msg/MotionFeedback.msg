# log/motion_feedback (REV-241, DEC-450): what gouda_motion_controller's speed-feedback layer did at each output, for the rosbag.
# Published at every output while active (also with the layer off: mode "off", only the targets, the odometry and the output).
# mode: off | ff_pi | ff_only | neutral | no_feedforward; reason: why ff_only / neutral / no_feedforward (empty for ff_pi).
# forward_* = the front-back axis (axes[0] of vehicle/joystick_command), turn_* = the turn axis (axes[1]). Stick amounts in
# [-1, 1]; *_out is what was sent. measured_* is the last localization/odometry twist (NaN = never received).
std_msgs/Header header
uint32 config_revision
string mode
string reason
float64 target_linear_x
float64 target_angular_z
float64 measured_linear_x
float64 measured_angular_z
float64 odometry_age_s
float64 forward_ff
float64 forward_p
float64 forward_i
float64 forward_out
float64 turn_ff
float64 turn_p
float64 turn_i
float64 turn_out
