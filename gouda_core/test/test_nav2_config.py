"""Unit tests of nav2_config (ND-10 settings, REV-061, DEC-121 / DEC-122, TS-37) without ROS.

Checked against the saved upstream template (design/research/upstream_jazzy, identical to the installed 1.3.13): only the listed
keys change; collision_monitor and the unused servers are not run; RPP / NavFn / spin-backup-wait / velocity_smoother; TwistStamped
everywhere a cmd_vel is published; the design's frames and topics; the obstacle height band and track_unknown_space; the
SpeedFilter; the BT gets PRM-11 / PRM-18 and nothing else; and with the vehicle files only (no trial) Nav2 is built only when every
vehicle value is decided: a copy of the generated files with one vehicle value removed builds nothing (Nav2 is not started rather
than run with general values, intent.md:85), the real generated files (all decided since REV-122) build (REV-125, DEC-199)."""
import copy
import json
import math
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
        # REV-185 (DEC-336 / DEC-321 / DEC-322): the band is cut in base_link by pointcloud_to_laserscan; both costmaps read its scan
        lc = self.p['local_costmap']['local_costmap']['ros__parameters']
        self.assertNotIn('voxel_layer', lc); self.assertEqual(lc['plugins'][0], 'obstacle_layer')
        g = self.p['global_costmap']['global_costmap']['ros__parameters']
        for layer in (lc['obstacle_layer'], g['obstacle_layer']):
            self.assertEqual(layer['plugin'], 'nav2_costmap_2d::ObstacleLayer'); self.assertEqual(layer['observation_sources'], 'scan')
            s = layer['scan']
            self.assertEqual((s['topic'], s['data_type']), (nc.SCAN_TOPIC, 'LaserScan')); self.assertIs(s['inf_is_valid'], True)
            self.assertEqual((s['min_obstacle_height'], s['max_obstacle_height']), (-float('inf'), float('inf')))   # no band in Nav2
            self.assertEqual((layer['min_obstacle_height'], layer['max_obstacle_height']), (-float('inf'), float('inf')))
            ts = template()['global_costmap']['global_costmap']['ros__parameters']['obstacle_layer']['scan']
            self.assertEqual((s['obstacle_max_range'], s['raytrace_max_range']), (ts['obstacle_max_range'], ts['raytrace_max_range']))
        sc = self.p[nc.SCAN_NODE]['ros__parameters']
        self.assertEqual(sc['target_frame'], 'base_link')
        self.assertEqual((sc['min_height'], sc['max_height']), (v['obstacle_min_height_m'], v['obstacle_max_height_m']))   # PRM-70 / PRM-71
        self.assertEqual((sc['angle_min'], sc['angle_max'], sc['use_inf']), (-math.pi, math.pi, True))
        # REV-186 (DEC-396): an inf beam must become a point: finite range_max beyond what the layer marks and clears
        self.assertTrue(math.isfinite(sc['range_max']))
        self.assertGreater(sc['range_max'], max(ts['obstacle_max_range'], ts['raytrace_max_range']))
        # DEC-216: what the LiDAR sees never turns the unknown outside of the swept corridor into free (global only)
        self.assertEqual(g['obstacle_layer']['combination_method'], 2)
        self.assertNotIn('combination_method', lc['obstacle_layer'])
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

    def test_mppi_is_the_default(self):   # REV-190 (DEC-400, DEC-402): PRM-130..133, PRM-124
        with tempfile.TemporaryDirectory() as d:
            r, p, bt = self.build(d, 'm')
            t = template(); tf = t['controller_server']['ros__parameters']['FollowPath']
            follow = p['controller_server']['ros__parameters']['FollowPath']
            vs = p['velocity_smoother']['ros__parameters']
            self.assertEqual(follow['plugin'], nc.MPPI_PLUGIN)
            self.assertEqual((follow['vx_max'], follow['vx_min'], follow['wz_max']), (0.8, 0.0, 1.0))
            self.assertEqual((follow['ax_max'], follow['ax_min'], follow['az_max']), (vs['max_accel'][0], -vs['max_accel'][0], vs['max_accel'][2]))
            self.assertAlmostEqual(follow['prune_distance'], tf['prune_distance'] * 0.8 / tf['vx_max'])
            horizon = follow['vx_max'] * follow['time_steps'] * follow['model_dt']
            self.assertGreater(follow['prune_distance'], horizon)
            self.assertIs(follow['CostCritic']['consider_footprint'], True); self.assertIs(follow['visualize'], False)
            lc = p['local_costmap']['local_costmap']['ros__parameters']
            self.assertEqual((lc['width'], lc['height'], lc['update_frequency']), (8, 8, 10.0))
            self.assertGreater(lc['width'] / 2, horizon)   # the prediction stays inside the costmap
            changed = {'plugin', 'vx_max', 'vx_min', 'wz_max', 'ax_max', 'ax_min', 'az_max', 'prune_distance', 'visualize', 'CostCritic',
                       'open_loop'}   # REV-240 (DEC-449): PRM-141 is written; its value is checked in test_mppi_open_loop
            self.assertEqual({k: v for k, v in follow.items() if k not in changed}, {k: v for k, v in tf.items() if k not in changed})

    def test_rpp_stays_selectable(self):
        saved = {'controller_use_mppi': False, 'rpp_lookahead_dist_m': 0.7}
        with tempfile.TemporaryDirectory() as d:
            r, p, bt = self.build(d, 'r', saved)
            follow = p['controller_server']['ros__parameters']['FollowPath']
            self.assertEqual(follow['plugin'], 'nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController')
            self.assertEqual(follow['lookahead_dist'], 0.7); self.assertNotIn('vx_max', follow)

    def test_saved_mppi_limits(self):
        with tempfile.TemporaryDirectory() as d:
            r, p, bt = self.build(d, 's', {'mppi_vx_max_mps': 0.5, 'mppi_wz_max_radps': 0.3, 'local_costmap_update_hz': 5})
            follow = p['controller_server']['ros__parameters']['FollowPath']
            self.assertEqual((follow['vx_max'], follow['wz_max']), (0.5, 0.3))
            self.assertEqual(p['local_costmap']['local_costmap']['ros__parameters']['update_frequency'], 5.0)

    def test_mppi_vx_min(self):   # REV-261 (DEC-480): PRM-162 by default, another value from /config, refused at or above vx_max
        with tempfile.TemporaryDirectory() as d:
            r, p, bt = self.build(d, 'v', {'mppi_vx_min_mps': 0.1})
            self.assertEqual(p['controller_server']['ros__parameters']['FollowPath']['vx_min'], 0.1)
        self.assertEqual(nc.mppi_follow({'plugin': nc.MPPI_PLUGIN, 'vx_max': 0.5, 'prune_distance': 1.7, 'CostCritic': {}}, {}, 1.0, 1.0)['vx_min'], 0.0)
        with self.assertRaises(ValueError):
            nc.mppi_follow({'plugin': nc.MPPI_PLUGIN, 'vx_max': 0.5, 'prune_distance': 1.7, 'CostCritic': {}}, {'mppi_vx_min_mps': 0.5}, 1.0, 1.0)

    def test_mppi_open_loop(self):   # REV-240 (DEC-449): PRM-141 true by default, false selectable in /config
        with tempfile.TemporaryDirectory() as d:
            r, p, bt = self.build(d, 'o')
            self.assertIs(p['controller_server']['ros__parameters']['FollowPath']['open_loop'], True)
        with tempfile.TemporaryDirectory() as d:
            r, p, bt = self.build(d, 'c', {'mppi_open_loop': False})
            self.assertIs(p['controller_server']['ros__parameters']['FollowPath']['open_loop'], False)
        with tempfile.TemporaryDirectory() as d:
            r, p, bt = self.build(d, 'r', {'controller_use_mppi': False})
            self.assertNotIn('open_loop', p['controller_server']['ros__parameters']['FollowPath'])

    def test_smooth_path_in_the_replanning_branch(self):   # REV-190 (DEC-401)
        with tempfile.TemporaryDirectory() as d:
            r, p, bt = self.build(d, 'p')
            inner = bt.find(".//RecoveryNode[@name='ComputePathThroughPoses']")
            planned = list(inner)[0]
            self.assertEqual((planned.tag, len(list(inner))), ('Sequence', 2))
            self.assertEqual([c.tag for c in planned], ['ReactiveSequence', 'SmoothPath'])   # not reactive around the smoother
            self.assertEqual(planned.find('ReactiveSequence/ComputePathThroughPoses').get('path'), '{unsmoothed_path}')
            s = planned.find('SmoothPath')
            self.assertEqual((s.get('unsmoothed_path'), s.get('smoothed_path'), s.get('smoother_id')), ('{unsmoothed_path}', '{path}', nc.SMOOTHER_ID))
            self.assertEqual(bt.find('.//FollowPath').get('path'), '{path}')
            self.assertEqual(template()['smoother_server']['ros__parameters']['smoother_plugins'], [nc.SMOOTHER_ID])
            r, p, off = self.build(d, 'q', {'path_smoothing_enabled': False})
            self.assertIsNone(off.find('.//SmoothPath'))
            self.assertEqual(off.find('.//ComputePathThroughPoses').get('path'), '{path}')

    def test_unresolved_and_unsaved_change_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            r, p, bt = self.build(d, 'a', {'controller_use_mppi': False})   # RPP: the values PRM-114..123 would go to
            t = template()
            self.assertEqual(p['bt_navigator']['ros__parameters']['default_server_timeout'], t['bt_navigator']['ros__parameters']['default_server_timeout'])
            follow = p['controller_server']['ros__parameters']['FollowPath']
            self.assertEqual(set(follow), {'plugin', 'desired_linear_vel', 'rotate_to_heading_angular_vel', 'allow_reversing'})
            lc, gc = p['local_costmap']['local_costmap']['ros__parameters'], p['global_costmap']['global_costmap']['ros__parameters']
            tl, tg = t['local_costmap']['local_costmap']['ros__parameters'], t['global_costmap']['global_costmap']['ros__parameters']
            self.assertEqual(gc['update_frequency'], tg['update_frequency'])
            ts = tg['obstacle_layer']['scan']   # the ranges stay the template's (REV-185)
            for src in (lc['obstacle_layer']['scan'], gc['obstacle_layer']['scan']):
                self.assertEqual((src['obstacle_max_range'], src['raytrace_max_range']), (ts['obstacle_max_range'], ts['raytrace_max_range']))
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
                 'inflation_cost_scaling_factor': 5.0, 'inflation_radius_m': 0.8, 'controller_use_mppi': False}
        with tempfile.TemporaryDirectory() as d:
            r, p, bt = self.build(d, 'b', saved)
            self.assertEqual(p['bt_navigator']['ros__parameters']['default_server_timeout'], 200)
            follow = p['controller_server']['ros__parameters']['FollowPath']
            self.assertEqual((follow['use_collision_detection'], follow['max_allowed_time_to_collision_up_to_carrot'], follow['min_lookahead_dist'],
                              follow['max_lookahead_dist'], follow['use_velocity_scaled_lookahead_dist']), (True, 1.5, 0.5, 1.8, True))
            self.assertNotIn('lookahead_dist', follow)   # not saved and unresolved: the plugin value stays
            lc, gc = p['local_costmap']['local_costmap']['ros__parameters'], p['global_costmap']['global_costmap']['ros__parameters']
            self.assertEqual((lc['width'], lc['height']), (6, 6))
            for src in (lc['obstacle_layer']['scan'], gc['obstacle_layer']['scan']):
                self.assertEqual((src['obstacle_max_range'], src['raytrace_max_range']), (3.0, 4.0))
            self.assertGreater(p[nc.SCAN_NODE]['ros__parameters']['range_max'], 4.0)   # REV-186: follows the saved ranges
            self.assertNotIn('voxel_layer', lc); self.assertEqual(gc['update_frequency'], 2.0)   # PRM-127 unused since REV-185
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
            self.assertEqual(lc['width'], 8)   # PRM-124
            self.assertIsNotNone(bt.find('.//Spin'))
            self.assertEqual(lc['obstacle_layer']['scan']['obstacle_max_range'], t['global_costmap']['global_costmap']['ros__parameters']['obstacle_layer']['scan']['obstacle_max_range'])
            for k in bad:
                self.assertIn('is not valid', r['tunables'][k]['note'], k)

    def test_valid_tunable_kinds(self):
        self.assertTrue(nc.valid_tunable('positive_int', 3)); self.assertTrue(nc.valid_tunable('positive_int', 3.0))
        self.assertFalse(nc.valid_tunable('positive_int', 0)); self.assertFalse(nc.valid_tunable('positive_int', 2.5))
        self.assertTrue(nc.valid_tunable('whole', 0)); self.assertFalse(nc.valid_tunable('whole', -1))
        self.assertFalse(nc.valid_tunable('positive', True)); self.assertFalse(nc.valid_tunable('boolean', 1))


