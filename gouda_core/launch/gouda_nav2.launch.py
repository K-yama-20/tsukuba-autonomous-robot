"""Nav2 (ND-10) for Gouda: included by gouda_core.launch.py (the one start path gouda.sh; DEC-090). REV-061, DEC-121 / DEC-122.

The servers are started but NOT activated: lifecycle_manager_navigation has autostart false, and gouda_mode_manager (ND-03)
starts them at 自律走行開始 (TR-05) and resets them when autonomy ends (TR-11 / TR-12) (IFD-36). In 手動走行 and 事前地図作成
Nav2 stays inactive (no map->odom owner then; RQ-I004).
The parameter file and the BT are built by gouda_core.nav2_config from the upstream nav2_bringup / nav2_bt_navigator files and
the generated parameter files (trial files only in test scripts). When a vehicle value is unresolved, no Nav2 server is
started and the reason is logged; ND-03 records it and refuses 自律走行開始 (intent.md:85: no general values).
Wiring as upstream navigation_launch.py without collision_monitor (RQ-I072): controller_server and behavior_server publish
cmd_vel_nav; velocity_smoother reads cmd_vel_nav and publishes cmd_vel (IFD-15, TwistStamped PRM-12) for ND-11.
REV-185 (DEC-336): pointcloud_to_laserscan (ND-09) turns the XT-32 points into the base_link-band scan the costmaps read; without
the package Nav2 is not started.
REV-242 (DEC-454): the MID-360 path (ND-20 livox_ros_driver2, ND-21 mid360_scan, the mid360_layer of both costmaps) starts with Nav2
only when PRM-142 is true, <config_dir>/mid360.json (IFD-61, the vehicle PC's own file) has both addresses, the monitor's /config
(<config_dir>/sensor_config.json, IFD-26) has the whole MID-360 mounting (REV-266, DEC-485) and livox_ros_driver2 is installed;
otherwise it is not started, the reason is logged, and everything else is as before (XT-32 only).

The BT's recovery count is the one saved in the monitor's /config 「Nav2」 tab (config_dir/nav2_recovery.json, IFD-54) when it is
valid, else PRM-18 (REV-132, DEC-207 (a)); the count used and its source are logged and written to run_dir/nav2/recovery.json.
Arguments: params_dir, run_dir (<data_root>/run; the built files go to run_dir/nav2), config_dir (<data_root>/config),
trial (TEST SCRIPTS ONLY).
"""
import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _mid360_ready(config_dir, run_dir):
    """('', the written driver config path, note) when the vehicle PC's mid360.json has both addresses, /config has the whole MID-360
    mounting (REV-266) and livox_ros_driver2 is installed, else (the reason, None, note). note tells about mounting keys left in
    mid360.json (not read since REV-266). The driver config (with the PC's addresses) goes to run_dir/mid360 only, never to the repository."""
    from ament_index_python.packages import get_package_share_directory, PackageNotFoundError
    from gouda_core import mid360_config as m3
    reason, addresses, note = m3.launch_inputs(config_dir or None)
    if reason:
        return reason, None, note
    try:
        tpl = m3.find_template(get_package_share_directory(m3.DRIVER_PACKAGE))
    except PackageNotFoundError:
        return f'{m3.DRIVER_PACKAGE} is not installed or not loaded (setup.sh builds it; gouda.sh loads <workspace>_livox)', None, note
    if tpl is None:
        return f'{m3.DRIVER_PACKAGE} has no config/{m3.TEMPLATE_NAME}', None, note
    out = os.path.join(run_dir, 'mid360', m3.TEMPLATE_NAME)
    try:
        m3.write_driver_config(tpl, addresses, out)
    except (OSError, ValueError) as e:
        return f'the driver config could not be written ({e})', None, note
    return '', out, note


