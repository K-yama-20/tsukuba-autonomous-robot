from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    config_file = Path(
        get_package_share_directory("gouda_bringup")
    ) / "config" / "imu.yaml"

    imu_node = Node(
        package="adi_imu_tr_driver_ros2",
        executable="adis_rcv_bin_node",
        name="adi_rcv_bin_node",
        output="screen",
        parameters=[str(config_file)],
    )

    return LaunchDescription([
        imu_node,
    ])
