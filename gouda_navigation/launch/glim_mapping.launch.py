"""CPU GLIM mapping with private native TF and a local-odometry-only bridge."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def validate_and_start(context):
    from gouda_navigation.mapping import load_mapping_settings, static_tf_args, validate_mapping_settings
    settings = load_mapping_settings(LaunchConfiguration('settings_file').perform(context))
    errors = validate_mapping_settings(settings, require_ready=True)
    if errors:
        raise ValueError('; '.join(errors))
    config_path = LaunchConfiguration('config_path').perform(context)
    dump_path = LaunchConfiguration('dump_path').perform(context)
    use_sim_time = LaunchConfiguration('use_sim_time').perform(context).lower() == 'true'
    private_tf = [('/tf', '/glim_internal/tf'), ('/tf_static', '/glim_internal/tf_static')]
    return [
        Node(package='tf2_ros', executable='static_transform_publisher', name='glim_calibrated_imu_lidar_tf',
             arguments=static_tf_args(settings), parameters=[{'use_sim_time': use_sim_time}],
             remappings=private_tf, output='screen'),
        Node(package='glim_ros', executable='glim_rosnode', name='glim_ros', output='screen',
             parameters=[{'config_path': config_path, 'dump_path': dump_path, 'use_sim_time': use_sim_time}], remappings=private_tf),
        Node(package='gouda_navigation', executable='glim_odom_tf', output='screen',
             parameters=[{'odom_frame': 'odom_lidar', 'base_frame': settings['lidar_frame'],
                          'imu_frame': settings['imu_frame'], 'lidar_topic': settings['lidar_topic'],
                          'imu_topic': settings['imu_topic'], 'point_time_field': settings['point_time_field'],
                          'point_time_datatype': settings['point_time_datatype'], 'use_sim_time': use_sim_time}]),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('settings_file', default_value=''),
        DeclareLaunchArgument('config_path', default_value=''),
        DeclareLaunchArgument('dump_path', default_value=''),
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        OpaqueFunction(function=validate_and_start),
    ])
