"""Unit tests of the stage 5-3 core modules without ROS: glim_runner (runtime config, stop/dump inspection with a fake
process), map_database (register source, publish/abort conversion, hashes, index) and map_convert (synthetic GLIM-like
dump -> occupancy grid, settings required, refusal without submaps). Design tests: TS-11 (core part), TS-27.
"""
import json
import math
import struct
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import glim_runner as gr  # noqa: E402
from gouda_core import map_database as mdb  # noqa: E402
from gouda_core import map_convert as mc  # noqa: E402

TEMPLATE_CONFIG = '{\n  /*** Global ***/\n  "global": {"config_path": "", "config_ros": "config_ros.json", "config_odometry": "config_odometry_gpu.json", "config_sub_mapping": "config_sub_mapping_gpu.json", "config_global_mapping": "config_global_mapping_gpu.json"}\n}\n'
TEMPLATE_ROS = '{\n  // comment\n  "glim_ros": {\n    "enable_local_mapping": true, // trailing\n    "imu_frame_id": "", "lidar_frame_id": "", "base_frame_id": "", "odom_frame_id": "odom", "map_frame_id": "map",\n    "extension_modules": ["libstandard_viewer.so"],\n    "imu_topic": "/os_cloud_node/imu", "points_topic": "/os_cloud_node/points"\n  }\n}\n'


def make_template(d: Path):
    d.mkdir(parents=True); (d / 'config.json').write_text(TEMPLATE_CONFIG); (d / 'config_ros.json').write_text(TEMPLATE_ROS)
    for n in ('config_odometry_cpu.json', 'config_sub_mapping_cpu.json', 'config_global_mapping_cpu.json'): (d / n).write_text('{}')


def settings(tpl):
    return gr.GlimSettings(points_topic='sensors/xt32/points', imu_topic='sensors/imu/data', lidar_frame_id='xt32_link', imu_frame_id='imu_link', base_frame_id='base_link', template_dir=tpl, executable='/bin/true')


class FakeProc:
    def __init__(self, cmd, stdout=None, stderr=None, start_new_session=False):
        self.cmd = cmd; self.pid = 4242; self._alive = True; FakeProc.last = self
    def poll(self): return None if self._alive else 0


