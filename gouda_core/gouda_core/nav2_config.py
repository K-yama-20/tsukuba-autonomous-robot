"""Nav2 settings of ND-10 (REV-061, DEC-121 / DEC-122). No ROS dependency.

The parameter file is built from the UPSTREAM template (installed share/nav2_bringup/params/nav2_params.yaml, the same as
design/research/upstream_jazzy/nav2_bringup/params/nav2_params.yaml for 1.3.13) with only these changes:
- the sections of the servers Gouda does not run are dropped (amcl, map_saver, waypoint_follower, route_server,
  collision_monitor (RQ-I072), docking_server, loopback_simulator); every value of the kept sections stays as in the template
  unless listed here;
- choices of DEC-122: controller FollowPath = Regulated Pure Pursuit (allow_reversing false), planner NavFn (template),
  behaviors spin / backup / wait, velocity_smoother kept, cmd_vel TwistStamped (PRM-12) for every cmd_vel publisher;
- interface names of the design: frames map / odom / base_link (IFD-18..20), odometry localization/odometry (IFD-25),
  obstacles from sensors/xt32/points (IFD-21) in the local VoxelLayer and the global ObstacleLayer, track_unknown_space true
  (RQ-I012), the SpeedFilter on the global costmap (IFD-14 / IFD-42, DEC-031), the navigate-through-poses BT built from the
  upstream BT with PRM-11 (RemovePassedGoals radius) and PRM-18 (outer RecoveryNode retries);
- vehicle values PRM-17, PRM-66..73 (speeds, accelerations, footprint, obstacle heights, inflation); the local VoxelLayer's
  z_resolution is derived so that its column reaches PRM-71 (the template's 16 x 0.05 m would cut it at 0.8 m);
- the velocity_smoother's reverse limit is PRM-78 (the wheelchair's reverse speed at full deflection, read from the
  gouda_motion_controller file where it is declared), not -PRM-66: reversing has a smaller deflection-to-speed slope (DEC-197),
  so Nav2 never commands a reverse faster than full deflection (DEC-198 plan A).
When a vehicle value is unresolved (the generated file has no value and no trial file is used), nothing is built and the
missing keys are returned: Nav2 is not started rather than run with a general value (intent.md:85, RQ-I076).
"""
from __future__ import annotations

import copy
import os
import xml.etree.ElementTree as ET
from typing import Optional

import yaml

from gouda_core import sensor_config as sc

# Interface names (not settings)
MAP_FRAME, ODOM_FRAME, BASE_FRAME = 'map', 'odom', 'base_link'
ODOM_TOPIC = 'localization/odometry'          # IFD-25
POINTS_TOPIC = '/sensors/xt32/points'          # IFD-21
# Absolute names: the SpeedFilter lives in the global_costmap namespace, where a relative name would become
# /global_costmap/... and miss the servers and the controller (found in the VM test of 2026-10-17).
SPEED_LIMIT_TOPIC = '/speed_limit'             # IFD-14
FILTER_INFO_TOPIC = '/costmap_filter_info'     # IFD-42
FILTER_MASK_TOPIC = '/speed_filter_mask'       # IFD-42
KEPT = ('bt_navigator', 'controller_server', 'local_costmap', 'global_costmap', 'planner_server', 'smoother_server', 'behavior_server',
        'velocity_smoother')
# Lifecycle order of upstream navigation_launch.py, without the servers Gouda does not run; plus the map servers (IFD-24, IFD-42).
LIFECYCLE_NODES = ['map_server', 'filter_mask_server', 'costmap_filter_info_server', 'controller_server', 'smoother_server', 'planner_server',
                   'behavior_server', 'velocity_smoother', 'bt_navigator']
BEHAVIORS = ['spin', 'backup', 'wait']
REQUIRED = {  # key in the generated files -> PRM (vehicle values that must be decided before Nav2 runs on the vehicle)
    ('gouda_nav2', 'max_linear_velocity_mps'): 'PRM-66', ('gouda_nav2', 'max_angular_velocity_radps'): 'PRM-67',
    ('gouda_nav2', 'linear_accel_limit_mps2'): 'PRM-68', ('gouda_nav2', 'angular_accel_limit_radps2'): 'PRM-73',
    ('gouda_nav2', 'footprint'): 'PRM-69', ('gouda_nav2', 'obstacle_min_height_m'): 'PRM-70', ('gouda_nav2', 'obstacle_max_height_m'): 'PRM-71',
    ('gouda_nav2', 'inflation_radius_m'): 'PRM-72', ('controller_server', 'controller_frequency'): 'PRM-17',
    ('controller_server', 'enable_stamped_cmd_vel'): 'PRM-12',
    ('bt_params', 'remove_passed_goals_radius_m'): 'PRM-11', ('bt_params', 'recovery_number_of_retries'): 'PRM-18',
    ('gouda_motion_controller', 'max_reverse_speed_mps'): 'PRM-78'}


