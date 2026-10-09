"""Unit tests of the stage 5-3 core modules without ROS: glim_runner (runtime config, stop/dump inspection with a fake
process), map_database (register source, publish/abort conversion, hashes, index) and map_convert (synthetic GLIM-like
dump -> occupancy grid, settings required, refusal without submaps). Design tests: TS-11 (core part), TS-27.
"""
import json
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


def make_dump(root: Path, submaps):
    root.mkdir(parents=True)
    (root / 'graph.txt').write_text('g'); (root / 'values.bin').write_bytes(b'v')
    for i, (T, pts) in enumerate(submaps):
        d = root / f'{i:06d}'; d.mkdir()
        rows = '\n'.join(' '.join(str(v) for v in row) for row in T)
        (d / 'data.txt').write_text(f'id: {i}\nT_world_origin:\n{rows}\nframe_id: LIDAR\n')
        (d / 'points_compact.bin').write_bytes(np.asarray(pts, dtype=np.float32).tobytes())


def grid_settings():
    return {'map_resolution_m': 0.5, 'ground_band_max_m': 0.1, 'obstacle_band_min_m': 0.3, 'obstacle_band_max_m': 1.5, 'occupied_min_points': 2}


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