class GlimRunnerTests(unittest.TestCase):
    def test_runtime_config_selects_cpu_modules_topics_frames_and_no_viewer(self):
        with tempfile.TemporaryDirectory() as d:
            tpl = Path(d) / 'tpl'; make_template(tpl)
            r = gr.build_runtime_config(settings(tpl), Path(d) / 'cfg')
            top = json.loads((Path(d) / 'cfg' / 'config.json').read_text())
            self.assertEqual(top['global']['config_odometry'], 'config_odometry_cpu.json')
            self.assertEqual(r['points_topic'], 'sensors/xt32/points'); self.assertEqual(r['base_frame_id'], 'base_link'); self.assertEqual(r['extension_modules'], [])

    def test_missing_template_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError): gr.build_runtime_config(settings(Path(d) / 'none'), Path(d) / 'cfg')

    def test_inspect_dump(self):
        with tempfile.TemporaryDirectory() as d:
            ok, n, msg = gr.inspect_dump(Path(d) / 'missing'); self.assertFalse(ok); self.assertIn('does not exist', msg)
            dd = Path(d) / 'dump'; dd.mkdir(); (dd / 'graph.txt').write_text('g')
            ok, n, msg = gr.inspect_dump(dd); self.assertFalse(ok); self.assertIn('values.bin', msg)
            (dd / 'values.bin').write_bytes(b'v'); (dd / '000000').mkdir()
            ok, n, msg = gr.inspect_dump(dd); self.assertTrue(ok); self.assertEqual(n, 1)

    def test_start_builds_command_and_stop_inspects_dump(self):
        with tempfile.TemporaryDirectory() as d:
            tpl = Path(d) / 'tpl'; make_template(tpl)
            t = [100.0]
            runner = gr.GlimRunner(settings(tpl), clock=lambda: t[0], popen=FakeProc)
            run = runner.start(Path(d) / 'work', Path(d) / 'dump', Path(d) / 'glim.log')
            self.assertIn('config_path:=' + str(Path(d) / 'work' / 'glim_config'), FakeProc.last.cmd); self.assertIn('dump_path:=' + str(Path(d) / 'dump'), FakeProc.last.cmd)
            self.assertTrue(runner.running)
            FakeProc.last._alive = False   # process exits on SIGINT (killpg is not reachable for a fake pid; stop handles the ended process)
            (Path(d) / 'dump').mkdir(); (Path(d) / 'dump' / 'graph.txt').write_text('g'); (Path(d) / 'dump' / 'values.bin').write_bytes(b'v')
            run = runner.stop(wait_s=5)
            self.assertTrue(run.dump_ok); self.assertEqual(run.submaps, 0); self.assertIn('no sensor data', run.note)
            self.assertIsNone(gr.unexpected_exit_report(run, 0, 130.0))   # ended by the stop request: not reported
            self.assertIsNone(run.exited_unexpectedly_at)

    def test_unexpected_exit_is_reported_with_exit_code_and_log_tail(self):
        # G-GLIM-EXIT: on 2026-10-14 (origin 175310) GLIM died and the mapping went on for 2 minutes unnoticed.
        with tempfile.TemporaryDirectory() as d:
            tpl = Path(d) / 'tpl'; make_template(tpl)
            runner = gr.GlimRunner(settings(tpl), clock=lambda: 100.0, popen=FakeProc)
            log = Path(d) / 'glim.log'
            run = runner.start(Path(d) / 'work', Path(d) / 'dump', log)
            self.assertEqual(run.log_file, log)
            log.write_text("info\nterminate called after throwing an instance of 'gtsam::IndeterminantLinearSystemException'\n  what():\n\n")
            reason, details = gr.unexpected_exit_report(run, -6, 250.0)
            self.assertIn('exit code -6', reason); self.assertIn('150 s', reason); self.assertIn('地図作成終了', reason)
            self.assertEqual(details['exit_code'], -6); self.assertEqual(details['exited_at'], 250.0); self.assertEqual(details['glim_log'], str(log))
            self.assertIn('IndeterminantLinearSystemException', ' '.join(details['log_tail']))
            self.assertEqual(run.exited_unexpectedly_at, 250.0)


def make_dump(root: Path, submaps):
    root.mkdir(parents=True)
    (root / 'graph.txt').write_text('g'); (root / 'values.bin').write_bytes(b'v')
    for i, (T, pts) in enumerate(submaps):
        d = root / f'{i:06d}'; d.mkdir()
        rows = '\n'.join(' '.join(str(v) for v in row) for row in T)
        (d / 'data.txt').write_text(f'id: {i}\nT_world_origin:\n{rows}\nframe_id: LIDAR\n')
        (d / 'points_compact.bin').write_bytes(np.asarray(pts, dtype=np.float32).tobytes())


def grid_settings():
    return {'map_resolution_m': 0.5, 'ground_band_max_m': 0.1, 'obstacle_band_min_m': 0.3, 'obstacle_band_max_m': 1.5, 'occupied_min_points': 2,
            'ground_cell_m': 0.5, 'ground_max_slope_deg': 10.0, 'ground_fill_radius_m': 1.0}


def read_pcd(path):
    raw = Path(path).read_bytes(); head, _, body = raw.partition(b'DATA binary\n')
    fields = dict(line.split(' ', 1) for line in head.decode('ascii').splitlines() if line and not line.startswith('#'))
    return fields, np.frombuffer(body, dtype='<f4').reshape(-1, 3)


def png_size(path):
    b = Path(path).read_bytes(); assert b.startswith(b'\x89PNG'); return struct.unpack('>II', b[16:24])


