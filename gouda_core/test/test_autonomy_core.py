"""Unit tests of autonomy_core and the stage 5-6 parts of mode_core without ROS (REV-061; TR-05 / 06 / 07 / 08 / 10 / 11,
TS-01 / 02 / 05 / 15 / 21 decision parts).

Checked: a start request is accepted only when the waypoint set, its mask and the converted map exist and every hash matches
(RQ-I078); the initial pose must be in the map frame; goal poses and the section index from the feedback; the
speed_limit_application_state (DEC-047) and that only 'applied' could release the hold (DEC-056); the human pause flag and the
automatic pauses (TR-07 / TR-08)."""
import json
import math
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import autonomy_core as ac  # noqa: E402
from gouda_core import keepout_mask as km  # noqa: E402
from gouda_core import mode_core as mc  # noqa: E402
from gouda_core import speed_mask as sm  # noqa: E402
from gouda_core import waypoints as wp  # noqa: E402

MAP_HASH = 'm' * 64


def make_data(root: Path, keepout: bool = True):
    """A converted map (manifest + map.yaml) and one waypoint set with its mask, as stages 5-3 / 5-4 store them."""
    mdir = root / 'maps' / 'origin1' / 'converted' / '001'; mdir.mkdir(parents=True)
    (mdir / 'manifest.json').write_text(json.dumps({'revision': 1, 'content_hash': MAP_HASH, 'created_at': time.time()}))
    (mdir / 'map.yaml').write_text('image: map.pgm\nresolution: 0.5\norigin: [-5.0, -5.0, 0.0]\n')
    db = wp.RouteDatabase(root / 'routes')
    ws = wp.WaypointSet('origin1', 1, MAP_HASH, [wp.Waypoint(-4, 0), wp.Waypoint(0, 0, math.pi / 2), wp.Waypoint(4, 0)], [1.0, 0.5])
    sid, rev, tmp = db.begin(None)
    g = sm.MapGeometry(resolution=0.5, origin_x=-5.0, origin_y=-5.0, width=40, height=40)
    res = sm.generate([(w.x, w.y) for w in ws.waypoints], ws.section_limits_mps, g, 0.6, 0.02)
    files = sm.write_mask(res, g, tmp, 'speed_filter_mask', 'costmap_filter_info')
    if keepout:   # REV-137: a waypoint set carries the KeepoutFilter mask of its drawn areas (none here)
        kfiles, krec = km.write(km.rasterize([], g), g, tmp, '/keepout_filter_mask', '/keepout_costmap_filter_info'); files.update(kfiles)
    ok, _, man = db.publish(sid, rev, tmp, ws, files, [], {'keepout': krec} if keepout else {})
    assert ok
    return {'waypoint_set_id': sid, 'waypoint_set_revision': str(rev), 'waypoint_set_hash': man['content_hash'],
            'map_id': 'origin1', 'map_revision': '1', 'map_hash': MAP_HASH}


