# The MIT License (MIT)
# Copyright (c) 2019 Techno Road Inc.
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import os

import launch
from ament_index_python.packages import get_package_share_directory
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():

    urdf = os.path.join(
        get_package_share_directory('adi_imu_tr_driver_ros2'),
        'urdf',
        'adis16470_breakout.urdf')

    rviz_config_dir = os.path.join(
        get_package_share_directory('adi_imu_tr_driver_ros2'),
        'rviz', 'imu.rviz')

    return launch.LaunchDescription([
        DeclareLaunchArgument(
            name="with_rviz",
            default_value="True",
            description="Launch Rviz2?"),
        DeclareLaunchArgument(
            name="device",
            default_value="/dev/ttyACM0",
            description="Device name"),
        DeclareLaunchArgument(
            name="parent_id",
            default_value="odom",
            description="Name of parent frame"),
        DeclareLaunchArgument(
            name="frame_id",
            default_value="imu",
            description="The frame name where the imu is mounted."),
        DeclareLaunchArgument(
            name="rate",
            default_value="100.0",
            description="Publish rate."),
        DeclareLaunchArgument(
            name="publish_tf",
            default_value="True",
            description="Publish the IMU attitude TF."),
        DeclareLaunchArgument(
            name="poll_period_us",
            default_value="500",
            description="Non-blocking serial drain period in microseconds."),
        Node(
            package='adi_imu_tr_driver_ros2',
            executable='adis_rcv_bin_node',
            output='screen',
            prefix=['stdbuf -o L'],
            parameters=[{
                '__log_level': 'INFO',
                'device': LaunchConfiguration("device"),
                'parent_id': LaunchConfiguration("parent_id"),
                'frame_id': LaunchConfiguration("frame_id"),
                'rate': LaunchConfiguration("rate"),
                'publish_tf': LaunchConfiguration("publish_tf"),
                'poll_period_us': LaunchConfiguration("poll_period_us"),
            }]),
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='log',
            parameters=[
                {'use_sim_time': False},
                {"robot_description": open(urdf, 'r').read()}],
        ),
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            arguments=['-d', rviz_config_dir],
            parameters=[{'use_sim_time': False}],
            output='log',
            condition=IfCondition(LaunchConfiguration("with_rviz")))
    ])
