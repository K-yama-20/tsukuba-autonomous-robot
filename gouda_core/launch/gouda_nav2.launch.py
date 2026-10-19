"""Nav2 (ND-10) for Gouda: included by gouda_core.launch.py (the one start path gouda.sh; DEC-090). REV-061, DEC-121 / DEC-122.

The servers are started but NOT activated: lifecycle_manager_navigation has autostart false, and gouda_mode_manager (ND-03)
starts them at 自律走行開始 (TR-05) and resets them when autonomy ends (TR-11 / TR-12) (IFD-36). In 手動走行 and 事前地図作成
Nav2 stays inactive (no map->odom owner then; RQ-I004).
The parameter file and the BT are built by gouda_core.nav2_config from the upstream nav2_bringup / nav2_bt_navigator files and
the generated parameter files (trial files only in test scripts). When a vehicle value is unresolved, no Nav2 server is
started and the reason is logged; ND-03 records it and refuses 自律走行開始 (intent.md:85: no general values).
Wiring as upstream navigation_launch.py without collision_monitor (RQ-I072): controller_server and behavior_server publish
cmd_vel_nav; velocity_smoother reads cmd_vel_nav and publishes cmd_vel (IFD-15, TwistStamped PRM-12) for ND-11.

Arguments: params_dir, run_dir (<data_root>/run; the built files go to run_dir/nav2), trial (TEST SCRIPTS ONLY).
"""
import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _nodes(context, *args, **kwargs):
    from ament_index_python.packages import get_package_share_directory, PackageNotFoundError
    from gouda_core import nav2_config as nc
    params_dir = LaunchConfiguration('params_dir').perform(context)
    run_dir = os.path.expanduser(LaunchConfiguration('run_dir').perform(context))
    trial = LaunchConfiguration('trial').perform(context).lower() in ('1', 'true', 'yes')
    try:
        tpl, bt = nc.find_templates(get_package_share_directory('nav2_bringup'), get_package_share_directory('nav2_bt_navigator'))
    except PackageNotFoundError:
        tpl, bt = None, None
    if tpl is None or bt is None:
        return [LogInfo(msg='[gouda_nav2] Nav2 is not installed (nav2_bringup / nav2_bt_navigator): Nav2 is not started (setup.sh installs it)')]
    r = nc.write(params_dir, trial, tpl, bt, os.path.join(run_dir, 'nav2'))
    if r['missing']:
        return [LogInfo(msg=f"[gouda_nav2] unresolved vehicle values {r['missing']}: Nav2 is not started (no general values: intent.md:85)")]
    p = [r['params']]
    out = 'screen'
    return [
        Node(package='nav2_map_server', executable='map_server', name='map_server', output=out, parameters=p),
        Node(package='nav2_map_server', executable='map_server', name='filter_mask_server', output=out, parameters=p),
        Node(package='nav2_map_server', executable='costmap_filter_info_server', name='costmap_filter_info_server', output=out, parameters=p),
        Node(package='nav2_controller', executable='controller_server', name='controller_server', output=out, parameters=p,
             remappings=[('cmd_vel', 'cmd_vel_nav')]),
        Node(package='nav2_smoother', executable='smoother_server', name='smoother_server', output=out, parameters=p),
        Node(package='nav2_planner', executable='planner_server', name='planner_server', output=out, parameters=p),
        Node(package='nav2_behaviors', executable='behavior_server', name='behavior_server', output=out, parameters=p,
             remappings=[('cmd_vel', 'cmd_vel_nav')]),
        Node(package='nav2_bt_navigator', executable='bt_navigator', name='bt_navigator', output=out, parameters=p),
        Node(package='nav2_velocity_smoother', executable='velocity_smoother', name='velocity_smoother', output=out, parameters=p,
             remappings=[('cmd_vel', 'cmd_vel_nav'), ('cmd_vel_smoothed', 'cmd_vel')]),
        Node(package='nav2_lifecycle_manager', executable='lifecycle_manager', name='lifecycle_manager_navigation', output=out, parameters=p),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('params_dir', description='design/generated/params directory'),
        DeclareLaunchArgument('run_dir', description='<data_root>/run (the built Nav2 files go to run_dir/nav2)'),
        DeclareLaunchArgument('trial', default_value='false', description='TEST SCRIPTS ONLY: also load the trial values'),
        OpaqueFunction(function=_nodes),
    ])