class MapConvertTests(unittest.TestCase):
    def test_grid_from_synthetic_submaps(self):
        with tempfile.TemporaryDirectory() as d:
            I = np.eye(4); T2 = np.eye(4); T2[0, 3] = 2.0   # second submap shifted 2 m in x
            ground = [[x * 0.5, y * 0.5, 0.0] for x in range(4) for y in range(4)]
            wall = [[1.0, 1.0, 0.5], [1.0, 1.0, 0.8], [1.0, 1.0, 1.2]]
            make_dump(Path(d) / 'dump', [(I, ground + wall), (T2, ground)])
            stats = mc.convert(Path(d) / 'dump', Path(d) / 'out', grid_settings())
            self.assertEqual(stats['submaps'], 2); self.assertGreaterEqual(stats['occupied'], 1); self.assertGreater(stats['free'], 10)
            self.assertEqual(stats['points_obstacle'], 3)
            yaml = (Path(d) / 'out' / 'map.yaml').read_text(); self.assertIn('resolution: 0.5', yaml); self.assertIn('image: map.pgm', yaml)
            pgm = (Path(d) / 'out' / 'map.pgm').read_bytes(); self.assertTrue(pgm.startswith(b'P5\n'))
            w, h = [int(x) for x in pgm.split(b'\n')[1].split()]; self.assertEqual(len(pgm.split(b'\n', 3)[3]), w * h)
            # every product is written; the 3D point map holds all points in the map frame
            self.assertEqual(stats['files'], mc.PRODUCT_FILES)
            for f in mc.PRODUCT_FILES: self.assertGreater((Path(d) / 'out' / f).stat().st_size, 0, f)
            fields, pcd = read_pcd(Path(d) / 'out' / 'pointmap.pcd')
            self.assertEqual(fields['FIELDS'], 'x y z'); self.assertEqual(int(fields['POINTS']), len(ground) * 2 + len(wall)); self.assertEqual(pcd.shape[0], int(fields['POINTS']))
            self.assertAlmostEqual(float(pcd[:, 0].max()), 3.5, places=5)   # the second submap's points are moved by its pose
            self.assertEqual(png_size(Path(d) / 'out' / 'height.png'), (w, h))
            terrain = json.loads((Path(d) / 'out' / 'terrain.json').read_text()); self.assertIn('display only', terrain['use'])
            self.assertEqual(png_size(Path(d) / 'out' / 'slope.png'), (terrain['ground_grid']['width'], terrain['ground_grid']['height']))

    def test_heights_are_measured_from_the_ground(self):
        """DEC-093: the ground is not at z=0 in GLIM's frame and may slope; the bands are heights above the estimated ground."""
        rng = np.random.default_rng(7); s = dict(grid_settings(), map_resolution_m=0.25, occupied_min_points=1)
        x = rng.uniform(0, 20, 8000); y = rng.uniform(0, 6, 8000); slope = np.tan(np.radians(5)); offset = -1.2
        ground = np.c_[x, y, offset + slope * x]
        box = np.c_[rng.uniform(12, 13, 300), rng.uniform(2, 3, 300), np.zeros(300)]; box[:, 2] = offset + slope * box[:, 0] + rng.uniform(0.4, 0.9, 300)
        canopy = np.c_[rng.uniform(4, 6, 200), rng.uniform(1, 3, 200), np.zeros(200)]; canopy[:, 2] = offset + slope * canopy[:, 0] + 3.0
        pts = np.concatenate([ground, box, canopy])
        g = mc.estimate_ground(pts, s['ground_cell_m'], s['ground_max_slope_deg'], s['ground_fill_radius_m'])
        hag, gnd, obst = mc.classify(pts, g, s)
        self.assertGreater(gnd[:8000].mean(), 0.95); self.assertEqual(int(obst[:8000].sum()), 0)    # the sloped, offset ground is ground
        self.assertTrue(obst[8000:8300].all())                                                     # the box (0.4..0.9 m above) is an obstacle
        self.assertFalse(obst[8300:].any())                                                        # the canopy (3 m above) is not
        # the same scene with absolute z (the old rule) would call the whole far half of the slope an obstacle
        self.assertGreater(((ground[:, 2] >= s['obstacle_band_min_m']) & (ground[:, 2] <= s['obstacle_band_max_m'])).mean(), 0.1)
        ter = mc.terrain(g, s); self.assertAlmostEqual(float(np.nanmedian(ter['slope_deg'])), 5.0, delta=0.5)

    def test_an_obstacle_seen_without_ground_below_does_not_lift_the_ground(self):
        """A cell that only sees a car body or a wall: the slope limit keeps its ground near the neighbours' ground."""
        s = grid_settings()
        floor = [[x * 0.25, y * 0.25, 0.0] for x in range(40) for y in range(40) if not (4 <= x * 0.25 < 6 and 4 <= y * 0.25 < 6)]
        body = [[4 + i * 0.1, 4 + j * 0.1, 0.5 + k * 0.1] for i in range(20) for j in range(20) for k in range(3)]   # no ground under it
        pts = np.array(floor + body, dtype=np.float64)
        g = mc.estimate_ground(pts, s['ground_cell_m'], s['ground_max_slope_deg'], s['ground_fill_radius_m'])
        hag, gnd, obst = mc.classify(pts, g, s)
        self.assertTrue(obst[len(floor):].all(), 'the body must stay an obstacle')
        self.assertLessEqual(float(np.nanmax(g.height)), np.tan(np.radians(s['ground_max_slope_deg'])) * s['ground_cell_m'] * 3)

    def test_ground_is_not_invented_far_from_points(self):
        s = grid_settings()
        near = [[x * 0.5, 0.0, 0.0] for x in range(10)]; far = [[x * 0.5, 20.0, 0.0] for x in range(10)]
        g = mc.estimate_ground(np.array(near + far, dtype=np.float64), s['ground_cell_m'], s['ground_max_slope_deg'], s['ground_fill_radius_m'])
        mid = g.height[int(10 / s['ground_cell_m']), :]
        self.assertTrue(np.isnan(mid).all(), 'no ground 10 m from any point (fill radius 1 m)')
        self.assertGreater(g.filled_cells, 0)
        g0 = mc.estimate_ground(np.array(near + far, dtype=np.float64), s['ground_cell_m'], s['ground_max_slope_deg'], 0.0)
        self.assertEqual(g0.filled_cells, 0)

    def test_step_view_shows_a_curb(self):
        s = grid_settings()
        pts = np.array([[x * 0.1, y * 0.1, 0.15 if y * 0.1 >= 2.0 else 0.0] for x in range(40) for y in range(40)], dtype=np.float64)
        g = mc.estimate_ground(pts, s['ground_cell_m'], s['ground_max_slope_deg'], s['ground_fill_radius_m'])
        ter = mc.terrain(g, s)
        self.assertAlmostEqual(float(np.nanmax(ter['step_m'])), 0.15, places=6)
        self.assertAlmostEqual(float(np.nanmin(ter['step_m'])), 0.0, places=6)

    def test_point_map_tiles_for_a3(self):
        """TS-43 (REV-128): the thinned points in square tiles with the autoware_pointcloud_map_loader metadata, and the
        trajectory copy. Every kept point is in exactly one tile; the metadata gives each tile's lower-left corner."""
        with tempfile.TemporaryDirectory() as d:
            ground = [[x * 0.5, y * 0.5, 0.0] for x in range(-20, 60) for y in range(-10, 10)]
            dup = [[0.01, 0.01, 0.0], [0.02, 0.02, 0.01]]                       # in the voxel of (0, 0, 0): thinned away
            make_dump(Path(d) / 'dump', [(np.eye(4), ground + dup)])
            (Path(d) / 'dump' / 'traj_imu.txt').write_text('1.0 0 0 1.2 0 0 0 1\n')
            s = dict(grid_settings(), pointmap_voxel_m=0.2, pointmap_tile_m=20.0)
            stats = mc.convert(Path(d) / 'dump', Path(d) / 'out', s)
            pm = stats['pointcloud_map']; self.assertTrue(pm['made']); self.assertEqual(pm['points'], len(ground))
            out = Path(d) / 'out' / mc.POINTCLOUD_MAP_DIR
            meta = (out / 'metadata.yaml').read_text().splitlines()
            self.assertEqual(meta[:2], ['x_resolution: 20.0', 'y_resolution: 20.0'])
            corners = dict(line.split(': ', 1) for line in meta[2:])
            self.assertEqual(sorted(corners), sorted(f'tile_{i}_{j}.pcd' for i in (-1, 0, 1) for j in (-1, 0)))
            self.assertEqual(corners['tile_-1_-1.pcd'], '[-20, -20]')   # integers: the loader rejects '[-20.0, -20.0]' (VM, 2026-10-21)
            total = 0
            for name, corner in corners.items():
                x0, y0 = [float(v) for v in corner.strip('[]').split(', ')]
                _, p = read_pcd(out / name); total += p.shape[0]
                self.assertTrue(((p[:, 0] >= x0) & (p[:, 0] < x0 + 20) & (p[:, 1] >= y0) & (p[:, 1] < y0 + 20)).all(), name)
            self.assertEqual(total, len(ground))
            self.assertIn(mc.POINTCLOUD_MAP_METADATA, stats['files']); self.assertIn(mc.TRAJECTORY_FILE, stats['files'])
            self.assertEqual((Path(d) / 'out' / mc.TRAJECTORY_FILE).read_text(), '1.0 0 0 1.2 0 0 0 1\n')

    def test_tile_size_must_be_whole_metres(self):
        with self.assertRaises(ValueError) as cm: mc.write_tiles(np.zeros((1, 3)), Path(tempfile.mkdtemp()) / 'pm', 12.5)
        self.assertIn('whole number', str(cm.exception))

    def test_no_tiles_without_their_settings(self):
        with tempfile.TemporaryDirectory() as d:
            make_dump(Path(d) / 'dump', [(np.eye(4), [[x * 0.5, y * 0.5, 0.0] for x in range(4) for y in range(4)])])
            stats = mc.convert(Path(d) / 'dump', Path(d) / 'out', dict(grid_settings(), pointmap_voxel_m=0.2))   # tile size unresolved
            self.assertFalse(stats['pointcloud_map']['made']); self.assertIn('PRM-95', stats['pointcloud_map']['reason'])
            self.assertFalse((Path(d) / 'out' / mc.POINTCLOUD_MAP_DIR).exists()); self.assertTrue((Path(d) / 'out' / 'map.yaml').is_file())

    # ---- plan C: the swept corridor (TS-44, REV-131) ----
    @staticmethod
    def _traj(points, yaw=0.0):
        q = (0.0, 0.0, math.sin(yaw / 2), math.cos(yaw / 2))
        return ''.join(f'{i * 0.1:.1f} {x} {y} 0.3 {q[0]} {q[1]} {q[2]} {q[3]}\n' for i, (x, y) in enumerate(points))

    def _corridor(self, d, traj_text, mount_values, half=0.5, gap=1.0):
        make_dump(Path(d) / 'dump', [(np.eye(4), [[x * 0.5, y * 0.5, 0.0] for x in range(4) for y in range(4)])])
        (Path(d) / 'dump' / 'traj_imu.txt').write_text(traj_text)
        s = dict(grid_settings(), map_resolution_m=0.1, corridor_half_width_m=half, corridor_gap_m=gap)
        stats = mc.convert(Path(d) / 'dump', Path(d) / 'out', s, {'values': mount_values, 'source': 'test'} if mount_values is not None else None)
        return stats

    def _free_centres(self, d):
        out = Path(d) / 'out'; meta = (out / 'map_swept_corridor.yaml').read_text()
        res = float(meta.split('resolution: ')[1].split()[0]); ox, oy = [float(v) for v in meta.split('origin: [')[1].split(',')[:2]]
        pgm = (out / 'map_swept_corridor.pgm').read_bytes(); w, h = [int(v) for v in pgm.split(b'\n')[1].split()]
        img = np.frombuffer(pgm.split(b'\n', 3)[3], dtype=np.uint8).reshape(h, w)[::-1, :]   # row 0 = lowest y
        self.assertTrue(set(np.unique(img)) <= {254, 205}, 'only free and unknown, no occupied cell')
        j, i = np.nonzero(img == 254)
        return np.c_[ox + (i + 0.5) * res, oy + (j + 0.5) * res]

    def test_corridor_is_free_only_near_the_path(self):
        with tempfile.TemporaryDirectory() as d:
            path = [(x * 0.1, 0.0) for x in range(51)] + [(5.0, y * 0.1) for y in range(1, 31)]   # straight, then a corner
            stats = self._corridor(d, self._traj(path), {})
            self.assertTrue(stats['swept_corridor']['made']); self.assertIn('map_swept_corridor.yaml', stats['files'])
            c = self._free_centres(d)
            def dist(p):   # distance to the polyline (two segments)
                a = np.clip(p[:, 0], 0, 5); d1 = np.hypot(p[:, 0] - a, p[:, 1])
                b = np.clip(p[:, 1], 0, 3); d2 = np.hypot(p[:, 0] - 5, p[:, 1] - b)
                return np.minimum(d1, d2)
            self.assertLessEqual(float(dist(c).max()), 0.5 + 1e-9)
            self.assertGreater(len(c), 0.8 * (5 + 3) * 1.0 / 0.01)    # most of the 1 m wide band is free
            rec = json.loads((Path(d) / 'out' / 'swept_corridor.json').read_text())
            self.assertEqual(rec['trajectory']['pieces'], 1); self.assertEqual(rec['trajectory']['not_joined'], [])
            self.assertIn('imu_mount_x_m', rec['mounting']['defaulted_fields'])   # UNKNOWN mounting -> neutral, recorded

    def test_a_jump_is_not_joined(self):
        with tempfile.TemporaryDirectory() as d:
            path = [(x * 0.1, 0.0) for x in range(21)] + [(x * 0.1, 0.0) for x in range(80, 101)]   # 2 m -> 8 m jump of 6 m
            self._corridor(d, self._traj(path), {})
            c = self._free_centres(d)
            self.assertFalse(((c[:, 0] > 2.6) & (c[:, 0] < 7.4)).any(), 'the jump is not free')
            rec = json.loads((Path(d) / 'out' / 'swept_corridor.json').read_text())
            self.assertEqual(rec['trajectory']['pieces'], 2); self.assertAlmostEqual(rec['trajectory']['not_joined'][0]['distance_m'], 6.0)

    def test_imu_mounting_moves_the_corridor(self):
        """base_link = IMU pose * inv(T_base_imu): an IMU 0.3 m ahead of base_link puts base_link 0.3 m behind the IMU path."""
        with tempfile.TemporaryDirectory() as d:
            path = [(x * 0.1, 0.0) for x in range(31)]
            self._corridor(d, self._traj(path), {'imu_mount_x_m': 0.3, 'imu_axis_mapping': '+x forward, +y left, +z up'}, half=0.2)
            c = self._free_centres(d)
            self.assertAlmostEqual(float(c[:, 0].min()), -0.3 - 0.2, delta=0.1); self.assertAlmostEqual(float(c[:, 0].max()), 3.0 - 0.3 + 0.2, delta=0.1)

    def test_corridor_needs_trajectory_mounting_and_settings(self):
        with tempfile.TemporaryDirectory() as d:
            st = self._corridor(d, '', {})
            self.assertFalse(st['swept_corridor']['made']); self.assertIn('traj_imu.txt', st['swept_corridor']['reason'])
        with tempfile.TemporaryDirectory() as d:
            st = self._corridor(d, self._traj([(0, 0), (1, 0)]), None)
            self.assertFalse(st['swept_corridor']['made']); self.assertIn('DEC-212', st['swept_corridor']['reason'])
            self.assertTrue((Path(d) / 'out' / 'map.yaml').is_file(), 'the 2D map used for driving is still made (DEC-211)')
        with tempfile.TemporaryDirectory() as d:
            make_dump(Path(d) / 'dump', [(np.eye(4), [[0, 0, 0], [1, 1, 0]])])
            st = mc.convert(Path(d) / 'dump', Path(d) / 'out', grid_settings(), {'values': {}, 'source': 'test'})
            self.assertFalse(st['swept_corridor']['made']); self.assertIn('PRM-96', st['swept_corridor']['reason'])

    def test_refuses_without_submaps_or_settings(self):
        with tempfile.TemporaryDirectory() as d:
            make_dump(Path(d) / 'dump', [])
            with self.assertRaises(ValueError) as cm: mc.convert(Path(d) / 'dump', Path(d) / 'out', grid_settings())
            self.assertIn('no submap', str(cm.exception))
            make_dump(Path(d) / 'dump2', [(np.eye(4), [[0, 0, 0]])])
            with self.assertRaises(ValueError) as cm: mc.convert(Path(d) / 'dump2', Path(d) / 'out2', {'map_resolution_m': 0.5})
            self.assertIn('settings missing', str(cm.exception))

    def test_refuses_unverified_point_layout(self):
        with tempfile.TemporaryDirectory() as d:
            make_dump(Path(d) / 'dump', [(np.eye(4), [[0, 0, 0]])])
            (Path(d) / 'dump' / '000000' / 'points_compact.bin').write_bytes(b'\x00' * 10)   # not a multiple of 12
            with self.assertRaises(ValueError) as cm: mc.convert(Path(d) / 'dump', Path(d) / 'out', grid_settings())
            self.assertIn('multiple of 12', str(cm.exception))