class MissionTests(unittest.TestCase):
    def test_resolved_when_everything_matches(self):
        with tempfile.TemporaryDirectory() as d:
            req = make_data(Path(d))
            m, why = ac.resolve_mission(Path(d), req)
            self.assertIsNotNone(m, why)
            self.assertEqual(len(m.waypoints), 3); self.assertTrue(m.map_yaml.endswith('converted/001/map.yaml'))
            self.assertEqual(m.filter_base, 0.0); self.assertAlmostEqual(m.filter_multiplier, 0.02)
            self.assertTrue(m.map_directory.endswith('converted/001'))
            self.assertTrue(m.keepout_yaml.endswith('keepout_mask.yaml')); self.assertEqual(len(m.keepout_sha256), 64); self.assertEqual(m.keepout_size, (40, 40))

    def test_a_set_without_keepout_mask_is_refused(self):
        """REV-137 (DEC-221, TR-05): a waypoint set saved before the drawn areas has no keepout mask: save it again."""
        with tempfile.TemporaryDirectory() as d:
            m, why = ac.resolve_mission(Path(d), make_data(Path(d), keepout=False))
            self.assertIsNone(m); self.assertIn('keepout', why)

    def test_localization_map_needs_tiles_and_trajectory(self):
        """REV-128 (TS-41): ND-07 (A3) starts only on a map converted with the point-map tiles and the mapping trajectory."""
        from gouda_core import map_convert
        with tempfile.TemporaryDirectory() as d:
            m, _ = ac.resolve_mission(Path(d), make_data(Path(d)))
            self.assertIn(map_convert.POINTCLOUD_MAP_METADATA, ac.check_localization_map(m.map_directory))
            (Path(m.map_directory) / map_convert.POINTCLOUD_MAP_DIR).mkdir(); (Path(m.map_directory) / map_convert.POINTCLOUD_MAP_METADATA).write_text('x_resolution: 20.0\n')
            self.assertIn(map_convert.TRAJECTORY_FILE, ac.check_localization_map(m.map_directory))
            (Path(m.map_directory) / map_convert.TRAJECTORY_FILE).write_text('1 0 0 0 0 0 0 1\n')
            self.assertIsNone(ac.check_localization_map(m.map_directory))

    def test_refused_on_any_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            req = make_data(Path(d))
            for key, bad in (('waypoint_set_hash', 'x'), ('map_hash', 'x'), ('map_revision', '2'), ('waypoint_set_revision', '9'), ('waypoint_set_id', '')):
                m, why = ac.resolve_mission(Path(d), dict(req, **{key: bad}))
                self.assertIsNone(m, key); self.assertTrue(why)
            (Path(d) / 'maps' / 'origin1' / 'converted' / '001' / 'map.yaml').unlink()
            self.assertIsNone(ac.resolve_mission(Path(d), req)[0])

    def test_initial_pose(self):
        self.assertIsNone(ac.check_initial_pose('map', 1.0, 2.0, 0.0, 1.0))
        self.assertIn('not map', ac.check_initial_pose('', 0.0, 0.0, 0.0, 1.0))
        self.assertIsNotNone(ac.check_initial_pose('map', float('nan'), 0.0, 0.0, 1.0))
        self.assertIsNotNone(ac.check_initial_pose('map', 0.0, 0.0, 0.0, 0.0))


class GoalAndSectionTests(unittest.TestCase):
    def test_goal_poses(self):
        p = ac.goal_poses([(-4, 0, 0.0), (0, 0, math.pi / 2), (4, 0, 0.0)], 1)
        self.assertEqual(len(p), 2); self.assertAlmostEqual(p[0][2], math.sin(math.pi / 4)); self.assertAlmostEqual(p[0][3], math.cos(math.pi / 4))

    def test_section_from_feedback(self):
        self.assertEqual(ac.section_from_feedback(0, 3, 3), 0)    # heading to W0: section 0 for the record
        self.assertEqual(ac.section_from_feedback(0, 3, 2), 0)    # heading to W1: section 0
        self.assertEqual(ac.section_from_feedback(0, 3, 1), 1)
        self.assertEqual(ac.section_from_feedback(0, 5, 2), 2)    # two removed at once (TS-02): position decides, the jump is recorded by the node
        self.assertEqual(ac.remaining_offset(0, 5, 2), 3)
        self.assertEqual(ac.section_from_feedback(2, 3, 3), 1)    # resumed at W2: section 1


