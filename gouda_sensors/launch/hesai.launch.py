from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from gouda_sensors.hesai_config import checked_config


def start(context):
    path = LaunchConfiguration('config').perform(context)
    mode = LaunchConfiguration('mode').perform(context)
    checked_config(path, mode)
    replay_clock = mode == 'packet_replay'
    return [Node(package='hesai_ros_driver', executable='hesai_ros_driver_node',
                 parameters=[{'config_path': path, 'use_sim_time': replay_clock}], output='screen'),
            Node(package='gouda_sensors', executable='cloud_monitor',
                 parameters=[{'use_sim_time': replay_clock}], output='screen')]


def generate_launch_description():
    return LaunchDescription([DeclareLaunchArgument('config'),
        DeclareLaunchArgument('mode', default_value='pcap'), OpaqueFunction(function=start)])
