# IFD-40 control/motion_hold: neutral request from gouda_mode_manager (ND-03) to gouda_motion_controller (ND-11).
# Published by ND-03 only; reliable, transient_local, depth 1 (REV-027). Custom type because a stop reason and the mode
# must travel with a time stamp (std_msgs/Bool has none; RQ-I055).
# hold=true is published in every software mode except 自律走行 (DEC-004). ND-11 outputs neutral when hold is true, when the
# last message is older than motion_hold_timeout_s (PRM-42), or when cmd_vel is stale (PRM-08). Before the first message is
# received ND-11 behaves as if hold were true.
std_msgs/Header header
bool hold
string reason     # why hold is requested, e.g. "mode=manual", "human_pause", "boot"
uint8 mode        # current software mode, same values as SoftwareMode.mode (1 manual, 2 mapping, 3 autonomy, 4 pause)
