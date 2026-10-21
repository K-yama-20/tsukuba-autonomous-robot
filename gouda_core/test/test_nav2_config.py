"""Unit tests of nav2_config (ND-10 settings, REV-061, DEC-121 / DEC-122, TS-37) without ROS.

Checked against the saved upstream template (design/research/upstream_jazzy, identical to the installed 1.3.13): only the listed
keys change; collision_monitor and the unused servers are not run; RPP / NavFn / spin-backup-wait / velocity_smoother; TwistStamped
everywhere a cmd_vel is published; the design's frames and topics; the obstacle height band and track_unknown_space; the
SpeedFilter; the BT gets PRM-11 / PRM-18 and nothing else; and with the vehicle files only (no trial) Nav2 is built only when every
vehicle value is decided: a copy of the generated files with one vehicle value removed builds nothing (Nav2 is not started rather
than run with general values, intent.md:85), the real generated files (all decided since REV-122) build (REV-125, DEC-199)."""
import copy
import json
import os
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gouda_core import nav2_config as nc  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
PARAMS = str(REPO / 'design' / 'generated' / 'params')
UP = REPO / 'design' / 'research' / 'upstream_jazzy'
NAV2_TEMPLATE = UP / 'nav2_bringup' / 'params' / 'nav2_params.yaml'
BT_TEMPLATE = UP / 'nav2_bt_navigator' / 'behavior_trees' / 'navigate_through_poses_w_replanning_and_recovery.xml'


def template():
    with open(NAV2_TEMPLATE, encoding='utf-8') as f:
        return yaml.safe_load(f)