class MapInspectTests(unittest.TestCase):
    """TS-34 analysis (DEC-099, DEC-100): GLIM frame rate, path, density and ground visibility near the path."""
    def test_report(self):
        from gouda_core import map_inspect as mi
        with tempfile.TemporaryDirectory() as d:
            # ground seen only from 2 m away from the path (a blind ring around the sensor), a wall at y = 4
            ground = [[x * 0.25, y * 0.25, 0.0] for x in range(41) for y in range(-16, 17) if abs(y * 0.25) >= 2.0]
            wall = [[x * 0.25, 4.0, z * 0.25] for x in range(41) for z in range(1, 8)]
            make_dump(Path(d) / 'src', [(np.eye(4), ground + wall)])
            stamps = 1000 + np.arange(0, 101) * 0.125     # 8 Hz for 12.5 s
            (Path(d) / 'src' / 'traj_lidar.txt').write_text('\n'.join(f'{t:.6f} {i * 0.1:.3f} 0 0 0 0 0 1' for i, t in enumerate(stamps)) + '\n')
            r = mi.inspect(Path(d) / 'src', 0.5, [1.0, 3.0], 0.1)
            self.assertAlmostEqual(r['glim_frames']['rate_hz'], 8.0, places=6); self.assertEqual(r['glim_frames']['frames'], 101)
            self.assertAlmostEqual(r['path']['length_m'], 10.0, places=6); self.assertAlmostEqual(r['path']['max_distance_from_start_m'], 10.0, places=6)
            near, far = r['near_path']
            self.assertEqual(near['radius_m'], 1.0); self.assertLess(near['share_with_points'], 0.2)    # blind close to the path
            self.assertGreater(far['share_with_points'], 0.4); self.assertGreater(far['points_per_m2'], 0)
            with self.assertRaises(ValueError): mi.inspect(Path(d) / 'src', 0, [1.0], 0.1)


