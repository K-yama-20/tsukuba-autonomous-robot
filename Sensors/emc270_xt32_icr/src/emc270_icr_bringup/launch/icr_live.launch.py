import math
import os

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, TimerAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _enabled(context, name):
    return LaunchConfiguration(name).perform(context).lower() in {
        "1", "true", "yes", "on"
    }


def _contains_required(value):
    if isinstance(value, str):
        return "REQUIRED" in value
    if isinstance(value, dict):
        return any(_contains_required(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_required(item) for item in value)
    return False


def _load_yaml(path, label):
    if not os.path.isabs(path) or not os.path.isfile(path):
        raise RuntimeError(f"{label} must be an existing absolute path: {path}")
    with open(path, encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    if not isinstance(data, dict) or _contains_required(data):
        raise RuntimeError(f"{label} still contains REQUIRED placeholders: {path}")
    return data


def _validate_inspection(inspection):
    horizontal = inspection.get("horizontal_origin_tolerance_m")
    angular = inspection.get("axis_angle_tolerance_rad")
    if not isinstance(horizontal, (int, float)) or not math.isfinite(horizontal) or \
            not 0.0 <= horizontal <= 0.002:
        raise RuntimeError("Fixture horizontal tolerance must be within 0..0.002 m")
    if not isinstance(angular, (int, float)) or not math.isfinite(angular) or \
            not 0.0 <= angular <= 0.003491:
        raise RuntimeError("Fixture axis-angle tolerance must be within 0..0.003491 rad")


def _validate_hesai(config):
    lidars = config.get("lidar")
    if not isinstance(lidars, list) or len(lidars) != 1:
        raise RuntimeError("Hesai config must contain exactly one lidar")
    driver = lidars[0].get("driver", {})
    ros = lidars[0].get("ros", {})
    required_values = {
        "source_type": 1,
        "use_timestamp_type": 0,
        "transform_flag": False,
        "distance_correction_flag": True,
        "frame_frequency": 20.0,
    }
    for key, expected in required_values.items():
        if driver.get(key) != expected:
            raise RuntimeError(f"Hesai {key} must be {expected!r}")
    if ros.get("ros_frame_id") != "hesai_lidar_native":
        raise RuntimeError("Hesai ros_frame_id must be hesai_lidar_native")
    if ros.get("ros_send_point_cloud_topic") != "/lidar_points" or \
            ros.get("send_point_cloud_ros") is not True:
        raise RuntimeError("Hesai must publish /lidar_points")
    udp = driver.get("lidar_udp_type", {})
    for key in ("device_ip_address", "host_ip_address"):
        if not isinstance(udp.get(key), str) or not udp[key]:
            raise RuntimeError(f"Hesai {key} is required")
    for key in ("correction_file_path", "firetimes_path"):
        path = udp.get(key)
        if not isinstance(path, str) or not os.path.isabs(path) or not os.path.isfile(path):
            raise RuntimeError(f"Hesai {key} must be an existing absolute file: {path}")


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
        package="tf2_ros",
        executable="static_transform_publisher",
        name=f"static_{parent}_to_{child}",
        arguments=[
            "--x", str(xyz[0]), "--y", str(xyz[1]), "--z", str(xyz[2]),
            "--roll", str(rpy[0]), "--pitch", str(rpy[1]), "--yaw", str(rpy[2]),
            "--frame-id", parent, "--child-frame-id", child,
        ],
    )


def _launch_setup(context):
    share = get_package_share_directory("emc270_icr_bringup")
    fixture_path = LaunchConfiguration("fixture_config").perform(context)
    fixture = _load_yaml(fixture_path, "fixture_config")
    frames = fixture.get("frames", {})
    inspection = fixture.get("inspection", {})
    _validate_inspection(inspection)
    native = frames["xt32_to_native"]
    imu = frames["xt32_to_imu"]
    if math.sqrt(sum(float(value) ** 2 for value in native["translation_m"])) > 1.0e-6:
        raise RuntimeError("xt32_link and hesai_lidar_native must share one geometric origin")

    actions = [
        _six_dof_node("xt32_link", "hesai_lidar_native", native),
        _six_dof_node("xt32_link", "imu_link", imu),
    ]

    if _enabled(context, "start_hesai"):
        hesai_path = LaunchConfiguration("hesai_config").perform(context)
        hesai_config = _load_yaml(hesai_path, "hesai_config")
        _validate_hesai(hesai_config)
        # KISS-ICP v1.3.0 falls back to an identity extrinsic if the static TF
        # is not available on its first scan. Start the sensor after both the
        # static publisher and KISS have had time to receive /tf_static.
        actions.append(TimerAction(period=1.0, actions=[Node(
            package="hesai_ros_driver",
            executable="hesai_ros_driver_node",
            name="hesai_ros_driver_node",
            output="screen",
            parameters=[{"config_path": hesai_path}],
        )]))

    if _enabled(context, "start_imu"):
        actions.append(Node(
            package="adi_imu_tr_driver_ros2",
            executable="adis_rcv_bin_node",
            name="adi_rcv_bin_node",
            output="screen",
            parameters=[
                os.path.join(share, "config", "imu.yaml"),
                {
                    "device": LaunchConfiguration("imu_device").perform(context),
                    "frame_id": "imu_link",
                    "publish_tf": False,
                },
            ],
        ))

    if _enabled(context, "start_kiss"):
        actions.append(TimerAction(period=0.5, actions=[Node(
            package="kiss_icp",
            executable="kiss_icp_node",
            name="kiss_icp_node",
            output="screen",
            remappings=[("pointcloud_topic", "/lidar_points")],
            parameters=[
                os.path.join(share, "config", "kiss_icp.yaml"),
                {
                    "base_frame": "xt32_link",
                    "lidar_odom_frame": "odom_lidar",
                    "publish_odom_tf": False,
                    "invert_odom_tf": True,
                    "publish_debug_clouds": False,
                    "use_sim_time": False,
                },
            ],
        )]))

    imu_translation = imu["translation_m"]
    imu_rotation = imu["rotation_rpy_rad"]
    actions.append(Node(
        package="emc270_icr_estimator",
        executable="icr_estimator_node",
        name="emc270_icr_estimator",
        output="screen",
        remappings=[("/diagnostics", "/icr/diagnostics")],
        parameters=[
            os.path.join(share, "config", "estimator.yaml"),
            {
                "fixture.imu_x_m": float(imu_translation[0]),
                "fixture.imu_y_m": float(imu_translation[1]),
                "fixture.imu_roll_rad": float(imu_rotation[0]),
                "fixture.imu_pitch_rad": float(imu_rotation[1]),
                "fixture.imu_yaw_rad": float(imu_rotation[2]),
                "fixture.xy_sigma_m": float(
                    inspection["horizontal_origin_tolerance_m"]),
                "fixture.axis_angle_sigma_rad": float(
                    inspection["axis_angle_tolerance_rad"]),
                "use_sim_time": False,
            },
        ],
    ))
    return actions


def generate_launch_description():
    share = get_package_share_directory("emc270_icr_bringup")
    return LaunchDescription([
        DeclareLaunchArgument(
            "hesai_config",
            default_value=os.path.join(share, "config", "hesai_xt32.example.yaml")),
        DeclareLaunchArgument(
            "fixture_config",
            default_value=os.path.join(share, "config", "fixture_extrinsics.example.yaml")),
        DeclareLaunchArgument("imu_device", default_value="/dev/ttyACM0"),
        DeclareLaunchArgument("start_hesai", default_value="true"),
        DeclareLaunchArgument("start_imu", default_value="true"),
        DeclareLaunchArgument("start_kiss", default_value="true"),
        OpaqueFunction(function=_launch_setup),
    ])