class Mid360LayerTests(unittest.TestCase):
    """REV-242 (DEC-454): the MID-360 as a layer of its own (plan B1 = drive_sim_layers S2)."""
    def build(self, d, name, ready, saved=None):
        cfg = os.path.join(d, 'config'); os.makedirs(cfg, exist_ok=True)
        if saved is not None:
            with open(os.path.join(cfg, nc.RECOVERY_CONFIG), 'w') as f:
                json.dump({'values': saved, 'config_revision': 2}, f)
        kw = {} if ready is None else {'mid360_ready': ready}
        r = nc.write(PARAMS, False, str(NAV2_TEMPLATE), str(BT_TEMPLATE), os.path.join(d, name), cfg, **kw)
        with open(r['params']) as f: params = yaml.safe_load(f)
        bt = params['bt_navigator']['ros__parameters']
        self.assertEqual(bt['default_nav_through_poses_bt_xml'], r['bt'])
        bt['default_nav_through_poses_bt_xml'] = 'BT'   # the out_dir differs per build; everything else is compared
        return r, params

    def test_prm142_is_true_in_the_generated_file(self):
        self.assertIs(nc.read_tunables(PARAMS, False)['mid360_enabled'], True)

    def test_off_or_not_ready_is_unchanged(self):
        """(a) disabled in /config, or not ready (no vehicle PC values / no driver), or not checked: the same file as before REV-242."""
        with tempfile.TemporaryDirectory() as d:
            r0, base = self.build(d, 'n', None)   # the callers before REV-242 (no argument)
            self.assertFalse(r0['mid360']['used'])
            for name, ready, saved in (('a', 'mid360.json does not exist', None), ('b', '', {'mid360_enabled': False}),
                                       ('c', 'livox_ros_driver2 is not installed', {'mid360_enabled': True})):
                r, p = self.build(d, name, ready, saved)
                self.assertFalse(r['mid360']['used'], name)
                self.assertEqual(p, base, name)
            self.assertIn('does not exist', self.build(d, 'a2', 'mid360.json does not exist')[0]['mid360']['reason'])
        self.assertNotIn('mid360_scan', base)
        lc, gc = base['local_costmap']['local_costmap']['ros__parameters'], base['global_costmap']['global_costmap']['ros__parameters']
        self.assertEqual(lc['plugins'], ['obstacle_layer', 'inflation_layer'])
        self.assertEqual(gc['plugins'], ['static_layer', 'obstacle_layer', nc.KEEPOUT_LAYER, 'inflation_layer'])
        self.assertNotIn('mid360_layer', lc); self.assertNotIn('mid360_layer', gc)

    def test_on_and_ready_adds_the_layer_and_the_scan(self):
        """(b) mid360_scan with xt32_scan's band, and a mid360_layer after obstacle_layer in local and global; the XT-32 layer as before."""
        with tempfile.TemporaryDirectory() as d:
            _, base = self.build(d, 'n', None)
            r, p = self.build(d, 'y', '')
        self.assertTrue(r['mid360']['used'])
        self.assertEqual(p['mid360_scan'], p['xt32_scan'])   # the same band PRM-70 / PRM-71 and range_max (DEC-455 open)
        self.assertEqual(p['xt32_scan'], base['xt32_scan'])
        for name in ('local_costmap', 'global_costmap'):
            c, b = p[name][name]['ros__parameters'], base[name][name]['ros__parameters']
            exp = list(b['plugins']); exp.insert(exp.index('obstacle_layer') + 1, 'mid360_layer')
            self.assertEqual(c['plugins'], exp, name)
            self.assertEqual(c['obstacle_layer'], b['obstacle_layer'], f'{name}: the XT-32 layer is not changed')
            self.assertEqual({k: v for k, v in c.items() if k not in ('plugins', 'mid360_layer')},
                             {k: v for k, v in b.items() if k != 'plugins'}, name)
            m = c['mid360_layer']; xs = c['obstacle_layer']['scan']
            self.assertEqual((m['plugin'], m['observation_sources']), ('nav2_costmap_2d::ObstacleLayer', 'mid_mark mid_clear'))
            mark, clear = m['mid_mark'], m['mid_clear']
            self.assertEqual((mark['topic'], mark['data_type'], mark['marking'], mark['clearing']), ('/sensors/mid360/scan', 'LaserScan', True, False))
            self.assertEqual((clear['topic'], clear['data_type'], clear['marking'], clear['clearing'], clear['sensor_frame']),
                             ('/sensors/mid360/points', 'PointCloud2', False, True, 'mid360_link'))   # only the MID-360's own rays clear
            self.assertEqual((mark['obstacle_max_range'], clear['raytrace_max_range']), (xs['obstacle_max_range'], xs['raytrace_max_range']))
            self.assertEqual(m.get('combination_method'), c['obstacle_layer'].get('combination_method'))
        others = {k for k in p if k != 'mid360_scan'}
        self.assertEqual(others, set(base))

    def test_layer_takes_the_saved_ranges(self):
        with tempfile.TemporaryDirectory() as d:
            r, p = self.build(d, 's', '', {'obstacle_max_range_m': 3.0, 'raytrace_max_range_m': 4.0})
        for name in ('local_costmap', 'global_costmap'):
            m = p[name][name]['ros__parameters']['mid360_layer']
            self.assertEqual((m['mid_mark']['obstacle_max_range'], m['mid_clear']['raytrace_max_range']), (3.0, 4.0))
        self.assertEqual(p['mid360_scan']['ros__parameters']['range_max'], p['xt32_scan']['ros__parameters']['range_max'])


if __name__ == '__main__':
    unittest.main()