def read_bt_params(params_dir: str, trial: bool) -> dict:
    out = {}
    for name in ['bt_params.yaml'] + (['bt_params.trial.yaml'] if trial else []):
        path = os.path.join(params_dir, name)
        if os.path.isfile(path):
            with open(path, encoding='utf-8') as f:
                out.update(yaml.safe_load(f) or {})
    return out


def read_values(params_dir: str, trial: bool) -> dict:
    """{(file, key): value} of every key Nav2 needs, from the generated files (trial files only when trial)."""
    files = {'gouda_nav2': sc.read_node_params(params_dir, 'gouda_nav2', trial),
             'controller_server': sc.read_node_params(params_dir, 'controller_server', trial),
             'bt_params': read_bt_params(params_dir, trial),
             'gouda_motion_controller': sc.read_node_params(params_dir, 'gouda_motion_controller', trial)}   # PRM-78 (DEC-198)
    return {(f, k): files[f].get(k) for (f, k) in REQUIRED}


def missing(values: dict) -> list:
    return [f'{k} ({REQUIRED[(f, k)]})' for (f, k) in REQUIRED if values.get((f, k)) is None]


def _observation(height_min: float, height_max: float) -> dict:
    return {'topic': POINTS_TOPIC, 'data_type': 'PointCloud2', 'clearing': True, 'marking': True,
            'min_obstacle_height': height_min, 'max_obstacle_height': height_max}


def nav2_parameters(template: dict, values: dict, bt_xml_path: str) -> dict:
    """The parameter dict for the Nav2 servers. `values` must be complete (see missing())."""
    v = {k: val for (_, k), val in values.items()}
    p = {k: copy.deepcopy(template[k]) for k in KEPT}
    vmax, wmax = float(v['max_linear_velocity_mps']), float(v['max_angular_velocity_radps'])
    vrev = float(v['max_reverse_speed_mps'])   # PRM-78: reverse at full deflection (DEC-197, DEC-198)
    acc, wacc = float(v['linear_accel_limit_mps2']), float(v['angular_accel_limit_radps2'])
    hmin, hmax = float(v['obstacle_min_height_m']), float(v['obstacle_max_height_m'])
    infl, footprint = float(v['inflation_radius_m']), str(v['footprint'])
    stamped = bool(v['enable_stamped_cmd_vel'])

    bt = p['bt_navigator']['ros__parameters']
    bt.update({'global_frame': MAP_FRAME, 'robot_base_frame': BASE_FRAME, 'odom_topic': ODOM_TOPIC,
               'default_nav_through_poses_bt_xml': bt_xml_path})

    cs = p['controller_server']['ros__parameters']
    follow = {'plugin': 'nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController',
              'desired_linear_vel': vmax, 'rotate_to_heading_angular_vel': wmax, 'allow_reversing': False}
    cs['FollowPath'] = follow
    cs.update({'controller_frequency': float(v['controller_frequency']), 'enable_stamped_cmd_vel': stamped, 'odom_topic': ODOM_TOPIC,
               'speed_limit_topic': SPEED_LIMIT_TOPIC})

    for name, frame in (('local_costmap', ODOM_FRAME), ('global_costmap', MAP_FRAME)):
        c = p[name][name]['ros__parameters']
        c.pop('robot_radius', None)
        c.update({'global_frame': frame, 'robot_base_frame': BASE_FRAME, 'footprint': footprint, 'track_unknown_space': True})
        c['inflation_layer']['inflation_radius'] = infl
    lc = p['local_costmap']['local_costmap']['ros__parameters']
    vl = lc['voxel_layer']
    vl.update({'observation_sources': 'points', 'max_obstacle_height': hmax, 'min_obstacle_height': hmin, 'points': _observation(hmin, hmax),
               # the voxel column (z_voxels x z_resolution above origin_z) must reach PRM-71, or points below it are dropped
               'z_resolution': (hmax - float(vl['origin_z'])) / int(vl['z_voxels'])})
    vl.pop('scan', None)
    gc = p['global_costmap']['global_costmap']['ros__parameters']
    ol = gc['obstacle_layer']
    ol.update({'observation_sources': 'points', 'max_obstacle_height': hmax, 'min_obstacle_height': hmin, 'points': _observation(hmin, hmax)})
    ol.pop('scan', None)
    gc['filters'] = ['speed_filter']
    gc['speed_filter'] = {'plugin': 'nav2_costmap_2d::SpeedFilter', 'enabled': True, 'filter_info_topic': FILTER_INFO_TOPIC,
                          'speed_limit_topic': SPEED_LIMIT_TOPIC}

    bs = p['behavior_server']['ros__parameters']
    bs['behavior_plugins'] = list(BEHAVIORS)
    for k in ('drive_on_heading', 'assisted_teleop'):
        bs.pop(k, None)
    bs.update({'max_rotational_vel': wmax, 'rotational_acc_lim': wacc, 'enable_stamped_cmd_vel': stamped})

    vs = p['velocity_smoother']['ros__parameters']
    vs.update({'max_velocity': [vmax, 0.0, wmax], 'min_velocity': [-vrev, 0.0, -wmax], 'max_accel': [acc, 0.0, wacc], 'max_decel': [-acc, 0.0, -wacc],
               'odom_topic': ODOM_TOPIC, 'enable_stamped_cmd_vel': stamped})

    p['map_server'] = {'ros__parameters': {'yaml_filename': ''}}             # set by ND-03 before the lifecycle start (TR-05)
    p['filter_mask_server'] = {'ros__parameters': {'yaml_filename': '', 'topic_name': FILTER_MASK_TOPIC}}
    p['costmap_filter_info_server'] = {'ros__parameters': {'type': 2, 'filter_info_topic': FILTER_INFO_TOPIC, 'mask_topic': FILTER_MASK_TOPIC,
                                                           'base': 0.0, 'multiplier': 0.0}}   # base / multiplier from the waypoint set (IFD-41) at TR-05
    p['lifecycle_manager_navigation'] = {'ros__parameters': {'autostart': False, 'node_names': list(LIFECYCLE_NODES)}}
    for sec in p.values():
        params = sec.get('ros__parameters') if 'ros__parameters' in sec else next(iter(sec.values()))['ros__parameters']
        params['use_sim_time'] = False
    return p


