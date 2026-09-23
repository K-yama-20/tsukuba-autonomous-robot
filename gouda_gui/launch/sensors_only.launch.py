"""Keep hardware receivers alive across GUI/SLAM restarts. No vehicle outputs."""
from pathlib import Path
from gouda_gui.paths import config_dir, data_dir
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
from gouda_sensors.hesai_config import checked_config


def start(context):
    config=LaunchConfiguration('hesai_config').perform(context)
    checked_config(config,'hardware')
    return [
        Node(package='hesai_ros_driver',executable='hesai_ros_driver_node',
             parameters=[{'config_path':config}],output='screen'),
        Node(package='adi_imu_tr_driver_ros2',executable='adis_rcv_bin_node',
             parameters=[{'device':LaunchConfiguration('imu_device'),
                 'frame_id':'imu_link','parent_id':'base_link','rate':100.,'publish_tf':False}],output='screen'),
    ]


def generate_launch_description():
    profile=str(Path(get_package_share_directory('gouda_gui'))/'config/fastdds_observation.xml')
    return LaunchDescription([
        SetEnvironmentVariable('ROS_DOMAIN_ID','99'),
        SetEnvironmentVariable('ROS_AUTOMATIC_DISCOVERY_RANGE','LOCALHOST'),
        SetEnvironmentVariable('FASTRTPS_DEFAULT_PROFILES_FILE',profile),
        SetEnvironmentVariable('FASTDDS_DEFAULT_PROFILES_FILE',profile),
        DeclareLaunchArgument('imu_device',default_value=''),
        DeclareLaunchArgument('hesai_config',default_value=str(config_dir()/'hesai.yaml')),
        OpaqueFunction(function=start),
    ])
