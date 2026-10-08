# IFD-28 log/decision: a decision with its reason, run id and section id (RQ-I030).
# header.stamp is the decision time. Input receive times are carried separately; values that were not received are not recorded (RQ-I015).
std_msgs/Header header
string node             # publishing node name (ND-03 / ND-11 / ND-12)
string event            # e.g. "transition", "boot", "record_auto_start", "goal_sent"
string transition_id    # design transition id (TR-xx) when applicable, else ""
string reason
string run_id
int32 section_id        # -1 when not applicable
string[] input_names    # inputs referred to by the decision
builtin_interfaces/Time[] input_stamps  # receive time of each input, same order as input_names
string details          # JSON object with structured fields; never a guessed value
