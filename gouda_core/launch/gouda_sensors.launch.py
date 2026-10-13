"""Sensor drivers ND-14 (hesai_ros_driver, XT-32) and ND-15 (adi_imu_driver, ADIS16607-2).

Started by gouda.sh (GOUDA_SENSORS=1) and kept running until gouda.sh stop: the drivers are NOT stopped/restarted on mode changes
because restarting the IMU driver has made the device unresponsive (docs/stage3_sensor_slam.md). They only publish data.

Arguments:
  params_dir  design/generated/params (PRM-50..56). trial:=true also loads <node>.trial.yaml (stub tests only, never the vehicle).
  run_dir     where the generated Hesai driver config is written (<run_dir>/hesai_ros_driver.config.yaml).
A driver whose settings are incomplete is NOT started; the missing parameter IDs are printed (RQ-I076: no silent defaults).
"""
import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

PRM = {'device_ip_address': 'PRM-50', 'host_ip_address': 'PRM-51', 'udp_port': 'PRM-52', 'ptc_port': 'PRM-53', 'use_timestamp_type': 'PRM-55',
       'device': 'PRM-54', 'rate': 'PRM-56'}


def _nodes(context, *args, **kwargs):
    from ament_index_python.packages import get_package_share_directory, PackageNotFoundError
    from gouda_core import sensor_config as sc
    params_dir = LaunchConfiguration('params_dir').perform(context)
    run_dir = os.path.expanduser(LaunchConfiguration('run_dir').perform(context))
    trial = LaunchConfiguration('trial').perform(context).lower() in ('1', 'true', 'yes')
    actions = []
    # ---- ND-14 XT-32 ----
    try:
        template = sc.find_template(get_package_share_directory('hesai_ros_driver'))
    except PackageNotFoundError:
        template = None
    if template is None:
        actions.append(LogInfo(msg='[gouda_sensors] hesai_ros_driver is not installed (no share/hesai_ros_driver/config/config.yaml): XT-32 NOT started'))
    else:
        out = os.path.join(run_dir, 'hesai_ros_driver.config.yaml')
        missing = sc.write_hesai_config(template, sc.read_node_params(params_dir, 'hesai_ros_driver', trial), out)
        if missing:
            actions.append(LogInfo(msg=f'[gouda_sensors] XT-32 NOT started: unresolved {[f"{k} ({PRM[k]})" for k in missing]} in {params_dir}/hesai_ros_driver.yaml'))
        else:
            actions.append(Node(package='hesai_ros_driver', executable='hesai_ros_driver_node', name='hesai_ros_driver', output='screen',
                                parameters=[{'config_path': out}]))
    # ---- ND-15 IMU ----
    p, missing = sc.imu_parameters(sc.read_node_params(params_dir, 'adi_imu_driver', trial))
    if missing:
        actions.append(LogInfo(msg=f'[gouda_sensors] IMU NOT started: unresolved {[f"{k} ({PRM[k]})" for k in missing]} in {params_dir}/adi_imu_driver.yaml'))
    else:
        actions.append(Node(package='adi_imu_tr_driver_ros2', executable='adis_rcv_bin_node', name='adi_imu_driver', output='screen',
                            parameters=[p], remappings=[(sc.IMU_DRIVER_TOPIC, sc.IMU_TOPIC)]))
    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('params_dir', description='design/generated/params directory'),
        DeclareLaunchArgument('run_dir', description='directory for the generated Hesai driver config'),
        DeclareLaunchArgument('trial', default_value='false', description='load <node>.trial.yaml (stub tests only, never the vehicle)'),
        OpaqueFunction(function=_nodes),
    ])
