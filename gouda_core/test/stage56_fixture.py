"""Stage 5-6 VM test fixture (test only): a synthetic converted map (free space) and a waypoint set with its speed mask, stored as
stages 5-3 / 5-4 store them, under <data_root>. Prints the StartAutonomy request fields (JSON) for the test script.
usage: python3 stage56_fixture.py <data_root> [corridor|free] [keepout|gap=<m>]
keepout (REV-137, TS-47): a 「走行禁止」 area KEEPOUT_SQUARE across the straight section (1,0)->(4,0) is drawn into the set.
gap=<m> (REV-140, TS-47, DEC-229): two keepout bands at the same x as the square, across the whole map, leaving a gap of <m>
centred on the straight section (the robot can only go through the gap). The areas are also written to <data_root>/keepout_areas.json
and the set to <data_root>/fixture_set.json (for the TS-47 check and the monitor save check of the test script).
corridor (plan C, REV-131, TS-44): the map is the swept corridor of a synthetic mapping walk along the waypoints instead of free
space (map_convert.corridor_grid, PRM-96 / PRM-97 from the generated files with the trial file, as the test stack loads them)."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import speed_mask as sm  # noqa: E402
from gouda_core import waypoints as wp  # noqa: E402

root = Path(sys.argv[1])
RES, W, H, OX, OY = 0.1, 300, 300, -15.0, -15.0          # 30 m x 30 m of free space (synthetic; not a vehicle value)
MAP_HASH = 'synthetic-free-map-stage56'
mdir = root / 'maps' / 'origin_st56' / 'converted' / '001'; mdir.mkdir(parents=True, exist_ok=True)
if len(sys.argv) > 2 and sys.argv[2] == 'corridor':
    import numpy as np, yaml
    from gouda_core import map_convert as mc
    from gouda_core import sensor_config
    # the generated values (approved) overlaid with the trial file, as the test stack loads them (trial:=true)
    trial = sensor_config.read_node_params(str(Path(__file__).resolve().parents[2] / 'design' / 'generated' / 'params'), 'gouda_map_creator', True)
    walk = np.array([(x / 10, 0.0) for x in range(0, 41)] + [(4.0, y / 10) for y in range(1, 31)])   # mapping walk (0,0)->(4,0)->(4,3)
    pieces, _ = mc.split_at_gaps(walk, trial['corridor_gap_m'])
    grid, gres = mc.corridor_grid(walk, pieces, trial['corridor_half_width_m'], RES)
    mc.write_map(grid, gres, mdir)
    print(f'corridor map: half width {trial["corridor_half_width_m"]} m, {gres.free} free cells', file=sys.stderr)
else:
    (mdir / 'map.pgm').write_bytes(b'P5\n%d %d\n255\n' % (W, H) + bytes([254]) * (W * H))
    (mdir / 'map.yaml').write_text(f'image: map.pgm\nmode: trinary\nresolution: {RES}\norigin: [{OX}, {OY}, 0.0]\nnegate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.25\n')
# the files ND-07 (A3) needs on the map (REV-128); the test's ND-07 is the stand-in nd07_stub.py, which does not read them
(mdir / 'pointcloud_map').mkdir(exist_ok=True)
(mdir / 'pointcloud_map' / 'metadata.yaml').write_text('x_resolution: 20.0\ny_resolution: 20.0\n')
(mdir / 'trajectory_imu.txt').write_text('0.0 0.0 0.0 0.0 0.0 0.0 0.0 1.0\n')
(mdir / 'manifest.json').write_text(json.dumps({'revision': 1, 'content_hash': MAP_HASH, 'created_at': time.time()}))
# synthetic; the test script checks the robot never enters it. Away from the start pose (1.5, 0): the footprint reaches 0.55 m
# forward and turning sweeps about 0.63 m (DEC-223: the human leaves that room; a square from x=2.0 stopped RPP at the start)
KEEPOUT_SQUARE = [[2.8, -0.5], [3.4, -0.5], [3.4, 0.5], [2.8, 0.5]]
areas = [{'kind': 'keepout', 'polygon': KEEPOUT_SQUARE}] if 'keepout' in sys.argv[3:] else []
for a in sys.argv[3:]:
    if a.startswith('gap='):
        half = float(a[4:]) / 2
        areas = [{'kind': 'keepout', 'polygon': [[2.8, half], [3.4, half], [3.4, OY + H * RES - 0.5], [2.8, OY + H * RES - 0.5]]},
                 {'kind': 'keepout', 'polygon': [[2.8, OY + 0.5], [3.4, OY + 0.5], [3.4, -half], [2.8, -half]]}]
(root / 'keepout_areas.json').write_text(json.dumps(areas))
ws = wp.WaypointSet('origin_st56', 1, MAP_HASH, [wp.Waypoint(1.0, 0.0), wp.Waypoint(4.0, 0.0), wp.Waypoint(4.0, 3.0)], [0.3, 0.2], areas=areas)
db = wp.RouteDatabase(root / 'routes')
sid, rev, tmp = db.begin(None)
g = sm.MapGeometry(resolution=RES, origin_x=OX, origin_y=OY, width=W, height=H)
res = sm.generate([(w.x, w.y) for w in ws.waypoints], ws.section_limits_mps, g, 1.0, 0.05)
files = sm.write_mask(res, g, tmp, 'speed_filter_mask', 'costmap_filter_info')
from gouda_core import keepout_mask as km  # noqa: E402
# REV-137: the waypoint set's KeepoutFilter mask (no drawn area here: all unknown, no effect on Nav2)
kfiles, krec = km.write(km.rasterize(ws.areas, g), g, tmp, '/keepout_filter_mask', '/keepout_costmap_filter_info'); files.update(kfiles)
ok, msg, man = db.publish(sid, rev, tmp, ws, files, [], {'half_width_m': 1.0, 'step_mps': 0.05, 'keepout': krec})
assert ok, msg
(root / 'fixture_set.json').write_text(json.dumps(ws.to_dict()))
print(json.dumps({'waypoint_set_id': sid, 'waypoint_set_revision': str(rev), 'waypoint_set_hash': man['content_hash'],
                  'map_id': 'origin_st56', 'map_revision': '1', 'map_hash': MAP_HASH}))
