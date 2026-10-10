"""Launch of the common Gouda core nodes (gouda_mode_manager, gouda_recorder, gouda_monitor, gouda_map_creator).

Arguments:
  params_dir  directory of the generated parameter files (design/generated/params). Values are declared once in
              design/model.yaml and generated; nothing is hard-coded here (RQ-I076, DR-15). A node whose generated file
              does not exist yet (no parameter declared for it) is started without a parameter file.
  data_root   PRM-25: directory under which records/ (recorder sessions), state/ (persisted mode record), config/ (/config)
              and run/ (monitor URL) are kept.
  monitor_port PRM-26: TCP port of the gouda_monitor page on 127.0.0.1; 0 lets the OS choose (URL in <data_root>/run/monitor.url).
  serial_port stage 5-5: serial device of the ESP32 for vehicle_bridge (operational value; pty path in stub tests).
  trial       true loads <node>.trial.yaml (software trial values of unresolved parameters) after <node>.yaml. For stub and
              software tests only; never on the vehicle. Default false.
Mode-dependent nodes (mapping, autonomy) are activated by later stages through lifecycle transitions (IFD-36), not here.
"""
import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
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

    return [
        Node(package='gouda_core', executable='gouda_mode_manager', name='gouda_mode_manager', output='screen',
             parameters=params('gouda_mode_manager', {'state_root': os.path.join(data_root, 'state'), 'data_root': data_root})),
        Node(package='gouda_core', executable='gouda_recorder', name='gouda_recorder', output='screen',
             parameters=params('gouda_recorder', {'record_root': os.path.join(data_root, 'records')})),
        Node(package='gouda_core', executable='gouda_map_creator', name='gouda_map_creator', output='screen',
             parameters=params('gouda_map_creator', {'data_root': data_root})),
        Node(package='gouda_core', executable='gouda_monitor', name='gouda_monitor', output='screen',
             parameters=params('gouda_monitor', {'data_root': data_root, 'monitor_port': int(LaunchConfiguration('monitor_port').perform(context))})),
        # Stage 5-5 vehicle output (ND-11, ND-12): lifecycle nodes, started UNCONFIGURED. They are configured/activated by
        # lifecycle transitions (IFD-36) — by the mode manager in stage 5-6/5-7, or with `ros2 lifecycle set` in stub tests.
        # Nothing drives the vehicle until both are active; the firmware stays neutral meanwhile (PRM-13).
        LifecycleNode(package='gouda_core', executable='gouda_motion_controller', name='gouda_motion_controller', namespace='', output='screen',
                      parameters=params('gouda_motion_controller', {})),
        LifecycleNode(package='gouda_core', executable='vehicle_bridge', name='vehicle_bridge', namespace='', output='screen',
                      parameters=params('vehicle_bridge', {'serial_port': LaunchConfiguration('serial_port').perform(context), 'params_dir': params_dir, 'trial': trial})),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('params_dir', description='design/generated/params directory (generated from design/model.yaml)'),
        DeclareLaunchArgument('data_root', description='PRM-25 data root: <data_root>/records, state, config, run'),
        DeclareLaunchArgument('monitor_port', default_value='0', description='PRM-26 monitor page port on 127.0.0.1; 0 = OS-chosen'),
        DeclareLaunchArgument('trial', default_value='false', description='load <node>.trial.yaml software trial values (stub tests only, never on the vehicle)'),
        DeclareLaunchArgument('serial_port', default_value='', description='vehicle_bridge serial port to the ESP32 (operational value; a pty path in stub tests). Empty: the bridge refuses to configure'),
        OpaqueFunction(function=_nodes),
    ])
