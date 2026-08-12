import os
from datetime import datetime

from launch import LaunchDescription
from launch.actions import ExecuteProcess, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource

from ament_index_python.packages import get_package_share_directory


def generate_launch_description():

    # -----------------------------
    # rosbag 保存先
    # -----------------------------
    bag_root = os.path.expanduser(
        "~/jazzy_ws/data/rosbag"
    )

    os.makedirs(
        bag_root,
        exist_ok=True
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    bag_path = os.path.join(
        bag_root,
        f"{timestamp}_xt32"
    )

    # -----------------------------
    # Hesai driver
    # -----------------------------
    hesai_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory(
                    "hesai_ros_driver"
                ),
                "launch",
                "start.py",
            )
        )
    )

    # -----------------------------
    # rosbag recording
    # -----------------------------
    bag_record = ExecuteProcess(
        cmd=[
            "ros2",
            "bag",
            "record",
            "-o",
            bag_path,
            "/lidar_points",
        ],
        output="screen",
    )

    return LaunchDescription([
        hesai_launch,
        bag_record,
    ])
