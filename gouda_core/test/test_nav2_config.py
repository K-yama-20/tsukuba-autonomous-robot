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

    def test_keepout_servers_and_filters(self):
        """REV-137 (DEC-220..222): keepout mask / info servers (type 0, base 0, multiplier 1) and a KeepoutFilter on both costmaps
        with override_lethal_cost true; the global costmap keeps the SpeedFilter too."""
        names = self.p['lifecycle_manager_navigation']['ros__parameters']['node_names']
        for n in ('keepout_mask_server', 'keepout_filter_info_server'): self.assertIn(n, names)
        info = self.p['keepout_filter_info_server']['ros__parameters']
        self.assertEqual((info['type'], info['base'], info['multiplier'], info['mask_topic']), (0, 0.0, 1.0, nc.KEEPOUT_MASK_TOPIC))
        self.assertEqual(self.p['keepout_mask_server']['ros__parameters']['topic_name'], nc.KEEPOUT_MASK_TOPIC)
        g = self.p['global_costmap']['global_costmap']['ros__parameters']; l = self.p['local_costmap']['local_costmap']['ros__parameters']
        self.assertEqual(g['filters'], ['speed_filter', 'keepout_filter']); self.assertEqual(l['filters'], ['keepout_filter'])
        for c in (g, l):
            k = c['keepout_filter']
            self.assertEqual((k['plugin'], k['filter_info_topic'], k['override_lethal_cost']), ('nav2_costmap_2d::KeepoutFilter', nc.KEEPOUT_INFO_TOPIC, True))
            self.assertTrue(k['filter_info_topic'].startswith('/'))   # absolute: the filters live in the costmap namespaces

    def test_keepout_layer_before_inflation(self):
        """DEC-227 plan A (REV-140): the global costmap reads the keepout mask in a StaticLayer before the inflation layer (keepout
        areas are inflated like walls); the local costmap has only the filter (DEC-222). The other layers keep their template order."""
        g = self.p['global_costmap']['global_costmap']['ros__parameters']; l = self.p['local_costmap']['local_costmap']['ros__parameters']
        self.assertEqual(g['plugins'], ['static_layer', 'obstacle_layer', nc.KEEPOUT_LAYER, 'inflation_layer'])
        k = g[nc.KEEPOUT_LAYER]
        self.assertEqual((k['plugin'], k['map_topic'], k['map_subscribe_transient_local'], k['subscribe_to_updates']),
                         ('nav2_costmap_2d::StaticLayer', nc.KEEPOUT_MASK_TOPIC, True, False))
        self.assertTrue(g['use_maximum'])            # the -1 cells of the mask leave the map as it is
        self.assertNotIn('map_topic', g['static_layer'])   # the map's own layer still reads /map
        self.assertNotIn(nc.KEEPOUT_LAYER, l['plugins']); self.assertNotIn('use_maximum', l)

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
            self.assertIs(c['inflation_layer']['inflate_around_unknown'], bool(v['inflate_around_unknown']))   # PRM-98 (DEC-217)
        vl = self.p['local_costmap']['local_costmap']['ros__parameters']['voxel_layer']
        self.assertEqual(vl['points']['topic'], nc.POINTS_TOPIC); self.assertNotIn('scan', vl)
        self.assertEqual((vl['points']['min_obstacle_height'], vl['points']['max_obstacle_height']), (v['obstacle_min_height_m'], v['obstacle_max_height_m']))
        self.assertAlmostEqual(vl['origin_z'] + vl['z_voxels'] * vl['z_resolution'], v['obstacle_max_height_m'])
        g = self.p['global_costmap']['global_costmap']['ros__parameters']
        # DEC-216: what the LiDAR sees never turns the unknown outside of the swept corridor into free (global only)
        self.assertEqual(g['obstacle_layer']['combination_method'], 2)
        self.assertNotIn('combination_method', self.p['local_costmap']['local_costmap']['ros__parameters']['voxel_layer'])
        self.assertEqual(g['filters'], ['speed_filter', 'keepout_filter']); self.assertEqual(g['speed_filter']['plugin'], 'nav2_costmap_2d::SpeedFilter')   # keepout: DEC-222 (REV-137)
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
        replan = [r for r in out.iter('RateController') if r.find('.//ComputePathThroughPoses') is not None]
        self.assertEqual(len(replan), 1)
        self.assertEqual(replan[0].get('hz'), repr(float(v['replan_rate_hz'])))   # PRM-103 (REV-167)
        def changed(e, k):
            return ((e.tag == 'RemovePassedGoals' and k == 'radius') or (e.get('name') == 'NavigateRecovery' and k == 'number_of_retries')
                    or (e.tag == 'RateController' and k == 'hz'))
        # A-1 (DEC-393): the guard in front of the outer recovery actions is the only removed node
        outer = out.find("./BehaviorTree/RecoveryNode[@name='NavigateRecovery']")
        self.assertEqual([c.tag for c in list(outer)[1]], ['ReactiveFallback'])
        src_branch = list(src.find("./BehaviorTree/RecoveryNode[@name='NavigateRecovery']"))[1]
        src_branch.remove([c for c in src_branch if c.tag == 'Fallback'][0])
        a = [(e.tag, {k: x for k, x in e.attrib.items() if not changed(e, k)}) for e in src.iter()]
        b = [(e.tag, {k: x for k, x in e.attrib.items() if not changed(e, k)}) for e in out.iter()]
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
            with open(os.path.join(cfg, nc.RECOVERY_CONFIG), 'w') as f:
                json.dump({'values': {'recovery_number_of_retries': 'UNKNOWN', 'inflate_around_unknown': True}, 'config_revision': 6}, f)
            r = nc.write(PARAMS, True, str(NAV2_TEMPLATE), str(BT_TEMPLATE), os.path.join(d, 'f'), cfg)   # DEC-217: the tab overrides PRM-98
            with open(r['params']) as f: doc = yaml.safe_load(f)
            for name in ('local_costmap', 'global_costmap'):
                self.assertIs(doc[name][name]['ros__parameters']['inflation_layer']['inflate_around_unknown'], True)
            self.assertIn('config_revision 6', r['inflate_around_unknown']['source']); self.assertEqual(bt_count(r), str(prm18))
            with open(os.path.join(d, 'f', 'overrides.json')) as f: self.assertIs(json.load(f)['inflate_around_unknown']['value'], True)
            with open(os.path.join(cfg, nc.RECOVERY_CONFIG), 'w') as f:
                json.dump({'values': {'inflate_around_unknown': 'yes'}}, f)
            r = nc.write(PARAMS, True, str(NAV2_TEMPLATE), str(BT_TEMPLATE), os.path.join(d, 'g'), cfg)
            self.assertEqual(r['inflate_around_unknown']['value'], self.values[('gouda_nav2', 'inflate_around_unknown')]); self.assertIn('not true / false', r['inflate_around_unknown']['note'])
            with open(os.path.join(cfg, nc.RECOVERY_CONFIG), 'w') as f: f.write('{broken')
            r = nc.write(PARAMS, True, str(NAV2_TEMPLATE), str(BT_TEMPLATE), os.path.join(d, 'e'), cfg)
            self.assertEqual(bt_count(r), str(prm18)); self.assertIn('could not be read', r['recovery']['note'])


    def test_replan_rate_from_the_monitor(self):
        """REV-167 (DEC-347): a positive replanning rate saved in the monitor goes into the BT's RateController; otherwise PRM-103."""
        prm103 = self.values[('bt_params', 'replan_rate_hz')]
        def bt_hz(r):
            root = ET.parse(r['bt']).getroot()
            return [x for x in root.iter('RateController') if x.find('.//ComputePathThroughPoses') is not None][0].get('hz')
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, 'config'); os.makedirs(cfg)
            r = nc.write(PARAMS, True, str(NAV2_TEMPLATE), str(BT_TEMPLATE), os.path.join(d, 'a'), cfg)
            self.assertEqual(bt_hz(r), repr(float(prm103))); self.assertIn('does not exist', r['replan_rate_hz']['note'])
            with open(os.path.join(cfg, nc.RECOVERY_CONFIG), 'w') as f:
                json.dump({'values': {'replan_rate_hz': 2.5}, 'config_revision': 8}, f)
            r = nc.write(PARAMS, True, str(NAV2_TEMPLATE), str(BT_TEMPLATE), os.path.join(d, 'b'), cfg)
            self.assertEqual(bt_hz(r), '2.5'); self.assertIn('config_revision 8', r['replan_rate_hz']['source'])
            with open(os.path.join(d, 'b', 'overrides.json')) as f: self.assertEqual(json.load(f)['replan_rate_hz']['value'], 2.5)
            for bad in (0, -1, True, 'UNKNOWN', '2', float('inf')):
                with open(os.path.join(cfg, nc.RECOVERY_CONFIG), 'w') as f:
                    json.dump({'values': {'replan_rate_hz': bad}}, f)
                r = nc.write(PARAMS, True, str(NAV2_TEMPLATE), str(BT_TEMPLATE), os.path.join(d, 'c'), cfg)
                self.assertEqual(bt_hz(r), repr(float(prm103)), repr(bad))


