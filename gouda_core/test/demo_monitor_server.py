"""Layout check of the monitor page without ROS: serves web/ with a clearly marked DEMO state.

    python3 gouda_core/test/demo_monitor_server.py [port]

Every value shown comes from this script, not from a robot; the mode run_id is "DEMO-NOT-REAL" so that a screenshot can
never be mistaken for an operating record. Commands are answered with a refusal that says DEMO.
"""
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core.monitor_core import MonitorCore  # noqa: E402
from gouda_core.monitor_server import MonitorServer  # noqa: E402
from gouda_core import map_tab, png as pngmod  # noqa: E402

DEMO_ORIGIN = 'DEMO-NOT-REAL_origin'


# DEMO conversion: a synthetic scene converted by the real converter (not a robot map; the settings are DEMO values)
DEMO_SETTINGS = {'map_resolution_m': 0.1, 'ground_band_max_m': 0.1, 'obstacle_band_min_m': 0.15, 'obstacle_band_max_m': 1.2, 'occupied_min_points': 1,
                 'ground_cell_m': 0.5, 'ground_max_slope_deg': 10, 'ground_fill_radius_m': 1}


def demo_conversion() -> tuple:
    """Write a GLIM-like dump of a synthetic scene (ground 1.2 m below the origin rising 5 degrees, a curb, a box, a wall,
    tree canopy) and convert it. Returns (out_dir, stats)."""
    import numpy as np
    from gouda_core import map_convert as mc
    rng = np.random.default_rng(3); root = Path(tempfile.mkdtemp(prefix='gouda_demo_map_'))
    x = rng.uniform(0, 12, 12000); y = rng.uniform(0, 6, 12000); slope = np.tan(np.radians(5))
    z = -1.2 + slope * x + np.where(y > 4.5, 0.15, 0.0)
    box = np.c_[rng.uniform(6, 7, 400), rng.uniform(2, 3, 400), np.zeros(400)]; box[:, 2] = -1.2 + slope * box[:, 0] + rng.uniform(0, 0.7, 400)
    wall = np.c_[rng.uniform(0, 12, 1500), np.full(1500, 6.0), np.zeros(1500)]; wall[:, 2] = -1.2 + slope * wall[:, 0] + 0.15 + rng.uniform(0, 2, 1500)
    tree = np.c_[rng.uniform(9, 11, 300), rng.uniform(0.5, 2.5, 300), np.zeros(300)]; tree[:, 2] = -1.2 + slope * tree[:, 0] + rng.uniform(2.5, 3.5, 300)
    pts = np.concatenate([np.c_[x, y, z], box, wall, tree]).astype(np.float32)
    sub = root / 'dump' / '000000'; sub.mkdir(parents=True)
    (sub / 'data.txt').write_text('id: 0\nT_world_origin:\n1 0 0 0\n0 1 0 0\n0 0 1 0\n0 0 0 1\n'); (sub / 'points_compact.bin').write_bytes(pts.tobytes())
    stats = mc.convert(root / 'dump', root / 'out', DEMO_SETTINGS)
    return root / 'out', stats


DEMO_OUT, DEMO_STATS = demo_conversion()


def demo_map(rest, query):
    from gouda_core import map_convert as mc
    parts = [x for x in rest.split('/') if x]
    what = parts[2] if len(parts) >= 3 else ''
    if what == 'map.png':
        data, _, _ = pngmod.pgm_to_png((DEMO_OUT / 'map.pgm').read_bytes()); return 200, 'image/png', data
    if what in mc.VIEW_FILES:
        return 200, 'image/png', (DEMO_OUT / what).read_bytes()
    if what == 'terrain.json':
        return {'ok': True, 'terrain': json.loads((DEMO_OUT / 'terrain.json').read_text())}
    if what == 'manifest.json':
        return {'ok': True, 'manifest': {'settings': DEMO_SETTINGS, 'stats': DEMO_STATS, 'files': DEMO_STATS['files'],
                'converter': {'version': DEMO_STATS['converter'] + ' (DEMO scene)'}, 'content_hash': 'DEMO-NOT-REAL', 'created_at': time.time()}}
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