def _nodes(context, *args, **kwargs):
    from ament_index_python.packages import get_package_share_directory, PackageNotFoundError
    from gouda_core import nav2_config as nc
    from gouda_core import mid360_config as m3
    params_dir = LaunchConfiguration('params_dir').perform(context)
    run_dir = os.path.expanduser(LaunchConfiguration('run_dir').perform(context))
    trial = LaunchConfiguration('trial').perform(context).lower() in ('1', 'true', 'yes')
    config_dir = os.path.expanduser(LaunchConfiguration('config_dir').perform(context))
    try:
        tpl, bt = nc.find_templates(get_package_share_directory('nav2_bringup'), get_package_share_directory('nav2_bt_navigator'))
    except PackageNotFoundError:
        tpl, bt = None, None
    if tpl is None or bt is None:
        return [LogInfo(msg='[gouda_nav2] Nav2 is not installed (nav2_bringup / nav2_bt_navigator): Nav2 is not started (setup.sh installs it)')]
    try:   # REV-185 (DEC-336): the obstacle band is cut by pointcloud_to_laserscan; without it the costmaps would see nothing
        get_package_share_directory(nc.SCAN_PACKAGE)
    except PackageNotFoundError:
        return [LogInfo(msg=f'[gouda_nav2] {nc.SCAN_PACKAGE} is not installed: Nav2 is not started (no obstacle input; setup.sh installs it)')]
    mid360_ready, mid360_cfg, mid360_note = _mid360_ready(config_dir, run_dir)   # REV-242 (DEC-454): '' when the MID-360 path can start
    r = nc.write(params_dir, trial, tpl, bt, os.path.join(run_dir, 'nav2'), config_dir or None, mid360_ready=mid360_ready)
    if r['missing']:
        return [LogInfo(msg=f"[gouda_nav2] unresolved vehicle values {r['missing']}: Nav2 is not started (no general values: intent.md:85)")]
    m = r['mid360']
    mid360_log = LogInfo(msg=f"[gouda_nav2] MID-360 layer {'used' if m['used'] else 'NOT used (XT-32 only)'}: {m['reason']}"
                         + (f' ({mid360_note})' if mid360_note else ''))
    rec, inf = r['recovery'], r['inflate_around_unknown']
    recovery_log = LogInfo(msg=f"[gouda_nav2] BT recovery count {rec['value']} from {rec['source']}" + (f" ({rec['note']})" if rec['note'] else '')
                           + f"; inflate_around_unknown {inf['value']} from {inf['source']}" + (f" ({inf['note']})" if inf['note'] else ''))
    if r['tunables']['controller_use_mppi']['value']:   # REV-190 (DEC-400): the controller plugin must be there, or the servers would not configure
        try:
            get_package_share_directory(nc.MPPI_PACKAGE)
        except PackageNotFoundError:
            return [LogInfo(msg=f'[gouda_nav2] {nc.MPPI_PACKAGE} is not installed: Nav2 is not started (setup.sh installs it; PRM-130 false in the monitor selects RPP)')]
    p = [r['params']]
    out = 'screen'
    mid360_nodes = [] if not m['used'] else [
        # ND-20 (REV-242): the upstream driver, PointCloud2 in mid360_link, its one topic remapped to IFD-59
        Node(package=m3.DRIVER_PACKAGE, executable=m3.DRIVER_EXECUTABLE, name=m3.DRIVER_NODE, output=out,
             parameters=[m3.driver_parameters(mid360_cfg)], remappings=[(m3.DRIVER_TOPIC, m3.POINTS_TOPIC)]),
        # ND-21 (REV-242): the MID-360 points in the same base_link band as xt32_scan, for the mid360_layer of both costmaps (IFD-60)
        Node(package=nc.SCAN_PACKAGE, executable=nc.SCAN_EXECUTABLE, name=m3.SCAN_NODE, output=out, parameters=p,
             remappings=[('cloud_in', m3.POINTS_TOPIC), ('scan', m3.SCAN_TOPIC)]),
    ]
    return [mid360_log] + mid360_nodes + [
        recovery_log,
        Node(package='nav2_map_server', executable='map_server', name='map_server', output=out, parameters=p),
        Node(package='nav2_map_server', executable='map_server', name='filter_mask_server', output=out, parameters=p),
        Node(package='nav2_map_server', executable='costmap_filter_info_server', name='costmap_filter_info_server', output=out, parameters=p),
        # the human-drawn areas (REV-137, IFD-55): the keepout mask and its filter info (type 0)
        Node(package='nav2_map_server', executable='map_server', name='keepout_mask_server', output=out, parameters=p),
        Node(package='nav2_map_server', executable='costmap_filter_info_server', name='keepout_filter_info_server', output=out, parameters=p),
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
        # ND-09 (REV-185, DEC-336): the XT-32 points in the base_link band as a LaserScan for both costmaps (IFD-21 -> IFD-57). Not a
        # lifecycle node; it subscribes to the points only while the costmaps (active Nav2) subscribe to the scan.
        Node(package=nc.SCAN_PACKAGE, executable=nc.SCAN_EXECUTABLE, name=nc.SCAN_NODE, output=out, parameters=p,
             remappings=[('cloud_in', nc.POINTS_TOPIC), ('scan', nc.SCAN_TOPIC)]),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('params_dir', description='design/generated/params directory'),
        DeclareLaunchArgument('run_dir', description='<data_root>/run (the built Nav2 files go to run_dir/nav2)'),
        DeclareLaunchArgument('config_dir', default_value='', description='<data_root>/config (the monitor Nav2 tab file, IFD-54)'),
        DeclareLaunchArgument('trial', default_value='false', description='TEST SCRIPTS ONLY: also load the trial values'),
        OpaqueFunction(function=_nodes),
    ])
