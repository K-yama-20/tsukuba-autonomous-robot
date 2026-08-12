from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

import os


def generate_launch_description():

	tsukuba_bringup_share = get_package_share_directory("tsukuba_bringup")

	# getting a config path
	kiss_icp_config = os.path.join(
		tsukuba_bringup_share,
		"config",
		"kiss_icp_xt32.yaml"
	)

	hesai_config = os.path.join(
		tsukuba_bringup_share,
		"config",
		"hesai_xt32.yaml"
	)

#	rviz_config = os.path.join(
#		tsukuba_bringup_share,
#		"rviz",
#		"mapping.rviz"
#	) 

	# getting a hesai launch path
	hesai_share = get_package_share_directory("hesai_ros_driver")
	hesai_launch = os.path.join(
		hesai_share,
		"launch",
		"start.py"
	)

	# conduct hesai_driver
	hesai_driver = IncludeLaunchDescription(
		PythonLaunchDescriptionSource(hesai_launch),
		launch_arguments={
			"config_path": hesai_config,
		}.items(),
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
			"config_file": kiss_icp_config,
			"base_frame": "hesai_lidar",
			"visualize": "true",
		}.items(),
	)

#	rviz = Node(
#		package="rviz2",
#		executable="rviz2",
#		arguments=[
#			"-d",
#			"rviz_config
#		],
#		output="screen",
#	)

	return LaunchDescription([
	hesai_driver,
	kiss_icp,
#	rviz,
])