class Nav2ConfigTests(unittest.TestCase):
    def setUp(self):
        self.values = nc.read_values(PARAMS, trial=True)
        self.p = nc.nav2_parameters(template(), self.values, '/x/bt.xml')

    def test_vehicle_files_alone_do_not_build(self):
        """A copy of the generated files with one vehicle value (PRM-66) removed: it is reported missing and nothing is built.
        The real generated files are not changed (REV-125, DEC-199)."""
        with tempfile.TemporaryDirectory() as d:
            params = os.path.join(d, 'params'); shutil.copytree(PARAMS, params)
            nav2 = os.path.join(params, 'gouda_nav2.yaml')
            with open(nav2, encoding='utf-8') as f:
                lines = f.read().splitlines(keepends=True)
            kept = [ln for ln in lines if not ln.lstrip().startswith('max_linear_velocity_mps:')]
            self.assertEqual(len(lines) - len(kept), 1, 'the generated gouda_nav2.yaml declares PRM-66 once')
            with open(nav2, 'w', encoding='utf-8') as f:
                f.writelines(kept)
            miss = nc.missing(nc.read_values(params, trial=False))
            self.assertEqual(miss, ['max_linear_velocity_mps (PRM-66)'])
            out = os.path.join(d, 'out')
            r = nc.write(params, False, str(NAV2_TEMPLATE), str(BT_TEMPLATE), out)
            self.assertEqual(r['missing'], miss); self.assertIsNone(r['params']); self.assertIsNone(r['bt']); self.assertFalse(os.path.exists(out))

    def test_vehicle_files_alone_build_when_all_decided(self):
        """The real generated files (every vehicle value decided, REV-122 / REV-124) build without the trial files."""
        self.assertEqual(nc.missing(nc.read_values(PARAMS, trial=False)), [])
        with tempfile.TemporaryDirectory() as d:
            r = nc.write(PARAMS, False, str(NAV2_TEMPLATE), str(BT_TEMPLATE), d)
            self.assertEqual(r['missing'], []); self.assertTrue(os.path.isfile(r['params'])); self.assertTrue(os.path.isfile(r['bt']))

    def test_trial_values_build(self):
        self.assertEqual(nc.missing(self.values), [])

    def test_servers(self):
        self.assertNotIn('collision_monitor', self.p, 'no PC-side stop mechanism (RQ-I072)')
        for k in ('amcl', 'docking_server', 'route_server', 'waypoint_follower', 'map_saver', 'loopback_simulator'):
            self.assertNotIn(k, self.p)
        self.assertEqual(self.p['lifecycle_manager_navigation']['ros__parameters']['autostart'], False)
        self.assertNotIn('collision_monitor', self.p['lifecycle_manager_navigation']['ros__parameters']['node_names'])

    def test_choices_and_values(self):
        v = {k: x for (_, k), x in self.values.items()}
        cs = self.p['controller_server']['ros__parameters']
        self.assertEqual(cs['FollowPath']['plugin'], 'nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController')
        self.assertEqual(cs['FollowPath']['desired_linear_vel'], v['max_linear_velocity_mps']); self.assertFalse(cs['FollowPath']['allow_reversing'])
        self.assertEqual(cs['controller_frequency'], v['controller_frequency'])
        for sec in ('controller_server', 'behavior_server', 'velocity_smoother'):
            self.assertTrue(self.p[sec]['ros__parameters']['enable_stamped_cmd_vel'], sec)
        self.assertEqual(self.p['planner_server']['ros__parameters']['GridBased']['plugin'], 'nav2_navfn_planner::NavfnPlanner')
        self.assertEqual(self.p['behavior_server']['ros__parameters']['behavior_plugins'], ['spin', 'backup', 'wait'])
        vs = self.p['velocity_smoother']['ros__parameters']
        self.assertEqual(vs['max_velocity'][0], v['max_linear_velocity_mps']); self.assertEqual(vs['max_decel'][2], -v['angular_accel_limit_radps2'])
        # DEC-198 plan A: reverse is limited by PRM-78 (full-deflection reverse speed), not by the forward limit PRM-66
        self.assertEqual(vs['min_velocity'][0], -v['max_reverse_speed_mps']); self.assertEqual(vs['min_velocity'][2], -v['max_angular_velocity_radps'])

    def test_reverse_limit_is_required(self):
        """PRM-78 is a vehicle value Nav2 needs (DEC-198): without it nothing is built."""
        values = dict(self.values); values[('gouda_motion_controller', 'max_reverse_speed_mps')] = None
        self.assertIn('max_reverse_speed_mps (PRM-78)', nc.missing(values))
        self.assertEqual(self.p['bt_navigator']['ros__parameters']['odom_topic'], nc.ODOM_TOPIC)

    def test_costmaps(self):
        v = {k: x for (_, k), x in self.values.items()}
        for name, frame in (('local_costmap', 'odom'), ('global_costmap', 'map')):
            c = self.p[name][name]['ros__parameters']
            self.assertEqual(c['global_frame'], frame); self.assertTrue(c['track_unknown_space']); self.assertNotIn('robot_radius', c)
            self.assertEqual(c['footprint'], v['footprint']); self.assertEqual(c['inflation_layer']['inflation_radius'], v['inflation_radius_m'])
        vl = self.p['local_costmap']['local_costmap']['ros__parameters']['voxel_layer']
        self.assertEqual(vl['points']['topic'], nc.POINTS_TOPIC); self.assertNotIn('scan', vl)
        self.assertEqual((vl['points']['min_obstacle_height'], vl['points']['max_obstacle_height']), (v['obstacle_min_height_m'], v['obstacle_max_height_m']))
        self.assertAlmostEqual(vl['origin_z'] + vl['z_voxels'] * vl['z_resolution'], v['obstacle_max_height_m'])
        g = self.p['global_costmap']['global_costmap']['ros__parameters']
        self.assertEqual(g['filters'], ['speed_filter']); self.assertEqual(g['speed_filter']['plugin'], 'nav2_costmap_2d::SpeedFilter')
        # the filter lives in the global_costmap namespace: its topics must be absolute to meet the servers and the controller
        self.assertTrue(g['speed_filter']['filter_info_topic'].startswith('/')); self.assertTrue(g['speed_filter']['speed_limit_topic'].startswith('/'))
        self.assertEqual(self.p['costmap_filter_info_server']['ros__parameters']['mask_topic'], self.p['filter_mask_server']['ros__parameters']['topic_name'])
        self.assertEqual(g['speed_filter']['speed_limit_topic'], self.p['controller_server']['ros__parameters']['speed_limit_topic'])

    def test_only_listed_keys_change(self):
        t = template()
        changed = {'bt_navigator': {'global_frame', 'robot_base_frame', 'odom_topic', 'default_nav_through_poses_bt_xml', 'use_sim_time'},
                   'planner_server': {'use_sim_time'}, 'smoother_server': {'use_sim_time'}}
        for sec, keys in changed.items():
            for k, x in t[sec]['ros__parameters'].items():
                if k not in keys:
                    self.assertEqual(self.p[sec]['ros__parameters'][k], x, f'{sec}.{k}')
        self.assertEqual(template(), t, 'the template is not modified')

    def test_bt(self):
        v = {k: x for (_, k), x in self.values.items()}
        xml = BT_TEMPLATE.read_text(encoding='utf-8')
        out = ET.fromstring(nc.build_bt(xml, self.values)); src = ET.fromstring(xml)
        self.assertEqual(out.find('.//RemovePassedGoals').get('radius'), repr(float(v['remove_passed_goals_radius_m'])))
        self.assertEqual(out.find("./BehaviorTree/RecoveryNode[@name='NavigateRecovery']").get('number_of_retries'), str(v['recovery_number_of_retries']))
        a = [(e.tag, {k: x for k, x in e.attrib.items() if not (e.tag == 'RemovePassedGoals' and k == 'radius') and not (e.get('name') == 'NavigateRecovery' and k == 'number_of_retries')}) for e in src.iter()]
        b = [(e.tag, {k: x for k, x in e.attrib.items() if not (e.tag == 'RemovePassedGoals' and k == 'radius') and not (e.get('name') == 'NavigateRecovery' and k == 'number_of_retries')}) for e in out.iter()]
        self.assertEqual(a, b, 'no other change to the BT')

    def test_write(self):
        with tempfile.TemporaryDirectory() as d:
            r = nc.write(PARAMS, True, str(NAV2_TEMPLATE), str(BT_TEMPLATE), d)
            self.assertEqual(r['missing'], [])
            with open(r['params']) as f: doc = yaml.safe_load(f)
            self.assertEqual(doc['bt_navigator']['ros__parameters']['default_nav_through_poses_bt_xml'], r['bt'])

    def test_recovery_count_from_the_monitor(self):
        """REV-132 (DEC-207 (a), DEC-209, TS-45): a valid count saved in the monitor goes into the BT; otherwise PRM-18, with the reason."""
        prm18 = self.values[('bt_params', 'recovery_number_of_retries')]
        def bt_count(r):
            return ET.parse(r['bt']).getroot().find("./BehaviorTree/RecoveryNode[@name='NavigateRecovery']").get('number_of_retries')
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, 'config'); os.makedirs(cfg)
            r = nc.write(PARAMS, True, str(NAV2_TEMPLATE), str(BT_TEMPLATE), os.path.join(d, 'a'), cfg)
            self.assertEqual(bt_count(r), str(prm18)); self.assertIn('does not exist', r['recovery']['note'])
            with open(os.path.join(cfg, nc.RECOVERY_CONFIG), 'w') as f:
                json.dump({'values': {'recovery_number_of_retries': 3}, 'config_revision': 4}, f)
            r = nc.write(PARAMS, True, str(NAV2_TEMPLATE), str(BT_TEMPLATE), os.path.join(d, 'b'), cfg)
            self.assertEqual(bt_count(r), '3'); self.assertIn('config_revision 4', r['recovery']['source'])
            with open(os.path.join(d, 'b', 'recovery.json')) as f: self.assertEqual(json.load(f)['value'], 3)
            for bad in (0, prm18 + 1, 2.5, True, 'UNKNOWN', '7'):
                with open(os.path.join(cfg, nc.RECOVERY_CONFIG), 'w') as f:
                    json.dump({'values': {'recovery_number_of_retries': bad}}, f)
                r = nc.write(PARAMS, True, str(NAV2_TEMPLATE), str(BT_TEMPLATE), os.path.join(d, 'c'), cfg)
                self.assertEqual(bt_count(r), str(prm18), repr(bad)); self.assertTrue(r['recovery']['note'], repr(bad))
            with open(os.path.join(cfg, nc.RECOVERY_CONFIG), 'w') as f: f.write('{broken')
            r = nc.write(PARAMS, True, str(NAV2_TEMPLATE), str(BT_TEMPLATE), os.path.join(d, 'e'), cfg)
            self.assertEqual(bt_count(r), str(prm18)); self.assertIn('could not be read', r['recovery']['note'])


if __name__ == '__main__':
    unittest.main()
