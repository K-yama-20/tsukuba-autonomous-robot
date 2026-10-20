"""Sensor drivers ND-14 (hesai_ros_driver, XT-32), ND-15 (adi_imu_driver, ADIS16607-2) and ND-19 (septentrio_gnss_driver, mosaic-go)
under gouda_sensor_supervisor (ND-18).

Always started by gouda_core.launch.py (the one start path gouda.sh; DEC-090). The supervisor starts each driver when its device is present and re-creates a driver
ONLY when its device is re-connected (new USB enumeration / re-registered network interface). It never restarts a driver for
the same device, because restarting the IMU driver without a re-plug leaves the IMU unresponsive (DEC-088,
docs/sensor_supervision.md). Mode changes do not stop or restart the drivers.

Arguments:
  params_dir  design/generated/params (PRM-50..56, PRM-59). trial:=true also loads <node>.trial.yaml (stub tests only, never the vehicle).
  run_dir     generated Hesai driver config, GNSS driver parameters and the device identities of the session (sensor_devices.json).
  config_dir  <data_root>/config: the human's private gnss_rtk.yaml (RTK corrections account; never in the repository).
A driver whose settings are incomplete is not started; the supervisor records which parameter is missing (RQ-I076).
"""
import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _nodes(context, *args, **kwargs):
    params_dir = LaunchConfiguration('params_dir').perform(context)
    run_dir = os.path.expanduser(LaunchConfiguration('run_dir').perform(context))
    config_dir = os.path.expanduser(LaunchConfiguration('config_dir').perform(context))
    trial = LaunchConfiguration('trial').perform(context).lower() in ('1', 'true', 'yes')
    files = [os.path.join(params_dir, n) for n in ['gouda_sensor_supervisor.yaml'] + (['gouda_sensor_supervisor.trial.yaml'] if trial else [])]
    import yaml
    def usable(path):
        try:
            with open(path, encoding='utf-8') as f:
                return bool(((yaml.safe_load(f) or {}).get('gouda_sensor_supervisor') or {}).get('ros__parameters'))
        except OSError:
            return False
    return [Node(package='gouda_core', executable='gouda_sensor_supervisor', name='gouda_sensor_supervisor', output='screen',
                 parameters=[f for f in files if usable(f)] + [{'params_dir': params_dir, 'run_dir': run_dir, 'config_dir': config_dir, 'trial': trial}])]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('params_dir', description='design/generated/params directory'),
        DeclareLaunchArgument('run_dir', description='directory for the generated Hesai driver config and sensor_devices.json'),
        DeclareLaunchArgument('config_dir', description='<data_root>/config (private gnss_rtk.yaml)'),
        DeclareLaunchArgument('trial', default_value='false', description='load <node>.trial.yaml (stub tests only, never the vehicle)'),
        OpaqueFunction(function=_nodes),
    ])