class MapDatabaseTests(unittest.TestCase):
    def test_register_source_requires_complete_dump_and_publishes_atomically(self):
        with tempfile.TemporaryDirectory() as d:
            db = mdb.MapDatabase(Path(d) / 'maps')
            inc = Path(d) / 'inc'; inc.mkdir(); (inc / 'graph.txt').write_text('g')
            ok, msg, _ = db.register_source(inc, 'o1', {'software': 'glim_ros'}, {}); self.assertFalse(ok); self.assertIn('incomplete', msg); self.assertTrue(inc.exists())
            make_dump(Path(d) / 'dump', [(np.eye(4), [[0, 0, 0]])])
            ok, msg, man = db.register_source(Path(d) / 'dump', 'o1', {'software': 'glim_ros', 'version': '1.2.2'}, {'run': 'x'})
            self.assertTrue(ok, msg); self.assertEqual(man['submaps'], 1); self.assertEqual(len(man['content_hash']), 64)
            self.assertFalse((Path(d) / 'dump').exists()); self.assertTrue(db.source_dir('o1').is_dir())
            self.assertEqual(db.index()['origins'][0]['origin_id'], 'o1')
            ok, msg, _ = db.register_source(Path(d) / 'dump', 'o1', {}, {}); self.assertFalse(ok)

    def test_conversion_publish_and_abort(self):
        with tempfile.TemporaryDirectory() as d:
            db = mdb.MapDatabase(Path(d) / 'maps')
            make_dump(Path(d) / 'dump', [(np.eye(4), [[x * 0.5, y * 0.5, 0.0] for x in range(3) for y in range(3)] + [[0.5, 0.5, 0.6], [0.5, 0.5, 0.7]])])
            db.register_source(Path(d) / 'dump', 'o1', {}, {})
            tmp = db.begin_conversion('o1')
            ok, msg, _ = db.finish_conversion('o1', tmp, {'version': 'v'}, {}, {}); self.assertFalse(ok); self.assertIn('discarded', msg); self.assertFalse(tmp.exists())
            tmp = db.begin_conversion('o1')
            stats = mc.convert(db.source_dir('o1'), tmp, grid_settings())
            ok, msg, man = db.finish_conversion('o1', tmp, {'version': mc.CONVERTER_VERSION}, grid_settings(), stats)
            self.assertTrue(ok, msg); self.assertEqual(man['revision'], 1); self.assertEqual(man['source_content_hash'], db.source_manifest('o1')['content_hash'])
            self.assertTrue((db.root / 'o1' / 'converted' / '001' / 'map.yaml').is_file())
            tmp2 = db.begin_conversion('o1'); self.assertIn('aborted', db.abort_conversion(tmp2, 'test')); self.assertFalse(tmp2.exists())
            self.assertEqual(db.index()['origins'][0]['converted'][0]['revision'], 1)
            with self.assertRaises(FileNotFoundError): db.begin_conversion('none')

    def test_content_hash_is_name_independent_but_content_dependent(self):
        with tempfile.TemporaryDirectory() as d:
            a = Path(d) / 'a'; a.mkdir(); (a / 'x.bin').write_bytes(b'1'); b = Path(d) / 'b'; b.mkdir(); (b / 'x.bin').write_bytes(b'1')
            self.assertEqual(mdb.content_hash(a), mdb.content_hash(b))
            (b / 'x.bin').write_bytes(b'2'); self.assertNotEqual(mdb.content_hash(a), mdb.content_hash(b))


if __name__ == '__main__': unittest.main()
