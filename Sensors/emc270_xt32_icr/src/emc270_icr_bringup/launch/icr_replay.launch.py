import math
import os

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, EmitEvent, ExecuteProcess,
                            OpaqueFunction, RegisterEventHandler, TimerAction)
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _contains_required(value):
    if isinstance(value, str):
        return "REQUIRED" in value
    if isinstance(value, dict):
        return any(_contains_required(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_required(item) for item in value)
    return False


def _load_fixture(path):
    if not os.path.isabs(path) or not os.path.isfile(path):
        raise RuntimeError(f"fixture_config must be an existing absolute path: {path}")
    with open(path, encoding="utf-8") as stream:
        fixture = yaml.safe_load(stream)
    if not isinstance(fixture, dict) or _contains_required(fixture):
        raise RuntimeError(f"fixture_config still contains REQUIRED placeholders: {path}")
    return fixture


def _validate_inspection(inspection):
    horizontal = inspection.get("horizontal_origin_tolerance_m")
    angular = inspection.get("axis_angle_tolerance_rad")
    if not isinstance(horizontal, (int, float)) or not math.isfinite(horizontal) or \
            not 0.0 <= horizontal <= 0.002:
        raise RuntimeError("Fixture horizontal tolerance must be within 0..0.002 m")
    if not isinstance(angular, (int, float)) or not math.isfinite(angular) or \
            not 0.0 <= angular <= 0.003491:
        raise RuntimeError("Fixture axis-angle tolerance must be within 0..0.003491 rad")


def _six_dof_node(parent, child, transform):
    xyz = transform["translation_m"]
    rpy = transform["rotation_rpy_rad"]
    if len(xyz) != 3 or len(rpy) != 3 or not all(
            isinstance(value, (int, float)) and math.isfinite(value)
            for value in xyz + rpy):
        raise RuntimeError(f"Invalid numeric transform for {parent}->{child}")
    if any(abs(float(value)) > math.pi for value in rpy):
        raise RuntimeError(f"RPY for {parent}->{child} must be radians in [-pi, pi]")
    return Node(
        package="tf2_ros", executable="static_transform_publisher",
        name=f"static_{parent}_to_{child}",
        arguments=[
            "--x", str(xyz[0]), "--y", str(xyz[1]), "--z", str(xyz[2]),
            "--roll", str(rpy[0]), "--pitch", str(rpy[1]), "--yaw", str(rpy[2]),
            "--frame-id", parent, "--child-frame-id", child,
        ])


def _launch_setup(context):
    share = get_package_share_directory("emc270_icr_bringup")
    fixture = _load_fixture(LaunchConfiguration("fixture_config").perform(context))
    bag = LaunchConfiguration("bag").perform(context)
    if not os.path.isabs(bag) or not os.path.exists(bag):
        raise RuntimeError(f"bag must be an existing absolute path: {bag}")
    output_bag = LaunchConfiguration("output_bag").perform(context)
    if output_bag and (not os.path.isabs(output_bag) or os.path.exists(output_bag)):
        raise RuntimeError(
            f"output_bag must be an unused absolute path (or empty): {output_bag}")
    frames = fixture["frames"]
    inspection = fixture["inspection"]
    _validate_inspection(inspection)
    if math.sqrt(sum(float(value) ** 2
                     for value in frames["xt32_to_native"]["translation_m"])) > 1.0e-6:
        raise RuntimeError("xt32_link and hesai_lidar_native must share one geometric origin")
    imu = frames["xt32_to_imu"]
    actions = [
        _six_dof_node("xt32_link", "hesai_lidar_native", frames["xt32_to_native"]),
        _six_dof_node("xt32_link", "imu_link", imu),
        Node(
            package="kiss_icp", executable="kiss_icp_node", name="kiss_icp_node",
            output="screen", remappings=[("pointcloud_topic", "/lidar_points")],
            parameters=[
                os.path.join(share, "config", "kiss_icp.yaml"),
                {
                    "base_frame": "xt32_link", "lidar_odom_frame": "odom_lidar",
                    "publish_odom_tf": False, "invert_odom_tf": True,
                    "publish_debug_clouds": False, "use_sim_time": True,
                },
            ]),
        Node(
            package="emc270_icr_estimator", executable="icr_estimator_node",
            name="emc270_icr_estimator", output="screen",
            remappings=[("/diagnostics", "/icr/diagnostics")],
            parameters=[
                os.path.join(share, "config", "estimator.yaml"),
                {
                    "fixture.imu_x_m": float(imu["translation_m"][0]),
                    "fixture.imu_y_m": float(imu["translation_m"][1]),
                    "fixture.imu_roll_rad": float(imu["rotation_rpy_rad"][0]),
                    "fixture.imu_pitch_rad": float(imu["rotation_rpy_rad"][1]),
                    "fixture.imu_yaw_rad": float(imu["rotation_rpy_rad"][2]),
                    "fixture.xy_sigma_m": float(
                        inspection["horizontal_origin_tolerance_m"]),
                    "fixture.axis_angle_sigma_rad": float(
                        inspection["axis_angle_tolerance_rad"]),
                    "use_sim_time": True,
                },
            ]),
    ]
    if output_bag:
        actions.append(ExecuteProcess(
            cmd=[
                "ros2", "bag", "record", "--storage", "mcap", "--output", output_bag,
                "/kiss/odometry", "/icr/fast", "/icr/smoothed",
                "/icr/diagnostics", "/tf",
            ],
            output="screen"))
    play = ExecuteProcess(
        cmd=[
            "ros2", "bag", "play", bag, "--clock", "1000.0", "--topics",
            "/lidar_points", "/imu/telemetry",
        ],
        output="screen")
    actions.extend([
        TimerAction(period=2.0, actions=[play]),
        RegisterEventHandler(OnProcessExit(
            target_action=play,
            on_exit=[EmitEvent(event=Shutdown(reason="Replay completed"))])),
    ])
    return actions


def generate_launch_description():
    share = get_package_share_directory("emc270_icr_bringup")
    return LaunchDescription([
        DeclareLaunchArgument("bag"),
        DeclareLaunchArgument("output_bag", default_value=""),
        DeclareLaunchArgument(
            "fixture_config",
            default_value=os.path.join(share, "config", "fixture_extrinsics.example.yaml")),
        OpaqueFunction(function=_launch_setup),
    ])
