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
