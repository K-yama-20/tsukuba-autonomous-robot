# IFD-01 mode/state: current software mode and mission context summary (design/model.yaml).
# Published by gouda_mode_manager (ND-03) only; reliable, transient_local, depth 1.
# header.stamp is the ROS time of the transition or update. state_revision is monotonic; an old value is never re-published with a new stamp.
std_msgs/Header header

# The four software modes (RQ-I065). No other value exists; there is no "fully stopped" mode.
uint8 MODE_MANUAL=1     # 手動走行 (default at boot: RQ-I080, TR-01)
uint8 MODE_MAPPING=2    # 事前地図作成
uint8 MODE_AUTONOMY=3   # 自律走行
uint8 MODE_PAUSE=4      # 一時停止
uint8 mode

# Processing stage, separate from the mode (DEC-010): e.g. "idle", "map_converting", "goal_sending", "cancel_waiting", "recovering".
string processing_state
# Mission context (SO-01). Empty when no mission is loaded.
string run_id
uint32 remaining_waypoints
int32 current_section        # for recording only (RQ-I030); -1 when unknown
# Stop reason category (RQ-I029): "", "human", "plan_failure", "blocked", "localization_lost", "comm_lost", "node_fault".
string stop_reason
# Speed limit application state (DEC-047): "unknown", "applied", "out_of_band_unlimited", "out_of_mask_last_value", "mask_not_loaded", "".
string speed_limit_application_state
# Previous mode persisted across PC restart (RQ-I064) and whether a human pause/end preceded it (RQ-I025).
uint8 previous_mode
bool human_pause_or_end_recorded
# Set after a PC restart until a human initial-pose request is accepted (DEC-009).
bool initial_pose_required
uint64 state_revision