class TunableTests(unittest.TestCase):
    """REV-183 (DEC-393): the /config 「Nav2」 tab values (PRM-105..129 and the PRM-72 override). While a PRM is unresolved and nothing
    is saved, nothing is written (the template / plugin value stays); a valid saved value is written; an invalid one is not."""
    def build(self, d, name, saved=None):
        cfg = os.path.join(d, 'config'); os.makedirs(cfg, exist_ok=True)
        if saved is not None:
            with open(os.path.join(cfg, nc.RECOVERY_CONFIG), 'w') as f:
                json.dump({'values': saved, 'config_revision': 4}, f)
        r = nc.write(PARAMS, True, str(NAV2_TEMPLATE), str(BT_TEMPLATE), os.path.join(d, name), cfg)
        with open(r['params']) as f: params = yaml.safe_load(f)
        return r, params, ET.parse(r['bt']).getroot()

    def test_unresolved_and_unsaved_change_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            r, p, bt = self.build(d, 'a')
            t = template()
            self.assertEqual(p['bt_navigator']['ros__parameters']['default_server_timeout'], t['bt_navigator']['ros__parameters']['default_server_timeout'])
            follow = p['controller_server']['ros__parameters']['FollowPath']
            self.assertEqual(set(follow), {'plugin', 'desired_linear_vel', 'rotate_to_heading_angular_vel', 'allow_reversing'})
            lc, gc = p['local_costmap']['local_costmap']['ros__parameters'], p['global_costmap']['global_costmap']['ros__parameters']
            tl, tg = t['local_costmap']['local_costmap']['ros__parameters'], t['global_costmap']['global_costmap']['ros__parameters']
            self.assertEqual((lc['width'], lc['height']), (tl['width'], tl['height']))
            self.assertEqual(gc['update_frequency'], tg['update_frequency'])
            self.assertNotIn('obstacle_max_range', lc['voxel_layer']['points']); self.assertNotIn('raytrace_max_range', gc['obstacle_layer']['points'])
            self.assertEqual(lc['voxel_layer']['mark_threshold'], tl['voxel_layer']['mark_threshold'])
            self.assertEqual(lc['inflation_layer']['cost_scaling_factor'], tl['inflation_layer']['cost_scaling_factor'])
            src = ET.parse(str(BT_TEMPLATE)).getroot()
            for tag in ('Spin', 'Wait', 'BackUp'):
                self.assertEqual(bt.find('.//' + tag).attrib, src.find('.//' + tag).attrib, tag)
            for name in ('ComputePathThroughPoses', 'FollowPath'):
                q = f".//RecoveryNode[@name='{name}']"
                self.assertEqual(bt.find(q).get('number_of_retries'), src.find(q).get('number_of_retries'))
            with open(os.path.join(d, 'a', 'overrides.json')) as f: o = json.load(f)
            self.assertIsNone(o['rpp_lookahead_dist_m']['value']); self.assertIn('not written', o['rpp_lookahead_dist_m']['note'])
            self.assertEqual(o['inflation_radius_m']['source'], 'PRM-72 (generated parameter file)')

    def test_saved_values_are_written(self):
        saved = {'bt_default_server_timeout_ms': 200, 'recovery_spin_enabled': False, 'recovery_wait_s': 3.5, 'recovery_backup_dist_m': 0.4,
                 'recovery_backup_speed_mps': 0.2, 'replan_recovery_retries': 2, 'follow_path_recovery_retries': 0,
                 'rpp_use_collision_detection': True, 'rpp_max_time_to_collision_s': 1.5, 'rpp_min_lookahead_dist_m': 0.5,
                 'rpp_max_lookahead_dist_m': 1.8, 'rpp_use_velocity_scaled_lookahead_dist': True, 'local_costmap_size_m': 6,
                 'obstacle_max_range_m': 3.0, 'raytrace_max_range_m': 4.0, 'voxel_mark_threshold': 1, 'global_costmap_update_hz': 2.0,
                 'inflation_cost_scaling_factor': 5.0, 'inflation_radius_m': 0.8}
        with tempfile.TemporaryDirectory() as d:
            r, p, bt = self.build(d, 'b', saved)
            self.assertEqual(p['bt_navigator']['ros__parameters']['default_server_timeout'], 200)
            follow = p['controller_server']['ros__parameters']['FollowPath']
            self.assertEqual((follow['use_collision_detection'], follow['max_allowed_time_to_collision_up_to_carrot'], follow['min_lookahead_dist'],
                              follow['max_lookahead_dist'], follow['use_velocity_scaled_lookahead_dist']), (True, 1.5, 0.5, 1.8, True))
            self.assertNotIn('lookahead_dist', follow)   # not saved and unresolved: the plugin value stays
            lc, gc = p['local_costmap']['local_costmap']['ros__parameters'], p['global_costmap']['global_costmap']['ros__parameters']
            self.assertEqual((lc['width'], lc['height']), (6, 6))
            for src in (lc['voxel_layer']['points'], gc['obstacle_layer']['points']):
                self.assertEqual((src['obstacle_max_range'], src['raytrace_max_range']), (3.0, 4.0))
            self.assertEqual(lc['voxel_layer']['mark_threshold'], 1); self.assertEqual(gc['update_frequency'], 2.0)
            for c in (lc, gc):
                self.assertEqual((c['inflation_layer']['cost_scaling_factor'], c['inflation_layer']['inflation_radius']), (5.0, 0.8))
            self.assertIsNone(bt.find('.//Spin')); self.assertIsNotNone(bt.find('.//BackUp'))   # spin removed, backup kept
            self.assertEqual(bt.find('.//Wait').get('wait_duration'), '3.5')
            self.assertEqual((bt.find('.//BackUp').get('backup_dist'), bt.find('.//BackUp').get('backup_speed')), ('0.4', '0.2'))
            self.assertEqual(bt.find(".//RecoveryNode[@name='ComputePathThroughPoses']").get('number_of_retries'), '2')
            self.assertEqual(bt.find(".//RecoveryNode[@name='FollowPath']").get('number_of_retries'), '0')
            self.assertIn('config_revision 4', r['tunables']['local_costmap_size_m']['source'])

    def test_invalid_saved_values_are_not_written(self):
        bad = {'local_costmap_size_m': 2.5, 'recovery_spin_enabled': 'yes', 'voxel_mark_threshold': -1, 'obstacle_max_range_m': 0,
               'bt_default_server_timeout_ms': True, 'global_costmap_update_hz': float('inf')}
        with tempfile.TemporaryDirectory() as d:
            r, p, bt = self.build(d, 'c', bad)
            t = template()
            lc = p['local_costmap']['local_costmap']['ros__parameters']
            self.assertEqual(lc['width'], t['local_costmap']['local_costmap']['ros__parameters']['width'])
            self.assertIsNotNone(bt.find('.//Spin'))
            self.assertNotIn('obstacle_max_range', lc['voxel_layer']['points'])
            for k in bad:
                self.assertIn('is not valid', r['tunables'][k]['note'], k)

    def test_valid_tunable_kinds(self):
        self.assertTrue(nc.valid_tunable('positive_int', 3)); self.assertTrue(nc.valid_tunable('positive_int', 3.0))
        self.assertFalse(nc.valid_tunable('positive_int', 0)); self.assertFalse(nc.valid_tunable('positive_int', 2.5))
        self.assertTrue(nc.valid_tunable('whole', 0)); self.assertFalse(nc.valid_tunable('whole', -1))
        self.assertFalse(nc.valid_tunable('positive', True)); self.assertFalse(nc.valid_tunable('boolean', 1))


if __name__ == '__main__':
    unittest.main()
