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
from gouda_core import map_tab, png as pngmod  # noqa: E402

DEMO_ORIGIN = 'DEMO-NOT-REAL_origin'


def demo_pgm(w=60, h=40):
    """A synthetic DEMO map: unknown border, free floor, an occupied wall (not a robot map)."""
    px = bytearray([205] * (w * h))
    for y in range(5, h - 5):
        for x in range(5, w - 5): px[y * w + x] = 254
    for x in range(5, w - 5): px[20 * w + x] = 0
    return f'P5\n{w} {h}\n255\n'.encode() + bytes(px)


def demo_map(rest, query):
    parts = [x for x in rest.split('/') if x]
    if len(parts) >= 3 and parts[2] == 'map.png':
        data, _, _ = pngmod.pgm_to_png(demo_pgm()); return 200, 'image/png', data
    if len(parts) >= 3 and parts[2] == 'manifest.json':
        return {'ok': True, 'manifest': {'settings': {'map_resolution_m': 0.1, 'ground_band_max_m': 0.05, 'obstacle_band_min_m': 0.2, 'obstacle_band_max_m': 1.0, 'occupied_min_points': 1},
                'stats': {'width': 60, 'height': 40, 'resolution': 0.1, 'occupied': 50, 'free': 1450, 'unknown': 900, 'points_total': 0, 'points_obstacle': 0, 'points_ground': 0, 'submaps': 0},
                'converter': {'version': 'DEMO'}, 'content_hash': 'DEMO-NOT-REAL', 'created_at': time.time()}}
    return {'ok': False, 'message': 'DEMO'}


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
    def snapshot():
        s = core.snapshot()
        s['maps'] = {'origins': [{'origin_id': DEMO_ORIGIN, 'source_hash': 'DEMO-NOT-REAL', 'submaps': 0, 'created_at': time.time(), 'converted': [{'revision': 1}, {'revision': 2}]}], 'note': 'DEMO（ロボットの地図ではない）'}
        s['map_conversion'] = map_tab.ConversionTracker().snapshot()
        return s
    settings = {'ok': True, 'settings': [dict(x, default=None) for x in map_tab.CONVERSION_SETTINGS], 'note': 'DEMO: gouda_map_creator に接続していない'}
    server = MonitorServer(Path(__file__).resolve().parents[1] / 'web', snapshot, lambda: cfg,
                           lambda name, body: {'ok': False, 'message': f'DEMO: {name} is not connected to a robot'},
                           lambda body: {'ok': False, 'message': 'DEMO: config is not saved', 'config': cfg}, port=port, keepalive_s=float(sys.argv[2]) if len(sys.argv) > 2 else 3.0,  # demo only
                           get_routes={'/api/map/': demo_map, '/api/map_settings': lambda r, q: settings},
                           post_routes={'/api/map_reconvert': lambda r, b: {'ok': False, 'message': 'DEMO: not connected to gouda_map_creator'}})
    print('DEMO monitor at', server.start(), flush=True)
    try:
        while True: time.sleep(3600)
    except KeyboardInterrupt:
        server.stop()


if __name__ == '__main__': main()
