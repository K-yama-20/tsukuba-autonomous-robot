from pathlib import Path

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _setup(context):
    config = LaunchConfiguration("config").perform(context)
    path = Path(config)
    if not path.is_absolute() or not path.is_file():
        raise RuntimeError(f"config must be an existing absolute path: {config}")
    if "REQUIRED" in path.read_text(encoding="utf-8"):
        raise RuntimeError(f"config still contains REQUIRED: {config}")
    return [
        Node(
            package="emc270_joystick_driver",
            executable="emc270_joystick_driver_node",
            name="emc270_joystick_driver",
            output="screen",
            parameters=[config],
        )
    ]


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "config",
                description="Absolute path to a completed driver YAML",
            ),
            OpaqueFunction(function=_setup),
        ]
    )
