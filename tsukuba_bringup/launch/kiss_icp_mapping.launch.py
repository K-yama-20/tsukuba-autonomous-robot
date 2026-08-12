from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource

from ament_index_python.packages import get_package_share_directory

import os


def generate_launch_description():

	hesai_share = get_package_share_directory("hesai_ros_driver")
	hesai_launch = os.path.join(
		hesai_share,
		"launch",
		"start.py"
	)

	hesai_driver = IncludeLaunchDescription(
		PythonLaunchDescriptionSource(hesai_launch)
	)

	kiss_icp_share = get_package_share_directory("kiss_icp")
	kiss_icp_launch = os.path.join(
		kiss_icp_share,
		"launch",
		"odometry.launch.py"
	)

	kiss_icp = IncludeLaunchDescription(
		PythonLaunchDescriptionSource(kiss_icp_launch),
		launch_arguments={
			"topic": "/lidar_points",
			"visualize": "true",
		}.items(),
	)

	return LaunchDescription([
	hesai_driver,
	kiss_icp,
])
