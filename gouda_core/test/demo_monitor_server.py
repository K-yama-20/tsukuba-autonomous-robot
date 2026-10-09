"""Layout check of the monitor page without ROS: serves web/ with a clearly marked DEMO state.

    python3 gouda_core/test/demo_monitor_server.py [port]

Every value shown comes from this script, not from a robot; the mode run_id is "DEMO-NOT-REAL" so that a screenshot can
never be mistaken for an operating record. Commands are answered with a refusal that says DEMO.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core.monitor_core import MonitorCore  # noqa: E402
from gouda_core.monitor_server import MonitorServer  # noqa: E402


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    core = MonitorCore()
    core.on_mode({'stamp': time.time(), 'mode': 1, 'processing_state': 'idle', 'run_id': 'DEMO-NOT-REAL', 'remaining_waypoints': 0, 'current_section': -1,
                  'stop_reason': '', 'speed_limit_application_state': 'unknown', 'previous_mode': 0, 'human_pause_or_end_recorded': False,
                  'initial_pose_required': False, 'state_revision': 1})
    core.on_record({'log_active': 'False', 'rosbag_active': 'False', 'session_dir': '', 'auto_started_by': '', 'log_started_by': '', 'rosbag_started_by': '',
                    'last_gap': '', 'failures': '0', 'status_revision': '0', 'level': 0, 'message': 'log stopped, rosbag stopped (DEMO)'})
    core.on_nodes(['/gouda_mode_manager', '/gouda_recorder', '/gouda_monitor'])
    core.on_decision({'node': 'gouda_mode_manager', 'event': 'boot', 'transition_id': 'TR-01', 'reason': 'no persisted previous mode record -> manual (RQ-I080)', 'details': '{"demo": true}'})
    core.on_decision({'node': 'gouda_mode_manager', 'event': 'human_request', 'transition_id': 'TR-06', 'reason': 'refused: pause is not accepted in mode manual (accepted in autonomy)', 'details': '{"accepted": false, "demo": true}'})
    cfg = {'values': {'lidar_mount_z_m': 'UNKNOWN', 'lidar_axis_mapping': 'UNKNOWN'}, 'kinds': {'lidar_mount_z_m': 'number', 'lidar_axis_mapping': 'text'}, 'config_revision': 0, 'updated_at': None, 'path': '(demo)', 'unknown_count': 2}
    server = MonitorServer(Path(__file__).resolve().parents[1] / 'web', core.snapshot, lambda: cfg,
                           lambda name, body: {'ok': False, 'message': f'DEMO: {name} is not connected to a robot'},
                           lambda body: {'ok': False, 'message': 'DEMO: config is not saved', 'config': cfg}, port=port, keepalive_s=float(sys.argv[2]) if len(sys.argv) > 2 else 3.0)  # demo only
    print('DEMO monitor at', server.start(), flush=True)
    try:
        while True: time.sleep(3600)
    except KeyboardInterrupt:
        server.stop()


if __name__ == '__main__': main()
