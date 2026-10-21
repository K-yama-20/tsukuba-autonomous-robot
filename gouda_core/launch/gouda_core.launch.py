"""Launch of everything gouda.sh starts (the one start path, DEC-090 / DEC-091): gouda_mode_manager, gouda_recorder,
gouda_monitor, gouda_map_creator, gouda_static_tf, gouda_global_localization (ND-07, lifecycle), the vehicle-output lifecycle nodes, the sensor drivers under
gouda_sensor_supervisor, and Nav2 (gouda_nav2.launch.py, started inactive).

Arguments (gouda.sh passes exactly params_dir and data_root):
  params_dir  directory of the generated parameter files (design/generated/params). Every setting, including the monitor
              port (PRM-26) and the ESP32 serial device (PRM-61), is declared once in design/model.yaml and generated;
              nothing is hard-coded here (RQ-I076, DR-15).
  data_root   PRM-25: records/ (recorder sessions), state/ (persisted mode record), config/ (/config), run/ (monitor URL,
              generated driver config, sensor_devices.json).
  trial       TEST SCRIPTS ONLY (gouda_core/test): also loads <node>.trial.yaml (software trial values of unresolved
              parameters). gouda.sh never sets it; never on the vehicle. Default false.
Mode-dependent nodes (mapping, autonomy) are activated through lifecycle transitions (IFD-36), not here.
"""
import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node, LifecycleNode


def _nodes(context, *args, **kwargs):
    params_dir = LaunchConfiguration('params_dir').perform(context)
    data_root = os.path.expanduser(LaunchConfiguration('data_root').perform(context))
    trial = LaunchConfiguration('trial').perform(context).lower() in ('1', 'true', 'yes')

    def params(node_name, extra):
        # Use the generated file only when it declares at least one value for this node; a file whose
        # ros__parameters is empty (all values still tbd) is skipped rather than passed as an empty map.
        import yaml
        def usable(path):
            if not os.path.isfile(path): return False
            try:
                doc = yaml.safe_load(open(path, encoding='utf-8')) or {}
                return bool((doc.get(node_name) or {}).get('ros__parameters'))
            except Exception:
                return False
        files = [f for f in [os.path.join(params_dir, f'{node_name}.yaml')] if usable(f)]
        if trial:
            files += [f for f in [os.path.join(params_dir, f'{node_name}.trial.yaml')] if usable(f)]
        return files + [extra]

    # ND-14 / ND-15 / ND-19 under ND-18: always started; a missing device is waited for, not an error (DEC-088, DEC-090)
    sensors = [IncludeLaunchDescription(PythonLaunchDescriptionSource(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gouda_sensors.launch.py')),
                                        launch_arguments={'params_dir': params_dir, 'run_dir': os.path.join(data_root, 'run'), 'config_dir': os.path.join(data_root, 'config'),
                                                          'trial': 'true' if trial else 'false'}.items())]
    # ND-10 Nav2: started inactive; ND-03 activates it at TR-05 (REV-061). Not started while a vehicle value is unresolved.
    nav2 = [IncludeLaunchDescription(PythonLaunchDescriptionSource(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gouda_nav2.launch.py')),
                                     launch_arguments={'params_dir': params_dir, 'run_dir': os.path.join(data_root, 'run'), 'trial': 'true' if trial else 'false'}.items())]
    return sensors + nav2 + [
        Node(package='gouda_core', executable='gouda_mode_manager', name='gouda_mode_manager', output='screen',
             parameters=params('gouda_mode_manager', {'state_root': os.path.join(data_root, 'state'), 'data_root': data_root,
                                                      'params_dir': params_dir, 'trial': trial})),   # params_dir / trial: Nav2 readiness (nav2_config)
        Node(package='gouda_core', executable='gouda_recorder', name='gouda_recorder', output='screen',
             parameters=params('gouda_recorder', {'record_root': os.path.join(data_root, 'records')})),
        Node(package='gouda_core', executable='gouda_map_creator', name='gouda_map_creator', output='screen',
             parameters=params('gouda_map_creator', {'data_root': data_root})),
        Node(package='gouda_core', executable='gouda_monitor', name='gouda_monitor', output='screen',
             parameters=params('gouda_monitor', {'data_root': data_root})),   # monitor_port: PRM-26 in the generated file
        # ND-08 relay: localization/odometry from GLIM's odometry-only TF (publishes only while ND-03 runs GLIM in autonomy)
        Node(package='gouda_core', executable='gouda_local_odometry', name='gouda_local_odometry', output='screen'),
        # ND-07 (trial A3, REV-128): lifecycle node, started UNCONFIGURED; ND-03 sets map_directory and configures / activates it at
        # 自律走行開始 (TR-05) and deactivates / cleans it up at the end (TR-11 / TR-12). Its A3 parts run as its child launch.
        LifecycleNode(package='gouda_core', executable='gouda_global_localization', name='gouda_global_localization', namespace='', output='screen',
                      parameters=params('gouda_global_localization', {'data_root': data_root})),
        # ND-13: the only static TF publisher (base_footprint -> base_link -> sensors and GNSS antennas, from /config)
        Node(package='gouda_core', executable='gouda_static_tf', name='gouda_static_tf', output='screen',
             parameters=params('gouda_static_tf', {'data_root': data_root})),   # base_link_z_m: PRM-05 in the generated file
        # Stage 5-5 vehicle output (ND-11, ND-12): lifecycle nodes, started UNCONFIGURED. They are configured/activated by
        # lifecycle transitions (IFD-36) — by the mode manager in stage 5-6/5-7, or with `ros2 lifecycle set` in stub tests.
        # Nothing drives the vehicle until both are active; the firmware stays neutral meanwhile (PRM-13).
        LifecycleNode(package='gouda_core', executable='gouda_motion_controller', name='gouda_motion_controller', namespace='', output='screen',
                      parameters=params('gouda_motion_controller', {})),
        LifecycleNode(package='gouda_core', executable='vehicle_bridge', name='vehicle_bridge', namespace='', output='screen',
                      parameters=params('vehicle_bridge', {'params_dir': params_dir, 'trial': trial})),   # serial_port: PRM-61 in the generated file
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('params_dir', description='design/generated/params directory (generated from design/model.yaml)'),
        DeclareLaunchArgument('data_root', description='PRM-25 data root: <data_root>/records, state, config, run'),
        DeclareLaunchArgument('trial', default_value='false', description='TEST SCRIPTS ONLY: also load <node>.trial.yaml software trial values (gouda.sh never sets it)'),
        OpaqueFunction(function=_nodes),
    ])