class SpeedStateTests(unittest.TestCase):
    def mask(self):
        data = [0] * 100; data[5 * 10 + 5] = 25   # one band cell at (5, 5)
        return ac.MaskGrid(0.0, 0.0, 1.0, 10, 10, data)

    def test_states(self):
        m = self.mask()
        self.assertEqual(ac.speed_limit_state(None, False, (5.5, 5.5), 0.5), ac.SL_NOT_LOADED)
        self.assertEqual(ac.speed_limit_state(m, False, (5.5, 5.5), 0.5), ac.SL_NOT_LOADED)
        self.assertEqual(ac.speed_limit_state(m, True, None, 0.5), ac.SL_UNKNOWN)
        self.assertEqual(ac.speed_limit_state(m, True, (20.0, 5.0), 0.5), ac.SL_OUTSIDE_MASK)
        self.assertEqual(ac.speed_limit_state(m, True, (1.5, 1.5), None), ac.SL_OUTSIDE_BAND)
        self.assertEqual(ac.speed_limit_state(m, True, (5.5, 5.5), None), ac.SL_UNKNOWN, 'no speed_limit yet: the hold stays (DEC-056)')
        self.assertEqual(ac.speed_limit_state(m, True, (5.5, 5.5), 0.0), ac.SL_UNKNOWN, '0 is unlimited, not applied')
        self.assertEqual(ac.speed_limit_state(m, True, (5.5, 5.5), 0.5), ac.SL_APPLIED)


class ModeCoreAutonomyTests(unittest.TestCase):
    IMPL = frozenset({'TR-05', 'TR-06', 'TR-10', 'TR-11', 'TR-12'})

    def test_start_pause_resume_end(self):
        s = mc.ModeState(mode=mc.MODE_MANUAL, human_pause_or_end_recorded=True)
        r = mc.request_transition('start_autonomy', s, self.IMPL); self.assertTrue(r.accepted)
        self.assertFalse(r.new_state.human_pause_or_end_recorded)
        p = mc.request_transition('pause', r.new_state, self.IMPL).new_state
        self.assertEqual((p.mode, p.human_pause_or_end_recorded, p.stop_reason), (mc.MODE_PAUSE, True, 'human'))
        q = mc.request_transition('resume', p, self.IMPL).new_state
        self.assertEqual((q.mode, q.human_pause_or_end_recorded, q.stop_reason), (mc.MODE_AUTONOMY, False, ''))
        e = mc.request_transition('end_autonomy', q, self.IMPL).new_state
        self.assertEqual((e.mode, e.human_pause_or_end_recorded), (mc.MODE_MANUAL, True))

    def test_resume_after_restart_needs_initial_pose(self):
        s = mc.ModeState(mode=mc.MODE_PAUSE, initial_pose_required=True)
        self.assertFalse(mc.request_transition('resume', s, self.IMPL).accepted)

    def test_automatic_pause(self):
        a = mc.ModeState(mode=mc.MODE_AUTONOMY, remaining_waypoints=4)
        n = mc.automatic_pause(a, 'TR-08', mc.STOP_REASON_GOAL_REACHED, 1)
        self.assertEqual((n.mode, n.remaining_waypoints, n.human_pause_or_end_recorded), (mc.MODE_PAUSE, 1, False))
        self.assertEqual(mc.automatic_pause(a, 'TR-07', mc.STOP_REASON_PLAN_FAILURE, 4).stop_reason, 'plan_failure')
        # REV-128 (DEC-200, RQ-I029): 推定不能 pauses through TR-07 with its own stop reason
        n = mc.automatic_pause(a, 'TR-07', mc.STOP_REASON_ESTIMATOR, 4)
        self.assertEqual((n.mode, n.stop_reason), (mc.MODE_PAUSE, 'estimator_unavailable'))
        self.assertEqual(len({mc.STOP_REASON_PLAN_FAILURE, mc.STOP_REASON_NODE_FAILURE, mc.STOP_REASON_ESTIMATOR, mc.STOP_REASON_GOAL_REACHED}), 4)
        self.assertIsNone(mc.automatic_pause(mc.ModeState(mode=mc.MODE_PAUSE), 'TR-07', 'x', 1), 'a result after a pause changes nothing')


if __name__ == '__main__':
    unittest.main()