def build_bt(template_xml: str, values: dict) -> str:
    """The upstream navigate-through-poses BT with PRM-11 and PRM-18 inserted (no other change)."""
    v = {k: val for (_, k), val in values.items()}
    root = ET.fromstring(template_xml)
    outer = root.find("./BehaviorTree/RecoveryNode[@name='NavigateRecovery']")
    rpg = root.findall('.//RemovePassedGoals')
    if outer is None or len(rpg) != 1:
        raise ValueError('the upstream BT does not have the expected NavigateRecovery / RemovePassedGoals nodes')
    outer.set('number_of_retries', str(int(v['recovery_number_of_retries'])))
    rpg[0].set('radius', repr(float(v['remove_passed_goals_radius_m'])))
    return ET.tostring(root, encoding='unicode')


def write(params_dir: str, trial: bool, nav2_template_path: str, bt_template_path: str, out_dir: str) -> dict:
    """Build and write nav2_params.yaml and the BT under out_dir. Returns {'missing': [...], 'params': path or None, 'bt': path or None}."""
    values = read_values(params_dir, trial)
    miss = missing(values)
    if miss:
        return {'missing': miss, 'params': None, 'bt': None}
    os.makedirs(out_dir, exist_ok=True)
    with open(bt_template_path, encoding='utf-8') as f:
        bt = build_bt(f.read(), values)
    bt_path = os.path.join(out_dir, 'navigate_through_poses.xml')
    with open(bt_path, 'w', encoding='utf-8') as f:
        f.write('<!-- GENERATED by gouda_core.nav2_config from the upstream BT with PRM-11 / PRM-18 -->\n' + bt + '\n')
    with open(nav2_template_path, encoding='utf-8') as f:
        template = yaml.safe_load(f)
    params = nav2_parameters(template, values, bt_path)
    params_path = os.path.join(out_dir, 'nav2_params.yaml')
    with open(params_path, 'w', encoding='utf-8') as f:
        f.write('# GENERATED by gouda_core.nav2_config from the upstream nav2_bringup params/nav2_params.yaml and design/generated/params\n')
        yaml.safe_dump(params, f, sort_keys=False, allow_unicode=True)
    return {'missing': [], 'params': params_path, 'bt': bt_path}


def find_templates(bringup_share: Optional[str], bt_navigator_share: Optional[str]) -> tuple:
    p = os.path.join(bringup_share, 'params', 'nav2_params.yaml') if bringup_share else None
    b = os.path.join(bt_navigator_share, 'behavior_trees', 'navigate_through_poses_w_replanning_and_recovery.xml') if bt_navigator_share else None
    return (p if p and os.path.isfile(p) else None), (b if b and os.path.isfile(b) else None)
