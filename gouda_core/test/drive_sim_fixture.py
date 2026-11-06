"""TEST ONLY (第179便): the driving simulator's free-space map and waypoint set for one scenario, stored as stages 5-3 / 5-4 store them
(the same form as stage56_fixture.py). Prints the StartAutonomy request fields (JSON) with the initial pose.
usage: python3 drive_sim_fixture.py <data_root> <scenario>"""
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import drive_sim_core as ds  # noqa: E402
from gouda_core import keepout_mask as km  # noqa: E402
from gouda_core import speed_mask as sm  # noqa: E402
from gouda_core import waypoints as wp  # noqa: E402

root, sc = Path(sys.argv[1]), ds.scenario(sys.argv[2])
RES, W, H, OX, OY = 0.1, 700, 500, -15.0, -25.0     # 70 m x 50 m of free space (synthetic; not a vehicle value)
MAP_ID, MAP_HASH = 'origin_drive_sim', 'synthetic-free-map-drive-sim'
mdir = root / 'maps' / MAP_ID / 'converted' / '001'; mdir.mkdir(parents=True, exist_ok=True)
(mdir / 'map.pgm').write_bytes(b'P5\n%d %d\n255\n' % (W, H) + bytes([254]) * (W * H))
(mdir / 'map.yaml').write_text(f'image: map.pgm\nmode: trinary\nresolution: {RES}\norigin: [{OX}, {OY}, 0.0]\nnegate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.25\n')
(mdir / 'pointcloud_map').mkdir(exist_ok=True)   # ND-07's files; the test's ND-07 is nd07_stub.py, which does not read them
(mdir / 'pointcloud_map' / 'metadata.yaml').write_text('x_resolution: 20.0\ny_resolution: 20.0\n')
(mdir / 'trajectory_imu.txt').write_text('0.0 0.0 0.0 0.0 0.0 0.0 0.0 1.0\n')
(mdir / 'manifest.json').write_text(json.dumps({'revision': 1, 'content_hash': MAP_HASH, 'created_at': time.time()}))
ws = wp.WaypointSet(MAP_ID, 1, MAP_HASH, [wp.Waypoint(x, y, skip_allowed=i in sc.skip_marks) for i, (x, y) in enumerate(sc.route[1:])],
                    [sc.limit_mps] * (len(sc.route) - 2), areas=[])
db = wp.RouteDatabase(root / 'routes')
sid, rev, tmp = db.begin(None)
g = sm.MapGeometry(resolution=RES, origin_x=OX, origin_y=OY, width=W, height=H)
res = sm.generate([(w.x, w.y) for w in ws.waypoints], ws.section_limits_mps, g, 1.0, 0.05)
files = sm.write_mask(res, g, tmp, 'speed_filter_mask', 'costmap_filter_info')
kfiles, krec = km.write(km.rasterize(ws.areas, g), g, tmp, '/keepout_filter_mask', '/keepout_costmap_filter_info'); files.update(kfiles)
ok, msg, man = db.publish(sid, rev, tmp, ws, files, [], {'half_width_m': 1.0, 'step_mps': 0.05, 'keepout': krec})
assert ok, msg
(sx, sy), (nx, ny) = sc.route[0], sc.route[1]
print(json.dumps({'waypoint_set_id': sid, 'waypoint_set_revision': str(rev), 'waypoint_set_hash': man['content_hash'], 'map_id': MAP_ID, 'map_revision': '1',
                  'map_hash': MAP_HASH, 'initial_pose': {'x': sx, 'y': sy, 'yaw': math.atan2(ny - sy, nx - sx)}, 'request_id': f'drive-sim-{int(time.time())}'}))
