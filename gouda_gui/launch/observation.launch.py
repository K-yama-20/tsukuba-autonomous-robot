"""Stage 3 only. Isolated ROS domain; no planner, follower, or vehicle bridge."""
from pathlib import Path
from gouda_gui.paths import config_dir, data_dir
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable, RegisterEventHandler, EmitEvent, OpaqueFunction
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from ament_index_python.packages import get_package_share_directory


def validate_mode(context):
    replay=LaunchConfiguration('replay').perform(context)
    sensors=LaunchConfiguration('sensors').perform(context)
    backend=LaunchConfiguration('backend').perform(context)
    if replay not in ('true','false') or sensors not in ('true','false'):
        raise ValueError('replay/sensors must be true or false')
    if backend not in ('kiss_icp', 'glim_imu'):
        raise ValueError('backend must be kiss_icp or glim_imu')
    if replay=='true' and sensors=='true':
        raise ValueError('Do not mix live sensors with bag replay')
    if sensors=='true':
        from gouda_sensors.hesai_config import checked_config
        checked_config(LaunchConfiguration('hesai_config').perform(context),'hardware')
    return []


def generate_launch_description():
    from gouda_navigation.mapping import load_mapping_settings
    mapping_settings = load_mapping_settings()
    backend_default = mapping_settings.get('backend', 'kiss_icp')
    scan_offset_default = mapping_settings.get('lidar_clock_offset_sec') if backend_default == 'glim_imu' else 0.0
    if scan_offset_default is None:
        scan_offset_default = 0.0
    replay = ParameterValue(LaunchConfiguration('replay'), value_type=bool)
    gui = Node(package='gouda_gui', executable='mission_control', output='screen', parameters=[{
        'mode': PythonExpression(["'replay' if '", LaunchConfiguration('replay'), "' == 'true' else 'live'"]),
        'observation_only': True, 'use_sim_time': replay,
        'mapping_backend': LaunchConfiguration('backend'),
        'port': ParameterValue(LaunchConfiguration('port'), value_type=int),
        'map_directory': str(data_dir() / 'maps_sensor_slam')}], sigterm_timeout=110)
    return LaunchDescription([
        SetEnvironmentVariable('ROS_DOMAIN_ID', '99'),
        SetEnvironmentVariable('ROS_AUTOMATIC_DISCOVERY_RANGE', 'LOCALHOST'),
        SetEnvironmentVariable('FASTRTPS_DEFAULT_PROFILES_FILE', str(Path(get_package_share_directory('gouda_gui'))/'config/fastdds_observation.xml')),
        SetEnvironmentVariable('FASTDDS_DEFAULT_PROFILES_FILE', str(Path(get_package_share_directory('gouda_gui'))/'config/fastdds_observation.xml')),
        DeclareLaunchArgument('replay', default_value='false'),
        DeclareLaunchArgument('port', default_value='8765'),
        DeclareLaunchArgument('sensors', default_value='false'),
        DeclareLaunchArgument('backend', default_value=backend_default),
        DeclareLaunchArgument('lidar_timestamp_offset_sec', default_value=str(scan_offset_default)),
        DeclareLaunchArgument('imu_device',default_value=''),
        DeclareLaunchArgument('hesai_config', default_value=str(config_dir()/'hesai.yaml')),
        OpaqueFunction(function=validate_mode),
        Node(package='hesai_ros_driver', executable='hesai_ros_driver_node',
             parameters=[{'config_path': LaunchConfiguration('hesai_config')}],
             condition=IfCondition(LaunchConfiguration('sensors')), output='screen'),
        Node(package='adi_imu_tr_driver_ros2', executable='adis_rcv_bin_node',
             parameters=[{'device': LaunchConfiguration('imu_device'),
                          'frame_id': 'imu_link', 'parent_id': 'base_link', 'rate': 100., 'publish_tf': False}],
             condition=IfCondition(LaunchConfiguration('sensors')), output='screen'),
        Node(package='kiss_icp', executable='kiss_icp_node', output='screen',
             condition=IfCondition(PythonExpression(["'", LaunchConfiguration('backend'), "' == 'kiss_icp'"])),
             remappings=[('pointcloud_topic', '/lidar_points')], parameters=[{
                 'use_sim_time': replay, 'base_frame': 'hesai_lidar', 'lidar_odom_frame': 'odom_lidar',
                 'invert_odom_tf': False, 'publish_odom_tf': True, 'publish_debug_clouds': True,
                 'data.deskew': False, 'data.min_range': .4, 'data.max_range': 30.,
                 'mapping.voxel_size': .3, 'registration.max_num_threads': 2}]),
        Node(package='gouda_sensors', executable='sensor_plane_scan', parameters=[{
            'use_sim_time': replay,
            'lidar_timestamp_offset_sec': ParameterValue(LaunchConfiguration('lidar_timestamp_offset_sec'), value_type=float)}]),
        Node(package='gouda_sensors', executable='cloud_monitor', parameters=[{'use_sim_time': replay}]),
        RegisterEventHandler(OnProcessExit(target_action=gui, on_exit=[EmitEvent(event=Shutdown(reason='Observation GUI exited'))])),
        gui,
    ])
